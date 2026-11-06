#!/usr/bin/env python3
"""Synchronize current LintLang release references without rewriting history."""

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

CURRENT_PIN_REPLACEMENTS = (
    (re.compile(rf"(lintlang==){VERSION}", re.IGNORECASE), r"\g<1>{version}"),
    (re.compile(rf"(PINNED_VERSION\s*=\s*[\"']){VERSION}([\"'])"), r"\g<1>{version}\g<2>"),
    (re.compile(rf"(\bLintLang\s+v?){VERSION}(?=\s+package\b)"), r"\g<1>{version}"),
    (re.compile(rf"(\bversion\s+){VERSION}(?=\s+or newer\b)"), r"\g<1>{version}"),
)

COMMAND_PIN_REPLACEMENTS = (
    (re.compile(rf"(uvx --from lintlang==){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(python -m pip install(?: -U)? lintlang==){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(pipx install lintlang==){VERSION}"), r"\g<1>{version}"),
    (re.compile(rf"(pip install --no-cache-dir lintlang==){VERSION}"), r"\g<1>{version}"),
)

CURRENT_PIN_FILES = {
    Path("docs/baselines.md"),
    Path("integrations/claude-code/README.md"),
    Path("integrations/claude-code/hooks-handlers/post-tool-use.py"),
    Path("integrations/claude-code/skills/lintlang-audit/SKILL.md"),
    Path("integrations/copilot-cli/README.md"),
    Path("integrations/copilot-cli/skills/lintlang-audit/SKILL.md"),
    Path("integrations/opencode/README.md"),
    Path("integrations/opencode/lintlang.js"),
    Path("mega-linter-plugin-lintlang/README.md"),
    Path("mega-linter-plugin-lintlang/lintlang.megalinter-descriptor.yml"),
    Path("skills/lintlang/SKILL.md"),
}

JSON_VERSION_FILES = {
    Path(".zenodo.json"),
    Path("codemeta.json"),
    Path("gemini-extension.json"),
    Path("integrations/claude-code/.claude-plugin/plugin.json"),
    Path("integrations/claude-code/.cursor-plugin/plugin.json"),
    Path("integrations/claude-code/plugin.json"),
}


def product_docs(root: Path) -> list[Path]:
    candidates = [root / "llms.txt", root / "llms-full.txt"]
    candidates.extend(sorted((root / "docs").rglob("*.md")))
    return [path for path in candidates if path.is_file() and path.name.lower() != "readme.md"]


def synchronized(text: str, version: str) -> str:
    for pattern, replacement in REPLACEMENTS:
        text = pattern.sub(replacement.format(version=version), text)
    return text


def synchronized_release_surface(path: Path, text: str, version: str) -> str:
    """Update a known current-version surface while preserving held pins."""
    text = synchronized(text, version)
    if path.parent == Path(".github/releases"):
        text = re.sub(
            rf"(?m)^(# LintLang v){VERSION}(\b.*)$",
            rf"\g<1>{version}\g<2>",
            text,
            count=1,
        )
    for pattern, replacement in COMMAND_PIN_REPLACEMENTS:
        text = pattern.sub(replacement.format(version=version), text)
    if path in CURRENT_PIN_FILES:
        for pattern, replacement in CURRENT_PIN_REPLACEMENTS:
            text = pattern.sub(replacement.format(version=version), text)
    if path in JSON_VERSION_FILES:
        text = re.sub(
            rf'(?m)^(\s*"version"\s*:\s*"){VERSION}("\s*,?)$',
            rf"\g<1>{version}\g<2>",
            text,
            count=1,
        )
    if path == Path("codemeta.json"):
        text = re.sub(
            rf"(pypi\.org/project/lintlang/){VERSION}(/?)",
            rf"\g<1>{version}\g<2>",
            text,
        )
    if path == Path("CITATION.cff"):
        text = re.sub(rf'(?m)^(version:\s*"){VERSION}("\s*)$', rf"\g<1>{version}\g<2>", text)
    if path == Path("pyproject.toml"):
        project = re.search(r"(?ms)^\[project\]\s*$.*?(?=^\[|\Z)", text)
        if project is None:
            raise ValueError("pyproject.toml has no [project] table")
        updated = re.sub(
            rf'(?m)^(version\s*=\s*"){VERSION}("\s*)$',
            rf"\g<1>{version}\g<2>",
            project.group(0),
            count=1,
        )
        text = text[: project.start()] + updated + text[project.end() :]
    if path == Path("src/lintlang/__init__.py"):
        text = re.sub(
            rf'(?m)^(__version__\s*=\s*"){VERSION}("\s*)$',
            rf"\g<1>{version}\g<2>",
            text,
            count=1,
        )
    return text


def release_surfaces(root: Path, version: str) -> list[Path]:
    relative_paths = CURRENT_PIN_FILES | JSON_VERSION_FILES | {
        Path(f".github/releases/v{version}.md"),
        Path("CITATION.cff"),
        Path("pyproject.toml"),
        Path("src/lintlang/__init__.py"),
    }
    paths = set(product_docs(root))
    paths.update(root / path for path in relative_paths if (root / path).is_file())
    return sorted(paths)


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
    for path in release_surfaces(root, args.version):
        before = path.read_text(encoding="utf-8")
        after = synchronized_release_surface(path.relative_to(root), before, args.version)
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
