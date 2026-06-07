# lintlang v0.3.0 — Launch Claim

**What it is:** Static linter for AI agent configs and prompts. 7 structural detectors
(H1-H7), 6 HERM v1.1 scoring dimensions. Scans YAML, JSON, prompt files, and Python
source (AST-based prompt extractor). Zero LLM calls per default scan. ~2ms per file.

**The invariant it holds:** Same input → same output, every run. No sampling, no network,
no model calls by default. CI-safe.

**The problem it solves:** AI agent configs fail for language reasons before they fail
for code reasons — vague tool descriptions, missing stop conditions, schema fields that
say nothing useful. These failures are invisible to JSON validators and YAML linters.
lintlang catches them statically.

**What changed in v0.3.0 (the P3 fix):**

The v0.2.2 → v0.3.0 change is a single correctness fix: P3 (scaffold quality via
nomic-embed-text embeddings) was running automatically on every `.py` scan, making a
localhost Ollama network call. That violated the zero-LLM, zero-network invariant stated
in INTENT.md. v0.3.0 gates P3 behind `--enable-embeddings` (CLI) and
`enable_embeddings=True` (API). Default behavior is unchanged except P3 no longer fires.

**Evidence:**
- 155 tests, all passing (pytest output: `155 passed in 0.58s`)
- ruff clean: `All checks passed!`
- HERM parity: 28-file comparison set unchanged
- framing lint: CHANGELOG entry clean (exit 0)

**What v0.3.0 does NOT claim:**
- P3 accuracy numbers are from `free-experiments-20260418` (100% separation on 5-exemplar
  centroid). Not a held-out eval. Don't market P3 as production-validated until more data.
