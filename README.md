# lintlang

**lintlang is a deterministic static linter for AI agent configs, tool descriptions, and system prompts. It combines 7 structural detectors (H1–H7) with 6 HERM v1.1 scoring dimensions and runs without model or network calls.**

> Release status: this checkout is the unreleased `0.3.1` candidate. The latest public PyPI release remains `0.2.2`.

Run `bash evals/sample-detection-rate.sh` to check the bundled regression fixtures: four deliberately broken samples must be flagged and one designated clean sample must pass. This is a repository regression check, not an accuracy estimate or validation corpus.

AI agent configs can be syntactically valid while their language remains vague, unbounded, or structurally inconsistent.

`lintlang` flags a bounded set of those static patterns before runtime review — without calling a model.

- "My agent picks the wrong tool because the tool descriptions all sound the same."
- "We only catch prompt and config drift after the agent starts looping."
- "I want a prompt linter or agent-config linter that runs in CI with no model calls."
- "Our YAML is valid, but the instructions inside it are still bad."

```bash
pip install lintlang
```

```bash
lintlang scan samples/bad_tool_descriptions.yaml
```

```text
LINTLANG v0.3.1
samples/bad_tool_descriptions.yaml

FAIL — 1 CRITICAL, 2 HIGH, 6 MEDIUM, 3 LOW
H1: Tool Description Ambiguity
  [CRITICAL] tool:process_ticket
  Tool 'process_ticket' has no description.
```

## How it differs from LLM-based config review

Model-based agent-config review depends on a model runtime and may add API cost, latency, or output variability. lintlang skips the model and applies local static rules.

| | LLM-based config review | lintlang |
|---|---|---|
| Model or API cost per scan | Provider-dependent | **None** |
| Model or API latency | Provider-dependent | **None** |
| Same input → same output | Model/configuration-dependent | **Yes (regex + AST)** |
| Runs without a model or API key | No | **Yes** |
| Catches *vague* tool descriptions | Model-dependent | **Static H1 heuristic** |
| Detects *missing* termination conditions | Model-dependent | **Static H2 heuristic** |

Detection rules are static regex + structural heuristics. File discovery and findings are deterministically ordered.

## When to use it

Use `lintlang` when you author or review AI agent tool descriptions, system prompts, or config files and want a static prompt/config quality gate in CI before runtime testing.

## When NOT to use it

- **Semantic correctness** — lintlang is structural. It catches *vague* tool descriptions, not *wrong* ones. ("delete_user" with empty description fails; "delete_user" pointing at the wrong table is invisible to lintlang.)
- **Open-ended creative writing** — H1–H7 are calibrated for agent configs and system prompts, not prose.
- **Auto-fix** — lintlang reports findings; it doesn't rewrite. Pair with a human or LLM for the fix step.
- **Behavioral safety proofs** — a clean lintlang scan is not evidence that an agent is safe or correct. Use runtime evaluation and domain review for behavioral claims.
- **Input boundaries** — JSON, YAML, plain text, `.prompt`, and Markdown are parsed as language-bearing inputs. Python files use AST extraction only for embedded prompts and agent-pipeline thresholds; lintlang does not lint general Python syntax, style, types, or program correctness. Arbitrary nested templates may not parse.

