"""H2-H7 detection heuristics, the H1-H7 registry, and compatible imports.

Shared models live in lintlang.models and H1 lives in lintlang.detectors.h1.
The names historically imported from this module remain identity-preserving
re-exports.
"""

from __future__ import annotations

import re
from pathlib import Path

from .detectors.h1 import _ALIAS_NOTICE as _ALIAS_NOTICE
from .detectors.h1 import _CAMEL_BOUNDARY as _CAMEL_BOUNDARY
from .detectors.h1 import _GENERIC_CANONICALS as _GENERIC_CANONICALS
from .detectors.h1 import _IDENTIFIER_SHAPED as _IDENTIFIER_SHAPED
from .detectors.h1 import _LOW_INFORMATION as _LOW_INFORMATION
from .detectors.h1 import _MIN_ANALYSABLE_TERMS as _MIN_ANALYSABLE_TERMS
from .detectors.h1 import _NON_DISCRIMINATING as _NON_DISCRIMINATING
from .detectors.h1 import _SKILL_DESCRIPTION_LIMIT as _SKILL_DESCRIPTION_LIMIT
from .detectors.h1 import _SKILL_NAME as _SKILL_NAME
from .detectors.h1 import _SKILL_NAME_LIMIT as _SKILL_NAME_LIMIT
from .detectors.h1 import _SKILL_TRIGGER as _SKILL_TRIGGER
from .detectors.h1 import _STOPWORDS as _STOPWORDS
from .detectors.h1 import _SUFFIXES as _SUFFIXES
from .detectors.h1 import _SYNONYM_CLASS as _SYNONYM_CLASS
from .detectors.h1 import _SYNONYM_GROUPS as _SYNONYM_GROUPS
from .detectors.h1 import VAGUE_WORDS as VAGUE_WORDS
from .detectors.h1 import _canonical as _canonical
from .detectors.h1 import _cross_references as _cross_references
from .detectors.h1 import _declared_alias as _declared_alias
from .detectors.h1 import _detect_skill_metadata as _detect_skill_metadata
from .detectors.h1 import _differentia as _differentia
from .detectors.h1 import _distinct_input_shapes as _distinct_input_shapes
from .detectors.h1 import _domination_is_meaningful as _domination_is_meaningful
from .detectors.h1 import _is_analysable as _is_analysable
from .detectors.h1 import _leading_verb as _leading_verb
from .detectors.h1 import _meaning_terms as _meaning_terms
from .detectors.h1 import _split_identifiers as _split_identifiers
from .detectors.h1 import _stem_candidates as _stem_candidates
from .detectors.h1 import _word_overlap as _word_overlap
from .detectors.h1 import detect_h1
from .models import AgentConfig, Finding, Severity
from .models import SkillMeta as SkillMeta
from .models import SourceRegion as SourceRegion
from .models import ToolDef as ToolDef
from .models import is_localization_reference as is_localization_reference
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

_EXPLICIT_NUMERIC_BUDGET = re.compile(
    r"\b(?:max(?:imum)?(?:\s+of)?|at\s+most|no\s+more\s+than|up\s+to)\s+\d+\s+"
    r"(?:tool\s+calls?|attempts?|retries|tries|iterations?|turns?|rounds?)\b",
    re.IGNORECASE,
)
_EXPLICIT_EXECUTION_STEP_BUDGET = re.compile(
    r"\b(?:execute|run|perform|take)\s+"
    r"(?:max(?:imum)?(?:\s+of)?|at\s+most|no\s+more\s+than|up\s+to)\s+\d+\s+steps?\b|"
    r"\b(?:max(?:imum)?(?:\s+of)?|at\s+most|no\s+more\s+than|up\s+to)\s+\d+\s+"
    r"(?:execution|agent|tool|action)\s+steps?\b|"
    r"\b(?:max(?:imum)?(?:\s+of)?|at\s+most|no\s+more\s+than|up\s+to)\s+\d+\s+steps?"
    r"\s*[,;.]?\s*(?:then\s+)?(?:stop|terminate|exit)\b",
    re.IGNORECASE,
)
_NEGATED_NUMERIC_BUDGET_PREFIX = re.compile(
    r"(?:\b(?:no|without)\s+(?:an?\s+)?(?:(?:explicit|fixed|hard)\s+)?|"
    r"\b(?:not|never)\s+(?:(?:have|use|set|enforce|apply|execute|run|perform|take)\s+)?(?:an?\s+)?"
    r"(?:(?:explicit|fixed|hard)\s+)?)$",
    re.IGNORECASE,
)
_NEGATED_CONSTRAINT_PREFIX = re.compile(
    r"(?:\b(?:no|without|neither)\b(?:\s+(?:an?|any|the))?"
    r"(?:\s+(?:explicit|fixed|hard|retry|iteration|turn|step|token|time|tool|"
    r"call|execution|action|max(?:imum)?|max_iterations|max_retries|retry_limit|"
    r"timeout|max_turns|max_steps|budget|limit|terminate|stop_condition|"
    r"exit_condition|max_tokens|or|nor|an?|the)){0,5}|"
    r"\b(?:do|does|did)\s+not(?:\s+(?:have|use|set|enforce|apply))?"
    r"(?:\s+(?:an?|any|the))?|"
    r"\b(?:not|never)(?:\s+(?:have|use|set|enforce|apply))?"
    r"(?:\s+(?:an?|any|the))?)\s*$",
    re.IGNORECASE,
)


