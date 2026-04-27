"""Mechanical consistency gate: README + CHANGELOG + pytest agree on test count.

CI fails if any documentation surface drifts from the actual pytest collection
count. Prevents the fabrication-class issue where a chisel pass updates the
README opener but leaves the CHANGELOG narrative quoting a stale figure (or
vice versa) — the same family as the κ=0.632 / 235-tests drift caught in
sister repos on 2026-04-26.

The test is intentionally narrow:
  - README must contain the actual pytest count somewhere in its first 1500
    chars (the opener / quantified claims band).
  - CHANGELOG's latest entry, if it makes a numeric tests claim at all, must
    cite the actual count.
  - Mismatches fail with a specific message naming which file to fix.

Future drift modes this test does NOT catch (intentionally — keep the gate
narrow + reliable):
  - Inflation / deflation of non-test numbers (latency, accuracy, etc.)
  - Marketing copy outside the documented bands
  - Coverage percentages
  - PyPI version drift between pyproject and CHANGELOG (separate gate)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _pytest_collected_count() -> int:
    """Run `pytest --collect-only -q` and parse the trailing count line."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    # Last non-empty line is "N tests collected in X.XXs"
    for line in reversed(out.stdout.strip().splitlines()):
        line = line.strip()
        m = re.match(r"(\d+)\s+tests?\s+collected", line)
        if m:
            return int(m.group(1))
    raise RuntimeError(
        f"could not parse pytest --collect-only output:\n{out.stdout}\n---\n{out.stderr}"
    )


def _readme_test_count_claim() -> int | None:
    """Extract the test-count claim from README opener.

    Looks in the first 1500 chars only — the bold quantified-opener band.
    Returns None if no claim is made (acceptable; not all flagships claim
    a test count up front).
    """
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    head = text[:1500]
    m = re.search(r"(\d+)\s+tests?\b", head)
    return int(m.group(1)) if m else None


def _changelog_test_count_claim() -> int | None:
    """Extract the test-count claim from the LATEST CHANGELOG entry.

    Reads from the first '## [' header to the next '## [' header. Returns
    None if the latest entry makes no numeric tests claim (acceptable).
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


def test_readme_test_count_matches_pytest_collection():
    """README's quantified-opener test count must equal `pytest --collect-only`.

    If this fails, update either README.md (to match the actual collection
    count) or pytest (if a test was added/removed without updating the opener).
    """
    actual = _pytest_collected_count()
    claimed = _readme_test_count_claim()
    if claimed is None:
        pytest.skip("README does not claim a test count in its opener band")
    assert claimed == actual, (
        f"\n\nREADME opener claims {claimed} tests; pytest --collect-only "
        f"returns {actual}.\n"
        f"Fix: update README.md so the bold opener cites '{actual} tests'.\n"
    )


def test_changelog_test_count_matches_pytest_collection():
    """Latest CHANGELOG entry's test count claim must equal pytest collection.

    If this fails, update CHANGELOG.md's most-recent version entry.
    """
    actual = _pytest_collected_count()
    claimed = _changelog_test_count_claim()
    if claimed is None:
        pytest.skip(
            "Latest CHANGELOG entry does not claim a test count "
            "(acceptable; gate is opt-in per entry)"
        )
    assert claimed == actual, (
        f"\n\nLatest CHANGELOG entry claims {claimed} tests; "
        f"pytest --collect-only returns {actual}.\n"
        f"Fix: update CHANGELOG.md's most-recent version entry to cite "
        f"'{actual} tests'.\n"
    )


def test_readme_and_changelog_agree_with_each_other():
    """Cross-check: if both README and CHANGELOG make claims, they must match.

    This catches the case where pytest is wrong / unreachable but the docs
    are at least internally consistent.
    """
    readme_n = _readme_test_count_claim()
    changelog_n = _changelog_test_count_claim()
    if readme_n is None or changelog_n is None:
        pytest.skip(
            "One of README / CHANGELOG does not claim a test count "
            "(internal-consistency gate is opt-in per surface)"
        )
    assert readme_n == changelog_n, (
        f"\n\nREADME opener claims {readme_n} tests; CHANGELOG latest entry "
        f"claims {changelog_n} tests.\n"
        f"Fix: pick one count (the actual pytest collection number) and "
        f"update both surfaces to match.\n"
    )
