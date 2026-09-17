"""Mechanical gate for evidence-scoped README and CHANGELOG claims.

The unreleased candidate intentionally avoids brittle collected-test counts:
the executable suite is the source of truth. The adoption path also keeps
regression methodology out of the main README. Version metadata has a separate
gate in ``test_version_consistency.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _readme_test_count_claim() -> int | None:
    """Extract the test-count claim from README opener.

    Looks in the first 1500 chars only — the bold quantified-opener band.
    Returns None if no claim is made.
    """
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    head = text[:1500]
    m = re.search(r"(\d+)\s+tests?\b", head)
    return int(m.group(1)) if m else None


def _changelog_test_count_claim() -> int | None:
    """Extract the test-count claim from the LATEST CHANGELOG entry.

    Reads from the first '## [' header to the next '## [' header. Returns
    None if the latest entry makes no numeric tests claim.
    """
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # Find the first '## [' header and the next one
    headers = list(re.finditer(r"^## \[", text, re.MULTILINE))
    if len(headers) < 1:
        return None
    start = headers[0].start()
    end = headers[1].start() if len(headers) >= 2 else len(text)
    section = text[start:end]
    m = re.search(r"(\d+)\s+tests?\b", section)
    return int(m.group(1)) if m else None


def test_readme_opener_avoids_brittle_test_count_claim():
    """The release-facing opener delegates suite size to executable pytest."""
    claimed = _readme_test_count_claim()
    assert claimed is None, (
        f"README opener claims {claimed} tests. Remove the brittle count and "
        "let the executable suite remain the source of truth."
    )


def test_unreleased_changelog_avoids_brittle_test_count_claim():
    """The pending release entry must not freeze an in-flight suite count."""
    claimed = _changelog_test_count_claim()
    assert claimed is None, (
        f"Latest CHANGELOG entry claims {claimed} tests. Remove the brittle "
        "count; final verification reports the executable suite result."
    )


def test_readme_keeps_regression_methodology_out_of_adoption_path():
    """The main README may show an excerpt without carrying eval methodology."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert "excerpt from `lintlang 0.6.0`" in readme
    assert "repository regression check" not in readme
    assert "external-project detector accuracy" not in readme


def test_public_docs_do_not_claim_a_clean_scan_proves_safety():
    """Static findings must not be promoted into a runtime guarantee."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    intent = (REPO_ROOT / "INTENT.md").read_text(encoding="utf-8").lower()
    assert "clean lintlang scan is not evidence" in readme
    assert "clean scan does not establish safety or correctness" in intent


def test_readme_opener_labels_the_failing_demo_and_its_clean_comparison():
    """A first-run FAIL must read as an intentional detection, not a broken install."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    opener = readme[:5000]

    assert "This is a deliberately failing fixture" in opener
    assert "`lintlang scan samples/clean_config.yaml --fail-on fail`" in opener
    assert "from a source\ncheckout" in opener
    assert "[checkout-free clean example](#first-run-without-a-checkout)" in opener
    assert "A clean static scan is not evidence" in opener


def test_readme_matches_released_baseline_and_scan_default_contracts():
    """Keep the adoption prose aligned with released CLI and Action behavior."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "Baseline support is included in released LintLang 0.6.0." in readme
    assert "The CLI has no verdict-failure threshold by default; the first-party GitHub\nAction defaults to `fail`." in readme
    assert "directory invocation that finds no eligible files" in readme
    assert "this “nothing scanned” outcome is\n  distinct from `ERROR`" in readme
