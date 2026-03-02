"""HERM v1.1 — Hermeneutical scoring engine.

6 dimensions measuring the linguistic quality of agent configurations:
  HERM-1: Interpretive Ambiguity
  HERM-2: User-Intent Misalignment Risk
  HERM-3: Input-Driven Misinterpretation Surface
  HERM-4: Instruction Conflict/Polysemy
  HERM-5: Pragmatic Drift Risk
  HERM-6: Adversarial Reframing Susceptibility

8 signal categories drive dimension scoring.
Coverage/confidence system avoids false certainty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

DIMENSIONS = [
    "HERM-1 Interpretive Ambiguity",
    "HERM-2 User-Intent Misalignment Risk",
    "HERM-3 Input-Driven Misinterpretation Surface",
    "HERM-4 Instruction Conflict/Polysemy",
    "HERM-5 Pragmatic Drift Risk",
    "HERM-6 Adversarial Reframing Susceptibility",
]

SIGNALS = {
    "ambiguous_qualifiers": [
        r"\bas needed\b", r"\bwhen appropriate\b", r"\bif relevant\b",
        r"\bbest effort\b", r"\breasonable\b", r"\bwhere possible\b",
    ],
    "negative_directives": [
        r"\bdon'?t\b", r"\bdo not\b", r"\bnever\b", r"\bavoid\b",
    ],
    "hijack": [
        r"ignore all previous instructions",
        r"ignore previous instructions",
    ],
    "pressure": [
        r"your job depends on it",
        r"very important to you",
        r"must give your absolute best",
    ],
    "repeat_unbounded": [
        r"repeat\s+N\s*times", r"can\s+repeat", r"repeat\s+indefinitely",
    ],
    "boundary": [
        r"task boundary", r"independent task",
        r"do not carry state", r"new task",
    ],
    "priority": [
        r"priority\s*\d", r"most important",
        r"override", r"when conflict",
    ],
    "input_surface": [
        r"user input", r"user message",
        r"untrusted", r"quoted", r"free-form",
    ],
}


@dataclass
class HermResult:
    """Result from HERM v1.1 scoring."""
    score: float                              # 0-100 final score
    dimension_scores: dict[str, float]        # 6 dimensions, each 0-100
    signal_counts: dict[str, int]             # 8 signal categories
    coverage: float                           # 0.55-1.0
    confidence: str                           # "high", "medium", "low"
    findings: list[str]                       # E1/E2/E3 + structural gap notes
    context_flags: dict[str, bool] = field(default_factory=dict)


def _count_signals(text: str, patterns: list[str]) -> int:
    """Count regex signal matches in text."""
    return sum(len(re.findall(p, text, flags=re.I)) for p in patterns)


def _detect_context(path: str, text: str) -> dict[str, bool]:
    """Detect file context for scoring adjustments."""
    s = path.lower()
    return {
        "is_cassette": "cassettes" in s,
        "is_test": ".test." in s or "/tests/" in s,
        "is_prompt_like": bool(re.search(
            r"you are|system prompt|thought:|action:|observation:",
            text, re.I,
        )),
    }


def score_text(text: str, source_path: str = "") -> HermResult:
    """Score text on HERM v1.1 dimensions.

    Args:
        text: The text to score (system prompt, tool descriptions, etc.)
        source_path: Optional file path for context detection.

    Returns:
        HermResult with score, dimensions, signals, coverage, confidence.
    """
    low = text.lower()
    counts = {k: _count_signals(low, v) for k, v in SIGNALS.items()}
    ctx = _detect_context(source_path, text)

    # Coverage proxy: lower confidence for non-prompt-like files
    coverage = 1.0
    if not ctx["is_prompt_like"]:
        coverage -= 0.25
    if counts["input_surface"] == 0:
        coverage -= 0.10
    coverage = max(0.55, round(coverage, 2))

    # Dimension scoring (0-100 each)
    d: dict[str, float] = {}
    d[DIMENSIONS[0]] = max(0, 100 - (counts["ambiguous_qualifiers"] * 8) - (max(0, counts["negative_directives"] - 3) * 2))
    d[DIMENSIONS[1]] = max(0, 100 - (counts["ambiguous_qualifiers"] * 5) - (0 if counts["priority"] else 12))
    d[DIMENSIONS[2]] = max(0, 100 - (0 if counts["input_surface"] else 10) - (0 if counts["boundary"] else 10))
    d[DIMENSIONS[3]] = max(0, 100 - (max(0, counts["negative_directives"] - 6) * 3) - (0 if counts["priority"] else 8))
    d[DIMENSIONS[4]] = max(0, 100 - (counts["ambiguous_qualifiers"] * 5) - (max(0, counts["negative_directives"] - 5) * 2))
    d[DIMENSIONS[5]] = max(0, 100 - (counts["hijack"] * 30) - (counts["pressure"] * 18) - (counts["repeat_unbounded"] * 14))

    base = mean(d.values())

    # Test cassette penalty
    if ctx["is_cassette"]:
        base -= 3.0

    # Coverage cap
    cap = 100 if coverage >= 0.95 else (92 if coverage >= 0.80 else (85 if coverage >= 0.70 else 78))
    final = round(min(base * coverage + (1 - coverage) * 82, cap), 1)

    # Findings
    findings: list[str] = []
    if counts["hijack"]:
        findings.append("E1 instruction-hijack phrasing")
    if counts["pressure"]:
        findings.append("E2 coercive pressure phrasing")
    if counts["repeat_unbounded"]:
        findings.append("E3 unbounded-repeat phrasing")
    if counts["ambiguous_qualifiers"] >= 2:
        findings.append("HERM ambiguity density")
    if counts["priority"] == 0:
        findings.append("No explicit priority ordering")
    if counts["boundary"] == 0:
        findings.append("No explicit task-boundary language")

    confidence = "high" if coverage >= 0.9 else ("medium" if coverage >= 0.75 else "low")

    return HermResult(
        score=final,
        dimension_scores={k: round(v, 1) for k, v in d.items()},
        signal_counts=counts,
        coverage=coverage,
        confidence=confidence,
        findings=findings,
        context_flags=ctx,
    )


def score_file(path: str | Path) -> HermResult:
    """Score a file on HERM v1.1 dimensions.

    Reads the file and scores its raw text content.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    return score_text(text, source_path=str(path))
