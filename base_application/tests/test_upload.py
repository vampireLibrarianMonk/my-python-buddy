# Native
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Django
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

# Environment Pull
from dotenv import load_dotenv

# Models
from base_application.models import AccountProfile, SubmittedFile

# Environment settings load and adjustment per needs of test environment
BASE_DIR = dj_settings.BASE_DIR if hasattr(dj_settings, "BASE_DIR") else Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Comma-separated list in environment file, falls back to "*"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
ALLOWED_HOSTS.append("testserver")

MEDIA_URL_ENV = os.getenv("DJANGO_MEDIA_URL", "/media/")

# Temporary media root for these tests
TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(
    MEDIA_ROOT=TEMP_MEDIA,
    MEDIA_URL=MEDIA_URL_ENV,
    ALLOWED_HOSTS=list(ALLOWED_HOSTS),
    SECURE_SSL_REDIRECT=False,
)
class UploadViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        # Create a logged-in user so views that require auth return 200
        user = get_user_model()
        username = os.getenv("TEST_USERNAME", "tester")
        email = os.getenv("TEST_EMAIL", "tester@example.com")
        password = os.getenv("TEST_PASSWORD", "pass1234!")
        self.user = user.objects.create_user(username, email, password)

        # Ensure a profile exists and DISABLE forced password change
        prof, _ = AccountProfile.objects.get_or_create(user=self.user)
        if prof.must_change_password:
            prof.must_change_password = False
            prof.save(update_fields=["must_change_password"])

        self.client.login(username=username, password=password)

    # Test Specification Location: documentation/test/unit/UT-11-01.md
    def test_get_upload_page(self):
        resp = self.client.get(reverse("upload"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Submit a Python file")

    # Test Specification Location: documentation/test/unit/UT-11-02.md
    def test_accepts_valid_py(self):
        f = SimpleUploadedFile("script.py", b"print('hello')\n", content_type="text/x-python")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/success/?f=", resp["Location"])

    # Test Specification Location: documentation/test/unit/UT-11-03.md
    def test_rejects_non_py(self):
        f = SimpleUploadedFile("notes.txt", b"not python", content_type="text/plain")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Only .py files are allowed.")

    # Test Specification Location: documentation/test/unit/UT-11-04.md
    def test_boundary_sizes(self):
        # 1 MB test file ok
        file_ok = SimpleUploadedFile("ok.py", b"x" * 1_000_000, content_type="text/x-python")
        response_ok = self.client.post(reverse("upload"), {"file": file_ok}, follow=False)
        self.assertEqual(response_ok.status_code, 302)

        # Just over 1 MB file too big
        file_too_big = SimpleUploadedFile("too_big.py", b"x" * 1_000_001, content_type="text/x-python")
        response_too_big = self.client.post(reverse("upload"), {"file": file_too_big}, follow=True)
        self.assertEqual(response_too_big.status_code, 200)
        self.assertContains(response_too_big, "File too large")

    # Test Specification Location: documentation/test/unit/UT-11-05.md
    def test_extension_rules_advanced(self):
        # Accept .PY (case-insensitive)
        file_one = SimpleUploadedFile("upper.PY", b"print(1)\n", content_type="text/x-python")
        response_one = self.client.post(reverse("upload"), {"file": file_one}, follow=False)
        self.assertEqual(response_one.status_code, 302)

        # Reject double extension
        file_two = SimpleUploadedFile("tricky.py.txt", b"print(1)\n", content_type="text/plain")
        response_two = self.client.post(reverse("upload"), {"file": file_two}, follow=True)
        self.assertEqual(response_two.status_code, 200)
        self.assertContains(response_two, "Only .py files are allowed.")

    # Test Specification Location: documentation/test/unit/UT-11-06.md
    def test_file_is_saved_under_uploads(self):
        file_object = SimpleUploadedFile("script.py", b"print(1)\n", content_type="text/x-python")
        response_one = self.client.post(reverse("upload"), {"file": file_object}, follow=False)
        self.assertEqual(response_one.status_code, 302)

        # Extract filename from redirect (?f=...)
        location = response_one["Location"]
        file_name = parse_qs(urlparse(location).query).get("f", [None])[0]
        self.assertIsNotNone(file_name, "Redirect missing ?f=<filename>")

        # Follow redirect and assert content/link
        response_two = self.client.get(location)
        self.assertEqual(response_two.status_code, 200)
        self.assertContains(response_two, f"/media/uploads/{file_name}")
        self.assertContains(response_two, file_name)

        # Confirm file present on disk
        path = os.path.join(TEMP_MEDIA, "uploads", file_name)
        self.assertTrue(os.path.exists(path))

    # Test Specification Location: documentation/test/unit/UT-11-07.md
    def test_delete_uploaded_file_removes_file_and_db(self):
        # Upload a valid .py
        f = SimpleUploadedFile("script.py", b"print(1)\n", content_type="text/x-python")
        response = self.client.post(reverse("upload"), {"file": f}, follow=False)
        self.assertEqual(response.status_code, 302)

        # Extract saved filename from redirect (?f=<saved_name>)
        location = response["Location"]
        file_name = parse_qs(urlparse(location).query).get("f", [None])[0]
        self.assertIsNotNone(file_name)

        # Success page should show an "uploaded successfully" message
        resp_success = self.client.get(location)
        self.assertEqual(resp_success.status_code, 200)
        self.assertRegex(resp_success.content.decode(), r"(?i)uploaded successfully")

        # Confirm file exists on disk under TEMP_MEDIA/uploads/
        path = os.path.join(TEMP_MEDIA, "uploads", file_name)
        self.assertTrue(os.path.exists(path))

        # Lookup database row to get the primary key (SHA256)
        file_object = SubmittedFile.objects.get(saved_name=file_name)

        # Delete must be POST: GET should return 405 (method not allowed)
        get_response = self.client.get(reverse("delete_file", args=[file_object.sha256]))
        self.assertEqual(get_response.status_code, 405)

        # Call delete endpoint via POST, follow redirect back to list
        response_two = self.client.post(reverse("delete_file", args=[file_object.sha256]), follow=True)
        self.assertEqual(response_two.status_code, 200)  # after follow, page renders

        # Assert delete success message is shown
        self.assertRegex(response_two.content.decode(), r"(?i)deleted")

        # Assert file is removed and database row deleted
        self.assertFalse(os.path.exists(path))
        self.assertFalse(SubmittedFile.objects.filter(pk=file_object.sha256).exists())

        # Deleting a non-existent SHA now should 404
        resp_missing = self.client.post(reverse("delete_file", args=[file_object.sha256]), follow=False)
        self.assertEqual(resp_missing.status_code, 404)

    # Test Specification Location: documentation/test/unit/UT-11-08.md
    def _fname_from_redirect(self, resp):
        from urllib.parse import parse_qs, urlparse

        return parse_qs(urlparse(resp["Location"]).query).get("f", [None])[0]

    # Test Specification Location: documentation/test/unit/UT-11-08.md
    def test_duplicate_content_prompts_reanalyze(self):
        content = b"print('same')\n"
        upload_one = SimpleUploadedFile("a.py", content, content_type="text/x-python")
        response_one = self.client.post(reverse("upload"), {"file": upload_one}, follow=False)
        self.assertEqual(response_one.status_code, 302)  # first upload redirects
        file_name_one = self._fname_from_redirect(response_one)

        upload_two = SimpleUploadedFile("b.py", content, content_type="text/x-python")
        response_two = self.client.post(reverse("upload"), {"file": upload_two}, follow=True)
        self.assertEqual(response_two.status_code, 200)  # duplicate upload renders page with prompt

        # Ensure duplicate modal is present in HTML
        self.assertContains(response_two, "Do you want to reanalyze it?")

        # Expect same saved file and exactly one database row (since primary is SHA256)
        file_name_two = SubmittedFile.objects.first().saved_name
        self.assertEqual(file_name_one, file_name_two)
        self.assertEqual(SubmittedFile.objects.count(), 1)

    # Test Specification Location: documentation/test/unit/UT-11-09.md
    def test_unicode_filename_saved_and_linked(self):
        # Create an unsophisticated test file upload
        name = "naïve_测试.py"
        funky_file_upload = SimpleUploadedFile(name, b"print(42)\n", content_type="text/x-python")

        # Upload the file
        resp = self.client.post(reverse("upload"), {"file": funky_file_upload}, follow=False)
        self.assertEqual(resp.status_code, 302)

        # Extract saved filename from redirect (?f=<saved_name>)
        location = resp["Location"]
        saved = parse_qs(urlparse(location).query).get("f", [None])[0]
        self.assertIsNotNone(saved, "Redirect missing ?f=<filename>")

        # Success page shows link with saved name
        response_two = self.client.get(location)
        self.assertEqual(response_two.status_code, 200)
        self.assertContains(response_two, f"/media/uploads/{saved}")

        # Database stores the original Unicode filename
        file_object = SubmittedFile.objects.get(saved_name=saved)
        self.assertEqual(file_object.original_name, name)

        # File exists on disk
        path = os.path.join(TEMP_MEDIA, "uploads", saved)
        self.assertTrue(os.path.exists(path))

    # Test Specification Location: documentation/test/unit/UT-11-11.md
    def test_success_page_handles_missing_db_record(self):
        # Manually save a file without a SubmittedFile record
        file_name = "manual.py"
        saved_path = os.path.join(TEMP_MEDIA, "uploads", file_name)
        with open(saved_path, "wb") as f:
            f.write(b"print('no db record')")

        # Access success page with this manually placed file
        resp = self.client.get(reverse("upload_success") + f"?f={file_name}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, file_name)  # Still renders the filename
        self.assertContains(resp, f"/media/uploads/{file_name}")

    # Test Specification Location: documentation/test/unit/UT-11-12.md
    def test_success_redirects_if_filename_missing(self):
        response = self.client.get(reverse("upload_success"))  # No ?f= in querystring
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertEqual(response.url, reverse("upload"))  # Redirects to upload page
