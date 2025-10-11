# Native
import os
import shutil
import tempfile

# Testing
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

# Django
from django.test import TestCase, override_settings

# Analyzer
from base_application.analyzers import (
    get_analyzer_version,
    run_bandit_analyzer,
    run_dodgy_analyzer,
    run_mypy_analyzer,
    run_semgrep_analyzer,
    run_vulture_analyzer,
)

# Model
from base_application.models import Run, SubmittedFile

# Define paths for loading the known good and vulnerable test files
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_files")
TEMP_MEDIA = tempfile.mkdtemp()

# Expected Bandit findings for bandit_ringer_test.py
EXPECTED_FINDINGS_BANDIT = [
    {"rule_id": "B102", "severity": "MEDIUM", "line": 3, "column": 4},
    {"rule_id": "B501", "severity": "HIGH", "line": 12, "column": 11},
    {"rule_id": "B113", "severity": "MEDIUM", "line": 12, "column": 11},
    {"rule_id": "B103", "severity": "HIGH", "line": 20, "column": 4},
    {"rule_id": "B404", "severity": "LOW", "line": 25, "column": 0},
    {"rule_id": "B602", "severity": "HIGH", "line": 29, "column": 4},
]

# Expected Dodgy findings for dodgy_ringer_test.py
EXPECTED_FINDINGS_DODGY = [
    {
        "severity": "Dodgy",
        "rule_id": "DODGY",
        "message": "Possible hardcoded secret key (variable: secret)",
        "line": 8,
        "column": 0,
    },
    {
        "severity": "Dodgy",
        "rule_id": "DODGY",
        "message": "Possible SSH private key (variable: ssh_rsa_private_key)",
        "line": 12,
        "column": 0,
    },
    {
        "severity": "Dodgy",
        "rule_id": "DODGY",
        "message": "Possible SSH private key (variable: ssh_rsa_private_key)",
        "line": 15,
        "column": 0,
    },
]

# Expected Mypy findings for mypy_ringer_test.py
EXPECTED_FINDINGS_MYPY = [
    {"severity": "note", "rule_id": "MYPY-001", "line": 0, "column": 0},
    {"severity": "note", "rule_id": "MYPY-003", "line": 0, "column": 0},
    {"severity": "note", "rule_id": "MYPY-005", "line": 0, "column": 0},
    {"severity": "note", "rule_id": "MYPY-007", "line": 0, "column": 0},
    {"severity": "error", "rule_id": "MYPY-002", "line": 6, "column": 12},
    {"severity": "error", "rule_id": "MYPY-004", "line": 10, "column": 1},
    {"severity": "error", "rule_id": "MYPY-006", "line": 18, "column": 0},
    {"severity": "error", "rule_id": "MYPY-008", "line": 23, "column": 11},
]

# Expected Semgrep findings for semgrep_ringer_test.py
EXPECTED_FINDINGS_SEMGREP = [
    {
        "severity": "MEDIUM",
        "rule_id": "python.lang.security.audit.eval-detected.eval-detected",
        "message": (
            "Detected the use of eval(). eval() can be dangerous if used to evaluate "
            "dynamic content. If this content can be input from outside the program, "
            "this may be a code injection vulnerability. Ensure evaluated content "
            "is not definable by external sources."
        ),
        "line": 27,
        "column": 5,
    },
    {
        "severity": "HIGH",
        "rule_id": "python.lang.security.audit.subprocess-shell-true.subprocess-shell-true",
        "message": (
            "Found 'subprocess' function 'run' with 'shell=True'. This is dangerous "
            "because this call will spawn the command using a shell process. Doing so "
            "propagates current shell settings and variables, which makes it much easier "
            "for a malicious actor to execute commands. Use 'shell=False' instead."
        ),
        "line": 32,
        "column": 31,
    },
]

