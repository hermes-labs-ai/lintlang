# INTENT — lintlang

> One-page invariants doc, in the Hermes Labs convention. Read before changing scope.

## What lintlang is

A static linter for AI agent tool descriptions, system prompts, and config files. Zero-LLM, deterministic, runs in CI. Combines HERM v1.1 dimensional scoring (6 dimensions, 8 signal categories) with 7 structural detectors (H1–H7) that flag bounded language patterns before runtime review.

## Accepts

- File or directory of AI agent configs in JSON, YAML, plain text, or `.prompt`.
- Python source files (`.py`) via AST-based prompt extractor — runs H1-H7 + P1-P2 on embedded prompts and thresholds.
- One present UTF-8 instruction plus an explicit typed context contract through the separate `preflight` API/CLI.
- Pattern filtering: `--patterns H1 H3` runs only listed detectors.
- Output formats: terminal (ANSI), Markdown, JSON for CI.
- Severity gating: `--fail-on fail|review` controls non-zero exit.
- Preflight states: `ALLOW | NOTICE | HOLD | UNAVAILABLE | ERROR`; unavailable coverage is never clean.

## Refuses

- Any operation that requires an LLM call. lintlang is static; if you want model-grading, use a different tool.
- Silent rewriting, provider sending, or history mining. A preflight correction is previewed, explicitly selected, source-hash-bound, and applied in memory only.
- Network access. lintlang makes no model calls, telemetry calls, or remote rule fetches.
- Languages outside its parsed format set. Currently JSON / YAML / plain text / `.prompt` / `.py`. Adding a format is a code change with regression coverage.

## Non-goals

- Runtime agent behavior evaluation (use a runtime harness).
- Behavioral safety certification (a clean scan does not establish safety or correctness).
- Semantic correctness of *what* the tool does (lintlang catches *vague*, not *wrong*).
- Replacing human review for high-stakes prompt design.
- Truth verification, provider compatibility, or claims that a detected input risk caused a published model-output mode.
- Personalized history retrieval; another system may supply an explicit binding, but preflight does not infer it.

## Invariants

- **Zero LLM calls.** Any change that introduces a model dependency violates the contract.
- **Deterministic.** Same input → same output, every run. No sampling, no timestamp-based behavior, no seed dependence.
- **Single runtime dependency.** `pyyaml` only. Adding a runtime dep requires a deliberate v0.x minor bump and CHANGELOG entry naming the reason.
- **Evidence-bound parity claims.** HERM scoring remains isolated from structural findings. Do not claim parity with another implementation unless the comparison corpus and an executable gate are checked into this repository.
- **Structural detectors don't modify HERM scores.** H1–H7 produce separate `Finding` records; HERM dimensional scores are independent.
- **Regression-bound rule changes.** Regex or heuristic changes require positive fixtures and hard negatives for their intended boundary.
- **Privacy-safe defaults.** Preflight serialization omits raw prompt, context, replacement, and diff text unless snippets are explicitly authorized.
- **Exact enforcement boundary.** Heuristic preflight findings are notice-only; only typed missing requirements and mechanical conflicts may hold.

## Verification contract

- `pytest -q` and `ruff check src/ tests/` must pass from a clean checkout.
- `bash evals/sample-detection-rate.sh` must match the expected outcomes for the bundled fixtures: four deliberately broken samples flagged and one designated clean sample passed.
- The bundled sample check is a regression fixture only. It is not an accuracy estimate, an external validation corpus, or evidence of HERM reference parity.
