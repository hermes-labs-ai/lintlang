"""Tests for the scanner module."""

from pathlib import Path

from lintlang.patterns import Finding, Severity
from lintlang.scanner import ScanResult, compute_health_score, scan_config, scan_directory, scan_file

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestScanConfig:
    def test_empty_config_returns_scan_result(self, empty_config):
        result = scan_config(empty_config)
        assert isinstance(result, ScanResult)
        assert result.structural_findings == []

    def test_clean_config_high_herm_score(self, clean_tools_config):
        result = scan_config(clean_tools_config)
        assert result.score >= 70  # HERM scores prompt-like content well

    def test_bad_config_has_structural_findings(self, bad_tools_config):
        result = scan_config(bad_tools_config)
        assert len(result.structural_findings) > 0

    def test_pattern_filtering(self, bad_tools_config):
        all_result = scan_config(bad_tools_config)
        h1_result = scan_config(bad_tools_config, patterns=["H1"])
        assert len(h1_result.structural_findings) <= len(all_result.structural_findings)
        assert all(f.pattern_id == "H1" for f in h1_result.structural_findings)

    def test_findings_sorted_by_severity(self, bad_prompt_config):
        result = scan_config(bad_prompt_config)
        findings = result.structural_findings
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for i in range(len(findings) - 1):
            assert severity_order[findings[i].severity.value] <= severity_order[findings[i + 1].severity.value]

    def test_herm_dimensions_present(self, clean_tools_config):
        result = scan_config(clean_tools_config)
        assert len(result.herm.dimension_scores) == 6
        assert all("HERM-" in dim for dim in result.herm.dimension_scores)

    def test_herm_coverage_and_confidence(self, clean_tools_config):
        result = scan_config(clean_tools_config)
        assert 0.55 <= result.herm.coverage <= 1.0
        assert result.herm.confidence in ("high", "medium", "low")


class TestScanFile:
    def test_scan_yaml_file(self):
        result = scan_file(SAMPLES_DIR / "bad_tool_descriptions.yaml")
        assert len(result.structural_findings) > 0

    def test_scan_json_file(self):
        result = scan_file(SAMPLES_DIR / "bad_agent_config.json")
        assert len(result.structural_findings) > 0

    def test_scan_text_file(self):
        result = scan_file(SAMPLES_DIR / "bad_system_prompt.txt")
        assert len(result.structural_findings) > 0

    def test_clean_config_file_high_score(self):
        result = scan_file(SAMPLES_DIR / "clean_config.yaml")
        assert result.score >= 70
        assert result.structural_findings == []

    def test_scan_returns_scan_result(self):
        result = scan_file(SAMPLES_DIR / "clean_config.yaml")
        assert isinstance(result, ScanResult)
        assert isinstance(result.score, float)


class TestScanDirectory:
    def test_scan_samples_directory(self):
        results = scan_directory(SAMPLES_DIR)
        assert len(results) > 0
        # All results should be ScanResults
        for r in results.values():
            assert isinstance(r, ScanResult)

    def test_scan_nonexistent_directory(self):
        results = scan_directory("/nonexistent/path/12345")
        assert results == {}

    def test_malformed_file_produces_error_finding(self, tmp_path):
        bad_file = tmp_path / "broken.json"
        bad_file.write_text("{invalid json content")
        results = scan_directory(tmp_path)
        assert len(results) > 0
        for result in results.values():
            assert any(f.pattern_id == "ERR" for f in result.structural_findings)


class TestHealthScore:
    """Legacy compute_health_score tests — kept for backward compat."""

    def test_no_findings_perfect_score(self):
        assert compute_health_score([]) == 100.0

    def test_critical_findings_low_score(self):
        findings = [
            Finding("H1", "Test", Severity.CRITICAL, "loc", "desc", "fix"),
            Finding("H2", "Test", Severity.CRITICAL, "loc", "desc", "fix"),
        ]
        score = compute_health_score(findings)
        assert score <= 80

    def test_info_findings_minimal_impact(self):
        findings = [
            Finding("H6", "Test", Severity.INFO, "loc", "desc", "fix"),
        ]
        score = compute_health_score(findings)
        assert score == 100  # INFO has 0 penalty

    def test_score_never_negative(self):
        findings = [
            Finding(f"H{i}", "Test", Severity.CRITICAL, "loc", "desc", "fix")
            for i in range(20)
        ]
        score = compute_health_score(findings)
        assert score >= 0
