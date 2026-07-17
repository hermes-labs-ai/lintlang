"""Frozen public models for provider-neutral prompt preflight.

The result model deliberately keeps raw evidence and replacement text in private,
``repr=False`` fields.  Serialization is redacted unless the caller explicitly
authorizes snippets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCHEMA_ID = "urn:lintlang:schema:preflight-result:v1"
SCHEMA_VERSION = "lintlang.preflight-result.v1"
ENGINE_VERSION = "0.3.1+preflight.1"
RULE_BUNDLE_VERSION = "preflight-rules.v1"
MAX_PROMPT_UTF8_BYTES = 32 * 1024
MAX_CONTEXT_UTF8_BYTES = 32 * 1024
ALL_RULE_IDS = ("PF001", "PF002", "PF003", "PF004", "PF005")


class _StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Status(_StringEnum):
    ALLOW = "ALLOW"
    NOTICE = "NOTICE"
    HOLD = "HOLD"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ScopeKind(_StringEnum):
    DIRECT = "DIRECT"
    QUOTED = "QUOTED"
    HYPOTHETICAL = "HYPOTHETICAL"
    CODE = "CODE"
    NEGATED = "NEGATED"
    # Internal-only classification. Operative findings are never emitted from it.
    METALINGUISTIC = "METALINGUISTIC"


class Confidence(_StringEnum):
    EXACT = "EXACT"
    HEURISTIC = "HEURISTIC"


class Maturity(_StringEnum):
    STABLE = "STABLE"
    BETA = "BETA"
    EXPERIMENTAL = "EXPERIMENTAL"


class Enforcement(_StringEnum):
    HOLD_ELIGIBLE = "HOLD_ELIGIBLE"
    NOTICE_ONLY = "NOTICE_ONLY"


class CoverageState(_StringEnum):
    FULL = "FULL"
    NONE = "NONE"
    NOT_REQUIRED = "NOT_REQUIRED"


class DiagnosticSeverity(_StringEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ContextSource(_StringEnum):
    USER = "user"
    CALLER = "caller"
    HERMENEUTIC = "hermeneutic"
    REPOSITORY = "repository"
    HOST = "host"


class Delivery(_StringEnum):
    SIDE_CHANNEL = "SIDE_CHANNEL"
    IN_PROMPT = "IN_PROMPT"


class ConstraintKind(_StringEnum):
    OUTPUT_FORMAT = "OUTPUT_FORMAT"


class ActionId(_StringEnum):
    PASS_AS_IS = "PASS_AS_IS"
    APPLY_PATCH = "APPLY_PATCH"
    ADD_CONTEXT = "ADD_CONTEXT"
    HOLD_AND_DISCUSS = "HOLD_AND_DISCUSS"


class MeaningPreservation(_StringEnum):
    UNVERIFIED = "UNVERIFIED"


class BoundaryErrorCode(_StringEnum):
    INVALID_UTF8 = "INVALID_UTF8"
    INVALID_CONTEXT_JSON = "INVALID_CONTEXT_JSON"
    INPUT_READ_FAILED = "INPUT_READ_FAILED"
    CONTEXT_READ_FAILED = "CONTEXT_READ_FAILED"


@dataclass(frozen=True, slots=True)
class Span:
    """A Python code-point ``[start, end)`` span into the original prompt."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid code-point span")


@dataclass(frozen=True, slots=True)
class ContextBinding:
    key: str
    value: str
    source: ContextSource
    delivery: Delivery


@dataclass(frozen=True, slots=True)
class ContextRequirement:
    key: str
    required: bool = True
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ContextConstraint:
    """A typed, caller-supplied constraint; free-form command strings are invalid."""

    kind: ConstraintKind
    value: str


@dataclass(frozen=True, slots=True)
class ContextContract:
    requirements: tuple[ContextRequirement, ...] = ()
    bindings: tuple[ContextBinding, ...] = ()
    constraints: tuple[ContextConstraint, ...] = ()


