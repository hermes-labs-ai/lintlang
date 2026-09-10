"""The README's checkout-free first run must keep producing what it publishes.

`README.md` → "First run without a checkout" tells a reader with no clone to
write two small YAML files and scan them. This module is the single source of
truth for those two fixtures: it extracts them straight out of the README, so
the published recipe cannot drift away from the scanner that has to satisfy it.

Pinned behaviour:

* the first fixture reports the ``H1.1`` CRITICAL and exits ``1`` under
  ``--fail-on fail`` — a successful detection, not a broken install;
* the second fixture no longer reports ``H1.1``, scans ``PASS`` and exits ``0``;
* an input that cannot be read stays the distinct ``ERROR`` verdict rather than
  collapsing into the finding-threshold exit.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

import lintlang
from lintlang.cli import main
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

README = Path(__file__).resolve().parent.parent / "README.md"
SECTION = "## First run without a checkout"
HEREDOC = re.compile(r"<<'YAML'\n(.*?)\nYAML\n", re.DOTALL)


def _readme_fixtures() -> list[str]:
    text = README.read_text(encoding="utf-8")
    start = text.index(SECTION)
    end = text.index("\n## ", start + len(SECTION))
    return HEREDOC.findall(text[start:end])


@pytest.fixture(scope="module")
def fixtures() -> list[str]:
    bodies = _readme_fixtures()
    assert len(bodies) == 2, (
        "README 'First run without a checkout' must publish exactly two YAML "
        f"fixtures; found {len(bodies)}"
    )
    return bodies


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body + "\n", encoding="utf-8")
    return path


def _codes(result) -> set[str]:
    return {f.code for f in result.structural_findings if f.code}


def test_bad_fixture_reports_h1_1_and_blocks(fixtures, tmp_path):
    path = _write(tmp_path, "agent.yaml", fixtures[0])
    result = scan_file(path)

    assert result.input_error is None
    assert "H1.1" in _codes(result)
    assert compute_verdict(result) == "FAIL"
    assert main(["scan", str(path), "--fail-on", "fail"]) == 1


def test_bad_fixture_severity_counts_match_the_published_line(fixtures, tmp_path):
    """README quotes 'FAIL — 1 CRITICAL, 1 HIGH, 1 MEDIUM'; pin that arithmetic."""
    path = _write(tmp_path, "agent.yaml", fixtures[0])
    result = scan_file(path)

    counts = Counter(f.severity.value for f in result.structural_findings)
    assert counts == Counter({"critical": 1, "high": 1, "medium": 1}), counts


def test_fixed_fixture_drops_h1_1_and_passes(fixtures, tmp_path):
    path = _write(tmp_path, "agent-fixed.yaml", fixtures[1])
    result = scan_file(path)

    assert result.input_error is None
    assert "H1.1" not in _codes(result)
    assert result.structural_findings == []
    assert compute_verdict(result) == "PASS"
    assert main(["scan", str(path), "--fail-on", "fail"]) == 0


def test_unscannable_input_stays_a_distinct_error(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    result = scan_file(missing)

    assert result.input_error is not None
    assert compute_verdict(result) == "ERROR"
    assert main(["scan", str(missing), "--fail-on", "fail"]) != 0


def _section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index(SECTION)
    return text[start : text.index("\n## ", start + len(SECTION))]


def test_section_publishes_exactly_the_scans_it_promises():
    """The prose says three scans; drift here misleads a first-time reader."""
    section = _section()
    scans = re.findall(r"^lintlang scan .*$", section, re.MULTILINE)
    assert len(scans) == 3, scans
    assert "run three scans" in section


def test_section_pins_the_packaged_release():
    """A floating install stops being release-matched the moment 0.5.3 ages out."""
    section = _section()
    assert f"pip install lintlang=={lintlang.__version__}" in section
    assert f"`lintlang {lintlang.__version__}` reports" in section


def test_section_does_not_claim_the_install_is_offline():
    """`pip install` reaches an index; only the scans are offline.

    The earlier wording ("Nothing here reads ... the network") covered the
    whole block including the install, which was not true.
    """
    section = _section()
    assert "Only the install reaches the network" in section
    assert "Every `lintlang scan` below is offline" in section
    assert "Nothing here reads" not in section
