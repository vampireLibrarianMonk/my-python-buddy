import os
import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils.crypto import get_random_string

from base_application.models import AccountProfile
from base_application.views import MustChangePasswordView


def _env_or(default_factory, *env_keys):
    """Return the first present env var among env_keys, else call default_factory()."""
    for k in env_keys:
        v = os.getenv(k)
        if v:
            return v
    return default_factory()


class MustChangePasswordHookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()

        # Use environment overrides when provided; otherwise generate deterministic-safe test values.
        username = _env_or(lambda: f"tester_{get_random_string(8)}", "TEST_USERNAME")
        email = _env_or(lambda: f"{get_random_string(6)}@example.invalid", "TEST_EMAIL")
        old_password = _env_or(lambda: secrets.token_urlsafe(16), "TEST_PASSWORD")

        self.user = User.objects.create_user(
            username=username,
            email=email,
            password=old_password,
        )

        self.old_password = old_password  # keep for the form

        self.profile = AccountProfile.objects.get(user=self.user)
        self.profile.must_change_password = True
        self.profile.save()

    def test_form_valid_clears_must_change_flag(self):
        # Prepare POST request + session
        request = self.factory.post("/accounts/password_change/")
        request.user = self.user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        # New password: from env if provided, else securely generated; ensure not equal to old.
        new_password = _env_or(lambda: secrets.token_urlsafe(18), "TEST_NEW_PASSWORD")
        if new_password == self.old_password:  # vanishingly rare, but make explicit
            new_password = secrets.token_urlsafe(20)

        form_data = {
            "old_password": self.old_password,
            "new_password1": new_password,
            "new_password2": new_password,
        }
        form = PasswordChangeForm(user=self.user, data=form_data)
        self.assertTrue(form.is_valid(), msg=f"Form errors: {form.errors}")

        # Execute view
        view = MustChangePasswordView()
        view.request = request
        view.object = self.user  # required by Django generic views
        response = view.form_valid(form)

        # Assertions
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.must_change_password)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/password_change/done/", response.url)
