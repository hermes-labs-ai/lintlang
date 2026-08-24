"""CLI entry point for lintlang."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .github_init import configure_init_parser, run_init
from .patterns import PATTERNS as _PATTERNS
from .preflight_cli import configure_preflight_parser, run_preflight
from .report import compute_verdict, format_markdown, format_summary_table, format_terminal
from .scanner import ScanResult, input_error_result, scan_directory, scan_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lintlang",
        description="Linguistic linter for AI agent systems. H1-H7 structural analysis with PASS/REVIEW/FAIL verdicts.",
    )
    parser.add_argument("--version", action="version", version=f"lintlang {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # ── scan command ───────────────────────────────────────────────
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan agent configs and embedded language in Python pipelines",
    )
    scan_parser.add_argument(
        "files",
        nargs="+",
        help=(
            "Language-bearing inputs: YAML, JSON, text, or Python "
            "(.py uses AST extraction for embedded prompts/pipeline artifacts; "
            "not general Python code linting)"
        ),
    )
    scan_parser.add_argument(
        "--patterns",
        "-p",
        nargs="+",
        choices=sorted(_PATTERNS.keys()),
        help="Only check specific structural patterns (default: all)",
    )
    scan_parser.add_argument(
        "--format",
        "-f",
        choices=["terminal", "markdown", "json", "sarif"],
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
        help="Exit with code 1 if quality score is below this threshold (legacy; prefer --fail-on)",
    )
    scan_parser.add_argument(
        "--fail-on",
        choices=["fail", "review"],
        default=None,
        help="Exit with code 1 on verdict: 'fail' (any CRITICAL/HIGH) or 'review' (any MEDIUM+). Default: no exit on verdict.",
    )
    scan_parser.add_argument(
        "--exclude",
        nargs="+",
        default=None,
        help="Glob patterns to exclude (e.g., 'CHANGELOG.md' 'docs/**'). Non-prompt files (README, LICENSE, etc.) are skipped automatically.",
    )
    # ── patterns command ───────────────────────────────────────────
    subparsers.add_parser("patterns", help="List all diagnostic patterns")
    configure_init_parser(subparsers)
    # Preflight is a separate provider-neutral surface; it does not alter the
    # scan parser, structural verdicts, or existing exit behavior.
    configure_preflight_parser(subparsers)

    args = parser.parse_args(argv)

    if args.command == "patterns":
        return _cmd_patterns()
    elif args.command == "scan":
        return _cmd_scan(args)
    elif args.command == "preflight":
        return run_preflight(args)
    elif args.command == "init":
        return run_init(args)
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
    import time

    t_start = time.monotonic()

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    min_sev = severity_order.get(args.min_severity, 4)

    results: dict[str, ScanResult] = {}

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            results[str(path)] = input_error_result(path, "File not found")
            continue

        if path.is_dir():
            dir_results = scan_directory(
                path,
                patterns=args.patterns,
                exclude=args.exclude,
            )
            for fpath, result in dir_results.items():
                result.structural_findings = [
                    f for f in result.structural_findings if severity_order.get(f.severity.value, 4) <= min_sev
                ]
                results[fpath] = result
            continue

        try:
            result = scan_file(path, patterns=args.patterns)
            result.structural_findings = [
                f for f in result.structural_findings if severity_order.get(f.severity.value, 4) <= min_sev
            ]
            results[str(path)] = result
        except Exception as e:
            results[str(path)] = input_error_result(path, f"Failed to parse: {e}")

    input_errors = [result for result in results.values() if result.input_error is not None]
    sarif_output_errors: list[str] = []

    if args.format != "sarif":
        for result in input_errors:
            print(f"Error: Input error: {result.file}: {result.input_error}", file=sys.stderr)

    # Output
    if args.format == "terminal":
        for result in results.values():
            print(format_terminal(result, show_suggestions=not args.no_suggestions))
    elif args.format == "markdown":
        for result in results.values():
            if result.input_error:
                print(f"# Lintlang Input Error\n\n- **File:** `{result.file}`\n- **Error:** {result.input_error}\n")
            else:
                print(format_markdown(result, show_suggestions=not args.no_suggestions))
    elif args.format == "json":
        output = []
        for result in results.values():
            verdict = compute_verdict(result)
            output.append(
                {
                    "file": result.file,
                    "verdict": verdict,
                    "input_error": result.input_error,
                    "structural_findings": [
                        {
                            "pattern_id": f.pattern_id,
                            # The most specific stable identifier — "H1.6" when
                            # the finding is sub-coded, "H1" otherwise. Cite this.
                            "code": f.code,
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
                    "herm": None
                    if result.input_error
                    else {
                        "score": result.score,
                        "dimensions": result.herm.dimension_scores,
                        "signal_counts": result.herm.signal_counts,
                        "coverage": result.herm.coverage,
                        "confidence": result.herm.confidence,
                        "findings": result.herm.findings,
                        "context_flags": result.herm.context_flags,
                    },
                }
            )
        print(json_mod.dumps(output, indent=2))
    elif args.format == "sarif":
        from .sarif import (
            SarifLocationError,
            find_repository_root,
            format_sarif,
            format_sarif_error,
            prepare_sarif_results,
        )

        invocation_root = Path.cwd()
        repository_root = find_repository_root(invocation_root)
        sarif_results, sarif_output_errors = prepare_sarif_results(
            results,
            repository_root=repository_root,
            source_base=invocation_root,
        )
        for error in sarif_output_errors:
            print(f"Error: SARIF output error: {error}", file=sys.stderr)
        try:
            print(
                format_sarif(
                    sarif_results,
                    repository_root=repository_root,
                    source_base=invocation_root,
                    show_suggestions=not args.no_suggestions,
                ),
                end="",
            )
        except SarifLocationError as error:
            print(f"Error: SARIF output error: {error}", file=sys.stderr)
            print(format_sarif_error(str(error)), end="")
            return 1

    # Summary table for multi-file terminal scans
    if args.format == "terminal" and len(results) > 1:
        elapsed = time.monotonic() - t_start
        print(format_summary_table(results, elapsed))

    if not results:
        print("Error: No files were successfully scanned.", file=sys.stderr)
        return 1

    # Input integrity is a fatal channel, independent of lint severity and
    # --fail-on. Never let another valid input mask a requested input error.
    if input_errors or sarif_output_errors:
        return 1

    # Verdict-based exit
    if args.fail_on:
        verdicts = [compute_verdict(r) for r in results.values()]
        if args.fail_on == "fail" and "FAIL" in verdicts:
            worst = next(r for r in results.values() if compute_verdict(r) == "FAIL")
            print(f"\nVerdict: FAIL — {worst.file} has CRITICAL/HIGH findings", file=sys.stderr)
            return 1
        if args.fail_on == "review" and any(v in ("FAIL", "REVIEW") for v in verdicts):
            print("\nVerdict: issues found — use --min-severity to filter", file=sys.stderr)
            return 1

    # Legacy --fail-under support (quality score threshold)
    if args.fail_under > 0:
        min_score = min(r.score for r in results.values())
        if min_score < args.fail_under:
            print(f"\nQuality score {min_score:.1f} is below threshold {args.fail_under:.1f}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
