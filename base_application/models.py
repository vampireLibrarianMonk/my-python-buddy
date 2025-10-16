# Django ORM models defining core database structures for analysis data
# Docs: https://docs.djangoproject.com/en/stable/topics/db/models/

# Native
from collections import OrderedDict

# Django
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class AccountProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile({self.user.username})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        AccountProfile.objects.create(user=instance)


class SubmittedFile(models.Model):
    class AnalysisStatus(models.TextChoices):
        NOT_REQUESTED = "NOT_REQUESTED", "Not requested"
        COMPLETE = "COMPLETE", "Complete"
        FAILED = "FAILED", "Failed"

    # 64 hex chars = SHA-256; use as primary key
    sha256 = models.CharField(primary_key=True, max_length=64, editable=False)

    # The actual file under MEDIA_ROOT/uploads/
    file = models.FileField(upload_to="uploads/")

    # Bookkeeping
    original_name = models.CharField(max_length=255)
    saved_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Analysis tracking
    analysis_status = models.CharField(
        max_length=20,
        choices=AnalysisStatus.choices,
        default=AnalysisStatus.NOT_REQUESTED,
    )
    analysis_analyzers = models.CharField(  # comma-separated keys reserved for analyzers, e.g. "bandit"
        max_length=255,
        blank=True,
        default="",
    )
    analysis_findings = models.PositiveIntegerField(default=0)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.saved_name} ({self.sha256[:12]}…)"


def severity_default():
    return OrderedDict(
        [
            # Bandit & other analyzers
            ("low", 0),
            ("medium", 0),
            ("high", 0),
            ("critical", 0),
            # Semgrep native severities
            ("info", 0),
            ("warning", 0),
            ("error", 0),
        ],
    )


def severity_color_map():
    return {
        # Bandit & other analyzers
        "low": {"bg": "#FFEB3B", "fg": "#000000"},  # Bright Yellow
        "medium": {"bg": "#FF9800", "fg": "#ffffff"},  # Orange
        "high": {"bg": "#F44336", "fg": "#ffffff"},  # Red
        "critical": {"bg": "#B71C1C", "fg": "#ffffff"},  # Deep Red
        # Semgrep (MyPy uses warning and error) native severities
        "info": {"bg": "#42a5f5", "fg": "#ffffff"},  # Light blue info
        "warning": {"bg": "#FFC107", "fg": "#000000"},  # Amber
        "error": {"bg": "#D32F2F", "fg": "#ffffff"},  # Deep Red
    }


class Run(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        REQUESTED = "REQUESTED", "Requested"
        COMPLETED = "COMPLETED", "Completed"
        ERRORED = "ERRORED", "Errored"

    submitted_file = models.ForeignKey("SubmittedFile", on_delete=models.CASCADE, related_name="runs")
    analyzer = models.CharField(max_length=15)
    analyzer_version = models.CharField(max_length=15, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    findings_count = models.IntegerField(default=0)
    severity_counts = models.JSONField(default=severity_default, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.analyzer} run on {self.submitted_file.saved_name}"


class Finding(models.Model):
    run = models.ForeignKey("Run", on_delete=models.CASCADE, related_name="findings")
    severity = models.CharField(max_length=20)
    rule_id = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    message = models.TextField()
    line = models.IntegerField()
    column = models.IntegerField(default=0)
    reference = models.URLField(blank=True)

    # New fields to track exact file
    file_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ["line", "column"]
        unique_together = ("run", "rule_id", "line", "column", "file_hash")

    def __str__(self):
        return f"{self.severity} {self.rule_id} (line {self.line}) [{self.file_name}]"
