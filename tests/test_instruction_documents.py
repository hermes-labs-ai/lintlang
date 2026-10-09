"""Markdown instruction documents: scoped heuristics, line numbers, front matter, references."""

from __future__ import annotations

import json

import pytest

from lintlang.cli import main
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

LONG_GUIDE = (
    "# Guide\n\n" + "\n".join(f"- Step {i}: Run the formatter. Then commit the result." for i in range(40)) + "\n"
)


def scan(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return scan_file(path, gate=False)


def test_an_ordinary_instruction_document_passes(tmp_path):
    result = scan(tmp_path, "AGENTS.md", LONG_GUIDE)
    assert compute_verdict(result) == "PASS"
    assert result.structural_findings == []
    assert result.inspected["instructions"] == 1


def test_the_same_text_as_a_chat_prompt_keeps_the_prompt_heuristics(tmp_path):
    result = scan(tmp_path, "system.txt", LONG_GUIDE)
    assert not any(f.pattern_id == "H5" for f in result.structural_findings)
    assert result.inspected["system_prompt"] == 1


def test_markdown_with_chat_prompt_evidence_keeps_the_prompt_heuristics(tmp_path):
    prompt = (
        "# System prompt\n\nYou are the release reviewer.\n\n"
        + "\n".join(f"- Check release requirement {i} and record the outcome." for i in range(12))
        + "\n"
    )

    result = scan(tmp_path, "system.md", prompt)

    assert not any(f.pattern_id == "H5" for f in result.structural_findings)
    assert result.inspected["system_prompt"] == 1


def test_markdown_filename_alone_does_not_make_ordinary_prose_a_chat_prompt(tmp_path):
    result = scan(tmp_path, "system.md", LONG_GUIDE)

    assert compute_verdict(result) == "PASS"
    assert result.inspected["instructions"] == 1


def test_documented_instruction_surface_stays_a_document_with_role_language(tmp_path):
    text = (
        "# Instructions\n\nYou are the repository maintainer.\n\n"
        + "\n".join(f"- Check repository requirement {i} and record the outcome." for i in range(12))
        + "\n"
    )

    result = scan(tmp_path, "AGENTS.md", text)

    assert not any("priority ordering" in f.description for f in result.structural_findings)
    assert result.inspected["instructions"] == 1


def test_findings_carry_the_file_line_and_quote_the_whole_line(tmp_path):
    text = "---\nname: x\ndescription: Use when the build fails and must be retried.\n---\n\n# T\n\nIf the build fails, keep trying until it works.\n"
    finding = next(f for f in scan(tmp_path, "AGENTS.md", text).structural_findings if f.pattern_id == "H2")
    assert finding.source_region.start_line == 8
    assert finding.evidence == "If the build fails, keep trying until it works."


def test_front_matter_is_not_linted_as_prose(tmp_path):
    text = "---\nname: retry-helper\ndescription: Use when a task says keep trying until it works.\n---\n\nBody.\n"
    assert not [
        f for f in scan(tmp_path, "skills/retry-helper/SKILL.md", text).structural_findings if f.pattern_id == "H2"
    ]


class TestSkillFrontMatter:
    def codes(self, tmp_path, front, directory="pdf-tools"):
        result = scan(tmp_path, f"{directory}/SKILL.md", f"---\n{front}\n---\n\nBody text.\n")
        return {f.code: f for f in result.structural_findings}

    def test_good_skill_is_clean(self, tmp_path):
        assert (
            self.codes(
                tmp_path, "name: pdf-tools\ndescription: Fill and merge PDF forms. Use when the user mentions a PDF."
            )
            == {}
        )

    def test_missing_description(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-tools")
        assert found == {}

    def test_description_without_a_trigger(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-tools\ndescription: Browser and desktop automation discipline.")
        assert found["H1.8"].source_region.start_line == 3

    def test_description_written_as_the_situation_is_a_trigger(self, tmp_path):
        assert "H1.8" not in self.codes(
            tmp_path, "name: pdf-tools\ndescription: About to cite a number whose source is a tracking doc."
        )

    def test_description_over_the_limit(self, tmp_path):
        assert "H1.7" in self.codes(tmp_path, "name: pdf-tools\ndescription: Use when " + "x" * 2500)

    def test_name_must_match_directory(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-helper\ndescription: Use when the user mentions a PDF file.")
        assert "does not match its directory" in found["H1.9"].description

    def test_invalid_name(self, tmp_path):
        found = self.codes(
            tmp_path, "name: PDF_Tools\ndescription: Use when the user mentions a PDF file.", "PDF_Tools"
        )
        assert "not a valid" in found["H1.9"].description


class TestDanglingReferences:
    def repo(self, tmp_path, body):
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("")
        return [f for f in scan(tmp_path, "AGENTS.md", body).structural_findings if f.code == "H4.5"]

    def test_missing_file_under_an_existing_directory(self, tmp_path):
        found = self.repo(tmp_path, "Entry point is `src/app.py`.\nConfig loading lives in `src/config/loader.py`.\n")
        assert [f.location for f in found] == ["reference:src/config/loader.py"]
        assert found[0].source_region.start_line == 2

    def test_line_suffix_and_links(self, tmp_path):
        found = self.repo(tmp_path, "See `src/app.py:42` and [utils](src/utils.py).\n")
        assert [f.location for f in found] == ["reference:src/utils.py"]

    def test_quiet_on_examples_creations_fences_and_foreign_paths(self, tmp_path):
        body = (
            "For example `src/feature.py`.\nCreate `src/new_module.py` for it.\n"
            "A `src/helper.py` script would be useful.\nSee `docs/style.md`.\nUse `src/*.py` and `src/<name>.py`.\n"
            "Copy `src/your_tool.py`.\n```\ncat src/missing.py\n```\n"
        )
        assert self.repo(tmp_path, body) == []


@pytest.mark.parametrize("path", [
    "skills/my-skill/assets/report-template.md",
    "agents/reviewer/assets/template.md",
    "commands/review/assets/template.md",
    "docs/getting-started.md",
    "docs/commands/scan.md",
    ".claude/agents/reviewer.mdc",
    ".claude/commands/review.mdc",
    ".claude/commands/release/deploy.mdc",
])
@pytest.mark.parametrize("front", ["name: '{name}'", "description: Install the tool and run your first scan."])
def test_ordinary_markdown_metadata_is_not_skill_selection(tmp_path, path, front):
    result = scan(tmp_path, path, f"---\n{front}\n---\n\nBody.\n")
    assert not any(f.pattern_id == "H1" for f in result.structural_findings)
    assert result.inspected.get("skills", 0) == 0


@pytest.mark.parametrize("path", [
    "my-skill/SKILL.md", ".claude/agents/reviewer.md", ".claude/commands/review.md",
    ".cursor/rules/style.mdc", ".claude/commands/release/deploy.md",
])
@pytest.mark.parametrize("front,code", [
    ("name: reviewer", None),
    ("description: Writes a status summary from a template.", "H1.8"),
])
def test_selection_definition_metadata_keeps_findings(tmp_path, path, front, code):
    result = scan(tmp_path, path, f"---\n{front}\n---\n\nBody.\n")
    codes = {f.code for f in result.structural_findings}
    assert code in codes if code else "H1.1" not in codes


@pytest.mark.parametrize("front,code,exit_code", [
    ("name: reviewer", None, 0),
    ("description: Writes a status summary from a template.", "H1.8", 0),
])
def test_directory_cli_scans_cursor_rules_without_classifying_assets(tmp_path, capsys, front, code, exit_code):
    rule = ".cursor/rules/reviewer.mdc"
    controls = [".cursor/rules/assets/template.mdc", "docs/page.mdc", "docs/page.md"]
    for path in [rule, *controls]:
        scan(tmp_path, path, f"---\n{front}\n---\n\nBody.\n")

    assert main(["scan", "--no-gate", str(tmp_path), "--patterns", "H1", "--format", "json", "--fail-on", "fail"]) == exit_code
    results = {item["file"]: item for item in json.loads(capsys.readouterr().out)}
    codes = {finding["code"] for finding in results[str(tmp_path / rule)]["structural_findings"]}
    assert code in codes if code else not codes
    for path in controls:
        assert not any(finding["pattern_id"] == "H1" for finding in results[str(tmp_path / path)]["structural_findings"])
