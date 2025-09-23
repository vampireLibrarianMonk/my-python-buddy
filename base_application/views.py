# Standard library
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import quote as urlquote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView

# Django
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

# Local
from .forms import AnalyzerSelectForm, UploadPyForm
from .models import SubmittedFile

# First phase templating until analyzers are implemented
SAMPLE_FINDINGS_MAP_TEMPLATE = {
    "bandit": [
        {
            "analyzer": "bandit",
            "severity": "<LOW|MEDIUM|HIGH>",
            "rule_id": "<B3xx or other Bandit ID>",
            "title": "<Short title e.g., Insecure hash usage>",
            "message": "<Human-friendly explanation of the issue>",
            "location": {"line": "<LINE_NUMBER>", "column": "<COLUMN_NUMBER>"},
            "reference": "https://bandit.readthedocs.io/",
        },
    ],
    "semgrep": [
        {
            "analyzer": "semgrep",
            "severity": "<INFO|WARNING|ERROR>",
            "rule_id": "<semgrep.rule.id>",
            "title": "<Short title e.g., Insecure hash: MD5>",
            "message": "<Why it matters / suggested fix>",
            "location": {"line": "<LINE_NUMBER>", "column": "<COLUMN_NUMBER>"},
            "reference": "https://semgrep.dev/",
        },
    ],
    "mypy": [
        {
            "analyzer": "mypy",
            "severity": "<NOTE|WARNING|ERROR>",
            "rule_id": "<mypy-code e.g., assignment|arg-type|call-arg>",
            "title": "<Short title e.g., Incompatible types in assignment>",
            "message": "<Expected vs actual types and where they came from>",
            "location": {"line": "<LINE_NUMBER>", "column": "<COLUMN_NUMBER>"},
            "reference": "https://mypy.readthedocs.io/en/stable/",
        },
    ],
    "vulture": [
        {
            "analyzer": "vulture",
            "severity": "<INFO|LOW>",
            "rule_id": "<unused-function|unused-variable|unused-import>",
            "title": "<Short title e.g., Dead code: unused function>",
            "message": "<What is unused and suggested cleanup>",
            "location": {"line": "<LINE_NUMBER>", "column": "<COLUMN_NUMBER>"},
            "reference": "https://github.com/jendrikseipp/vulture",
        },
    ],
    "dodgy": [
        {
            "analyzer": "dodgy",
            "severity": "<LOW|MEDIUM|HIGH>",
            "rule_id": "<hardcoded-secret|insecure-usage|suspicious-pattern>",
            "title": "<Short title e.g., Possible hardcoded credential>",
            "message": "<What looks sensitive and why it’s risky>",
            "location": {"line": "<LINE_NUMBER>", "column": "<COLUMN_NUMBER>"},
            "reference": "https://github.com/landscapeio/dodgy",
        },
    ],
}


def _safe_unique_py_name(original_filename: str) -> str:
    """
    Sanitize the incoming filename to a safe slug and append a short random suffix.
    Always returns a .py extension.
    """
    stem = Path(original_filename).stem  # drop any provided path
    safe_stem = slugify(stem) or "file"
    return f"{safe_stem}-{secrets.token_hex(6)}.py"


def _sha256_of_upload(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()


@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request):
    # --- Handle upload ---
    if request.method == "POST":
        form = UploadPyForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]

            # 1) Hash
            file_hash = _sha256_of_upload(uploaded)

            # 2) If identical file already tracked, reuse it (no duplicate save)
            existing = SubmittedFile.objects.filter(pk=file_hash).first()
            if existing:
                messages.info(
                    request,
                    f"Identical file already exists (SHA-256: {file_hash[:12]}…). Using existing copy.",
                )
                return redirect(f"/success/?f={urlquote(os.path.basename(existing.file.name))}")

            # 3) New file: sanitize + unique name, then save via FileField
            safe_name = _safe_unique_py_name(uploaded.name)  # you already have this helper

            with transaction.atomic():
                record = SubmittedFile(
                    sha256=file_hash,
                    original_name=uploaded.name,
                    saved_name=safe_name,
                )
                # This writes to MEDIA_ROOT/uploads/safe_name
                record.file.save(safe_name, uploaded, save=True)

            messages.success(request, f"File '{safe_name}' uploaded successfully.")
            return redirect(f"/success/?f={urlquote(safe_name)}")
        else:
            messages.error(request, "There was a problem with your upload. See errors below.")
    else:
        form = UploadPyForm()

    # --- List: paginated table of prior uploads ---
    ps = request.GET.get("ps", "10")
    page_size = int(ps) if ps.isdigit() else 10
    page_size = max(1, min(100, page_size))  # Clamp to 1–100
    page_no = request.GET.get("page", "1")

    qs = SubmittedFile.objects.all()
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page_no)

    return render(
        request,
        "base_application/upload.html",
        {
            "form": form,
            "page_obj": page_obj,
            "page_size": page_size,
        },
    )


