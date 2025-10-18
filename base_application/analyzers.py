# Static Code Analyzer run methods.

# Native
import json
import re
import subprocess  # nosec B404: subprocess is used safely with shell=False and fixed arguments
import tempfile
from collections import Counter, OrderedDict, defaultdict
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

# Channels
from asgiref.sync import async_to_sync

# Analyzers
# Bandit
from bandit.core.config import BanditConfig
from bandit.core.manager import BanditManager
from channels.layers import get_channel_layer
from django.db import transaction

# Django
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now

# Dodgy
from dodgy.checks import check_file_contents

# Vulture
from vulture import Vulture

# Models
from .models import Finding, Run


def detect_frameworks_in_file(file_path: str) -> set:
    frameworks = set()

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().lower()

    if "import django" in content or "from django" in content:
        frameworks.add("django")
    if "import flask" in content or "from flask" in content:
        frameworks.add("flask")

    return frameworks


def get_analyzer_version(analyzer):
    try:
        version = get_version(analyzer)
    except PackageNotFoundError:
        version = "unknown"
    return version


def run_bandit_analyzer(run):
    try:
        # Configure bandit, create manager, read in (discover) file and scan it.
        config = BanditConfig()
        manager = BanditManager(config, 'file', 'json')
        manager.discover_files([run.submitted_file.file.path], True)
        manager.run_tests()

        issues = manager.get_issue_list()

        for issue in issues:
            data = issue.as_dict()
            Finding.objects.get_or_create(
                run=run,
                severity=data.get("issue_severity"),
                rule_id=data.get("test_id"),
                title=data.get("test_name"),
                message=data.get("issue_text"),
                line=data.get("line_number"),
                column=data.get("col_offset", 0),
                reference="https://bandit.readthedocs.io/",
                file_hash=run.submitted_file.sha256,
                file_name=run.submitted_file.saved_name,
            )

        # Count severity levels from database, not JSON (a better templated way to setup for html presentation)
        severity_counter = Counter(run.findings.values_list("severity", flat=True))

        # Severity Tracking (Ordered)
        run.severity_counts = OrderedDict(
            [
                ("Low", severity_counter.get("LOW", 0)),
                ("Medium", severity_counter.get("MEDIUM", 0)),
                ("High", severity_counter.get("HIGH", 0)),
                ("Critical", severity_counter.get("CRITICAL", 0)),
            ],
        )

        # Run Metadata Fill
        run.analyzer_version = get_analyzer_version("bandit")
        run.findings_count = run.findings.count()
        run.completed_at = timezone.now()
        run.status = Run.Status.COMPLETED
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "findings_count",
                "severity_counts",
                "analyzer_version",
            ],
        )

        # Get the active Django Channels layer
        channel_layer = get_channel_layer()

        # Send WebSocket update after database commit completes
        transaction.on_commit(
            lambda: async_to_sync(channel_layer.group_send)(
                f"analyzer_{run.submitted_file.sha256}",
                {
                    "type": "send_update",
                    "data": {
                        "analyzer": run.analyzer,
                        "status": run.status,
                        "severity_counts": run.severity_counts,
                        "findings_count": run.findings_count,
                        "run_url": reverse("run_detail", args=[run.id]),
                        "timestamp": now().isoformat(),
                    },
                },
            ),
        )

    except Exception as e:
        run.status = "ERRORED"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}


def run_dodgy_analyzer(run):
    try:
        file_path = run.submitted_file.file.path
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            file_contents = f.read()

        # Run Dodgy checks on the file contents
        issues = check_file_contents(file_contents)

        # Parse each issue into the Finding model
        counter = 1
        for line_number, variable_name, reason in issues:
            message = f"{reason} (variable: {variable_name})"
            Finding.objects.get_or_create(
                run=run,
                severity="DODGY",
                rule_id=f"DODGY-{counter}",
                title=f"Dodgy variable '{variable_name}' detected",
                message=message,
                line=line_number,
                column=0,
                reference="https://github.com/landscapeio/dodgy",
                file_hash=run.submitted_file.sha256,
                file_name=run.submitted_file.saved_name,
            )
            counter += 1

        # === Dodginess metric ===
        dodgy_count = run.findings.count()
        run.severity_counts = OrderedDict([("Dodgy", dodgy_count)])

        run.analyzer_version = get_analyzer_version("dodgy")
        run.findings_count = dodgy_count
        run.completed_at = timezone.now()
        run.status = Run.Status.COMPLETED
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "findings_count",
                "severity_counts",
                "analyzer_version",
            ],
        )

        # Get the active Django Channels layer
        channel_layer = get_channel_layer()

        # Send WebSocket update after database commit completes
        transaction.on_commit(
            lambda: async_to_sync(channel_layer.group_send)(
                f"analyzer_{run.submitted_file.sha256}",
                {
                    "type": "send_update",
                    "data": {
                        "analyzer": run.analyzer,
                        "status": run.status,
                        "severity_counts": run.severity_counts,
                        "findings_count": run.findings_count,
                        "run_url": reverse("run_detail", args=[run.id]),
                        "timestamp": now().isoformat(),
                    },
                },
            ),
        )

    except Exception as e:
        run.status = Run.Status.ERRORED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}