def _has_explicit_numeric_budget(text: str) -> bool:
    """Recognize an affirmative numeric action budget, not its negation."""
    for pattern in (_EXPLICIT_NUMERIC_BUDGET, _EXPLICIT_EXECUTION_STEP_BUDGET):
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 64) : match.start()]
            if not _NEGATED_NUMERIC_BUDGET_PREFIX.search(prefix):
                return True
    return False


def _has_affirmative_constraint_signal(text: str, signal: str) -> bool:
    """Recognize a constraint keyword only when the local phrase is affirmative."""
    pattern = re.compile(rf"\b{re.escape(signal)}\b", re.IGNORECASE)
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 64) : match.start()]
        if not _NEGATED_CONSTRAINT_PREFIX.search(prefix):
            return True
    return False

_RETRY_UNTIL_PATTERN = r"(?:retry(?:ing)?|try\s+again|repeat)\s+(?:until|as\s+many\s+times)"
_LOOP_OVER_THROUGH_PATTERN = r"loop\s+(?:through|over)"


DANGEROUS_PATTERNS = [
    (r"keep\s+(?:on\s+)?trying\s+until", "Unbounded retry loop — 'keep trying until' needs an explicit limit."),
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
_UNBOUNDED_CONTINUATION_SIGNALS = re.compile(
    r"\b(?:indefinitely|forever|endlessly|continuously|perpetually|non-?stop|without\s+(?:end|stopping|limit))\b",
    re.IGNORECASE,
)
# ── H2 negation: one mechanism ─────────────────────────────────────
# "Do not continue indefinitely" states a bound; reporting it as unbounded
# inverts the author's meaning. ``_is_negated_prohibition`` is the only place
# H2 decides that, for every ``DANGEROUS_PATTERNS`` entry and for the
# continuation signal of a ``loop over/through`` traversal alike.
#
# H2 findings are CRITICAL, so a missed unbounded instruction costs more than a
# prohibition that stays reported. Every rule below is therefore written to
# fail towards reporting: anything not positively recognized is not a
# prohibition.

# Whitespace allowed between the negator, its adverbs, and the behavior: spaces,
# or one line break with optional indentation, because hard-wrapped prose ends
# lines anywhere ("you should never\nretry until ..."). A tab within a line, a
# blank line, a list marker, and any punctuation all break adjacency.
_NEG_GAP = r"(?:[ ]+|[ \t]*\r?\n[ \t]*)"
_NEG_APOSTROPHE = "['\u2019]"
_NEGATOR = (
    rf"(?:never|do{_NEG_GAP}not|don{_NEG_APOSTROPHE}?t"
    rf"|should{_NEG_GAP}not|shouldn{_NEG_APOSTROPHE}t"
    rf"|must{_NEG_GAP}not|mustn{_NEG_APOSTROPHE}t"
    rf"|(?P<ability>cannot|can{_NEG_APOSTROPHE}t))"
)
# A closed list, not ``\w+ly``: "reply", "apply", "rely", "comply", and "supply"
# end in the same letters and are verbs. Restrictive adverbs ("only", "merely",
# "simply", "solely", "just") are deliberately absent: "do not merely retry
# until ..." asks for more than the retry, not for none.
_NEGATION_ADVERBS = (
    r"(?:ever|blindly|continuously|continually|constantly|endlessly|perpetually|repeatedly|indefinitely)"
)
# The negator sits immediately before the behavior, with at most two listed
# adverbs between them. The anchor is ``\Z``: ``$`` also matches before a
# trailing newline.
_ADJACENT_NEGATOR = re.compile(
    rf"\b(?P<negator>{_NEGATOR})(?:{_NEG_GAP}{_NEGATION_ADVERBS}){{0,2}}{_NEG_GAP}\Z",
    re.IGNORECASE,
)
# Another negative word earlier in the negator's own clause is a double
# negation ("it is not true that you must not ...", "do not never ...").
# Contractions are listed with and without their apostrophe, because an author
# who writes "dont" also writes "wont", "isnt" and "didnt"; the apostrophe form
# alone would make the guard's verdict depend on typing style.
_APOSTROPHE_LESS_NEGATIVE = (
    r"(?:dont|wont|cant|isnt|arent|wasnt|werent|doesnt|didnt|hasnt|havent"
    r"|hadnt|shouldnt|wouldnt|couldnt|mustnt|aint)"
)
_EARLIER_NEGATIVE = re.compile(
    rf"\b(?:not|never|no|nor|neither|cannot|{_APOSTROPHE_LESS_NEGATIVE})\b|n{_NEG_APOSTROPHE}t\b",
    re.IGNORECASE,
)
_LEADING_NEGATOR = re.compile(rf"{_NEGATOR}\b", re.IGNORECASE)
_SUBJECT_BEFORE_NEGATOR = re.compile(rf"\w{_NEG_GAP}\Z")
# An exception licenses the unbounded run wherever it sits in the sentence:
# "unless the operator sets RUN_FOREVER, do not continue indefinitely" and
# "do not continue indefinitely unless ..." both permit it.
_LICENSING_EXCEPTION = re.compile(r"\b(?:unless|except)\b", re.IGNORECASE)
# A prohibition that is conditional, interrogative, or itself negated by "no
# reason" does not state a bound either.
_PROHIBITION_DEFEATER = re.compile(
    r"\b(?:if|when|whenever|why)\b|\bno\s+reason\b",
    re.IGNORECASE,
)
_SENTENCE_BREAK = re.compile(
    r"[.!?;](?=\s|\Z)|\n[ \t]*\n|\n[ \t]*(?:[-*+\u2022]|\d+[.)]|#{1,6})[ \t]",
)
# A condition attached to the prohibited behavior itself makes the prohibition
# conditional ("do not keep trying until it works when the credentials are
# wrong"). A condition in a clause coordinated *after* it is the author's own
# stop condition ("do not continue indefinitely and stop when the queue
# drains") \u2014 which is exactly the corrected wording a user writes once H2 has
# flagged them \u2014 and must not defeat the prohibition. The right-hand defeater
# search therefore ends at the first clause boundary after the behavior.
_RIGHT_CLAUSE_BOUNDARY = re.compile(
    r"[,(]|\s[-\u2013\u2014]\s|\s(?:and|but|or|then)\s",
    re.IGNORECASE,
)
# ...except when the comma, dash, or opening parenthesis introduces a condition
# of its own ("do not retry until it works, if the queue is non-empty", "do not
# retry until it works (if the queue is non-empty)"). That condition qualifies
# the prohibited behavior rather than stating the author's stop condition, so
# the right-hand search must see it. A parenthesis that opens anything else
# ("... (see the runbook)", "... (stop after ten items)") still closes the
# clause, because it is an aside or the author's own bound, not a condition.
_TRAILING_CONDITION = re.compile(
    r"(?:[,(\u2013\u2014]|\s[-\u2013\u2014])\s*(?:\(\s*)*"
    r"(?:(?:but\s+)?only\s+)?(?:if|when|whenever)\b",
    re.IGNORECASE,
)
# A comma only starts a new clause to the left of the negator when it opens a
# coordinated one ("... , and do not retry until success"). A fronted condition
# still qualifies the prohibition ("When the push fails, do not retry until
# ..."), so it must remain visible to the defeater check. Taking the last comma
# unconditionally hid both conditions and earlier negatives behind a
# parenthetical or complement ("It is not true, however, that you must never
# retry until it works"), which inverted the author's meaning.
_LEFT_CLAUSE_COMMA = re.compile(r",")
_COORDINATED_CLAUSE = re.compile(
    r"\s*(?:and|but|or|so|then|yet|while|whereas)\b",
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


def _left_clause_start(before_negator: str, sentence_start: int) -> int:
    """Return where the negator's own clause begins, at or after ``sentence_start``.

    Only a comma that opens a coordinated clause moves the start. A fronted
    condition must remain in the clause because it qualifies the prohibition;
    a parenthetical (", however,") or complement (", that you must ...") also
    leaves the earlier text in the clause.
    """
    clause_start = sentence_start
    for comma in _LEFT_CLAUSE_COMMA.finditer(before_negator, sentence_start):
        if _COORDINATED_CLAUSE.match(before_negator, comma.end()):
            clause_start = comma.end()
    return clause_start


def _is_negated_prohibition(text: str, position: int) -> bool:
    """Return whether the behavior starting at ``position`` is forbidden, not instructed.

    True only when all of these hold:

    - a negator sits immediately before ``position``, separated by nothing but
      whitespace and at most two adverbs from the closed list;
    - ``cannot`` / ``can't`` has a subject ("You cannot ..."), because a bare
      "Cannot continue indefinitely: ..." reads as a status message;
    - no other negative word precedes the negator in its own clause ("do not
      never ...", "it is not true that you must not ..."), and the behavior does
      not itself open with one ("never don't stop until ...");
    - the sentence carries no licensing exception ("unless", "except"), before
      or after the prohibition, and the next sentence does not open with one;
    - the sentence is not a question;
    - the negator's clause is not conditional or interrogative. To the left the
      clause begins after a sentence break or after a comma that opens a
      coordinated clause ("..., and do not retry until success"); a fronted
      condition remains part of it. To
      the right it ends at the first clause boundary after the behavior, so the
      author's own stop condition in a coordinated clause ("do not continue
      indefinitely and stop when the queue drains") does not defeat the
      prohibition — unless that boundary itself introduces a condition on the
      behavior ("..., if the queue is non-empty", "... (if the queue is
      non-empty)"), which does.

    Known limitations, reported rather than guessed at: an interrupted negator
    ("Do not, under any circumstances, ...", "Never, ever ..."), a delegated
    one ("Do not let the agent ...", "Do not allow it to ..."), and a
    subjectless "Cannot ..." all stay reported.
    """
    prefix = text[:position]
    adjacent = _ADJACENT_NEGATOR.search(prefix)
    if adjacent is None:
        return False

    before_negator = prefix[: adjacent.start("negator")]
    if adjacent.group("ability") and not _SUBJECT_BEFORE_NEGATOR.search(before_negator):
        return False
    # The behavior itself opens with a negator: "never don't stop until ...".
    if _LEADING_NEGATOR.match(text, position):
        return False

    sentence_start = 0
    for boundary in _SENTENCE_BREAK.finditer(before_negator):
        sentence_start = boundary.end()
    next_break = _SENTENCE_BREAK.search(text, position)
    sentence_end = next_break.start() if next_break else len(text)
    # A question asks about the behavior; it does not forbid it.
    if next_break is not None and next_break.group().startswith("?"):
        return False
    if _LICENSING_EXCEPTION.search(text, sentence_start, sentence_end):
        return False
    # "...; except when directed otherwise" and "... . Unless RUN_FOREVER is set."
    # attach to the prohibition even though a break precedes them.
    if next_break is not None:
        after_break = len(text) - len(text[next_break.end() :].lstrip())
        if _LICENSING_EXCEPTION.match(text, after_break):
            return False

    clause_start = _left_clause_start(before_negator, sentence_start)
    if _EARLIER_NEGATIVE.search(text, clause_start, adjacent.start("negator")):
        return False
    right_boundary = _RIGHT_CLAUSE_BOUNDARY.search(text, position, sentence_end)
    clause_end = right_boundary.start() if right_boundary else sentence_end
    if right_boundary is not None and _TRAILING_CONDITION.match(text, right_boundary.start()):
        clause_end = sentence_end
    return _PROHIBITION_DEFEATER.search(text, clause_start, clause_end) is None


def _is_unbounded_loop_traversal(text: str, match: re.Match[str]) -> bool:
    """Return whether ``loop over/through`` describes an unbounded loop, not enumeration.

    ``loop over`` and ``loop through`` ordinarily introduce enumeration of a
    finite collection ("loop through the search results") — that is normal
    control flow, not a missing-constraint risk. Only treat it as a potential
    infinite loop when the same clause also carries an explicit indefinite-
    continuation signal (e.g. "loop over tasks indefinitely").

    A negator before the traversal itself is handled by ``detect_h2``, which
    applies ``_is_negated_prohibition`` to every pattern. The same guard is
    applied here to the continuation signal ("loop over the items but never
    indefinitely").
    """
    window = _immediate_clause(text, match.end())
    signal = _UNBOUNDED_CONTINUATION_SIGNALS.search(window)
    if signal is None:
        return False
    return not _is_negated_prohibition(text, match.end() + signal.start())


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


_STATED_BOUND = re.compile(
    r"\bmax(?:imum)?\b|\bmax[_A-Za-z]\w*|\bat\s+most\b|\bup\s+to\s+\d|\bno\s+more\s+than\b|"
    r"\b\d+\s*(?:x|times?|attempts?|retries|tries|iterations?|rounds?|minutes?|seconds?|s|ms)\b|"
    r"\btime(?:s)?\s*out\b|\btimeout\b|\blimit(?:ed)?\s+(?:of|to)\b|\bbudget\b|\bthen\s+stop\b|\bor\s+stop\b",
    re.IGNORECASE,
)
_LOOP_AS_NOUN = re.compile(
    r"(?:\b(?:a|an|the|this|that|its|their|your|each|every|agent|agentic|run|event|main|outer|inner|"
    r"feedback|control|tool|game|while|for|revise|retry|review)\s+|[-=]>\s*\w+\s+|\w-)$",
    re.IGNORECASE,
)


def _sentence_around(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n\n", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    rights = [i for i in (text.find(". ", end), text.find(".\n", end), text.find("\n\n", end)) if i != -1]
    return text[left + 1 : (min(rights) if rights else len(text))]


def _is_bounded_or_descriptive(text: str, match: re.Match[str]) -> bool:
    """The same sentence states the bound, or 'loop' is a noun being described.

    "... runs a revise loop until the artifact meets the rubric, hits
    `max_iterations`, or is interrupted" names its limit. "block the agent loop
    until answered" describes a loop; it does not instruct one.
    """
    if _STATED_BOUND.search(_sentence_around(text, match.start(), match.end())):
        return True
    return match.group().lower().startswith("loop") and bool(_LOOP_AS_NOUN.search(text[max(0, match.start() - 24) : match.start()]))


def _is_ordinary_loop_in_document(text: str, match: re.Match[str]) -> bool:
    """In a Markdown document, "loop / repeat / continue until <condition>" states
    its own termination condition ("Loop until `stop_reason == \"end_turn\"`",
    "Repeat until the branch is one commit ahead"). That is what `until` means; it
    is a procedure, not an unbounded instruction. What stays reported there is
    effort without a cap — keep trying / retry until, "don't stop until",
    "continue indefinitely" — and anything inside a quoted example is not an
    instruction at all.
    """
    phrase = match.group().lower()
    line_start = text.rfind("\n", 0, match.start()) + 1
    if text.count('"', line_start, match.start()) % 2 == 1:
        return True
    if "indefinitely" in phrase:
        return False
    return phrase.startswith(("loop", "repeat", "continue"))


def detect_h2(config: AgentConfig) -> list[Finding]:
    """Detect missing constraint scaffolding."""
    findings: list[Finding] = []

    # Check system prompt for constraint keywords
    prompt = config.system_prompt.lower()
    constraints = config.constraints

    has_any_constraint = _has_explicit_numeric_budget(prompt)
    constraints_str = str(constraints).lower()
    for signal in CONSTRAINT_SIGNALS:
        if has_any_constraint:
            break
        if _has_affirmative_constraint_signal(
            prompt, signal
        ) or _has_affirmative_constraint_signal(constraints_str, signal):
            has_any_constraint = True
            break

    if config.system_prompt and config.kind != "server" and not has_any_constraint and len(config.tools) > 0:
        findings.append(
            Finding(
                pattern_id="H2",
                pattern_name="Missing Constraint Scaffolding",
                severity=Severity.HIGH,
                location="system_prompt",
                description="System prompt defines tools but contains no termination conditions, retry budgets, or progress checks.",
                suggestion=(
                    "Add explicit constraints: 'Retry limit: 2 attempts. "
                    "If no progress after 2 attempts, stop and report the issue.'"
                ),
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
            if _is_negated_prohibition(text, match.start()):
                continue
            if _is_bounded_or_descriptive(text, match):
                continue
            if config.kind == "instructions" and _is_ordinary_loop_in_document(text, match):
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
                    offset=match.start(),
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
        if not params or not isinstance(params, dict):
            continue

        properties = params.get("properties", {})
        required_list = params.get("required", [])
        if not isinstance(properties, dict):
            continue
        if not isinstance(required_list, list):
            required_list = []

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

        _check_properties(findings, tool.name, properties, "parameters", tool.description)

    # Check schemas list too
    for i, schema in enumerate(config.schemas):
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            continue
        for prop_name, prop_def in props.items():
            if not isinstance(prop_def, dict):
                continue
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


def _check_properties(
    findings: list[Finding], tool_name: str, properties: dict, path: str, tool_description: str = "",
) -> None:
    """Check properties for schema-intent issues, including nested objects."""
    for prop_name, prop_def in properties.items():
        full_path = f"{path}.{prop_name}"
        if not isinstance(prop_def, dict):
            continue  # `true` / `false` are valid JSON Schema and say nothing to lint

        # A schema constraint or the tool's own prose can explain a scalar
        # parameter. Do not demand a duplicate sentence for a format, enum,
        # named boolean switch, or an input explicitly named in that prose.
        explained = bool(prop_def.get("enum") or "const" in prop_def or prop_def.get("format"))
        scalar = prop_def.get("type") in ("string", "boolean", "integer", "number")
        words = _split_identifiers(prop_name).lower().split()
        prose = set(re.findall(r"\w+", tool_description.lower()))
        if scalar and prop_name.lower() not in GENERIC_PROP_NAMES:
            explained |= bool(words and set(words) <= prose)
            explained |= prop_def.get("type") == "boolean" and len(words) > 1
            explained |= prop_name.lower() == "password" and prop_def.get("type") == "string"
            explained |= prop_name.lower() == "path" and bool(prose & {"file", "files", "disk"})
        if "description" not in prop_def and not explained:
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
                if not isinstance(variants, list):
                    continue
                variants = [v for v in variants if isinstance(v, dict)]
                undescribed = [v for v in variants if "description" not in v and "title" not in v]
                # A union of scalar types ({"type": "string"} | {"type": "number"},
                # or the nullable idiom) explains itself. The defect is a choice
                # between STRUCTURES the model cannot tell apart.
                structural = [
                    v for v in undescribed
                    if v.get("type") in ("object", "array") or "properties" in v or "$ref" in v or "items" in v
                ]
                # A parent description long enough to explain the forms does the job.
                parent_explains = isinstance(prop_def.get("description"), str) and len(prop_def["description"]) >= 80
                if undescribed and structural and not parent_explains:
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
            _check_properties(
                findings, tool_name, prop_def["properties"], full_path, tool_description
            )


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


_H4_STATEFULNESS_SIGNALS = re.compile(
    r"(?:"
    r"\b(?:conversation|chat|message|dialogue)\s+history\b|"
    r"\bcontext\s+window\b|"
    r"\b(?:prior|previous|past|earlier)\s+(?:[\w'-]+\s+){0,2}?"
    r"(?:conversations?|messages?|turns?|tasks?|sessions?|requests?|interactions?|"
    r"exchanges?|answers?|responses?|results?|states?|context|contexts|inputs?|chats?)\b|"
    r"\bacross\s+(?:the\s+|all\s+|multiple\s+)?"
    r"(?:conversations?|tasks?|sessions?|turns?|requests?|messages?|threads?)\b|"
    r"\bbetween\s+(?:conversations?|tasks?|sessions?|turns?|requests?|messages?)\b|"
    r"\bcarry(?:ing)?\s+(?:over\s+)?(?:state|context|memory|results?|information)\b|"
    r"\bcarry[- ]?over\b|\bcross[- ]?(?:task|session|turn|request|conversation)\b|"
    r"\bremember\s+(?:everything|all|each|every)\b|"
    r"\b(?:what|anything|everything)\s+the\s+user\s+(?:said|told|asked|wrote)\b|"
    r"\bmulti[- ]?turn\b|"
    r"\b(?:maintain|maintaining|keep|keeping|track|tracking|retain|retaining|persist|persisting)\s+"
    r"(?:[\w'-]+\s+){0,2}?(?:context|state|memory|history)\b|"
    r"\b(?:every|each|any)\s+future\s+"
    r"(?:request|session|chat|conversation|message|task|turn|visit|reply|response)\b|"
    r"\bfrom\s+(?:that|the)\s+same\s+(?:person|user|customer|client)\b|"
    r"\bnext\s+time\s+(?:they|he|she|the\s+[\w'-]+)\s+"
    r"(?:ask|asks|request|requests|return|returns|come|comes|visit|visits|write|writes|message|messages)\b|"
    r"\bbrand\s+new\s+(?:chat|session|conversation)(?:\s+window)?\b"
    r")",
    re.IGNORECASE,
)


def _shows_cross_context_statefulness(prompt: str, scope: ScopeAnalysis) -> bool:
    """Return whether a prompt demonstrates the statefulness H4's length rule assumes.

    The historical rule was applicability-free: any system prompt longer than 500
    characters had to contain context-boundary vocabulary or it was reported as
    MEDIUM "Long system prompt with no context boundary markers". Length alone is
    not evidence of boundary erosion risk: a long, single-shot reference document
    that never asks the agent to carry anything between turns has no boundary to
    erode, and LintLang's own ``AGENTS.md`` and ``SKILL.md`` prose were reported
    that way (RESEARCH.md section 5).

    The rule now requires demonstrated applicability: the prompt must actually
    instruct or describe cross-context behaviour — conversation/chat history, a
    context window, prior turns/tasks/sessions, carrying state across or between
    them, remembering everything, maintaining context/state/memory, or an
    instruction to carry behaviour into a future request/session ("every future
    request", "from that same user", "next time they ask", "a brand new chat
    window"). A prompt with no such signal is not reported for missing boundary
    vocabulary; the EROSION_PATTERNS rules are unchanged and still fire on their
    own evidence.
    """
    return any(
        _is_direct_match(scope, match.start(), match.end())
        for match in _H4_STATEFULNESS_SIGNALS.finditer(prompt)
    )


_FENCE = re.compile(r"^[ \t]*(```|~~~)")
_PATH_CANDIDATE = re.compile(r"`([^`\n]+)`|\]\(([^)\s]+)\)")
_PATH_EXTENSION = re.compile(
    r"\.(?:md|mdc|txt|json|ya?ml|toml|ini|cfg|py|pyi|js|jsx|mjs|cjs|ts|tsx|go|rs|rb|java|kt|swift|c|h|cc|cpp|hpp|"
    r"cs|php|sh|bash|zsh|ps1|sql|html|css|scss|vue|svelte|lock|env|proto|graphql|tf|gradle|xml|ipynb)$",
    re.IGNORECASE,
)
_NOT_A_LITERAL_PATH = re.compile(r"[\s*?\[\]{}<>$|=,;'\"\\%#]|\.\.\.|://|^[-~/@.]?$|^[-~/@]|^\.\./")
_HYPOTHETICAL_LINE = re.compile(
    r"\b(?:e\.g\.|for example|examples?|such as|like|would|could|append(?:s|ed)?|create[sd]?|creating|generate[sd]?|generating|"
    r"will (?:be|write|create)|writes? (?:to|a|the)|written to|outputs?|produces?|add a|new file|rename[sd]?|"
    r"moved?|deleted?|removed?|formerly|used to|instead of|not|never|don't|do not|if (?:it|there|a|the)|"
    r"optional(?:ly)?|may|might|when present|if present|ignored?)\b",
    re.IGNORECASE,
)


_AGENT_DOCUMENT_NAMES = frozenset(
    {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "SKILL.md", "copilot-instructions.md", ".cursorrules", ".windsurfrules"}
)


def _repository_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _detect_dangling_references(config: AgentConfig) -> list[Finding]:
    """Report file paths an instruction document names that are not there.

    Agents act on AGENTS.md / CLAUDE.md literally: a path that no longer exists
    after a refactor sends them searching, or makes them recreate the file. This
    is context that points nowhere. The check is deliberately narrow — a finding
    needs ALL of:

    - a literal relative path with a directory part, in backticks or a Markdown
      link, outside fenced code blocks;
    - whose FIRST segment exists beside the document or at the repository root
      (so it is a path into this project, not an illustration from another one);
    - that resolves from neither place;
    - on a line that does not talk about creating, renaming, removing or
      exemplifying it.
    """
    if config.kind != "instructions" or not config.source_file:
        return []
    source = Path(config.source_file)
    # Only documents written FOR an agent. A user guide that tells a person to
    # create `.vscode/mcp.json` is not an instruction pointing at a missing file.
    if config.skill is None and source.name not in _AGENT_DOCUMENT_NAMES and not source.name.endswith(
        ".instructions.md"
    ):
        return []
    try:
        if not source.is_file():
            return []
        base = source.resolve().parent
    except OSError:
        return []
    roots = [base]
    repo = _repository_root(base)
    if repo is not None and repo != base:
        roots.append(repo)

    findings: list[Finding] = []
    seen: set[str] = set()
    in_fence = False
    offset = 0
    for line in config.system_prompt.split("\n"):
        line_offset = offset
        offset += len(line) + 1
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or _HYPOTHETICAL_LINE.search(line):
            continue
        for match in _PATH_CANDIDATE.finditer(line):
            token = (match.group(1) or match.group(2) or "").strip()
            token = re.sub(r"(?::\d+(?:-\d+)?|#[\w-]+)$", "", token)
            if token.startswith("./"):
                token = token[2:]
            if "/" not in token.strip("/") or _NOT_A_LITERAL_PATH.search(token):
                continue
            # Files only: a named directory is as often a build output or a
            # runtime location as a checked-in one.
            if not _PATH_EXTENSION.search(token):
                continue
            if re.search(r"(?:^|[/_.-])(?:your|my|foo|bar|baz|example|sample|name|xxx|placeholder)(?:[/_.-]|$)", token, re.I):
                continue
            if token in seen:
                continue
            first = token.split("/", 1)[0]
            try:
                anchored = [root for root in roots if (root / first).is_dir()]
                if not anchored or any((root / token).exists() for root in roots):
                    continue
            except OSError:
                continue
            seen.add(token)
            findings.append(
                Finding(
                    pattern_id="H4",
                    sub_id="H4.5",
                    pattern_name="Context Boundary Erosion",
                    severity=Severity.MEDIUM,
                    location=f"reference:{token}",
                    description=(
                        f"Referenced path '{token}' does not exist, although '{first}/' does. An agent "
                        "following this instruction is sent to a file that is not there."
                    ),
                    suggestion="Update the path, or remove the reference if the file is gone.",
                    evidence=line.strip()[:160],
                    offset=line_offset + match.start(),
                )
            )
    return findings


def detect_h4(config: AgentConfig) -> list[Finding]:
    """Detect context boundary erosion risks."""
    findings: list[Finding] = _detect_dangling_references(config)
    prompt = config.system_prompt

    if prompt:
        scope = analyze_scope(prompt)

        # Check for boundary markers (word boundary matching)
        has_boundary = any(
            _is_direct_match(scope, match.start(), match.end())
            for signal in BOUNDARY_SIGNALS
            for match in re.finditer(rf"\b{re.escape(signal)}\b", prompt, re.IGNORECASE)
        )

        # Absence of boundary vocabulary is a property of a chat system prompt;
        # a Markdown reference document that mentions "conversation history"
        # is describing an API, not failing to scope a session.
        if (
            config.kind not in ("instructions", "templates", "server")
            and len(prompt) > 500
            and not has_boundary
            and _shows_cross_context_statefulness(prompt, scope)
        ):
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
                        offset=match.start(),
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

    # The two density heuristics below judge the SHAPE of a chat system prompt.
    # An instruction document (AGENTS.md, CLAUDE.md, a SKILL.md body) is a
    # reference an agent consults, not one prompt. In the audited instruction
    # corpus, "N instructions with no priority ordering" fired broadly and
    # named no sentence to repair. A finding that cannot point at its evidence,
    # on a surface it was not designed for, is noise.
    is_chat_prompt = config.kind not in ("instructions", "templates", "server")

    # Flag problematic negatives (those NOT near safety keywords)
    if is_chat_prompt and len(problematic_negatives) > 3:
        findings.append(
            Finding(
                pattern_id="H5",
                pattern_name="Implicit Instruction Failure",
                severity=Severity.MEDIUM,
                location="system_prompt",
                description=f"System prompt has {len(problematic_negatives)} negative instructions ('don't', 'never', 'avoid'). Models follow positive instructions more reliably.",
                suggestion="Rewrite negatives as positives. Instead of 'Don't apologize', use 'Respond directly without apologies'. Instead of 'Never make up data', use 'Only cite data from provided context'.",
                evidence=problematic_negatives[0][1],
                offset=problematic_negatives[0][0],
            )
        )

    # Per-negative LOW notices were removed: a single unexempted negative directive
    # is ordinary, correct instruction prose, and the exemption layers above are a
    # 100-character keyword window rather than a scope decision, so each notice
    # asserted a defect the detector had not demonstrated (RESEARCH.md section 5).
    # The tested density signal — more than three unexempted negatives in one
    # prompt — is kept above, unchanged, as the aggregated MEDIUM finding.

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
                    offset=match.start(),
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
    if is_chat_prompt and instruction_count > 10 and not has_priority:
        findings.append(
            Finding(
                pattern_id="H5",
                pattern_name="Implicit Instruction Failure",
                # A sentence count is not evidence of a conflict. It stays MEDIUM
                # where it was designed (a standalone prompt file or a config's
                # system prompt) and is advice for a literal extracted from code.
                severity=Severity.LOW if config.kind == "python" else Severity.MEDIUM,
                location="system_prompt",
                description=f"System prompt has ~{instruction_count} instructions with no explicit priority ordering.",
                suggestion="Add priority ordering: 'PRIORITY 1: Always cite sources. PRIORITY 2: Be concise. When these conflict, prioritize accuracy over brevity.'",
            )
        )

    return findings


# ── H6: Template Format Contract Violation ─────────────────────────


_OUTPUT_FORMAT_INSTRUCTION_TEMPLATES = (
    # A descriptive contract on the agent's own response is still a contract:
    # "The agent's reply is delivered as JSON ... and as Markdown ...". Keep
    # the subject explicit so descriptions of another service stay silent.
    r"\b(?:the\s+agent(?:'s)?\s+)?(?:responses?|reply|replies|answers?)\b"
    r"[^\n.!?]{{0,120}}\b(?:as|in|using)\s+{fmt}\b",
    # "respond in JSON", "return the result as markdown", "output using XML", and
    # the coordinated form "respond in JSON and Markdown" / "output as JSON or XML",
    # where one instruction names both halves of the competing contract.
    r"\b(?:respond|reply|answer|output|return|emit|print|render|produce|send|format|write)"
    r"(?:\w+)?\s+(?:[\w'-]+\s+){{0,3}}?(?:in|as|with|using|to)\s+"
    r"(?:(?:valid|plain|raw|pure|strict)\s+)?"
    r"(?:[\w'-]+\s*(?:,|/|\band\b|\bor\b)\s*){{0,3}}?{fmt}\b",
    # "write your reply as friendly Markdown text", "answer the user in plain XML" —
    # a response verb pointed at the format through a single descriptive word
    # ("friendly", "clean", "simple") rather than a comma/and/or coordination.
    r"\b(?:respond|reply|answer|write)\s+(?:[\w'-]+\s+){{0,3}}?(?:as|in|using|with|to)\s+"
    r"(?:[\w'-]+\s+){{0,1}}?{fmt}\b",
    # "use JSON for data queries", "use markdown when it helps"
    r"\b(?:use|using|prefer|choose)\s+{fmt}\s+(?:for|when|if|unless)\b",
    # dispatch ellipsis at the start of a sentence: "XML for configs."
    r"(?:^|[.;:!?\n]\s*){fmt}\s+for\s+[\w'-]+",
    # "XML is acceptable", "Markdown is also allowed"
    r"(?:^|[.;:!?\n]\s*){fmt}\s+(?:is|are)\s+(?:also\s+)?"
    r"(?:acceptable|allowed|fine|ok|okay|preferred|required|expected|permitted)\b",
    # "output format: JSON", "output format is markdown"
    r"\boutput\s+format\s*(?:[:=]|is|must\s+be|should\s+be)\s*"
    r"(?:[\w'-]+\s+){{0,2}}?{fmt}\b",
    # "JSON output only", "markdown response required"
    r"\b{fmt}\s+(?:output|response|responses|reply|replies)\s+"
    r"(?:only|required|expected|is\s+required|is\s+expected)\b",
    # "responses conform to this JSON schema", "output adheres to the XML format" —
    # a schema/format-conformance contract on the response/output is itself an
    # output-format instruction (kept narrow: the subject must name the
    # response/output, not just any document or file conforming to a schema).
    r"\b(?:responses?|output|reply|replies|answers?)\s+"
    r"(?:must\s+|should\s+|will\s+|shall\s+)?"
    r"(?:conform|conforms|conforming|adhere|adheres|adhering)\s+to\s+"
    r"(?:(?:this|a|an|the)\s+)?(?:[\w'-]+\s+){{0,2}}?{fmt}\b",
    # Bare imperative taking the format as a direct object: "Always output
    # JSON.", "Return JSON only.", "Emit XML." This is the most ordinary way to
    # state an output contract, and without it the narrowing above cut a real
    # positive. The verb must be imperative — at a sentence start, or after a
    # modal or one of these adverbs — so a descriptive third-person clause
    # ("The upstream service returns JSON.") is still not a contract.
    r"(?:(?:^|[.;:!?\n]|\b(?:always|only|just|strictly|must|should|shall|will|please|also|and)\b)\s*)"
    r"(?:(?:always|only|just|strictly|also)\s+)?"
    r"(?:respond|reply|answer|output|return|emit)\s+"
    r"(?:(?:only|always|just|strictly)\s+)?"
    r"(?:(?:valid|plain|raw|pure|strict|well-?formed)\s+)?{fmt}\b",
)

_OUTPUT_FORMAT_INSTRUCTIONS: dict[str, tuple[re.Pattern[str], ...]] = {
    fmt: tuple(
        re.compile(template.format(fmt=fmt), re.IGNORECASE)
        for template in _OUTPUT_FORMAT_INSTRUCTION_TEMPLATES
    )
    for fmt in ("json", "markdown", "xml")
}


def _instructs_output_format(cleaned: str, fmt: str) -> bool:
    """Return whether the prompt actually instructs responding in ``fmt``.

    H6's competing-contract finding used to be true whenever the words "JSON",
    "Markdown", or "XML" appeared twice over, so a document that merely listed
    the file types a tool accepts was reported as a format contract violation.
    A format now counts only when the prompt gives it as an output instruction:
    a response verb pointing at it (including through a single descriptive word,
    as in "write your reply as friendly Markdown"), a "use X for/when" dispatch,
    a sentence-initial dispatch ellipsis ("XML for configs."), an explicit
    acceptability statement, an "output format:" declaration, an "X output only"
    demand, or a response/output schema-conformance clause ("responses conform
    to this JSON schema"). The existing code-block, inline-code, filename, and
    CLI-flag cleaning still runs first and is unchanged.
    """
    return any(pattern.search(cleaned) for pattern in _OUTPUT_FORMAT_INSTRUCTIONS[fmt])


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

    # Mixed format instructions. A bare mention is not a contract: naming JSON and
    # Markdown while describing which file types a tool reads is ordinary prose,
    # and it made any document that named two formats an H6 MEDIUM
    # (RESEARCH.md section 5). Each format must carry its own output-format
    # instruction before it counts towards a competing contract.
    has_json = _instructs_output_format(cleaned, "json")
    has_markdown = _instructs_output_format(cleaned, "markdown")
    has_xml = _instructs_output_format(cleaned, "xml")
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

    # No output format specification at all. The recognizer has to accept the
    # ordinary ways of stating one, or the finding contradicts the document it
    # is reporting on: "Return Markdown only." and "Return a plan as Markdown."
    # both specify a format, and both used to be missed because the verb had to
    # be immediately followed by in/as/with/using. It is deliberately not
    # widened to arbitrary words before the format name, which would reopen the
    # mere-mention false positive that the competing-contract rule above just
    # removed — so "Output exactly one Markdown document." is a known miss.
    has_output_format = bool(
        re.search(
            r"\b(?:respond|output|return|reply|answer|emit|format)\s+"
            r"(?:(?:[\w'-]+\s+){0,3}?(?:in|as|with|using)\s+)?"
            r"(?:(?:only|valid|plain|raw|strict|well-?formed)\s+)*"
            r"(?:json|markdown|xml|yaml|text|html|csv)\b",
            prompt,
            re.IGNORECASE,
        )
    )
    has_format_example = bool(re.search(r"```|example\s*(?:output|response)", prompt, re.IGNORECASE))

    # An output contract is a property of a chat/system prompt. A Markdown
    # instruction document has no single response to contract.
    is_chat_prompt = config.kind not in ("instructions", "templates", "server")
    if is_chat_prompt and len(prompt) > 200 and not has_output_format and not has_format_example:
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
    if is_chat_prompt and config.kind != "python" and len(prompt) > 500 and not has_version:
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
