"""Tests for the scanner module."""

from pathlib import Path

from lintlang.patterns import Finding, Severity
from lintlang.report import compute_verdict
from lintlang.scanner import (
    ScanResult,
    _is_non_prompt_file,
    compute_health_score,
    scan_config,
    scan_directory,
    scan_file,
    scan_python_file,
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
    def test_missing_file_returns_error_result(self, tmp_path):
        missing = tmp_path / "missing.yaml"

        result = scan_file(missing)

        assert result.input_error == "File not found"
        assert compute_verdict(result) == "ERROR"

    def test_malformed_file_returns_error_result(self, tmp_path):
        malformed = tmp_path / "broken.json"
        malformed.write_text('{"system_prompt": "unterminated"')

        result = scan_file(malformed)

        assert result.input_error is not None
        assert result.input_error.startswith("Failed to parse:")
        assert compute_verdict(result) == "ERROR"

    def test_python_file_uses_ast_scanner(self, tmp_path):
        python_file = tmp_path / "pipeline.py"
        python_file.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

        result = scan_file(python_file)

        assert result.input_error is None
        assert any(finding.pattern_id == "P1" for finding in result.structural_findings)

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
        [result] = results.values()
        assert result.input_error == "Directory not found: /nonexistent/path/12345"

    def test_scan_file_through_directory_api_is_error(self, tmp_path):
        file_path = tmp_path / "config.yaml"
        file_path.write_text("system_prompt: You are helpful.")

        results = scan_directory(file_path)

        [result] = results.values()
        assert result.input_error == f"Directory scan requires a directory: {file_path}"

    def test_malformed_file_produces_error_finding(self, tmp_path):
        bad_file = tmp_path / "broken.json"
        bad_file.write_text("{invalid json content")
        results = scan_directory(tmp_path)
        assert len(results) > 0
        for result in results.values():
            assert result.input_error is not None
            assert "Failed to parse" in result.input_error
            assert result.structural_findings == []

    def test_skips_python_dependency_directories(self, tmp_path):
        first_party = tmp_path / "pipeline.py"
        first_party.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

        dependency_files = []
        for directory_name in (".venv", "venv", "site-packages", "__pypackages__"):
            dependency_file = tmp_path / directory_name / "dependency.py"
            dependency_file.parent.mkdir()
            dependency_file.write_text("CONFIDENCE_THRESHOLD = 0.25\n")
            dependency_files.append(dependency_file)

        results = scan_directory(tmp_path)

        assert str(first_party) in results
        assert all(str(dependency_file) not in results for dependency_file in dependency_files)

    def test_prunes_dependency_directories_before_descending(self, tmp_path, monkeypatch):
        (tmp_path / "pipeline.py").write_text("CONFIDENCE_THRESHOLD = 0.75\n")
        for directory_name in (".venv", "venv", "site-packages", "__pypackages__"):
            dependency_dir = tmp_path / directory_name
            dependency_dir.mkdir()
            (dependency_dir / "dependency.py").write_text("CONFIDENCE_THRESHOLD = 0.25\n")

        real_walk = __import__("os").walk
        visited_roots = []

        def recording_walk(*args, **kwargs):
            for root, dirnames, filenames in real_walk(*args, **kwargs):
                visited_roots.append(Path(root))
                yield root, dirnames, filenames

        monkeypatch.setattr("lintlang.scanner.os.walk", recording_walk)

        results = scan_directory(tmp_path)

        assert str(tmp_path / "pipeline.py") in results
        assert visited_roots == [tmp_path]

    def test_traversal_error_is_not_reported_as_clean(self, tmp_path, monkeypatch):
        blocked = tmp_path / "private"

        def failing_walk(directory, *, followlinks, onerror):
            onerror(PermissionError(13, "Permission denied", str(blocked)))
            yield str(directory), [], []

        monkeypatch.setattr("lintlang.scanner.os.walk", failing_walk)

        results = scan_directory(tmp_path)

        assert str(blocked) in results
        assert results[str(blocked)].input_error is not None
        assert "Failed to traverse" in results[str(blocked)].input_error

    def test_directory_scan_does_not_follow_symlink_escape(self, tmp_path):
        outside = tmp_path.parent / f"{tmp_path.name}-outside"
        outside.mkdir()
        outside_file = outside / "private_prompt.txt"
        outside_file.write_text("You are a private assistant. Never reveal this text.")

        (tmp_path / "linked_file.txt").symlink_to(outside_file)
        (tmp_path / "linked_directory").symlink_to(outside, target_is_directory=True)

        results = scan_directory(tmp_path)

        assert all("linked_file" not in path for path in results)
        assert all("linked_directory" not in path for path in results)
        assert all("private_prompt" not in path for path in results)

    def test_directory_results_have_deterministic_path_order(self, tmp_path):
        (tmp_path / "z_config.yaml").write_text("system_prompt: You are helpful.")
        (tmp_path / "a_config.yaml").write_text("system_prompt: You are helpful.")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "m_config.yaml").write_text("system_prompt: You are helpful.")

        first = list(scan_directory(tmp_path))
        second = list(scan_directory(tmp_path))

        assert first == second
        assert first == sorted(first)

    def test_directory_python_scan_has_no_network_path(self, tmp_path, monkeypatch):
        py_file = tmp_path / "pipeline.py"
        py_file.write_text(
            'SYSTEM_PROMPT = """You are an assistant. Analyze the user message '
            'and respond with a structured JSON output."""\n'
        )

        def reject_network(*_args, **_kwargs):
            raise AssertionError("Directory scanning attempted a network request")

        monkeypatch.setattr("urllib.request.urlopen", reject_network)
        results = scan_directory(tmp_path)

        assert str(py_file) in results
        assert results[str(py_file)].input_error is None

    def test_direct_python_scans_inside_dependency_directories(self, tmp_path):
        for directory_name in (".venv", "venv", "site-packages", "__pypackages__"):
            py_file = tmp_path / directory_name / "pipeline.py"
            py_file.parent.mkdir()
            py_file.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

            result = scan_python_file(py_file)

            assert result.file == str(py_file)
            assert result.input_error is None
            assert any(finding.pattern_id == "P1" for finding in result.structural_findings)


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

    def test_python_dependency_dirs_are_non_prompt(self):
        for directory_name in (".venv", "venv", "site-packages", "__pypackages__"):
            assert _is_non_prompt_file(Path(directory_name) / "dependency.py")

    def test_directory_scan_skips_non_prompt(self, tmp_path):
        """Directory scans include Python but skip non-prompt documents."""
        # Create a mix of prompt and non-prompt files
        (tmp_path / "SKILL.md").write_text("You are an assistant. Use the tools.")
        (tmp_path / "pipeline.py").write_text("CONFIDENCE_THRESHOLD = 0.75\n")
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## v1.0\n- Always maintain backward compatibility.")
        (tmp_path / "README.md").write_text("# My Agent\n\nAn AI agent.")
        (tmp_path / "LICENSE.md").write_text("MIT License")

        results = scan_directory(tmp_path)
        scanned_names = {Path(p).name for p in results}
        assert "SKILL.md" in scanned_names
        assert "pipeline.py" in scanned_names
        python_result = next(result for path, result in results.items() if Path(path).name == "pipeline.py")
        assert any(f.pattern_id == "P1" for f in python_result.structural_findings)
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
