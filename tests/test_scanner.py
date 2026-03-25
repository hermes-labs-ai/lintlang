"""Tests for the scanner module."""

from pathlib import Path

from lintlang.patterns import Finding, Severity
from lintlang.scanner import (
    ScanResult,
    _is_non_prompt_file,
    compute_health_score,
    scan_config,
    scan_directory,
    scan_file,
)

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


class TestFileTypeFiltering:
    """Tests for non-prompt file detection and filtering."""

    def test_changelog_is_non_prompt(self):
        assert _is_non_prompt_file(Path("CHANGELOG.md"))

    def test_readme_is_non_prompt(self):
        assert _is_non_prompt_file(Path("README.md"))

    def test_license_is_non_prompt(self):
        assert _is_non_prompt_file(Path("LICENSE.md"))

    def test_contributing_is_non_prompt(self):
        assert _is_non_prompt_file(Path("CONTRIBUTING.md"))

    def test_code_of_conduct_is_non_prompt(self):
        assert _is_non_prompt_file(Path("CODE_OF_CONDUCT.md"))

    def test_security_is_non_prompt(self):
        assert _is_non_prompt_file(Path("SECURITY.md"))

    def test_skill_md_is_prompt(self):
        assert not _is_non_prompt_file(Path("SKILL.md"))

    def test_config_yaml_is_prompt(self):
        assert not _is_non_prompt_file(Path("agent_config.yaml"))

    def test_system_prompt_is_prompt(self):
        assert not _is_non_prompt_file(Path("system_prompt.txt"))

    def test_egg_info_dir_is_non_prompt(self):
        assert _is_non_prompt_file(Path("pkg.egg-info/SOURCES.txt"))

    def test_pytest_cache_is_non_prompt(self):
        assert _is_non_prompt_file(Path(".pytest_cache/README.md"))

    def test_directory_scan_skips_non_prompt(self, tmp_path):
        """scan_directory should skip CHANGELOG.md, README.md, etc."""
        # Create a mix of prompt and non-prompt files
        (tmp_path / "SKILL.md").write_text("You are an assistant. Use the tools.")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v1.0\n- Always maintain backward compatibility.")
        (tmp_path / "README.md").write_text("# My Agent\n\nAn AI agent.")
        (tmp_path / "LICENSE.md").write_text("MIT License")

        results = scan_directory(tmp_path)
        scanned_names = {Path(p).name for p in results}
        assert "SKILL.md" in scanned_names
        assert "CHANGELOG.md" not in scanned_names
        assert "README.md" not in scanned_names
        assert "LICENSE.md" not in scanned_names

    def test_exclude_patterns(self, tmp_path):
        """--exclude should filter matching files."""
        (tmp_path / "config.yaml").write_text("system_prompt: You are helpful.")
        (tmp_path / "test_config.yaml").write_text("system_prompt: Test mode.")

        results = scan_directory(tmp_path, exclude=["test_*"])
        scanned_names = {Path(p).name for p in results}
        assert "config.yaml" in scanned_names
        assert "test_config.yaml" not in scanned_names

    def test_lintlangignore(self, tmp_path):
        """.lintlangignore should filter matching files."""
        (tmp_path / "config.yaml").write_text("system_prompt: You are helpful.")
        (tmp_path / "draft.md").write_text("You are a draft assistant.")
        (tmp_path / ".lintlangignore").write_text("draft.md\n")

        results = scan_directory(tmp_path)
        scanned_names = {Path(p).name for p in results}
        assert "config.yaml" in scanned_names
        assert "draft.md" not in scanned_names


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
