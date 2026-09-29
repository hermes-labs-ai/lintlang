"""Re-run every ``examples/real-world/`` transcript and compare it to the checked-in output.

Each example directory holds ``commands.txt`` (one ``lintlang`` argument list per
line) and ``expected-output.txt`` (the exact combined stdout/stderr and exit code
of each command). The scan runs in a scratch copy of the tree so that examples
which write a baseline never touch the checkout. Only the lintlang version string
is normalized; any other drift means the documented output is stale.

Refresh after an intentional output change with::

    python tests/test_real_world_examples.py --regenerate
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples" / "real-world"
SLUGS = sorted(p.name for p in EXAMPLES.iterdir() if (p / "commands.txt").is_file())
VERSION = re.compile(r"(?i)\b(lintlang) v\d+\.\d+\.\d+")
SHA40 = re.compile(r"\b[0-9a-f]{40}\b")


def _commands(slug: str) -> list[list[str]]:
    lines = (EXAMPLES / slug / "commands.txt").read_text(encoding="utf-8").splitlines()
    return [shlex.split(line) for line in lines if line.strip() and not line.startswith("#")]


def render_transcript(slug: str, tree: Path) -> str:
    """Run the example's commands inside ``tree`` (a copy of examples/real-world)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO_ROOT / "src"), env.get("PYTHONPATH")]))
    parts: list[str] = []
    for args in _commands(slug):
        done = subprocess.run(
            [sys.executable, "-m", "lintlang", *args],
            cwd=tree / slug, env=env, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        parts.append(f"$ lintlang {shlex.join(args)}\n{done.stdout}{done.stderr}[exit {done.returncode}]\n")
    return "\n".join(parts)


def _normalize(text: str) -> str:
    return VERSION.sub(r"\1 v<VERSION>", text)


def _scratch_copy(tmp_path: Path) -> Path:
    tree = tmp_path / "real-world"
    shutil.copytree(EXAMPLES, tree)
    return tree


def _input_available(slug: str) -> bool:
    # The OpenRouterTeam/skills repository publishes no license, so its SKILL.md is
    # pinned by commit and checksum instead of being vendored here.
    return not (slug == "openrouter-skill-benchmarks" and not (EXAMPLES / slug / "input" / "SKILL.md").is_file())


def test_examples_are_discovered():
    assert len(SLUGS) >= 5


@pytest.mark.parametrize("slug", SLUGS)
def test_example_has_required_files_and_provenance(slug: str):
    directory = EXAMPLES / slug
    for name in ("README.md", "commands.txt", "expected-output.txt"):
        assert (directory / name).is_file(), f"{slug}/{name} is missing"
    readme = (directory / "README.md").read_text(encoding="utf-8")
    for heading in ("## What real job this models", "## Provenance", "## What this does not tell you"):
        assert heading in readme, f"{slug}/README.md lacks '{heading}'"
    assert f"({slug}/)" in (EXAMPLES / "README.md").read_text(encoding="utf-8")


def test_pinned_third_party_sources_record_a_commit_and_checksum():
    for slug in ("openrouter-skill-benchmarks", "okta-tool-manifest", "baseline-tool-manifest", "ci-gate-exit-codes"):
        readme = (EXAMPLES / slug / "README.md").read_text(encoding="utf-8")
        assert SHA40.search(readme), f"{slug} does not pin a commit SHA"
        assert re.search(r"\b[0-9a-f]{64}\b", readme), f"{slug} does not record a sha256"


def test_vendored_inputs_match_recorded_checksums():
    import hashlib

    recorded = {
        "okta-tool-manifest/input.json": "635119ee73ab64163f9a2f6d51ada013f1002d5cdfee47a1381be759b1bfcc92",
        "baseline-tool-manifest/input.json": "48a6434dbfe98eb10428e2b45a57030f924c29aa1d107ff3be6ec59b4bab36a1",
        "ci-gate-exit-codes/input-unrecognized-shape.json": (
            "9756a1e9176917945823cbd2c8d5eb763b4c83e6257235a369474cf079919f33"
        ),
    }
    for relative, digest in recorded.items():
        assert hashlib.sha256((EXAMPLES / relative).read_bytes()).hexdigest() == digest, relative
    skill = EXAMPLES / "openrouter-skill-benchmarks" / "input" / "SKILL.md"
    if skill.is_file():
        assert hashlib.sha256(skill.read_bytes()).hexdigest() == (
            "6bfc172fe75e95c9b2f9df0510d61f5913663e123f70ae4d94e351a9401940fd"
        )


@pytest.mark.parametrize("slug", SLUGS)
def test_example_output_matches_transcript(slug: str, tmp_path: Path):
    if not _input_available(slug):
        pytest.skip("third-party SKILL.md is not vendored; see the example README to fetch it at the pinned commit")
    expected = (EXAMPLES / slug / "expected-output.txt").read_text(encoding="utf-8")
    actual = render_transcript(slug, _scratch_copy(tmp_path))
    assert _normalize(actual) == _normalize(expected)


def _regenerate() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        tree = _scratch_copy(Path(scratch))
        for slug in SLUGS:
            if not _input_available(slug):
                print(f"skipped {slug}: input not present")
                continue
            (EXAMPLES / slug / "expected-output.txt").write_text(render_transcript(slug, tree), encoding="utf-8")
            print(f"wrote {slug}/expected-output.txt")


if __name__ == "__main__":
    if "--regenerate" in sys.argv:
        _regenerate()
    else:
        raise SystemExit("usage: python tests/test_real_world_examples.py --regenerate")
