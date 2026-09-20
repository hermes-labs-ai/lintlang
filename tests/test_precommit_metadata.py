"""Contract tests for the native pre-commit hook and its owning guide."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = yaml.safe_load((REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
LINTLANG_ACTION_VERSION = "v0.6.0"
LINTLANG_V060_SHA = "58e66871531eb585869336189d07b4334e963a5f"


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
    integration = (REPO_ROOT / "docs/integrations.md").read_text(encoding="utf-8")
    baseline = (REPO_ROOT / "docs/baselines.md").read_text(encoding="utf-8")
    github = (REPO_ROOT / "docs/github.md").read_text(encoding="utf-8")
    example = (REPO_ROOT / "examples/github-code-scanning.yml").read_text(encoding="utf-8")

    for text in (readme, reference):
        assert "uvx lintlang scan AGENTS.md" in text
    assert "pipx install lintlang" in reference
    assert "pipx ensurepath" in reference
    assert "repo: https://github.com/hermes-labs-ai/lintlang" in integration
    assert "rev: v0.7.0" in integration
    assert "id: lintlang" in integration
    assert "args: [AGENTS.md, --fail-on, fail]" in integration
    assert "pre-commit install" in integration
    assert "pre-commit run lintlang" in integration
    assert f"hermes-labs-ai/lintlang@{LINTLANG_V060_SHA} # {LINTLANG_ACTION_VERSION}" in baseline
    assert "(docs/integrations.md)" in readme
    assert "(docs/github.md)" in readme
    assert "(docs/baselines.md)" in readme

    # Preserve the immutable-pin guarantee added on main in POL-065.
    assert f"actions/checkout@{CHECKOUT_V7_SHA} # v7.0.1" in example
    for text in (readme, reference, integration, baseline, github, example):
        assert "actions/checkout@v7" not in text
        assert "hermes-labs-ai/lintlang@v0.4.0" not in text
        assert f"uses: hermes-labs-ai/lintlang@{LINTLANG_ACTION_VERSION}" not in text
    assert f"hermes-labs-ai/lintlang@{LINTLANG_V060_SHA} # v0.6.0" in example
    assert f"hermes-labs-ai/lintlang@{LINTLANG_ACTION_VERSION}" not in example
