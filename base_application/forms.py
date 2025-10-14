# Django forms for secure file upload and analyzer selection
# Docs: https://docs.djangoproject.com/en/stable/topics/forms/

# Django
from django import forms

# Allowed content types to prevent malicious uploads
ALLOWED_CTYPES = {
    "text/x-python",
    "application/x-python-code",
    "text/plain",  # allow fallback for some browsers
}


# Form handling Python file uploads with validation checks
class UploadPyForm(forms.Form):
    file = forms.FileField(label="Python file")

    # Validate file extension, content type, and size
    def clean_file(self):
        f = self.cleaned_data["file"]
        # Check extension matches .py requirement
        if not f.name.lower().endswith(".py"):
            raise forms.ValidationError("Only .py files are allowed.")
        # Validate Content-Type against allowed list
        ctype = (getattr(f, "content_type", None) or "").lower()
        if ctype and ctype not in ALLOWED_CTYPES:
            raise forms.ValidationError("Unexpected file type; please upload a .py file.")
        # Enforce file size limit (1 MB max)
        if f.size > 1_000_000:
            raise forms.ValidationError("File too large (max 1 MB).")
        return f


# Form for selecting one or more static analyzers
class AnalyzerSelectForm(forms.Form):
    ANALYZER_CHOICES = [
        ("bandit", "Bandit – Python security scanner"),
        ("dodgy", "Dodgy – secrets and patterns"),
        ("mypy", "MyPy – type checker"),
        ("semgrep", "Semgrep – pattern matcher"),
        ("vulture", "Vulture – dead code finder"),
    ]

    # Hidden field to preserve uploaded file name
    file_name = forms.CharField(widget=forms.HiddenInput())
    # Multi-select dropdown for choosing analyzers
    analyzers = forms.MultipleChoiceField(
        choices=ANALYZER_CHOICES,
        widget=forms.SelectMultiple(attrs={"size": 6}),
        help_text="Hold Ctrl (Cmd on macOS) to select multiple analyzers.",
    )
