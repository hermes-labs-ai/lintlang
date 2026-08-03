# LintLang

[![CI](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![Python](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](LICENSE)

**Static analysis for the natural-language layer of AI agents.**

Valid JSON, YAML, or Python can still contain agent instructions that are
ambiguous, unbounded, or structurally inconsistent. LintLang flags patterns
such as:

- empty, vague, or overlapping tool descriptions;
- missing stop conditions and unbounded retries;
- inconsistencies between tool schemas and their descriptions;
- unscoped context and vague instructions;
- conflicting output formats and malformed message roles;
- embedded prompts and uncalibrated thresholds in Python pipelines.

LintLang's default static checks are deterministic and local. They make no LLM,
API, telemetry, or network calls.

## Quick start

Install from PyPI:

```bash
python -m pip install lintlang
```

From your project root, point LintLang at an actual instruction file:

```bash
lintlang scan AGENTS.md --fail-on fail
```

If your project uses another filename, replace `AGENTS.md` with its prompt,
tool-definition, agent-configuration, or supported directory path.

Each finding identifies the affected location, the detected pattern, its
severity, and a suggested review action.

## Try the bundled example

The source repository includes a deliberately broken example:

```bash
git clone --depth 1 https://github.com/hermes-labs-ai/lintlang.git
cd lintlang

lintlang scan samples/bad_tool_descriptions.yaml --fail-on fail
```

Excerpt from `lintlang 0.3.1`:

```text
FAIL — 1 CRITICAL, 2 HIGH, 6 MEDIUM, 3 LOW

H1: Tool Description Ambiguity

  [CRITICAL] tool:process_ticket
  Tool 'process_ticket' has no description.

  [HIGH] tool:get_user_info
  Tool 'get_user_info' has a very short description (13 chars):
  "Get user info"

…

H2: Missing Constraint Scaffolding

  [HIGH] system_prompt
  System prompt defines tools but contains no termination conditions,
  retry budgets, or progress checks.
```

The command exits with status `1` because it includes `--fail-on fail`.

## Verdicts and CI behavior

| Verdict | Practical meaning |
|---|---|
| `PASS` | No `MEDIUM`, `HIGH`, or `CRITICAL` finding remained after the selected checks and filters |
| `REVIEW` | At least one `MEDIUM` finding remained |
| `FAIL` | At least one `HIGH` or `CRITICAL` finding remained |
| `ERROR` | A requested input could not be inspected |

`PASS` applies only to recognized content extracted from the requested inputs
and the checks and severity filters selected for that run. It does not mean
that every structure in an arbitrary JSON or YAML file was extracted.
A clean LintLang scan is not evidence that an agent is safe or runtime-correct.

By default, findings are reported without failing the process.

- `--fail-on fail` blocks on `FAIL`.
- `--fail-on review` blocks on `REVIEW` or `FAIL`.
- Missing, malformed, unreadable, or otherwise unscannable requested inputs
  remain nonzero regardless of the chosen finding threshold.
- A requested directory with no eligible files also exits nonzero.

Filters such as `--min-severity` are applied before the verdict. For initial
adoption, keep the full output visible and use `--fail-on fail` to block only
the highest-severity findings.

## Add it to CI

After choosing one real instruction path in your repository:

```yaml
jobs:
  lint-agent-instructions:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: Install LintLang
        run: python -m pip install "lintlang==0.3.1"

      - name: Inspect agent instructions
        run: lintlang scan AGENTS.md --fail-on fail
```

Pinning LintLang keeps the reviewed rule version fixed. Upgrade that pin
deliberately and inspect newly introduced findings before making them blocking.

For machine-readable output:

```bash
lintlang scan AGENTS.md --format json --fail-on fail
```

## What it inspects

LintLang currently accepts:

- JSON and YAML objects using recognized top-level agent fields such as
  `system_prompt`, `instructions`, `tools`, `functions`, `messages`, and
  selected response-schema fields;
- `.txt`, `.md`, and `.prompt` instruction files;
- Python files, using AST extraction for prompt-like strings and
  threshold assignments.

Nested vendor-specific layouts and raw top-level YAML arrays are not
automatically normalized. A syntactically valid input must still match a
recognized shape for its structured tools or messages to be inspected.

The checks cover reader-facing categories including tool clarity, execution
bounds, schema-description alignment, context boundaries, instruction
specificity, output contracts, message-role structure, and Python pipeline
hygiene.

Use narrow, intentional paths. Directory scans can discover Markdown and Python
files that were not written as agent configuration; use `.lintlangignore` or
`--exclude` where needed.

For exact H-series and Python rule identifiers:

```bash
lintlang patterns
```

See the [full technical reference](llms-full.txt) for detector and HERM details.

## Where it fits

```text
syntax and schema validation
        ↓
LintLang static language checks
        ↓
runtime agent evaluation
        ↓
domain and security review
```

LintLang is useful during authoring and pull-request review, before runtime
testing. It does not:

- determine whether an instruction is factually or semantically correct;
- observe an agent selecting or executing tools;
- prove that a finding causes a runtime failure;
- certify an agent as safe or production-ready;
- replace runtime evaluation or human review.

Suggestions are review aids, not guaranteed meaning-preserving fixes.

## In use

Public examples include package execution in
[Character.AI's Larch CI integration](https://github.com/character-ai/larch/pull/7960),
rule-methodology adaptation in
[Muster](https://github.com/Adnova-Group/muster/commit/516c5854fb232c0e4ec365214e7304ed7eb93ff6),
and downstream packaging in an independent
[Gentoo overlay](https://github.com/thehaven/haven-overlay/blob/master/dev-util/lintlang/lintlang-0.3.1.ebuild).

## Optional instruction preflight

Secondary capability: [provider-neutral instruction preflight](docs/preflight.md)
inspects one present instruction plus explicit context.

## More

- [Technical reference](llms-full.txt)
- [Product scope and invariants](INTENT.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Report an issue or disputed finding](https://github.com/hermes-labs-ai/lintlang/issues)
- [Security policy](SECURITY.md)

## License

[Apache License 2.0](LICENSE)

LintLang is maintained by [Hermes Labs](https://hermes-labs.ai).
