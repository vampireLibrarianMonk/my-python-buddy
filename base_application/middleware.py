# Django Middleware enforcing password change policy
# Docs: https://docs.djangoproject.com/en/stable/topics/http/middleware/

# Django
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import resolve


class ForcePasswordChangeMiddleware:
    """
    Middleware that enforces password change for flagged users.
    Redirects authenticated users to password-change page if required.
    """

    # Initialize middleware and capture next response handler
    def __init__(self, get_response):
        self.get_response = get_response

    # Process each incoming request before view execution
    def __call__(self, request):
        # Safely retrieve user object if available
        user = getattr(request, "user", None)
        if user is None:
            return self.get_response(request)

        # Enforce password update if user is flagged
        if user.is_authenticated:
            prof = getattr(user, "accountprofile", None)
            allowed_names = {"password_change", "password_change_done", "logout", "login"}
            try:
                # Resolve current route name for conditional redirection
                current_name = resolve(request.path_info).url_name
            except Exception:
                current_name = None

            # Redirect flagged users away from restricted pages
            if prof and getattr(prof, "must_change_password", False) and current_name not in allowed_names:
                messages.warning(request, "Please set a new password to continue.")
                return redirect("password_change")

        # Continue normal request processing
        return self.get_response(request)
