# lintlang v0.2.0 — Release Readiness

**Status:** Release-ready (private). Awaiting decision on public launch timing.
**Date:** March 1, 2026

---

## What It Is

A **gate**, not a diagnosis. lintlang catches prompt hygiene issues — negative instructions, missing boundaries, vague tool descriptions, format contract violations. It tells you your prompt has problems. It does NOT tell you what the problems mean or how they'll manifest at runtime.

Think of it like a linter for code: it catches style violations and anti-patterns, not logic bugs.

## What It Does Well

- Catches negative instructions, missing context boundaries, vague verbs, instruction overload — all real patterns that correlate with agent failures
- Zero false alarms on what it flags (5/6 finding types are legitimate)
- Fast: 10 files in <2 seconds, no API calls, no model inference
- CI-ready: `lintlang scan --fail-under 90` as a regression gate
- 87 tests passing, supports YAML/JSON/text input

## What It Does NOT Do

These are the honest caveats from testing against 10 real configs from 4 major frameworks (smolagents, LangChain, CrewAI, Dify — 470k combined GitHub stars):

### 1. Cannot find deep bugs
The format contradictions (instruction says dict, examples show bare string), observation drift (static examples don't match runtime output), and semantic inconsistencies that our manual diagnostics find — lintlang cannot detect these. They require understanding what the prompt *means*, not just what patterns it contains.

### 2. Template variables blind 3 of 7 detectors
Real frameworks define tools via `{tools}`, `{{tools}}`, `{tool_names}` template variables. The parser returns `tools=[]` for all of them. This silently disables H1 (tool ambiguity), H2 (tools-related constraint checks), and H3 (schema-intent mismatch). Only H4, H5, H6, H7 fire reliably on real-world configs.

### 3. H2 regex gaps
The most common unbounded loop pattern in real frameworks — `repeat N times` / `can repeat` — is not covered. Current H2 regexes catch textbook anti-patterns (`keep trying until`, `don't stop until`) but miss the dominant real-world pattern. Found in 6/10 test files (60%).

### 4. False positive on format detection
H6 flags "no output format specification" on 7/10 files. But 6 of those DO specify format — the ReAct format (Thought/Action/Observation). The scanner only recognizes JSON/Markdown/XML keywords, not ReAct as a format contract.

### 5. Misses prompt injection patterns in framework code
CrewAI ships "ignore all previous instructions" in its error handling and "your job depends on it" as emotional coercion in every task execution. lintlang does not detect either. These would require a new pattern category (H8 or similar).

## Recommended Fixes for v0.3.0 (by impact)

1. **Parser: detect template variable tool references** — HIGH IMPACT, unblocks 3 detectors
2. **H2: add "repeat N times" regex** — HIGH IMPACT, catches 60% of real-world files
3. **H6: recognize ReAct format** — MEDIUM IMPACT, eliminates main false positive
4. **New H8: coercion/injection detection** — NEW CATEGORY, catches CrewAI patterns

## Positioning

**Open source as:** "Prompt linter" / "Agent config hygiene checker"
**NOT as:** "Diagnostic tool" / "Agent debugging system"

The deep diagnostic work (finding the hard bugs, explaining what they mean, producing audit reports) is the consulting service. lintlang is the top of the funnel — the free thing that gets attention and demonstrates the problem space exists.

## Test Matrix (Real-World Validation)

| Framework | Stars | Score | Findings | Notes |
|-----------|-------|-------|----------|-------|
| smolagents | 25.7k | 84-86 | 5-6/file | Lowest scorer, real bugs confirmed |
| LangChain | 103k | 90-94 | 3-4/file | Decent, some missing boundaries |
| CrewAI | 26k | 94-98 | 2-3/file | Good scores BUT missed worst issues |
| Dify | 96k | 96 | 2/file | Cleanest |
| PR Pilot (ours) | — | 89→97 | 23→7 | Self-audit, 3/4 bugs predicted |
