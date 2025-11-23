# Native
import secrets

# Django
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import Resolver404
from django.utils.crypto import get_random_string

# Middleware
import base_application.middleware as mw
from base_application.middleware import ForcePasswordChangeMiddleware

# Models
from base_application.models import AccountProfile

# Views
from base_application.views import MustChangePasswordView


class MustChangePasswordHookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()

        # Use environment overrides when provided; otherwise generate deterministic-safe test values.
        username = f"tester_{get_random_string(8)}"
        email = f"{get_random_string(6)}@example.invalid"
        old_password = secrets.token_urlsafe(16)

        self.user = User.objects.create_user(
            username=username,
            email=email,
            password=old_password,
        )

        self.old_password = old_password  # keep for the form

        self.profile = AccountProfile.objects.get(user=self.user)
        self.profile.must_change_password = True
        self.profile.save()

    # Test Specification Location: documentation/test/unit/UT-11-13.md
    def test_form_valid_clears_must_change_flag(self):
        # Prepare POST request + session
        request = self.factory.post("/accounts/password_change/")
        request.user = self.user
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        # New password: from environment if provided, else securely generated.
        # Ensure the old and new password are not equal.
        new_password = secrets.token_urlsafe(18)
        if new_password == self.old_password:
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


class TestForcePasswordChangeMiddleware(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ForcePasswordChangeMiddleware(lambda r: r)

        User = get_user_model()

        username = f"tester_{get_random_string(8)}"
        email = f"{get_random_string(6)}@example.invalid"
        old_password = secrets.token_urlsafe(16)

        self.user = User.objects.create_user(
            username=username,
            email=email,
            password=old_password,
        )

        self.old_password = old_password

        self.profile = AccountProfile.objects.get(user=self.user)
        self.profile.must_change_password = True
        self.profile.save()

    def _add_messages(self, request):
        setattr(request, "session", {})
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

    #  When user is None it must return get_response(request)
    def test_user_none_returns_normal_flow(self):
        request = self.factory.get("/")
        request.user = None

        response = self.middleware(request)
        self.assertEqual(response, request)

    # Route resolution will fail when current_name is None
    def test_route_resolve_exception_sets_current_name_none(self):
        request = self.factory.get("/bad!route")
        request.user = self.user

        original_resolve = mw.resolve

        def bad_resolve(path, *args, **kwargs):
            raise Resolver404

        mw.resolve = bad_resolve

        try:
            self._add_messages(request)
            response = self.middleware(request)
        finally:
            mw.resolve = original_resolve

        self.assertEqual(response.status_code, 302)
        self.assertIn("/password_change", response.url)

    # Flagged user must redirect with warning message
    def test_flagged_user_redirects_with_message(self):
        request = self.factory.get("/dashboard")
        request.user = self.user  # real profile

        self._add_messages(request)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/password_change", response.url)

        stored_messages = list(request._messages)
        self.assertTrue(any("Please set a new password" in str(m) for m in stored_messages))
