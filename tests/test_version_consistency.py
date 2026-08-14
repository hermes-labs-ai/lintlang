"""Mechanical gate: `lintlang.__version__` must equal `pyproject.toml` version.

The doc-consistency gate (`test_docs_consistency.py`) explicitly documents that
"PyPI version drift between pyproject and CHANGELOG" is a *separate gate* it does
not cover. This is that gate — the narrowest possible version-of-record check.

Why it exists: on 2026-07-05 the shipped package (`pip show lintlang` → 0.2.2,
PyPI latest 0.2.2, `pyproject.toml` → 0.2.2) reported `lintlang.__version__ ==
"0.2.1"`. `lintlang --version` and any programmatic `importlib.metadata`-vs-
`__version__` comparison therefore disagreed with the published artifact — a
falsifiable public inconsistency in a tool people already depend on. This gate
fails CI the moment the two drift again.

The check reads the source `__version__` and the `[project].version` field
directly (not the installed metadata) so it holds in a fresh clone before any
build/install step.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None  # type: ignore[assignment]

import lintlang

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
CITATION = REPO_ROOT / "CITATION.cff"
README = REPO_ROOT / "README.md"
ZENODO = REPO_ROOT / ".zenodo.json"
CODEMETA = REPO_ROOT / "codemeta.json"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        data = tomllib.loads(text)
        return str(data["project"]["version"])
    # Python 3.10: minimal regex fallback (no tomllib in stdlib)
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert m, "could not locate [project] version in pyproject.toml"
    return m.group(1)


def test_dunder_version_matches_pyproject():
    """`lintlang.__version__` must equal the packaged `[project].version`.

    If this fails, update `src/lintlang/__init__.py:__version__` (or
    `pyproject.toml`) so the runtime version-of-record matches the published
    artifact. They must never disagree — `lintlang --version` reports the
    dunder, PyPI/pip report the pyproject value.
    """
    dunder = lintlang.__version__
    packaged = _pyproject_version()
    assert dunder == packaged, (
        f"\n\nlintlang.__version__ == {dunder!r} but pyproject [project].version "
        f"== {packaged!r}.\n"
        f"Fix: set both to the same string (the version actually published to "
        f"PyPI).\n"
    )


def test_version_surfaces_match_pyproject_and_release_state():
    """Metadata must name the package version without inventing a release date."""
    packaged = _pyproject_version()
    changelog = CHANGELOG.read_text(encoding="utf-8")
    citation = CITATION.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    zenodo = json.loads(ZENODO.read_text(encoding="utf-8"))

    changelog_match = re.search(r"(?m)^## \[([^]]+)\] - (Unreleased|\d{4}-\d{2}-\d{2})$", changelog)
    citation_match = re.search(r'(?m)^version:\s*["\']?([^"\'\s]+)', citation)
    citation_date_match = re.search(r'(?m)^date-released:\s*["\']?([^"\'\s]+)', citation)

    assert changelog_match, "CHANGELOG.md has no release heading"
    assert citation_match, "CITATION.cff has no version field"
    assert changelog_match.group(1) == packaged, (
        f"CHANGELOG latest version {changelog_match.group(1)!r} does not match pyproject version {packaged!r}"
    )
    assert citation_match.group(1) == packaged, (
        f"CITATION.cff version {citation_match.group(1)!r} does not match pyproject version {packaged!r}"
    )
    assert zenodo["version"] == packaged, (
        f".zenodo.json version {zenodo['version']!r} does not match pyproject version {packaged!r}"
    )
    release_state = changelog_match.group(2)
    if release_state == "Unreleased":
        assert citation_date_match is None, (
            "CITATION.cff must not contain date-released while the latest CHANGELOG entry is Unreleased"
        )
    else:
        assert citation_date_match, "released CITATION.cff has no date-released field"
        assert citation_date_match.group(1) == release_state, (
            f"CITATION.cff date {citation_date_match.group(1)!r} does not match "
            f"CHANGELOG release date {release_state!r}"
        )
    assert f"LINTLANG v{packaged}" in readme or f"@v{packaged}" in readme
    assert "LINTLANG v0.2.0" not in readme
    assert "LINTLANG v0.2.1" not in readme


def test_codemeta_matches_release_metadata():
    """CodeMeta must use a stable context and track the packaged release."""
    packaged = _pyproject_version()
    citation = CITATION.read_text(encoding="utf-8")
    codemeta = json.loads(CODEMETA.read_text(encoding="utf-8"))

    repository_match = re.search(r'(?m)^repository-code:\s*["\']?([^"\'\s]+)', citation)
    assert repository_match, "CITATION.cff has no repository-code field"

    release_url = f"https://pypi.org/project/lintlang/{packaged}/"
    assert codemeta["@context"] == "https://w3id.org/codemeta/3.1"
    assert codemeta["@type"] == "SoftwareSourceCode"
    assert codemeta["version"] == packaged
    assert codemeta["codeRepository"] == repository_match.group(1)
    assert codemeta["url"] == release_url
    assert release_url in codemeta["identifier"]