def run_mypy_analyzer(run):
    try:
        file_path = run.submitted_file.file.path

        # Run MyPy as a subprocess with isolation and timeout
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "mypy",
                "--no-incremental",  # avoid shared cache locks
                f"--cache-dir={tmpdir}",  # isolated temp cache
                "--show-error-codes",  # include mypy error codes
                "--show-column-numbers",  # show column for findings
                "--disallow-untyped-defs",  # flag untyped functions
                "--warn-return-any",  # warn on Any return type
                "--warn-unused-ignores",  # warn on unused ignores
                "--ignore-missing-imports",  # suppress crash on missing libs
                "--show-error-context",  # include 'note:' follow-ups
                "--no-error-summary",  # keep raw output readable
                file_path,  # target file path
            ]

            # Run MyPy assembled command in subprocess
            result = subprocess.run(  # nosec B603: shell=False, trusted cmd list, no untrusted input
                cmd,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=30,  # hard stop after 30 seconds
            )
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode

        # If mypy fails entirely with no output
        if exit_code != 0 and not stdout:
            run.status = Run.Status.ERRORED
            run.completed_at = timezone.now()
            run.findings_count = 0
            run.analyzer_version = get_analyzer_version("mypy")
            run.severity_counts = OrderedDict()
            run.save(update_fields=["status", "completed_at", "findings_count", "analyzer_version", "severity_counts"])

            # Get the active Django Channels layer
            channel_layer = get_channel_layer()

            # Send WebSocket update after database commit completes
            transaction.on_commit(
                lambda: async_to_sync(channel_layer.group_send)(
                    f"analyzer_{run.submitted_file.sha256}",
                    {
                        "type": "send_update",
                        "data": {
                            "analyzer": run.analyzer,
                            "status": run.status,
                            "severity_counts": run.severity_counts,
                            "findings_count": run.findings_count,
                            "run_url": reverse("run_detail", args=[run.id]),
                            "timestamp": now().isoformat(),
                        },
                    },
                ),
            )
            return {"error": stderr or "MyPy execution failed"}

        # No issues signaled with a blank stdout
        if stdout == "":
            run.status = Run.Status.COMPLETED
            run.completed_at = timezone.now()
            run.findings_count = 0
            run.analyzer_version = get_analyzer_version("mypy")
            run.severity_counts = OrderedDict([("Error", 0)])  # consistent schema
            run.save(update_fields=["status", "completed_at", "findings_count", "analyzer_version", "severity_counts"])

            # Get the active Django Channels layer
            channel_layer = get_channel_layer()

            # Send WebSocket update after database commit completes
            transaction.on_commit(
                lambda: async_to_sync(channel_layer.group_send)(
                    f"analyzer_{run.submitted_file.sha256}",
                    {
                        "type": "send_update",
                        "data": {
                            "analyzer": run.analyzer,
                            "status": run.status,
                            "severity_counts": run.severity_counts,
                            "findings_count": run.findings_count,
                            "run_url": reverse("run_detail", args=[run.id]),
                            "timestamp": now().isoformat(),
                        },
                    },
                ),
            )
            return {"results": []}

        # Pattern: file:line[:col]: type: message [error-code]
        pattern = re.compile(
            r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<col>\d+))?:\s*(?P<type>\w+):\s*(?P<message>.*?)(?:\s*\[(?P<code>[-\w]+)\])?$",
        )

        # Simple sequential rule_id counter
        counter = 1

        pending_note = None  # store last note context

        for line in stdout.splitlines():
            line = line.strip()
            match = pattern.match(line)

            # Pre-clean for "note:" lines with path prefixes
            cleaned_line = re.sub(r"^.*?:\s*note:\s*", "", line).strip()

            # Skip summary/footer lines
            if not match:
                if not line.startswith("Found ") and not line.isdigit():
                    # Identify standalone "note" context lines (no match)
                    if "note:" in line:
                        # Save it temporarily to attach to next error
                        pending_note = cleaned_line.rstrip(":")
                    else:
                        counter += 1
                continue

            # Normal MyPy structured line
            data = match.groupdict()
            file_name = run.submitted_file.saved_name
            line_num = int(data.get("line") or 0)
            col_num = int(data.get("col") or 0)
            msg_type = data.get("type", "error").lower()
            message = data.get("message", "").strip()

            # If this is an error and we have a pending note → prepend it
            if msg_type == "error" and pending_note:
                message = f"{pending_note}. {message}"
                pending_note = None  # reset after use

            severity = "Error"
            rule_id = f"MYPY-{counter:03d}"
            counter += 1

            Finding.objects.create(
                run=run,
                severity=severity,
                rule_id=rule_id,
                title="Type Checking Issue",
                message=message,
                line=line_num,
                column=col_num,
                reference="https://mypy.readthedocs.io/",
                file_hash=run.submitted_file.sha256,
                file_name=file_name,
            )

        # Simple counts by category
        category_counter = Counter(
            Finding.objects.filter(run=run).values_list("severity", flat=True),
        )

        run.severity_counts = OrderedDict(
            [
                ("Error", category_counter.get("Error", 0)),
            ],
        )

        # Metadata + completion
        run.analyzer_version = get_analyzer_version("mypy")
        run.findings_count = run.findings.count()
        run.completed_at = timezone.now()
        run.status = Run.Status.COMPLETED
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "findings_count",
                "severity_counts",
                "analyzer_version",
            ],
        )

        # Get the active Django Channels layer
        channel_layer = get_channel_layer()

        # Send WebSocket update after database commit completes
        transaction.on_commit(
            lambda: async_to_sync(channel_layer.group_send)(
                f"analyzer_{run.submitted_file.sha256}",
                {
                    "type": "send_update",
                    "data": {
                        "analyzer": run.analyzer,
                        "status": run.status,
                        "severity_counts": run.severity_counts,
                        "findings_count": run.findings_count,
                        "run_url": reverse("run_detail", args=[run.id]),
                        "timestamp": now().isoformat(),
                    },
                },
            ),
        )

    except Exception as e:
        # Capture any unexpected analyzer-level exceptions
        run.status = Run.Status.ERRORED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}


