from __future__ import annotations

from pathlib import Path

import yaml

from lintlang.cli import main

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = (
    ROOT
    / "mega-linter-plugin-lintlang"
    / "lintlang.megalinter-descriptor.yml"
)


def _descriptor() -> dict:
    return yaml.safe_load(DESCRIPTOR.read_text(encoding="utf-8"))


def test_megalinter_descriptor_contract() -> None:
    descriptor = _descriptor()

    assert descriptor["descriptor_id"] == "AI"
    assert descriptor["descriptor_type"] == "other"
    assert descriptor["descriptor_flavors"] == ["all_flavors"]
    assert set(descriptor["file_extensions"]) == {
        ".json",
        ".md",
        ".py",
        ".txt",
        ".yaml",
        ".yml",
    }

    assert len(descriptor["linters"]) == 1
    linter = descriptor["linters"][0]
    assert linter["linter_name"] == "lintlang"
    assert linter["name"] == "AI_LINTLANG"
    assert linter["cli_lint_mode"] == "list_of_files"
    assert linter["supported_cli_lint_modes"] == ["list_of_files"]
    assert linter["cli_lint_extra_args"] == ["scan", "--fail-on", "fail"]
    assert linter["install"]["dockerfile"] == [
        "RUN pip install --no-cache-dir lintlang==0.5.3"
    ]


def test_megalinter_invocation_passes_clean_and_fails_bad_fixture() -> None:
    linter = _descriptor()["linters"][0]
    prefix = linter["cli_lint_extra_args"]

    assert main([*prefix, str(ROOT / "samples" / "clean_config.yaml")]) == 0
    assert main([*prefix, str(ROOT / "samples" / "bad_tool_descriptions.yaml")]) == 1


def test_megalinter_list_of_files_batch_fails_only_on_known_finding(
    tmp_path: Path,
) -> None:
    """Mirror the real ``oxsecurity/megalinter-python:v9.4.0`` list_of_files call.

    MegaLinter passes every kept file in one command:
    ``lintlang scan --fail-on fail <file> <file> ...``. The batch must exit 1
    when exactly one file carries a known FAIL verdict, and exit 0 once that
    file is removed, without unrelated ``.md``/``.py``/``.txt``/``.json``
    files producing findings.
    """
    linter = _descriptor()["linters"][0]
    prefix = linter["cli_lint_extra_args"]

    bad = tmp_path / "bad_tool_descriptions.yaml"
    bad.write_text(
        (ROOT / "samples" / "bad_tool_descriptions.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    clean = tmp_path / "clean_config.yaml"
    clean.write_text(
        (ROOT / "samples" / "clean_config.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    unrelated = [
        tmp_path / "README.md",
        tmp_path / "notes.txt",
        tmp_path / "package.json",
        tmp_path / "app.py",
    ]
    unrelated[0].write_text("# Fixture\n\nOrdinary readme text.\n", encoding="utf-8")
    unrelated[1].write_text("plain notes, nothing prompt-like\n", encoding="utf-8")
    unrelated[2].write_text('{"name": "demo", "version": 1}\n', encoding="utf-8")
    unrelated[3].write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    batch = [str(clean), *(str(path) for path in unrelated)]

    assert main([*prefix, str(bad), *batch]) == 1
    assert main([*prefix, *batch]) == 0
