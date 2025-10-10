# Native
import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

# Django
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

# Models
from base_application.models import AccountProfile, Run, SubmittedFile

# Forms
from ..forms import AnalyzerSelectForm

# Comma-separated list in environment file, falls back to "*"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
ALLOWED_HOSTS.append("testserver")

MEDIA_URL_ENV = os.getenv("DJANGO_MEDIA_URL", "/media/")

# Temporary media root for these tests
TEMP_MEDIA = tempfile.mkdtemp()

# Define path to sample files for known good and vulnerable test inputs
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_files")


@override_settings(
    MEDIA_ROOT=TEMP_MEDIA,
    MEDIA_URL=MEDIA_URL_ENV,
    ALLOWED_HOSTS=list(ALLOWED_HOSTS),
    SECURE_SSL_REDIRECT=False,
)
class AnalyzeFileViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        # Remove the temporary media directory once all tests in this class have finished
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        # Create a test user, disable forced password change→ and log in so protected views can be accessed
        user = get_user_model()
        username = os.getenv("TEST_USERNAME", "tester")
        email = os.getenv("TEST_EMAIL", "tester@example.com")
        password = os.getenv("TEST_PASSWORD", "pass1234!")
        self.user = user.objects.create_user(username, email, password)

        prof, _ = AccountProfile.objects.get_or_create(user=self.user)
        if prof.must_change_password:
            prof.must_change_password = False
            prof.save(update_fields=["must_change_password"])

        self.client.login(username=username, password=password)

        # Load both a clean file and a vulnerable file into the database as SubmittedFile objects
        with open(os.path.join(SAMPLE_DIR, "sample.py"), "rb") as f:
            clean = SimpleUploadedFile("sample.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "bandit_ringer_test.py"), "rb") as f:
            vuln = SimpleUploadedFile("bandit_ringer_test.py", f.read(), content_type="text/x-python")

        self.clean_file = SubmittedFile.objects.create(
            sha256="sha256_clean",
            saved_name="sample.py",
            original_name="sample.py",
            file=clean,
        )
        self.vuln_file = SubmittedFile.objects.create(
            sha256="sha256_vuln",
            saved_name="bandit_ringer_test.py",
            original_name="bandit_ringer_test.py",
            file=vuln,
        )

    # Tests for analyze_file_view
    # Test Specification Location: documentation/test/unit/UT-11-14.md

    # GET requests
    def test_analyze_file_view_get_prefills_form(self):
        # A GET request should render the form prefilled with file metadata
        resp = self.client.get(reverse("analyze_file", args=[self.clean_file.sha256]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.clean_file.saved_name)
        self.assertContains(resp, "form")

    # POST requests with invalid input
    def test_analyze_file_view_post_invalid(self):
        # Submitting no analyzers should redirect back with a validation error
        resp = self.client.post(reverse("analyze_file", args=[self.clean_file.sha256]), data={})
        self.assertRedirects(resp, reverse("analyze_file", args=[self.clean_file.sha256]))
        messages = list(resp.wsgi_request._messages)
        self.assertTrue(any("Please choose at least one analyzer" in str(m) for m in messages))

    # POST requests with valid input
    def test_analyze_file_view_post_creates_runs(self):
        # Gather all available analyzers from the form choices
        all_analyzers = [choice[0] for choice in AnalyzerSelectForm.ANALYZER_CHOICES]

        # Prepare valid POST payload
        payload = {
            "file_name": self.clean_file.saved_name,
            "analyzers": all_analyzers,
            "llm_notes": "full analyzer sweep",
        }

        # Submit POST request
        resp = self.client.post(
            reverse("analyze_file", args=[self.clean_file.sha256]),
            data=payload,
        )

        # Expect page reload (not redirect) with HTTP 200
        self.assertEqual(resp.status_code, 200)

        # Query all Run objects created for this file
        created_runs = Run.objects.filter(submitted_file=self.clean_file).order_by("analyzer")

        # Validate the number and names of analyzers created
        created_analyzers = list(created_runs.values_list("analyzer", flat=True))
        self.assertEqual(sorted(created_analyzers), sorted(all_analyzers))

        # Each run should be marked as REQUESTED
        for run in created_runs:
            self.assertEqual(run.status, Run.Status.REQUESTED)

        # Ensure the template context includes the selected analyzers
        self.assertIn("selected_analyzers", resp.context)
        self.assertEqual(sorted(resp.context["selected_analyzers"]), sorted(all_analyzers))

    # ---

    # Tests for the run_analyzer view
    # Test Specification Location: documentation/test/unit/UT-11-15.md

    def test_run_analyzer_requires_existing_run(self):
        # Without a preexisting Run object, the analyzer endpoint should return an error
        resp = self.client.post(reverse("run_analyzer", args=[self.clean_file.sha256, "bandit"]))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Error: Run not initialized", resp.json()["status"])

    def test_run_analyzer_marks_requested_and_returns_json(self):
        # With an existing Run, the endpoint should update its status and return queued JSON
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="bandit", status=Run.Status.PENDING)
        resp = self.client.post(reverse("run_analyzer", args=[self.clean_file.sha256, "bandit"]))
        self.assertEqual(resp.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(run.status, Run.Status.REQUESTED)
        self.assertEqual(resp.json()["status"], "Queued")

    # ---

    # Tests for the json view --> requested
    # Test Specification Location: documentation/test/unit/UT-11-16.md

    def test_bandit_status_json_reports_status(self):
        # When a bandit run exists, the JSON should reflect its status and findings count
        Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="bandit",
            status=Run.Status.COMPLETED,
            findings_count=3,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("bandit_status_json"))
        data = resp.json()
        self.assertIn(self.vuln_file.sha256, data)
        self.assertEqual(data[self.vuln_file.sha256]["status"], "COMPLETED")
        self.assertEqual(data[self.vuln_file.sha256]["findings_count"], 3)

    def test_dodgy_status_json_reports_status(self):
        # When a dodgy run exists, the JSON should reflect its status and findings count
        Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="dodgy",
            status=Run.Status.COMPLETED,
            findings_count=3,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("dodgy_status_json"))
        data = resp.json()
        self.assertIn(self.vuln_file.sha256, data)
        self.assertEqual(data[self.vuln_file.sha256]["status"], "COMPLETED")
        self.assertEqual(data[self.vuln_file.sha256]["findings_count"], 3)

    def test_mypy_status_json_reports_status(self):
        # When a mypy run exists, the JSON should reflect its status and findings count
        Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="mypy",
            status=Run.Status.COMPLETED,
            findings_count=3,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("mypy_status_json"))
        data = resp.json()
        self.assertIn(self.vuln_file.sha256, data)
        self.assertEqual(data[self.vuln_file.sha256]["status"], "COMPLETED")
        self.assertEqual(data[self.vuln_file.sha256]["findings_count"], 3)

    def test_semgrep_status_json_reports_status(self):
        # When a semgrep run exists, the JSON should reflect its status and findings count
        Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="semgrep",
            status=Run.Status.COMPLETED,
            findings_count=3,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("semgrep_status_json"))
        data = resp.json()
        self.assertIn(self.vuln_file.sha256, data)
        self.assertEqual(data[self.vuln_file.sha256]["status"], "COMPLETED")
        self.assertEqual(data[self.vuln_file.sha256]["findings_count"], 3)

    def test_vulture_status_json_reports_status(self):
        # When a vulture run exists, the JSON should reflect its status and findings count
        Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="vulture",
            status=Run.Status.COMPLETED,
            findings_count=3,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("vulture_status_json"))
        data = resp.json()
        self.assertIn(self.vuln_file.sha256, data)
        self.assertEqual(data[self.vuln_file.sha256]["status"], "COMPLETED")
        self.assertEqual(data[self.vuln_file.sha256]["findings_count"], 3)

    # ---

    # Tests for the json view not requested
    # Test Specification Location: documentation/test/unit/UT-11-17.md

    def test_bandit_status_json_reports_not_requested(self):
        # If no bandit run exists for a file, it should report as NOT_REQUESTED
        resp = self.client.get(reverse("bandit_status_json"))
        data = resp.json()
        self.assertEqual(data[self.clean_file.sha256]["status"], "NOT_REQUESTED")

    def test_dodgy_status_json_reports_not_requested(self):
        # If no dodgy run exists for a file, it should report as NOT_REQUESTED
        resp = self.client.get(reverse("dodgy_status_json"))
        data = resp.json()
        self.assertEqual(data[self.clean_file.sha256]["status"], "NOT_REQUESTED")

    def test_mypy_status_json_reports_not_requested(self):
        # If no mypy run exists for a file, it should report as NOT_REQUESTED
        resp = self.client.get(reverse("mypy_status_json"))
        data = resp.json()
        self.assertEqual(data[self.clean_file.sha256]["status"], "NOT_REQUESTED")

    def test_semgrep_status_json_reports_not_requested(self):
        # If no semgrep run exists for a file, it should report as NOT_REQUESTED
        resp = self.client.get(reverse("semgrep_status_json"))
        data = resp.json()
        self.assertEqual(data[self.clean_file.sha256]["status"], "NOT_REQUESTED")

    def test_vulture_status_json_reports_not_requested(self):
        # If no vulture run exists for a file, it should report as NOT_REQUESTED
        resp = self.client.get(reverse("vulture_status_json"))
        data = resp.json()
        self.assertEqual(data[self.clean_file.sha256]["status"], "NOT_REQUESTED")

    # ---

    # Tests for the run_detail view
    # Test Specification Location: documentation/test/unit/UT-11-18.md

    def test_run_detail_renders_with_findings(self):
        # The run detail page should render file contents and findings for a vulnerable file
        run = Run.objects.create(
            submitted_file=self.vuln_file,
            analyzer="bandit",
            status=Run.Status.COMPLETED,
            started_at=timezone.now(),
        )
        resp = self.client.get(reverse("run_detail", args=[run.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.vuln_file.saved_name)
        self.assertIn("file_content", resp.context)
        self.assertIn("findings", resp.context)
