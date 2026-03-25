# lintlang

[![CI](https://github.com/roli-lpci/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/roli-lpci/lintlang/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](https://github.com/roli-lpci/lintlang/blob/main/LICENSE)

**Static linter for AI agent tool descriptions, system prompts, and configs.**

Most AI agent bugs aren't code bugs — they're language bugs. Vague tool descriptions make agents pick the wrong tool. Missing constraints cause infinite loops. Schema mismatches break structured output. lintlang catches these at authoring time, in CI, with zero LLM calls.

## Install

```bash
pip install lintlang
```

Requires Python 3.10+. One dependency (`pyyaml`).

## Quick Start

```bash
# Scan a single file
lintlang scan agent_config.yaml

# Scan a directory
lintlang scan configs/

# JSON output for CI
lintlang scan config.yaml --format json

# Fail CI if score drops below 80
lintlang scan config.yaml --fail-under 80
```

### Example Output

```
  LINTLANG REPORT (HERM v1.1)
  bad_tool_descriptions.yaml
  ──────────────────────────────────────────────────

  Hermeneutical Dimensions
    HERM-1 Interpretive Ambiguity           ██████████  100.0
    HERM-2 User-Intent Misalignment Risk    █████████░   88.0
    HERM-3 Input-Driven Misinterpretation   ████████░░   80.0
    HERM-4 Instruction Conflict/Polysemy    █████████░   92.0
    HERM-5 Pragmatic Drift Risk             ██████████  100.0
    HERM-6 Adversarial Reframing            ██████████  100.0

  Coverage: 90%  |  Confidence: high

  Structural Issues  (1 critical, 2 high, 6 medium, 3 low)

  H1: Tool Description Ambiguity (5 findings)

    !! [CRITICAL] tool:process_ticket
      Tool 'process_ticket' has no description.
      Fix: Add a specific description explaining WHEN to use this tool.

    ! [HIGH] tool:get_user_info
      Tool 'get_user_info' has a very short description (13 chars)
      Fix: Expand to include purpose, when to use, expected input/output.

  ──────────────────────────────────────────────────
  HERM Score: 92.0/100
```

## How Scoring Works (HERM v1.1)

lintlang uses the **HERM v1.1** (Hermeneutical Evaluation and Risk Metrics) scoring engine. It evaluates 6 dimensions of linguistic quality:

| Dimension | What It Measures |
|-----------|-----------------|
| **HERM-1** Interpretive Ambiguity | How many vague qualifiers like "as needed", "when appropriate" |
| **HERM-2** User-Intent Misalignment Risk | Ambiguity density + whether priority ordering exists |
| **HERM-3** Input-Driven Misinterpretation | Input surface signals + task boundary language |
| **HERM-4** Instruction Conflict/Polysemy | Excessive negatives + missing priority signals |
| **HERM-5** Pragmatic Drift Risk | Ambiguity + negative directive density |
| **HERM-6** Adversarial Reframing | Hijack phrases, coercive pressure, unbounded repeats |

The final score (0-100) is the coverage-weighted mean of all 6 dimensions. Files that don't look like prompts or configs receive lower coverage (and thus a score cap), preventing false confidence.

**Coverage** (55-100%) reflects how much of the file lintlang could meaningfully evaluate. **Confidence** (high/medium/low) summarizes coverage for quick triage.

The `--fail-under` flag checks the HERM score (lowest across all files). Exit code 0 = pass, 1 = fail.

## What's New in v0.2.0

**H5 (Implicit Instruction Failure) — Context-Aware Negatives**

H5 now distinguishes between safety/policy constraints and style issues, reducing false positives by 96%.

Old behavior (v0.1.x):
- Flagged *any* 4+ negative instructions ("don't", "never", "avoid") as problematic
- 90% false positive rate on real agent configs — security prompts were flagged as "bad style"

New behavior (v0.2.0):
- Exempts negatives near 60+ safety/policy/accuracy/legal keywords
- Context window: 100 chars before/after the negative (covers full sentences)
- Only flags true style negatives that lack security/policy/accuracy context
- 96% accuracy on 26 real-world agent configs

**Examples:**

✅ PASS (exempted — legitimate constraints):
- "Never expose API keys or credentials" → safety
- "Do not execute code without user approval" → authorization
- "Never extrapolate beyond the data range" → accuracy  
- "Don't make promises without manager approval" → business policy

❌ FLAG (caught — style negatives):
- "Don't apologize for simple mistakes" → style, rewrite as positive
- "Never be overly verbose" → style, rewrite as positive

## Structural Detectors (H1-H7)

On top of HERM scoring, lintlang runs 7 structural detectors that catch issues HERM can't — like empty tool descriptions, duplicate names, phantom schema fields:

| Pattern | Name | What Users Report | Severity |
|---------|------|-------------------|----------|
| **H1** | Tool Description Ambiguity | "Agent picks wrong tool" | CRITICAL-MEDIUM |
| **H2** | Missing Constraint Scaffolding | "Agent loops infinitely" | CRITICAL-HIGH |
| **H3** | Schema-Intent Mismatch | "Structured output broken" | CRITICAL-LOW |
| **H4** | Context Boundary Erosion | "Agent leaks state across tasks" | HIGH-MEDIUM |
| **H5** | Implicit Instruction Failure | "Model doesn't follow instructions" | MEDIUM-LOW |
| **H6** | Template Format Contract Violation | "Agent broke after prompt change" | MEDIUM-INFO |
| **H7** | Role Confusion | "Chat history is messed up" | CRITICAL-MEDIUM |

## Usage

```bash
# Scan files (YAML, JSON, or plain text)
lintlang scan config.yaml prompt.txt tools.json

# Scan a directory recursively
lintlang scan configs/

# Check only specific patterns
lintlang scan config.yaml --patterns H1 H3

# Filter by minimum severity
lintlang scan config.yaml --min-severity high

# Markdown report
lintlang scan config.yaml --format markdown

# Hide fix suggestions
lintlang scan config.yaml --no-suggestions

# List all patterns and dimensions
lintlang patterns
```

### Programmatic API

```python
from lintlang import scan_file, scan_directory

# Scan a single file
result = scan_file("config.yaml")
print(f"HERM Score: {result.score}/100")
print(f"Coverage: {result.herm.coverage}, Confidence: {result.herm.confidence}")

for dim, score in result.herm.dimension_scores.items():
    print(f"  {dim}: {score}")

for finding in result.structural_findings:
    print(f"  [{finding.severity.value}] {finding.description}")

# Scan a directory
results = scan_directory("configs/")
for path, result in results.items():
    print(f"{path}: {result.score}")
```

## Supported Formats

lintlang auto-detects file format:

- **YAML** (`.yaml`, `.yml`) — OpenAI function-calling format, tool definitions
- **JSON** (`.json`) — OpenAI and Anthropic tool schemas, message arrays
- **Plain text** (`.txt`, `.md`, `.prompt`) — System prompts, instruction docs

Unknown extensions: tried as JSON, then YAML, then plain text.

## CI Integration

### GitHub Actions

```yaml
- name: Lint agent configs
  run: |
    pip install lintlang
    lintlang scan configs/ --fail-under 80
```

### Pre-commit

```bash
lintlang scan src/agent/config.yaml --fail-under 80 || exit 1
```

Exit code 0 = all files pass. Exit code 1 = score below threshold or scan failure.

## How Is lintlang Different?

| Tool | What It Does | How lintlang Differs |
|------|-------------|---------------------|
| **promptfoo** | Tests prompts via eval suites at runtime | lintlang is static analysis — catches issues at authoring time, no LLM calls |
| **guardrails-ai** | Validates LLM outputs at runtime | lintlang catches the root cause (bad instructions), not symptoms (bad outputs) |
| **NeMo Guardrails** | Runtime dialogue rails (Colang DSL) | lintlang operates on config files, not live conversations |
| **eslint / ruff** | Lints source code syntax | lintlang lints natural language in agent configs |
| **semgrep** | Code pattern matching (SAST) | lintlang matches linguistic patterns in prose |

lintlang is the only tool that treats tool descriptions, system prompts, and agent configs as **lintable artifacts** — applying static analysis to natural language the same way eslint applies rules to JavaScript.

## Development

```bash
git clone https://github.com/roli-lpci/lintlang.git
cd lintlang
pip install -e ".[dev]"
pytest
```

## License

[Apache 2.0](LICENSE)
