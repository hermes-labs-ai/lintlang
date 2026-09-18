"""H2-H7 detection heuristics, the H1-H7 rule registry, and the compatible
import surface for `lintlang.patterns`.

Shared models live in `lintlang.models`; H1 lives in `lintlang.detectors.h1`.
Both are re-exported below: every name that has ever been importable from this
module still is, including the private helpers the test suite imports directly.
Do not remove a re-export without checking `tests/test_patterns_compat.py`.

Each registry entry has:
- id: H1-H7
- name: Human-readable name
- detect(config): Returns list of Finding objects
"""

from __future__ import annotations

import re

from .detectors.h1 import VAGUE_WORDS as VAGUE_WORDS
from .detectors.h1 import _differentia as _differentia
from .detectors.h1 import _meaning_terms as _meaning_terms
from .detectors.h1 import _word_overlap as _word_overlap
from .detectors.h1 import detect_h1
from .models import AgentConfig, Finding, Severity
from .models import SourceRegion as SourceRegion
from .models import ToolDef as ToolDef
from .preflight.models import ScopeKind
from .preflight.scope import ScopeAnalysis, analyze_scope


def _is_direct_match(scope: ScopeAnalysis, start: int, end: int) -> bool:
    """Return whether a match is live text, preserving detection if classification fails."""
    return scope.unavailable_reason is not None or scope.is_direct(start, end)


def _is_h5_negative_match(scope: ScopeAnalysis, start: int, end: int) -> bool:
    """Keep H5 negative directives operative while excluding quoted and non-operative text."""
    return scope.unavailable_reason is not None or (
        0 <= start < end <= len(scope.scopes)
        and all(kind in {ScopeKind.DIRECT, ScopeKind.NEGATED} for kind in scope.scopes[start:end])
    )


# ── H2: Missing Constraint Scaffolding ─────────────────────────────


CONSTRAINT_SIGNALS = [
    "max_iterations",
    "max_retries",
    "retry_limit",
    "timeout",
    "max_turns",
    "max_steps",
    "budget",
    "limit",
    "terminate",
    "stop_condition",
    "exit_condition",
    "max_tokens",
]

_RETRY_UNTIL_PATTERN = r"retry\s+(?:until|as\s+many\s+times)"
_LOOP_OVER_THROUGH_PATTERN = r"loop\s+(?:through|over)"


DANGEROUS_PATTERNS = [
    (r"keep\s+trying\s+until", "Unbounded retry loop — 'keep trying until' needs an explicit limit."),
    (_RETRY_UNTIL_PATTERN, "Unbounded retry — add max_retries or a fallback."),
    (r"don'?t\s+stop\s+until", "Negative termination condition — rephrase as a positive bound."),
    (r"loop\s+until", "Potential infinite loop — ensure a max iteration count."),
    (_LOOP_OVER_THROUGH_PATTERN, "Potential infinite loop — ensure a max iteration count."),
    (r"continue\s+(?:until|indefinitely)", "Unbounded continuation — add an explicit termination condition."),
]


_SUCCESS_CRITERIA_PREFIX = re.compile(
    r"\b(?:define|set|state|establish)\s+(?:clear\s+)?success\s+criteria\s*\.\s*$",
    re.IGNORECASE,
)
_VERIFICATION_GUIDANCE = re.compile(
    r"\bverify\s*:\s*\S|\b(?:write|run|ensure)\s+(?:[\w-]+\s+){0,6}(?:tests?|checks?)\b",
    re.IGNORECASE,
)
_NEGATED_RETRY_PROHIBITION = re.compile(r"\b(?:never|do\s+not|don'?t)\s+$", re.IGNORECASE)
_UNBOUNDED_CONTINUATION_SIGNALS = re.compile(
    r"\b(?:indefinitely|forever|endlessly|continuously|perpetually|non-?stop|without\s+(?:end|stopping|limit))\b",
    re.IGNORECASE,
)
# Allow up to two adverbial modifiers between the negator and ``loop``
# ("don't continuously loop", "never ever loop"), but not arbitrary words, so
# "never give up and loop ... forever" is still an instruction, not a prohibition.
_NEGATED_UNBOUNDED_LOOP = re.compile(
    r"\b(?:never|do\s+not|don'?t|should\s+not)(?:\s+(?!only\b)(?:\w+ly|ever)\b){0,2}\s*$",
    re.IGNORECASE,
)


_CLAUSE_BOUNDARY = re.compile(
    r"[.!?](?=\s|$)|[;\n]|,\s*(?:and|but|or|so|then|while|whereas)\b",
    re.IGNORECASE,
)


