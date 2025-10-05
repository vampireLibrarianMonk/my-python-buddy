# Native
from collections import Counter, OrderedDict
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version

# Analyzers
from bandit.core.config import BanditConfig
from bandit.core.manager import BanditManager

# Django
from django.utils import timezone

# Models
from .models import Finding, Run

# from dodgy.checks import check_file_contents TODO
# from mypy import api TODO
# from vulture import Vulture TODO


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
                ("LOW", severity_counter.get("LOW", 0)),
                ("MEDIUM", severity_counter.get("MEDIUM", 0)),
                ("HIGH", severity_counter.get("HIGH", 0)),
                ("CRITICAL", severity_counter.get("CRITICAL", 0)),
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

        return {"results": list(run.findings.values())}

    except Exception as e:
        run.status = "ERRORED"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        return {"error": str(e)}
