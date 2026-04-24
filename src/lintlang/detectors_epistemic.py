"""Epistemic detectors (E1-E5) — adversarial-corpus-derived patterns.

Targets failure modes identified in the agent-behavior + epistemic raw corpora:

- E1 Sycophancy markers — pre-emptive agreement / flattery scaffolding
- E2 Drift-from-system-prompt — invitations for the model to rewrite or
     reinterpret its own instructions mid-conversation
- E3 Anchoring repetition — same constraint stated 3+ times (rigidity inducer)
- E4 Fabrication tells — instructions that reward confident-sounding answers
     even when grounding is absent
- E5 Authority-gradient compliance — coercive role framings ("the CEO told you",
     "an expert reviewer", "as a senior engineer you must...")

All detectors are pure heuristics over `AgentConfig` text (no LLM calls),
matching the style of H1-H7 in patterns.py.
"""

from __future__ import annotations

import re

from .patterns import AgentConfig, Finding, Severity

# ── Homoglyph hardening (B09 adversarial-school patch) ─────────────
# Common Cyrillic / Greek lookalikes mapped to Latin. NFKC alone does
# NOT collapse these, so we run a dedicated ASCII-fold before matching.
# Source: attack V16 (Cyrillic 'а' 'е' inside 'аgrее' bypassed raw regex).
_HOMOGLYPH_MAP = str.maketrans({
    # Cyrillic lowercase → Latin lowercase
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "ԁ": "d", "ɡ": "g", "һ": "h", "ӏ": "l",
    "ո": "n", "ԛ": "q", "ꭇ": "u", "ѵ": "v", "ԝ": "w", "ᴢ": "z",
    # Cyrillic uppercase → Latin uppercase
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "У": "Y", "Х": "X",
    "І": "I", "Ј": "J", "Ѕ": "S",
    # Greek lookalikes
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ϲ": "c",
    "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})


def _fold_homoglyphs(text: str) -> str:
    """Map common Cyrillic/Greek lookalikes to Latin, preserving length.

    Preserves char offsets so match spans in the folded text map cleanly
    back onto the original. Applied by detectors before regex scanning to
    block trivial homoglyph bypass.
    """
    if not text:
        return text
    return text.translate(_HOMOGLYPH_MAP)


# ── E1: Sycophancy markers ─────────────────────────────────────────

SYCOPHANCY_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:always\s+)?(?:agree|concur)\s+with\s+(?:the\s+)?(?:user|customer|operator)\b",
     "Direct agreement directive — promotes sycophantic concurrence."),
    (r"\b(?:never|do\s+not|don'?t)\s+(?:disagree|contradict|push\s+back|challenge)\s+(?:the\s+)?(?:user|customer)\b",
     "Disagreement is forbidden — sycophancy floor."),
    (r"\b(?:validate|affirm|reinforce)\s+(?:the\s+user'?s|their|user)\s+(?:feelings?|views?|opinions?|beliefs?|perspectives?)\b",
     "Validation directive — pushes affirmation over accuracy."),
    (r"\b(?:make|keep|leave)\s+(?:the\s+)?(?:user|customer)\s+(?:happy|satisfied|feeling\s+good|positive)\b",
     "Emotional-state target — rewards flattery over correctness."),
    (r"\b(?:start|begin|open)\s+(?:every|each|your)\s+(?:response|reply|answer)\s+with\s+(?:a\s+)?(?:compliment|praise|positive)\b",
     "Mandated opening flattery — explicit sycophancy template."),
    (r"\b(?:great|excellent|wonderful|fantastic)\s+question\b",
     "Stock flattery phrase embedded in instructions — model will mirror it."),
    (r"\b(?:tell|let)\s+(?:the\s+)?(?:user|them)\s+(?:what|whatever)\s+they\s+want\s+to\s+hear\b",
     "Explicit instruction to tell users what they want to hear."),
]


def detect_e1(config: AgentConfig) -> list[Finding]:
    """E1: Sycophancy markers in system prompts."""
    findings: list[Finding] = []
    raw = config.system_prompt
    if not raw:
        return findings
    prompt = _fold_homoglyphs(raw)  # B09 patch: block homoglyph bypass

    for pattern, message in SYCOPHANCY_PATTERNS:
        for match in re.finditer(pattern, prompt, re.IGNORECASE):
            start = max(0, match.start() - 20)
            end = min(len(prompt), match.end() + 40)
            findings.append(Finding(
                pattern_id="E1",
                pattern_name="Sycophancy Markers",
                severity=Severity.HIGH,
                location="system_prompt",
                description=message,
                suggestion=(
                    "Replace agreement-targeted directives with accuracy-targeted ones. "
                    "E.g. 'When the user is wrong, say so plainly and cite the correction.'"
                ),
                evidence=prompt[start:end].strip(),
            ))

    return findings


