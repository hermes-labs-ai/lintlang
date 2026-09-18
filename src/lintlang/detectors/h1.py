"""H1: Tool Description Ambiguity detector."""

from __future__ import annotations

import re

from ..models import AgentConfig, Finding, Severity, ToolDef

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
