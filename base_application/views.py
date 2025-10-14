# Django view logic handling user requests and application workflows
# Docs: https://docs.djangoproject.com/en/stable/topics/http/views/

# Standard library
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import quote as urlquote

# Django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

# Models and Associated Methods
from base_application.models import Run, severity_color_map

# Tasking
from base_application.taskings import executor, run_analyzer_task

# Local
from .forms import AnalyzerSelectForm, UploadPyForm
from .models import SubmittedFile

# First phase templating until analyzers are implemented TODO delete once all analyzers are implemented.
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
    """
    Secure Hashing Algorithm 256 implementation for unique file entries ID (primary keys) in database.
    """
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()


@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request):
    # Upload Handling
    if request.method == "POST":
        form = UploadPyForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]

            # 1) Hash the file
            file_hash = _sha256_of_upload(uploaded)

            # 2) If identical file already tracked, reuse it (no duplicate save)
            existing = SubmittedFile.objects.filter(pk=file_hash).first()
            if existing:
                # Build the same pagination context used at the end of the view
                page_size = int(request.GET.get("ps", 10))
                paginator = Paginator(SubmittedFile.objects.order_by("-uploaded_at"), page_size)
                page_number = request.GET.get("page", 1)
                page_obj = paginator.get_page(page_number)

                return render(
                    request,
                    "base_application/upload.html",
                    {
                        "form": form,
                        "page_obj": page_obj,
                        "page_size": page_size,
                        "duplicate_file": existing,  # The html template will trigger confirm prompt
                        "severity_colors": severity_color_map(),
                    },
                )

            # 3) New file: sanitize + unique name, then save via FileField
            safe_name = _safe_unique_py_name(uploaded.name)

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

    # List: paginated table of prior uploads
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
            "severity_colors": severity_color_map(),
        },
    )


@login_required
@require_http_methods(["POST"])
def delete_file_view(request, sha256):
    """Delete database record and the stored file. Requires POST + CSRF; confirms in user interface."""
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

    if request.method == "GET":
        initial = {"file_name": os.path.basename(obj.file.name)}
        if obj.analysis_analyzers:
            initial["analyzers"] = obj.analysis_analyzers.split(",")
        form = AnalyzerSelectForm(initial=initial)
        return render(
            request,
            "base_application/analyze_select.html",
            {
                "file_name": obj.saved_name,
                "sha256": obj.sha256,
                "form": form,
                "selected_analyzers": initial.get("analyzers", []),  # pre-fill JavaScript context
            },
        )

    # POST --> user selected one or more analyzers
    form = AnalyzerSelectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please choose at least one analyzer.")
        return redirect("analyze_file", sha256=obj.sha256)

    selected = list(form.cleaned_data["analyzers"])

    # Preserve user interface order
    choice_order = [key for key, _label in AnalyzerSelectForm.ANALYZER_CHOICES]
    ordered_selection = [a for a in choice_order if a in selected]

    # Ensure Run objects exist with status = REQUESTED
    for analyzer in ordered_selection:
        Run.objects.get_or_create(
            submitted_file=obj,
            analyzer=analyzer,
            defaults={
                "status": Run.Status.REQUESTED,
                "started_at": timezone.now(),
            },
        )

    # Skip analyzing in this view – leave that to the run_analyzer endpoint
    return render(
        request,
        "base_application/analyze_select.html",
        {
            "file_name": obj.saved_name,
            "sha256": obj.sha256,
            "form": form,
            "selected_analyzers": ordered_selection,
        },
    )


@require_http_methods(["POST"])
@login_required
def run_analyzer(request, sha256: str, analyzer: str):
    submitted_file = get_object_or_404(SubmittedFile, pk=sha256)

    try:
        run = Run.objects.get(submitted_file=submitted_file, analyzer=analyzer)
    except Run.DoesNotExist:
        return JsonResponse({"status": "Error: Run not initialized"}, status=400)

    # Immediately mark as requested (assumes this was done earlier)
    run.status = "REQUESTED"
    run.save(update_fields=["status"])

    # Enqueue background job (non-blocking)
    executor.submit(run_analyzer_task, run.id, run.analyzer)

    return JsonResponse({"status": "Queued"})


