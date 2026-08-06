# LintLang

[![CI](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![Python](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](LICENSE)

**LintLang statically analyzes the natural-language instructions that control
AI agents, catching ambiguous tools, missing limits, and conflicting directives
before runtime.**

It flags patterns such as:

- empty, vague, or overlapping tool descriptions;
- tool pairs with no term that distinguishes one from the other (`H1.6`);
- missing stop conditions and unbounded retries;
- inconsistencies between tool schemas and their descriptions;
- unscoped context and vague instructions;
- conflicting output formats and malformed message roles;
- embedded prompts and uncalibrated thresholds in Python pipelines.

LintLang's default static checks are deterministic and local. They make no LLM,
API, telemetry, or network calls.

## Technical note

[Tool Differentia: Relational Static Analysis for AI Agent Tool Descriptions](https://hermes-labs.ai/research/tool-differentia)
documents LintLang H1.6, the bounded pairwise check for tool descriptions that
do not supply an analyzed distinction from a neighboring tool. It is a
technical note, not a semantic-equivalence proof or a runtime-selection
evaluation. Cite the archived Version 1.0 record at
[10.5281/zenodo.21817243](https://doi.org/10.5281/zenodo.21817243).

## Quick start

Run once without installing, using [uv](https://docs.astral.sh/uv/):

```bash
uvx lintlang scan AGENTS.md
```

For a persistent command in an isolated environment, use
[pipx](https://pipx.pypa.io/stable/):

```bash
pipx install lintlang
lintlang scan AGENTS.md
```

If pipx's app directory is not on `PATH`, run `pipx ensurepath`, open a new
shell, and retry the scan.

Or install from PyPI into the current Python environment:

```bash
python -m pip install lintlang
```

Requires Python 3.10+.

From your project root, point LintLang at an actual instruction file:

```bash
lintlang scan AGENTS.md
```

If your project uses another filename, replace `AGENTS.md` with its prompt,
tool-definition, agent-configuration, or supported directory path.

**3,000+ PyPI downloads · Used in recurring CI by [Character.AI's public Larch repository](https://github.com/character-ai/larch/pull/7960) · Independently packaged for [Gentoo](https://github.com/thehaven/haven-overlay/tree/master/dev-util/lintlang)**

When you are ready to make `HIGH` or `CRITICAL` findings block CI:

```bash
lintlang scan AGENTS.md --fail-on fail
```

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
LINTLANG v0.3.1

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

      - name: Inspect agent instructions
        uses: hermes-labs-ai/lintlang@v0.3.8
        with:
          path: AGENTS.md
```

The release tag pins both the action and the LintLang source it installs.
Upgrade that pin deliberately and inspect newly introduced findings before
making them blocking.

## Add it to pre-commit

Add the hook to `.pre-commit-config.yaml` with the explicit instruction paths
to scan:

```yaml
repos:
  - repo: https://github.com/hermes-labs-ai/lintlang
    rev: v0.3.8
    hooks:
      - id: lintlang
        args: [AGENTS.md]
```

Activate it and test the configured paths:

```bash
pre-commit install
pre-commit run lintlang
```

Replace or extend `args` with the prompt, tool-definition, agent-configuration,
or supported directory paths your repository owns. The hook scans only those
configured paths and reports findings without blocking on a verdict by default.
After reviewing the repository's baseline, opt into blocking `FAIL` findings:

```yaml
hooks:
  - id: lintlang
    args: [AGENTS.md, --fail-on, fail]
```

Missing, unreadable, or malformed configured inputs still return nonzero.

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

### H1.6: tool descriptions without a differentia

Per-tool schema validation assesses one definition at a time. Within one parsed
input, H1.6 instead compares tool definitions with each other and reports a pair
when, under LintLang's term-and-synonym model, one or both descriptions provide
no distinguishing term. Both tools can be individually valid, so per-tool
validation has nothing to report. A *mutual* finding means neither description
distinguishes itself; *domination* means one tool's terms are all covered by the
other, and the finding names which description to repair. Directory scans do
not aggregate tool definitions across files or infer a shared namespace.

Findings print the sub-code:
`~ [MEDIUM] H1.6 tool:find_tickets vs tool:search_tickets`. `pattern_id` stays
`H1`; JSON output adds a `code` field holding the most specific identifier.

H1.6 is MEDIUM, so `--fail-on fail` does not block on it. Matching uses a
finite English synonym lexicon, so pairs that say the same thing in different
words or a different sentence shape are missed. The absence of an H1.6 finding
is not evidence that no such pair exists.

Use narrow, intentional paths. Directory scans can discover Markdown and Python
files that were not written as agent configuration; use `.lintlangignore` or
`--exclude` where needed.

For exact H-series and Python rule identifiers:

```bash
lintlang patterns
```

See the [full technical reference](llms-full.txt) for detector details.

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

## Ecosystem

Public ecosystem signals include:

- [Character.AI's public Larch repository](https://github.com/character-ai/larch/pull/7960)
  runs the pinned `lintlang==0.3.1` package in recurring CI.
- [Agent Lint](https://github.com/zhupanov/agent-lint/issues/192) explicitly
  attributes improvements to LintLang's ideas, including structured diagnostics,
  rule selection, regression coverage, and prompt analysis.
- [The Haven Gentoo overlay](https://github.com/thehaven/haven-overlay/tree/master/dev-util/lintlang)
  packages LintLang for downstream installation.

These represent three distinct ecosystem signals: direct package execution,
product influence, and downstream packaging.

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
