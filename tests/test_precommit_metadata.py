"""Contract tests for the native pre-commit hook and its owning guide."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from lintlang.instructions import is_recognized_instruction_path

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
    # The hook must consume pre-commit's own changed-file selection rather than
    # a hard-coded path, and must not force itself to run on unrelated commits.
    assert "args" not in hook
    assert "pass_filenames" not in hook
    assert "always_run" not in hook
    assert hook["verbose"] is True
    assert "files" in hook


# Paths that must be selected by the hook's `files:` regex, and must therefore
# agree with lintlang.instructions.is_recognized_instruction_path.
RECOGNIZED_PATHS = [
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "SKILL.md",
    ".agents/skills/lintlang/SKILL.md",
    "docs/sub/CLAUDE.md",
    "agent.yaml",
    "agent.yml",
    "agent.json",
    ".github/copilot-instructions.md",
    ".github/instructions/foo.md",
]

# Paths that must NOT be selected by the hook's `files:` regex.
UNRECOGNIZED_PATHS = [
    "README.md",
    "CHANGELOG.md",
    "docs/notes.md",
    "src/lintlang/cli.py",
    "agents.md",
    "AGENTS.txt",
    ".github/instructions/foo.txt",
    "pyproject.toml",
]


@pytest.mark.parametrize("path", RECOGNIZED_PATHS + UNRECOGNIZED_PATHS)
def test_precommit_hook_files_regex_agrees_with_instruction_primitive(path):
    hook = HOOKS[0]
    pattern = re.compile(hook["files"])
    regex_matches = pattern.search(path) is not None
    primitive_matches = is_recognized_instruction_path(path)
    assert regex_matches == primitive_matches, (
        f"hook files regex and is_recognized_instruction_path disagree on {path!r}: "
        f"regex={regex_matches} primitive={primitive_matches}"
    )
    expected = path in RECOGNIZED_PATHS
    assert regex_matches is expected
    assert primitive_matches is expected


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
    assert "rev: v0.6.0" in integration
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
