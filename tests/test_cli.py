"""Tests for the CLI interface."""

import json
from pathlib import Path

import pytest

from lintlang.cli import main
from lintlang.report import format_markdown, format_summary_table, format_terminal
from lintlang.scanner import input_error_result

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestCLI:
    def test_public_formatters_never_render_input_error_as_clean(self, tmp_path):
        result = input_error_result(tmp_path / "missing.yaml", "File not found")

        terminal = format_terminal(result)
        markdown = format_markdown(result)
        assert "ERROR" in terminal
        assert "Input error: File not found" in terminal
        assert "No structural issues found" not in terminal
        assert "**ERROR**" in markdown
        assert "**Input error:** File not found" in markdown
        assert "No structural issues found" not in markdown

        summary = format_summary_table({"one": result, "two": result}, elapsed=0.01)
        assert "2 ERROR" in summary
        assert "0 FAIL" in summary
        assert "input error" in summary
        assert "clean" not in summary

    def test_scan_clean_config(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml")])
        assert exit_code == 0

    def test_scan_bad_config(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml")])
        assert exit_code == 0

    def test_scan_with_pattern_filter(self):
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--patterns", "H1"])
        assert exit_code == 0

    def test_scan_help_does_not_expose_embeddings(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["scan", "--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--enable-embeddings" not in captured.out

    def test_removed_embedding_flag_is_rejected(self):
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "scan",
                    str(SAMPLES_DIR / "clean_config.yaml"),
                    "--enable-embeddings",
                ]
            )

        assert exc_info.value.code == 2

    def test_direct_python_file_inside_venv_is_scannable(self, tmp_path, capsys):
        py_file = tmp_path / ".venv" / "pipeline.py"
        py_file.parent.mkdir()
        py_file.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

        exit_code = main(["scan", str(py_file), "--format", "json"])

        assert exit_code == 0
        captured = capsys.readouterr()
        [result] = json.loads(captured.out)
        assert result["file"] == str(py_file)
        assert any(finding["pattern_id"] == "P1" for finding in result["structural_findings"])

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
        exit_code = main(
            [
                "scan",
                str(SAMPLES_DIR / "clean_config.yaml"),
                str(SAMPLES_DIR / "bad_tool_descriptions.yaml"),
            ]
        )
        assert exit_code == 0

    def test_missing_file_returns_error(self):
        """CLI should return 1 when no files are successfully scanned."""
        exit_code = main(["scan", "/nonexistent/file.yaml"])
        assert exit_code == 1

    def test_fail_on_with_missing_file(self):
        """CLI should not silently pass when all files are missing."""
        exit_code = main(["scan", "/nonexistent/file.yaml", "--fail-on", "fail"])
        assert exit_code == 1

    def test_fail_on_with_valid_and_missing_file_is_input_error(self, tmp_path, capsys):
        """A valid input must not mask an explicitly requested missing input."""
        valid = tmp_path / "valid.yaml"
        valid.write_text("system_prompt: You are helpful.")
        missing = tmp_path / "missing.yaml"

        exit_code = main(
            [
                "scan",
                str(valid),
                str(missing),
                "--format",
                "json",
                "--fail-on",
                "fail",
            ]
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        by_file = {item["file"]: item for item in data}
        assert by_file[str(valid)]["verdict"] == "PASS"
        assert by_file[str(valid)]["input_error"] is None
        assert by_file[str(missing)]["verdict"] == "ERROR"
        assert by_file[str(missing)]["input_error"] == "File not found"
        assert f"Input error: {missing}: File not found" in captured.err

    def test_terminal_reports_and_counts_valid_and_missing_inputs(self, tmp_path, capsys):
        valid = tmp_path / "valid.yaml"
        valid.write_text("system_prompt: You are helpful.")
        missing = tmp_path / "missing.yaml"

        exit_code = main(["scan", str(valid), str(missing)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert str(valid) in captured.out
        assert str(missing) in captured.out
        assert "ERROR" in captured.out
        assert "2 files scanned" in captured.out
        assert "1 ERROR" in captured.out
        assert "Input error" in captured.err

    def test_fail_on_with_directory_parse_error_is_input_error(self, tmp_path, capsys):
        """A malformed supported file found in a directory must fail closed."""
        (tmp_path / "valid.yaml").write_text("system_prompt: You are helpful.")
        malformed = tmp_path / "broken.json"
        malformed.write_text('{"system_prompt": "unterminated"')

        exit_code = main(
            [
                "scan",
                str(tmp_path),
                "--format",
                "json",
                "--fail-on",
                "fail",
            ]
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        by_file = {item["file"]: item for item in data}
        assert by_file[str(malformed)]["verdict"] == "ERROR"
        assert "Failed to parse" in by_file[str(malformed)]["input_error"]
        assert by_file[str(malformed)]["structural_findings"] == []
        assert by_file[str(malformed)]["herm"] is None
        assert f"Input error: {malformed}: Failed to parse" in captured.err

    def test_min_severity_filter(self, capsys):
        exit_code = main(
            [
                "scan",
                str(SAMPLES_DIR / "bad_system_prompt.txt"),
                "--min-severity",
                "high",
                "--format",
                "json",
            ]
        )
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
