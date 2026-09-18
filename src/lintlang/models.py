"""Shared scan models: severities, findings, and normalized agent config.

These types are the vocabulary every detector and the rule registry in
`lintlang.patterns` share. This module must not import from `patterns.py`
or from any detector module, so it can be imported by both without creating
a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def score(self) -> int:
        return {
            Severity.CRITICAL: 10,
            Severity.HIGH: 7,
            Severity.MEDIUM: 4,
            Severity.LOW: 2,
            Severity.INFO: 0,
        }[self]


@dataclass(frozen=True)
class SourceRegion:
    """A one-based source line span supported by parser or AST evidence."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("source regions require positive, ordered line numbers")


@dataclass
class Finding:
    pattern_id: str
    pattern_name: str
    severity: Severity
    location: str
    description: str
    suggestion: str
    evidence: str = ""
    sub_id: str = ""
    """Stable sub-code within the pattern, e.g. "H1.6". Empty for un-subcoded findings.

    Sub-codes exist so a finding can be cited precisely ("that's an H1.6") without
    renaming the pattern IDs people already reference. The pattern ID stays the
    citable root; the sub-code narrows it.
    """
    source_region: SourceRegion | None = None

    @property
    def code(self) -> str:
        """The most specific stable identifier for this finding."""
        return self.sub_id or self.pattern_id


@dataclass
class AgentConfig:
    """Normalized representation of an agent configuration."""

    tools: list[ToolDef] = field(default_factory=list)
    system_prompt: str = ""
    messages: list[dict] = field(default_factory=list)
    schemas: list[dict] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    source_file: str = ""
    source_region: SourceRegion | None = None


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
