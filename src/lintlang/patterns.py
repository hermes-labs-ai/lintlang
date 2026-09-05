"""H1-H7 pattern definitions and detection heuristics.

Each pattern has:
- id: H1-H7
- name: Human-readable name
- user_reports_as: What users typically say
- detect(config): Returns list of Finding objects
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .preflight.models import ScopeKind
from .preflight.scope import ScopeAnalysis, analyze_scope


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


def _is_direct_match(scope: ScopeAnalysis, start: int, end: int) -> bool:
    """Return whether a match is live text, preserving detection if classification fails."""
    return scope.unavailable_reason is not None or scope.is_direct(start, end)


def _is_h5_negative_match(scope: ScopeAnalysis, start: int, end: int) -> bool:
    """Keep H5 negative directives operative while excluding quoted and non-operative text."""
    return scope.unavailable_reason is not None or (
        0 <= start < end <= len(scope.scopes)
        and all(kind in {ScopeKind.DIRECT, ScopeKind.NEGATED} for kind in scope.scopes[start:end])
    )


# ── H1: Tool Description Ambiguity ─────────────────────────────────


VAGUE_WORDS = {
    "handle",
    "process",
    "manage",
    "do",
    "run",
    "execute",
    "perform",
    "deal",
    "work",
    "use",
    "make",
    "get",
    "set",
}


# ── H1.6 support: differentia detection ────────────────────────────
#
# A *description* says what a tool is. A *diagnosis* says what distinguishes it
# from its nearest neighbour. A description can be entirely accurate and still
# fail as a diagnosis — which is precisely when a model picks the wrong tool.
#
# H1.5 (word overlap) asks "are these two worded alike?". That is a different
# question, and it misses the common case: two descriptions can share almost no
# vocabulary and still be perfectly interchangeable, because their differing
# words are synonyms. H1.6 asks the right question — "is there any term here
# that would let a reader choose one over the other?" — and fires when the
# answer is no.

_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    # Retrieval splits three ways on purpose. `list X` (enumerate all),
    # `search X` (filter by predicate) and `get X` (fetch by identity) are
    # genuinely different operations with different parameter shapes, and
    # collapsing them fires on the most common tool-pair shape in MCP servers.
    ("search", "find", "query", "lookup", "look", "seek", "locate", "grep"),
    ("get", "fetch", "retrieve", "read", "obtain", "pull", "load", "access"),
    ("list", "enumerate", "index", "browse"),
    # creation
    ("create", "add", "new", "insert", "register", "make", "generate"),
    # deletion
    ("delete", "remove", "destroy", "drop", "erase", "purge", "clear"),
    # modification
    ("update", "modify", "edit", "change", "patch", "alter", "set"),
    # Persistence verbs. "store" belongs here, not with the container nouns:
    # as a container it would canonicalize to "system" and be dropped as
    # low-information, which silently deletes the only verb in a name like
    # `fidelis_store` and makes it look dominated by `fidelis_recall`.
    ("store", "save", "persist", "write", "commit", "put"),
    # transmission
    ("send", "post", "submit", "dispatch", "publish", "transmit"),
    # generic action verbs — these carry no selection signal at all
    ("handle", "process", "manage", "do", "perform", "execute", "run", "deal", "work"),
    # generic payload nouns
    ("info", "information", "data", "detail", "details", "record", "entry", "content"),
    # generic container nouns
    ("system", "database", "db", "repository", "backend", "service", "platform"),
    # documentation
    ("doc", "docs", "documentation", "manual", "guide", "reference"),
)

_SYNONYM_CLASS: dict[str, str] = {
    term: group[0] for group in _SYNONYM_GROUPS for term in group
}

# Terms that cannot serve as a differentia even when they are unique to one side.
# A word only distinguishes two tools if it narrows *when* to reach for one.
# "thing", "system", "various" narrow nothing.
_LOW_INFORMATION = {
    # Canonical form of the generic-container synonym class (store, database,
    # db, repository, backend, service). "…from the system" narrows nothing.
    "system",
    # Canonical form of the generic-payload class (information, data, detail,
    # record, entry, content). "user record" vs "user account" must not be
    # separated by the word "record" — it names no distinction.
    "info",
    "thing",
    "things",
    "stuff",
    "item",
    "items",
    "object",
    "objects",
    "entity",
    "entities",
    "various",
    "general",
    "generic",
    "relevant",
    "appropriate",
    "given",
    "specific",
    "certain",
    "particular",
    "necessary",
    "required",
    "available",
    "valid",
    "proper",
    "correct",
}

# Function words that carry no selection signal. Kept separate from the
# module-level _STOPWORDS (which H1.5's overlap score depends on) so that
# widening this set cannot silently move H1.5's threshold behaviour.
_NON_DISCRIMINATING = {
    "through",
    "into",
    "onto",
    "over",
    "under",
    "via",
    "about",
    "across",
    "up",
    "out",
    "off",
    "down",
    # NOT here: all, any, each, every, some. They look like filler and are not.
    # `list_all_users` vs `list_active_users` is a real distinction carried
    # entirely by the quantifier; stripping it left the all-variant with no
    # terms of its own and reported it as redundant.
    "its",
    "their",
    "your",
    "our",
    "you",
    "they",
    "them",
    "there",
    "here",
    "then",
    "than",
    "not",
    "can",
    "will",
    "should",
    "must",
    "may",
    "also",
    "only",
    "just",
    "more",
    "most",
    "new",
    "old",
}

_SUFFIXES = ("ations", "ation", "ings", "ing", "ies", "ied", "es", "ed", "s")

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# A name that reads as an identifier rather than an ordinary word: it carries a
# separator or an internal capital. Used to decide whether an occurrence of the
# name in prose is plausibly a deliberate reference to the tool.
_IDENTIFIER_SHAPED = re.compile(r"[_.\-]|[a-z0-9][A-Z]")

# Wording that admits two tools are the same rather than explaining how they
# differ. A description carrying this is conceding the collision, not resolving
# it, and must not be treated as self-disambiguation.
_ALIAS_NOTICE = re.compile(
    # Deliberately excludes "use X instead": it reads as an alias notice but is
    # far more often ordinary disambiguation — "Do NOT use for forecasts, use
    # get_forecast instead" is a well-written tool doing exactly the right
    # thing, and matching it flagged this project's own clean sample. A
    # description that means "these are the same tool" says so unambiguously.
    r"\b(alias(ed)?\s+(for|of)|compatibility\s+alias|deprecated"
    r"|superseded\s+by|renamed\s+to"
    r"|same\s+as|equivalent\s+to|synonym\s+for)\b",
    re.IGNORECASE,
)


def _split_identifiers(text: str) -> str:
    """Break identifiers into their component words.

    ``search_orders``, ``search-orders`` and ``searchOrders`` all have to reduce
    to the same two words, or a tool name contributes one opaque token that
    always looks like a differentia and never is.
    """
    return _CAMEL_BOUNDARY.sub(" ", text).replace("_", " ").replace("-", " ")


def _stem_candidates(word: str) -> list[str]:
    """Every plausible base form of ``word``, longest-suffix-first.

    Returns candidates rather than one answer because a naive single-answer
    stemmer strips the wrong thing on short words — "does" loses "s" and becomes
    "doe", which then fails to match "do" in the synonym lexicon and manufactures
    a differentia that is not there. Generating candidates and letting the
    lexicon pick avoids that whole class of error.
    """
    out = [word]
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 2:
            base = word[: -len(suffix)]
            out.append(base + "y" if suffix == "ies" else base)
            # "searches" → "search" needs the trailing "e" restored after "es".
            if suffix in ("es", "ed", "ings", "ing"):
                out.append(base + "e")
    return out




def _canonical(word: str) -> str:
    """Map a word to the token that stands for its meaning class.

    Normalization is lexicon-driven and nothing else. A word reaches a meaning
    class only if some base form of it is listed; otherwise it stands for
    itself, unchanged.

    That restraint is deliberate. Stemming words the lexicon has never heard of
    destroys a distinction the lexicon was never asked about — and in tool
    naming the most common such distinction is **number**. `get_order` and
    `get_orders` are not two spellings of one tool; one returns a record and the
    other returns a collection, which is as real a difference as any. Collapsing
    them produced a confident "these are redundant, remove one" verdict on
    `get_user`/`get_users`, which is close to the most common naming convention
    there is.

    Contrast `docs` and `documentation`: genuinely one referent under two
    spellings, and both are listed, so both reach the same class. Synonymy is a
    claim about meaning and belongs in the lexicon. Suffix-stripping is a guess
    about spelling and does not.
    """
    lowered = word.lower()
    for candidate in _stem_candidates(lowered):
        if candidate in _SYNONYM_CLASS:
            return _SYNONYM_CLASS[candidate]
    return lowered


def _meaning_terms(tool: ToolDef) -> set[str]:
    """Canonical meaning-bearing terms for a tool, from its name and description.

    The name is included deliberately: namespacing is a real differentiator
    (``asana_search`` vs ``jira_search`` are distinguishable even with identical
    descriptions), and the synonym lexicon keeps it honest — ``process_ticket``
    and ``handle_ticket`` do *not* separate, because those verbs mean the same
    thing to a reader choosing between them.
    """
    text = _split_identifiers(f"{tool.name} {tool.description}")
    # Unicode-aware: `[a-z0-9]+` matched nothing at all in Chinese, Japanese,
    # Korean, Cyrillic or Arabic, and shredded accented Latin ("récupère" into
    # "r", "cup", "re"). `[^\W_]+` keeps every alphanumeric script and still
    # drops the underscore, which _split_identifiers has already handled.
    words = re.findall(r"[^\W_]+", text.lower(), re.UNICODE)
    # Filter on the surface form as well as the canonical one — stemming can
    # carry a word out of the reach of the filter that exists to catch it.
    keep = (
        w
        for w in words
        if w not in _STOPWORDS
        and w not in _NON_DISCRIMINATING
        and w not in _LOW_INFORMATION
    )
    return {_canonical(w) for w in keep} - {""}


_MIN_ANALYSABLE_TERMS = 2


def _is_analysable(tool: ToolDef) -> bool:
    """Whether this tool carries enough meaning to compare against another.

    Below two informative terms there is nothing to diagnose, and pretending
    otherwise is worse than staying quiet: set containment holds vacuously for
    an empty set, so an unreadable description reads as "dominated by" whatever
    it is compared with.
    """
    return len(_meaning_terms(tool)) >= _MIN_ANALYSABLE_TERMS


def _declared_alias(a: ToolDef, b: ToolDef) -> tuple[ToolDef, ToolDef] | None:
    """Return ``(alias, canonical)`` when one description admits it duplicates the other.

    Only counts when the description both carries alias wording *and* names the
    other tool. "Deprecated" on its own says nothing about which tool replaces
    it; "Compatibility alias for cogito_recall" says exactly that, and a model
    offered both has nothing to choose between.
    """
    for alias, canonical in ((a, b), (b, a)):
        if not canonical.name or not alias.description:
            continue
        if _ALIAS_NOTICE.search(alias.description) and (
            canonical.name.lower() in alias.description.lower()
        ):
            return alias, canonical
    return None


def _cross_references(a: ToolDef, b: ToolDef) -> bool:
    """True when either description explicitly names the other tool.

    A description that says "use get_forecast for future predictions" has already
    done the disambiguation work, and doing it inline is exactly what Anthropic's
    tool-authoring guidance recommends. Such a pair must never be reported.

    It also has to be excluded for a mechanical reason: naming the sibling pulls
    the sibling's vocabulary into this tool's term set, which can make a
    well-written description look like a subset of its neighbour and invert the
    measure. The best-written pairs would be the ones flagged.
    """

    # Naming the sibling is not always disambiguation. "Compatibility alias for
    # cogito_recall" names it in order to admit the two are the same tool — the
    # most certain collision there is — and suppressing that inverts the check.
    # Disambiguation says how the two differ; an alias notice says they do not.
    if _ALIAS_NOTICE.search(a.description) or _ALIAS_NOTICE.search(b.description):
        return False

    def mentions(text: str, target: ToolDef) -> bool:
        if not target.name:
            return False
        # Only an identifier-shaped name counts as a reference. A tool named
        # `access` matches inside "Manage Discord channel access", and treating
        # that as a deliberate pointer silenced genuinely near-duplicate
        # descriptions across a whole plugin family. A bare common word in prose
        # is not someone naming a tool; `get_forecast` is.
        if not _IDENTIFIER_SHAPED.search(target.name):
            return False
        # The identifier must appear verbatim, separator included. Matching the
        # name's *words* instead would be far too loose in both directions:
        # "handles a ticket" would count as referencing `do_ticket` because both
        # contain "ticket", and the prose "Get user data from the database"
        # opens with the exact word sequence of a sibling named `get_user`.
        # A real cross-reference names the tool, and naming it means writing it.
        return target.name.lower() in text.lower()

    return mentions(a.description, b) or mentions(b.description, a)


def _differentia(a: ToolDef, b: ToolDef) -> tuple[set[str], set[str]]:
    """Terms that could let a reader choose ``a`` over ``b``, and vice versa.

    Returns only *informative* terms — ones that actually narrow applicability.
    An empty pair on both sides means the two tools are indistinguishable.
    """
    ta, tb = _meaning_terms(a), _meaning_terms(b)

    only_a, only_b = ta - tb, tb - ta

    def informative(terms: set[str]) -> set[str]:
        # No length floor. Short tokens are frequently the entire distinction:
        # `v1`/`v2`, `get_po`/`get_so`, `top_10`/`top_100`. Discarding them made
        # genuinely different tools look identical and produced a confident
        # "remove one" recommendation for a version pair — the worst possible
        # advice, stated in the most confident voice. Function words like "up"
        # are already handled by _NON_DISCRIMINATING; length was never the right
        # proxy for "carries no meaning".
        return {
            t
            for t in terms
            if t not in _LOW_INFORMATION and t not in _NON_DISCRIMINATING
        }

    return informative(only_a), informative(only_b)


def detect_h1(config: AgentConfig) -> list[Finding]:
    """Detect tool description ambiguity."""
    findings: list[Finding] = []
    tools = config.tools
    if not tools:
        return findings

    for tool in tools:
        # Missing description
        if not tool.description or not tool.description.strip():
            findings.append(
                Finding(
                    pattern_id="H1",
                    sub_id="H1.1",
                    pattern_name="Tool Description Ambiguity",
                    severity=Severity.CRITICAL,
                    location=f"tool:{tool.name}",
                    description=f"Tool '{tool.name}' has no description.",
                    suggestion="Add a specific, disambiguating description that explains WHEN to use this tool, not just WHAT it does.",
                )
            )
            continue

        desc = tool.description.strip()

        # Very short description
        if len(desc) < 20:
            findings.append(
                Finding(
                    pattern_id="H1",
                    sub_id="H1.2",
                    pattern_name="Tool Description Ambiguity",
                    severity=Severity.HIGH,
                    location=f"tool:{tool.name}",
                    description=f"Tool '{tool.name}' has a very short description ({len(desc)} chars): \"{desc}\"",
                    suggestion="Expand description to include: purpose, when to use vs alternatives, expected input shape, output behavior.",
                    evidence=desc,
                )
            )

        # Vague leading verbs (strip punctuation)
        first_match = re.match(r"\w+", desc.lower()) if desc else None
        first_word = first_match.group() if first_match else ""
        if first_word in VAGUE_WORDS:
            findings.append(
                Finding(
                    pattern_id="H1",
                    sub_id="H1.3",
                    pattern_name="Tool Description Ambiguity",
                    severity=Severity.MEDIUM,
                    location=f"tool:{tool.name}",
                    description=f"Tool '{tool.name}' starts with vague verb '{first_word}'.",
                    suggestion=f"Replace '{first_word}' with a specific action verb. Instead of 'Handle user data', use 'Validate and persist user profile updates to the database'.",
                    evidence=desc[:80],
                )
            )

    # Duplicate tool names
    seen_names: dict[str, int] = {}
    for i, tool in enumerate(tools):
        lower_name = tool.name.lower()
        if lower_name in seen_names:
            findings.append(
                Finding(
                    pattern_id="H1",
                    sub_id="H1.4",
                    pattern_name="Tool Description Ambiguity",
                    severity=Severity.CRITICAL,
                    location=f"tool:{tool.name}",
                    description=f"Duplicate tool name '{tool.name}' (also at index {seen_names[lower_name]}). LLM cannot distinguish between identically-named tools.",
                    suggestion="Give each tool a unique, descriptive name.",
                )
            )
        else:
            seen_names[lower_name] = i

    # Cross-tool pair checks. H1.5 asks whether two descriptions are worded
    # alike; H1.6 asks whether either one distinguishes itself from the other.
    # A pair reported by H1.5 is not also reported by H1.6 — same defect, and
    # duplicate findings are how a linter loses trust.
    for i, t1 in enumerate(tools):
        for t2 in tools[i + 1 :]:
            if not t1.description or not t2.description:
                continue

            # A pair that disambiguates itself inline is already correct.
            # A declared alias needs no analysis — the description already says
            # the two are the same tool. Reported on the strength of the
            # declaration, because computing a differentia here would find one:
            # the words "compatibility alias for" are themselves terms one
            # description has and the other does not, so the notice would mask
            # the very collision it announces.
            # A tool we cannot read is not a tool that duplicates another.
            # Containment is vacuously true for an empty set, so a description
            # yielding no analysable terms would be reported as "dominated by"
            # every other tool in the file, with advice to delete it. That fired
            # on ordinary internationalized configs before tokenization became
            # Unicode-aware, and still would on a description of pure
            # punctuation. Silence is the only honest answer here.
            if not _is_analysable(t1) or not _is_analysable(t2):
                continue

            declared = _declared_alias(t1, t2)
            if declared is not None:
                alias, canonical = declared
                findings.append(
                    Finding(
                        pattern_id="H1",
                        sub_id="H1.6",
                        pattern_name="Tool Description Ambiguity",
                        severity=Severity.MEDIUM,
                        location=f"tool:{alias.name} vs tool:{canonical.name}",
                        description=(
                            f"Tool '{alias.name}' declares itself an alias of "
                            f"'{canonical.name}'. Both are offered to the model, which "
                            "has no basis for preferring one, and no description "
                            "distinguishes them because none is meant to."
                        ),
                        suggestion=(
                            f"Stop exposing '{alias.name}' to the model, or state what it "
                            "is for that the other is not. An alias kept for callers does "
                            "not need to be in the tool list."
                        ),
                        evidence=f"'{alias.description[:70]}'",
                    )
                )
                continue

            # A cross-reference answers H1.6's question and not H1.5's. Naming
            # the sibling explains how the two differ, so there is a differentia
            # and H1.6 should stay quiet — but it does not make the surrounding
            # prose any less near-duplicate, which is all H1.5 measures. The
            # guard used to skip the pair outright, so a bare "See check_status."
            # appended to an otherwise identical description silenced both.
            self_disambiguating = _cross_references(t1, t2)

            only_a, only_b = _differentia(t1, t2)

            overlap = _word_overlap(t1.description, t2.description)
            # H1.5 reports a fact about the descriptions and nothing else. An
            # earlier version suppressed it when the tool NAMES differed, on the
            # theory that `asana_search` / `jira_search` are disambiguated by
            # their prefix. That was wrong in a way that cost real recall: names
            # feed the term set, so *any* two distinct names produced a
            # differentia and silenced the check — `get_invoice_pdf` and
            # `get_receipt_pdf` with byte-identical descriptions stopped being
            # reported at all. Two identical descriptions are worth saying out
            # loud even when a name carries the distinction, because then the
            # description is doing no work. Name-awareness belongs in H1.6,
            # which asks a different question.
            if overlap > 0.7:
                findings.append(
                    Finding(
                        pattern_id="H1",
                        sub_id="H1.5",
                        pattern_name="Tool Description Ambiguity",
                        severity=Severity.HIGH,
                        location=f"tool:{t1.name} vs tool:{t2.name}",
                        description=f"Tools '{t1.name}' and '{t2.name}' have {overlap:.0%} word overlap — LLM may confuse them.",
                        suggestion="Differentiate descriptions by adding WHEN to use each tool. E.g., 'Use X for new records, use Y for updates to existing records'.",
                        evidence=f"'{t1.description[:50]}...' vs '{t2.description[:50]}...'",
                    )
                )
                continue

            if self_disambiguating:
                continue

            # Two distinct defects, not one. Mutual emptiness means neither tool
            # distinguishes itself. One-sided emptiness — domination — means one
            # tool's every term is already covered by the other, so a model has
            # no reason to ever reach for it. Domination is the more actionable
            # of the two, because it names which tool must be repaired.
            if not only_a and not only_b:
                findings.append(
                    Finding(
                        pattern_id="H1",
                        sub_id="H1.6",
                        pattern_name="Tool Description Ambiguity",
                        # MEDIUM, deliberately. FAIL (and therefore
                        # `--fail-on fail`, which the shipped Action uses) keys
                        # on CRITICAL/HIGH. H1.6 is new and its recall is not
                        # yet measured against a labelled corpus, so it should
                        # inform a build, not break one. Raise to HIGH when
                        # there are numbers to justify it.
                        severity=Severity.MEDIUM,
                        location=f"tool:{t1.name} vs tool:{t2.name}",
                        description=(
                            f"Tools '{t1.name}' and '{t2.name}' carry no differentia — "
                            "every meaning-bearing term in one is present, or has a synonym, "
                            "in the other. Both descriptions may be accurate and still give "
                            "a model nothing to choose between them."
                        ),
                        suggestion=(
                            "Name a condition that selects one over the other. State what each "
                            "tool is for that the other is NOT for — e.g. 'use X for orders "
                            "already placed, use Y for carts not yet submitted'."
                        ),
                        evidence=f"'{t1.description[:50]}' vs '{t2.description[:50]}'",
                    )
                )
            elif not only_a or not only_b:
                dominated, dominant = (t1, t2) if not only_a else (t2, t1)
                distinguishing = sorted(only_a or only_b)
                findings.append(
                    Finding(
                        pattern_id="H1",
                        sub_id="H1.6",
                        pattern_name="Tool Description Ambiguity",
                        # warn-only; see the H1.6 severity note above
                        severity=Severity.MEDIUM,
                        location=f"tool:{dominated.name} vs tool:{dominant.name}",
                        description=(
                            f"Tool '{dominated.name}' is dominated by '{dominant.name}' — "
                            f"every meaning-bearing term in '{dominated.name}' also appears, "
                            f"or has a synonym, in '{dominant.name}', which additionally names "
                            f"{', '.join(repr(t) for t in distinguishing[:4])}. A model has no "
                            f"reason to select '{dominated.name}' over '{dominant.name}'."
                        ),
                        suggestion=(
                            f"Add to '{dominated.name}' a term that '{dominant.name}' does not "
                            "use, naming what it is for that the other is not. If the two are "
                            "genuinely redundant, remove one."
                        ),
                        evidence=f"'{dominated.description[:50]}' vs '{dominant.description[:50]}'",
                    )
                )

    return findings


_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "is",
    "it",
    "this",
    "that",
    "be",
    "as",
}


def _word_overlap(a: str, b: str) -> float:
    """Jaccard similarity of word sets (excluding stopwords)."""
    wa = set(re.findall(r"\w+", a.lower())) - _STOPWORDS
    wb = set(re.findall(r"\w+", b.lower())) - _STOPWORDS
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


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


DANGEROUS_PATTERNS = [
    (r"keep\s+trying\s+until", "Unbounded retry loop — 'keep trying until' needs an explicit limit."),
    (_RETRY_UNTIL_PATTERN, "Unbounded retry — add max_retries or a fallback."),
    (r"don'?t\s+stop\s+until", "Negative termination condition — rephrase as a positive bound."),
    (r"loop\s+(?:through|over|until)", "Potential infinite loop — ensure a max iteration count."),
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


def _is_negated_retry_prohibition(text: str, retry_start: int) -> bool:
    """Return whether an adjacent negation forbids, rather than requires, retrying."""
    prefix = text[max(0, retry_start - 20) : retry_start]
    return bool(_NEGATED_RETRY_PROHIBITION.search(prefix))


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

EROSION_PATTERNS = [
    (r"remember\s+everything", "Unbounded memory — context will grow until it erodes task boundaries."),
    (
        r"use\s+(?:all|entire)\s+(?:conversation|history|context)",
        "Referencing entire history without scoping — promotes boundary erosion.",
    ),
    (r"always\s+(?:keep|maintain|remember)", "Persistence without scope — specify WHAT to persist and for HOW LONG."),
]


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
