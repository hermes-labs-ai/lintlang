"""Deterministic provider-neutral preflight engine for PF001--PF005."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from .models import (
    ALL_RULE_IDS,
    ENGINE_VERSION,
    MAX_CONTEXT_UTF8_BYTES,
    MAX_PROMPT_UTF8_BYTES,
    RULE_BUNDLE_VERSION,
    SCHEMA_ID,
    SCHEMA_VERSION,
    Action,
    ActionId,
    BoundaryErrorCode,
    Confidence,
    ConstraintKind,
    ContextBinding,
    ContextConstraint,
    ContextContract,
    ContextEvidence,
    ContextRequirement,
    ContextSource,
    Correction,
    CorrectionError,
    Coverage,
    CoverageState,
    Delivery,
    Diagnostic,
    DiagnosticSeverity,
    Enforcement,
    Evidence,
    Finding,
    InputMetadata,
    Maturity,
    MeaningPreservation,
    Override,
    PreflightPolicy,
    PreflightRequest,
    PreflightResult,
    PromptEvidence,
    ScopeKind,
    Span,
    Status,
    TextEdit,
)
from .scope import ScopeAnalysis, analyze_scope
from .serialization import result_to_dict

EXIT_CODES = {
    Status.ALLOW: 0,
    Status.NOTICE: 0,
    Status.HOLD: 1,
    Status.ERROR: 2,
    Status.UNAVAILABLE: 3,
}
ACTION_ORDER = (
    ActionId.PASS_AS_IS,
    ActionId.APPLY_PATCH,
    ActionId.ADD_CONTEXT,
    ActionId.HOLD_AND_DISCUSS,
)

_PF001_PATTERNS = (
    re.compile(
        r"\b(?:is|was|are|were)\s+(?:it|this|that)\s+(?:really\s+)?true\s+that\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bwouldn['’]?t\s+you\s+(?:agree|say)\b", re.IGNORECASE),
    re.compile(r",\s*(?:right|correct)\s*\?", re.IGNORECASE),
)
_PF002_PATTERN = re.compile(
    r"\bwhy\s+(?:does|do|did)\s+(?P<subject>[^?!.]{1,160}?)\s+"
    r"(?P<verb>causes?)\s+(?P<object>[^?!.]{1,160}?)(?=\s*(?:[,?!.]|$))",
    re.IGNORECASE | re.DOTALL,
)
_PF003_PATTERNS = (
    (re.compile(r"\b(?:our|the)\s+usual\s+format\b", re.IGNORECASE), "usual_format"),
    (
        re.compile(r"\bas\s+(?:we|you)\s+always\s+(?:do|use)\b", re.IGNORECASE),
        "usual_process",
    ),
    (re.compile(r"\bas\s+before\b", re.IGNORECASE), "previous_process"),
    (
        re.compile(r"\b(?:the\s+)?same\s+as\s+last\s+time\b", re.IGNORECASE),
        "previous_process",
    ),
    (
        re.compile(r"\bour\s+standard\s+(?:format|process)\b", re.IGNORECASE),
        "standard_process",
    ),
)
_FORMAT_DIRECTIVE_PATTERN = re.compile(r"\b(?:return|respond(?:\s+with)?|output|format)\b", re.IGNORECASE)
_FORMAT_VALUE_PATTERN = re.compile(r"\b(?:json|markdown)\b", re.IGNORECASE)
_FORMAT_ALTERNATIVE_SEPARATOR_PATTERN = re.compile(
    r"\s*(?:,?\s*(?:or|and/or)(?:\s+(?:return|respond(?:\s+with)?|output|format))?\s*|/\s*)",
    re.IGNORECASE,
)
_ONE_SENTENCE_PATTERN = re.compile(r"\bexactly\s+one\s+sentence\b", re.IGNORECASE)
_THREE_PARAGRAPHS_PATTERN = re.compile(r"\bat\s+least\s+(?:three|3)\s+paragraphs?\b", re.IGNORECASE)
_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_FINDING_ID_PATTERN = re.compile(r"^pf_[0-9a-f]{20}$")


@dataclass(frozen=True, slots=True)
class _RuleMeta:
    label: str
    risk: str
    explanation: str
    suggestion: str
    confidence: Confidence
    maturity: Maturity
    enforcement: Enforcement
    related_output_modes: tuple[str, ...] = ()


_RULE_META = {
    "PF001": _RuleMeta(
        "validation-seeking-frame",
        "The wording frames confirmation as the conversational default.",
        "This input-side steer is not evidence that the proposition is true or false.",
        "Ask for evidence for and against the proposition.",
        Confidence.HEURISTIC,
        Maturity.BETA,
        Enforcement.NOTICE_ONLY,
        ("Controversy-Truth Conflation",),
    ),
    "PF002": _RuleMeta(
        "presupposed-causality",
        "The question grammatically assumes a causal relation that may be disputed.",
        "The detector identifies presupposition; it does not evaluate causal truth.",
        "Ask whether credible evidence supports the causal relation.",
        Confidence.HEURISTIC,
        Maturity.BETA,
        Enforcement.NOTICE_ONLY,
    ),
    "PF003": _RuleMeta(
        "unresolved-context-reference",
        "A deictic reference has no explicit value in the current request contract.",
        "History is outside LintLang's boundary; the caller must supply the value.",
        "Add an explicit context binding.",
        Confidence.EXACT,
        Maturity.BETA,
        Enforcement.NOTICE_ONLY,
        ("Silent Instruction Relaxation",),
    ),
    "PF004": _RuleMeta(
        "missing-required-context",
        "A required context key is missing or has not been materialized as promised.",
        "The requirement comes from the typed contract, not an inferred preference.",
        "Supply the binding or preview its exact materialization.",
        Confidence.EXACT,
        Maturity.BETA,
        Enforcement.HOLD_ELIGIBLE,
        ("Silent Instruction Relaxation",),
    ),
    "PF005": _RuleMeta(
        "explicit-instruction-conflict",
        "Two exact instructions cannot both be satisfied.",
        "The conflict is mechanical; LintLang does not choose which instruction wins.",
        "Clarify or remove one conflicting constraint.",
        Confidence.EXACT,
        Maturity.BETA,
        Enforcement.HOLD_ELIGIBLE,
        ("Constraint Evasion",),
    ),
}


@dataclass(frozen=True, slots=True)
class _FindingSeed:
    rule_id: str
    trigger_kind: str
    trigger: Evidence
    proposition_kind: str | None
    proposition: Evidence | None
    additional_evidence: tuple[Evidence, ...]
    discriminator: str
    edits: tuple[tuple[int, int, str], ...] = ()
    enforcement: Enforcement | None = None


@dataclass(frozen=True, slots=True)
class _ValidatedContext:
    bindings: dict[str, tuple[ContextBinding, int]]
    requirements: tuple[tuple[ContextRequirement, int], ...]
    constraints: tuple[tuple[ContextConstraint, int], ...]


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _is_utf8_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _materialization_word_char(value: str) -> bool:
    return value.isalnum() or value == "_"


def _explicit_short_value_label(prefix: str, key: str) -> bool:
    folded_key = key.casefold()
    key_forms = {folded_key, re.sub(r"[._-]+", " ", folded_key).strip()}
    for key_form in sorted(key_forms, key=len, reverse=True):
        if not key_form:
            continue
        index = prefix.rfind(key_form)
        if index < 0:
            continue
        before = prefix[index - 1] if index else ""
        after_index = index + len(key_form)
        after = prefix[after_index : after_index + 1]
        if (before and _materialization_word_char(before)) or (after and _materialization_word_char(after)):
            continue
        suffix = prefix[after_index:]
        if re.fullmatch(
            r"\s*[)\]}]?\s*(?:(?:code|value)\s*)?(?:(?:is)\s*|[:=\-]\s*)?",
            suffix,
            re.IGNORECASE,
        ):
            return True
    return False


def _binding_value_is_materialized(prompt: str, binding: ContextBinding) -> bool:
    folded_prompt = prompt.casefold()
    folded_value = binding.value.casefold()
    start = folded_prompt.find(folded_value)
    while start >= 0:
        end = start + len(folded_value)
        left_ok = (
            not _materialization_word_char(folded_value[0])
            or start == 0
            or not _materialization_word_char(folded_prompt[start - 1])
        )
        right_ok = (
            not _materialization_word_char(folded_value[-1])
            or end == len(folded_prompt)
            or not _materialization_word_char(folded_prompt[end])
        )
        if left_ok and right_ok:
            short_alphanumeric = len(folded_value) <= 3 and folded_value.isalnum()
            prefix = folded_prompt[max(0, start - 64) : start]
            if not short_alphanumeric or _explicit_short_value_label(prefix, binding.key):
                return True
        start = folded_prompt.find(folded_value, start + 1)
    return False


def _wire_language(value: Any) -> str:
    if isinstance(value, str) and value.strip() and _is_utf8_text(value):
        return value
    return "und"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _context_bytes(context: Any) -> bytes:
    if not isinstance(context, ContextContract):
        return _canonical_bytes({"invalid_context_type": type(context).__name__})
    payload = {
        "requirements": [
            {
                "key": item.key,
                "required": item.required,
                "description": item.description,
            }
            if isinstance(item, ContextRequirement)
            else {"invalid_type": type(item).__name__}
            for item in context.requirements
        ]
        if isinstance(context.requirements, tuple)
        else [{"invalid_collection": type(context.requirements).__name__}],
        "bindings": [
            {
                "key": item.key,
                "value": item.value,
                "source": _enum_value(item.source),
                "delivery": _enum_value(item.delivery),
            }
            if isinstance(item, ContextBinding)
            else {"invalid_type": type(item).__name__}
            for item in context.bindings
        ]
        if isinstance(context.bindings, tuple)
        else [{"invalid_collection": type(context.bindings).__name__}],
        "constraints": [
            {"kind": _enum_value(item.kind), "value": item.value}
            if isinstance(item, ContextConstraint)
            else {"invalid_type": type(item).__name__}
            for item in context.constraints
        ]
        if isinstance(context.constraints, tuple)
        else [{"invalid_collection": type(context.constraints).__name__}],
    }
    try:
        return _canonical_bytes(payload)
    except (TypeError, UnicodeEncodeError):
        return _canonical_bytes({"invalid_context_encoding": True})


def _input_metadata(request: Any) -> InputMetadata:
    prompt = request.prompt if isinstance(request, PreflightRequest) else ""
    language = request.language if isinstance(request, PreflightRequest) else ""
    context = request.context if isinstance(request, PreflightRequest) else ContextContract()
    if isinstance(prompt, str):
        prompt_bytes = prompt.encode("utf-8", errors="surrogatepass")
        codepoints = len(prompt)
    else:
        prompt_bytes = _canonical_bytes({"invalid_prompt_type": type(prompt).__name__})
        codepoints = 0
    context_bytes = _context_bytes(context)
    return InputMetadata(
        sha256=_sha_bytes(prompt_bytes),
        codepoints=codepoints,
        utf8_bytes=len(prompt_bytes),
        context_sha256=_sha_bytes(context_bytes),
        context_utf8_bytes=len(context_bytes),
        language=_wire_language(language),
    )


def _coverage(enabled: set[str], required: set[str], state: CoverageState, reason: str) -> tuple[Coverage, ...]:
    has_enabled = bool(enabled)
    items = [
        Coverage(
            "scope-parser",
            bool(required),
            state if has_enabled else CoverageState.NOT_REQUIRED,
            reason if has_enabled else "no enabled rules",
        )
    ]
    for rule_id in ALL_RULE_IDS:
        if rule_id not in enabled:
            items.append(Coverage(rule_id, False, CoverageState.NOT_REQUIRED, "disabled by policy"))
        else:
            items.append(Coverage(rule_id, rule_id in required, state, reason))
    return tuple(items)


def _actions(status: Status, findings: Sequence[Finding], corrections: Sequence[Correction]) -> tuple[Action, ...]:
    rule_ids = {finding.rule_id for finding in findings}
    holds = [
        finding
        for finding in findings
        if finding.confidence is Confidence.EXACT and finding.enforcement is Enforcement.HOLD_ELIGIBLE
    ]
    all_holds_overridden = bool(holds) and all(finding.overridden for finding in holds)
    available: set[ActionId] = set()
    if status is Status.UNAVAILABLE:
        available.add(ActionId.HOLD_AND_DISCUSS)
    elif status is not Status.ERROR:
        available.add(ActionId.HOLD_AND_DISCUSS)
        if status in {Status.ALLOW, Status.NOTICE} or all_holds_overridden:
            available.add(ActionId.PASS_AS_IS)
        if corrections:
            available.add(ActionId.APPLY_PATCH)
        if rule_ids.intersection({"PF003", "PF004", "PF005"}):
            available.add(ActionId.ADD_CONTEXT)
    preconditions = {
        ActionId.PASS_AS_IS: "No active unoverridden HOLD; provider send remains outside LintLang.",
        ActionId.APPLY_PATCH: "Select one correction whose source hash matches, then re-lint once.",
        ActionId.ADD_CONTEXT: "Caller supplies or clarifies a typed binding or constraint.",
        ActionId.HOLD_AND_DISCUSS: "Inspect evidence; no provider send is performed.",
    }
    return tuple(Action(action_id, action_id in available, preconditions[action_id]) for action_id in ACTION_ORDER)


def _finalize(result: PreflightResult) -> PreflightResult:
    payload = result_to_dict(result, include_snippets=False, include_fingerprint=False)
    fingerprint = "sha256:" + _sha_bytes(_canonical_bytes(payload))
    return replace(result, fingerprint=fingerprint)


def _result(
    *,
    metadata: InputMetadata,
    status: Status,
    coverage: tuple[Coverage, ...],
    findings: tuple[Finding, ...] = (),
    corrections: tuple[Correction, ...] = (),
    diagnostics: tuple[Diagnostic, ...] = (),
    snippets_authorized: bool = False,
    parent_fingerprint: str | None = None,
    applied_correction_id: str | None = None,
    relint_depth: int = 0,
) -> PreflightResult:
    result = PreflightResult(
        schema_id=SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        engine_version=ENGINE_VERSION,
        rule_bundle_version=RULE_BUNDLE_VERSION,
        fingerprint="",
        status=status,
        exit_code=EXIT_CODES[status],
        input=metadata,
        coverage=coverage,
        findings=findings,
        corrections=corrections,
        actions=_actions(status, findings, corrections),
        diagnostics=diagnostics,
        parent_fingerprint=parent_fingerprint,
        applied_correction_id=applied_correction_id,
        relint_depth=relint_depth,
        _snippets_authorized=snippets_authorized,
    )
    return _finalize(result)


def _early(
    metadata: InputMetadata,
    status: Status,
    code: str,
    message: str,
    *,
    enabled: set[str] | None = None,
    required: set[str] | None = None,
    snippets_authorized: bool = False,
    context_pointer: str | None = None,
    parent_fingerprint: str | None = None,
    applied_correction_id: str | None = None,
    relint_depth: int = 0,
) -> PreflightResult:
    enabled = set(ALL_RULE_IDS) if enabled is None else enabled
    required = set(enabled) if required is None else required
    coverage_state = CoverageState.NONE
    return _result(
        metadata=metadata,
        status=status,
        coverage=_coverage(enabled, required, coverage_state, message),
        diagnostics=(Diagnostic(code, DiagnosticSeverity.ERROR, message, context_pointer),),
        snippets_authorized=snippets_authorized,
        parent_fingerprint=parent_fingerprint,
        applied_correction_id=applied_correction_id,
        relint_depth=relint_depth,
    )


def _coverage_unavailable(
    metadata: InputMetadata,
    code: str,
    message: str,
    *,
    enabled: set[str],
    required: set[str],
    snippets_authorized: bool,
    parent_fingerprint: str | None,
    applied_correction_id: str | None,
    relint_depth: int,
) -> PreflightResult:
    if required:
        return _early(
            metadata,
            Status.UNAVAILABLE,
            code,
            message,
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            parent_fingerprint=parent_fingerprint,
            applied_correction_id=applied_correction_id,
            relint_depth=relint_depth,
        )
    return _result(
        metadata=metadata,
        status=Status.ALLOW,
        coverage=_coverage(enabled, required, CoverageState.NONE, message),
        diagnostics=(Diagnostic(code, DiagnosticSeverity.WARNING, message),),
        snippets_authorized=snippets_authorized,
        parent_fingerprint=parent_fingerprint,
        applied_correction_id=applied_correction_id,
        relint_depth=relint_depth,
    )


_BOUNDARY_MESSAGES = {
    BoundaryErrorCode.INVALID_UTF8: "input is not valid UTF-8",
    BoundaryErrorCode.INPUT_TOO_LARGE: "input exceeds 32 KiB",
    BoundaryErrorCode.INVALID_CONTEXT_JSON: "context is not valid JSON",
    BoundaryErrorCode.INPUT_READ_FAILED: "input could not be read",
    BoundaryErrorCode.CONTEXT_READ_FAILED: "context could not be read",
}


def boundary_error(
    code: BoundaryErrorCode,
    *,
    input_sha256: str | None = None,
    input_codepoints: int = 0,
    input_utf8_bytes: int = 0,
    context_sha256: str | None = None,
    context_utf8_bytes: int = 0,
    language: str = "en",
) -> PreflightResult:
    """Build a schema-coherent, redacted ERROR at a file/JSON boundary.

    Messages are selected from an enum so raw exception strings cannot leak input.
    """

    empty_hash = _sha_bytes(b"")
    hash_pattern = re.compile(r"^[0-9a-f]{64}$")
    safe_input_hash = input_sha256 if input_sha256 and hash_pattern.fullmatch(input_sha256) else empty_hash
    safe_context_hash = context_sha256 if context_sha256 and hash_pattern.fullmatch(context_sha256) else empty_hash
    metadata = InputMetadata(
        safe_input_hash,
        max(0, input_codepoints),
        max(0, input_utf8_bytes),
        safe_context_hash,
        max(0, context_utf8_bytes),
        _wire_language(language),
    )
    if not isinstance(code, BoundaryErrorCode):
        code = BoundaryErrorCode.INPUT_READ_FAILED
    return _early(metadata, Status.ERROR, code.value, _BOUNDARY_MESSAGES[code])


def _prompt_evidence(prompt: str, start: int, end: int) -> PromptEvidence:
    if not 0 <= start < end <= len(prompt):
        raise ValueError("prompt evidence must be a non-empty exact source span")
    snippet = prompt[start:end]
    encoded = snippet.encode("utf-8")
    return PromptEvidence(Span(start, end), _sha_bytes(encoded), len(snippet), len(encoded), snippet)


def _context_evidence(pointer: str, value: str) -> ContextEvidence:
    encoded = value.encode("utf-8")
    return ContextEvidence(pointer, _sha_bytes(encoded), len(value), len(encoded), value)


def _evidence_identity(evidence: Evidence) -> dict[str, Any]:
    if isinstance(evidence, PromptEvidence):
        return {
            "source": "prompt",
            "start": evidence.span.start,
            "end": evidence.span.end,
            "sha256": evidence.sha256,
        }
    return {
        "source": "context",
        "json_pointer": evidence.json_pointer,
        "sha256": evidence.sha256,
    }


def _finding_id(seed: _FindingSeed, prompt_sha256: str) -> str:
    material = {
        "schema": SCHEMA_VERSION,
        "rules": RULE_BUNDLE_VERSION,
        "rule_id": seed.rule_id,
        "prompt_sha256": prompt_sha256,
        "trigger": _evidence_identity(seed.trigger),
        "proposition": None if seed.proposition is None else _evidence_identity(seed.proposition),
        "additional": [_evidence_identity(item) for item in seed.additional_evidence],
        "discriminator": seed.discriminator,
    }
    return "pf_" + _sha_bytes(_canonical_bytes(material))[:20]


def _make_text_edit(start: int, end: int, replacement: str) -> TextEdit:
    encoded = replacement.encode("utf-8")
    return TextEdit(start, end, _sha_bytes(encoded), len(replacement), len(encoded), replacement)


def _apply_edits(prompt: str, edits: Sequence[TextEdit]) -> str:
    ordered = sorted(edits, key=lambda item: (item.start, item.end))
    previous_end = -1
    for edit in ordered:
        if not 0 <= edit.start <= edit.end <= len(prompt):
            raise CorrectionError("correction offsets are outside the source")
        if edit.start < previous_end:
            raise CorrectionError("correction edits overlap")
        if _sha_text(edit._replacement) != edit.replacement_sha256:
            raise CorrectionError("correction replacement hash does not match")
        previous_end = edit.end
    corrected = prompt
    for edit in reversed(ordered):
        corrected = corrected[: edit.start] + edit._replacement + corrected[edit.end :]
    return corrected


def _make_correction(prompt: str, finding_id: str, seed: _FindingSeed) -> Correction:
    edits = tuple(_make_text_edit(start, end, value) for start, end, value in seed.edits)
    corrected = _apply_edits(prompt, edits)
    source_sha = _sha_text(prompt)
    edit_identity = [
        {
            "start": item.start,
            "end": item.end,
            "replacement_sha256": item.replacement_sha256,
        }
        for item in edits
    ]
    correction_id = (
        "pc_"
        + _sha_bytes(
            _canonical_bytes(
                {
                    "finding_id": finding_id,
                    "source_sha256": source_sha,
                    "edits": edit_identity,
                    "schema": SCHEMA_VERSION,
                    "engine": ENGINE_VERSION,
                    "rules": RULE_BUNDLE_VERSION,
                }
            )
        )[:20]
    )
    diff_parts: list[str] = []
    for line in difflib.unified_diff(
        prompt.splitlines(keepends=True),
        corrected.splitlines(keepends=True),
        fromfile="prompt",
        tofile="corrected",
        lineterm="\n",
    ):
        diff_parts.append(line)
        if line[:1] in {" ", "-", "+"} and not line.endswith("\n"):
            diff_parts.extend(("\n", "\\ No newline at end of file\n"))
    diff = "".join(diff_parts)
    diff_bytes = diff.encode("utf-8")
    return Correction(
        correction_id,
        finding_id,
        source_sha,
        _sha_text(corrected),
        SCHEMA_VERSION,
        ENGINE_VERSION,
        RULE_BUNDLE_VERSION,
        edits,
        _sha_bytes(diff_bytes),
        len(diff_bytes),
        MeaningPreservation.UNVERIFIED,
        True,
        diff,
    )


def _seed_sort_key(seed: _FindingSeed) -> tuple[Any, ...]:
    prompt_evidence = [
        item for item in (seed.trigger, seed.proposition, *seed.additional_evidence) if isinstance(item, PromptEvidence)
    ]
    if prompt_evidence:
        start = min(item.span.start for item in prompt_evidence)
        end = max(item.span.end for item in prompt_evidence)
        return (0, start, end, seed.rule_id, seed.discriminator)
    context_evidence = [
        item
        for item in (seed.trigger, seed.proposition, *seed.additional_evidence)
        if isinstance(item, ContextEvidence)
    ]
    pointer = min((item.json_pointer for item in context_evidence), default="")
    return (1, pointer, seed.rule_id, seed.discriminator)


def _validate_policy(
    policy: Any,
) -> tuple[PreflightPolicy | None, set[str], set[str], tuple[str, str] | None]:
    all_rules = set(ALL_RULE_IDS)
    if not isinstance(policy, PreflightPolicy):
        return (
            None,
            all_rules,
            all_rules,
            ("INVALID_POLICY", "policy must use typed preflight models"),
        )
    if policy.id != "default-v1":
        return (
            policy,
            all_rules,
            all_rules,
            ("UNKNOWN_POLICY", "policy identifier is unsupported"),
        )
    enabled_values = policy.enabled_rules if policy.enabled_rules is not None else ALL_RULE_IDS
    required_values = policy.required_rules if policy.required_rules is not None else enabled_values
    if not isinstance(enabled_values, tuple) or not isinstance(required_values, tuple):
        return (
            policy,
            all_rules,
            all_rules,
            ("INVALID_POLICY", "rule selections must be immutable tuples"),
        )
    if any(not isinstance(item, str) or item not in all_rules for item in enabled_values):
        return (
            policy,
            all_rules,
            all_rules,
            ("UNKNOWN_RULE", "policy contains an unsupported rule identifier"),
        )
    enabled = set(enabled_values)
    if any(not isinstance(item, str) or item not in all_rules for item in required_values):
        return (
            policy,
            enabled,
            enabled,
            ("UNKNOWN_REQUIRED_RULE", "policy requires an unsupported rule identifier"),
        )
    required = set(required_values)
    if not required.issubset(enabled):
        return (
            policy,
            enabled,
            required,
            ("INVALID_POLICY", "a required rule is disabled"),
        )
    if not isinstance(policy.include_snippets, bool) or not isinstance(policy.overrides, tuple):
        return (
            policy,
            enabled,
            required,
            ("INVALID_POLICY", "policy fields have invalid types"),
        )
    seen_overrides: set[str] = set()
    for override in policy.overrides:
        if not isinstance(override, Override):
            return (
                policy,
                enabled,
                required,
                ("INVALID_OVERRIDE", "override must use the typed model"),
            )
        if (
            not isinstance(override.finding_id, str)
            or not _FINDING_ID_PATTERN.fullmatch(override.finding_id)
            or not isinstance(override.reason, str)
            or not override.reason.strip()
            or not _is_utf8_text(override.reason)
        ):
            return (
                policy,
                enabled,
                required,
                ("INVALID_OVERRIDE", "override identifier or reason is invalid"),
            )
        if override.finding_id in seen_overrides:
            return (
                policy,
                enabled,
                required,
                ("DUPLICATE_OVERRIDE", "a finding has multiple overrides"),
            )
        seen_overrides.add(override.finding_id)
    return policy, enabled, required, None


def _validate_context(
    context: Any,
) -> tuple[_ValidatedContext | None, tuple[str, str, str | None] | None]:
    if not isinstance(context, ContextContract):
        return None, (
            "INVALID_CONTEXT",
            "context must use typed preflight models",
            None,
        )
    if not all(
        isinstance(collection, tuple) for collection in (context.requirements, context.bindings, context.constraints)
    ):
        return None, (
            "INVALID_CONTEXT",
            "context collections must be immutable tuples",
            None,
        )
    if len(_context_bytes(context)) > MAX_CONTEXT_UTF8_BYTES:
        return None, ("CONTEXT_TOO_LARGE", "context exceeds 32 KiB", None)

    requirements: list[tuple[ContextRequirement, int]] = []
    seen_requirements: set[str] = set()
    for index, requirement in enumerate(context.requirements):
        pointer = f"/requirements/{index}"
        if not isinstance(requirement, ContextRequirement):
            return None, (
                "INVALID_REQUIREMENT",
                "requirement must use the typed model",
                pointer,
            )
        if (
            not isinstance(requirement.key, str)
            or not _KEY_PATTERN.fullmatch(requirement.key)
            or not isinstance(requirement.required, bool)
            or (requirement.description is not None and not _is_utf8_text(requirement.description))
        ):
            return None, (
                "INVALID_REQUIREMENT",
                "requirement fields are invalid",
                pointer,
            )
        if requirement.key in seen_requirements:
            return None, (
                "DUPLICATE_REQUIREMENT",
                "requirement keys must be unique",
                pointer,
            )
        seen_requirements.add(requirement.key)
        requirements.append((requirement, index))

    bindings: dict[str, tuple[ContextBinding, int]] = {}
    for index, binding in enumerate(context.bindings):
        pointer = f"/bindings/{index}"
        if not isinstance(binding, ContextBinding):
            return None, (
                "INVALID_BINDING",
                "binding must use the typed model",
                pointer,
            )
        if (
            not isinstance(binding.key, str)
            or not _KEY_PATTERN.fullmatch(binding.key)
            or not isinstance(binding.value, str)
            or not binding.value.strip()
            or not _is_utf8_text(binding.value)
        ):
            return None, ("INVALID_BINDING", "binding fields are invalid", pointer)
        if not isinstance(binding.source, ContextSource) or not isinstance(binding.delivery, Delivery):
            return None, (
                "INVALID_BINDING",
                "binding source or delivery is invalid",
                pointer,
            )
        if binding.key in bindings:
            return None, (
                "CONFLICTING_BINDINGS",
                "binding keys must be unique",
                pointer,
            )
        bindings[binding.key] = (binding, index)

    constraints: list[tuple[ContextConstraint, int]] = []
    output_format: str | None = None
    for index, constraint in enumerate(context.constraints):
        pointer = f"/constraints/{index}"
        if not isinstance(constraint, ContextConstraint):
            return None, (
                "INVALID_CONSTRAINT",
                "constraint must use the typed model",
                pointer,
            )
        if (
            not isinstance(constraint.kind, ConstraintKind)
            or not isinstance(constraint.value, str)
            or not _is_utf8_text(constraint.value)
        ):
            return None, (
                "INVALID_CONSTRAINT",
                "constraint fields are invalid",
                pointer,
            )
        value = constraint.value.strip().casefold()
        if constraint.kind is ConstraintKind.OUTPUT_FORMAT:
            if value not in {"json", "markdown"}:
                return None, (
                    "INVALID_CONSTRAINT",
                    "output format constraint is unsupported",
                    pointer,
                )
            if output_format is not None and output_format != value:
                return None, (
                    "CONFLICTING_CONTEXT_CONSTRAINTS",
                    "context declares incompatible output formats",
                    pointer,
                )
            output_format = value
        constraints.append((constraint, index))
    return _ValidatedContext(bindings, tuple(requirements), tuple(constraints)), None


def _question_end(prompt: str, start: int) -> int:
    for index in range(start, len(prompt)):
        if prompt[index] in "?!.\n":
            return index
    return len(prompt)


def _trim_span(prompt: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and prompt[start].isspace():
        start += 1
    while end > start and (prompt[end - 1].isspace() or prompt[end - 1] == ","):
        end -= 1
    return (start, end) if start < end else None


def _detect(
    prompt: str,
    scope: ScopeAnalysis,
    context: _ValidatedContext,
    enabled: set[str],
) -> list[_FindingSeed]:
    seeds: list[_FindingSeed] = []

    if "PF001" in enabled:
        for pattern_index, pattern in enumerate(_PF001_PATTERNS):
            for match in pattern.finditer(prompt):
                if not scope.is_direct(match.start(), match.end()):
                    continue
                proposition: PromptEvidence | None = None
                if pattern_index == 2:
                    sentence_start = (
                        max(
                            prompt.rfind(".", 0, match.start()),
                            prompt.rfind("?", 0, match.start()),
                            prompt.rfind("!", 0, match.start()),
                            prompt.rfind("\n", 0, match.start()),
                        )
                        + 1
                    )
                    trimmed = _trim_span(prompt, sentence_start, match.start())
                else:
                    trimmed = _trim_span(prompt, match.end(), _question_end(prompt, match.end()))
                if trimmed is not None:
                    proposition = _prompt_evidence(prompt, *trimmed)
                replacement = (
                    "What evidence supports or refutes whether"
                    if pattern_index == 0
                    else "Assess whether"
                    if pattern_index == 1
                    else "?"
                )
                seeds.append(
                    _FindingSeed(
                        "PF001",
                        "VALIDATION_FRAME",
                        _prompt_evidence(prompt, match.start(), match.end()),
                        "FRAMED_PROPOSITION" if proposition is not None else None,
                        proposition,
                        (),
                        f"pattern-{pattern_index}",
                        ((match.start(), match.end(), replacement),),
                    )
                )

    if "PF002" in enabled:
        for match in _PF002_PATTERN.finditer(prompt):
            if not scope.is_direct(match.start(), match.end()):
                continue
            trigger_end = match.start("subject")
            subject = match.group("subject").strip()
            verb = match.group("verb").strip()
            object_ = match.group("object").strip()
            replacement = f"What evidence supports or refutes whether {subject} {verb} {object_}"
            seeds.append(
                _FindingSeed(
                    "PF002",
                    "PRESUPPOSING_WHY_CAUSE",
                    _prompt_evidence(prompt, match.start(), trigger_end),
                    "PRESUPPOSED_CAUSAL_RELATION",
                    _prompt_evidence(prompt, match.start("subject"), match.end("object")),
                    (),
                    "why-cause",
                    ((match.start(), match.end(), replacement),),
                )
            )

    if "PF003" in enabled:
        for pattern, binding_key in _PF003_PATTERNS:
            for match in pattern.finditer(prompt):
                if not scope.is_direct(match.start(), match.end()):
                    continue
                if binding_key in context.bindings:
                    continue
                seeds.append(
                    _FindingSeed(
                        "PF003",
                        "DEICTIC_CONTEXT_REFERENCE",
                        _prompt_evidence(prompt, match.start(), match.end()),
                        None,
                        None,
                        (),
                        "binding-key:" + _sha_text(binding_key),
                    )
                )

    if "PF004" in enabled:
        for requirement, requirement_index in sorted(context.requirements, key=lambda item: (item[0].key, item[1])):
            if not requirement.required:
                continue
            binding_entry = context.bindings.get(requirement.key)
            requirement_evidence = _context_evidence(f"/requirements/{requirement_index}/key", requirement.key)
            if binding_entry is None:
                seeds.append(
                    _FindingSeed(
                        "PF004",
                        "MISSING_REQUIRED_BINDING",
                        requirement_evidence,
                        None,
                        None,
                        (),
                        "missing:" + _sha_text(requirement.key),
                    )
                )
                continue
            binding, binding_index = binding_entry
            if binding.delivery is Delivery.IN_PROMPT and not _binding_value_is_materialized(prompt, binding):
                binding_evidence = _context_evidence(f"/bindings/{binding_index}/value", binding.value)
                insertion = f"\n\nContext ({binding.key}): {binding.value}"
                seeds.append(
                    _FindingSeed(
                        "PF004",
                        "UNMATERIALIZED_REQUIRED_BINDING",
                        binding_evidence,
                        "DECLARED_REQUIREMENT",
                        requirement_evidence,
                        (),
                        "materialize:" + _sha_text(requirement.key),
                        ((len(prompt), len(prompt), insertion),),
                        Enforcement.NOTICE_ONLY,
                    )
                )

    if "PF005" in enabled:
        output_constraints = [
            (constraint, index)
            for constraint, index in context.constraints
            if constraint.kind is ConstraintKind.OUTPUT_FORMAT
        ]
        if output_constraints:
            constraint, constraint_index = output_constraints[0]
            expected_format = constraint.value.strip().casefold()
            context_evidence = _context_evidence(f"/constraints/{constraint_index}/value", constraint.value)
            seen_format_spans: set[tuple[int, int]] = set()
            for directive in _FORMAT_DIRECTIVE_PATTERN.finditer(prompt):
                window_end = min(len(prompt), directive.end() + 48)
                for index in range(directive.end(), window_end):
                    if prompt[index] in "?!.\n":
                        window_end = index
                        break
                format_matches = list(_FORMAT_VALUE_PATTERN.finditer(prompt, directive.end(), window_end))
                for match in format_matches:
                    span = (match.start(), match.end())
                    if span in seen_format_spans or not scope.is_direct(directive.start(), match.end()):
                        continue
                    seen_format_spans.add(span)
                    requested = match.group().casefold()
                    if requested == expected_format:
                        continue
                    is_resolved_alternative = any(
                        candidate.group().casefold() == expected_format
                        and _FORMAT_ALTERNATIVE_SEPARATOR_PATTERN.fullmatch(
                            prompt[min(match.end(), candidate.end()) : max(match.start(), candidate.start())]
                        )
                        is not None
                        for candidate in format_matches
                    )
                    if is_resolved_alternative:
                        continue
                    seeds.append(
                        _FindingSeed(
                            "PF005",
                            "OUTPUT_FORMAT_CONFLICT",
                            _prompt_evidence(prompt, match.start(), match.end()),
                            "TYPED_FORMAT_CONSTRAINT",
                            context_evidence,
                            (),
                            "format-conflict:" + _sha_text(f"{requested}!={expected_format}"),
                        )
                    )

        sentence_matches = [
            item for item in _ONE_SENTENCE_PATTERN.finditer(prompt) if scope.is_direct(item.start(), item.end())
        ]
        paragraph_matches = [
            item for item in _THREE_PARAGRAPHS_PATTERN.finditer(prompt) if scope.is_direct(item.start(), item.end())
        ]
        if sentence_matches and paragraph_matches:
            first = sentence_matches[0]
            second = paragraph_matches[0]
            seeds.append(
                _FindingSeed(
                    "PF005",
                    "INTRINSIC_STRUCTURE_CONFLICT",
                    _prompt_evidence(prompt, first.start(), first.end()),
                    "MUTUALLY_EXCLUSIVE_CONSTRAINT",
                    _prompt_evidence(prompt, second.start(), second.end()),
                    (),
                    "one-sentence-v-three-paragraphs",
                )
            )

    unique: dict[tuple[Any, ...], _FindingSeed] = {}
    for seed in seeds:
        key = (
            seed.rule_id,
            json.dumps(_evidence_identity(seed.trigger), sort_keys=True),
            seed.discriminator,
        )
        unique.setdefault(key, seed)
    return sorted(unique.values(), key=_seed_sort_key)


def _materialize(
    prompt: str, prompt_sha256: str, seeds: Sequence[_FindingSeed]
) -> tuple[tuple[Finding, ...], tuple[Correction, ...]]:
    findings: list[Finding] = []
    corrections: list[Correction] = []
    for seed in seeds:
        meta = _RULE_META[seed.rule_id]
        finding_id = _finding_id(seed, prompt_sha256)
        correction_ids: tuple[str, ...] = ()
        if seed.edits:
            correction = _make_correction(prompt, finding_id, seed)
            corrections.append(correction)
            correction_ids = (correction.correction_id,)
        findings.append(
            Finding(
                finding_id,
                seed.rule_id,
                "1.0.0",
                meta.label,
                ScopeKind.DIRECT,
                seed.trigger_kind,
                seed.trigger,
                seed.proposition_kind,
                seed.proposition,
                seed.additional_evidence,
                meta.risk,
                meta.explanation,
                meta.suggestion,
                meta.confidence,
                meta.maturity,
                seed.enforcement or meta.enforcement,
                meta.related_output_modes,
                correction_ids,
            )
        )
    return tuple(findings), tuple(corrections)


def _preflight(
    request: Any,
    *,
    parent_fingerprint: str | None = None,
    applied_correction_id: str | None = None,
    relint_depth: int = 0,
) -> PreflightResult:
    metadata = _input_metadata(request)
    if not isinstance(request, PreflightRequest):
        return _early(
            metadata,
            Status.ERROR,
            "INVALID_REQUEST",
            "request must use the typed preflight model",
            parent_fingerprint=parent_fingerprint,
            applied_correction_id=applied_correction_id,
            relint_depth=relint_depth,
        )
    policy, enabled, required, policy_error = _validate_policy(request.policy)
    snippets_authorized = bool(policy and policy.include_snippets)
    lineage = {
        "parent_fingerprint": parent_fingerprint,
        "applied_correction_id": applied_correction_id,
        "relint_depth": relint_depth,
    }
    if policy_error is not None:
        return _early(
            metadata,
            Status.ERROR,
            policy_error[0],
            policy_error[1],
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    if not isinstance(request.prompt, str):
        return _early(
            metadata,
            Status.ERROR,
            "INVALID_PROMPT",
            "prompt must be a string",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    try:
        prompt_bytes = request.prompt.encode("utf-8")
    except UnicodeEncodeError:
        return _early(
            metadata,
            Status.ERROR,
            "INVALID_UTF8",
            "prompt is not valid UTF-8",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    if not request.prompt.strip():
        return _early(
            metadata,
            Status.ERROR,
            "EMPTY_INPUT",
            "prompt is empty",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    if len(prompt_bytes) > MAX_PROMPT_UTF8_BYTES:
        return _early(
            metadata,
            Status.ERROR,
            "INPUT_TOO_LARGE",
            "prompt exceeds 32 KiB",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    if not isinstance(request.language, str) or not request.language.strip() or not _is_utf8_text(request.language):
        return _early(
            metadata,
            Status.ERROR,
            "INVALID_LANGUAGE",
            "declared language is invalid",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    context, context_error = _validate_context(request.context)
    if context_error is not None:
        return _early(
            metadata,
            Status.ERROR,
            context_error[0],
            context_error[1],
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            context_pointer=context_error[2],
            **lineage,
        )
    assert context is not None and policy is not None
    if not enabled:
        return _result(
            metadata=metadata,
            status=Status.ALLOW,
            coverage=_coverage(enabled, required, CoverageState.NOT_REQUIRED, "no enabled rules"),
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    if request.language.casefold() != "en":
        return _coverage_unavailable(
            metadata,
            "UNSUPPORTED_LANGUAGE",
            "preflight-rules.v1 supports declared language en only",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    scope = analyze_scope(request.prompt)
    if scope.unavailable_reason is not None:
        return _coverage_unavailable(
            metadata,
            "UNSAFE_SCOPE",
            scope.unavailable_reason,
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )

    seeds = _detect(request.prompt, scope, context, enabled)
    findings, corrections = _materialize(request.prompt, metadata.sha256, seeds)
    findings_by_id = {finding.finding_id: finding for finding in findings}
    override_ids = {override.finding_id for override in policy.overrides}
    if not override_ids.issubset(findings_by_id):
        return _early(
            metadata,
            Status.ERROR,
            "UNKNOWN_OVERRIDE_TARGET",
            "override does not match a current finding",
            enabled=enabled,
            required=required,
            snippets_authorized=snippets_authorized,
            **lineage,
        )
    overrides = {override.finding_id: override.reason for override in policy.overrides}
    if overrides:
        findings = tuple(
            replace(
                finding,
                overridden=finding.finding_id in overrides,
                override_reason_sha256=(
                    _sha_text(overrides[finding.finding_id]) if finding.finding_id in overrides else None
                ),
            )
            for finding in findings
        )

    if any(
        finding.confidence is Confidence.EXACT and finding.enforcement is Enforcement.HOLD_ELIGIBLE
        for finding in findings
    ):
        status = Status.HOLD
    elif findings:
        status = Status.NOTICE
    else:
        status = Status.ALLOW
    return _result(
        metadata=metadata,
        status=status,
        coverage=_coverage(enabled, required, CoverageState.FULL, "completed"),
        findings=findings,
        corrections=corrections,
        snippets_authorized=snippets_authorized,
        **lineage,
    )


def preflight_text(request: PreflightRequest) -> PreflightResult:
    """Analyze the present prompt and explicit context without I/O or provider calls."""

    return _preflight(request)


def apply_correction(
    request: PreflightRequest,
    result: PreflightResult,
    correction_id: str,
) -> tuple[str, PreflightResult]:
    """Apply one source-bound in-memory correction and perform exactly one re-lint."""

    if not isinstance(request, PreflightRequest) or not isinstance(result, PreflightResult):
        raise CorrectionError("correction inputs must use typed preflight models")
    if result.relint_depth != 0:
        raise CorrectionError("only one correction re-lint is allowed")
    if (
        result.schema_version != SCHEMA_VERSION
        or result.engine_version != ENGINE_VERSION
        or result.rule_bundle_version != RULE_BUNDLE_VERSION
    ):
        raise CorrectionError("correction result version does not match this engine")
    if not isinstance(request.prompt, str):
        raise CorrectionError("correction source is invalid")
    source_sha = _sha_text(request.prompt)
    if result.input.sha256 != source_sha:
        raise CorrectionError("request source hash does not match preflight result")
    correction = next(
        (item for item in result.corrections if item.correction_id == correction_id),
        None,
    )
    if correction is None:
        raise CorrectionError("unknown correction identifier")
    if correction.source_sha256 != source_sha:
        raise CorrectionError("correction source hash does not match")
    if (
        correction.schema_version != SCHEMA_VERSION
        or correction.engine_version != ENGINE_VERSION
        or correction.rule_bundle_version != RULE_BUNDLE_VERSION
    ):
        raise CorrectionError("correction version does not match this engine")
    finding = next(
        (item for item in result.findings if item.finding_id == correction.finding_id),
        None,
    )
    if finding is None or correction.correction_id not in finding.correction_ids:
        raise CorrectionError("correction provenance is not present in the result")
    corrected = _apply_edits(request.prompt, correction.edits)
    if _sha_text(corrected) != correction.result_sha256:
        raise CorrectionError("corrected result hash does not match")
    corrected_request = replace(request, prompt=corrected)
    relint = _preflight(
        corrected_request,
        parent_fingerprint=result.fingerprint,
        applied_correction_id=correction.correction_id,
        relint_depth=1,
    )
    return corrected, relint
