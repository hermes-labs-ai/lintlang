"""Korean activation clause mined from labeled skill descriptions.

The KEEP-only corpus has no Korean activation cue. Two additional labeled
FPs in the same frozen corpus (ESCALATE) share this explicit use directive;
it occurs in none of the twelve Korean TPs. Generic 위한/사용 and method
clauses remain unchanged.
"""

import re

# (Korean pattern, canonical English trigger), most-specific first.
_MAP: list[tuple[str, str]] = [
    # security-review, u-4523f71beaef; tdd-workflow, u-eed217343bb1.
    (r"(?<!\w)시 이 스킬을 사용하세요(?=[.!。！]|$)", " use this when "),
]
_COMPILED = tuple((re.compile(pattern), replacement) for pattern, replacement in _MAP)


def normalize(text: str) -> str:
    """Map the observed positive directive, leaving other Korean text intact."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    return text