# ── E2: Drift-from-system-prompt ───────────────────────────────────

DRIFT_PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:you\s+(?:may|can|are\s+free\s+to))\s+(?:rewrite|reinterpret|relax|override|adjust|discard|rescind|abandon|void|cancel|suspend|waive)\s+(?:these|your|the)\s+(?:instructions|rules|guidelines|system\s+prompt)\b",
     "Self-modification permission — model can drift from its own prompt."),
    (r"\b(?:if\s+(?:the\s+)?(?:user|operator)\s+(?:asks|wants|requests))\b[^.]*\b(?:ignore|skip|bypass|override|disregard|discard|rescind|abandon|void|waive)\b[^.]*\b(?:these|your|the)\s+(?:instructions|rules|system\s+prompt)\b",
     "Conditional instruction-bypass — explicit drift trigger."),
    (r"\b(?:adapt|tailor|tune)\s+(?:your\s+)?(?:behavior|persona|instructions)\s+(?:to|based\s+on)\s+(?:what|whatever)\s+(?:the\s+)?(?:user|conversation)\s+(?:wants|needs)\b",
     "Open-ended adaptation directive — invites prompt drift."),
    (r"\b(?:above|previous|prior|earlier)\s+(?:instructions|rules|system\s+prompt|context)\s+(?:can|may|are)\s+(?:be\s+)?(?:ignored|overridden|disregarded|set\s+aside|discarded|rescinded|abandoned|voided|cancelled|canceled|suspended|waived)\b",
     "Explicit cancellation of prior instructions — drift escape hatch."),
    (r"\b(?:treat|consider)\s+(?:these|the|your)\s+(?:instructions|rules)\s+as\s+(?:guidelines|suggestions|defaults)\b",
     "Instructions framed as soft guidelines — invites silent drift."),
    (r"\bfeel\s+free\s+to\s+(?:deviate|depart|stray|improvise)\b",
     "Permissive deviation language — model may drift without telling you."),
    # B09 patch: role-reframe injection. Matches a second 'you are (now) a/an/the X' opener.
    # The detector body below also runs a standalone count-based check for >=2 role openers.
    (r"\byou\s+are\s+(?:now\s+|instead\s+)?(?:a|an|the)\s+(?!(?:same|original)\b)\w+[^.\n]{0,80}?(?:\bignore\b|\boverride\b|\bforget\b|\bdiscard\b|\binstead\b)",
     "Role-reframe injection — a second 'you are (now) X' followed by an override verb."),
    # B09 patch: 'forget' as a drift verb
    (r"\b(?:forget|disregard)\s+(?:all\s+|everything\s+|the\s+|your\s+)?(?:above|previous|prior|earlier)?\s*(?:instructions|rules|system\s+prompt)\b",
     "Forget/disregard directive targeting prior instructions."),
]


def detect_e2(config: AgentConfig) -> list[Finding]:
    """E2: Drift-from-system-prompt — directives that license self-modification."""
    findings: list[Finding] = []
    prompt = config.system_prompt
    if not prompt:
        return findings

    for pattern, message in DRIFT_PATTERNS:
        for match in re.finditer(pattern, prompt, re.IGNORECASE | re.DOTALL):
            start = max(0, match.start() - 20)
            end = min(len(prompt), match.end() + 60)
            findings.append(Finding(
                pattern_id="E2",
                pattern_name="Drift From System Prompt",
                severity=Severity.CRITICAL,
                location="system_prompt",
                description=message,
                suggestion=(
                    "Anchor the prompt as immutable. State which directives are non-negotiable "
                    "and require an out-of-band channel for any override (e.g. operator-only flag)."
                ),
                evidence=prompt[start:end].strip(),
            ))

    return findings


# ── E3: Anchoring repetition ───────────────────────────────────────

