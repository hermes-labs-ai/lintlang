"""Shared scan models and normalization types used by every detector.

This module must not import from lintlang.patterns or a detector module, so
parsers, detectors, and the compatible lintlang.patterns import surface can
share the same class objects without a cycle.
"""

from __future__ import annotations

import re
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
    offset: int | None = None
    """Character offset of the evidence inside ``AgentConfig.system_prompt``.
    The scanner turns it into a file line for text inputs."""

    @property
    def code(self) -> str:
        """The most specific stable identifier for this finding."""
        return self.sub_id or self.pattern_id


@dataclass
class SkillMeta:
    """``name`` / ``description`` front matter of a skill or sub-agent file.

    The description is what a model reads when deciding whether to load the
    skill, so it is a selection-time tool description in everything but name."""

    name: str
    description: str
    has_name: bool = True
    has_description: bool = True
    name_line: int = 0
    description_line: int = 0
    dir_name: str = ""


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
    kind: str = "config"
    """What the input is: "config" (parsed YAML/JSON), "prompt" (a prompt text
    file), "instructions" (a Markdown document an agent reads, such as AGENTS.md
    or a SKILL.md body) or "python" (an extracted literal). Detectors that only
    make sense for one kind consult it rather than treating everything as a chat
    system prompt."""
    unclaimed: list[str] = field(default_factory=list)
    """Paths of tool-like objects the parser saw and did not inspect."""
    uninspected_text: list[str] = field(default_factory=list)
    """Description paths whose localization keys could not be resolved offline."""
    dropped: list[str] = field(default_factory=list)
    """Members of a tool container the parser could not read."""
    not_agent_content: str = ""
    """Set when the document is a recognised non-agent format (JSON Schema, SBOM...)."""
    prompt_paths: list[str] = field(default_factory=list)
    """Paths of prompts read from nested keys of a config."""
    skill: SkillMeta | None = None
    """Front matter of a SKILL.md / agent definition, when the file has one."""
    prompt_line_offset: int = 0
    """Lines of the source file that precede ``system_prompt`` (front matter)."""


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    path: str = ""
    """JSON path of the tool object inside its file."""
    group: str = "tools"
    """Path of the enclosing container. Pairwise checks compare within a group:
    two MCP servers may each legitimately expose a tool called ``search``."""
    owner: str = ""
    has_schema: bool = False


def is_localization_reference(text: str) -> bool:
    """VS Code percent-delimited message keys are not model-facing prose."""
    return bool(re.fullmatch(r"%[A-Za-z0-9_.-]+%", text.strip()))
