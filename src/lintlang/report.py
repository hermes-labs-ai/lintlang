"""Report generation — human-readable diagnostic output.

Supports:
- Terminal (colored, rich formatting)
- Markdown (for export/sharing)
"""

from __future__ import annotations

from . import __version__
from .patterns import Finding, Severity
from .scanner import compute_health_score


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


def _severity_icon(severity: Severity) -> str:
    return {
        Severity.CRITICAL: "!!",
        Severity.HIGH: "!",
        Severity.MEDIUM: "~",
        Severity.LOW: "-",
        Severity.INFO: ".",
    }[severity]


# ── Terminal Report ────────────────────────────────────────────────


def format_terminal(
    findings: list[Finding],
    source_file: str = "",
    show_suggestions: bool = True,
) -> str:
    """Format findings for terminal output with ANSI colors."""
    lines: list[str] = []

    # Header
    lines.append("")
    lines.append(f"{BOLD}  LINGUISTIC DIAGNOSTICS REPORT{RESET}")
    if source_file:
        lines.append(f"  {DIM}{source_file}{RESET}")
    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append("")

    if not findings:
        lines.append(f"  {BOLD}\033[32mNo issues found.{RESET}")
        lines.append("")
        lines.append(f"  Health Score: {BOLD}100/100{RESET}")
        lines.append("")
        return "\n".join(lines)

    # Summary counts
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    summary_parts = []
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        if sev in counts:
            color = COLORS[sev]
            summary_parts.append(f"{color}{counts[sev]} {sev.value}{RESET}")
    lines.append(f"  Found {len(findings)} issues: {', '.join(summary_parts)}")
    lines.append("")

    # Findings grouped by pattern
    by_pattern: dict[str, list[Finding]] = {}
    for f in findings:
        by_pattern.setdefault(f.pattern_id, []).append(f)

    for pid in sorted(by_pattern.keys()):
        pattern_findings = by_pattern[pid]
        pattern_name = pattern_findings[0].pattern_name
        lines.append(f"  {BOLD}{pid}: {pattern_name}{RESET} ({len(pattern_findings)} findings)")
        lines.append("")

        for f in pattern_findings:
            color = COLORS[f.severity]
            icon = _severity_icon(f.severity)
            lines.append(f"    {color}{icon} [{f.severity.value.upper()}]{RESET} {f.location}")
            lines.append(f"      {f.description}")
            if f.evidence:
                lines.append(f"      {DIM}Evidence: \"{f.evidence}\"{RESET}")
            if show_suggestions:
                lines.append(f"      {DIM}Fix: {f.suggestion}{RESET}")
            lines.append("")

    # Health score
    score = compute_health_score(findings)
    if score >= 80:
        score_color = "\033[32m"  # green
    elif score >= 50:
        score_color = "\033[33m"  # yellow
    else:
        score_color = "\033[31m"  # red

    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append(f"  Health Score: {BOLD}{score_color}{score:.0f}/100{RESET}")
    lines.append("")

    return "\n".join(lines)


# ── Markdown Report ────────────────────────────────────────────────


def format_markdown(
    findings: list[Finding],
    source_file: str = "",
    show_suggestions: bool = True,
) -> str:
    """Format findings as a Markdown document."""
    lines: list[str] = []

    lines.append("# Linguistic Diagnostics Report")
    lines.append("")
    if source_file:
        lines.append(f"**Source:** `{source_file}`")
        lines.append("")

    if not findings:
        lines.append("**No issues found.** Health Score: 100/100")
        return "\n".join(lines)

    # Summary
    score = compute_health_score(findings)
    lines.append(f"**Health Score: {score:.0f}/100** | {len(findings)} findings")
    lines.append("")

    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    summary_parts = []
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        if sev in counts:
            summary_parts.append(f"{counts[sev]} {sev.value}")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        if sev in counts:
            lines.append(f"| {sev.value.upper()} | {counts[sev]} |")
    lines.append("")

    # Findings by pattern
    by_pattern: dict[str, list[Finding]] = {}
    for f in findings:
        by_pattern.setdefault(f.pattern_id, []).append(f)

    for pid in sorted(by_pattern.keys()):
        pattern_findings = by_pattern[pid]
        pattern_name = pattern_findings[0].pattern_name
        lines.append(f"## {pid}: {pattern_name}")
        lines.append("")

        for f in pattern_findings:
            severity_badge = f"**[{f.severity.value.upper()}]**"
            lines.append(f"### {severity_badge} `{f.location}`")
            lines.append("")
            lines.append(f"{f.description}")
            lines.append("")
            if f.evidence:
                lines.append(f"> Evidence: *\"{f.evidence}\"*")
                lines.append("")
            if show_suggestions:
                lines.append(f"**Fix:** {f.suggestion}")
                lines.append("")

    lines.append("---")
    lines.append(f"*Generated by lintlang v{__version__}*")

    return "\n".join(lines)
