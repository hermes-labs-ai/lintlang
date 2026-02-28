"""Tests for the CLI interface."""

import pytest
from pathlib import Path

from lingdiag.cli import main


SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestCLI:
    def test_scan_clean_config(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml")])
        assert exit_code == 0

    def test_scan_bad_config(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml")])
        assert exit_code == 0

    def test_scan_with_pattern_filter(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--patterns", "H1"])
        assert exit_code == 0

    def test_scan_json_format(self, capsys):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--format", "json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"health_score": 100.0' in captured.out

    def test_scan_markdown_format(self, capsys):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--format", "markdown"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "# Linguistic Diagnostics Report" in captured.out

    def test_fail_under_passes(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--fail-under", "80"])
        assert exit_code == 0

    def test_fail_under_fails(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_agent_config.json"), "--fail-under", "80"])
        assert exit_code == 1

    def test_patterns_command(self):
        exit_code = main(["patterns"])
        assert exit_code == 0

    def test_no_command_shows_help(self):
        exit_code = main([])
        assert exit_code == 0

    def test_multiple_files(self):
        exit_code = main([
            "scan",
            str(SAMPLES_DIR / "clean_config.yaml"),
            str(SAMPLES_DIR / "bad_tool_descriptions.yaml"),
        ])
        assert exit_code == 0

    def test_missing_file_returns_error(self):
        """CLI should return 1 when no files are successfully scanned."""
        exit_code = main(["scan", "/nonexistent/file.yaml"])
        assert exit_code == 1

    def test_fail_under_with_missing_file_doesnt_pass(self):
        """CLI should not silently pass when all files are missing."""
        exit_code = main(["scan", "/nonexistent/file.yaml", "--fail-under", "80"])
        assert exit_code == 1

    def test_min_severity_filter(self, capsys):
        exit_code = main([
            "scan",
            str(SAMPLES_DIR / "bad_system_prompt.txt"),
            "--min-severity", "high",
            "--format", "json",
        ])
        assert exit_code == 0
        import json
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for result in data:
            for finding in result["findings"]:
                assert finding["severity"] in ("critical", "high")
