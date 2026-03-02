"""Report generation — human-readable diagnostic output.

Supports:
- Terminal (colored, rich formatting with HERM dimensions)
- Markdown (for export/sharing)
"""

from __future__ import annotations

from . import __version__
from .patterns import Finding, Severity
from .scanner import ScanResult

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


def _score_color(score: float) -> str:
    if score >= 90:
        return "\033[32m"   # green
    elif score >= 70:
        return "\033[33m"   # yellow
    else:
        return "\033[31m"   # red


def _bar(value: float, width: int = 10) -> str:
    """Render a simple bar chart: filled + empty blocks."""
    filled = max(0, min(width, round(value / 100 * width)))
    return "\u2588" * filled + "\u2591" * (width - filled)


# ── Terminal Report ────────────────────────────────────────────────


def format_terminal(
    result: ScanResult,
    show_suggestions: bool = True,
) -> str:
    """Format a ScanResult for terminal output with ANSI colors."""
    lines: list[str] = []
    herm = result.herm

    # Header
    lines.append("")
    lines.append(f"{BOLD}  LINTLANG REPORT (HERM v1.1){RESET}")
    if result.file:
        lines.append(f"  {DIM}{result.file}{RESET}")
    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append("")

    # HERM dimensions
    lines.append(f"  {BOLD}Hermeneutical Dimensions{RESET}")
    for dim_name, dim_score in herm.dimension_scores.items():
        color = _score_color(dim_score)
        bar = _bar(dim_score)
        # Truncate dimension name for alignment
        short = dim_name.split(" ", 1)[1] if " " in dim_name else dim_name
        lines.append(f"    {dim_name.split(' ')[0]} {short[:32]:<32s} {color}{bar}{RESET}  {dim_score:5.1f}")
    lines.append("")

    # Coverage + confidence
    cov_pct = f"{herm.coverage * 100:.0f}%"
    lines.append(f"  Coverage: {cov_pct}  |  Confidence: {herm.confidence}")
    lines.append("")

    # HERM findings
    if herm.findings:
        lines.append(f"  {BOLD}Signals{RESET}")
        for finding in herm.findings:
            lines.append(f"    {DIM}- {finding}{RESET}")
        lines.append("")

    # Structural findings (H1-H7)
    findings = result.structural_findings
    if findings:
        counts: dict[Severity, int] = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        summary_parts = []
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            if sev in counts:
                color = COLORS[sev]
                summary_parts.append(f"{color}{counts[sev]} {sev.value}{RESET}")

        lines.append(f"  {BOLD}Structural Issues{RESET}  ({', '.join(summary_parts)})")
        lines.append("")

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

    # Score
    sc = _score_color(result.score)
    lines.append(f"  {DIM}{'─' * 50}{RESET}")
    lines.append(f"  HERM Score: {BOLD}{sc}{result.score:.1f}/100{RESET}")
    lines.append("")

    return "\n".join(lines)


# ── Markdown Report ────────────────────────────────────────────────


def format_markdown(
    result: ScanResult,
    show_suggestions: bool = True,
) -> str:
    """Format a ScanResult as a Markdown document."""
    lines: list[str] = []
    herm = result.herm

    lines.append("# Lintlang Report (HERM v1.1)")
    lines.append("")
    if result.file:
        lines.append(f"**Source:** `{result.file}`")
        lines.append("")

    # Score
    lines.append(f"**HERM Score: {result.score:.1f}/100** | Coverage: {herm.coverage * 100:.0f}% | Confidence: {herm.confidence}")
    lines.append("")

    # Dimensions table
    lines.append("## Hermeneutical Dimensions")
    lines.append("")
    lines.append("| Dimension | Score |")
    lines.append("|-----------|-------|")
    for dim_name, dim_score in herm.dimension_scores.items():
        lines.append(f"| {dim_name} | {dim_score:.1f} |")
    lines.append("")

    # Signals
    if herm.findings:
        lines.append("## Signals")
        lines.append("")
        for finding in herm.findings:
            lines.append(f"- {finding}")
        lines.append("")

    # Structural findings
    findings = result.structural_findings
    if findings:
        lines.append("## Structural Issues")
        lines.append("")

        counts: dict[Severity, int] = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            if sev in counts:
                lines.append(f"| {sev.value.upper()} | {counts[sev]} |")
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

    lines.append("---")
    lines.append(f"*Generated by lintlang v{__version__} (HERM v1.1)*")

    return "\n".join(lines)
