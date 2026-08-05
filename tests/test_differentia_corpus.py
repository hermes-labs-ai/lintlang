"""Precision tripwire for H1.6 against real, independently-authored descriptions.

Every other H1.6 test uses a pair someone chose to demonstrate a behaviour. That
is how the detector shipped false positives twice: the cases were selected to
match the design. This module measures it against text nobody wrote for us, and
freezes the result, so that a later lexicon edit cannot buy recall with silent
precision loss.

The corpus is NOT vendored. It is read from the locally installed Claude Code
plugin marketplace when present, and the module skips otherwise. That keeps
third-party description text out of this repository while keeping the
measurement reproducible on any machine that has the marketplace.

Baseline measured 2026-08-05 by this module's own loader: 76 descriptions from
independent plugin authors, 2850 pairs.

    pair findings (H1.5 + H1.6)   0
    pairs within 1 term of firing 10
    pairs within 2 terms          23

Zero findings is the expected result and the important one: these are curated,
well-differentiated descriptions and a linter that fires on them is noise. The
near-miss counts are recorded alongside because they are what distinguishes
"correctly quiet" from "inert" — the nearest pair, `agent-sdk-verifier-py` vs
`agent-sdk-verifier-ts`, is separated by exactly one term ("python").

If a change moves these numbers, that is a real finding about the change. Decide
deliberately and update the constants with a note; do not adjust them to make a
red test green.
"""

from __future__ import annotations

import itertools
import os
import re
from pathlib import Path

import pytest

from lintlang.patterns import AgentConfig, ToolDef, _differentia, detect_h1

MARKETPLACE = Path(
    os.path.expanduser("~/.claude/plugins/marketplaces/claude-plugins-official")
)

EXPECTED_PAIR_FINDINGS = 0
EXPECTED_WITHIN_1 = 10
EXPECTED_WITHIN_2 = 23
MIN_CORPUS_SIZE = 60

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.S)
_NAME = re.compile(r"^name:\s*(.+)$", re.M)
_DESCRIPTION = re.compile(r"^description:\s*(.+?)(?=\n[a-z_-]+:\s|\Z)", re.S | re.M)


def _load_corpus() -> list[ToolDef]:
    """Real skill/agent/command descriptions from independent plugin authors."""
    seen: dict[str, str] = {}
    for path in MARKETPLACE.rglob("*.md"):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        matter = _FRONTMATTER.match(text)
        if not matter:
            continue
        block = matter.group(1)
        described = _DESCRIPTION.search(block)
        if not described:
            continue
        description = " ".join(described.group(1).split())
        if len(description) < 12:
            continue
        named = _NAME.search(block)
        name = named.group(1).strip() if named else path.parent.name
        # Key on owning plugin + name: two plugins may each ship a skill called
        # "commands", and both are legitimate independent entries.
        parts = path.relative_to(MARKETPLACE).parts
        plugin = parts[1] if len(parts) > 1 else parts[0]
        seen.setdefault(f"{plugin}\t{name}", description)
    return [ToolDef(key.split("\t", 1)[1], desc) for key, desc in sorted(seen.items())]


@pytest.fixture(scope="module")
def corpus() -> list[ToolDef]:
    if not MARKETPLACE.is_dir():
        pytest.skip(f"plugin marketplace not installed at {MARKETPLACE}")
    tools = _load_corpus()
    if len(tools) < MIN_CORPUS_SIZE:
        pytest.skip(f"corpus too small to be meaningful ({len(tools)} descriptions)")
    return tools


def test_no_false_positives_on_real_descriptions(corpus):
    """The precision half of the guarantee."""
    findings = [
        f
        for f in detect_h1(AgentConfig(tools=corpus))
        if f.code in ("H1.5", "H1.6")
    ]
    detail = "\n".join(f"  {f.code} {f.location}" for f in findings)
    assert len(findings) == EXPECTED_PAIR_FINDINGS, (
        f"expected {EXPECTED_PAIR_FINDINGS} pair findings across "
        f"{len(corpus) * (len(corpus) - 1) // 2} real pairs, got {len(findings)}:\n{detail}"
    )


def test_detector_is_quiet_not_inert(corpus):
    """The other half — zero findings must not be zero because nothing is measured.

    A detector that always returns "no" also scores zero false positives. What
    separates the two is whether real pairs land near the firing boundary.
    """
    within_1 = within_2 = 0
    for a, b in itertools.combinations(corpus, 2):
        only_a, only_b = _differentia(a, b)
        distance = min(len(only_a), len(only_b))
        within_1 += distance <= 1
        within_2 += distance <= 2

    assert within_1 == EXPECTED_WITHIN_1, (
        f"pairs within one term of firing moved: {within_1} (was {EXPECTED_WITHIN_1}). "
        "The detector's sensitivity changed even though its verdicts did not."
    )
    assert within_2 == EXPECTED_WITHIN_2, (
        f"pairs within two terms moved: {within_2} (was {EXPECTED_WITHIN_2})."
    )
    assert within_1 > 0, "no real pair is near the boundary — detector may be inert"


def test_corpus_is_actually_diverse(corpus):
    """Guard the guard: a corpus of near-duplicates would prove nothing."""
    assert len(corpus) >= MIN_CORPUS_SIZE
    assert len({t.description for t in corpus}) == len(corpus), "duplicate descriptions"