@dataclass(frozen=True, slots=True)
class Override:
    finding_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class PreflightPolicy:
    id: str = "default-v1"
    enabled_rules: tuple[str, ...] | None = None
    required_rules: tuple[str, ...] | None = None
    include_snippets: bool = False
    overrides: tuple[Override, ...] = ()


@dataclass(frozen=True, slots=True)
class PreflightRequest:
    prompt: str
    language: str = "en"
    context: ContextContract = field(default_factory=ContextContract)
    policy: PreflightPolicy = field(default_factory=PreflightPolicy)


@dataclass(frozen=True, slots=True)
class PromptEvidence:
    span: Span
    sha256: str
    codepoints: int
    utf8_bytes: int
    _snippet: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ContextEvidence:
    json_pointer: str
    sha256: str
    codepoints: int
    utf8_bytes: int
    _value: str = field(repr=False, compare=False)


Evidence = PromptEvidence | ContextEvidence


@dataclass(frozen=True, slots=True)
class Coverage:
    component: str
    required: bool
    state: CoverageState
    reason: str


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    context_pointer: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    finding_id: str
    rule_id: str
    rule_version: str
    label: str
    scope: ScopeKind
    trigger_kind: str
    trigger: Evidence
    proposition_kind: str | None
    proposition: Evidence | None
    additional_evidence: tuple[Evidence, ...]
    risk: str
    explanation: str
    suggestion: str
    confidence: Confidence
    maturity: Maturity
    enforcement: Enforcement
    related_output_modes: tuple[str, ...]
    correction_ids: tuple[str, ...] = ()
    overridden: bool = False
    override_reason_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class TextEdit:
    start: int
    end: int
    replacement_sha256: str
    replacement_codepoints: int
    replacement_utf8_bytes: int
    _replacement: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Correction:
    correction_id: str
    finding_id: str
    source_sha256: str
    result_sha256: str
    schema_version: str
    engine_version: str
    rule_bundle_version: str
    edits: tuple[TextEdit, ...]
    diff_sha256: str
    diff_utf8_bytes: int
    meaning_preservation: MeaningPreservation
    requires_relint: bool
    _diff: str = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Action:
    id: ActionId
    available: bool
    precondition: str


@dataclass(frozen=True, slots=True)
class InputMetadata:
    sha256: str
    codepoints: int
    utf8_bytes: int
    context_sha256: str
    context_utf8_bytes: int
    language: str


@dataclass(frozen=True, slots=True)
class PreflightResult:
    schema_id: str
    schema_version: str
    engine_version: str
    rule_bundle_version: str
    fingerprint: str
    status: Status
    exit_code: int
    input: InputMetadata
    coverage: tuple[Coverage, ...]
    findings: tuple[Finding, ...]
    corrections: tuple[Correction, ...]
    actions: tuple[Action, ...]
    diagnostics: tuple[Diagnostic, ...]
    parent_fingerprint: str | None = None
    applied_correction_id: str | None = None
    relint_depth: int = 0
    network_attempted: bool = False
    storage_persisted: bool = False
    _snippets_authorized: bool = field(default=False, repr=False, compare=False)

    def to_dict(self, include_snippets: bool | None = None) -> dict:
        """Return a deterministic wire object.

        Raw evidence, context values, replacements, and diffs are omitted unless
        snippets were authorized in policy or explicitly requested here.
        """

        from .serialization import result_to_dict

        reveal = self._snippets_authorized if include_snippets is None else include_snippets
        return result_to_dict(self, include_snippets=reveal)

    def to_json(self, include_snippets: bool | None = None, *, indent: int | None = None) -> str:
        from .serialization import result_to_json

        reveal = self._snippets_authorized if include_snippets is None else include_snippets
        return result_to_json(self, include_snippets=reveal, indent=indent)


class CorrectionError(ValueError):
    """A correction failed a closed applicability check."""
