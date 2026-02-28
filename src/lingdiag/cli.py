"""CLI entry point for lingdiag."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .parsers import parse_file
from .scanner import scan_config, compute_health_score
from .report import format_terminal, format_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lingdiag",
        description="Linguistic diagnostics for AI agent systems. Scans tool descriptions, system prompts, and agent configs for H1-H7 failure patterns.",
    )
    parser.add_argument("--version", action="version", version=f"lingdiag {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # ── scan command ───────────────────────────────────────────────
    scan_parser = subparsers.add_parser("scan", help="Scan agent config files for linguistic issues")
    scan_parser.add_argument("files", nargs="+", help="Config files to scan (YAML, JSON, or text)")
    scan_parser.add_argument(
        "--patterns", "-p",
        nargs="+",
        choices=["H1", "H2", "H3", "H4", "H5", "H6", "H7"],
        help="Only check specific patterns (default: all)",
    )
    scan_parser.add_argument(
        "--format", "-f",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    scan_parser.add_argument(
        "--no-suggestions",
        action="store_true",
        help="Hide fix suggestions",
    )
    scan_parser.add_argument(
        "--min-severity",
        choices=["critical", "high", "medium", "low", "info"],
        default="info",
        help="Minimum severity to show (default: info)",
    )
    scan_parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="Exit with code 1 if health score is below this threshold (default: 0)",
    )

    # ── patterns command ───────────────────────────────────────────
    patterns_parser = subparsers.add_parser("patterns", help="List all diagnostic patterns")

    args = parser.parse_args(argv)

    if args.command == "patterns":
        return _cmd_patterns()
    elif args.command == "scan":
        return _cmd_scan(args)
    else:
        parser.print_help()
        return 0


def _cmd_patterns() -> int:
    """List all diagnostic patterns."""
    from .patterns import PATTERNS

    print()
    print("  LINGUISTIC DIAGNOSTIC PATTERNS")
    print("  " + "─" * 50)
    print()

    for pid, info in sorted(PATTERNS.items()):
        print(f"  {pid}: {info['name']}")

    print()
    print("  Use 'lingdiag scan --patterns H1 H3' to check specific patterns.")
    print()
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    """Scan files for linguistic issues."""
    import json as json_mod
    from .patterns import Severity

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    min_sev = severity_order.get(args.min_severity, 4)

    all_findings = []
    file_findings: dict[str, list] = {}

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            continue

        try:
            config = parse_file(path)
            findings = scan_config(config, patterns=args.patterns)
            # Filter by severity
            findings = [f for f in findings if severity_order.get(f.severity.value, 4) <= min_sev]
            all_findings.extend(findings)
            file_findings[str(path)] = findings
        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            continue

    # Output
    if args.format == "terminal":
        for filepath, findings in file_findings.items():
            print(format_terminal(findings, source_file=filepath, show_suggestions=not args.no_suggestions))
    elif args.format == "markdown":
        for filepath, findings in file_findings.items():
            print(format_markdown(findings, source_file=filepath, show_suggestions=not args.no_suggestions))
    elif args.format == "json":
        output = []
        for filepath, findings in file_findings.items():
            output.append({
                "file": filepath,
                "health_score": compute_health_score(findings),
                "findings": [
                    {
                        "pattern_id": f.pattern_id,
                        "pattern_name": f.pattern_name,
                        "severity": f.severity.value,
                        "location": f.location,
                        "description": f.description,
                        "suggestion": f.suggestion,
                        "evidence": f.evidence,
                    }
                    for f in findings
                ],
            })
        print(json_mod.dumps(output, indent=2))

    # Health score check
    overall_score = compute_health_score(all_findings)
    if args.fail_under > 0 and overall_score < args.fail_under:
        print(f"\nHealth score {overall_score:.0f} is below threshold {args.fail_under:.0f}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
