"""Core scanning engine — runs all pattern detectors against an AgentConfig."""

from __future__ import annotations

from pathlib import Path

from .parsers import parse_file
from .patterns import AgentConfig, Finding, PATTERNS


def scan_config(config: AgentConfig, patterns: list[str] | None = None) -> list[Finding]:
    """Run all (or selected) pattern detectors against a config.

    Args:
        config: The normalized agent configuration to scan.
        patterns: Optional list of pattern IDs to run (e.g., ["H1", "H3"]).
                  If None, runs all patterns.

    Returns:
        List of findings sorted by severity (critical first).
    """
    findings: list[Finding] = []
    pattern_ids = patterns or list(PATTERNS.keys())

    for pid in pattern_ids:
        if pid not in PATTERNS:
            continue
        detector = PATTERNS[pid]["detect"]
        findings.extend(detector(config))

    # Sort: critical first, then high, medium, low, info
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: severity_order.get(f.severity.value, 5))

    return findings


def scan_file(path: str | Path, patterns: list[str] | None = None) -> list[Finding]:
    """Parse a file and scan it for pattern violations.

    Args:
        path: Path to agent config file (YAML, JSON, or text).
        patterns: Optional list of pattern IDs to check.

    Returns:
        List of findings.
    """
    config = parse_file(path)
    return scan_config(config, patterns=patterns)


def scan_directory(
    directory: str | Path,
    patterns: list[str] | None = None,
    extensions: tuple[str, ...] = (".yaml", ".yml", ".json", ".txt", ".prompt"),
) -> dict[str, list[Finding]]:
    """Scan all matching files in a directory.

    Returns:
        Dict mapping file paths to their findings.
    """
    directory = Path(directory)
    results: dict[str, list[Finding]] = {}

    for ext in extensions:
        for filepath in directory.rglob(f"*{ext}"):
            try:
                findings = scan_file(filepath, patterns=patterns)
                if findings:
                    results[str(filepath)] = findings
            except Exception as e:
                results[str(filepath)] = [Finding(
                    pattern_id="ERR",
                    pattern_name="Parse Error",
                    severity=findings[0].severity if findings else __import__("lingdiag.patterns", fromlist=["Severity"]).Severity.INFO,
                    location=str(filepath),
                    description=f"Failed to parse: {e}",
                    suggestion="Check file format (YAML, JSON, or plain text).",
                )]

    return results


def compute_health_score(findings: list[Finding]) -> float:
    """Compute a 0-100 health score based on findings.

    100 = no issues, 0 = maximum severity issues.
    """
    if not findings:
        return 100.0

    total_penalty = sum(f.severity.score for f in findings)
    # Cap at 100 penalty points
    capped = min(total_penalty, 100)
    return max(0.0, 100.0 - capped)