# Expected Vulture findings for vulture_ringer_test.py
EXPECTED_FINDINGS_VULTURE = [
    {
        "severity": "MEDIUM",
        "rule_id": "FUNCTION-001",
        "message": "unused function 'critical_example' (confidence 60%)",
        "line": 7,
        "column": 0,
    },
    {
        "severity": "HIGH",
        "rule_id": "IMPORT-001",
        "message": "unused import 'math' (confidence 90%)",
        "line": 2,
        "column": 0,
    },
    {
        "severity": "CRITICAL",
        "rule_id": "UNREACHABLE_CODE-001",
        "message": "unreachable code after 'return' (confidence 100%)",
        "line": 9,
        "column": 0,
    },
]


@override_settings(MEDIA_ROOT=TEMP_MEDIA, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"])
class AnalyzerTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        # Clean up the temporary media directory after all tests run
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        # Load the clean sample.py file
        with open(os.path.join(SAMPLE_DIR, "sample.py"), "rb") as f:
            clean = SimpleUploadedFile("sample.py", f.read(), content_type="text/x-python")

        # Load vulnerable file series for each analyzer
        with open(os.path.join(SAMPLE_DIR, "bandit_ringer_test.py"), "rb") as f:
            vuln_bandit = SimpleUploadedFile("bandit_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "dodgy_ringer_test.py"), "rb") as f:
            vuln_dodgy = SimpleUploadedFile("dodgy_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "mypy_ringer_test.py"), "rb") as f:
            vuln_mypy = SimpleUploadedFile("mypy_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "semgrep_ringer_test.py"), "rb") as f:
            vuln_semgrep = SimpleUploadedFile("semgrep_ringer_test.py", f.read(), content_type="text/x-python")

        with open(os.path.join(SAMPLE_DIR, "vulture_ringer_test.py"), "rb") as f:
            vuln_vulture = SimpleUploadedFile("vulture_ringer_test.py", f.read(), content_type="text/x-python")

        # Assign clean file
        self.clean_file = SubmittedFile.objects.create(
            sha256="sha256_clean",
            saved_name="sample.py",
            original_name="sample.py",
            file=clean,
        )
        # Assign vulnerable file series for each analyzer
        self.vuln_file_bandit = SubmittedFile.objects.create(
            sha256="sha256_vuln_bandit",
            saved_name="bandit_ringer_test.py",
            original_name="bandit_ringer_test.py",
            file=vuln_bandit,
        )
        self.vuln_file_dodgy = SubmittedFile.objects.create(
            sha256="sha256_vuln_dodgy",
            saved_name="dodgy_ringer_test.py",
            original_name="dodgy_ringer_test.py",
            file=vuln_dodgy,
        )
        self.vuln_file_mypy = SubmittedFile.objects.create(
            sha256="sha256_vuln_mypy",
            saved_name="mypy_ringer_test.py",
            original_name="mypy_ringer_test.py",
            file=vuln_mypy,
        )
        self.vuln_file_semgrep = SubmittedFile.objects.create(
            sha256="sha256_vuln_semgrep",
            saved_name="semgrep_ringer_test.py",
            original_name="semgrep_ringer_test.py",
            file=vuln_semgrep,
        )
        self.vuln_file_vulture = SubmittedFile.objects.create(
            sha256="sha256_vuln_vulture",
            saved_name="vulture_ringer_test.py",
            original_name="vulture_ringer_test.py",
            file=vuln_vulture,
        )

    # Clean file test
    # Test Specification Location: documentation/test/unit/UT-11-20.md

    def test_bandit_analyzer_on_clean_file(self):
        # Running Bandit on a clean file should complete successfully with zero findings
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="bandit", status=Run.Status.REQUESTED)
        run_bandit_analyzer(run)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertEqual(run.findings_count, 0)

    def test_dodgy_analyzer_on_clean_file(self):
        # Running Dodgy on a clean file should complete successfully with zero findings
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="dodgy", status=Run.Status.REQUESTED)
        run_dodgy_analyzer(run)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertEqual(run.findings_count, 0)

    def test_mypy_analyzer_on_clean_file(self):
        # Running MyPy on a clean file should complete successfully with zero findings
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="mypy", status=Run.Status.REQUESTED)
        run_mypy_analyzer(run)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertEqual(run.findings_count, 0)

    def test_semgrep_analyzer_on_clean_file(self):
        # Running Semgrep on a clean file should complete successfully with zero findings
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="semgrep", status=Run.Status.REQUESTED)
        run_semgrep_analyzer(run)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertEqual(run.findings_count, 0)

    def test_vulture_analyzer_on_clean_file(self):
        # Running Vulture on a clean file should complete successfully with zero findings
        run = Run.objects.create(submitted_file=self.clean_file, analyzer="vulture", status=Run.Status.REQUESTED)
        run_vulture_analyzer(run)
        run.refresh_from_db()

        self.assertEqual(run.status, Run.Status.COMPLETED)
        self.assertEqual(run.findings_count, 0)
        self.assertIsInstance(run.severity_counts, dict)

    # Vulnerable file test
    # Test Specification Location: documentation/test/unit/UT-11-21.md

    def test_bandit_analyzer_on_vulnerable_file(self):
        """
        Running Bandit on a vulnerable file should complete successfully and persist known findings in the database.
        Also should not have any unexpected findings.
        """
        # Create the Run entry for this file/analyzer
        run = Run.objects.create(
            submitted_file=self.vuln_file_bandit,
            analyzer="bandit",
            status=Run.Status.REQUESTED,
        )

        # Execute analyzer
        run_bandit_analyzer(run)

        # Reload the run to capture any database updates
        run.refresh_from_db()

        # Verify the run completed successfully
        self.assertEqual(run.status, Run.Status.COMPLETED, msg="Bandit run did not complete properly")

        # Verify the finding count matches expectations
        self.assertEqual(
            run.findings_count,
            len(EXPECTED_FINDINGS_BANDIT),
            msg="Bandit finding count mismatch",
        )

        # Confirm severity counts were persisted as a dictionary
        self.assertIsInstance(run.severity_counts, dict, msg="Severity counts not stored correctly")

        # Retrieve persisted findings from database
        if hasattr(run, "findings"):
            stored_findings = list(run.findings.values("rule_id", "severity", "line", "column"))
        else:
            stored_findings = []

        # Convert to simplified tuples for comparison
        actual = [(f["rule_id"], f["severity"], f["line"], f["column"]) for f in stored_findings]

        # Check that each expected finding is present in database results
        for expected in EXPECTED_FINDINGS_BANDIT:
            self.assertIn(
                (expected["rule_id"], expected["severity"], expected["line"], expected["column"]),
                actual,
                msg=f"Missing expected finding {expected['rule_id']} at line {expected['line']}",
            )

        # Ensure no unexpected extras exist
        self.assertEqual(
            len(actual),
            len(EXPECTED_FINDINGS_BANDIT),
            msg="Unexpected number of persisted Bandit findings",
        )

    def test_dodgy_analyzer_on_vulnerable_file(self):
        """
        Running Dodgy on a vulnerable file should complete successfully and persist known findings in the database.
        Also should not have any unexpected findings.
        """
        # Create the Run entry for this file/analyzer
        run = Run.objects.create(
            submitted_file=self.vuln_file_dodgy,
            analyzer="dodgy",
            status=Run.Status.REQUESTED,
        )

        # Execute analyzer
        run_dodgy_analyzer(run)

        # Reload the run to capture any database updates
        run.refresh_from_db()

        # Verify the run completed successfully
        self.assertEqual(run.status, Run.Status.COMPLETED, msg="Dodgy run did not complete properly")

        # Verify the finding count matches expectations
        self.assertEqual(
            run.findings_count,
            len(EXPECTED_FINDINGS_DODGY),
            msg="Dodgy finding count mismatch",
        )

        # Confirm severity counts were persisted as a dictionary
        self.assertIsInstance(run.severity_counts, dict, msg="Severity counts not stored correctly")

        # Retrieve persisted findings from database
        if hasattr(run, "findings"):
            stored_findings = list(run.findings.values("rule_id", "line", "column"))
        else:
            stored_findings = []

        # Convert to simplified tuples for comparison
        actual = [(f["rule_id"], f["line"], f["column"]) for f in stored_findings]

        # Check that each expected finding is present in database results
        for expected in EXPECTED_FINDINGS_DODGY:
            self.assertIn(
                (expected["rule_id"], expected["line"], expected["column"]),
                actual,
                msg=f"Missing expected finding {expected['rule_id']} at line {expected['line']}",
            )

        # Ensure no unexpected extras exist
        self.assertEqual(
            len(actual),
            len(EXPECTED_FINDINGS_DODGY),
            msg="Unexpected number of persisted Dodgy findings",
        )

    def test_mypy_analyzer_on_vulnerable_file(self):
        """
        Running Mypy on a vulnerable file should complete successfully and persist known findings in the database.
        Also should not have any unexpected findings.
        """
        # Create the Run entry for this file/analyzer
        run = Run.objects.create(
            submitted_file=self.vuln_file_mypy,
            analyzer="mypy",
            status=Run.Status.REQUESTED,
        )

        # Execute analyzer (no return expected now)
        run_mypy_analyzer(run)

        # Reload the run to capture any database updates
        run.refresh_from_db()

        # Verify the run completed successfully
        self.assertEqual(run.status, Run.Status.COMPLETED, msg="Mypy run did not complete properly")

        # Verify the finding count matches expectations
        self.assertEqual(
            run.findings_count,
            len(EXPECTED_FINDINGS_MYPY),
            msg="Mypy finding count mismatch",
        )

        # Confirm severity counts were persisted as a dictionary
        self.assertIsInstance(run.severity_counts, dict, msg="Severity counts not stored correctly")

        # Retrieve persisted findings from database (supports JSONField or related model)
        if hasattr(run, "findings"):
            stored_findings = list(run.findings.values("rule_id", "line", "column"))
        else:
            stored_findings = []

        # Convert to simplified tuples for comparison
        actual = [(f["rule_id"], f["line"], f["column"]) for f in stored_findings]

        # Check that each expected finding is present in database results
        for expected in EXPECTED_FINDINGS_MYPY:
            self.assertIn(
                (expected["rule_id"], expected["line"], expected["column"]),
                actual,
                msg=f"Missing expected finding {expected['rule_id']} at line {expected['line']}",
            )

        # Ensure no unexpected extras exist
        self.assertEqual(
            len(actual),
            len(EXPECTED_FINDINGS_MYPY),
            msg="Unexpected number of persisted Mypy findings",
        )

    def test_semgrep_analyzer_on_vulnerable_file(self):
        """
        Running Semgrep on a vulnerable file should complete successfully and persist known findings in the database.
        Also should not have any unexpected findings.
        """
        # Create the Run entry for this file/analyzer
        run = Run.objects.create(
            submitted_file=self.vuln_file_semgrep,
            analyzer="semgrep",
            status=Run.Status.REQUESTED,
        )

        # Execute analyzer (no return expected now)
        run_semgrep_analyzer(run)

        # Reload the run to capture any DB updates
        run.refresh_from_db()

        # Verify the run completed successfully
        self.assertEqual(run.status, Run.Status.COMPLETED, msg="Semgrep run did not complete properly")

        # Verify the finding count matches expectations
        self.assertEqual(
            run.findings_count,
            len(EXPECTED_FINDINGS_SEMGREP),
            msg="Semgrep finding count mismatch",
        )

        # Confirm severity counts were persisted as a dictionary
        self.assertIsInstance(run.severity_counts, dict, msg="Severity counts not stored correctly")

        # Retrieve persisted findings from database
        if hasattr(run, "findings"):
            stored_findings = list(run.findings.values("rule_id", "line", "column"))
        else:
            stored_findings = []

        # Convert to simplified tuples for comparison
        actual = [(f["rule_id"], f["line"], f["column"]) for f in stored_findings]

        # Check that each expected finding is present in database results
        for expected in EXPECTED_FINDINGS_SEMGREP:
            self.assertIn(
                (expected["rule_id"], expected["line"], expected["column"]),
                actual,
                msg=f"Missing expected finding {expected['rule_id']} at line {expected['line']}",
            )

        # Ensure no unexpected extras exist
        self.assertEqual(
            len(actual),
            len(EXPECTED_FINDINGS_SEMGREP),
            msg="Unexpected number of persisted Semgrep findings",
        )

    def test_vulture_analyzer_on_vulnerable_file(self):
        """
        Running Vulture on a vulnerable file should complete successfully and persist known findings in the database.
        Also should not have any unexpected findings.
        """
        # Create the Run entry for this file/analyzer
        run = Run.objects.create(
            submitted_file=self.vuln_file_vulture,
            analyzer="vulture",
            status=Run.Status.REQUESTED,
        )

        # Execute analyzer (no return expected now)
        run_vulture_analyzer(run)

        # Reload the run to capture any DB updates
        run.refresh_from_db()

        # Verify the run completed successfully
        self.assertEqual(run.status, Run.Status.COMPLETED, msg="Vulture run did not complete properly")

        # Verify the finding count matches expectations
        self.assertEqual(
            run.findings_count,
            len(EXPECTED_FINDINGS_VULTURE),
            msg="Vulture finding count mismatch",
        )

        # Confirm severity counts were persisted as a dictionary
        self.assertIsInstance(run.severity_counts, dict, msg="Severity counts not stored correctly")

        # Retrieve persisted findings from database
        if hasattr(run, "findings"):
            stored_findings = list(run.findings.values("rule_id", "line", "column"))
        else:
            stored_findings = []

        # Convert to simplified tuples for comparison
        actual = [(f["rule_id"], f["line"], f["column"]) for f in stored_findings]

        # Check that each expected finding is present in database results
        for expected in EXPECTED_FINDINGS_VULTURE:
            self.assertIn(
                (expected["rule_id"], expected["line"], expected["column"]),
                actual,
                msg=f"Missing expected finding {expected['rule_id']} at line {expected['line']}",
            )

        # Ensure no unexpected extras exist
        self.assertEqual(
            len(actual),
            len(EXPECTED_FINDINGS_VULTURE),
            msg="Unexpected number of persisted Vulture findings",
        )

    # Versioning check
    # Test Specification Location: documentation/test/unit/UT-11-22.md

    def test_get_analyzer_version_known_and_unknown(self):
        # Verify that known analyzers return valid version strings and unknown analyzers safely return 'unknown'.

        # Bandit
        version = get_analyzer_version("bandit")
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "unknown", msg="Bandit version should be detected")

        # Dodgy
        version = get_analyzer_version("dodgy")
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "unknown", msg="Dodgy version should be detected")

        # MyPy
        version = get_analyzer_version("mypy")
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "unknown", msg="MyPy version should be detected")

        # Semgrep
        version = get_analyzer_version("semgrep")
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "unknown", msg="Semgrep version should be detected")

        # Vulture
        version = get_analyzer_version("vulture")
        self.assertIsInstance(version, str)
        self.assertNotEqual(version, "unknown", msg="Vulture version should be detected")

        # Faux tool (negative control)
        version = get_analyzer_version("faux_tool_does_not_exist")
        self.assertEqual(version, "unknown", msg="Unknown tools should safely return 'unknown'")

    # Error handling (more of a code coverage insurance)
    # Test Specification Location: documentation/test/unit/UT-11-23.md

    # Diagnostics (put as first line in each test method)
    # import sys
    # print("Analyzer loaded as:", [k for k in sys.modules.keys() if "analyzers" in k])

    def test_run_bandit_analyzer_exception_marks_error(self):
        # Force BanditManager.run_tests to raise an exception so the analyzer falls into the error path
        with patch("base_application.analyzers.BanditManager.run_tests", side_effect=RuntimeError("failed task")):
            run = Run.objects.create(submitted_file=self.clean_file, analyzer="bandit", status=Run.Status.REQUESTED)
            result = run_bandit_analyzer(run)
            run.refresh_from_db()

            # Verify the run is marked errored
            self.assertEqual(run.status, Run.Status.ERRORED)
            self.assertIsNotNone(run.completed_at)

            # Verify the error dictionary is returned
            self.assertIn("error", result)
            self.assertIn("failed task", result["error"])

    def test_run_dodgy_analyzer_exception_marks_error(self):
        # Patch Dodgy's check_file_contents to raise an exception
        with patch("base_application.analyzers.check_file_contents", side_effect=RuntimeError("failed task")):
            run = Run.objects.create(
                submitted_file=self.clean_file,
                analyzer="dodgy",
                status=Run.Status.REQUESTED,
            )

            # Execute analyzer, expecting failure
            result = run_dodgy_analyzer(run)
            run.refresh_from_db()

            # Verify the run is marked as errored
            self.assertEqual(run.status, Run.Status.ERRORED)
            self.assertIsNotNone(run.completed_at)

            # Verify the analyzer returned an error dictionary
            self.assertIn("error", result)
            self.assertIn("failed task", result["error"])

    def test_run_mypy_analyzer_exception_marks_error(self):
        # Force mypy_api.run to raise an exception so the analyzer falls into the error path
        with patch("base_application.analyzers.mypy_api.run", side_effect=RuntimeError("failed task")):
            run = Run.objects.create(
                submitted_file=self.clean_file,
                analyzer="mypy",
                status=Run.Status.REQUESTED,
            )
            result = run_mypy_analyzer(run)
            run.refresh_from_db()

            # Verify the run is marked errored
            self.assertEqual(run.status, Run.Status.ERRORED)
            self.assertIsNotNone(run.completed_at)

            # Verify the error dictionary is returned
            self.assertIn("error", result)
            self.assertIn("failed task", result["error"])

    def test_run_semgrep_analyzer_exception_marks_error(self):
        # Force subprocess.run inside semgrep analyzer to raise an exception
        with patch("base_application.analyzers.subprocess.run", side_effect=RuntimeError("failed task")):
            run = Run.objects.create(
                submitted_file=self.clean_file,
                analyzer="semgrep",
                status=Run.Status.REQUESTED,
            )
            result = run_semgrep_analyzer(run)
            run.refresh_from_db()

            # Verify the run is marked errored
            self.assertEqual(run.status, Run.Status.ERRORED)
            self.assertIsNotNone(run.completed_at)

            # Verify the error dictionary is returned
            self.assertIn("error", result)
            self.assertIn("failed task", result["error"])

    def test_run_vulture_analyzer_exception_marks_error(self):
        # Force Vulture initialization or scanning to raise an exception
        with patch("base_application.analyzers.Vulture.scan", side_effect=RuntimeError("failed task")):
            run = Run.objects.create(
                submitted_file=self.clean_file,
                analyzer="vulture",
                status=Run.Status.REQUESTED,
            )
            result = run_vulture_analyzer(run)
            run.refresh_from_db()

            # Verify the run is marked errored
            self.assertEqual(run.status, Run.Status.ERRORED)
            self.assertIsNotNone(run.completed_at)

            # Verify the error dictionary is returned
            self.assertIn("error", result)
            self.assertIn("failed task", result["error"])
