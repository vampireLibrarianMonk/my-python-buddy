"""
URL config for core project.

# This file defines the WebSocket consumer responsible for real-time analyzer updates in Django Channels.
# It manages client connections, group messaging and streaming of analyzer status or findings to the browser.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from base_application.views import MustChangePasswordView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # App routes
    path("", include("base_application.urls")),
    # Auth (centralized here)
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_change/", MustChangePasswordView.as_view(), name="password_change"),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
]

# Development Only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
