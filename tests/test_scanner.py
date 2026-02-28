"""Tests for the scanner module."""

import pytest
from pathlib import Path

from lingdiag.scanner import scan_config, scan_file, compute_health_score
from lingdiag.patterns import AgentConfig, Finding, Severity, ToolDef


SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestScanConfig:
    def test_empty_config_no_findings(self, empty_config):
        findings = scan_config(empty_config)
        assert findings == []

    def test_clean_config_high_score(self, clean_tools_config):
        findings = scan_config(clean_tools_config)
        score = compute_health_score(findings)
        assert score >= 90

    def test_bad_config_low_score(self, bad_tools_config):
        findings = scan_config(bad_tools_config)
        score = compute_health_score(findings)
        assert score < 60

    def test_pattern_filtering(self, bad_tools_config):
        all_findings = scan_config(bad_tools_config)
        h1_only = scan_config(bad_tools_config, patterns=["H1"])
        assert len(h1_only) <= len(all_findings)
        assert all(f.pattern_id == "H1" for f in h1_only)

    def test_findings_sorted_by_severity(self, bad_prompt_config):
        findings = scan_config(bad_prompt_config)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        for i in range(len(findings) - 1):
            assert severity_order[findings[i].severity.value] <= severity_order[findings[i + 1].severity.value]


class TestScanFile:
    def test_scan_yaml_file(self):
        findings = scan_file(SAMPLES_DIR / "bad_tool_descriptions.yaml")
        assert len(findings) > 0

    def test_scan_json_file(self):
        findings = scan_file(SAMPLES_DIR / "bad_agent_config.json")
        assert len(findings) > 0

    def test_scan_text_file(self):
        findings = scan_file(SAMPLES_DIR / "bad_system_prompt.txt")
        assert len(findings) > 0

    def test_clean_config_file(self):
        findings = scan_file(SAMPLES_DIR / "clean_config.yaml")
        score = compute_health_score(findings)
        assert score == 100


class TestHealthScore:
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
