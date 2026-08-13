"""Verify that a release tag exactly matches the package version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def project_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    project_match = re.search(r"(?ms)^\[project\]\s*$([\s\S]*?)(?=^\[|\Z)", text)
    if project_match is None:
        raise ValueError("pyproject.toml has no [project] table")
    version_match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', project_match.group(1))
    if version_match is None:
        raise ValueError("pyproject.toml [project] table has no literal version")
    return version_match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)

    try:
        version = project_version(args.pyproject)
    except (OSError, ValueError) as error:
        print(f"release verification failed: {error}", file=sys.stderr)
        return 1
    expected = f"v{version}"
    if args.tag != expected:
        print(f"release tag {args.tag!r} does not match expected tag {expected!r}", file=sys.stderr)
        return 1
    print(f"release tag {args.tag} matches package version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