def run_semgrep_analyzer(run):
    try:
        file_path = run.submitted_file.file.path

        frameworks = detect_frameworks_in_file(file_path)

        semgrep_configs = [
            ("p/default", "default"),  # General security checks
            ("p/owasp-top-ten", "owasp-top-ten"),  # OWASP Top Ten risks
            ("p/python", "python"),  # Python-specific issues
            ("p/comment", "comment"),  # TODO/FIXME and notes
            ("p/security-audit", "security-audit"),  # Audit-focused findings
        ]

        if "django" in frameworks:
            semgrep_configs.append(("p/django", "django"))
        if "flask" in frameworks:
            semgrep_configs.append(("p/flask", "flask"))

        # Normalize older severities → modern equivalents
        severity_map = {
            "INFO": "LOW",
            "WARNING": "MEDIUM",
            "ERROR": "HIGH",
        }

        seen = set()  # (check_id, severity, line, msg)
        for config, label in semgrep_configs:
            cmd = [
                "semgrep",
                "--config",
                config,
                "--json",
                "--metrics",
                "off",
                "--disable-version-check",
                file_path,
            ]
            result = subprocess.run(  # nosec B603: shell=False, trusted cmd list, no untrusted input
                cmd,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
            )

            # Semgrep exit codes: 0 = no findings, 1 = findings
            if result.returncode not in (0, 1):
                print(f"[Semgrep] {config} failed: {result.stderr.strip()}")
                continue  # Don’t abort entire analyzer — just skip this pack

            try:
                data = json.loads(result.stdout or "{}")
            except json.JSONDecodeError as je:
                print(f"[Semgrep JSON Error] {config}: {je}")
                continue

            for issue in data.get("results", []):
                check_id = issue.get("check_id", "UNKNOWN")
                msg = issue.get("extra", {}).get("message", "")
                sev_raw = (issue.get("extra", {}).get("severity", "LOW") or "LOW").strip().upper()
                sev = severity_map.get(sev_raw, sev_raw)  # normalize old → new
                start = issue.get("start", {}) or {}
                line = int(start.get("line", 0) or 0)
                col = int(start.get("col", 0) or 0)
                rule_url = issue.get("extra", {}).get("metadata", {}).get("source", "https://semgrep.dev/rules")

                key = (check_id, sev, line, msg)
                if key in seen:
                    continue
                seen.add(key)

                Finding.objects.get_or_create(
                    run=run,
                    severity=sev,
                    rule_id=check_id,
                    title=f"Semgrep ({label}): {check_id}",
                    message=msg,
                    line=line,
                    column=col,
                    reference=rule_url,
                    file_hash=run.submitted_file.sha256,
                    file_name=run.submitted_file.saved_name,
                )

        # Unified severity breakdown
        # All Semgrep rules have one of four severity levels: Critical, High, Medium, or Low.
        # The levels ERROR, WARNING and INFO used in existing rules are older values that correspond to High, Medium
        # and Low, respectively.
        severity_counter = Counter(run.findings.values_list("severity", flat=True))
        run.severity_counts = OrderedDict(
            [
                ("Low", severity_counter.get("LOW", 0)),
                ("Medium", severity_counter.get("MEDIUM", 0)),
                ("High", severity_counter.get("HIGH", 0)),
                ("Critical", severity_counter.get("CRITICAL", 0)),
            ],
        )

        # Finalize run
        run.analyzer_version = get_analyzer_version("semgrep")
        run.findings_count = run.findings.count()
        run.completed_at = timezone.now()
        run.status = Run.Status.COMPLETED
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "findings_count",
                "severity_counts",
                "analyzer_version",
            ],
        )

        # Get the active Django Channels layer
        channel_layer = get_channel_layer()

        # Send WebSocket update after database commit completes
        transaction.on_commit(
            lambda: async_to_sync(channel_layer.group_send)(
                f"analyzer_{run.submitted_file.sha256}",
                {
                    "type": "send_update",
                    "data": {
                        "analyzer": run.analyzer,
                        "status": run.status,
                        "severity_counts": run.severity_counts,
                        "findings_count": run.findings_count,
                        "run_url": reverse("run_detail", args=[run.id]),
                        "timestamp": now().isoformat(),
                    },
                },
            ),
        )

    except Exception as e:
        run.status = Run.Status.ERRORED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}