def _immediate_clause(text: str, start: int, limit: int = 80) -> str:
    """Return text from ``start`` up to the nearest sentence or clause boundary.

    Qualifier signals for a matched phrase must come from the phrase's own
    clause; a later sentence, semicolon clause, or coordinated clause says
    nothing about it.
    """
    window = text[start : start + limit]
    boundary = _CLAUSE_BOUNDARY.search(window)
    return window[: boundary.start()] if boundary else window


def _is_negated_retry_prohibition(text: str, retry_start: int) -> bool:
    """Return whether an adjacent negation forbids, rather than requires, retrying."""
    prefix = text[max(0, retry_start - 20) : retry_start]
    return bool(_NEGATED_RETRY_PROHIBITION.search(prefix))


def _is_unbounded_loop_traversal(text: str, match: re.Match[str]) -> bool:
    """Return whether ``loop over/through`` describes an unbounded loop, not enumeration.

    ``loop over`` and ``loop through`` ordinarily introduce enumeration of a
    finite collection ("loop through the search results") — that is normal
    control flow, not a missing-constraint risk. Only treat it as a potential
    infinite loop when the same clause also carries an explicit indefinite-
    continuation signal (e.g. "loop over tasks indefinitely").
    """
    window = _immediate_clause(text, match.end())
    signal = _UNBOUNDED_CONTINUATION_SIGNALS.search(window)
    if signal is None:
        return False

    # A prohibition such as "do not loop over the queue indefinitely" must
    # not be treated as an instruction to run indefinitely. Check both a
    # negation immediately before the traversal and one attached to the
    # continuation signal later in the same clause.
    before_match = text[max(0, match.start() - 40) : match.start()]
    # Only a negation in the traversal's own clause counts.
    before_match = re.split(r"[.!?;,\n]", before_match)[-1]
    if _NEGATED_UNBOUNDED_LOOP.search(before_match):
        return False
    before_signal = window[: signal.start()]
    return not re.search(
        r"\b(?:never|do\s+not|don'?t|should\s+not)\b(?:\s+\w+){0,6}\s*$",
        before_signal,
        re.IGNORECASE,
    )


def _is_bounded_verification_loop(text: str, match: re.Match[str]) -> bool:
    """Recognize a documented verification loop with an explicit local exit.

    ``loop until`` is usually an unsafe open-ended instruction.  The specific
    ``Define success criteria. Loop until verified.`` form is different only
    when the immediately surrounding guidance also names a concrete check.
    Keep this deliberately narrow: it does not exempt retries, negative
    termination, or a bare promise to define criteria.
    """
    if match.group().lower().split() != ["loop", "until"]:
        return False

    if not re.match(r"\s+verified\b", text[match.end() :], re.IGNORECASE):
        return False

    prefix = text[max(0, match.start() - 160) : match.start()]
    guidance = text[match.end() : match.end() + 600]
    return bool(_SUCCESS_CRITERIA_PREFIX.search(prefix) and _VERIFICATION_GUIDANCE.search(guidance))


def detect_h2(config: AgentConfig) -> list[Finding]:
    """Detect missing constraint scaffolding."""
    findings: list[Finding] = []

    # Check system prompt for constraint keywords
    prompt = config.system_prompt.lower()
    constraints = config.constraints

    has_any_constraint = False
    constraints_str = str(constraints).lower()
    for signal in CONSTRAINT_SIGNALS:
        pattern = rf"\b{re.escape(signal)}\b"
        if re.search(pattern, prompt) or re.search(pattern, constraints_str):
            has_any_constraint = True
            break

    if config.system_prompt and not has_any_constraint and len(config.tools) > 0:
        findings.append(
            Finding(
                pattern_id="H2",
                pattern_name="Missing Constraint Scaffolding",
                severity=Severity.HIGH,
                location="system_prompt",
                description="System prompt defines tools but contains no termination conditions, retry budgets, or progress checks.",
                suggestion="Add explicit constraints: 'You have a maximum of 5 tool calls per task. If no progress after 2 attempts, stop and report the issue.'",
            )
        )

    # Check for dangerous unbounded patterns
    text = config.system_prompt
    scope = analyze_scope(text)
    for pattern, message in DANGEROUS_PATTERNS:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        for match in matches:
            if not _is_direct_match(scope, match.start(), match.end()):
                continue
            if _is_bounded_verification_loop(text, match):
                continue
            if pattern == _RETRY_UNTIL_PATTERN and _is_negated_retry_prohibition(text, match.start()):
                continue
            if pattern == _LOOP_OVER_THROUGH_PATTERN and not _is_unbounded_loop_traversal(text, match):
                continue
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 40)
            findings.append(
                Finding(
                    pattern_id="H2",
                    pattern_name="Missing Constraint Scaffolding",
                    severity=Severity.CRITICAL,
                    location="system_prompt",
                    description=message,
                    suggestion="Add an explicit bound: max iterations, timeout, or fallback behavior.",
                    evidence=text[start:end].strip(),
                )
            )

    return findings