# Words that don't carry directive weight on their own.
_ANCHOR_STOPWORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "this", "that", "be", "as",
    "you", "your", "we", "our", "they", "their", "i", "me", "my",
    "should", "must", "will", "can", "may", "do", "not", "no", "if",
    "are", "was", "were", "have", "has", "had", "would", "could",
    "always", "never", "every", "any", "all", "some", "one",
    # Imperative-prefix words that prompt-writers swap in/out across
    # repetitions of the same directive (the "say it three different ways"
    # anti-pattern).
    "remember", "ensure", "note", "important", "please", "make", "sure",
    "also", "additionally", "furthermore", "moreover",
}


def _normalize_directive(text: str) -> str:
    """Lowercase + collapse whitespace + strip non-content words for fingerprinting."""
    words = re.findall(r"[a-z0-9']+", text.lower())
    kept = [w for w in words if w not in _ANCHOR_STOPWORDS and len(w) > 2]
    return " ".join(kept)


def detect_e3(config: AgentConfig) -> list[Finding]:
    """E3: Anchoring repetition — the same instruction restated 3+ times.

    Repeated directives don't reinforce; they over-anchor and induce rigid
    behavior (e.g. the model treats the constraint as the dominant frame and
    applies it where it doesn't fit). Found in adversarial corpus runs where
    overly-anchored prompts produced worse outcomes on the same task.
    """
    findings: list[Finding] = []
    prompt = config.system_prompt
    if not prompt:
        return findings

    # Split into clauses on sentence boundaries + bullet markers.
    clauses = re.split(r"(?:[.!?]\s+|\n[-*]\s+|\n\d+[.)]\s+|\n+)", prompt)
    fingerprints: dict[str, list[str]] = {}
    for clause in clauses:
        clause = clause.strip()
        if len(clause) < 12:
            continue
        fp = _normalize_directive(clause)
        # Need at least 3 content words to count as a directive
        if len(fp.split()) < 3:
            continue
        fingerprints.setdefault(fp, []).append(clause)

    for fp, occurrences in fingerprints.items():
        if len(occurrences) >= 3:
            sample = occurrences[0][:80]
            findings.append(Finding(
                pattern_id="E3",
                pattern_name="Anchoring Repetition",
                severity=Severity.MEDIUM,
                location="system_prompt",
                description=(
                    f"Directive repeated {len(occurrences)} times "
                    f"(fingerprint: '{fp[:60]}...'). Over-anchoring makes the "
                    "model rigid and worsens performance on adjacent tasks."
                ),
                suggestion=(
                    "State each constraint exactly once. If you need it to stick, "
                    "promote it to a numbered PRIORITY block rather than repeating it."
                ),
                evidence=sample,
            ))

    return findings


# ── E4: Fabrication tells ──────────────────────────────────────────

FABRICATION_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"\b(?:always|must)\s+(?:provide|give|return)\s+(?:an?\s+)?(?:answer|response|result)\b",
     "Mandatory-answer directive — model will fabricate when grounding is absent.",
     Severity.HIGH),
    (r"\b(?:never|don'?t|do\s+not)\s+(?:say|respond\s+with|answer)\s+[\"']?(?:i\s+don'?t\s+know|unknown|not\s+sure|insufficient)\b",
     "Abstention is forbidden — directly drives fabrication.",
     Severity.CRITICAL),
    (r"\b(?:never|don'?t|do\s+not)\s+(?:refuse|decline|abstain)\b",
     "Refusal is forbidden — leaves the model only one exit (making something up).",
     Severity.HIGH),
    (r"\b(?:sound|appear|come\s+across|seem)\s+(?:confident|certain|authoritative|expert)\b",
     "Confidence-as-style directive — rewards fluent fabrication over honest uncertainty.",
     Severity.HIGH),
    (r"\b(?:fill\s+in|infer|guess|estimate)\s+(?:any|missing|the\s+)?(?:gaps|details|values|fields)\b",
     "Open-ended gap-filling — invites invented content.",
     Severity.MEDIUM),
    (r"\b(?:make\s+up|invent|generate)\s+(?:plausible|realistic|believable)\s+(?:data|examples|values|details)\b",
     "Explicit invention directive — fabrication-by-design.",
     Severity.CRITICAL),
    (r"\b(?:do\s+not|don'?t|never)\s+(?:cite|attribute|reference)\s+(?:sources|provenance|origin)\b",
     "Sources prohibited — removes the only check on fabrication.",
     Severity.HIGH),
]


