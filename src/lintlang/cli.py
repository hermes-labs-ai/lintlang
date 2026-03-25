"""CLI entry point for lintlang."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .parsers import parse_file
from .patterns import PATTERNS as _PATTERNS
from .report import compute_verdict, format_markdown, format_terminal
from .scanner import ScanResult, scan_config, scan_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lintlang",
        description="Linguistic linter for AI agent systems. H1-H7 structural analysis with PASS/REVIEW/FAIL verdicts.",
    )
    parser.add_argument("--version", action="version", version=f"lintlang {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # ── scan command ───────────────────────────────────────────────
    scan_parser = subparsers.add_parser("scan", help="Scan agent config files for linguistic issues")
    scan_parser.add_argument("files", nargs="+", help="Config files to scan (YAML, JSON, or text)")
    scan_parser.add_argument(
        "--patterns", "-p",
        nargs="+",
        choices=sorted(_PATTERNS.keys()),
        help="Only check specific structural patterns (default: all)",
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
        help="Minimum severity for structural findings (default: info)",
    )
    scan_parser.add_argument(
        "--fail-under",
        type=float,
        default=0.0,
        help="Exit with code 1 if HERM score is below this threshold (legacy; prefer --fail-on)",
    )
    scan_parser.add_argument(
        "--fail-on",
        choices=["fail", "review"],
        default=None,
        help="Exit with code 1 on verdict: 'fail' (any CRITICAL/HIGH) or 'review' (any MEDIUM+). Default: no exit on verdict.",
    )

    # ── patterns command ───────────────────────────────────────────
    subparsers.add_parser("patterns", help="List all diagnostic patterns")

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
    print("  STRUCTURAL DETECTORS (H1-H7)")
    print("  " + "─" * 50)
    for pid, info in sorted(PATTERNS.items()):
        print(f"  {pid}: {info['name']}")

    print()
    print("  Use 'lintlang scan --patterns H1 H3' to filter structural checks.")
    print()
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    """Scan files with H1-H7 structural detectors."""
    import json as json_mod

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    min_sev = severity_order.get(args.min_severity, 4)

    results: dict[str, ScanResult] = {}

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            continue

        if path.is_dir():
            dir_results = scan_directory(path, patterns=args.patterns)
            for fpath, result in dir_results.items():
                result.structural_findings = [
                    f for f in result.structural_findings
                    if severity_order.get(f.severity.value, 4) <= min_sev
                ]
                results[fpath] = result
            continue

        try:
            config = parse_file(path)
            result = scan_config(config, patterns=args.patterns)
            result.structural_findings = [
                f for f in result.structural_findings
                if severity_order.get(f.severity.value, 4) <= min_sev
            ]
            results[str(path)] = result
        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            continue

    # Output
    if args.format == "terminal":
        for result in results.values():
            print(format_terminal(result, show_suggestions=not args.no_suggestions))
    elif args.format == "markdown":
        for result in results.values():
            print(format_markdown(result, show_suggestions=not args.no_suggestions))
    elif args.format == "json":
        output = []
        for result in results.values():
            verdict = compute_verdict(result.structural_findings)
            output.append({
                "file": result.file,
                "verdict": verdict,
                "structural_findings": [
                    {
                        "pattern_id": f.pattern_id,
                        "pattern_name": f.pattern_name,
                        "severity": f.severity.value,
                        "location": f.location,
                        "description": f.description,
                        "suggestion": f.suggestion,
                        "evidence": f.evidence,
                    }
                    for f in result.structural_findings
                ],
                # Raw HERM data preserved for programmatic consumers
                "herm": {
                    "score": result.score,
                    "dimensions": result.herm.dimension_scores,
                    "signal_counts": result.herm.signal_counts,
                    "coverage": result.herm.coverage,
                    "confidence": result.herm.confidence,
                    "findings": result.herm.findings,
                    "context_flags": result.herm.context_flags,
                },
            })
        print(json_mod.dumps(output, indent=2))

    if not results:
        print("Error: No files were successfully scanned.", file=sys.stderr)
        return 1

    # Verdict-based exit
    if args.fail_on:
        verdicts = [compute_verdict(r.structural_findings) for r in results.values()]
        if args.fail_on == "fail" and "FAIL" in verdicts:
            worst = next(r for r in results.values() if compute_verdict(r.structural_findings) == "FAIL")
            print(f"\nVerdict: FAIL — {worst.file} has CRITICAL/HIGH findings", file=sys.stderr)
            return 1
        if args.fail_on == "review" and any(v in ("FAIL", "REVIEW") for v in verdicts):
            print("\nVerdict: issues found — use --min-severity to filter", file=sys.stderr)
            return 1

    # Legacy --fail-under support (HERM score threshold)
    if args.fail_under > 0:
        min_score = min(r.score for r in results.values())
        if min_score < args.fail_under:
            print(f"\nHERM score {min_score:.1f} is below threshold {args.fail_under:.1f}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
