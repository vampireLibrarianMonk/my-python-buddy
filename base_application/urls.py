from django.urls import path
from .views import (
    upload_view,
    upload_success_view,
    healthcheck_view,
    analyze_file_view,
    delete_file_view,
)

urlpatterns = [
    path("", upload_view, name="upload"),
    path("success/", upload_success_view, name="upload_success"),
    path("healthz/", healthcheck_view, name="healthcheck"),
    path("analyze/<str:sha256>/", analyze_file_view, name="analyze_file"),
    path("delete/<str:sha256>/", delete_file_view, name="delete_file"),
]