# ── H3: Schema-Intent Mismatch ─────────────────────────────────────

GENERIC_PROP_NAMES = {"data", "value", "result", "output", "input", "item", "obj", "payload"}


def detect_h3(config: AgentConfig) -> list[Finding]:
    """Detect schema-intent mismatches."""
    findings: list[Finding] = []

    for tool in config.tools:
        params = tool.parameters
        if not params:
            continue

        properties = params.get("properties", {})
        required_list = params.get("required", [])

        # Phantom required fields
        for req_name in required_list:
            if req_name not in properties:
                findings.append(
                    Finding(
                        pattern_id="H3",
                        pattern_name="Schema-Intent Mismatch",
                        severity=Severity.HIGH,
                        location=f"tool:{tool.name}.parameters.required",
                        description=f"Required field '{req_name}' in tool '{tool.name}' does not exist in properties.",
                        suggestion=f"Either add '{req_name}' to properties or remove it from required.",
                    )
                )

        _check_properties(findings, tool.name, properties, "parameters")

    # Check schemas list too
    for i, schema in enumerate(config.schemas):
        props = schema.get("properties", {})
        for prop_name, prop_def in props.items():
            if "description" not in prop_def and prop_name.lower() in GENERIC_PROP_NAMES:
                findings.append(
                    Finding(
                        pattern_id="H3",
                        pattern_name="Schema-Intent Mismatch",
                        severity=Severity.MEDIUM,
                        location=f"schema[{i}].{prop_name}",
                        description=f"Schema property '{prop_name}' is generic and undescribed.",
                        suggestion="Add specific descriptions to help the LLM understand the semantic intent.",
                    )
                )

    return findings


def _check_properties(findings: list[Finding], tool_name: str, properties: dict, path: str) -> None:
    """Check properties for schema-intent issues, including nested objects."""
    for prop_name, prop_def in properties.items():
        full_path = f"{path}.{prop_name}"

        # Missing description on parameter
        if "description" not in prop_def:
            findings.append(
                Finding(
                    pattern_id="H3",
                    pattern_name="Schema-Intent Mismatch",
                    severity=Severity.MEDIUM,
                    location=f"tool:{tool_name}.{full_path}",
                    description=f"Parameter '{prop_name}' in tool '{tool_name}' has no description.",
                    suggestion="Add a description explaining what this parameter means semantically, not just its type.",
                )
            )

        # Generic property names
        if prop_name.lower() in GENERIC_PROP_NAMES:
            findings.append(
                Finding(
                    pattern_id="H3",
                    pattern_name="Schema-Intent Mismatch",
                    severity=Severity.LOW,
                    location=f"tool:{tool_name}.{full_path}",
                    description=f"Parameter '{prop_name}' in tool '{tool_name}' uses a generic name.",
                    suggestion=f"Rename '{prop_name}' to something specific: e.g., 'user_email' instead of 'data', 'search_query' instead of 'input'.",
                )
            )

        # anyOf/oneOf without descriptions
        for union_key in ("anyOf", "oneOf"):
            if union_key in prop_def:
                variants = prop_def[union_key]
                undescribed = [v for v in variants if "description" not in v]
                if undescribed:
                    findings.append(
                        Finding(
                            pattern_id="H3",
                            pattern_name="Schema-Intent Mismatch",
                            severity=Severity.HIGH,
                            location=f"tool:{tool_name}.{full_path}",
                            description=f"Parameter '{prop_name}' has {union_key} with {len(undescribed)}/{len(variants)} undescribed variants.",
                            suggestion=f"Add a description to each {union_key} variant explaining WHEN to use it. Without this, the LLM has no basis for choosing.",
                        )
                    )

        # Recurse into nested object properties
        if prop_def.get("type") == "object" and "properties" in prop_def:
            _check_properties(findings, tool_name, prop_def["properties"], full_path)


# ── H4: Context Boundary Erosion ───────────────────────────────────

BOUNDARY_SIGNALS = [
    "current task",
    "task boundary",
    "context window",
    "conversation scope",
    "session",
    "thread",
    "isolated",
    "separate context",
    "new conversation",
    "clear history",
    "reset context",
    "independent",
    "do not reference",
    "do not carry",
    "don't carry",
    "previous task",
    "per query",
    "per request",
    "scope",
    "boundary",
]

_ALWAYS_PERSIST_PATTERN = r"always\s+(?:keep|maintain|remember)"

EROSION_PATTERNS = [
    (r"remember\s+everything", "Unbounded memory — context will grow until it erodes task boundaries."),
    (
        r"use\s+(?:all|entire)\s+(?:conversation|history|context)",
        "Referencing entire history without scoping — promotes boundary erosion.",
    ),
    (_ALWAYS_PERSIST_PATTERN, "Persistence without scope — specify WHAT to persist and for HOW LONG."),
]

