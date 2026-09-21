"""Tests for the shared recognized-instruction primitive.

One conservative definition of "this path is a known agent instruction
surface" is owned by ``lintlang.instructions`` and reused by repository
discovery and ``lintlang init``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lintlang.instructions import (
    RECOGNIZED_INSTRUCTION_BASENAMES,
    RECOGNIZED_INSTRUCTION_DIRECTORIES,
    RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES,
    RECOGNIZED_INSTRUCTION_RELATIVE_PATHS,
    discover_instruction_files,
    is_recognized_instruction_path,
)


class TestRecognizedConstants:
    def test_documented_surfaces_are_public(self):
        assert frozenset(
            {
                "AGENTS.md",
                "CLAUDE.md",
                "GEMINI.md",
                "SKILL.md",
                "agent.yaml",
                "agent.yml",
                "agent.json",
            }
        ) == RECOGNIZED_INSTRUCTION_BASENAMES
        assert frozenset(
            {".github/copilot-instructions.md"}
        ) == RECOGNIZED_INSTRUCTION_RELATIVE_PATHS
        assert frozenset({".github/instructions"}) == RECOGNIZED_INSTRUCTION_DIRECTORIES
        assert frozenset({".instructions.md"}) == RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES


class TestIsRecognizedInstructionPath:
    @pytest.mark.parametrize(
        "path",
        (
            "AGENTS.md",
            "CLAUDE.md",
            "GEMINI.md",
            "SKILL.md",
            "agent.yaml",
            "agent.yml",
            "agent.json",
            "packages/worker/AGENTS.md",
            ".agents/skills/lintlang/SKILL.md",
            ".github/copilot-instructions.md",
            ".github/instructions/review.instructions.md",
            ".github/instructions/nested/review.instructions.md",
            "packages/worker/.github/instructions/style.instructions.md",
            "/abs/repo/AGENTS.md",
        ),
    )
    def test_recognized(self, path):
        assert is_recognized_instruction_path(path) is True

    @pytest.mark.parametrize(
        "path",
        (
            "README.md",
            "docs/adoption-notes.md",
            "notes.md",
            "config/agent contract.yaml",
            "agents.yaml",
            "AGENTS.md.bak",
            "AGENTS.txt",
            "copilot-instructions.md",
            "instructions/review.instructions.md",
            ".github/workflows/lintlang.yml",
            ".github/instructions/notes.txt",
            "integrations/opencode/lintlang.js",
            "src/lintlang/cli.py",
        ),
    )
    def test_not_recognized(self, path):
        assert is_recognized_instruction_path(path) is False

    @pytest.mark.parametrize(
        "path",
        (
            ".github/instructions/notes.md",
            ".github/instructions/README.md",
            ".github/instructions/nested/notes.md",
            ".github/instructions/.instructions.md",
            ".github/instructions/review.instructions.markdown",
            "packages/worker/.github/instructions/style.md",
        ),
    )
    def test_instructions_directory_takes_only_its_documented_spelling(self, path):
        """HARD NEGATIVE: the layout documents ``*.instructions.md``.

        Accepting every Markdown file under ``.github/instructions`` pulled in
        a README or a scratch note kept beside the real instruction files and
        scanned it as an agent instruction surface.
        """
        assert is_recognized_instruction_path(path) is False

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: these editor and host instruction layouts are not discovery targets yet",
    )
    @pytest.mark.parametrize("path", (".cursor/rules/style.md", ".claude/agents/reviewer.md", ".windsurfrules"))
    def test_documented_omissions_should_be_recognized(self, path):
        """DESIRED BEHAVIOUR, not today's behaviour.

        Each of these is an agent instruction surface a real project keeps, so
        discovery should find it. It does not: every one of them needs its own
        file-shape decision first, and adding a surface widens discovery, the
        pre-commit file filter, and the initializer at once. The module
        docstring records why; passing such a file as an explicit scan argument
        works today and remains canonical. The day a layout is added, this test
        passes, strict xfail turns that into a suite failure, and the marker
        comes off with the decision.
        """
        assert is_recognized_instruction_path(path) is True

    @pytest.mark.parametrize(
        "path",
        ("agents.md", "Agents.md", "claude.md", "Skill.md", "AGENT.YAML", "Agent.Json"),
    )
    def test_basenames_are_case_sensitive(self, path):
        """The documented spelling is the contract; case variants are not
        silently accepted, so discovery cannot vary by filesystem case
        folding."""
        assert is_recognized_instruction_path(path) is False

    def test_accepts_path_objects(self):
        assert is_recognized_instruction_path(Path("AGENTS.md")) is True

    @pytest.mark.parametrize(
        "path",
        ("AGENTS.md/", "skills/SKILL.md/", ".github//instructions/x.md", ".github//copilot-instructions.md"),
    )
    def test_non_normal_spellings_are_rejected_not_normalized(self, path):
        """``pathlib`` would silently fold a trailing or doubled separator away,
        but the pre-commit ``files:`` regex is a literal string match and would
        not. The primitive declines the malformed spelling so the two surfaces
        cannot answer the same question differently."""
        assert is_recognized_instruction_path(path) is False


class TestDiscoverInstructionFiles:
    def test_returns_only_recognized_paths_sorted(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "adoption-notes.md").write_text("notes\n", encoding="utf-8")
        skill = tmp_path / "skills" / "audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
        github = tmp_path / ".github"
        (github / "instructions").mkdir(parents=True)
        (github / "copilot-instructions.md").write_text("# Copilot\n", encoding="utf-8")
        (github / "instructions" / "review.instructions.md").write_text("# R\n", encoding="utf-8")

        found = discover_instruction_files(tmp_path)

        assert found == [
            tmp_path / ".github" / "copilot-instructions.md",
            tmp_path / ".github" / "instructions" / "review.instructions.md",
            tmp_path / "AGENTS.md",
            tmp_path / "skills" / "audit" / "SKILL.md",
        ]
        assert found == sorted(found, key=str)

    def test_prunes_non_prompt_directories(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        for pruned in ("node_modules", ".git", "__pycache__", ".venv", "dist"):
            nested = tmp_path / pruned / "vendor"
            nested.mkdir(parents=True)
            (nested / "AGENTS.md").write_text("# vendored\n", encoding="utf-8")
        egg = tmp_path / "lintlang.egg-info"
        egg.mkdir()
        (egg / "AGENTS.md").write_text("# packaged\n", encoding="utf-8")

        assert discover_instruction_files(tmp_path) == [tmp_path / "AGENTS.md"]

    def test_skips_symlinked_files_and_directories(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        (real / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (tmp_path / "linked").symlink_to(real, target_is_directory=True)
        (tmp_path / "CLAUDE.md").symlink_to(real / "AGENTS.md")

        assert discover_instruction_files(tmp_path) == [real / "AGENTS.md"]

    def test_rejects_symlinked_discovery_root(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "AGENTS.md").write_text("# Outside\n", encoding="utf-8")
        root = tmp_path / "repository"
        root.symlink_to(outside, target_is_directory=True)

        assert discover_instruction_files(root) == []

    def test_skipped_symlinked_instruction_files_are_reported_to_the_caller(self, tmp_path):
        """A skipped symlink is a coverage gap, so it is available to say out
        loud rather than being dropped from the returned list in silence."""
        real = tmp_path / "real"
        real.mkdir()
        (real / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (tmp_path / "CLAUDE.md").symlink_to(real / "AGENTS.md")
        (tmp_path / "GEMINI.md").symlink_to(real / "AGENTS.md")
        (tmp_path / "README.md").symlink_to(real / "AGENTS.md")

        skipped: list[Path] = []
        found = discover_instruction_files(tmp_path, skipped_symlinks=skipped)

        assert found == [real / "AGENTS.md"]
        # Only recognized instruction surfaces; an unrecognized symlink is not
        # a gap, because it was never a discovery target.
        assert skipped == [tmp_path / "CLAUDE.md", tmp_path / "GEMINI.md"]

    def test_no_symlinks_reports_nothing(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")

        skipped: list[Path] = []

        assert discover_instruction_files(tmp_path, skipped_symlinks=skipped) == [tmp_path / "AGENTS.md"]
        assert skipped == []

    def test_missing_root_returns_empty(self, tmp_path):
        assert discover_instruction_files(tmp_path / "absent") == []
