"""Contract tests for the native pre-commit hook and its owning guide."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from lintlang.instructions import is_recognized_instruction_path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = yaml.safe_load((REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
CHECKOUT_V7_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
LINTLANG_ACTION_VERSION = "v0.7.0"
LINTLANG_V070_SHA = "175a9a19414aff9a1752d3b9850d6cf58d59fb32"


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
    ".github/instructions/foo.instructions.md",
    ".github/instructions/nested/foo.instructions.md",
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
    # HARD NEGATIVE: the layout's documented spelling is `*.instructions.md`;
    # a plain Markdown file kept in that directory is not an instruction file.
    ".github/instructions/foo.md",
    ".github/instructions/README.md",
    ".github/instructions/.instructions.md",
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


class TestHookInvokedAsPreCommitWouldInvokeIt:
    """End-to-end over the hook definition itself: entry + args + filenames.

    ``pre-commit try-repo`` is the real thing, and it is not used here: it
    builds an isolated environment and installs this package into it, which
    needs the network, and these tests must run offline. This is the closest
    faithful invocation without that step — the hook's own ``entry``, its own
    ``files:`` selection applied to a temporary repository exactly as
    pre-commit applies it (``re.search`` over repository-relative POSIX
    paths), and the selected filenames appended after ``args`` — run as a
    subprocess against the installed package. What it does not cover is
    environment construction: that the declared ``language: python``
    environment installs and puts the entry point on ``PATH``.
    """

    HOOK = HOOKS[0]

    @staticmethod
    def _repository(root: Path) -> None:
        (root / "AGENTS.md").write_text(
            "You are an agent. Keep trying until it works. Retry until success.\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("# Readme\n", encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs" / "notes.md").write_text("Prose about the project.\n", encoding="utf-8")
        instructions = root / ".github" / "instructions"
        instructions.mkdir(parents=True)
        (instructions / "review.instructions.md").write_text(
            "Review the diff. Summarize each change in one sentence.\n", encoding="utf-8"
        )
        (instructions / "notes.md").write_text("Scratch notes.\n", encoding="utf-8")

    @classmethod
    def _selected_filenames(cls, root: Path) -> list[str]:
        """The filenames pre-commit would pass: every file in the repository
        whose path its ``files:`` regex selects, repository-relative."""
        pattern = re.compile(cls.HOOK["files"])
        paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
        return [path for path in paths if pattern.search(path) is not None]

    @classmethod
    def _run(cls, root: Path, args: list[str], filenames: list[str]) -> subprocess.CompletedProcess[str]:
        entry = shlex.split(cls.HOOK["entry"])
        assert entry[0] == "lintlang"
        # The console script is the entry point pre-commit installs; the
        # module form invokes the same CLI without depending on this test
        # environment's PATH.
        command = [sys.executable, "-m", "lintlang", *entry[1:], *args, *filenames]
        return subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "NO_COLOR": "1", "PYTHONPATH": str(REPO_ROOT / "src")},
        )

    def test_default_hook_scans_the_selected_files_and_does_not_block(self, tmp_path):
        """A FAIL verdict alone does not block a commit.

        Without `--fail-on` the scan is advisory: it reports FAIL and exits 0,
        so pre-commit lets the commit through. This is the behavior the guide
        has to state, because a hook that reports FAIL and passes looks broken
        to someone who did not read it.
        """
        self._repository(tmp_path)
        filenames = self._selected_filenames(tmp_path)

        assert filenames == [".github/instructions/review.instructions.md", "AGENTS.md"]

        completed = self._run(tmp_path, [], filenames)

        assert completed.returncode == 0, completed.stderr
        assert "FAIL" in completed.stdout
        assert "AGENTS.md" in completed.stdout
        # Files the regex did not select are never passed, so never scanned.
        assert "README.md" not in completed.stdout
        assert "notes.md" not in completed.stdout

    def test_fail_on_blocks_the_commit(self, tmp_path):
        self._repository(tmp_path)
        filenames = self._selected_filenames(tmp_path)

        completed = self._run(tmp_path, ["--fail-on", "fail"], filenames)

        assert completed.returncode == 1
        assert "FAIL" in completed.stdout

    def test_configured_args_do_not_replace_the_appended_filenames(self, tmp_path):
        """pre-commit appends the filenames after `args`.

        A path in `args:` is therefore scanned *in addition to* each changed
        file, not instead of it. The guide documents this; here it is the
        observed behavior of the same argument vector.
        """
        self._repository(tmp_path)
        (tmp_path / "CLAUDE.md").write_text("Summarize the diff in one sentence.\n", encoding="utf-8")
        filenames = self._selected_filenames(tmp_path)
        assert "CLAUDE.md" in filenames

        completed = self._run(tmp_path, ["docs/notes.md"], filenames)

        assert completed.returncode == 0, completed.stderr
        # The configured path AND every selected filename were scanned.
        assert "docs/notes.md" in completed.stdout
        assert "CLAUDE.md" in completed.stdout
        assert "AGENTS.md" in completed.stdout

    def test_a_commit_touching_nothing_recognized_selects_no_filenames(self, tmp_path):
        """The hook is not run at all in that case; the regex selects nothing,
        so the empty-scan input error is never reached from this hook."""
        self._repository(tmp_path)
        pattern = re.compile(self.HOOK["files"])

        assert [path for path in ("README.md", "docs/notes.md") if pattern.search(path)] == []


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
    assert "rev: v0.7.1" in integration
    assert "id: lintlang" in integration
    assert "args: [AGENTS.md, --fail-on, fail]" in integration
    assert "pre-commit install" in integration
    assert "pre-commit run lintlang" in integration
    assert f"hermes-labs-ai/lintlang@{LINTLANG_V070_SHA} # {LINTLANG_ACTION_VERSION}" in baseline
    assert "(docs/integrations.md)" in readme
    assert "(docs/github.md)" in readme
    assert "(docs/baselines.md)" in readme

    # Preserve the immutable-pin guarantee added on main in POL-065.
    assert f"actions/checkout@{CHECKOUT_V7_SHA} # v7.0.1" in example
    for text in (readme, reference, integration, baseline, github, example):
        assert "actions/checkout@v7" not in text
        assert "hermes-labs-ai/lintlang@v0.4.0" not in text
        assert f"uses: hermes-labs-ai/lintlang@{LINTLANG_ACTION_VERSION}" not in text
    assert f"hermes-labs-ai/lintlang@{LINTLANG_V070_SHA} # v0.7.0" in example
    assert f"hermes-labs-ai/lintlang@{LINTLANG_ACTION_VERSION}" not in example