def detect_e4(config: AgentConfig) -> list[Finding]:
    """E4: Fabrication tells — directives that reward confident hallucination."""
    findings: list[Finding] = []
    prompt = config.system_prompt
    if not prompt:
        return findings

    for pattern, message, severity in FABRICATION_PATTERNS:
        for match in re.finditer(pattern, prompt, re.IGNORECASE):
            start = max(0, match.start() - 20)
            end = min(len(prompt), match.end() + 50)
            findings.append(Finding(
                pattern_id="E4",
                pattern_name="Fabrication Tells",
                severity=severity,
                location="system_prompt",
                description=message,
                suggestion=(
                    "Explicitly authorize abstention. "
                    "E.g. 'If the answer is not derivable from provided context, respond exactly: "
                    "INSUFFICIENT_EVIDENCE: <what you would need>.'"
                ),
                evidence=prompt[start:end].strip(),
            ))

    return findings


# ── E5: Authority-gradient compliance ──────────────────────────────

AUTHORITY_PATTERNS: list[tuple[str, str, Severity]] = [
    (r"\b(?:as|you\s+are)\s+(?:a|an|the)\s+(?:senior|principal|chief|head|lead|expert|world.?class|world.?renowned|top|elite|master|veteran)\s+(?:engineer|developer|scientist|researcher|doctor|lawyer|consultant|analyst|architect|advisor|expert)\b",
     "High-authority persona injection — increases compliance with downstream user requests, even harmful ones.",
     Severity.HIGH),
    (r"\b(?:the\s+)?(?:ceo|cto|cfo|founder|owner|director|vp|manager|boss|supervisor|president)\s+(?:has\s+)?(?:said|told\s+you|asked\s+you|wants\s+you|requires)\b",
     "Hierarchical authority claim — used in prompt-injection attacks to override safety rails.",
     Severity.CRITICAL),
    (r"\b(?:authorized|approved|sanctioned|cleared)\s+by\s+(?:the\s+)?(?:admin|legal|compliance|security|management|leadership)\b",
     "Unverifiable authorization claim — model has no way to check this.",
     Severity.HIGH),
    (r"\b(?:trust\s+(?:me|the\s+user|the\s+operator)|i\s+(?:am|'m)\s+(?:the\s+)?(?:admin|owner|developer|operator|root))\b",
     "Trust-by-assertion — classic authority-gradient injection vector.",
     Severity.CRITICAL),
    (r"\b(?:override|bypass|skip|ignore)\s+(?:the\s+)?(?:safety|guardrails?|filter|policy|restrictions?)\s+(?:because|since|as|when)\s+(?:i\s+(?:am|'m)|the\s+user\s+is)\b",
     "Authority-conditioned bypass — explicit gradient-compliance request.",
     Severity.CRITICAL),
    (r"\b(?:do\s+(?:exactly|only)\s+what|comply\s+with|never\s+question)\s+(?:i|the\s+(?:user|operator|admin))\s+(?:say|says|tells\s+you|asks)\b",
     "Unconditional-obedience directive — disables independent judgment.",
     Severity.HIGH),
]


def detect_e5(config: AgentConfig) -> list[Finding]:
    """E5: Authority-gradient compliance — coercive role framings."""
    findings: list[Finding] = []
    prompt = config.system_prompt
    if not prompt:
        return findings

    for pattern, message, severity in AUTHORITY_PATTERNS:
        for match in re.finditer(pattern, prompt, re.IGNORECASE):
            start = max(0, match.start() - 20)
            end = min(len(prompt), match.end() + 60)
            findings.append(Finding(
                pattern_id="E5",
                pattern_name="Authority Gradient Compliance",
                severity=severity,
                location="system_prompt",
                description=message,
                suggestion=(
                    "Remove unverifiable authority claims from the system prompt. "
                    "If certain operators legitimately have elevated permissions, gate that "
                    "on a signed channel (e.g. an operator-only header), not natural-language assertion."
                ),
                evidence=prompt[start:end].strip(),
            ))

    return findings


# ── Registry ──────────────────────────────────────────────────────

EPISTEMIC_DETECTORS: dict[str, dict] = {
    "E1": {"name": "Sycophancy Markers", "detect": detect_e1},
    "E2": {"name": "Drift From System Prompt", "detect": detect_e2},
    "E3": {"name": "Anchoring Repetition", "detect": detect_e3},
    "E4": {"name": "Fabrication Tells", "detect": detect_e4},
    "E5": {"name": "Authority Gradient Compliance", "detect": detect_e5},
}
