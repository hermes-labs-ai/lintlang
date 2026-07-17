"""Small finite-state scope classifier over original Python code points."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ScopeKind

_HYPOTHETICAL_CUE = re.compile(r"\b(?:hypothetically|in\s+a\s+hypothetical|suppose|imagine)\b", re.IGNORECASE)
_METALINGUISTIC_CUE = re.compile(
    r"\b(?:the\s+phrase|(?:analy[sz]e|discuss|rewrite|avoid|use)\s+"
    r"(?:the\s+)?(?:phrase|wording|prompt|question))\b",
    re.IGNORECASE,
)
_NEGATED_CUE = re.compile(
    r"\b(?:do\s+not|don['’]t|never)\s+(?:ask|say|claim|write|use|phrase)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ScopeAnalysis:
    scopes: tuple[ScopeKind, ...]
    unavailable_reason: str | None = None

    def is_direct(self, start: int, end: int) -> bool:
        return 0 <= start < end <= len(self.scopes) and all(
            scope is ScopeKind.DIRECT for scope in self.scopes[start:end]
        )


def _mark(scopes: list[ScopeKind], start: int, end: int, kind: ScopeKind) -> None:
    for index in range(start, end):
        if scopes[index] is ScopeKind.DIRECT:
            scopes[index] = kind


def _paired_token_regions(
    text: str,
    scopes: list[ScopeKind],
    token: str,
    kind: ScopeKind,
    label: str,
) -> str | None:
    positions: list[int] = []
    start = 0
    while True:
        index = text.find(token, start)
        if index < 0:
            break
        if all(scopes[pos] is ScopeKind.DIRECT for pos in range(index, index + len(token))):
            positions.append(index)
        start = index + len(token)
    if len(positions) % 2:
        return f"unclosed {label} delimiter"
    for offset in range(0, len(positions), 2):
        _mark(scopes, positions[offset], positions[offset + 1] + len(token), kind)
    return None


def _ascii_single_quote_regions(text: str, scopes: list[ScopeKind]) -> str | None:
    opening: int | None = None
    for index, char in enumerate(text):
        if char != "'" or scopes[index] is not ScopeKind.DIRECT:
            continue
        left_alnum = index > 0 and text[index - 1].isalnum()
        right_alnum = index + 1 < len(text) and text[index + 1].isalnum()
        if opening is None:
            # Contractions and trailing possessives are apostrophes, not openers.
            if left_alnum:
                continue
            if right_alnum:
                opening = index
        elif not right_alnum:
            _mark(scopes, opening, index + 1, ScopeKind.QUOTED)
            opening = None
    if opening is not None:
        return "unclosed single-quote delimiter"
    return None


def _smart_quote_regions(text: str, scopes: list[ScopeKind]) -> str | None:
    pairs = (("“", "”", "smart double-quote"), ("‘", "’", "smart single-quote"))
    for opening_char, closing_char, label in pairs:
        opening: int | None = None
        for index, char in enumerate(text):
            if scopes[index] is not ScopeKind.DIRECT:
                continue
            if char == opening_char:
                if opening is not None:
                    return f"nested {label} delimiter"
                opening = index
            elif char == closing_char:
                if opening is None:
                    # Curly apostrophes in contractions are not quote closers.
                    if closing_char == "’" and index > 0 and text[index - 1].isalnum():
                        continue
                    return f"misordered {label} delimiter"
                _mark(scopes, opening, index + 1, ScopeKind.QUOTED)
                opening = None
        if opening is not None:
            return f"unclosed {label} delimiter"
    return None


def _validate_nesting(text: str, scopes: list[ScopeKind]) -> str | None:
    opening_for = {")": "(", "]": "[", "}": "{"}
    openers = set(opening_for.values())
    stack: list[tuple[str, int]] = []
    for index, char in enumerate(text):
        if scopes[index] is not ScopeKind.DIRECT:
            continue
        if char in openers:
            stack.append((char, index))
        elif char in opening_for:
            if not stack or stack[-1][0] != opening_for[char]:
                return "misordered nesting delimiter"
            stack.pop()
    if stack:
        return "unclosed nesting delimiter"
    return None


def _sentence_end(text: str, start: int) -> int:
    for index in range(start, len(text)):
        if text[index] in ".?!\n":
            return index + 1
    return len(text)


def analyze_scope(text: str) -> ScopeAnalysis:
    """Classify scope without normalizing or changing original offsets."""

    scopes = [ScopeKind.DIRECT] * len(text)

    reason = _paired_token_regions(text, scopes, "```", ScopeKind.CODE, "fenced-code")
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)
    reason = _paired_token_regions(text, scopes, "`", ScopeKind.CODE, "inline-code")
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)
    reason = _paired_token_regions(text, scopes, '"', ScopeKind.QUOTED, "ASCII double-quote")
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)
    reason = _smart_quote_regions(text, scopes)
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)
    reason = _ascii_single_quote_regions(text, scopes)
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)
    reason = _validate_nesting(text, scopes)
    if reason:
        return ScopeAnalysis(tuple(scopes), reason)

    for pattern, kind in (
        (_HYPOTHETICAL_CUE, ScopeKind.HYPOTHETICAL),
        (_METALINGUISTIC_CUE, ScopeKind.METALINGUISTIC),
        (_NEGATED_CUE, ScopeKind.NEGATED),
    ):
        for match in pattern.finditer(text):
            if scopes[match.start()] is ScopeKind.DIRECT:
                _mark(scopes, match.start(), _sentence_end(text, match.end()), kind)

    return ScopeAnalysis(tuple(scopes))