def run_vulture_analyzer(run):
    """
    Run Vulture static analysis to detect unused code and classify by confidence.
    """
    try:
        file_path = run.submitted_file.file.path

        # Analyze the submitted file using Vulture
        v = Vulture(verbose=False)
        v.scavenge([file_path])
        unused_items = v.get_unused_code()

        # Prepare rule counters for unique rule IDs
        rule_counters = defaultdict(int)

        # Map Vulture confidence scores to severity.
        # Confidence values (60, 90, 100) are hardcoded in Vulture’s source logic.
        # 60 = general unused item, 90 = unused import, 100 = unreachable code.
        # We widen MEDIUM to include 60–79% for practical balance.
        # If confidence is missing, default to 50 (safety fallback for unknown cases).
        def confidence_to_severity(confidence: int | None) -> str:
            confidence = confidence or 50  # default safety fallback
            if confidence >= 95:
                return "CRITICAL"
            elif confidence >= 80:
                return "HIGH"
            else:
                return "MEDIUM"  # broaden range for realism

        # Process each unused code element reported by Vulture
        for item in unused_items:
            rule_counters[item.typ] += 1
            severity = confidence_to_severity(getattr(item, "confidence", 50))  # default to trigger a closer look
            rule_id = f"{item.typ.upper()}-{rule_counters[item.typ]:03d}"

            Finding.objects.get_or_create(
                run=run,
                severity=severity,
                rule_id=rule_id,
                title=f"Unused {item.typ}",
                message=f"{item.message or f'Unused {item.typ} named {item.name}'} (confidence {item.confidence}%)",
                line=item.first_lineno or 0,
                column=0,
                reference="https://vulture.readthedocs.io/en/latest/",
                file_hash=run.submitted_file.sha256,
                file_name=run.submitted_file.saved_name,
            )

        # Aggregate severity counts for dashboard summaries
        severity_counter = Counter(run.findings.values_list("severity", flat=True))
        run.severity_counts = OrderedDict(
            [
                ("Low", severity_counter.get("LOW", 0)),
                ("Medium", severity_counter.get("MEDIUM", 0)),
                ("High", severity_counter.get("HIGH", 0)),
                ("Critical", severity_counter.get("CRITICAL", 0)),
            ],
        )

        # Record analyzer metadata and finalize run
        run.analyzer_version = get_analyzer_version("vulture")
        run.findings_count = run.findings.count()
        run.completed_at = timezone.now()
        run.status = Run.Status.COMPLETED
        run.save(
            update_fields=[
                "status",
                "completed_at",
                "findings_count",
                "severity_counts",
                "analyzer_version",
            ],
        )

        # Get the active Django Channels layer
        channel_layer = get_channel_layer()

        # Send WebSocket update after database commit completes
        transaction.on_commit(
            lambda: async_to_sync(channel_layer.group_send)(
                f"analyzer_{run.submitted_file.sha256}",
                {
                    "type": "send_update",
                    "data": {
                        "analyzer": run.analyzer,
                        "status": run.status,
                        "severity_counts": run.severity_counts,
                        "findings_count": run.findings_count,
                        "run_url": reverse("run_detail", args=[run.id]),
                        "timestamp": now().isoformat(),
                    },
                },
            ),
        )

    except Exception as e:
        run.status = Run.Status.ERRORED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}
