# Native
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

# Django
import django
import llama_cpp

# Third Party
import psutil
import redis
from django.conf import settings as dj_settings
from llama_cpp import Llama

# Cache the result of llama-cpp-python (one time inference)
_cached_llama_result = None


def check_redis_channel():
    """
    Checks Redis connectivity and returns health with version.
    """
    try:
        r = redis.Redis(host="127.0.0.1", port=6379, db=0)
        pong = r.ping()
        info = r.info()
        return {
            "status": "ok" if pong else "fail",
            "version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", "n/a"),
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def check_cpu():
    """
    Collect CPU utilization, model and core information (with Linux model fallback).
    """
    try:
        usage_percent = psutil.cpu_percent(interval=0.5)
        core_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0.0

        # Try platform first, then fallback to /proc/cpuinfo on Linux
        cpu_model = platform.processor() or platform.uname().machine
        if cpu_model in ("x86_64", "AMD64", ""):
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.strip().split(":")[1].strip()
                        break

        return {
            "status": "ok",
            "model": cpu_model,
            "usage_percent": usage_percent,
            "cores": core_count,
            "speed_mhz": round(cpu_freq, 1),
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def check_memory():
    """
    Report memory usage, capacity, and device information.
    """
    try:
        mem = psutil.virtual_memory()
        total_gb = round(mem.total / (1024**3), 2)
        used_gb = round(mem.used / (1024**3), 2)
        return {
            "status": "ok",
            "used_gb": used_gb,
            "total_gb": total_gb,
            "percent": mem.percent,
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def check_gpu():
    """
    Query GPU details using nvidia-smi for model, utilization, and memory.
    """
    try:
        # Ask nvidia-smi for GPU name and usage details
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        lines = [x.strip() for x in result.stdout.strip().splitlines() if x.strip()]
        gpus = []

        for idx, line in enumerate(lines):
            # Parse each CSV line: "Name, util, mem_used, mem_total" (skip if malformed, < 4)
            fields = line.split(",")
            parts = [x.strip() for x in fields] if len(fields) == 4 else []

            name = parts[0]
            util = float(parts[1])
            mem_used = float(parts[2])
            mem_total = float(parts[3])

            gpus.append(
                {
                    "id": idx,
                    "name": name,
                    "utilization_percent": util,
                    "memory_used_gb": round(mem_used / 1024, 2),
                    "memory_total_gb": round(mem_total / 1024, 2),
                },
            )

        return {
            "status": "ok" if gpus else "no_gpu",
            "count": len(gpus),
            "devices": gpus,
        }

    except FileNotFoundError:
        return {"status": "no_gpu", "message": "nvidia-smi not found"}
    except Exception as e:
        return {"status": "fail", "error": str(e)}


def get_driver_and_cuda_from_smi():
    """
    From the nvidia-smi base banner get the cuda runtime support and driver version.
    """
    try:
        smi = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            check=True,
        )

        output = smi.stdout

        # Regex patterns that match ONLY the intended fields
        driver_match = re.search(r"Driver Version:\s+([0-9.]+)", output)
        cuda_match = re.search(r"CUDA Version:\s+([0-9.]+)", output)

        driver_version = driver_match.group(1) if driver_match else "unavailable"
        cuda_version = cuda_match.group(1) if cuda_match else "unavailable"

        return driver_version, cuda_version

    except subprocess.CalledProcessError:
        return "unable to run check for driver", "unable to run check for driver"
    except FileNotFoundError:
        return "driver_version_unavailable", "cuda_version_unavailable"


def get_system_cuda_runtime():
    """
    Queries /usr/local/cuda/version.json for CUDA Runtime (libcudart).
    """
    version_json = Path("/usr/local/cuda/version.json")

    if version_json.exists():
        try:
            with open(version_json) as f:
                data = json.load(f)

            # We want the libcudart version:
            return data.get("cuda_cudart", {}).get("version", "unavailable")
        except Exception:
            pass

    return "cuda_runtime_unavailable"


def check_runtime_versions():
    """
    Returns versions including Python, Django, llama-cpp-python, NVIDIA driver/CUDA runtime and system CUDA runtime.
    """
    # llama-cpp-python version
    try:
        llama_version = getattr(llama_cpp, "__version__", "unknown")
    except AttributeError:
        llama_version = "not installed"

    # Extract from the nvidia-smi banner header
    driver_version, driver_cuda_runtime = get_driver_and_cuda_from_smi()

    # System CUDA runtime (actual libcudart.so version)
    system_cuda_runtime = get_system_cuda_runtime()

    return {
        "python": platform.python_version(),
        "django": django.get_version(),
        "llama_cpp_python": llama_version,
        "nvidia_driver": driver_version,
        "cuda_runtime_driver": driver_cuda_runtime,
        "cuda_runtime_system": system_cuda_runtime,
    }


def full_health_summary(app_name, app_env, app_version, app_build, debug=False):
    """
    Aggregate all health metrics.
    """
    return {
        "timestamp": time.time(),
        "app": {
            "name": app_name,
            "env": app_env,
            "version": app_version,
            "build": app_build,
            "debug": debug,
        },
        "dependencies": {
            "redis": check_redis_channel(),
        },
        "system": {
            "cpu": check_cpu(),
            "memory": check_memory(),
            "gpu": check_gpu(),
        },
        "runtime": check_runtime_versions(),
        "llama": get_cached_llama_result(),
    }


def get_cached_llama_result():
    global _cached_llama_result
    if _cached_llama_result is None:
        _cached_llama_result = smoke_test_llama()
    return _cached_llama_result


def smoke_test_llama():
    """
    Run a minimal inference to check llama-cpp-python's access to the GGUF model.
    """
    start = time.time()
    try:
        # Base directory grab
        base_dir = Path(__file__).resolve().parent.parent

        model_name = dj_settings.GGUF_FILE_NAME
        full_model_path = os.path.join(base_dir, "models", model_name)
        llm = Llama(model_path=full_model_path, n_threads=4, verbose=False)
        load_time = round(time.time() - start, 2)

        # Check that llama-cpp-python (in notebook) can find the gpu
        result = subprocess.run(
            [
                "bash",
                "-c",
                f"python -c \"from llama_cpp import Llama; " f"Llama(model_path='{full_model_path}', n_gpu_layers=1, verbose=True)\" 2>&1 " "| grep 'Device'",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        captured_output = result.stdout

        gpu_devices_found = [line for line in captured_output.splitlines() if "Device" in line]

        joined_devices = "\n".join(gpu_devices_found)

        # Make a basic inquisitive question for the model to answer
        question = "What type model are you?"
        prompt = f"You explain what type of large language model you are. Q: {question}\nA:"
        output = llm(
            prompt,
            max_tokens=40,
            stop=["[/INST]", "</s>", "[INST]"],
        )
        text = output["choices"][0]["text"].strip()

        # Clean up artifacts like "Q:" or "A:"
        text = text.split("Q:")[0].strip().replace("\n", " ")

        return {
            "gpu_used": joined_devices,
            "status": "ok",
            "model_name": model_name,
            "load_time_sec": load_time,
            "sample_output": f"Question {question}. {text}",
        }
    except Exception as e:
        return {"status": "fail", "error": str(e)}
