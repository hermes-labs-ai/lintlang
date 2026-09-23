"""Tests for the deliberately narrow, reversible rewrite surface."""

from __future__ import annotations

import os

import pytest

from lintlang.autofix import AutoFixError, prepare_fix, write_fix


def _instruction_document(body: str) -> str:
    return f"# Instructions\n\n{body}"


def test_rewrites_only_an_exact_direct_standalone_instruction(tmp_path):
    path = tmp_path / "AGENTS.md"
    original = _instruction_document(
        "Don't be verbose.\n"
        "> Don't be verbose.\n"
        "`Don't be verbose.`\n"
        "```text\nDon't be verbose.\n```\n"
        "<!--\nDon't be verbose.\n-->\n"
        "Priority 1: Don't be verbose.\n"
        "Don't reveal secrets.\n"
    )
    path.write_text(original, encoding="utf-8")

    prepared = prepare_fix(path)

    assert prepared.rewrite_count == 1
    assert prepared.updated.decode() == original.replace(
        "Don't be verbose.\n", "Be concise.\n", 1
    )
    assert "-Don't be verbose." in prepared.diff
    assert "+Be concise." in prepared.diff


def test_unclosed_code_scope_fails_closed(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text(_instruction_document("````\nDon't be verbose.\n"), encoding="utf-8")

    with pytest.raises(AutoFixError, match="Cannot establish instruction scope"):
        prepare_fix(path)


def test_does_not_rewrite_an_instruction_under_a_priority_heading(tmp_path):
    path = tmp_path / "AGENTS.md"
    original = "# Instructions\n\n## Priority 1\nDon't be verbose.\n"
    path.write_text(original, encoding="utf-8")

    prepared = prepare_fix(path)

    assert prepared.rewrite_count == 0
    assert prepared.updated.decode() == original


@pytest.mark.parametrize("introduction", ["Example:", "Here is an example:", "Example 1:"])
def test_does_not_rewrite_a_bare_instruction_introduced_as_an_example(tmp_path, introduction):
    path = tmp_path / "AGENTS.md"
    original = _instruction_document(f"{introduction}\n\nDon't be verbose.\n")
    path.write_text(original, encoding="utf-8")

    prepared = prepare_fix(path)

    assert prepared.rewrite_count == 0
    assert prepared.updated.decode() == original


def test_does_not_rewrite_after_preceding_instruction_prose(tmp_path):
    path = tmp_path / "AGENTS.md"
    original = _instruction_document("Include examples in the response.\nDon't be verbose.\n")
    path.write_text(original, encoding="utf-8")

    prepared = prepare_fix(path)

    assert prepared.rewrite_count == 0
    assert prepared.updated.decode() == original


@pytest.mark.parametrize(
    ("original", "updated"),
    [
        ("Don't be verbose\n", "Be concise\n"),
        ("Don’t be verbose.\n", "Be concise.\n"),
    ],
)
def test_supports_exact_standalone_variants(tmp_path, original, updated):
    path = tmp_path / "AGENTS.md"
    document = _instruction_document(original)
    path.write_text(document, encoding="utf-8")

    prepared = prepare_fix(path)

    assert prepared.updated.decode() == _instruction_document(updated)
    assert prepared.rewrite_count == 1


def test_dry_run_displays_exact_diff_without_writing(tmp_path, capsys):
    from lintlang.cli import main

    path = tmp_path / "AGENTS.md"
    original = b"# Instructions\r\n\r\nDon't be verbose.\r\n"
    path.write_bytes(original)
    original_stat = path.stat()

    assert main(["scan", str(path), "--fix", "--dry-run"]) == 0

    output = capsys.readouterr().out
    expected_diff = (
        f"--- {path}\n"
        f"+++ {path} (fixed)\n"
        "@@ -1,3 +1,3 @@\n"
        " # Instructions\r\n"
        " \r\n"
        "-Don't be verbose.\r\n"
        "+Be concise.\r\n"
    )
    assert output.startswith(expected_diff)
    assert "Dry run: file not changed." in output
    assert path.read_bytes() == original
    assert path.stat().st_ino == original_stat.st_ino
    assert path.stat().st_mtime_ns == original_stat.st_mtime_ns


def test_write_creates_exact_backup_that_restores_and_is_idempotent(tmp_path, capsys):
    from lintlang.cli import main

    path = tmp_path / "AGENTS.md"
    original = b"# Instructions\r\n\r\nDon't be verbose.\r\n"
    path.write_bytes(original)
    backup = tmp_path / "AGENTS.md.lintlang.bak"

    assert main(["scan", str(path), "--fix", "--backup"]) == 0

    assert path.read_bytes() == b"# Instructions\r\n\r\nBe concise.\r\n"
    assert backup.read_bytes() == original
    assert main(["scan", str(path), "--fix", "--backup"]) == 0
    assert path.read_bytes() == b"# Instructions\r\n\r\nBe concise.\r\n"

    path.write_bytes(backup.read_bytes())
    assert path.read_bytes() == original
    assert "No supported safe rewrites found" in capsys.readouterr().out


def test_refuses_to_overwrite_an_existing_backup(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text(_instruction_document("Don't be verbose.\n"), encoding="utf-8")
    backup = tmp_path / "AGENTS.md.lintlang.bak"
    backup.write_text("keep this", encoding="utf-8")
    original = path.read_bytes()

    with pytest.raises(AutoFixError, match="Backup already exists"):
        prepare_fix(path, backup=True)

    assert path.read_bytes() == original
    assert backup.read_text(encoding="utf-8") == "keep this"


def test_rechecks_file_before_writing_prepared_diff(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text(_instruction_document("Don't be verbose.\n"), encoding="utf-8")
    prepared = prepare_fix(path)
    path.write_text(_instruction_document("Be concise.\n"), encoding="utf-8")

    with pytest.raises(AutoFixError, match="Input changed after the diff"):
        write_fix(prepared)

    assert path.read_text(encoding="utf-8") == _instruction_document("Be concise.\n")


@pytest.mark.parametrize(
    ("options", "files"),
    [
        (["--dry-run"], ["AGENTS.md"]),
        (["--backup"], ["AGENTS.md"]),
        (["--fix", "--dry-run", "--backup"], ["AGENTS.md"]),
        (["--fix"], ["AGENTS.md", "other.md"]),
    ],
)
def test_cli_rejects_ambiguous_fix_options(tmp_path, capsys, options, files):
    from lintlang.cli import main

    paths = [tmp_path / file for file in files]
    for path in paths:
        path.write_text("Don't be verbose.\n", encoding="utf-8")
    originals = [path.read_bytes() for path in paths]

    assert main(["scan", *(str(path) for path in paths), *options]) == 2
    assert [path.read_bytes() for path in paths] == originals
    assert "Error:" in capsys.readouterr().err


def test_cli_rejects_machine_output_and_stdin_fixes(tmp_path, capsys, monkeypatch):
    from io import StringIO

    from lintlang.cli import main

    path = tmp_path / "AGENTS.md"
    path.write_text("Don't be verbose.\n", encoding="utf-8")
    monkeypatch.setattr("sys.stdin", StringIO("Don't be verbose.\n"))

    assert main(["scan", str(path), "--fix", "--format", "json"]) == 2
    assert main(["scan", "-", "--stdin-filename", "AGENTS.md", "--fix"]) == 2
    assert path.read_text(encoding="utf-8") == "Don't be verbose.\n"
    assert "Error:" in capsys.readouterr().err


def test_cli_help_describes_the_supported_auto_fix_scope(capsys):
    from lintlang.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["scan", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--fix" in output
    assert "--dry-run" in output
    assert "--backup" in output
    assert "first body line" in output
    assert "# Instructions" in output


def test_auto_fix_preserves_file_mode(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text(_instruction_document("Don't be verbose.\n"), encoding="utf-8")
    os.chmod(path, 0o640)
    prepared = prepare_fix(path)

    write_fix(prepared)

    assert path.stat().st_mode & 0o777 == 0o640
