from django.urls import path

from .views import (
    analyze_file_view,
    bandit_status_json,
    delete_file_view,
    healthcheck_view,
    run_analyzer,
    run_detail,
    upload_success_view,
    upload_view,
)

urlpatterns = [
    path("", upload_view, name="upload"),
    path("success/", upload_success_view, name="upload_success"),
    path("healthz/", healthcheck_view, name="healthcheck"),
    path("analyze/<str:sha256>/", analyze_file_view, name="analyze_file"),
    path("delete/<str:sha256>/", delete_file_view, name="delete_file"),
    path("run-analyzer/<str:sha256>/<str:analyzer>/", run_analyzer, name="run_analyzer"),
    path("api/bandit-statuses/", bandit_status_json, name="bandit_status_json"),
    path("runs/<int:pk>/", run_detail, name="run_detail"),
]
