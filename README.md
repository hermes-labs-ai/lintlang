# lintlang

[![CI](https://github.com/roli-lpci/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/roli-lpci/lintlang/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![PyPI downloads](https://img.shields.io/pypi/dm/lintlang)](https://pypi.org/project/lintlang/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](https://github.com/roli-lpci/lintlang/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/roli-lpci/lintlang)](https://github.com/roli-lpci/lintlang)

**Static linter for AI agent tool descriptions, system prompts, and configs.**

Most AI agent bugs aren't code bugs — they're language bugs. Vague tool descriptions make agents pick the wrong tool. Missing constraints cause infinite loops. Schema mismatches break structured output. lintlang catches these at authoring time, in CI, with zero LLM calls.

## Install

```bash
pip install lintlang
```

Requires Python 3.10+. One dependency (`pyyaml`). No API keys, no network access, no LLM calls.

## Quick Start

```bash
# Scan a single file
lintlang scan agent_config.yaml

# Scan a directory (finds .yaml, .json, .txt, .md, .prompt)
lintlang scan configs/

# JSON output for CI
lintlang scan config.yaml --format json

# Fail CI on CRITICAL/HIGH findings
lintlang scan config.yaml --fail-on fail

# Fail CI on any MEDIUM+ findings
lintlang scan config.yaml --fail-on review
```

### Example Output

```
  LINTLANG v0.2.0
  bad_tool_descriptions.yaml
  ──────────────────────────────────────────────────

  ❌ FAIL — 1 CRITICAL, 2 HIGH, 6 MEDIUM, 3 LOW

  H1: Tool Description Ambiguity

    !! [CRITICAL] tool:process_ticket
      Tool 'process_ticket' has no description.
      → Add a specific description explaining WHEN to use this tool.

    ! [HIGH] tool:get_user_info
      Tool 'get_user_info' has a very short description (13 chars)
      → Expand to include purpose, when to use, expected input/output.

    ~ [MEDIUM] tool:handle_request
      Tool 'handle_request' starts with vague verb 'handle'.
      → Replace with a specific action verb.

  H2: Missing Constraint Scaffolding

    ! [HIGH] system_prompt
      System prompt defines tools but has no termination conditions.
      → Add: 'Maximum 5 tool calls per task. Stop and report after 2 failures.'

  ──────────────────────────────────────────────────
  lintlang v0.2.0 | H1-H7 structural analysis | Zero LLM calls
```

## How It Works

lintlang gives you a **verdict**, not a score:

| Verdict | Meaning | When |
|---------|---------|------|
| ✅ **PASS** | Ship it | Only LOW/INFO findings or none |
| ⚠️ **REVIEW** | Has blind spots | MEDIUM findings present |
| ❌ **FAIL** | Will break in production | CRITICAL or HIGH findings |

Each finding includes the **pattern** (H1-H7), **severity**, **location**, and a **concrete fix suggestion**. No vague "improve your prompt" — specific rewrites you can apply immediately.

## Structural Detectors (H1-H7)

| Pattern | Name | What Users Report | Severity |
|---------|------|-------------------|----------|
| **H1** | Tool Description Ambiguity | "Agent picks wrong tool" | CRITICAL-MEDIUM |
| **H2** | Missing Constraint Scaffolding | "Agent loops infinitely" | CRITICAL-HIGH |
| **H3** | Schema-Intent Mismatch | "Structured output broken" | CRITICAL-LOW |
| **H4** | Context Boundary Erosion | "Agent leaks state across tasks" | HIGH-MEDIUM |
| **H5** | Implicit Instruction Failure | "Model doesn't follow instructions" | MEDIUM-LOW |
| **H6** | Template Format Contract Violation | "Agent broke after prompt change" | MEDIUM-INFO |
| **H7** | Role Confusion | "Chat history is messed up" | CRITICAL-MEDIUM |

### H5: Context-Aware Negatives

H5 distinguishes between **safety constraints** and **style negatives**. Security rules like "Never expose API keys" are correctly exempted. Style issues like "Don't be verbose" are flagged with positive rewrites.

Validated on 26 real-world configs (OpenHands, RAG agents, HIPAA compliance, financial advisors, content moderation, DevOps safety).

## CI Integration

### GitHub Actions

```yaml
- name: Lint agent configs
  run: |
    pip install lintlang
    lintlang scan configs/ --fail-on fail
```

### Verdict-Based Gating

| Flag | Exits 1 when | Use case |
|------|-------------|----------|
| `--fail-on fail` | Any CRITICAL/HIGH finding | Blocking deploy gate |
| `--fail-on review` | Any MEDIUM+ finding | Strict quality gate |
| `--fail-under 80` | HERM score < threshold | Legacy score-based gate |

### Filter by Severity

```bash
# Only show CRITICAL and HIGH
lintlang scan config.yaml --min-severity high

# Only check specific patterns
lintlang scan config.yaml --patterns H1 H3
```

## Programmatic API

```python
from lintlang import scan_file, compute_verdict

result = scan_file("config.yaml")
verdict = compute_verdict(result.structural_findings)
print(f"Verdict: {verdict}")  # PASS, REVIEW, or FAIL

for finding in result.structural_findings:
    print(f"  [{finding.severity.value}] {finding.description}")
    print(f"  → {finding.suggestion}")
```

```python
# Scan a directory
from lintlang import scan_directory, compute_verdict

results = scan_directory("configs/")
for path, result in results.items():
    verdict = compute_verdict(result.structural_findings)
    print(f"{path}: {verdict}")
```

## Supported Formats

lintlang auto-detects file format:

- **YAML** (`.yaml`, `.yml`) — OpenAI function-calling format, tool definitions
- **JSON** (`.json`) — OpenAI and Anthropic tool schemas, message arrays
- **Plain text** (`.txt`, `.md`, `.prompt`) — System prompts, instruction docs

Unknown extensions are tried as JSON → YAML → plain text.

## How Is lintlang Different?

| Tool | What It Does | How lintlang Differs |
|------|-------------|---------------------|
| **promptfoo** | Tests prompts via eval suites at runtime | lintlang is static — no LLM calls, catches issues at authoring time |
| **guardrails-ai** | Validates LLM outputs at runtime | lintlang catches root causes (bad instructions), not symptoms |
| **NeMo Guardrails** | Runtime dialogue rails | lintlang operates on config files, not live conversations |
| **eslint / ruff** | Lints source code | lintlang lints natural language in agent configs |

lintlang treats tool descriptions, system prompts, and agent configs as **lintable artifacts** — static analysis for prose, like eslint for JavaScript.

## Development

```bash
git clone https://github.com/roli-lpci/lintlang.git
cd lintlang
pip install -e ".[dev]"
pytest
```

## Hermes Labs Ecosystem

lintlang is part of the [Hermes Labs](https://hermes-labs.ai) open-source suite:

- [**little-canary**](https://github.com/roli-lpci/little-canary) — Prompt injection detection
- [**zer0dex**](https://github.com/roli-lpci/zer0dex) — Dual-layer memory for AI agents
- [**forgetted**](https://github.com/roli-lpci/forgetted) — Selective memory governance
- [**zer0lint**](https://github.com/roli-lpci/zer0lint) — mem0 extraction diagnostics
- [**suy-sideguy**](https://github.com/roli-lpci/suy-sideguy) — Autonomous agent watchdog
- [**quickthink**](https://github.com/roli-lpci/quickthink) — Planning scaffolding for local LLMs

---

If lintlang saves you time, please [star the repo](https://github.com/roli-lpci/lintlang) — it helps others find it.

## License

[Apache 2.0](LICENSE)
