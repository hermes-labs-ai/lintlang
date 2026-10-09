"""Turkish action directives and concrete purposes from the labeled corpus.

The generic suffix için occurs in both groups. Only the observed action
directives and task-specific purpose clauses become canonical triggers.
"""

import re

_MAP = (
    # u-565265c5f7ec, postgres-patterns: an actionable query-optimization
    # purpose, optionally followed by the corpus's comma-separated tasks.
    (r"\bsorgu optimizasyonu(?:\s*,[^.;!?\n]{1,100})?\s+için\b", " use for query optimization "),
    # u-cb937cb9f59f, deployment-patterns: production-readiness purpose.
    (r"\biçin üretim hazırlığı\b", " use for production readiness "),
    # u-390e93ea4d84, api-design: rate-limiting applicability.
    (r"\biçin hız sınırlama\b", " use for rate limiting "),
    # u-88ae4028433e, database-migrations: deployment purpose.
    (r"\bdeployment'ları için\b", " use for deployments "),
    # u-a732d5b69c22, docker-patterns: service-orchestration purpose.
    (r"\borkestrasyon için\b", " use for orchestration "),
    # u-2eb887f210fd, continuous-learning: imperative extract-and-save task.
    (r"\bçıkarın\b", " use to extract "),
    (r"\bbu skill'i kullanın\b", " use this "),
    (r"\boluşturmak için\b(?!\s+kullanma(?:yın|yınız)?\b)", " use for building "),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), replacement) for pattern, replacement in _MAP)
_EXCLUSION = re.compile(r"\b(?:kullanma(?:yın|yınız)?|değil(?:dir)?|içermez)\b", re.IGNORECASE)
_NEVER = re.compile(r"\basla\s*$", re.IGNORECASE)


def _negated(text: str, match: re.Match[str]) -> bool:
    # Keep exclusion checks local to this clause, with a bounded lookahead
    # so repeated task cues do not rescan an entire long description.
    if _NEVER.search(text, max(0, match.start() - 12), match.start()):
        return True
    clause = re.split(r"[.;!?\n]", text[match.end():match.end() + 160], maxsplit=1)[0]
    return bool(_EXCLUSION.search(clause))


def normalize(text: str) -> str:
    """Map observed use cues without stemming Turkish words."""
    for pattern, replacement in _COMPILED:
        text = pattern.sub(
            lambda match, source=text, canonical=replacement:
                match.group() if _negated(source, match) else canonical,
            text,
        )
    return text
