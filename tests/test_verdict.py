"""Tests for the verdict system (PASS/REVIEW/FAIL)."""

from lintlang.patterns import Finding, Severity
from lintlang.report import compute_verdict


class TestVerdict:
    def test_no_findings_is_pass(self):
        assert compute_verdict([]) == "PASS"

    def test_info_only_is_pass(self):
        findings = [Finding("H6", "Test", Severity.INFO, "loc", "desc", "fix")]
        assert compute_verdict(findings) == "PASS"

    def test_low_only_is_pass(self):
        findings = [Finding("H5", "Test", Severity.LOW, "loc", "desc", "fix")]
        assert compute_verdict(findings) == "PASS"

    def test_medium_is_review(self):
        findings = [Finding("H5", "Test", Severity.MEDIUM, "loc", "desc", "fix")]
        assert compute_verdict(findings) == "REVIEW"

    def test_medium_plus_low_is_review(self):
        findings = [
            Finding("H5", "Test", Severity.MEDIUM, "loc", "desc", "fix"),
            Finding("H6", "Test", Severity.LOW, "loc", "desc", "fix"),
            Finding("H6", "Test", Severity.INFO, "loc", "desc", "fix"),
        ]
        assert compute_verdict(findings) == "REVIEW"

    def test_high_is_fail(self):
        findings = [Finding("H1", "Test", Severity.HIGH, "loc", "desc", "fix")]
        assert compute_verdict(findings) == "FAIL"

    def test_critical_is_fail(self):
        findings = [Finding("H1", "Test", Severity.CRITICAL, "loc", "desc", "fix")]
        assert compute_verdict(findings) == "FAIL"

    def test_mixed_critical_and_low_is_fail(self):
        findings = [
            Finding("H1", "Test", Severity.CRITICAL, "loc", "desc", "fix"),
            Finding("H6", "Test", Severity.LOW, "loc", "desc", "fix"),
        ]
        assert compute_verdict(findings) == "FAIL"

    def test_mixed_high_and_medium_is_fail(self):
        """HIGH outranks MEDIUM — verdict is FAIL not REVIEW."""
        findings = [
            Finding("H2", "Test", Severity.HIGH, "loc", "desc", "fix"),
            Finding("H5", "Test", Severity.MEDIUM, "loc", "desc", "fix"),
        ]
        assert compute_verdict(findings) == "FAIL"

    def test_many_lows_still_pass(self):
        """Even many LOW findings should not escalate to REVIEW."""
        findings = [
            Finding(f"H{i}", "Test", Severity.LOW, "loc", "desc", "fix")
            for i in range(10)
        ]
        assert compute_verdict(findings) == "PASS"
