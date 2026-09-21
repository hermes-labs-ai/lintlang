"""Evidence, navigation, and ownership contracts for public documentation.

Behavioral promises follow their owning guide when the README is shortened.
Release metadata and executable first-run fixtures have separate gates.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOCS = (
    "README.md", "INTENT.md", "CONTRIBUTING.md", "llms-full.txt",
    "docs/research.md", "docs/integrations.md", "docs/github.md", "docs/baselines.md",
    "integrations/claude-code/README.md", "docs/gemini-cli-extension.md",
    "integrations/opencode/README.md", "mega-linter-plugin-lintlang/README.md",
)


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _prose(path: str) -> str:
    return re.sub(r"\s+", " ", _text(path))


def _readme_test_count_claim() -> int | None:
    match = re.search(r"(\d+)\s+tests?\b", _text("README.md")[:1500])
    return int(match.group(1)) if match else None


def _changelog_test_count_claim() -> int | None:
    text = _text("CHANGELOG.md")
    headers = list(re.finditer(r"^## \[", text, re.MULTILINE))
    if not headers:
        return None
    start = headers[0].start()
    end = headers[1].start() if len(headers) >= 2 else len(text)
    match = re.search(r"(\d+)\s+tests?\b", text[start:end])
    return int(match.group(1)) if match else None


def test_readme_opener_avoids_brittle_test_count_claim():
    assert _readme_test_count_claim() is None


def test_unreleased_changelog_avoids_brittle_test_count_claim():
    assert _changelog_test_count_claim() is None


def test_readme_keeps_regression_methodology_out_of_adoption_path():
    readme = _text("README.md").lower()
    assert "repository regression check" not in readme
    assert "external-project detector accuracy" not in readme
    assert "excerpt from `lintlang 0.6.0`" in _text("llms-full.txt").lower()
    assert "(llms-full.txt)" in readme


def test_public_docs_do_not_claim_a_clean_scan_proves_safety():
    readme = _prose("README.md").lower()
    intent = _prose("INTENT.md").lower()
    assert "does not run models" in readme
    assert "or establish that an agent is production-safe" in readme
    assert "a clean scan means only that the selected static checks found no covered defects" in readme
    assert "clean scan does not establish safety or correctness" in intent


def test_reference_labels_the_failing_demo_and_its_clean_comparison():
    reference = _text("llms-full.txt")
    section = reference.split("## Reading a repository sample", 1)[1].split("## First run", 1)[0]
    assert "This is a deliberately failing fixture" in section
    assert "`lintlang scan samples/clean_config.yaml --fail-on fail`" in section
    assert "from a source\ncheckout" in section
    assert "[checkout-free clean example](#first-run-without-a-checkout)" in section
    assert "A clean static scan is not evidence" in section


def test_readme_links_to_checkout_free_first_run():
    assert "[No instruction file yet? Try the checkout-free first run.]" in _text("README.md")


def test_owning_guides_match_baseline_and_scan_default_contracts():
    baseline = _prose("docs/baselines.md").lower()
    github = _prose("docs/github.md")
    reference = _prose("llms-full.txt")
    assert "baseline support is included in released lintlang 0.6.0" in baseline
    assert "no verdict-failure threshold by default" in reference
    assert "Action" in github and "its default is `fail`" in github
    assert "directory with no eligible files" in github
    assert "is an input/coverage error" in github and "exits 1" in github
    assert "`--allow-empty`" in github
    assert "`--write-baseline`" in github and "zero scanned files is always an error" in github
    assert "github.md#code-scanning" in baseline
    assert "README.md#machine-readable-output" not in _text("docs/baselines.md")


def _without_fences(text: str) -> str:
    return re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$", "", text)


def _anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    for title in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", _without_fences(text)):
        title = re.sub(r"<[^>]*>", "", title)
        title = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", title)
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        occurrence = occurrences.get(slug, 0)
        occurrences[slug] = occurrence + 1
        anchors.add(f"{slug}-{occurrence}" if occurrence else slug)
    anchors.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', text))
    return anchors


@pytest.mark.parametrize("document", PUBLIC_DOCS)
def test_relative_documentation_links_resolve(document):
    source = REPO_ROOT / document
    text = _without_fences(source.read_text(encoding="utf-8"))
    for destination in re.findall(r"\[[^\]\n]*\]\(([^\s)]+)\)", text):
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc:
            continue
        target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
        assert target.is_relative_to(REPO_ROOT), (document, destination)
        assert target.exists(), (document, destination)
        if parsed.fragment and target.is_file():
            assert unquote(parsed.fragment) in _anchors(target.read_text(encoding="utf-8")), (
                document, destination,
            )


def test_readme_routes_to_the_owning_guides():
    readme = _text("README.md")
    for target in (
        "docs/research.md", "docs/integrations.md", "docs/github.md", "docs/baselines.md",
        "llms-full.txt", "INTENT.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "LICENSE",
        "integrations/claude-code/README.md", "docs/gemini-cli-extension.md",
        "mega-linter-plugin-lintlang/README.md",
    ):
        assert f"]({target})" in readme, target
    assert "## Evidence\n" in readme
    assert "## Code scanning\n" in _text("docs/github.md")


def test_research_identifiers_and_claim_boundaries_remain_separate():
    research = _prose("docs/research.md")
    citation = _text("CITATION.cff")
    for identifier in ("10.5281/zenodo.19042468", "10.5281/zenodo.21817243"):
        assert identifier in research and identifier in citation
    assert "https://hermes-labs.ai/research/taxonomy-of-epistemic-failure-modes" in research
    assert "https://hermes-labs.ai/research/tool-differentia" in research
    assert "not a one-to-one implementation of the taxonomy" in research
    assert "does not validate every detector or prove LintLang's accuracy" in research
    assert "not proofs of semantic equivalence or predictions of tool selection" in research
    assert "## Public ecosystem references" in _text("docs/integrations.md")
    assert "not a claim of broad production adoption" in research or "broad production adoption" in _text("docs/integrations.md")


def test_historical_host_evidence_is_not_silently_upgraded():
    gemini = _text("docs/gemini-cli-extension.md")
    opencode = _text("integrations/opencode/README.md")
    mega = _prose("mega-linter-plugin-lintlang/README.md")
    assert "f89c3b0b8986fad162859dca052a8d5fe227eede" in gemini
    assert "0.32.1" in gemini and "0.5.3" in gemini
    assert "1.18.27" in opencode and "tool.execute.after" in opencode
    assert "type declarations" in opencode
    assert "8.8.0" in mega and "0.5.3" in mega
    assert "in-process" in mega and "container" in mega


def test_reference_api_example_executes_with_real_findings(tmp_path, monkeypatch, capsys):
    section = _text("llms-full.txt").split("## Programmatic API", 1)[1]
    example = re.search(r"```python\n(.*?)\n```", section, re.DOTALL)
    assert example is not None
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        'tools:\n  - name: process_ticket\n    description: ""\n', encoding="utf-8",
    )
    (tmp_path / "prompts").mkdir()
    exec(compile(example.group(1), "llms-full.txt API example", "exec"), {})
    output = capsys.readouterr().out
    assert "FAIL" in output and "H1.1" in output
    (tmp_path / "config.yaml").unlink()
    exec(compile(example.group(1), "llms-full.txt API example", "exec"), {})
    assert "ERROR" in capsys.readouterr().out
