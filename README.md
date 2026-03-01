# lintlang

Linguistic linter for AI agent systems. Scans tool descriptions, system prompts, and agent configs for language-to-action boundary failures.

## Quick Start

```bash
pip install lintlang
lintlang scan your_agent_config.yaml
```

## What It Detects

| Pattern | Name | What Users Report |
|---------|------|-------------------|
| H1 | Tool Description Ambiguity | "Agent picks wrong tool" |
| H2 | Missing Constraint Scaffolding | "Agent loops infinitely" |
| H3 | Schema-Intent Mismatch | "Structured output broken" |
| H4 | Context Boundary Erosion | "Agent leaks state" |
| H5 | Implicit Instruction Failure | "Model doesn't follow instructions" |
| H6 | Template Format Contract Violation | "Agent broke after prompt change" |
| H7 | Role Confusion | "Chat history messed up" |

## Usage

```bash
# Scan a single file
lintlang scan agent_config.yaml

# Scan multiple files
lintlang scan config1.yaml config2.json prompt.txt

# Check specific patterns only
lintlang scan config.yaml --patterns H1 H3

# Output as markdown
lintlang scan config.yaml --format markdown

# Output as JSON (for CI integration)
lintlang scan config.yaml --format json

# Fail CI if health score drops below threshold
lintlang scan config.yaml --fail-under 80

# List all patterns
lintlang patterns
```

## License

Apache 2.0
