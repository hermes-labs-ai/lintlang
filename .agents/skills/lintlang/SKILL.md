---
name: lintlang
description: Use when writing or reviewing AI agent configs, system prompts, or tool definitions (JSON/YAML/Python) and you need to catch ambiguous tool descriptions, missing stop conditions, schema/description mismatches, or embedded prompts before they reach runtime. Deterministic static analysis, no LLM or network calls.
license: Apache-2.0
compatibility: Requires Python 3.10+; installs via pip or runs standalone via `uvx lintlang`. Scans need no network access.
---

# LintLang

LintLang statically analyzes the natural-language instructions that control AI
agents — system prompts, tool descriptions, and configs — catching ambiguous
tools, missing limits, and conflicting directives before they reach an agent
at runtime. It is zero-LLM: deterministic pattern and structural checks only,
no model calls, no telemetry, no network access.

## Use it for

- Linting tool descriptions before agents start choosing between them
  (detects pairs like `get_user_info` / `fetch_user_data` with no
  distinguishing term — check `H1.6`)
- Checking prompts and configs for missing stop conditions, unbounded
  retries, and schema/description mismatches
- Running a zero-LLM CI gate over YAML, JSON, prompt text, and Python source
- Scanning `.py` files for embedded prompts and uncalibrated thresholds
  (detectors `P1`/`P2`)
- Preflighting one present instruction plus explicit typed context before a
  host sends it to a model

## Do not use it for

- Runtime evaluation of a live agent
- Dynamic agent testing or behavioral benchmarking
- Proving an agent is safe in production
- Retrieving preferences from history, deciding truth, or rewriting/sending
  prompts on the agent's behalf

## Quickstart

```bash
python -m pip install lintlang
lintlang scan AGENTS.md
```

Or without installing, via [uv](https://docs.astral.sh/uv/):

```bash
uvx lintlang scan AGENTS.md
```

Scan a fixture with a known finding:

```bash
uvx lintlang scan samples/bad_tool_descriptions.yaml
```

## Output shape

- Repository scan outcomes: `ERROR`, `PASS`, `REVIEW`, or `FAIL`
- Structural findings by pattern `H1` through `H7`, plus Python pipeline
  findings `P1` and `P2`
- JSON output for CI via `--format json`
- Preflight states: `ALLOW`, `NOTICE`, `HOLD`, `UNAVAILABLE`, or `ERROR`
- Preflight evidence uses exact code-point spans and stable `PF001`-`PF005`
  IDs

## Common gotchas

- LintLang judges structure, not runtime model behavior — a config can pass
  every LintLang check and still fail at inference time.
- Configs can be syntactically valid YAML/JSON while still under-specified
  for their intended use; LintLang flags this as `REVIEW`, not `FAIL`.
- Preflight heuristic findings are notice-only; only exact contract/conflict
  rules may hold (`HOLD`).

## More

Full docs, CLI reference, and CI integration:
https://github.com/hermes-labs-ai/lintlang
