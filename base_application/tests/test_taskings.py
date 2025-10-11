# Native
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile

# Django
from django.test import TestCase, override_settings
from django.utils import timezone

# Model
from base_application.models import Finding, Run, SubmittedFile

# Tasking
from base_application.taskings import run_analyzer_task

# Define paths for loading the known vulnerable test file
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_files")
TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"])
class TaskingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        # Clean up the temporary media directory after all tests run
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        # Load a clean file
        with open(os.path.join(SAMPLE_DIR, "sample.py"), "rb") as f:
            clean = SimpleUploadedFile("sample.py", f.read(), content_type="text/x-python")

        # Load vulnerable file series for each analyzer
        with open(os.path.join(SAMPLE_DIR, "bandit_ringer_test.py"), "rb") as f:
            vuln_bandit = SimpleUploadedFile("bandit_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "dodgy_ringer_test.py"), "rb") as f:
            vuln_dodgy = SimpleUploadedFile("dodgy_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "mypy_ringer_test.py"), "rb") as f:
            vuln_mypy = SimpleUploadedFile("mypy_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "semgrep_ringer_test.py"), "rb") as f:
            vuln_semgrep = SimpleUploadedFile("semgrep_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "vulture_ringer_test.py"), "rb") as f:
            vuln_vulture = SimpleUploadedFile("vulture_ringer_test.py", f.read(), content_type="text/x-python")

        # Assign clean file
        self.clean_file = SubmittedFile.objects.create(
            sha256="sha256_clean",
            saved_name="sample.py",
            original_name="sample.py",
            file=clean,
        )
        # Assign vulnerable file series for each analyzer
        self.vuln_file_bandit = SubmittedFile.objects.create(
            sha256="sha256_vuln_bandit",
            saved_name="bandit_ringer_test.py",
            original_name="bandit_ringer_test.py",
            file=vuln_bandit,
        )
        self.vuln_file_dodgy = SubmittedFile.objects.create(
            sha256="sha256_vuln_dodgy",
            saved_name="dodgy_ringer_test.py",
            original_name="dodgy_ringer_test.py",
            file=vuln_dodgy,
        )
        self.vuln_file_mypy = SubmittedFile.objects.create(
            sha256="sha256_vuln_mypy",
            saved_name="mypy_ringer_test.py",
            original_name="mypy_ringer_test.py",
            file=vuln_mypy,
        )
        self.vuln_file_semgrep = SubmittedFile.objects.create(
            sha256="sha256_vuln_semgrep",
            saved_name="semgrep_ringer_test.py",
            original_name="semgrep_ringer_test.py",
            file=vuln_semgrep,
        )
        self.vuln_file_vulture = SubmittedFile.objects.create(
            sha256="sha256_vuln_vulture",
            saved_name="vulture_ringer_test.py",
            original_name="vulture_ringer_test.py",
            file=vuln_vulture,
        )

    # Run specific analyzer task for status update and findings count greater than 0 (exact checks in test_analyzers.py)
    # Test Specification Location: documentation/test/unit/UT-11-19.md

    def test_run_analyzer_task_executes_bandit(self):
        # Running a Bandit analyzer task should mark the run as completed and create findings
        run = Run.objects.create(
            submitted_file=self.vuln_file_bandit,
            analyzer="bandit",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertGreater(run.findings.count(), 0)
        self.assertTrue(Finding.objects.filter(run=run).exists())

    def test_run_analyzer_task_executes_dodgy(self):
        # Running a Dodgy analyzer task should mark the run as completed and create findings
        run = Run.objects.create(
            submitted_file=self.vuln_file_dodgy,
            analyzer="dodgy",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertGreater(run.findings.count(), 0)
        self.assertTrue(Finding.objects.filter(run=run).exists())

    def test_run_analyzer_task_executes_mypy(self):
        # Running a MyPy analyzer task should mark the run as completed and create findings
        run = Run.objects.create(
            submitted_file=self.vuln_file_mypy,
            analyzer="mypy",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertGreater(run.findings.count(), 0)
        self.assertTrue(Finding.objects.filter(run=run).exists())

    def test_run_analyzer_task_executes_semgrep(self):
        # Running a Semgrep analyzer task should mark the run as completed and create findings.
        run = Run.objects.create(
            submitted_file=self.vuln_file_semgrep,
            analyzer="semgrep",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertGreater(run.findings.count(), 0)
        self.assertTrue(Finding.objects.filter(run=run).exists())

    def test_run_analyzer_task_executes_vulture(self):
        # Running a Vulture analyzer task should mark the run as completed and create findings.
        run = Run.objects.create(
            submitted_file=self.vuln_file_vulture,
            analyzer="vulture",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertGreater(run.findings.count(), 0)
        self.assertTrue(Finding.objects.filter(run=run).exists())

    def test_run_analyzer_task_with_unknown_analyzer(self):
        # Running an unknown analyzer task with an unsupported analyzer should mark the run as errored with no findings.
        run = Run.objects.create(
            submitted_file=self.clean_file,
            analyzer="fake_tool",
            status=Run.Status.REQUESTED,
            started_at=timezone.now(),
        )
        run_analyzer_task(run.id, run.analyzer)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.ERRORED)
        self.assertEqual(run.findings.count(), 0)
