# Routing for base_application

# Django
from django.urls import path

# Views
from . import views_chat
from .views import (
    analyze_file_view,
    bandit_status_json,
    delete_file_view,
    dodgy_status_json,
    mypy_status_json,
    run_analyzer,
    run_detail,
    semgrep_status_json,
    upload_success_view,
    upload_view,
    vulture_status_json,
)

# Pathway routing for base_application
urlpatterns = [
    # File menu
    path("", upload_view, name="upload"),
    # File upload success
    path("success/", upload_success_view, name="upload_success"),
    # Menu actions
    path("analyze/<str:sha256>/", analyze_file_view, name="analyze_file"),
    path("delete/<str:sha256>/", delete_file_view, name="delete_file"),
    path("run-analyzer/<str:sha256>/<str:analyzer>/", run_analyzer, name="run_analyzer"),
    # Application Programming Interface for analyzers
    path("api/bandit-statuses/", bandit_status_json, name="bandit_status_json"),
    path("api/dodgy-statuses/", dodgy_status_json, name="dodgy_status_json"),
    path("api/mypy-statuses/", mypy_status_json, name="mypy_status_json"),
    path("api/semgrep-statuses/", semgrep_status_json, name="semgrep_status_json"),
    path("api/vulture-statuses/", vulture_status_json, name="vulture_status_json"),
    # Analysis results for a particular run
    path("runs/<int:pk>/", run_detail, name="run_detail"),
    # LLM Chat Bot
    path("api/chat_llm/", views_chat.chat_llm, name="chat_llm"),
    path("api/chat_reset/", views_chat.chat_reset, name="chat_reset"),
]