[![CI](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![PyPI downloads](https://img.shields.io/pypi/dm/lintlang)](https://pypi.org/project/lintlang/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](https://github.com/hermes-labs-ai/lintlang/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/hermes-labs-ai/lintlang)](https://github.com/hermes-labs-ai/lintlang)

**Static linter for AI agent tool descriptions, system prompts, and configs.**

Valid syntax does not guarantee clear instructions. Ambiguous tool descriptions, missing bounds, and schema-language mismatches can create review obligations that code linters do not express. lintlang flags its shipped static patterns at authoring time and in CI with zero LLM calls.

## Install

```bash
pip install lintlang
```

Requires Python 3.10+. One dependency (`pyyaml`). No API keys, network calls, or LLM calls.

## Quick Start

```bash
# Scan a single file
lintlang scan agent_config.yaml

# Scan a directory (finds .yaml, .json, .txt, .md, .prompt, and .py)
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
  LINTLANG v0.3.1
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
  lintlang v0.3.1 | H1-H7 structural analysis | Zero LLM calls
```

## How It Works

lintlang gives you a **verdict**, not a score:

| Verdict | Meaning | When |
|---------|---------|------|
| ✅ **PASS** | No blocking structural finding detected | Only LOW/INFO findings or none |
| ⚠️ **REVIEW** | Review structural warnings | MEDIUM findings present |
| ❌ **FAIL** | Blocking structural finding detected | CRITICAL or HIGH findings |

Each finding includes the **pattern** (H1-H7), **severity**, **location**, and a concrete suggestion. Suggestions are review aids, not guaranteed meaning-preserving fixes.

## Why These 7 Detectors?

The shipped rule set groups its structural checks into seven categories for
agent configuration and prompt surfaces. Each detector maps to a condition that
general syntax and schema linters do not evaluate.

Tools such as yamllint, semgrep, and ruff cover syntax or source-code patterns.
lintlang focuses on a different layer: whether descriptions are ambiguous or
whether an instruction surface omits explicit termination conditions. Those
findings are heuristic structural warnings, not predictions of runtime behavior.
Current checked-in evidence is limited to unit tests and the small regression
fixture described below; detector accuracy on external projects is unmeasured.

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

The checked-in [`samples/`](samples/) directory contains a small regression set for detector behavior. It does not establish performance on external projects or production workloads.

### Why not just use GPT-4?

No model/API cost, model latency, or prompt transmission is required. lintlang runs offline and applies deterministic structural checks; it complements rather than replaces model-based or human review.

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
| `--fail-under 80` | Quality score < threshold | Legacy score-based gate |

Input integrity is a separate fatal channel: every explicitly requested input,
and every supported file discovered in a requested directory, must be readable
and parseable. A missing, unreadable, or malformed input exits `1` regardless
of `--fail-on`. JSON output keeps the affected path in the result list with
`"verdict": "ERROR"` and a non-null `"input_error"`; it is never labeled
`PASS` or silently omitted because another input scanned successfully.

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
if result.input_error:
    raise ValueError(f"lintlang could not scan the input: {result.input_error}")
verdict = compute_verdict(result)  # ERROR, PASS, REVIEW, or FAIL
print(f"Verdict: {verdict}")  # ERROR, PASS, REVIEW, or FAIL

for finding in result.structural_findings:
    print(f"  [{finding.severity.value}] {finding.description}")
    print(f"  → {finding.suggestion}")
```

```python
# Scan a directory
from lintlang import scan_directory, compute_verdict

results = scan_directory("configs/")
for path, result in results.items():
    if result.input_error:
        print(f"{path}: ERROR — {result.input_error}")
        continue
    verdict = compute_verdict(result)
    print(f"{path}: {verdict}")
```

## Supported Formats

lintlang auto-detects file format:

- **YAML** (`.yaml`, `.yml`) — OpenAI function-calling format, tool definitions
- **JSON** (`.json`) — OpenAI and Anthropic tool schemas, message arrays
- **Plain text** (`.txt`, `.md`, `.prompt`) — System prompts, instruction docs
- **Python source** (`.py`) — AST extraction of embedded prompts and language-bearing agent-pipeline thresholds. This is not Python code linting: lintlang does not judge style, types, control flow, or general program correctness. A Python parse error is reported only because the requested language-bearing input could not be extracted safely.

Unknown extensions are tried as JSON → YAML → plain text.

## How Is lintlang Different?

| Tool | What It Does | How lintlang Differs |
|------|-------------|---------------------|
| **promptfoo** | Tests prompts via eval suites at runtime | lintlang is static — no LLM calls, catches issues at authoring time |
| **guardrails-ai** | Validates LLM outputs at runtime | lintlang examines static instruction artifacts before runtime |
| **NeMo Guardrails** | Runtime dialogue rails | lintlang operates on config files, not live conversations |
| **eslint / ruff** | Lints source code | lintlang lints natural language in agent configs |

lintlang treats tool descriptions, system prompts, and agent configs as **lintable artifacts** — static analysis for prose, like eslint for JavaScript.

## Development

```bash
git clone https://github.com/hermes-labs-ai/lintlang.git
cd lintlang
pip install -e ".[dev]"
pytest
```

## License

[Apache 2.0](LICENSE)

---

## About Hermes Labs

Hermes Labs is an independent AI-reliability lab building open-source tools that catch silent failure modes in production AI. More at [hermes-labs.ai](https://hermes-labs.ai).
