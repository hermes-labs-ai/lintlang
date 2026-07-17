# AGENTS.md

`lintlang` is a static linter for AI agent configs, tool definitions, and system prompts.

## Use it for

- linting tool descriptions before agents start choosing the wrong tools
- checking prompts and configs for missing constraints, schema mismatches, and role confusion
- running a zero-LLM CI gate over YAML, JSON, prompt text, and Python source files
- scanning `.py` files to find embedded prompts and uncalibrated thresholds (P1/P2 detectors)

## Do not use it for

- runtime evaluation
- dynamic agent testing
- proving an agent is safe in production

## Minimal commands

```bash
pip install -e ".[dev]"
lintlang --help
lintlang scan samples/bad_tool_descriptions.yaml
pytest -q
ruff check src/ tests/
```

## Output shape

- repository scan outcomes: `ERROR`, `PASS`, `REVIEW`, or `FAIL`
- structural findings by pattern `H1` through `H7`, plus Python pipeline findings `P1` and `P2`
- JSON output for CI via `--format json`

## Success means

- the same config file produces the same verdict and findings
- scan output points to concrete locations and rewrite guidance
- tests and sample self-scan pass offline

## Common failure cases

- users expect lintlang to judge runtime model behavior
- configs are syntactically valid but still underspecified for their intended use
- teams gate only on syntax and do not review language-level instruction risks

## Maintainer notes

- keep detector language aligned with the exact patterns exercised by the samples
- keep CLI examples and severity semantics aligned with README
- keep the tool fully offline and deterministic
