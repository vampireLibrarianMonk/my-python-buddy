from django.contrib import admin

from .models import Finding, Run, SubmittedFile


class RunInline(admin.TabularInline):
    model = Run
    extra = 0
    fields = ("analyzer", "status", "started_at", "completed_at", "findings_count")
    readonly_fields = ("started_at", "completed_at", "findings_count")
    show_change_link = True


@admin.register(SubmittedFile)
class SubmittedFileAdmin(admin.ModelAdmin):
    list_display = ("saved_name", "original_name", "sha256", "uploaded_at", "analysis_status", "analysis_findings")
    search_fields = ("saved_name", "original_name", "sha256")
    list_filter = ("analysis_status", "uploaded_at")
    inlines = [RunInline]


class FindingInline(admin.TabularInline):
    model = Finding
    extra = 0
    fields = (
        "severity",
        "rule_id",
        "title",
        "line",
        "column",
        "reference",
        "file_name",
        "file_hash",
    )
    readonly_fields = (
        "severity",
        "rule_id",
        "title",
        "line",
        "column",
        "reference",
        "file_name",
        "file_hash",
    )
    show_change_link = True


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("id", "submitted_file", "analyzer", "status", "started_at", "completed_at", "findings_count")
    search_fields = ("submitted_file__saved_name", "submitted_file__sha256", "analyzer")
    list_filter = ("analyzer", "status", "started_at", "completed_at")
    inlines = [FindingInline]
