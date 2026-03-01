# CLAUDE.md — lintlang

## Project Overview

lintlang is a static linter for AI agent tool descriptions, system prompts, and configs.
It uses HERM v1.1 (Hermeneutical Evaluation and Risk Metrics) as its primary scoring engine,
with 7 structural detectors (H1-H7) providing supplementary findings.

## Tech Stack

- Language: Python 3.10+
- Build: hatchling (PEP 517)
- Runtime dependency: pyyaml
- Test: pytest + pytest-cov
- License: Apache 2.0

## Directory Layout

```
src/lintlang/
  __init__.py          # Public API: scan_file, scan_directory, ScanResult, etc.
  cli.py               # argparse CLI: scan + patterns commands
  herm.py              # HERM v1.1 scoring engine (6 dimensions, 8 signal categories)
  scanner.py           # Orchestrator: HERM scoring + structural detectors
  patterns.py          # H1-H7 structural detectors + Finding/AgentConfig dataclasses
  parsers.py           # YAML/JSON/text parsers with auto-detection
  report.py            # Terminal (ANSI) + Markdown formatters
  py.typed             # PEP 561 type marker
tests/
  conftest.py          # Fixtures: clean_tools_config, bad_tools_config, etc.
  test_cli.py          # CLI integration tests
  test_scanner.py      # Scanner + ScanResult tests
  test_patterns.py     # H1-H7 detector tests (bulk of test suite)
  test_parsers.py      # Parser format detection tests
samples/               # 5 example configs (clean + 4 bad variations)
```

## Development Commands

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=lintlang --cov-report=term-missing

# Scan a file
lintlang scan samples/bad_tool_descriptions.yaml

# Scan a directory
lintlang scan samples/

# JSON output
lintlang scan samples/clean_config.yaml --format json

# List patterns and dimensions
lintlang patterns

# Build package
python -m build
```

## Architecture

### Scoring Flow

1. `cli.py` parses args, calls `parse_file()` per input
2. `parsers.py` auto-detects format (YAML/JSON/text), returns `AgentConfig`
3. `scanner.py:scan_config()` orchestrates:
   - Assembles text from AgentConfig (system prompt + tool descriptions + messages)
   - Calls `herm.py:score_text()` for HERM v1.1 dimensional scoring
   - Runs H1-H7 structural detectors from `patterns.py`
   - Returns `ScanResult` (HERM score + structural findings)
4. `report.py` formats output (terminal/markdown), or CLI emits JSON directly

### HERM v1.1 Scoring

- 6 dimensions (HERM-1 through HERM-6), each 0-100
- 8 signal categories drive dimension scores via regex counting
- Coverage (0.55-1.0) reflects how much of the file is evaluable
- Final score = coverage-weighted dimension mean, capped by coverage tier
- Confidence = high/medium/low (derived from coverage)

### Structural Detectors (H1-H7)

- H1: Tool description ambiguity (empty, short, vague verbs, overlapping)
- H2: Missing constraint scaffolding (no termination, unbounded patterns)
- H3: Schema-intent mismatch (phantom required, generic names, missing descriptions)
- H4: Context boundary erosion (no scope/boundary signals, erosion patterns)
- H5: Implicit instruction failure (negative density, vague qualifiers)
- H6: Template format violation (mixed formats, missing format spec)
- H7: Role confusion (system message placement, consecutive roles, orphan tool results)

## Code Conventions

- Type hints on all public functions (strict, modern syntax: `list[str] | None`)
- Dataclasses for all structured data (Finding, AgentConfig, ToolDef, ScanResult, HermResult)
- `from __future__ import annotations` in all modules
- Word-boundary regex (`\b...\b`) for all text matching to avoid substring false positives
- Findings sorted by severity (critical first)
- All detectors registered in `PATTERNS` dict in patterns.py

## Key Constraints

- Zero LLM calls — all analysis is static (regex + heuristics)
- Single runtime dependency (pyyaml) — keep it minimal
- HERM scores must match standalone HERM v1.1 exactly (validated against 28 comparison files)
- H1-H7 detectors must not modify HERM scores — they produce separate structural findings
- `compute_health_score()` is legacy — kept for backward compat, never used by CLI