_CROSS_CONTEXT_PERSISTENCE_SIGNALS = re.compile(
    r"\b(?:context|history|conversation|memory|session|thread|"
    r"(?:prior|previous|past|earlier)\s+(?:[\w'-]+\s+){0,2}?"
    r"(?:state|sessions?|tasks?|turns?|requests?|conversations?|contexts?|messages?|"
    r"results?|interactions?|exchanges?|answers?|responses?|outputs?|chats?)|"
    r"from\s+(?:before|earlier)|"
    r"carry(?:ing|over)?|cross[- ]?(?:task|session|turn|request)|"
    r"across\s+(?:tasks?|sessions?|turns?|requests?)|between\s+(?:tasks?|sessions?|turns?|requests?)|"
    r"what\s+(?:the\s+)?user\s+(?:said|told|asked))\b",
    re.IGNORECASE,
)


def _is_cross_context_persistence(text: str, match: re.Match[str]) -> bool:
    """Return whether ``always keep/maintain/remember`` targets cross-context state.

    The verb alone is ambiguous: "always maintain backward compatibility" or
    "always keep responses under 200 words" state a domain invariant, not an
    instruction to carry state across tasks or sessions. Only flag it when the
    object names context, memory, history, prior state/results, or cross-task/
    session carryover within the same clause. Bare temporal words such as
    "before" ("keep results sorted before returning them") are not evidence.
    """
    window = _immediate_clause(text, match.end())
    return bool(_CROSS_CONTEXT_PERSISTENCE_SIGNALS.search(window))


def detect_h4(config: AgentConfig) -> list[Finding]:
    """Detect context boundary erosion risks."""
    findings: list[Finding] = []
    prompt = config.system_prompt

    if prompt:
        scope = analyze_scope(prompt)

        # Check for boundary markers (word boundary matching)
        has_boundary = any(
            _is_direct_match(scope, match.start(), match.end())
            for signal in BOUNDARY_SIGNALS
            for match in re.finditer(rf"\b{re.escape(signal)}\b", prompt, re.IGNORECASE)
        )

        if len(prompt) > 500 and not has_boundary:
            findings.append(
                Finding(
                    pattern_id="H4",
                    pattern_name="Context Boundary Erosion",
                    severity=Severity.MEDIUM,
                    location="system_prompt",
                    description="Long system prompt with no context boundary markers.",
                    suggestion="Add explicit boundary markers: 'Each user message is an independent task. Do not carry state from previous tasks unless explicitly told to.'",
                )
            )

        # Check for erosion patterns
        for pattern, message in EROSION_PATTERNS:
            matches = list(re.finditer(pattern, prompt, re.IGNORECASE))
            for match in matches:
                if not _is_direct_match(scope, match.start(), match.end()):
                    continue
                if pattern == _ALWAYS_PERSIST_PATTERN and not _is_cross_context_persistence(prompt, match):
                    continue
                start = max(0, match.start() - 20)
                end = min(len(prompt), match.end() + 40)
                findings.append(
                    Finding(
                        pattern_id="H4",
                        pattern_name="Context Boundary Erosion",
                        severity=Severity.HIGH,
                        location="system_prompt",
                        description=message,
                        suggestion="Scope what should be remembered: 'Remember the user's name for this session. Do not carry tool results between tasks.'",
                        evidence=prompt[start:end].strip(),
                    )
                )

    # Check messages for flat structure without boundary markers
    messages = config.messages
    if len(messages) > 10:
        has_system_boundary = any(
            m.get("role") == "system"
            and any(s in m.get("content", "").lower() for s in ["new task", "task boundary", "---"])
            for m in messages
        )
        if not has_system_boundary:
            findings.append(
                Finding(
                    pattern_id="H4",
                    pattern_name="Context Boundary Erosion",
                    severity=Severity.MEDIUM,
                    location="messages",
                    description=f"Message history has {len(messages)} messages with no task boundary markers.",
                    suggestion="Insert system messages between tasks: {'role': 'system', 'content': '--- New Task ---'}",
                )
            )

    return findings


# ── H5: Implicit Instruction Failure ───────────────────────────────

NEGATIVE_PATTERNS = [
    (r"\bdon'?t\b", "Negative instruction"),
    (r"\bnever\b", "Negative instruction"),
    (r"\bavoid\b", "Negative instruction"),
    (r"\bdo\s+not\b", "Negative instruction"),
]

# ── Layer 1: Structural exemptions ────────────────────────────────
# Precompiled regexes for regions where negatives should be ignored entirely.
# HTML comments, fenced code blocks, and template/generated-file markers.
_STRUCTURAL_EXEMPT_REGIONS: list[re.Pattern[str]] = [
    re.compile(r"<!--.*?-->", re.DOTALL),  # HTML comments
    re.compile(r"```.*?```", re.DOTALL),  # Fenced code blocks
    re.compile(r"`[^`\n]+`"),  # Inline code spans
    re.compile(r"(?:DO NOT EDIT|GENERATED|AUTO-GENERATED)[^\n]*", re.IGNORECASE),  # Generated-file markers
]

