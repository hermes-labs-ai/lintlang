"""Report generation — human-readable diagnostic output.

Supports:
- Terminal (colored, rich formatting with verdict + findings)
- Markdown (for export/sharing)

v0.2.0: Replaced numeric HERM score with PASS/REVIEW/FAIL verdict
based on structural findings severity.
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
