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
