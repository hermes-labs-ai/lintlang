"""Tests for the CLI interface."""

import json
from pathlib import Path

from lintlang.cli import main

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
        data = json.loads(captured.out)
        assert len(data) == 1
        assert "verdict" in data[0]
        assert "structural_findings" in data[0]
        # HERM data preserved under 'herm' key
        assert "herm" in data[0]
        assert "score" in data[0]["herm"]
        assert "dimensions" in data[0]["herm"]

    def test_scan_json_verdict_values(self, capsys):
        """Clean config should have PASS verdict in JSON."""
        main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["verdict"] == "PASS"

    def test_scan_json_bad_config_verdict(self, capsys):
        """Bad config should have FAIL or REVIEW verdict."""
        main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--format", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["verdict"] in ("FAIL", "REVIEW")

    def test_scan_markdown_format(self, capsys):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--format", "markdown"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "# Lintlang Report" in captured.out
        assert "Verdict:" in captured.out

    def test_scan_terminal_shows_verdict(self, capsys):
        """Terminal output should show verdict, not HERM score."""
        main(["scan", str(SAMPLES_DIR / "clean_config.yaml")])
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        # HERM score should NOT appear in terminal output
        assert "HERM Score:" not in captured.out

    def test_fail_on_fail_passes_clean(self):
        """Clean config should pass with --fail-on fail."""
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--fail-on", "fail"])
        assert exit_code == 0

    def test_fail_on_fail_catches_bad(self):
        """Bad config with CRITICAL findings should fail with --fail-on fail."""
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--fail-on", "fail"])
        assert exit_code == 1

    def test_fail_on_review_catches_medium(self):
        """Config with MEDIUM findings should fail with --fail-on review."""
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_system_prompt.txt"), "--fail-on", "review"])
        assert exit_code == 1

    def test_legacy_fail_under_still_works(self):
        """Legacy --fail-under should still function."""
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_agent_config.json"), "--fail-under", "99"])
        assert exit_code == 1

    def test_legacy_fail_under_passes(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--fail-under", "80"])
        assert exit_code == 0

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

    def test_fail_on_with_missing_file(self):
        """CLI should not silently pass when all files are missing."""
        exit_code = main(["scan", "/nonexistent/file.yaml", "--fail-on", "fail"])
        assert exit_code == 1

    def test_min_severity_filter(self, capsys):
        exit_code = main([
            "scan",
            str(SAMPLES_DIR / "bad_system_prompt.txt"),
            "--min-severity", "high",
            "--format", "json",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for result in data:
            # Structural findings should only be high or critical
            for finding in result["structural_findings"]:
                assert finding["severity"] in ("critical", "high")

    def test_json_output_structure(self, capsys):
        """JSON output should have verdict + structural_findings + herm."""
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--format", "json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        result = data[0]
        assert "verdict" in result
        assert "structural_findings" in result
        assert "herm" in result
        assert "score" in result["herm"]
        assert "dimensions" in result["herm"]
        assert "signal_counts" in result["herm"]
        assert "coverage" in result["herm"]
        assert "confidence" in result["herm"]