# ── Layer 2: Phrase-level exemptions ──────────────────────────────
# Regex patterns for negatives that are idiomatic, descriptive, or non-instructional.
# Each is compiled once; a match anywhere around the negative text exempts it.
H5_PHRASE_EXEMPTIONS: list[re.Pattern[str]] = [
    # Privacy / telemetry disclaimers
    re.compile(r"never\s+(?:sent|shared|stored|transmitted|collected|uploaded|tracked|leaves)", re.IGNORECASE),
    # Idiomatic / deliberate style (specific-object phrases)
    re.compile(
        r"don'?t\s+(?:cry\s+wolf|dance\s+around|reinvent|overthink|overengineer|second.guess|sugar.coat|sweat)",
        re.IGNORECASE,
    ),
    # UI / button labels — negatives inside quoted strings that look like choices
    re.compile(
        r'["\u201c](?:Never\s+ask\s+again|Not?\s+now|Don\'?t\s+show\s+again|Don\'?t\s+remind)["\u201d]', re.IGNORECASE
    ),
    # Descriptive / explanatory text (third-person subject + negative verb — describing state, not instructing)
    # Excludes "I" and "you" which commonly appear in direct agent behavioral instructions.
    re.compile(
        r"\b(?:it|we|they|that|this|there|the\s+\w+)\s+(?:don'?t|doesn'?t|didn'?t|won'?t|can'?t|couldn'?t|isn'?t|aren'?t|wasn'?t|haven'?t|hasn'?t)\b",
        re.IGNORECASE,
    ),
    # "do not edit" / "do not modify" markers (build system boilerplate)
    re.compile(r"do\s+not\s+(?:edit|modify|change|touch|remove|delete)\s+(?:directly|manually|this)", re.IGNORECASE),
    # "avoid" in non-instruction context (e.g., "to avoid confusion", "avoid false positives")
    re.compile(r"\bto\s+avoid\b", re.IGNORECASE),
    # Negatives inside array/list literals: ["...", "Never ask again", ...]
    re.compile(r'\[(?:[^\]]*,\s*)?["\u201c][^"\u201d]*(?:never|don\'?t|not\s+now)[^"\u201d]*["\u201d]', re.IGNORECASE),
]

# Safety/constraint keywords — negative instructions near these are EXEMPT from H5 flagging
# Covers: security, authorization, accuracy, policy/business rules
SAFETY_CONTEXT_KEYWORDS = {
    # Security
    "api key",
    "api_key",
    "secret",
    "password",
    "credential",
    "token",
    "auth",
    "permission",
    "authorize",
    "authorization",
    "authenticated",
    "security",
    "secure",
    "sensitive",
    "private",
    "confidential",
    "protected",
    "dangerous",
    "destructive",
    "delete",
    "drop",
    "overwrite",
    "truncate",
    "production",
    "prod",
    "execute",
    "eval",
    "exec",
    "code",
    "share",
    "expose",
    "leak",
    "disclose",
    "external",
    "public",
    "sql injection",
    "xss",
    "cve",
    "vulnerability",
    "attack",
    # Authorization / approval gates
    "approval",
    "approved",
    "review",
    "reviewed",
    "confirmation",
    "confirm",
    "without",
    "manager",
    "supervisor",
    "admin",
    # Accuracy / methodology constraints
    "estimate",
    "guess",
    "hallucinate",
    "fabricate",
    "make up",
    "invent",
    "assume",
    "speculate",
    "infer",
    "combine",
    "unrelated",
    "extrapolate",
    "correlation",
    "causation",
    "cherry-pick",
    "cherry pick",
    "outlier",
    "preliminary",
    "findings",
    "data",
    # Policy / business rules
    "promise",
    "guarantee",
    "commit",
    "warrant",
    "assure",
    "refund",
    "pricing",
    "competitor",
    "internal",
    "investment",
    "recommendation",
    "legal",
    "medical",
    "financial",
    "advice",
    "liability",
    # Content moderation
    "hate speech",
    "explicit",
    "sexually",
    "violence",
    "approve",
    "content",
    "moderate",
    "moderation",
    "flag",
    "manual review",
    # Scope constraints
    "reference",
    "previous",
    "prior",
    "history",
    "context",
    # Safety actions
    "irreversible",
    "damage",
    "command",
    "test",
    "tests",
    "break",
    "modify",
    "workspace",
    "directory",
    "file",
    "system",
}

