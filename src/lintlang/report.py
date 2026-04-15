"""Report generation — human-readable diagnostic output.

Supports:
- Terminal (colored, rich formatting with verdict + findings)
- Markdown (for export/sharing)

v0.2.0: Replaced numeric HERM score with PASS/REVIEW/FAIL verdict
based on structural findings severity.
"""

from __future__ import annotations

import re

from . import __version__
from .patterns import Finding, Severity
from .scanner import ScanResult

_ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")


def _ansi_len(s: str) -> int:
    """Return the visible length of a string, ignoring ANSI escape codes."""
    return len(_ANSI_ESCAPE.sub("", s))

# ── ANSI Colors ────────────────────────────────────────────────────

COLORS = {
    Severity.CRITICAL: "\033[91m",  # bright red
    Severity.HIGH: "\033[31m",      # red
    Severity.MEDIUM: "\033[33m",    # yellow
    Severity.LOW: "\033[36m",       # cyan
    Severity.INFO: "\033[90m",      # gray
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BRIGHT_RED = "\033[91m"


def _severity_icon(severity: Severity) -> str:
    return {
        Severity.CRITICAL: "!!",
        Severity.HIGH: "!",
        Severity.MEDIUM: "~",
        Severity.LOW: "-",
        Severity.INFO: ".",
    }[severity]


def compute_verdict(findings: list[Finding]) -> str:
    """Compute PASS/REVIEW/FAIL verdict from structural findings.

    - FAIL: any CRITICAL or HIGH finding
    - REVIEW: any MEDIUM finding (no CRITICAL/HIGH)
    - PASS: only LOW/INFO findings or none
    """
    for f in findings:
        if f.severity in (Severity.CRITICAL, Severity.HIGH):
            return "FAIL"
    for f in findings:
        if f.severity == Severity.MEDIUM:
            return "REVIEW"
    return "PASS"


def _verdict_display(verdict: str) -> tuple[str, str]:
    """Return (icon, color) for a verdict."""
    if verdict == "PASS":
        return "✅", GREEN
    elif verdict == "REVIEW":
        return "⚠️", YELLOW
    else:
        return "❌", BRIGHT_RED


def _severity_summary(findings: list[Finding]) -> str:
    """Build a compact severity count string like '2 CRITICAL, 1 HIGH, 3 MEDIUM'."""
    counts: dict[Severity, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    parts = []
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        if sev in counts:
            parts.append(f"{counts[sev]} {sev.value.upper()}")
    return ", ".join(parts) if parts else "0 findings"


# ── Terminal Report ────────────────────────────────────────────────


def format_terminal(
    result: ScanResult,
    show_suggestions: bool = True,
) -> str:
    """Format a ScanResult for terminal output with ANSI colors."""
    lines: list[str] = []
    findings = result.structural_findings
    verdict = compute_verdict(findings)
    icon, vcolor = _verdict_display(verdict)

    # Header
    lines.append("")
    lines.append(f"{BOLD}  LINTLANG v{__version__}{RESET}")
    if result.file:
        lines.append(f"  {DIM}{result.file}{RESET}")
    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append("")

    # Verdict
    lines.append(f"  {icon} {BOLD}{vcolor}{verdict}{RESET} — {_severity_summary(findings)}")
    lines.append("")

    # Structural findings (H1-H7) — the main output
    if findings:
        by_pattern: dict[str, list[Finding]] = {}
        for f in findings:
            by_pattern.setdefault(f.pattern_id, []).append(f)

        for pid in sorted(by_pattern.keys()):
            pattern_findings = by_pattern[pid]
            pattern_name = pattern_findings[0].pattern_name
            lines.append(f"  {BOLD}{pid}: {pattern_name}{RESET}")
            lines.append("")

            for f in pattern_findings:
                color = COLORS[f.severity]
                icon_f = _severity_icon(f.severity)
                lines.append(f"    {color}{icon_f} [{f.severity.value.upper()}]{RESET} {f.location}")
                lines.append(f"      {f.description}")
                if f.evidence:
                    lines.append(f"      {DIM}Evidence: \"{f.evidence}\"{RESET}")
                if show_suggestions:
                    lines.append(f"      {DIM}→ {f.suggestion}{RESET}")
                lines.append("")
    else:
        lines.append(f"  {GREEN}No structural issues found.{RESET}")
        lines.append("")

    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append(f"  {DIM}lintlang v{__version__} | H1-H7 structural analysis | Zero LLM calls{RESET}")
    lines.append("")

    return "\n".join(lines)


# ── Markdown Report ────────────────────────────────────────────────


def format_markdown(
    result: ScanResult,
    show_suggestions: bool = True,
) -> str:
    """Format a ScanResult as a Markdown document."""
    lines: list[str] = []
    findings = result.structural_findings
    verdict = compute_verdict(findings)

    if verdict == "PASS":
        verdict_md = "✅ **PASS**"
    elif verdict == "REVIEW":
        verdict_md = "⚠️ **REVIEW**"
    else:
        verdict_md = "❌ **FAIL**"

    lines.append("# Lintlang Report")
    lines.append("")
    if result.file:
        lines.append(f"**Source:** `{result.file}`")
        lines.append("")

    # Verdict
    lines.append(f"**Verdict:** {verdict_md} — {_severity_summary(findings)}")
    lines.append("")

    # Structural findings
    if findings:
        lines.append("## Findings")
        lines.append("")

        by_pattern: dict[str, list[Finding]] = {}
        for f in findings:
            by_pattern.setdefault(f.pattern_id, []).append(f)

        for pid in sorted(by_pattern.keys()):
            pattern_findings = by_pattern[pid]
            pattern_name = pattern_findings[0].pattern_name
            lines.append(f"### {pid}: {pattern_name}")
            lines.append("")

            for f in pattern_findings:
                severity_badge = f"**[{f.severity.value.upper()}]**"
                lines.append(f"#### {severity_badge} `{f.location}`")
                lines.append("")
                lines.append(f"{f.description}")
                lines.append("")
                if f.evidence:
                    lines.append(f"> Evidence: *\"{f.evidence}\"*")
                    lines.append("")
                if show_suggestions:
                    lines.append(f"**Fix:** {f.suggestion}")
                    lines.append("")
    else:
        lines.append("No structural issues found.")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by lintlang v{__version__} — H1-H7 structural analysis, zero LLM calls*")

    return "\n".join(lines)


# ── Summary Table ─────────────────────────────────────────────────


def _findings_compact(findings: list[Finding]) -> str:
    """Build compact findings summary like '2 high, 3 medium, 1 low'."""
    counts: dict[str, int] = {}
    for f in findings:
        key = f.severity.value.lower()
        counts[key] = counts.get(key, 0) + 1

    parts = []
    for sev in ["critical", "high", "medium", "low", "info"]:
        if sev in counts:
            parts.append(f"{counts[sev]} {sev}")
    return ", ".join(parts) if parts else "clean"


def _verdict_short(verdict: str) -> tuple[str, str]:
    """Return (display_text, color) for summary table verdict column."""
    if verdict == "PASS":
        return "\u2705 PASS", GREEN
    elif verdict == "REVIEW":
        return "\u26a0\ufe0f  REV", YELLOW
    else:
        return "\u274c FAIL", BRIGHT_RED


def format_summary_table(results: dict[str, ScanResult], elapsed: float) -> str:
    """Format a summary table for multi-file scans.

    Only produced when more than one file was scanned.
    """
    if len(results) <= 1:
        return ""

    rows: list[tuple[str, str, str, str]] = []  # (file, verdict, color, findings)
    verdict_counts = {"PASS": 0, "REVIEW": 0, "FAIL": 0}

    for fpath, result in results.items():
        verdict = compute_verdict(result.structural_findings)
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        display, color = _verdict_short(verdict)
        findings_str = _findings_compact(result.structural_findings)
        rows.append((fpath, display, color, findings_str))

    # Column widths
    col_file = max(len(r[0]) for r in rows)
    col_file = max(col_file, 36)  # minimum width
    col_verdict = 10
    col_findings = max(len(r[3]) for r in rows)
    col_findings = max(col_findings, 23)

    # Also need room for footer text
    n_files = len(results)
    footer_file = f"{n_files} files scanned in {elapsed:.2f}s"
    col_file = max(col_file, len(footer_file))

    lines: list[str] = []
    lines.append("")
    lines.append(f"  {BOLD}SUMMARY{RESET}")
    lines.append("")

    # Top border
    lines.append(f"  \u250c{'─' * (col_file + 2)}\u252c{'─' * (col_verdict + 2)}\u252c{'─' * (col_findings + 2)}\u2510")
    # Header row
    lines.append(
        f"  \u2502 {BOLD}{'File':<{col_file}}{RESET} "
        f"\u2502 {BOLD}{'Verdict':<{col_verdict}}{RESET} "
        f"\u2502 {BOLD}{'Findings':<{col_findings}}{RESET} \u2502"
    )
    # Header separator
    lines.append(f"  \u251c{'─' * (col_file + 2)}\u253c{'─' * (col_verdict + 2)}\u253c{'─' * (col_findings + 2)}\u2524")

    # Data rows
    for fpath, display, color, findings_str in rows:
        lines.append(
            f"  \u2502 {fpath:<{col_file}} "
            f"\u2502 {color}{display}{RESET}{' ' * (col_verdict - len(display))} "
            f"\u2502 {findings_str:<{col_findings}} \u2502"
        )

    # Footer separator
    lines.append(f"  \u251c{'─' * (col_file + 2)}\u253c{'─' * (col_verdict + 2)}\u253c{'─' * (col_findings + 2)}\u2524")

    # Footer rows
    pass_str = f"{GREEN}{verdict_counts['PASS']} PASS{RESET}"
    rev_str = f"{YELLOW}{verdict_counts['REVIEW']} REV{RESET}"
    fail_str = f"{BRIGHT_RED}{verdict_counts['FAIL']} FAIL{RESET}"

    # Row 1: file count + PASS + cost
    cost_str = "$0.00 | 0 LLM calls"
    lines.append(
        f"  \u2502 {footer_file:<{col_file}} "
        f"\u2502 {pass_str}{' ' * (col_verdict - _ansi_len(pass_str))} "
        f"\u2502 {cost_str:<{col_findings}} \u2502"
    )
    # Row 2: blank + REV + blank
    lines.append(
        f"  \u2502 {'':<{col_file}} "
        f"\u2502 {rev_str}{' ' * (col_verdict - _ansi_len(rev_str))} "
        f"\u2502 {'':<{col_findings}} \u2502"
    )
    # Row 3: blank + FAIL + blank
    lines.append(
        f"  \u2502 {'':<{col_file}} "
        f"\u2502 {fail_str}{' ' * (col_verdict - _ansi_len(fail_str))} "
        f"\u2502 {'':<{col_findings}} \u2502"
    )

    # Bottom border
    lines.append(f"  \u2514{'─' * (col_file + 2)}\u2534{'─' * (col_verdict + 2)}\u2534{'─' * (col_findings + 2)}\u2518")
    lines.append("")

    return "\n".join(lines)
