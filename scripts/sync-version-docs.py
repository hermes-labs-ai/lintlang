#!/usr/bin/env python3
"""Synchronize release-bearing LintLang references in product documentation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+!-]*)"
REPLACEMENTS = (
    (re.compile(rf"(LINTLANG v){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(\blintlang\s+v?){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(hermes-labs-ai/lintlang@v){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(^[ \t]*rev:[ \t]*v){VERSION}", re.MULTILINE), r"\g<1>{version}"),
)


def product_docs(root: Path, version: str) -> list[Path]:
    candidates = [root / "llms.txt", root / "llms-full.txt"]
    candidates.extend(sorted((root / "docs").rglob("*.md")))
    current_match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    assert current_match is not None
    current = tuple(int(part) for part in current_match.groups())
    selected = []
    for path in candidates:
        if not path.is_file() or path.name.lower() == "readme.md":
            continue
        release_match = re.fullmatch(r"release-(\d+)\.(\d+)\.(\d+)\.md", path.name)
        if release_match and tuple(int(part) for part in release_match.groups()) < current:
            continue
        selected.append(path)
    return selected


def synchronized(text: str, version: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        text = pattern.sub(replacement.format(version=version), text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if re.fullmatch(VERSION, args.version) is None:
        parser.error("--version must be a three-component release version")

    changed: list[Path] = []
    root = args.root.resolve()
    for path in product_docs(root, args.version):
        before = path.read_text(encoding="utf-8")
        after = synchronized(before, args.version)
        if after == before:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(after, encoding="utf-8")

    for path in changed:
        print(path.relative_to(root))
    return int(args.check and bool(changed))


if __name__ == "__main__":
    raise SystemExit(main())