@login_required
def bandit_status_json(request):
    files = SubmittedFile.objects.all().order_by("-uploaded_at")
    data = {}

    for f in files:
        run = f.runs.filter(analyzer="bandit").order_by("-started_at").first()
        if run:
            # Always return one of the defined status values
            status = run.status or "PENDING"
            data[f.sha256] = {
                "status": status,
                "findings_count": run.findings_count,
                "run_id": run.id,
            }
        else:
            # No Run yet --> explicitly "NOT_REQUESTED"
            data[f.sha256] = {
                "status": "NOT_REQUESTED",
                "findings_count": 0,
                "run_id": None,
            }

    return JsonResponse(data)


@login_required
def dodgy_status_json(request):
    files = SubmittedFile.objects.all().order_by("-uploaded_at")
    data = {}

    for f in files:
        run = f.runs.filter(analyzer="dodgy").order_by("-started_at").first()
        if run:
            # Always return one of the defined status values
            status = run.status or "PENDING"
            data[f.sha256] = {
                "status": status,
                "findings_count": run.findings_count,
                "run_id": run.id,
            }
        else:
            # No Run yet --> explicitly "NOT_REQUESTED"
            data[f.sha256] = {
                "status": "NOT_REQUESTED",
                "findings_count": 0,
                "run_id": None,
            }

    return JsonResponse(data)


@login_required
def mypy_status_json(request):
    files = SubmittedFile.objects.all().order_by("-uploaded_at")
    data = {}

    for f in files:
        run = f.runs.filter(analyzer="mypy").order_by("-started_at").first()
        if run:
            # Always return one of the defined status values
            status = run.status or "PENDING"
            data[f.sha256] = {
                "status": status,
                "findings_count": run.findings_count,
                "run_id": run.id,
            }
        else:
            # No Run yet --> explicitly "NOT_REQUESTED"
            data[f.sha256] = {
                "status": "NOT_REQUESTED",
                "findings_count": 0,
                "run_id": None,
            }

    return JsonResponse(data)


@login_required
def semgrep_status_json(request):
    files = SubmittedFile.objects.all().order_by("-uploaded_at")
    data = {}

    for f in files:
        run = f.runs.filter(analyzer="semgrep").order_by("-started_at").first()
        if run:
            # Always return one of the defined status values
            status = run.status or "PENDING"
            data[f.sha256] = {
                "status": status,
                "findings_count": run.findings_count,
                "run_id": run.id,
            }
        else:
            # No Run yet --> explicitly "NOT_REQUESTED"
            data[f.sha256] = {
                "status": "NOT_REQUESTED",
                "findings_count": 0,
                "run_id": None,
            }

    return JsonResponse(data)


@login_required
def vulture_status_json(request):
    files = SubmittedFile.objects.all().order_by("-uploaded_at")
    data = {}

    for f in files:
        run = f.runs.filter(analyzer="vulture").order_by("-started_at").first()
        if run:
            # Always return one of the defined status values
            status = run.status or "PENDING"
            data[f.sha256] = {
                "status": status,
                "findings_count": run.findings_count,
                "run_id": run.id,
            }
        else:
            # No Run yet --> explicitly "NOT_REQUESTED"
            data[f.sha256] = {
                "status": "NOT_REQUESTED",
                "findings_count": 0,
                "run_id": None,
            }

    return JsonResponse(data)


def run_detail(request, pk):
    run = get_object_or_404(Run, pk=pk)
    submitted_file = run.submitted_file

    # Read file content safely
    file_content = ""
    try:
        with submitted_file.file.open("rb") as f:
            file_content = f.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        file_content = "[Error: Could not read Python file contents]"

    # Build severity order from the run's OrderedDict (fallback provided)
    sev_order_list = list(getattr(run, "severity_counts", {}).keys()) or ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    sev_cases = [When(severity=key, then=Value(idx)) for idx, key in enumerate(sev_order_list)]

    # Annotate rank and order by it (stable tie-breakers: line, column, id)
    findings_qs = run.findings.annotate(sev_rank=Case(*sev_cases, default=Value(999), output_field=IntegerField())).order_by("sev_rank", "line", "column", "id")

    context = {
        "run": run,
        "file_content": file_content.splitlines(),
        "file_hash": run.submitted_file.sha256,
        "file_name": run.submitted_file.saved_name,
        "findings": findings_qs,
        "severity_colors": severity_color_map(),
    }
    return render(request, "base_application/run_detail.html", context)


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
