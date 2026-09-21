"""Markdown instruction documents: scoped heuristics, line numbers, front matter, references."""

from __future__ import annotations

from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

LONG_GUIDE = "# Guide\n\n" + "\n".join(f"- Step {i}: Run the formatter. Then commit the result." for i in range(40)) + "\n"


def scan(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return scan_file(path)


def test_an_ordinary_instruction_document_passes(tmp_path):
    result = scan(tmp_path, "AGENTS.md", LONG_GUIDE)
    assert compute_verdict(result) == "PASS"
    assert result.structural_findings == []
    assert result.inspected["instructions"] == 1


def test_the_same_text_as_a_chat_prompt_keeps_the_prompt_heuristics(tmp_path):
    result = scan(tmp_path, "system.txt", LONG_GUIDE)
    assert any("priority ordering" in f.description for f in result.structural_findings)


def test_findings_carry_the_file_line_and_quote_the_whole_line(tmp_path):
    text = "---\nname: x\ndescription: Use when the build fails and must be retried.\n---\n\n# T\n\nIf the build fails, keep trying until it works.\n"
    finding = next(f for f in scan(tmp_path, "AGENTS.md", text).structural_findings if f.pattern_id == "H2")
    assert finding.source_region.start_line == 8
    assert finding.evidence == "If the build fails, keep trying until it works."


def test_front_matter_is_not_linted_as_prose(tmp_path):
    text = "---\nname: retry-helper\ndescription: Use when a task says keep trying until it works.\n---\n\nBody.\n"
    assert not [f for f in scan(tmp_path, "skills/retry-helper/SKILL.md", text).structural_findings if f.pattern_id == "H2"]


class TestSkillFrontMatter:
    def codes(self, tmp_path, front, directory="pdf-tools"):
        result = scan(tmp_path, f"{directory}/SKILL.md", f"---\n{front}\n---\n\nBody text.\n")
        return {f.code: f for f in result.structural_findings}

    def test_good_skill_is_clean(self, tmp_path):
        assert self.codes(tmp_path, "name: pdf-tools\ndescription: Fill and merge PDF forms. Use when the user mentions a PDF.") == {}

    def test_missing_description(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-tools")
        assert found["H1.1"].severity.value == "high"

    def test_description_without_a_trigger(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-tools\ndescription: Browser and desktop automation discipline.")
        assert found["H1.8"].source_region.start_line == 3

    def test_description_written_as_the_situation_is_a_trigger(self, tmp_path):
        assert "H1.8" not in self.codes(tmp_path, "name: pdf-tools\ndescription: About to cite a number whose source is a tracking doc.")

    def test_description_over_the_limit(self, tmp_path):
        assert "H1.7" in self.codes(tmp_path, "name: pdf-tools\ndescription: Use when " + "x" * 1100)

    def test_name_must_match_directory(self, tmp_path):
        found = self.codes(tmp_path, "name: pdf-helper\ndescription: Use when the user mentions a PDF file.")
        assert "does not match its directory" in found["H1.9"].description

    def test_invalid_name(self, tmp_path):
        found = self.codes(tmp_path, "name: PDF_Tools\ndescription: Use when the user mentions a PDF file.", "PDF_Tools")
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
