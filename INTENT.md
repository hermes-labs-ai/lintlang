# INTENT — lintlang

> One-page invariants doc, in the Hermes Labs convention. Read before changing scope.

## What lintlang is

A static linter for AI agent tool descriptions, system prompts, and config files. Zero-LLM, deterministic, runs in CI. Combines HERM v1.1 dimensional scoring (6 dimensions, 8 signal categories) with 7 structural detectors (H1–H7) that catch language-level failures before runtime.

## Accepts

- File or directory of AI agent configs in JSON, YAML, plain text, or `.prompt`.
- Pattern filtering: `--patterns H1 H3` runs only listed detectors.
- Output formats: terminal (ANSI), Markdown, JSON for CI.
- Severity gating: `--fail-on fail|review|any` controls non-zero exit.
- Verbosity flags: `--verbose`, `--quiet`.

## Refuses

- Any operation that requires an LLM call. lintlang is static; if you want model-grading, use a different tool.
- Auto-fix / rewriting. lintlang reports; it does not modify input files.
- Network access. No telemetry, no model calls, no remote rule fetch.
- Languages outside its parsed format set. Currently JSON / YAML / plain text / `.prompt`. Adding a format is a code change with regression coverage.

## Non-goals

- Runtime agent behavior evaluation (use a runtime harness).
- Behavioral safety certification (a clean scan is necessary but not sufficient).
- Semantic correctness of *what* the tool does (lintlang catches *vague*, not *wrong*).
- Replacing human review for high-stakes prompt design.

## Invariants

- **Zero LLM calls.** Any change that introduces a model dependency violates the contract.
- **Deterministic.** Same input → same output, every run. No sampling, no timestamp-based behavior, no seed dependence.
- **Single runtime dependency.** `pyyaml` only. Adding a runtime dep requires a deliberate v0.x minor bump and CHANGELOG entry naming the reason.
- **HERM v1.1 parity.** Scores must match the standalone HERM v1.1 reference implementation exactly. Validated against 28 comparison files; CI gate checks this.
- **Structural detectors don't modify HERM scores.** H1–H7 produce separate `Finding` records; HERM dimensional scores are independent.
- **Word-boundary regex everywhere.** `\b...\b` to avoid substring false positives.

## Verification contract

- `pytest`: 235+ tests collected, all passing.
- `lintlang scan samples/`: detects 4-of-5 known-bad sample files; 1 known-clean file PASSES.
- HERM v1.1 reference parity: 28-file comparison set produces identical scores to the standalone HERM v1.1 implementation.