@login_required
@require_http_methods(["POST"])
def delete_file_view(request, sha256):
    """Delete database record and the stored file. Requires POST + CSRF; confirms in UI."""
    obj = get_object_or_404(SubmittedFile, pk=sha256)
    # Delete file from storage first (don't save model after delete file)
    obj.file.delete(save=False)
    obj.delete()
    messages.success(request, f"Deleted '{obj.saved_name}' ({sha256[:12]}…).")

    # Keep pagination state if present
    ps = request.GET.get("ps", "10")
    page = request.GET.get("page", "1")
    return redirect(f"{reverse('upload')}?ps={ps}&page={page}")


@login_required
@require_http_methods(["GET"])
def upload_success_view(request):
    saved_name = request.GET.get("f")
    if not saved_name:
        return redirect("upload")

    saved_name = os.path.basename(saved_name)
    file_url = settings.MEDIA_URL + "uploads/" + saved_name

    # Try to find the database record so we can link to per-file analyze
    sha256 = ""
    try:
        obj = SubmittedFile.objects.get(saved_name=saved_name)
        sha256 = obj.sha256
    except SubmittedFile.DoesNotExist:
        pass  # File may predate database tracking; just show the download link

    return render(
        request,
        "base_application/success.html",
        {"file_name": saved_name, "file_url": file_url, "sha256": sha256},
    )


@login_required
@require_http_methods(["GET"])
def healthcheck_view(request):
    """
    Healthcheck driven by .env-backed Django settings.
    """
    return JsonResponse(
        {
            "status": "ok",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
            "version": settings.APP_VERSION,
            "build": settings.APP_BUILD,
            "debug": bool(settings.DEBUG),
            "time": time.time(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def analyze_file_view(request, sha256: str):
    obj = get_object_or_404(SubmittedFile, pk=sha256)

    # GET → show selection form (preselect previously used analyzers)
    if request.method == "GET":
        initial = {"file_name": os.path.basename(obj.file.name)}
        if obj.analysis_analyzers:
            initial["analyzers"] = obj.analysis_analyzers.split(",")
        form = AnalyzerSelectForm(initial=initial)
        return render(
            request,
            "base_application/analyze_select.html",
            {"file_name": obj.saved_name, "sha256": obj.sha256, "form": form},
        )

    # POST → run placeholder, update status fields, render split pane
    form = AnalyzerSelectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please choose at least one analyzer.")
        return redirect("analyze_file", sha256=obj.sha256)

    selected = list(form.cleaned_data["analyzers"])
    llm_text = (form.cleaned_data.get("llm_notes") or "").strip()

    # Read code
    path = obj.file.path
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            code_text = f.read()
    except Exception as e:
        obj.analysis_status = SubmittedFile.AnalysisStatus.FAILED
        obj.analysis_analyzers = ",".join(selected)
        obj.analysis_findings = 0
        obj.analyzed_at = timezone.now()
        obj.save(update_fields=["analysis_status", "analysis_analyzers", "analysis_findings", "analyzed_at"])
        messages.error(request, f"Unable to read file: {e}")
        return redirect("upload")

    code_lines = code_text.splitlines()

    # Preserve UI order
    choice_order = [key for key, _label in AnalyzerSelectForm.ANALYZER_CHOICES]
    ordered_selection = [a for a in choice_order if a in selected]

    # Compose placeholder findings
    findings = []
    for analyzer in ordered_selection:
        findings.extend(SAMPLE_FINDINGS_MAP_TEMPLATE.get(analyzer, []))

    # ✅ Persist status
    obj.analysis_status = SubmittedFile.AnalysisStatus.COMPLETE
    obj.analysis_analyzers = ",".join(ordered_selection)
    obj.analysis_findings = len(findings)
    obj.analyzed_at = timezone.now()
    obj.save(update_fields=["analysis_status", "analysis_analyzers", "analysis_findings", "analyzed_at"])

    results_template = {
        "summary": {
            "file": obj.saved_name,
            "analyzers_requested": ordered_selection,
            "notes": "Sample placeholder results shown per selected analyzer. Replace with real tool outputs when integrated.",
        },
        "findings": findings,
        "how_to_read": (
            "This pane shows static analysis results. Each finding includes a severity, a rule ID, an explanation, "
            "and a source location (line/column). When you wire up real analyzers, populate this structure (or similar) "
            "and render it here."
        ),
        "llm_placemarker": {
            "text": llm_text,
        },
    }

    return render(
        request,
        "base_application/analyze.html",
        {
            "file_name": obj.saved_name,
            "code_lines": code_lines,
            "selected_analyzers": ordered_selection,
            "results": results_template,
            "file_url": settings.MEDIA_URL + "uploads/" + obj.saved_name,
        },
    )


class MustChangePasswordView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        resp = super().form_valid(form)  # changes password & updates session
        prof = getattr(self.request.user, "accountprofile", None)
        if prof and prof.must_change_password:
            prof.must_change_password = False
            prof.save(update_fields=["must_change_password"])
        return resp