VAGUE_QUALIFIERS = [
    # "be + adjective" with no operational definition
    (r"\bbe\s+(?:concise|brief|helpful|careful|thorough|creative|professional)\b", "Vague qualitative instruction"),
    (r"\bbe\s+(?:smart|natural|aggressive|adversarial|rigorous|pragmatic|nuanced)\b", "Vague qualitative instruction"),
    (
        r"\bbe\s+(?:appropriate|reasonable|responsible|respectful|transparent|consistent)\b",
        "Vague qualitative instruction",
    ),
    # Human-level inference
    (
        r"\buse\s+(?:common\s+sense|good\s+judgment|your\s+best\s+judgment|your\s+discretion)\b",
        "Assumes human-level inference",
    ),
    # Ambiguous conditionals
    (r"\bas\s+(?:needed|appropriate|necessary)\b", "Ambiguous conditional — 'as needed' by whose criteria?"),
    (r"\bwhen\s+(?:appropriate|necessary|relevant|possible)\b", "Ambiguous conditional"),
    (r"\bif\s+(?:appropriate|necessary|relevant|needed)\b", "Ambiguous conditional"),
    # Figurative verbs — almost never have operational definitions
    (r"\b(?:dance|shy|shying)\s+around\b", "Figurative verb — no operational definition"),
    (r"\blean\s+into\b", "Figurative verb — no operational definition"),
    (r"\bdouble\s+down\s+on\b", "Figurative verb — no operational definition"),
    (r"\bpush\s+back\s+on\b", "Figurative verb — no operational definition"),
    (r"\berr\s+on\s+the\s+side\s+of\b", "Figurative verb — no operational definition"),
    (r"\bkeep\s+(?:it|things)\s+(?:simple|clean|tight|short)\b", "Vague qualitative instruction"),
]


def detect_h5(config: AgentConfig) -> list[Finding]:
    """Detect implicit instruction failures."""
    findings: list[Finding] = []
    prompt = config.system_prompt

    if not prompt:
        return findings

    scope = analyze_scope(prompt)

    # Negative instructions — layered exemption filtering
    neg_matches = []
    for pattern, _category in NEGATIVE_PATTERNS:
        matches = list(re.finditer(pattern, prompt, re.IGNORECASE))
        for match in matches:
            if not _is_h5_negative_match(scope, match.start(), match.end()):
                continue
            neg_matches.append((match.start(), match.end(), match.group()))

    # ── Layer 1: Build set of structurally-exempt character ranges ──
    exempt_ranges: list[tuple[int, int]] = []
    for region_re in _STRUCTURAL_EXEMPT_REGIONS:
        for m in region_re.finditer(prompt):
            exempt_ranges.append((m.start(), m.end()))

    # ── Layered filtering ──────────────────────────────────────────
    safety_context_window = 100  # chars before/after — covers most full sentences
    legitimate_negatives = 0  # negatives exempted (these are GOOD)
    problematic_negatives = []  # negatives NOT exempted

    for neg_start, neg_end, neg_text in neg_matches:
        # Layer 1: Skip if inside a structurally-exempt region
        if any(rs <= neg_start and neg_end <= re for rs, re in exempt_ranges):
            legitimate_negatives += 1
            continue

        # Layer 2: Skip if the surrounding text matches a known-good phrase
        phrase_window = 80  # chars around the negative to check
        phrase_start = max(0, neg_start - phrase_window)
        phrase_end = min(len(prompt), neg_end + phrase_window)
        phrase_ctx = prompt[phrase_start:phrase_end]

        if any(pat.search(phrase_ctx) for pat in H5_PHRASE_EXEMPTIONS):
            legitimate_negatives += 1
            continue

        # Layer 3 (fallback): Skip if near a safety keyword
        context_start = max(0, neg_start - safety_context_window)
        context_end = min(len(prompt), neg_end + safety_context_window)
        context = prompt[context_start:context_end].lower()

        in_safety_context = any(keyword in context for keyword in SAFETY_CONTEXT_KEYWORDS)

        if in_safety_context:
            legitimate_negatives += 1
        else:
            problematic_negatives.append((neg_start, neg_text))

    # Flag problematic negatives (those NOT near safety keywords)
    if len(problematic_negatives) > 3:
        findings.append(
            Finding(
                pattern_id="H5",
                pattern_name="Implicit Instruction Failure",
                severity=Severity.MEDIUM,
                location="system_prompt",
                description=f"System prompt has {len(problematic_negatives)} negative instructions ('don't', 'never', 'avoid'). Models follow positive instructions more reliably.",
                suggestion="Rewrite negatives as positives. Instead of 'Don't apologize', use 'Respond directly without apologies'. Instead of 'Never make up data', use 'Only cite data from provided context'.",
            )
        )

    # Optionally flag each problematic negative individually (helps with targeted fixes)
    for neg_start, neg_text in problematic_negatives[:2]:  # Show first 2 examples
        start = max(0, neg_start - 30)
        end = min(len(prompt), neg_start + 60)
        evidence = prompt[start:end].strip()
        findings.append(
            Finding(
                pattern_id="H5",
                pattern_name="Implicit Instruction Failure",
                severity=Severity.LOW,
                location="system_prompt",
                description=f"Negative instruction '{neg_text}' could be reframed positively.",
                suggestion=f"Instead of '{neg_text}...', specify what TO do. Example context: '{evidence}'",
                evidence=evidence,
            )
        )

    # Vague qualifiers (deduplicate identical matched text)
    seen_vague: set[str] = set()
    for pattern, category in VAGUE_QUALIFIERS:
        matches = list(re.finditer(pattern, prompt, re.IGNORECASE))
        for match in matches:
            if not _is_direct_match(scope, match.start(), match.end()):
                continue
            key = match.group().lower()
            if key in seen_vague:
                continue
            seen_vague.add(key)
            start = max(0, match.start() - 20)
            end = min(len(prompt), match.end() + 30)
            findings.append(
                Finding(
                    pattern_id="H5",
                    pattern_name="Implicit Instruction Failure",
                    severity=Severity.LOW,
                    location="system_prompt",
                    description=f"{category}: '{match.group()}'",
                    suggestion="Make it procedural. Instead of 'be concise', specify 'Respond in 2-3 sentences maximum'. Instead of 'as needed', specify the exact condition.",
                    evidence=prompt[start:end].strip(),
                )
            )

    # Check for conflicting instructions without priority
    has_priority = any(
        keyword in prompt.lower()
        for keyword in ["priority", "most important", "above all", "first and foremost", "override"]
    )
    # Count instructions more accurately (sentence-ending periods + list items)
    instruction_count = (
        len(re.findall(r"[.!?]\s+[A-Z]", prompt)) + prompt.count("\n-") + prompt.count("\n*") + prompt.count("\n1")
    )
    if instruction_count > 10 and not has_priority:
        findings.append(
            Finding(
                pattern_id="H5",
                pattern_name="Implicit Instruction Failure",
                severity=Severity.MEDIUM,
                location="system_prompt",
                description=f"System prompt has ~{instruction_count} instructions with no explicit priority ordering.",
                suggestion="Add priority ordering: 'PRIORITY 1: Always cite sources. PRIORITY 2: Be concise. When these conflict, prioritize accuracy over brevity.'",
            )
        )

    return findings


