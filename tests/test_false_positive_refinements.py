"""H4.5 path exemptions apply to occurrences, preserving required inputs."""

from pathlib import Path

import pytest

from lintlang.scanner import scan_file


def _references(tmp_path: Path, body: str) -> list[tuple[str, int]]:
    for directory in ("docs", "src", "dist", "examples"):
        (tmp_path / directory).mkdir(exist_ok=True)
    source = tmp_path / "AGENTS.md"
    source.write_text(body)
    return [
        (finding.location, finding.source_region.start_line)
        for finding in scan_file(source, gate=False).structural_findings
        if finding.code == "H4.5"
    ]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Build emits\n`dist/app.js`, then reads `src/input.py`.\n", [("reference:src/input.py", 2)]),
        ("Create:\n- `docs/report.md`\n- Read `src/input.py`.\n", [("reference:src/input.py", 3)]),
        ("Read `src/input.py`, installed as `dist/app.js`.\n", [("reference:src/input.py", 1)]),
        ("Create `docs/report.md` from `src/input.py`.\n", [("reference:src/input.py", 1)]),
        ("Build emits\n\n`dist/app.js`\n", [("reference:dist/app.js", 3)]),
        ("Build emits\n`dist/app.js`. Read `src/input.py`.\n", [("reference:src/input.py", 2)]),
        ("If `docs/policy.md` exists, read `docs/policy.md`.\n", [("reference:docs/policy.md", 1)]),
        ("For example, read `src/input.py`.\n", []),
        ("Do not read `src/input.py`.\n", []),
        ("Read `examples/runner.py` before starting.\n", [("reference:examples/runner.py", 1)]),
    ],
)
def test_path_role_preserves_actionable_input(tmp_path: Path, body: str, expected: list[tuple[str, int]]) -> None:
    assert _references(tmp_path, body) == expected


def test_external_declaration_exempts_only_its_bare_items(tmp_path: Path) -> None:
    body = (
        "Load these files from `acme/reference-library` (they are not available locally).\n"
        "- `docs/policy.md`\n\n"
        "Read `docs/policy.md` from this local repository.\n"
    )
    assert _references(tmp_path, body) == [("reference:docs/policy.md", 4)]


@pytest.mark.parametrize("interruption", ["", "## New section", "- Read `src/other.py`"])
def test_external_binding_ends_on_interruption(tmp_path: Path, interruption: str) -> None:
    body = (
        "Load these files from `acme/reference-library` (they are not available locally).\n"
        f"{interruption}\n- `docs/policy.md`\n"
    )
    assert ("reference:docs/policy.md", 3) in _references(tmp_path, body)


def test_external_route_requires_prior_unique_source_and_preserves_local_read(tmp_path: Path) -> None:
    body = (
        "Load these files from `acme/reference-library` (they are not available locally).\n"
        "- `docs/policy.md`\n\n"
        "After loading the matching workflow prompt or skill, follow it directly:\n"
        "- Design workflows: `docs/policy.md`\n"
        "Read `docs/policy.md` from this local repository.\n"
    )
    assert _references(tmp_path, body) == [("reference:docs/policy.md", 6)]


def test_contrast_sample_keeps_only_local_reference(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "samples/release_088/h4_occurrences.md"
    assert _references(tmp_path, fixture.read_text()) == [("reference:docs/policy.md", 6)]
