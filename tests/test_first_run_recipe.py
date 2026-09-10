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


def _section() -> str:
    """The published section, sliced once and reused by every check.

    The section currently has a sibling after it, but it must keep working as
    the last section in the file — `str.index` would raise there, so fall back
    to end-of-file instead.
    """
    text = README.read_text(encoding="utf-8")
    start = text.index(SECTION)
    next_heading = text.find("\n## ", start + len(SECTION))
    end = len(text) if next_heading == -1 else next_heading
    return text[start:end]


def _readme_fixtures() -> list[str]:
    return HEREDOC.findall(_section())


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


def test_section_scopes_pass_to_the_fixed_file_only():
    """Only the repaired fixture passes; the original still FAILs.

    Earlier wording ("this pair of files scans PASS", "these two files") read
    as though both fixtures came out clean, which contradicts the FAIL the
    section publishes a few lines earlier.
    """
    section = _section()
    assert "this pair of files scans" not in section
    assert "these two files" not in section
    assert "the fixed file scans `PASS — 0 findings`" in section
    assert "the original\n`/tmp/agent.yaml` still scans `FAIL`" in section
    assert "extracted from `/tmp/agent-fixed.yaml`" in section


def test_section_extraction_survives_being_the_last_section(tmp_path, monkeypatch):
    """`_section()` must not depend on a heading following the block."""
    truncated = tmp_path / "README.md"
    truncated.write_text(_section(), encoding="utf-8")
    monkeypatch.setattr(f"{__name__}.README", truncated, raising=False)
    monkeypatch.setitem(globals(), "README", truncated)

    assert len(_readme_fixtures()) == 2
    assert _section().startswith(SECTION)


def test_section_publishes_an_explicit_latest_install():
    """A reader who declines the pin needs the command, not just permission."""
    section = _section()
    assert "python -m pip install --upgrade lintlang" in section
    assert "re-read the counts below as approximate" in section


# --- outbound-network deny guard ------------------------------------------

# Prepended to the CHILD script, so the denial is installed in the scanning
# process before lintlang is imported rather than asserted from the parent. A
# `sitecustomize.py` would shadow the interpreter's own, which on some builds
# is what puts site-packages on the path.
_DENY_OUTBOUND = """\
import socket


class OutboundNetworkDenied(RuntimeError):
    pass


def _deny(*args, **kwargs):
    raise OutboundNetworkDenied("outbound network access attempted")


socket.socket = _deny
socket.create_connection = _deny
socket.getaddrinfo = _deny
"""

# Both paths the README documents: the library entry point and the CLI.
_OFFLINE_DRIVER = """\
import json
import sys

from lintlang.cli import main
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

bad, fixed, missing = sys.argv[1:4]

result = scan_file(bad)
payload = {
    "scan_file_codes": sorted({f.code for f in result.structural_findings if f.code}),
    "scan_file_verdict": compute_verdict(result),
    "fixed_verdict": compute_verdict(scan_file(fixed)),
    "missing_verdict": compute_verdict(scan_file(missing)),
    "cli_bad": main(["scan", bad, "--fail-on", "fail"]),
    "cli_fixed": main(["scan", fixed, "--fail-on", "fail"]),
    "cli_missing": main(["scan", missing, "--fail-on", "fail"]),
}
print("RESULT " + json.dumps(payload))
"""


def test_documented_paths_run_with_outbound_network_denied(fixtures, tmp_path):
    """The published offline claim, enforced inside the scanning process.

    Exercises both documented paths — `scan_file` and the CLI — so the claim
    covers what a reader actually runs, not just one of them.
    """
    import json
    import os
    import subprocess
    import sys

    bad = _write(tmp_path, "agent.yaml", fixtures[0])
    fixed = _write(tmp_path, "agent-fixed.yaml", fixtures[1])
    missing = tmp_path / "does-not-exist.yaml"

    repo_src = Path(__file__).resolve().parent.parent / "src"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path / "no-such-home"),
        "PYTHONPATH": str(repo_src),
    }

    # The guard must actually bite, or this test proves nothing.
    proof = subprocess.run(
        [sys.executable, "-c", _DENY_OUTBOUND + "\nimport socket\nsocket.socket()\n"],
        capture_output=True, text=True, env=env, cwd=os.fspath(tmp_path), check=False,
    )
    assert proof.returncode != 0
    assert "OutboundNetworkDenied" in proof.stderr

    run = subprocess.run(
        [sys.executable, "-c", _DENY_OUTBOUND + _OFFLINE_DRIVER,
         str(bad), str(fixed), str(missing)],
        capture_output=True, text=True, env=env, cwd=os.fspath(tmp_path), check=False,
    )
    assert run.returncode == 0, run.stderr
    line = next(ln for ln in run.stdout.splitlines() if ln.startswith("RESULT "))
    payload = json.loads(line[len("RESULT "):])

    assert "H1.1" in payload["scan_file_codes"]
    assert payload["scan_file_verdict"] == "FAIL"
    assert payload["fixed_verdict"] == "PASS"
    assert payload["missing_verdict"] == "ERROR"
    assert payload["cli_bad"] == 1
    assert payload["cli_fixed"] == 0
    assert payload["cli_missing"] != 0
