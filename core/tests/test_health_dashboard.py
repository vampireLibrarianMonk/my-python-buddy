# Native
import re
import secrets
import subprocess
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

# Django
from django.urls import reverse
from django.utils.crypto import get_random_string

# Models
from base_application.models import AccountProfile

# Core Health
from core.health import (
    check_cpu,
    check_gpu,
    check_memory,
    check_redis_channel,
    check_runtime_versions,
    get_driver_and_cuda_from_smi,
    get_system_cuda_runtime,
    smoke_test_llama,
)


class HealthcheckViewTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()

        # Use environment overrides when provided; otherwise generate deterministic-safe test values.
        username = f"tester_{get_random_string(8)}"
        email = f"{get_random_string(6)}@example.invalid"
        old_password = secrets.token_urlsafe(16)

        self.user = User.objects.create_superuser(
            username=username,
            email=email,
            password=old_password,
        )

        self.old_password = old_password  # keep for the form

        self.profile = AccountProfile.objects.get(user=self.user)
        self.profile.must_change_password = False
        self.profile.save()

    def test_healthcheck_view_renders_ok(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("healthz"), follow=True)
        self.assertEqual(response.status_code, 200)

        # The view converts timestamp to datetime
        summary = response.context["summary"]

        # Application Section
        app = summary["app"]

        # Required Keys
        for key in ["name", "env", "version", "build", "debug"]:
            self.assertIn(key, app)

        # Name is non-empty
        self.assertIsInstance(app["name"], str)
        self.assertTrue(app["name"].strip())

        # Environment non-empty
        self.assertIsInstance(app["env"], str)
        self.assertTrue(app["env"].strip())

        # Version pattern (e.g., 1.0.0)
        version_pattern = re.compile(r"^\d+(?:\.\d+){1,3}$")
        self.assertIsInstance(app["version"], str)
        self.assertRegex(app["version"], version_pattern)

        # Build type
        self.assertIsInstance(app["build"], str)
        self.assertIn(app["build"], ["cloud", "local"])

        # Debug (change to enforce prior to deployment)
        self.assertIsInstance(app["debug"], bool)

        # REDIS Section
        redis = summary["dependencies"]["redis"]

        # Required Keys
        for key in ["status", "version", "connected_clients"]:
            self.assertIn(key, redis)

        # Status is non-empty
        self.assertIsInstance(redis["status"], str)
        self.assertTrue(redis["status"].strip())

        # Semantic Versioning
        version_pattern = re.compile(r"^\d+(?:\.\d+){1,3}$")
        self.assertIsInstance(redis["version"], str)
        self.assertRegex(redis["version"], version_pattern)

        # Number of connected clients (>0)
        self.assertIsInstance(redis["connected_clients"], int)
        self.assertGreaterEqual(redis["connected_clients"], 0)

        # CPU Section
        cpu = summary["system"]["cpu"]

        # Required Keys
        for key in ["status", "model", "usage_percent", "cores", "speed_mhz"]:
            self.assertIn(key, cpu)

        # Status non-empty
        self.assertIsInstance(cpu["status"], str)
        self.assertTrue(cpu["status"].strip())

        # Model non-empty
        self.assertIsInstance(cpu["model"], str)
        self.assertTrue(cpu["model"].strip())

        # Usage Percent float or int, between 0–100
        self.assertIsInstance(cpu["usage_percent"], (int, float))
        self.assertGreaterEqual(cpu["usage_percent"], 0)
        self.assertLessEqual(cpu["usage_percent"], 100)

        # Core count integer ≥ 1
        self.assertIsInstance(cpu["cores"], int)
        self.assertGreaterEqual(cpu["cores"], 1)

        # Speed MHZ numeric ≥ 0
        self.assertIsInstance(cpu["speed_mhz"], (int, float))
        self.assertGreater(cpu["speed_mhz"], 0)

        # Memory Section
        memory = summary["system"]["memory"]

        # Required Keys
        for key in ["status", "used_gb", "total_gb", "percent"]:
            self.assertIn(key, memory)

        # Status non-empty
        self.assertIsInstance(memory["status"], str)
        self.assertTrue(memory["status"].strip())

        # Used GB ≥ 0
        self.assertIsInstance(memory["used_gb"], (int, float))
        self.assertGreaterEqual(memory["used_gb"], 0)

        # Total GB > 0
        self.assertIsInstance(memory["total_gb"], (int, float))
        self.assertGreater(memory["total_gb"], 0)

        # Logic: used_gb cannot exceed total_gb
        self.assertLessEqual(memory["used_gb"], memory["total_gb"])

        # Usage Percent between 0–100
        self.assertIsInstance(memory["percent"], (int, float))
        self.assertGreaterEqual(memory["percent"], 0)
        self.assertLessEqual(memory["percent"], 100)

        # GPU Section
        gpu = summary["system"]["gpu"]

        # Required Keys
        for key in ["status", "count", "devices"]:
            self.assertIn(key, gpu)

        # Status non-empty
        self.assertIsInstance(gpu["status"], str)
        self.assertTrue(gpu["status"].strip())

        # Count, integer ≥ 0
        self.assertIsInstance(gpu["count"], int)
        self.assertGreaterEqual(gpu["count"], 0)

        # Device list, length must match count (when count > 0)
        self.assertIsInstance(gpu["devices"], list)

        self.assertGreater(len(gpu["devices"]), 0)
        self.assertEqual(len(gpu["devices"]), gpu["count"])

        # Device entry validation
        for device in gpu["devices"]:
            # required keys
            for dk in ["id", "name", "utilization_percent", "memory_used_gb", "memory_total_gb"]:
                self.assertIn(dk, device)

            # Device ID, integer ≥ 0
            self.assertIsInstance(device["id"], int)
            self.assertGreaterEqual(device["id"], 0)

            # Name non-empty
            self.assertIsInstance(device["name"], str)
            self.assertTrue(device["name"].strip())

            # Utilization percent, (int, float)) between 0–100
            self.assertIsInstance(device["utilization_percent"], (int, float))
            self.assertGreaterEqual(device["utilization_percent"], 0)
            self.assertLessEqual(device["utilization_percent"], 100)

            # Memory Used & Total
            self.assertIsInstance(device["memory_used_gb"], (int, float))
            self.assertIsInstance(device["memory_total_gb"], (int, float))

            self.assertGreater(device["memory_total_gb"], 0)
            self.assertGreaterEqual(device["memory_used_gb"], 0)
            self.assertLessEqual(device["memory_used_gb"], device["memory_total_gb"])

        # Runtime Section
        runtime = summary["runtime"]

        # Check for presence of keys in runtime
        for key in [
            "python",
            "django",
            "llama_cpp_python",
            "nvidia_driver",
            "cuda_runtime_driver",
            "cuda_runtime_system",
        ]:
            self.assertIn(key, runtime)

        # Abstract version check: digits.digits(.digits)(.digits)
        version_pattern = re.compile(r"^\d+(?:\.\d+){1,3}$")

        for key in runtime:
            value = runtime[key]
            self.assertIsInstance(value, str)
            self.assertRegex(
                value,
                version_pattern,
                msg=f"Runtime field '{key}' does not match version pattern: {value}",
            )

        # Llama Section
        llama = summary["llama"]

        # Check for presence of keys in llama
        for key in [
            "gpu_used",
            "status",
            "model_name",
            "load_time_sec",
            "sample_output",
        ]:
            self.assertIn(key, llama)

        # gpu_used to non-empty string
        self.assertIsInstance(llama["gpu_used"], str)
        self.assertTrue(llama["gpu_used"].strip())

        # Status, string
        self.assertIsInstance(llama["status"], str)
        self.assertTrue(len(llama["status"]) > 0)

        # Model string check must end in .gguf
        self.assertIsInstance(llama["model_name"], str)
        self.assertTrue(llama["model_name"])
        self.assertTrue(
            llama["model_name"].lower().endswith(".gguf"),
            msg=f"Model name must end with .gguf, got: {llama['model_name']}",
        )

        # Model load time, float > 0
        self.assertIsInstance(llama["load_time_sec"], (float, int))
        self.assertGreater(llama["load_time_sec"], 0)

        # Sample output, string non-empty
        self.assertIsInstance(llama["sample_output"], str)
        self.assertTrue(llama["sample_output"].strip())


