"""Execute the reference's checkout-free first run, including its offline claim.

The technical reference owns the published fixtures. Moving them out of the
README must preserve FAIL/PASS/ERROR, severity counts, release pins, Windows
parity, overwrite guidance, and the child-process outbound-network denial gate.
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

REFERENCE = Path(__file__).resolve().parent.parent / "llms-full.txt"
SECTION = "## First run without a checkout"
HEREDOC = re.compile(r"<<'YAML'\n(.*?)\nYAML\n", re.DOTALL)
WINDOWS_HEADING = "### Windows PowerShell"
POWERSHELL_HERE_STRING = re.compile(r"@'\n(.*?)\n'@", re.DOTALL)


def _section() -> str:
    text = REFERENCE.read_text(encoding="utf-8")
    start = text.index(SECTION)
    next_heading = text.find("\n## ", start + len(SECTION))
    end = len(text) if next_heading == -1 else next_heading
    return text[start:end]


def _reference_fixtures() -> list[str]:
    return HEREDOC.findall(_section())


def _windows_section() -> str:
    section = _section()
    return section[section.index(WINDOWS_HEADING):]


def _powershell_fixtures() -> list[str]:
    return POWERSHELL_HERE_STRING.findall(_windows_section())


@pytest.fixture(scope="module")
def fixtures() -> list[str]:
    bodies = _reference_fixtures()
    assert len(bodies) == 2, f"Reference first run must publish two YAML fixtures; found {len(bodies)}"
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
    result = scan_file(_write(tmp_path, "agent.yaml", fixtures[0]))
    counts = Counter(f.severity.value for f in result.structural_findings)
    assert counts == Counter({"critical": 1, "high": 1, "medium": 1}), counts
    assert "FAIL — 1 CRITICAL, 1 HIGH, 1 MEDIUM" in _section()


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
    section = _section()
    scans = re.findall(r"^lintlang scan .*$", section, re.MULTILINE)
    assert len(scans) == 3, scans
    assert "run three scans" in section


def test_section_pins_the_packaged_release():
    section = _section()
    assert f"pip install lintlang=={lintlang.__version__}" in section
    assert f"`lintlang {lintlang.__version__}` reports" in section


def test_section_does_not_claim_the_install_is_offline():
    section = _section()
    assert "Only the install reaches the network" in section
    assert "Every `lintlang scan` below is offline" in section
    assert "Nothing here reads" not in section


def test_section_scopes_pass_to_the_fixed_file_only():
    section = _section()
    assert "this pair of files scans" not in section
    assert "these two files" not in section
    assert "the fixed file scans `PASS — 0 findings`" in section
    assert "the original\n`/tmp/agent.yaml` still scans `FAIL`" in section
    assert "extracted from `/tmp/agent-fixed.yaml`" in section


def test_section_extraction_survives_being_the_last_section(tmp_path, monkeypatch):
    truncated = tmp_path / "llms-full.txt"
    truncated.write_text(_section(), encoding="utf-8")
    monkeypatch.setitem(globals(), "REFERENCE", truncated)
    assert len(_reference_fixtures()) == 2
    assert _section().startswith(SECTION)


def test_section_publishes_an_explicit_latest_install():
    section = _section()
    assert "python -m pip install --upgrade lintlang" in section
    assert "re-read the counts below as approximate" in section


def test_successful_first_run_surfaces_the_non_destructive_github_next_step():
    section = _section()
    heading = "### Keep a successful check in GitHub CI"
    assert heading in section
    assert section.index(heading) > section.index("`PASS` here means")
    assert "lintlang init --github --path AGENTS.md" in section
    assert "Run this from the repository root" in section
    assert "left alone" in section
    assert "replacing it with `--force`" in section


def test_windows_powershell_recipe_matches_the_verified_fixtures(fixtures):
    section = _windows_section()
    assert _powershell_fixtures() == fixtures
    assert 'Join-Path $env:TEMP "agent.yaml"' in section
    assert 'Join-Path $env:TEMP "agent-fixed.yaml"' in section
    assert "python -m lintlang scan $badPath --fail-on fail" in section
    assert "python -m lintlang scan $fixedPath --fail-on fail" in section
    assert "python -m lintlang scan (Join-Path $env:TEMP" in section


# Denial is installed INSIDE the child before the scanner is imported.
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
    proof = subprocess.run(
        [sys.executable, "-c", _DENY_OUTBOUND + "\nimport socket\nsocket.socket()\n"],
        capture_output=True, text=True, env=env, cwd=os.fspath(tmp_path), check=False,
    )
    assert proof.returncode != 0
    assert "OutboundNetworkDenied" in proof.stderr
    run = subprocess.run(
        [sys.executable, "-c", _DENY_OUTBOUND + _OFFLINE_DRIVER, str(bad), str(fixed), str(missing)],
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
