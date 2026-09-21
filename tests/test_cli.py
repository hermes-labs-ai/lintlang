"""Tests for the CLI interface."""

import json
import sys
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

    def test_scan_sarif_emits_sarif_2_1_0_document(self, capsys):
        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml"), "--format", "sarif"])

        assert exit_code == 0
        captured = capsys.readouterr()
        document = json.loads(captured.out)
        assert document["version"] == "2.1.0"
        assert document["$schema"] == (
            "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/"
            "schemas/sarif-schema-2.1.0.json"
        )
        assert len(document["runs"]) == 1

    def test_sarif_parser_error_does_not_expose_source_evidence_on_stderr(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "agent.yaml"
        private_value = "PRIVATE_PROMPT_EVIDENCE"
        source.write_text(f"system_prompt: [{private_value}\n", encoding="utf-8")

        exit_code = main(["scan", str(source), "--format", "sarif"])

        assert exit_code == 1
        captured = capsys.readouterr()
        json.loads(captured.out)
        assert private_value not in captured.out
        assert private_value not in captured.err
        assert str(source) not in captured.err

    def test_sarif_relative_input_from_git_subdirectory_uses_repository_path(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        configs = repository / "configs"
        configs.mkdir()
        (configs / "agent.yaml").write_text(
            "system_prompt: Keep trying until it works.\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(configs)

        exit_code = main(["scan", "agent.yaml", "--format", "sarif"])

        assert exit_code == 0
        document = json.loads(capsys.readouterr().out)
        artifact_uris = {
            result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for result in document["runs"][0]["results"]
        }
        assert artifact_uris == {"configs/agent.yaml"}

    def test_sarif_shared_filters_apply_before_emission_and_verdict(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "agent.yaml"
        source.write_text(
            "system_prompt: Keep trying until it works. Respond in JSON and Markdown.\n",
            encoding="utf-8",
        )

        exit_code = main(
            [
                "scan",
                str(source),
                "--format",
                "sarif",
                "--patterns",
                "H6",
                "--min-severity",
                "medium",
                "--no-suggestions",
                "--fail-on",
                "review",
            ]
        )

        assert exit_code == 1
        document = json.loads(capsys.readouterr().out)
        run = document["runs"][0]
        assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == ["H6"]
        assert {result["ruleId"] for result in run["results"]} == {"H6"}
        assert all(result["level"] == "warning" for result in run["results"])
        assert all("Suggested action:" not in result["message"]["text"] for result in run["results"])

    def test_sarif_preserves_legacy_fail_under_and_directory_exclude(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        source_dir = tmp_path / "configs"
        source_dir.mkdir()
        (source_dir / "clean.yaml").write_text("system_prompt: You are helpful.\n", encoding="utf-8")
        (source_dir / "excluded.yaml").write_text(
            "system_prompt: Keep trying until it works.\n",
            encoding="utf-8",
        )

        exit_code = main(
            [
                "scan",
                str(source_dir),
                "--format",
                "sarif",
                "--exclude",
                "excluded.yaml",
                "--fail-under",
                "101",
            ]
        )

        assert exit_code == 1
        document = json.loads(capsys.readouterr().out)
        run = document["runs"][0]
        assert run["invocations"][0]["executionSuccessful"] is True
        assert run["results"] == []

    def test_sarif_rejects_out_of_root_source_without_absolute_path_leakage(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        outside = tmp_path / "private" / "agent.yaml"
        outside.parent.mkdir()
        outside.write_text("system_prompt: Keep trying until it works.\n", encoding="utf-8")
        monkeypatch.chdir(repository)

        exit_code = main(["scan", str(outside), "--format", "sarif"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out
        run = json.loads(captured.out)["runs"][0]
        assert run["results"] == []
        assert run["invocations"][0]["executionSuccessful"] is False
        assert "inside the repository root" in captured.err

    def test_sarif_out_of_root_error_preserves_valid_in_root_findings(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        inside = repository / "agent.yaml"
        inside.write_text("system_prompt: Keep trying until it works.\n", encoding="utf-8")
        outside = tmp_path / "private" / "agent.yaml"
        outside.parent.mkdir()
        outside.write_text("system_prompt: Respond in JSON and Markdown.\n", encoding="utf-8")
        monkeypatch.chdir(repository)

        exit_code = main(["scan", str(inside), str(outside), "--format", "sarif"])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out
        run = json.loads(captured.out)["runs"][0]
        assert run["invocations"][0]["executionSuccessful"] is False
        assert run["results"]
        assert {
            result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
            for result in run["results"]
        } == {"agent.yaml"}

    @pytest.mark.parametrize("output_format", ["terminal", "markdown", "json", "sarif"])
    @pytest.mark.parametrize("fail_on", [None, "fail", "review"])
    @pytest.mark.parametrize(
        ("source_text", "expected"),
        [
            ("system_prompt: You are helpful.", {None: 0, "fail": 0, "review": 0}),
            ("system_prompt: Respond in JSON and Markdown.", {None: 0, "fail": 0, "review": 1}),
            ("system_prompt: Keep trying until it works.", {None: 0, "fail": 1, "review": 1}),
            (None, {None: 1, "fail": 1, "review": 1}),
        ],
    )
    def test_format_fail_on_and_verdict_exit_matrix(
        self,
        output_format,
        fail_on,
        source_text,
        expected,
        capsys,
        monkeypatch,
        tmp_path,
    ):
        monkeypatch.chdir(tmp_path)
        source = tmp_path / "agent.yaml"
        if source_text is not None:
            source.write_text(source_text, encoding="utf-8")
        args = ["scan", str(source), "--format", output_format]
        if fail_on is not None:
            args.extend(["--fail-on", fail_on])

        exit_code = main(args)

        assert exit_code == expected[fail_on]
        captured = capsys.readouterr()
        if output_format in {"json", "sarif"}:
            json.loads(captured.out)

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

    def test_scan_terminal_redirected_output_has_no_ansi(self, capsys, monkeypatch):
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml")])

        assert exit_code == 0
        assert "\033[" not in capsys.readouterr().out

    def test_scan_terminal_honors_no_color(self, capsys, monkeypatch):
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        monkeypatch.setenv("NO_COLOR", "1")

        exit_code = main(["scan", str(SAMPLES_DIR / "clean_config.yaml")])

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "\033[" not in output
        assert "https://github.com/hermes-labs-ai/lintlang" in output

    def test_scan_terminal_multi_file_repo_pointer_is_emitted_once(self, capsys, monkeypatch):
        """Interactive multi-file scans should point to the repo once overall."""
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

        exit_code = main(
            [
                "scan",
                str(SAMPLES_DIR / "clean_config.yaml"),
                str(SAMPLES_DIR / "bad_tool_descriptions.yaml"),
            ]
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        pointer = "https://github.com/hermes-labs-ai/lintlang"
        assert captured.out.count(pointer) == 1
        assert captured.out.rfind(pointer) > captured.out.find("SUMMARY")

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

    def test_directory_scan_with_no_matching_files_is_an_input_error(self, tmp_path, capsys):
        """A valid directory containing only non-prompt files (README, LICENSE)
        has zero scannable candidates. An invoked scan that inspected nothing
        proves no coverage, so it is an input error at the process boundary
        (previously: exit 0 with a bare stderr note). ``--allow-empty`` is the
        only opt-out; see TestEmptyScanIsNonzero.
        """
        (tmp_path / "README.md").write_text("# hi\n")
        (tmp_path / "LICENSE").write_text("MIT\n")

        exit_code = main(["scan", str(tmp_path)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error: No files were inspected" in captured.err
        assert "--allow-empty" in captured.err

        assert main(["scan", str(tmp_path), "--allow-empty"]) == 0
        assert "Error:" not in capsys.readouterr().err

    def test_python_scan_with_only_python_excluded_patterns_warns(self, tmp_path, capsys):
        """scan_python_file() never runs H1/H3/H7 against extracted prompts —
        they reason over a declared config schema that AST extraction from
        .py source does not produce. Requesting --patterns H1 against a .py
        file therefore always scores zero structural findings, which would
        otherwise look identical to a genuinely clean PASS to a CI gate using
        --fail-on. The CLI must warn instead of staying silent.
        """
        python_file = tmp_path / "pipeline.py"
        python_file.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

        exit_code = main(["scan", str(python_file), "--patterns", "H1", "--fail-on", "fail"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "H1" in captured.err
        assert "do not apply to Python extraction mode" in captured.err

    def test_python_scan_with_applicable_pattern_does_not_warn(self, tmp_path, capsys):
        """The warning is specific to patterns scan_python_file() always
        skips — a pattern it actually runs (H2) must not trigger it."""
        python_file = tmp_path / "pipeline.py"
        python_file.write_text("CONFIDENCE_THRESHOLD = 0.75\n")

        exit_code = main(["scan", str(python_file), "--patterns", "H2"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "do not apply to Python extraction mode" not in captured.err

    def test_non_python_scan_with_excluded_patterns_does_not_warn(self, capsys):
        """The warning only fires for .py inputs — H1/H3/H7 are the normal,
        fully-applicable detectors for YAML/JSON/text config files."""
        exit_code = main(["scan", str(SAMPLES_DIR / "bad_tool_descriptions.yaml"), "--patterns", "H1"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "do not apply to Python extraction mode" not in captured.err

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


class TestRepositoryDiscovery:
    """`--discover` is an opt-in repository mode over recognized instruction
    surfaces. Explicit inputs stay canonical and generic directory scanning
    keeps its broad extension sweep."""

    @staticmethod
    def _repository(root: Path) -> None:
        (root / "AGENTS.md").write_text("You are an agent. Follow the steps.\n", encoding="utf-8")
        (root / "README.md").write_text("# Readme\n", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "notes.md").write_text("Some prose about the project.\n", encoding="utf-8")
        skill = root / "skills" / "audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Audit the config carefully.\n", encoding="utf-8")

    def test_discover_selects_only_recognized_instruction_files(self, tmp_path, monkeypatch, capsys):
        self._repository(tmp_path)
        monkeypatch.chdir(tmp_path)

        exit_code = main(["scan", "--discover", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert sorted(Path(item["file"]).name for item in data) == ["AGENTS.md", "SKILL.md"]

    def test_discover_accepts_an_explicit_root(self, tmp_path, capsys):
        self._repository(tmp_path)

        exit_code = main(["scan", "--discover", str(tmp_path), "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert sorted(Path(item["file"]).name for item in data) == ["AGENTS.md", "SKILL.md"]

    def test_generic_directory_scan_is_unchanged_by_discovery(self, tmp_path, capsys):
        """A plain directory argument keeps the broad extension sweep: it still
        inspects docs/notes.md, which discovery deliberately never selects."""
        self._repository(tmp_path)

        exit_code = main(["scan", str(tmp_path), "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        names = sorted(Path(item["file"]).name for item in data)
        assert names == ["AGENTS.md", "SKILL.md", "notes.md"]

    def test_discover_unions_and_dedupes_with_explicit_files(self, tmp_path, monkeypatch, capsys):
        self._repository(tmp_path)
        monkeypatch.chdir(tmp_path)

        exit_code = main(["scan", "AGENTS.md", "docs/notes.md", "--discover", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        files = [item["file"] for item in data]
        assert files.count("AGENTS.md") == 1
        assert sorted(Path(f).name for f in files) == ["AGENTS.md", "SKILL.md", "notes.md"]

    def test_discover_names_the_instruction_symlinks_it_skipped(self, tmp_path, capsys):
        """Discovery does not follow symlinks, and it must not hide that.

        A recognized instruction file that is a symlink is a coverage gap: it
        is not scanned, and nothing in the scan output says so. The scan
        continues and stays exit 0; only the gap is named, on stderr.
        """
        self._repository(tmp_path)
        (tmp_path / "CLAUDE.md").symlink_to(tmp_path / "AGENTS.md")
        (tmp_path / "LICENSE.md").symlink_to(tmp_path / "README.md")

        exit_code = main(["scan", "--discover", str(tmp_path), "--format", "json"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert sorted(Path(item["file"]).name for item in json.loads(captured.out)) == ["AGENTS.md", "SKILL.md"]
        assert "CLAUDE.md: it is a symlink" in captured.err
        assert "does not follow symlinks" in captured.err
        # An unrecognized symlink was never a discovery target, so it is not a gap.
        assert "LICENSE.md" not in captured.err

    def test_discover_is_silent_when_no_instruction_symlink_was_skipped(self, tmp_path, capsys):
        self._repository(tmp_path)

        assert main(["scan", "--discover", str(tmp_path), "--format", "json"]) == 0
        assert "symlink" not in capsys.readouterr().err

    def test_discover_symlink_notice_honours_exclude_globs(self, tmp_path, capsys):
        """An excluded path is not a coverage gap: the caller said so."""
        self._repository(tmp_path)
        (tmp_path / "docs" / "CLAUDE.md").symlink_to(tmp_path / "AGENTS.md")

        exit_code = main(["scan", "--discover", str(tmp_path), "--exclude", "docs/**", "--format", "json"])

        assert exit_code == 0
        assert "symlink" not in capsys.readouterr().err

    def test_discover_root_must_exist(self, tmp_path, capsys):
        exit_code = main(["scan", "--discover", str(tmp_path / "absent")])

        assert exit_code == 1
        assert "Error:" in capsys.readouterr().err

    def test_discover_with_no_recognized_files_is_an_empty_scan_error(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")

        exit_code = main(["scan", "--discover", str(tmp_path)])

        assert exit_code == 1
        assert "No files were inspected" in capsys.readouterr().err

    def test_scan_without_files_or_discover_fails_clearly(self, capsys):
        exit_code = main(["scan"])

        assert exit_code != 0
        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "--discover" in captured.err

    def test_discover_root_that_is_a_file_explains_the_spelling(self, tmp_path, capsys):
        """`--discover` takes an optional ROOT, so `scan --discover FILE` reads
        FILE as that root. Say so rather than reporting a bare type error."""
        target = tmp_path / "AGENTS.md"
        target.write_text("You are an agent.\n", encoding="utf-8")

        exit_code = main(["scan", "--discover", str(target)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "not a directory" in captured.err
        assert "scan FILE --discover" in captured.err

    def test_discover_honours_exclude_globs(self, tmp_path, monkeypatch, capsys):
        """Discovery is an input source, not a separate filtering contract: a
        repository that keeps deliberately broken instruction fixtures must be
        able to keep them out of its own repository-mode gate."""
        self._repository(tmp_path)
        fixtures = tmp_path / "tests" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "AGENTS.md").write_text("Loop over the queue indefinitely.\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        exit_code = main(["scan", "--discover", "--exclude", "tests/**", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert all("fixtures" not in item["file"] for item in data)
        assert sorted(Path(item["file"]).name for item in data) == ["AGENTS.md", "SKILL.md"]

    def test_discover_honours_lintlangignore(self, tmp_path, monkeypatch, capsys):
        self._repository(tmp_path)
        vendored = tmp_path / "vendor" / "pkg"
        vendored.mkdir(parents=True)
        (vendored / "AGENTS.md").write_text("Loop over the queue indefinitely.\n", encoding="utf-8")
        (tmp_path / ".lintlangignore").write_text("vendor/**\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        exit_code = main(["scan", "--discover", "--format", "json"])

        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert all("vendor" not in item["file"] for item in data)

    def test_discover_is_rejected_together_with_stdin(self, tmp_path, capsys):
        """One invocation, one unambiguous source of files. A union would have
        to define what happens when the virtual stdin path and a discovered
        path name the same document; rejecting is the smaller contract."""
        self._repository(tmp_path)

        exit_code = main(["scan", "-", "--stdin-filename", "AGENTS.md", "--discover", str(tmp_path)])

        assert exit_code == 2
        assert "cannot be combined with --discover" in capsys.readouterr().err


class TestEmptyScanIsNonzero:
    """An invoked scan that inspects zero files is an input/coverage error at
    every boundary: terminal, JSON, SARIF, and process status."""

    def test_directory_scan_with_no_matching_files_is_an_error(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
        (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")

        exit_code = main(["scan", str(tmp_path)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error: No files were inspected" in captured.err
        assert "--allow-empty" in captured.err

    def test_empty_scan_json_reports_the_error(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")

        exit_code = main(["scan", str(tmp_path), "--format", "json"])

        assert exit_code == 1
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["verdict"] == "ERROR"
        assert "No files were inspected" in data[0]["input_error"]
        assert data[0]["inspected"] == {}
        assert data[0]["not_inspected"] == []
        assert data[0]["skipped"] is None
        assert data[0]["structural_findings"] == []
        assert data[0]["herm"] is None

    def test_empty_scan_sarif_is_unsuccessful_and_nonzero(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")

        exit_code = main(["scan", str(tmp_path), "--format", "sarif"])

        assert exit_code == 1
        document = json.loads(capsys.readouterr().out)
        invocation = document["runs"][0]["invocations"][0]
        assert invocation["executionSuccessful"] is False
        assert "No files were inspected" in invocation["toolExecutionNotifications"][0]["message"]["text"]

    def test_allow_empty_restores_exit_zero(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")

        exit_code = main(["scan", str(tmp_path), "--allow-empty", "--format", "json"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == []
        assert "No matching files found to scan." in captured.err
        assert "Error:" not in captured.err

    def test_allow_empty_sarif_agrees_with_the_exit_status(self, tmp_path, capsys):
        """The whole point of the zero-file contract is that the report and the
        process status never disagree. `--allow-empty` is an accepted outcome,
        so SARIF must not declare the run unsuccessful at exit 0."""
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")

        exit_code = main(["scan", str(tmp_path), "--allow-empty", "--format", "sarif"])

        assert exit_code == 0
        document = json.loads(capsys.readouterr().out)
        invocation = document["runs"][0]["invocations"][0]
        assert invocation["executionSuccessful"] is True
        assert "toolExecutionNotifications" not in invocation

    def test_write_baseline_empty_scan_error_is_unchanged(self, tmp_path, capsys):
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
        baseline = tmp_path / "baseline.json"

        exit_code = main(["scan", str(tmp_path), "--format", "json", "--write-baseline", str(baseline)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert json.loads(captured.out) == []
        assert "No files were successfully scanned" in captured.err
        assert f"baseline {baseline} was not written." in captured.err
        assert not baseline.exists()