class TestHealthFailures(TestCase):

    def test_check_redis_channel_failure(self):
        with patch("redis.Redis.ping", side_effect=Exception("fail")):
            result = check_redis_channel()
            self.assertEqual(result["status"], "fail")

    def test_check_cpu_failure(self):
        with patch("psutil.cpu_percent", side_effect=Exception("cpu_fail")):
            result = check_cpu()
            self.assertEqual(result["status"], "fail")

    def test_check_memory_failure(self):
        with patch("psutil.virtual_memory", side_effect=Exception("mem_fail")):
            result = check_memory()
            self.assertEqual(result["status"], "fail")

    def test_check_gpu_file_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = check_gpu()
            self.assertEqual(result["status"], "no_gpu")

    def test_check_gpu_generic_exception(self):
        with patch("subprocess.run", side_effect=Exception("gpu_fail")):
            result = check_gpu()
            self.assertEqual(result["status"], "fail")

    def test_driver_called_process_error(self):
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        ):
            driver, cuda = get_driver_and_cuda_from_smi()
            self.assertEqual(driver, "unable to run check for driver")
            self.assertEqual(cuda, "unable to run check for driver")

    def test_driver_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            driver, cuda = get_driver_and_cuda_from_smi()
            self.assertEqual(driver, "driver_version_unavailable")
            self.assertEqual(cuda, "cuda_version_unavailable")

    def test_system_cuda_json_failure(self):
        with patch("pathlib.Path.exists", return_value=True), patch("builtins.open", side_effect=Exception("json_fail")):
            result = get_system_cuda_runtime()
            self.assertEqual(result, "cuda_runtime_unavailable")

    def test_check_runtime_version_llama_attribute_error(self):
        with patch("core.health.getattr", side_effect=AttributeError()):
            result = check_runtime_versions()
            self.assertEqual(result["llama_cpp_python"], "not installed")

    def test_smoke_test_llama_failure(self):
        with patch("core.health.smoke_test_llama", side_effect=Exception("llama_fail")), patch("core.health.subprocess.run", side_effect=Exception("smi_fail")):
            result = smoke_test_llama()
            self.assertEqual(result["status"], "fail")
