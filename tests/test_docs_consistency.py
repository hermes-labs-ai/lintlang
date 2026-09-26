"""Evidence, navigation, and ownership contracts for public documentation.

Behavioral promises follow their owning guide.
Release metadata and executable first-run fixtures have separate gates.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DOCS = (
    "INTENT.md", "CONTRIBUTING.md", "llms-full.txt",
    "docs/research.md", "docs/integrations.md", "docs/github.md", "docs/baselines.md",
    "docs/gemini-cli-extension.md",
)


def _text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _prose(path: str) -> str:
    return re.sub(r"\s+", " ", _text(path))


def _changelog_test_count_claim() -> int | None:
    text = _text("CHANGELOG.md")
    headers = list(re.finditer(r"^## \[", text, re.MULTILINE))
    if not headers:
        return None
    start = headers[0].start()
    end = headers[1].start() if len(headers) >= 2 else len(text)
    match = re.search(r"(\d+)\s+tests?\b", text[start:end])
    return int(match.group(1)) if match else None


def test_unreleased_changelog_avoids_brittle_test_count_claim():
    assert _changelog_test_count_claim() is None


def test_intent_does_not_claim_a_clean_scan_proves_safety():
    intent = _prose("INTENT.md").lower()
    assert "clean scan does not establish safety or correctness" in intent


def test_reference_labels_the_failing_demo_and_its_clean_comparison():
    reference = _text("llms-full.txt")
    section = reference.split("## Reading a repository sample", 1)[1].split("## First run", 1)[0]
    assert "This is a deliberately failing fixture" in section
    assert "`lintlang scan samples/clean_config.yaml --fail-on fail`" in section
    assert "from a source\ncheckout" in section
    assert "[checkout-free clean example](#first-run-without-a-checkout)" in section
    assert "A clean static scan is not evidence" in section


def test_reference_failing_demo_count_matches_the_fixture():
    from collections import Counter

    from lintlang.scanner import scan_file

    findings = scan_file(REPO_ROOT / "samples/bad_tool_descriptions.yaml").structural_findings
    counts = Counter(finding.severity.name for finding in findings)
    summary = ", ".join(
        f"{counts[severity]} {severity}"
        for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        if counts[severity]
    )

    assert summary
    assert f"FAIL — {summary}" in _text("llms-full.txt")


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
        if target.name.lower() == "readme.md":
            continue
        assert target.is_relative_to(REPO_ROOT), (document, destination)
        assert target.exists(), (document, destination)
        if parsed.fragment and target.is_file():
            assert unquote(parsed.fragment) in _anchors(target.read_text(encoding="utf-8")), (
                document, destination,
            )


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


def test_gemini_host_evidence_is_not_silently_upgraded():
    gemini = _text("docs/gemini-cli-extension.md")
    assert "f89c3b0b8986fad162859dca052a8d5fe227eede" in gemini
    assert "0.32.1" in gemini and "0.5.3" in gemini


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
