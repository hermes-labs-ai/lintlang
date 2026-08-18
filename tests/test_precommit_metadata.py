"""Contract tests for the native pre-commit hook."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = yaml.safe_load((REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
CHECKOUT_V7_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"


def test_precommit_hook_is_explicit_and_advisory_by_default():
    assert len(HOOKS) == 1
    hook = HOOKS[0]

    assert hook["id"] == "lintlang"
    assert hook["entry"] == "lintlang scan"
    assert hook["language"] == "python"
    assert hook["args"] == ["AGENTS.md"]
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True
    assert hook["verbose"] is True


def test_public_docs_show_exercised_install_and_hook_paths():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    reference = (REPO_ROOT / "llms-full.txt").read_text(encoding="utf-8")

    for text in (readme, reference):
        assert "uvx lintlang scan AGENTS.md" in text
        assert "pipx install lintlang" in text
        assert "pipx ensurepath" in text
        assert "repo: https://github.com/hermes-labs-ai/lintlang" in text
        assert "rev: v0.4.1" in text
        assert f"actions/checkout@{CHECKOUT_V7_SHA}" in text
        assert "actions/checkout@v7" not in text
        assert "id: lintlang" in text
        assert "args: [AGENTS.md, --fail-on, fail]" in text
