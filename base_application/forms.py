from django import forms

# Content types for first line of defense from malicious input files
ALLOWED_CTYPES = {
    "text/x-python",
    "application/x-python-code",
    "text/plain",  # for now allow that some browsers view python as text
}


class UploadPyForm(forms.Form):
    file = forms.FileField(label="Python file")

    def clean_file(self):
        f = self.cleaned_data["file"]
        # Check extension
        if not f.name.lower().endswith(".py"):
            raise forms.ValidationError("Only .py files are allowed.")
        # Content-Type check (room to grow if hardening becomes the desired end goal)
        ctype = (getattr(f, "content_type", None) or "").lower()
        if ctype and ctype not in ALLOWED_CTYPES:
            raise forms.ValidationError("Unexpected file type; please upload a .py file.")
        # Optional size guard (e.g., 1 MB)
        # Size review at a later time TODO
        if f.size > 1_000_000:
            raise forms.ValidationError("File too large (max 1 MB).")
        return f


class AnalyzerSelectForm(forms.Form):
    ANALYZER_CHOICES = [
        ("bandit", "Bandit – Python security scanner"),
        ("dodgy", "Dodgy – secrets and patterns"),
        ("mypy", "MyPy – type checker"),
        ("semgrep", "Semgrep – pattern matcher"),
        ("vulture", "Vulture – dead code finder"),
    ]

    file_name = forms.CharField(widget=forms.HiddenInput())
    analyzers = forms.MultipleChoiceField(
        choices=ANALYZER_CHOICES,
        widget=forms.SelectMultiple(attrs={"size": 6}),  # “combo box” style
        help_text="Hold Ctrl (Cmd on macOS) to select multiple analyzers.",
    )