# ── H6: Template Format Contract Violation ─────────────────────────


def detect_h6(config: AgentConfig) -> list[Finding]:
    """Detect template format contract violations."""
    findings: list[Finding] = []
    prompt = config.system_prompt

    if not prompt:
        return findings

    # Build a cleaned version of the prompt that strips out non-instructional
    # format references (code blocks, inline code, filenames, CLI flags) to
    # reduce false positives when counting output-format keywords.
    cleaned = re.sub(r"```[^`]*```", " ", prompt, flags=re.DOTALL)  # fenced code blocks
    cleaned = re.sub(r"`[^`]+`", " ", cleaned)  # inline code
    cleaned = re.sub(r"\w+\.(?:json|yaml|yml|xml|md|toml|csv)\b", " ", cleaned, flags=re.IGNORECASE)  # filenames
    cleaned = re.sub(r"--(?:json|format|output)(?:\s+\w+)?", " ", cleaned, flags=re.IGNORECASE)  # CLI flags

    # Mixed format instructions
    has_json = bool(re.search(r"\bjson\b", cleaned, re.IGNORECASE))
    has_markdown = bool(re.search(r"\bmarkdown\b", cleaned, re.IGNORECASE))
    has_xml = bool(re.search(r"\bxml\b", cleaned, re.IGNORECASE))
    format_count = sum([has_json, has_markdown, has_xml])

    if format_count > 1:
        formats = [f for f, present in [("JSON", has_json), ("Markdown", has_markdown), ("XML", has_xml)] if present]
        findings.append(
            Finding(
                pattern_id="H6",
                pattern_name="Template Format Contract Violation",
                severity=Severity.MEDIUM,
                location="system_prompt",
                description=f"System prompt references multiple output formats ({', '.join(formats)}) — model may produce hybrid output.",
                suggestion="Specify ONE primary output format per response type, or clearly delineate: 'For data queries, respond in JSON. For explanations, use Markdown.'",
            )
        )

    # No output format specification at all
    has_output_format = bool(
        re.search(
            r"(?:respond|output|return|format|reply)\s+(?:in|as|with|using)\s+(?:json|markdown|xml|yaml|text|plain|html|csv)",
            prompt,
            re.IGNORECASE,
        )
    )
    has_format_example = bool(re.search(r"```|example\s*(?:output|response)", prompt, re.IGNORECASE))

    if len(prompt) > 200 and not has_output_format and not has_format_example:
        findings.append(
            Finding(
                pattern_id="H6",
                pattern_name="Template Format Contract Violation",
                severity=Severity.LOW,
                location="system_prompt",
                description="System prompt has no explicit output format specification or example.",
                suggestion="Add an output format contract: 'Always respond in JSON with keys: answer, confidence, sources.' Or provide an example output.",
            )
        )

    # Check for versioning
    has_version = bool(
        re.search(r"(?:^|\s)v\d+\.\d|version\s*[:\d]|prompt\s*v\d", prompt, re.IGNORECASE | re.MULTILINE)
    )
    if len(prompt) > 500 and not has_version:
        findings.append(
            Finding(
                pattern_id="H6",
                pattern_name="Template Format Contract Violation",
                severity=Severity.INFO,
                location="system_prompt",
                description="Long system prompt with no version marker.",
                suggestion="Add a version comment (e.g., '# Prompt v2.1 — 2024-01-15') to track prompt changes and enable A/B testing.",
            )
        )

    return findings


