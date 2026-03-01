# AGENTS.md — lintlang

## What This Is

lintlang is a Python CLI and library that statically lints AI agent tool descriptions,
system prompts, and configs. It catches language-level failures (vague descriptions,
missing constraints, schema mismatches) that cause agents to pick wrong tools,
loop infinitely, or break structured output.

No LLM calls. One dependency (pyyaml). Runs in CI.

## Quick Setup

```bash
pip install lintlang
```

Requires Python 3.10+.

## CLI Usage

```bash
# Scan files or directories
lintlang scan config.yaml
lintlang scan configs/
lintlang scan config.yaml --format json
lintlang scan config.yaml --fail-under 80

# List available patterns
lintlang patterns
```

Exit code 0 = pass. Exit code 1 = score below threshold or scan failure.

## Programmatic Usage

```python
from lintlang import scan_file, scan_directory, ScanResult

result = scan_file("config.yaml")
print(result.score)                    # HERM score (0-100)
print(result.herm.dimension_scores)    # 6 HERM dimensions
print(result.herm.coverage)            # 0.55-1.0
print(result.herm.confidence)          # "high", "medium", "low"
print(result.structural_findings)      # list[Finding] from H1-H7 detectors

results = scan_directory("configs/")   # dict[str, ScanResult]
```

## JSON Output Schema

```json
{
  "file": "config.yaml",
  "score": 92.0,
  "dimensions": {"HERM-1 Interpretive Ambiguity": 100.0, ...},
  "signal_counts": {"ambiguous_qualifiers": 0, ...},
  "coverage": 0.90,
  "confidence": "high",
  "findings": ["No explicit priority ordering"],
  "structural_findings": [
    {
      "pattern_id": "H1",
      "severity": "critical",
      "location": "tool:process_ticket",
      "description": "Tool has no description.",
      "suggestion": "Add a specific description."
    }
  ]
}
```

## Build & Test

```bash
pip install -e ".[dev]"
pytest
python -m build
```

## Architecture

- `src/lintlang/herm.py` — HERM v1.1 scoring engine (6 dimensions, 8 signal categories)
- `src/lintlang/scanner.py` — Orchestrator combining HERM + H1-H7 structural detectors
- `src/lintlang/patterns.py` — 7 structural detectors (H1-H7) with Finding dataclass
- `src/lintlang/parsers.py` — YAML/JSON/text auto-detection
- `src/lintlang/cli.py` — CLI entry point
- `src/lintlang/report.py` — Terminal + Markdown formatters

## Supported File Formats

- YAML (.yaml, .yml) — OpenAI function-calling format, tool definitions
- JSON (.json) — OpenAI/Anthropic tool schemas, message arrays
- Plain text (.txt, .md, .prompt) — System prompts, instruction docs
