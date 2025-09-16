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
        max_length=255, blank=True, default=""
    )
    analysis_findings = models.PositiveIntegerField(default=0)
    analyzed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.saved_name} ({self.sha256[:12]}…)"
