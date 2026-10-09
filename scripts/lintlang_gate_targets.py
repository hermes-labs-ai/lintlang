"""Scan changed agent instructions for Hermes Gate using this checkout's LintLang."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lintlang.cli import main  # noqa: E402
from lintlang.instructions import is_recognized_instruction_path  # noqa: E402

FIXTURE_ROOTS = frozenset({"samples", "tests", "evals", "vendor", ".hermes", "build", "dist"})


def select_targets(changed: list[str]) -> list[str]:
    """Keep production instruction inputs; fixtures are tested by pytest."""
    selected: set[str] = set()
    for name in changed:
        path = Path(name)
        if not path.parts or path.parts[0] in FIXTURE_ROOTS:
            continue
        if any(part in {"fixtures", "__fixtures__", "testdata"} for part in path.parts[:-1]):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if is_recognized_instruction_path(name) or path.suffix == ".prompt":
            selected.add(name)
    return sorted(selected)


if __name__ == "__main__":
    targets = select_targets(sys.argv[1:])
    if targets:
        raise SystemExit(main(["scan", *targets, "--no-gate", "--format", "json", "--fail-on", "review"]))
    print("[]")
