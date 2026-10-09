"""English purpose/timing cues missed by the canonical H1.8 regex.

These phrases were mined from FPs, not added to _SKILL_TRIGGER. Topic lists
(e.g. "best practices") and tool implementation methods remain unchanged.
"""

import re

_MAP = (
    (r"\bfor building\b", " use for building "),
    (r"\bfor interacting with and testing\b", " use for interacting with and testing "),
    (r"\bfor query optimization\b", " use for query optimization "),
    (r"\bat logical intervals\b", " when at logical intervals "),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), replacement) for pattern, replacement in _MAP)
_NEGATED = re.compile(r"\b(?:not|never)\s*$", re.IGNORECASE)


def _negated(text: str, offset: int) -> bool:
    word_end = offset
    while word_end and text[word_end - 1].isspace():
        word_end -= 1
    # Inspect only the preceding word, avoiding a full-prefix search for
    # each repeated cue in a long description.
    return bool(_NEGATED.search(text, max(0, word_end - 6), offset))


def normalize(text: str) -> str:
    """Expose mined purpose and timing clauses to the existing English gate."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(
            lambda match, source=text, canonical=replacement:
                match.group() if _negated(source, match.start()) else canonical,
            text,
        )
    return text
