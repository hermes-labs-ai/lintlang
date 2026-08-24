"""Safe, deterministic GitHub Actions setup for LintLang."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_WORKFLOW_PATH = Path(".github/workflows/lintlang.yml")
_DEFAULT_INPUTS = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path(".github/copilot-instructions.md"),
    Path("agent.yaml"),
    Path("agent.yml"),
    Path("agent.json"),
)

_WORKFLOW = """name: LintLang

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  language-contract:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Scan agent instructions
        uses: hermes-labs-ai/lintlang@6be2907d557e534732865d3a3a3c55ea5f1a0ec9 # v0.4.1
        with:
          path: __LINTLANG_INPUT__
          fail-on: fail
          sarif-file: lintlang.sarif

      - name: Upload SARIF
        if: always() && (github.event_name == 'push' || (github.actor != 'dependabot[bot]' && github.event.pull_request.head.repo.full_name == github.repository))
        uses: github/codeql-action/upload-sarif@5595ccaf912efad79be6eef63a5619ff05969be3 # v4
        with:
          sarif_file: lintlang.sarif
"""


def configure_init_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the repository initialization command."""
    parser = subparsers.add_parser(
        "init",
        help="Add a pinned LintLang integration to the current repository",
    )
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--github",
        action="store_true",
        help="Create .github/workflows/lintlang.yml with SARIF upload",
    )
    parser.add_argument(
        "--path",
        help="Repository-relative instruction file or directory to scan",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing LintLang workflow whose content differs",
    )


def _git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _scan_target(root: Path, requested: str | None) -> Path:
    if requested is None:
        target = next((candidate for candidate in _DEFAULT_INPUTS if (root / candidate).exists()), None)
        if target is None:
            raise ValueError(
                "No supported instruction file was found; rerun with --path <repository-relative input>"
            )
    else:
        target = Path(requested)

    resolved_root = root.resolve()
    resolved_target = (root / target).resolve()
    try:
        relative = resolved_target.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("The scan path must stay inside the current Git repository") from error
    if not resolved_target.exists():
        raise ValueError(f"The scan path does not exist: {relative.as_posix()}")
    if not (resolved_target.is_file() or resolved_target.is_dir()):
        raise ValueError(f"The scan path is not a regular file or directory: {relative.as_posix()}")
    return relative


def _workflow(scan_target: Path) -> str:
    yaml_path = json.dumps(scan_target.as_posix(), ensure_ascii=False)
    return _WORKFLOW.replace("__LINTLANG_INPUT__", yaml_path)


def run_init(args: argparse.Namespace) -> int:
    """Create an idempotent GitHub Actions integration without silent overwrite."""
    if not args.github:
        print("Error: select an initialization target", file=sys.stderr)
        return 2

    root = _git_root(Path.cwd())
    if root is None:
        print("Error: lintlang init must run inside a Git repository", file=sys.stderr)
        return 1

    try:
        scan_target = _scan_target(root, args.path)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    destination = root / _WORKFLOW_PATH
    content = _workflow(scan_target)
    if destination.exists():
        if not destination.is_file():
            print(f"Error: workflow destination is not a file: {_WORKFLOW_PATH}", file=sys.stderr)
            return 1
        if destination.read_text(encoding="utf-8") == content:
            print(f"Up to date: {_WORKFLOW_PATH} scans {scan_target.as_posix()}")
            return 0
        if not args.force:
            print(
                f"Error: {_WORKFLOW_PATH} already exists and differs; review it or rerun with --force",
                file=sys.stderr,
            )
            return 1

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.write_text(content, encoding="utf-8")
        action = "Updated"
    else:
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(content)
        action = "Created"

    print(f"{action}: {_WORKFLOW_PATH}")
    print(f"Scans: {scan_target.as_posix()}")
    print(f"Next: git diff -- {_WORKFLOW_PATH}")
    return 0