# ── H7: Role Confusion ────────────────────────────────────────────


def detect_h7(config: AgentConfig) -> list[Finding]:
    """Detect role confusion in message sequences."""
    findings: list[Finding] = []
    messages = config.messages

    if not messages:
        return findings

    system_count = sum(1 for m in messages if m.get("role") == "system")

    # Multiple system messages
    if system_count > 1:
        findings.append(
            Finding(
                pattern_id="H7",
                pattern_name="Role Confusion",
                severity=Severity.HIGH,
                location="messages",
                description=f"Message history has {system_count} system messages. Most models expect exactly one system message at the start.",
                suggestion="Consolidate into a single system message, or use the framework's dedicated system prompt field.",
            )
        )

    # Check alternation
    prev_role = None
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")

        # System message not at start
        if role == "system" and i > 0 and prev_role != "system":
            findings.append(
                Finding(
                    pattern_id="H7",
                    pattern_name="Role Confusion",
                    severity=Severity.MEDIUM,
                    location=f"messages[{i}]",
                    description=f"System message at position {i} (not at the start).",
                    suggestion="Move system instructions to the first message, or use a dedicated system prompt field.",
                )
            )

        # Consecutive same-role messages (user-user or assistant-assistant)
        if role == prev_role and role in ("user", "assistant"):
            findings.append(
                Finding(
                    pattern_id="H7",
                    pattern_name="Role Confusion",
                    severity=Severity.MEDIUM,
                    location=f"messages[{i}]",
                    description=f"Consecutive '{role}' messages at positions {i - 1} and {i}. Most APIs expect alternating user/assistant.",
                    suggestion="Merge consecutive same-role messages, or insert the expected alternating role between them.",
                )
            )

        # Tool result without tool_use
        if role == "tool":
            # Look back for a preceding tool_use
            has_preceding_tool_use = False
            for j in range(i - 1, max(i - 3, -1), -1):
                prev_msg = messages[j]
                if prev_msg.get("role") == "assistant":
                    content = prev_msg.get("content", "")
                    if isinstance(content, list):
                        has_preceding_tool_use = any(
                            block.get("type") == "tool_use" for block in content if isinstance(block, dict)
                        )
                    break
            if not has_preceding_tool_use:
                findings.append(
                    Finding(
                        pattern_id="H7",
                        pattern_name="Role Confusion",
                        severity=Severity.HIGH,
                        location=f"messages[{i}]",
                        description="Tool result message without a preceding tool_use in the assistant message.",
                        suggestion="Ensure every tool result is preceded by an assistant message containing a tool_use block.",
                    )
                )

        # Missing role
        if "role" not in msg:
            findings.append(
                Finding(
                    pattern_id="H7",
                    pattern_name="Role Confusion",
                    severity=Severity.CRITICAL,
                    location=f"messages[{i}]",
                    description=f"Message at position {i} has no 'role' field.",
                    suggestion="Every message must have a 'role' field: 'system', 'user', 'assistant', or 'tool'.",
                )
            )

        prev_role = role

    return findings


# ── Pattern Registry ───────────────────────────────────────────────

PATTERNS = {
    "H1": {"name": "Tool Description Ambiguity", "detect": detect_h1},
    "H2": {"name": "Missing Constraint Scaffolding", "detect": detect_h2},
    "H3": {"name": "Schema-Intent Mismatch", "detect": detect_h3},
    "H4": {"name": "Context Boundary Erosion", "detect": detect_h4},
    "H5": {"name": "Implicit Instruction Failure", "detect": detect_h5},
    "H6": {"name": "Template Format Contract Violation", "detect": detect_h6},
    "H7": {"name": "Role Confusion", "detect": detect_h7},
}
