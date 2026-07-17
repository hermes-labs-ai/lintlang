# INTENT — lintlang

> One-page invariants doc, in the Hermes Labs convention. Read before changing scope.

## What lintlang is

A static linter for AI agent tool descriptions, system prompts, and config files. Zero-LLM, deterministic, runs in CI. Combines HERM v1.1 dimensional scoring (6 dimensions, 8 signal categories) with 7 structural detectors (H1–H7) that flag bounded language patterns before runtime review.

## Accepts

- File or directory of AI agent configs in JSON, YAML, plain text, or `.prompt`.
- Python source files (`.py`) via AST-based prompt extractor — runs H1-H7 + P1-P2 on embedded prompts and thresholds.
- Pattern filtering: `--patterns H1 H3` runs only listed detectors.
- Output formats: terminal (ANSI), Markdown, JSON for CI.
- Severity gating: `--fail-on fail|review` controls non-zero exit.

## Refuses

- Any operation that requires an LLM call. lintlang is static; if you want model-grading, use a different tool.
- Auto-fix / rewriting. lintlang reports; it does not modify input files.
- Network access. lintlang makes no model calls, telemetry calls, or remote rule fetches.
- Languages outside its parsed format set. Currently JSON / YAML / plain text / `.prompt` / `.py`. Adding a format is a code change with regression coverage.

## Non-goals

- Runtime agent behavior evaluation (use a runtime harness).
- Behavioral safety certification (a clean scan does not establish safety or correctness).
- Semantic correctness of *what* the tool does (lintlang catches *vague*, not *wrong*).
- Replacing human review for high-stakes prompt design.

## Invariants

- **Zero LLM calls.** Any change that introduces a model dependency violates the contract.
- **Deterministic.** Same input → same output, every run. No sampling, no timestamp-based behavior, no seed dependence.
- **Single runtime dependency.** `pyyaml` only. Adding a runtime dep requires a deliberate v0.x minor bump and CHANGELOG entry naming the reason.
- **Evidence-bound parity claims.** HERM scoring remains isolated from structural findings. Do not claim parity with another implementation unless the comparison corpus and an executable gate are checked into this repository.
- **Structural detectors don't modify HERM scores.** H1–H7 produce separate `Finding` records; HERM dimensional scores are independent.
- **Regression-bound rule changes.** Regex or heuristic changes require positive fixtures and hard negatives for their intended boundary.

## Verification contract

- `pytest -q` and `ruff check src/ tests/` must pass from a clean checkout.
- `bash evals/sample-detection-rate.sh` must match the expected outcomes for the bundled fixtures: four deliberately broken samples flagged and one designated clean sample passed.
- The bundled sample check is a regression fixture only. It is not an accuracy estimate, an external validation corpus, or evidence of HERM reference parity.
