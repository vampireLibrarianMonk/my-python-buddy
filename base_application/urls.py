from django.urls import path

# Route mapping
from .views import (
    upload_view,          # Upload form with paginated table of prior uploads
    upload_success_view,  # Post-upload confirmation + download/view link
    healthcheck_view,     # health check
    analyze_file_view,    # GET: analyzer select; POST: run analysis for a file
    delete_file_view,     # Delete a file + its database record (POST only)
)

urlpatterns = [
    path("", upload_view, name="upload"),  # /
    path("success/", upload_success_view, name="upload_success"),
    path("healthz/", healthcheck_view, name="healthcheck"),
    path("analyze/<str:sha256>/", analyze_file_view, name="analyze_file"),
    path("delete/<str:sha256>/", delete_file_view, name="delete_file"),
]
