from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.contrib import messages

class ForcePasswordChangeMiddleware:
    """
    If a logged-in user is flagged (profile.must_change_password=True),
    force them to the password-change page until updated.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Guard: AuthenticationMiddleware may not have run yet (or be absent)
        user = getattr(request, "user", None)
        if user is None:
            return self.get_response(request)

        if user.is_authenticated:
            prof = getattr(user, "accountprofile", None)
            allowed_names = {"password_change", "password_change_done", "logout", "login"}
            try:
                current_name = resolve(request.path_info).url_name
            except Exception:
                current_name = None

            if prof and getattr(prof, "must_change_password", False) and current_name not in allowed_names:
                messages.warning(request, "Please set a new password to continue.")
                return redirect("password_change")

        return self.get_response(request)
