"""Exactly one stdin scan, identified by a required virtual path.

``lintlang scan - --stdin-filename <virtual-path>`` lets a generator hand
LintLang a document it never wrote to disk. The virtual path — not the stream —
drives parser selection, locations, JSON/SARIF identity, and baseline matching.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from lintlang.cli import main

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture
def stdin_text(monkeypatch):
    def _set(text: str) -> None:
        monkeypatch.setattr("sys.stdin", io.StringIO(text))

    return _set


class TestStdinRejections:
    def test_dash_without_stdin_filename_is_rejected(self, stdin_text, capsys):
        stdin_text("system_prompt: Be concise.\n")

        exit_code = main(["scan", "-"])

        assert exit_code != 0
        assert "--stdin-filename" in capsys.readouterr().err

    def test_more_than_one_dash_is_rejected(self, stdin_text, capsys):
        stdin_text("system_prompt: Be concise.\n")

        exit_code = main(["scan", "-", "-", "--stdin-filename", "agent.yaml"])

        assert exit_code != 0
        assert "exactly once" in capsys.readouterr().err

    def test_stdin_filename_without_dash_is_rejected(self, capsys):
        exit_code = main(
            ["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--stdin-filename", "agent.yaml"]
        )

        assert exit_code != 0
        assert "--stdin-filename" in capsys.readouterr().err


class TestStdinIdentity:
    def test_virtual_path_drives_parser_selection(self, stdin_text, capsys):
        stdin_text('{"system_prompt": "You are helpful."}\n')

        exit_code = main(["scan", "-", "--stdin-filename", "config/agent.json", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["file"] == "config/agent.json"
        assert data[0]["input_error"] is None

    def test_virtual_path_is_used_for_locations(self, stdin_text, capsys):
        source = (SAMPLES_DIR / "bad_tool_descriptions.yaml").read_text(encoding="utf-8")
        stdin_text(source)

        exit_code = main(["scan", "-", "--stdin-filename", "virtual/tools.yaml", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert data[0]["file"] == "virtual/tools.yaml"
        assert data[0]["structural_findings"]

    @pytest.mark.parametrize(
        "sample",
        ("clean_config.yaml", "bad_tool_descriptions.yaml", "bad_system_prompt.txt"),
    )
    def test_stdin_json_matches_a_real_file_scan(self, sample, stdin_text, capsys):
        path = SAMPLES_DIR / sample

        assert main(["scan", str(path), "--format", "json"]) == 0
        from_file = capsys.readouterr().out

        stdin_text(path.read_text(encoding="utf-8"))
        assert main(["scan", "-", "--stdin-filename", str(path), "--format", "json"]) == 0
        from_stdin = capsys.readouterr().out

        assert from_stdin == from_file

    def test_python_virtual_path_uses_extraction(self, stdin_text, capsys):
        stdin_text('CONFIDENCE_THRESHOLD = 0.75\n')

        exit_code = main(["scan", "-", "--stdin-filename", "pipeline.py", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert data[0]["file"] == "pipeline.py"
        assert [f["pattern_id"] for f in data[0]["structural_findings"]] == ["P1"]

    def test_python_stdin_matches_a_real_python_file_scan(self, tmp_path, stdin_text, capsys):
        source = "SYSTEM_PROMPT = 'You are a helpful assistant. Respond in JSON format.'\nTHRESHOLD = 0.82\n"
        real = tmp_path / "pipeline.py"
        real.write_text(source, encoding="utf-8")

        assert main(["scan", str(real), "--format", "json"]) == 0
        from_file = capsys.readouterr().out

        stdin_text(source)
        assert main(["scan", "-", "--stdin-filename", str(real), "--format", "json"]) == 0
        from_stdin = capsys.readouterr().out

        assert from_stdin == from_file

    def test_unparsable_python_stdin_is_a_fatal_input_error(self, stdin_text, capsys):
        stdin_text("def broken(:\n")

        exit_code = main(["scan", "-", "--stdin-filename", "pipeline.py", "--format", "json"])

        assert exit_code == 1
        data = json.loads(capsys.readouterr().out)
        assert data[0]["verdict"] == "ERROR"
        assert "Python parse error" in data[0]["input_error"]

    def test_stdin_can_be_combined_with_explicit_files(self, stdin_text, capsys):
        stdin_text("system_prompt: Be concise.\n")

        exit_code = main(
            [
                "scan",
                str(SAMPLES_DIR / "clean_config.yaml"),
                "-",
                "--stdin-filename", "virtual/agent.yaml",
                "--format", "json",
            ]
        )

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert [item["file"] for item in data] == [
            str(SAMPLES_DIR / "clean_config.yaml"),
            "virtual/agent.yaml",
        ]

    def test_baseline_matches_on_the_virtual_path(self, tmp_path, monkeypatch, stdin_text, capsys):
        """A baseline recorded from a real file suppresses the same findings
        when the identical document arrives on stdin under that path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()
        source = (SAMPLES_DIR / "bad_tool_descriptions.yaml").read_text(encoding="utf-8")
        real = tmp_path / "tools.yaml"
        real.write_text(source, encoding="utf-8")
        baseline = tmp_path / "baseline.json"

        assert main(["scan", "tools.yaml", "--write-baseline", str(baseline)]) == 0
        capsys.readouterr()

        stdin_text(source)
        assert main(["scan", "-", "--stdin-filename", "tools.yaml", "--baseline", str(baseline), "--format", "json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data[0]["file"] == "tools.yaml"
        assert data[0]["structural_findings"] == []
        assert data[0]["baseline"]["suppressed"] > 0
