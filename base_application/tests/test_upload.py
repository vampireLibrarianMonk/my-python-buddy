import io
import os
import shutil
import tempfile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

# Temporary media root for these tests
TEMP_MEDIA = tempfile.mkdtemp()

"""
Test file upload

Serves as the mechanism to verify file upload behavior is as advertised. 
- Will use temporary media root separate from one utilized for end use.
- Temporary media folder is removed when testing is completed.

Covered behavior:
- GET /  renders the upload page (200) with the "Submit a Python file" prompt.
- POST valid .py    returns 302 redirect to /success/?f=...
- POST invalid .py  displays "Only .py files are allowed."
- POST >1 MB .py    displays with "File too large."
- When a successful upload occurs, the saved filename appears on the success page and within the uploads directory.
"""
@override_settings(MEDIA_ROOT=TEMP_MEDIA, MEDIA_URL="/media/")
class UploadViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def test_get_upload_page(self):
        resp = self.client.get(reverse("upload"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Submit a Python file")

    def test_accepts_valid_py(self):
        content = b"print('hello')\n"
        f = SimpleUploadedFile("script.py", content, content_type="text/x-python")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/success/?f=", resp["Location"])

    def test_rejects_non_py(self):
        f = SimpleUploadedFile("notes.txt", b"not python", content_type="text/plain")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Only .py files are allowed.")

    def test_rejects_large_file(self):
        big = io.BytesIO(b"x" * (1_000_000 + 1))  # > 1 MB
        f = SimpleUploadedFile("big.py", big.getvalue(), content_type="text/x-python")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "File too large")

    def test_file_is_saved_under_uploads(self):
        f = SimpleUploadedFile("script.py", b"print(1)\n", content_type="text/x-python")
        resp = self.client.post(reverse("upload"), {"file": f}, follow=False)
        self.assertEqual(resp.status_code, 302)

        # Follow redirect to success page
        resp2 = self.client.get(resp["Location"])
        self.assertEqual(resp2.status_code, 200)

        fname = resp2.context["file_name"]
        self.assertContains(resp2, f"/media/uploads/{fname}")
        self.assertContains(resp2, fname)

        # Confirm file present on disk
        path = os.path.join(TEMP_MEDIA, "uploads", fname)
        self.assertTrue(os.path.exists(path))
