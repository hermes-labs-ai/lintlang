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

**Consequence worth stating plainly: these three tests do not run in CI.** No
GitHub Actions runner has that marketplace installed, so the suite gates 266
there and 269 on a maintainer machine. The one test measuring this detector
against text nobody wrote for the project is therefore a local pre-merge check,
not an automated gate. Quote 266 when quoting a CI number. Vendoring a small
licence-safe corpus would close this and is the right fix; it is not done.

Baseline measured 2026-08-05 by this module's own loader: 76 descriptions from
independent plugin authors, 2850 pairs.

    pair findings (H1.5 + H1.6)   5
    pairs within 1 term of firing 7
    pairs within 2 terms          14

Four of the five findings are an artifact of flattening: the Discord, iMessage
and Telegram plugins each ship a skill named `access` and `configure` with
descriptions identical but for the platform name. Within one plugin those never
meet; only this corpus puts them side by side. They are correct H1.5 reports of
near-duplicate text and wrong as a claim about any real manifest — one more
reason to read the pair count as 181 realistic pairs, not 2850.

The fifth is H1.5 on `agent-sdk-verifier-py` vs `-ts`, whose
descriptions are ~90% identical and differ only by the language name. H1.6
correctly stays quiet — the language IS the distinction — while H1.5 reports
that the surrounding text is near-duplicate. That is defensible, and it is
v0.3.2 behaviour: an earlier baseline of 0 was measured while a bug in the
H1.5 name guard was suppressing it.

Revised 2026-08-05 from 8/18 after making normalization lexicon-only, so that
number is no longer collapsed: `get_order` and `get_orders` are different
operations, and treating them as one spelling produced a "remove one" verdict
on `get_user`/`get_users`. Fewer terms now normalize together, so pairs sit
further from the boundary.

Previously revised from 10/23 after removing a length floor in the
informative-terms filter. That floor discarded tokens of two characters or
fewer, which made `v1`/`v2`, `get_po`/`get_so` and `top_10`/`top_100` read as
indistinguishable — false positives carrying a "remove one" recommendation.
Dropping it makes more tokens count as distinguishing, so pairs moved further
from the firing boundary. Verdicts did not change; sensitivity did. This
tripwire caught that, which is what it is for.

READ THE PAIR COUNT HONESTLY. Only 181 of those 2850 pairs are between tools
belonging to the *same* plugin, and only those can actually collide — plugin
skills are namespaced (`/plugin-a:scan` vs `/plugin-b:scan`), so two entries
from different authors never compete at decision time. Quoting 2850 overstates
the test by roughly 15x. The defensible statement is "no false positives across
181 realistic pairs", which is a modest result, not a strong one.

Two further limits worth stating before anyone cites this:

  - These are skill/agent descriptions, which are long and written to be
    matched. Real MCP tool descriptions run far shorter (median ~31 chars in a
    local sample) and are a systematically harder population that this corpus
    does not represent.
  - Hand-inspecting the 4 within-plugin near-misses, all 4 are correctly quiet:
    `agent-sdk-verifier-ts` vs `-py` differ only by language, which is a real
    distinction; `scan-researcher` vs `scan-inventory` are genuinely different
    roles. That is evidence the threshold sits in a sane place, on an easy
    population.

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

EXPECTED_PAIR_FINDINGS = 5
EXPECTED_WITHIN_1 = 7
EXPECTED_WITHIN_2 = 14
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
