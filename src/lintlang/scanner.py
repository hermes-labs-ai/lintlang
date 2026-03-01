"""Core scanning engine — HERM v1.1 hermeneutical scoring + structural detectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .herm import HermResult, score_text
from .parsers import parse_file
from .patterns import PATTERNS, AgentConfig, Finding


@dataclass
class ScanResult:
    """Combined HERM score + structural findings for a file."""
    file: str
    score: float                                    # HERM hermeneutical score (0-100)
    herm: HermResult                                # Full HERM result
    structural_findings: list[Finding] = field(default_factory=list)


def _build_scoring_text(config: AgentConfig) -> str:
    """Assemble text corpus for HERM scoring from parsed AgentConfig."""
    parts: list[str] = []
    if config.system_prompt:
        parts.append(config.system_prompt)
    for tool in config.tools:
        if tool.description:
            parts.append(tool.description)
    for msg in config.messages:
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            parts.append(content)
    return "\n\n".join(parts)


def scan_config(
    config: AgentConfig,
    patterns: list[str] | None = None,
) -> ScanResult:
    """Score a config with HERM v1.1 + run structural detectors.

    Args:
        config: Normalized agent configuration.
        patterns: Optional list of structural pattern IDs (H1-H7).

    Returns:
        ScanResult with HERM score and structural findings.
    """
    # HERM scoring on assembled text
    text = _build_scoring_text(config)
    herm = score_text(text, source_path=config.source_file)

    # Structural detectors (H1-H7) as supplementary findings
    structural: list[Finding] = []
    pattern_ids = patterns or list(PATTERNS.keys())
    for pid in pattern_ids:
        if pid not in PATTERNS:
            continue
        detector = PATTERNS[pid]["detect"]
        structural.extend(detector(config))

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    structural.sort(key=lambda f: severity_order.get(f.severity.value, 5))

    return ScanResult(
        file=config.source_file,
        score=herm.score,
        herm=herm,
        structural_findings=structural,
    )


def scan_file(path: str | Path, patterns: list[str] | None = None) -> ScanResult:
    """Parse a file and produce a full scan result.

    Uses HERM v1.1 as the primary scorer with structural detectors
    (H1-H7) providing supplementary findings.
    """
    config = parse_file(path)
    return scan_config(config, patterns=patterns)


def scan_directory(
    directory: str | Path,
    patterns: list[str] | None = None,
    extensions: tuple[str, ...] = (".yaml", ".yml", ".json", ".txt", ".prompt"),
) -> dict[str, ScanResult]:
    """Scan all matching files in a directory.

    Returns:
        Dict mapping file paths to ScanResults.
    """
    directory = Path(directory)
    results: dict[str, ScanResult] = {}

    for ext in extensions:
        for filepath in directory.rglob(f"*{ext}"):
            try:
                results[str(filepath)] = scan_file(filepath, patterns=patterns)
            except Exception as e:
                from .patterns import Severity as _Severity
                herm = score_text("", source_path=str(filepath))
                results[str(filepath)] = ScanResult(
                    file=str(filepath),
                    score=herm.score,
                    herm=herm,
                    structural_findings=[Finding(
                        pattern_id="ERR",
                        pattern_name="Parse Error",
                        severity=_Severity.INFO,
                        location=str(filepath),
                        description=f"Failed to parse: {e}",
                        suggestion="Check file format (YAML, JSON, or plain text).",
                    )],
                )

    return results


def compute_health_score(findings: list[Finding]) -> float:
    """Legacy penalty-based scorer. Kept for backward compatibility.

    For new code, use scan_file().score (HERM v1.1) instead.
    """
    if not findings:
        return 100.0
    total_penalty = sum(f.severity.score for f in findings)
    capped = min(total_penalty, 100)
    return max(0.0, 100.0 - capped)
