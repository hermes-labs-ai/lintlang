<div align="center">

<img src="assets/lintlang-mark.svg" alt="LintLang" width="88" height="88">

# LintLang

**Static analysis for the instructions your AI agents execute.**

[![CI](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml/badge.svg)](https://github.com/hermes-labs-ai/lintlang/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lintlang)](https://pypi.org/project/lintlang/)
[![Downloads](https://img.shields.io/pypi/dm/lintlang?label=downloads%2Fmonth)](https://pypistats.org/packages/lintlang)
[![Python](https://img.shields.io/pypi/pyversions/lintlang)](https://pypi.org/project/lintlang/)
[![License](https://img.shields.io/pypi/l/lintlang)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/hermes-labs-ai/lintlang/badge)](https://scorecard.dev/viewer/?uri=github.com/hermes-labs-ai/lintlang)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20471007.svg)](https://doi.org/10.5281/zenodo.20471007)

[Product page](https://hermes-labs.ai/lintlang) · [Browser playground](https://hermes-labs.ai/lintlang#playground) · [PyPI](https://pypi.org/project/lintlang/) · [Documentation](llms-full.txt)

<img src="assets/preview.png" alt="lintlang scan reporting a CRITICAL tool-description finding" width="760">

</div>

LintLang catches ambiguous tool descriptions, missing operational limits, schema/description mismatches, conflicting output contracts, and other bounded instruction defects before a model runs.

**Local · deterministic · zero LLM calls · no telemetry or network access during a scan**

## Quick start

Requires Python 3.10+.

Run once without installing:

```bash
uvx lintlang scan AGENTS.md
```

Or install it:

```bash
pip install lintlang
lintlang scan AGENTS.md
```

Use the instruction file your agent actually reads: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, GitHub Copilot instructions, or another supported prompt/configuration path.

A normal scan reports findings without blocking:

```text
REVIEW — findings detected
```

To make `HIGH` or `CRITICAL` findings fail CI:

```bash
lintlang scan AGENTS.md --fail-on fail
```

## What LintLang catches

- **Ambiguous tools** — empty, vague, or overlapping descriptions without a clear selection rule.
- **Missing bounds** — retries, loops, or tool use without explicit stopping or progress conditions.
- **Contract mismatches** — descriptions that disagree with schemas, malformed message roles, or conflicting output-format requirements.
- **Context and prompt defects** — vague or unscoped context, embedded prompt issues, and selected problems in supported Python prompt pipelines.

Every finding has a stable identifier, severity, evidence, and a suggested review action where the parser can justify one.

LintLang does not decide whether arbitrary prose is true, predict runtime model behavior, or certify an agent as safe.

## What it can scan

| Surface | Examples |
| --- | --- |
| Coding-agent instructions | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot instructions |
| Agent configuration | YAML and JSON tool/config structures |
| Prompts and instructions | Markdown, text, and prompt files |
| Python | Supported extractable pipeline patterns |
| Invocation | Individual files, directories |

See the [technical reference](llms-full.txt) for detector coverage and extraction behavior.

## Use it where instructions change

### Local review

```bash
lintlang scan AGENTS.md
```

### Existing repositories

Create a baseline for findings already reviewed, then gate only new findings:

```bash
lintlang scan AGENTS.md --write-baseline .lintlang-baseline.json
lintlang scan AGENTS.md \
  --baseline .lintlang-baseline.json \
  --fail-on review
```

See [baseline adoption](docs/baselines.md) for matching semantics and maintenance.

### GitHub CI and Code Scanning

Generate a pinned workflow for a known instruction path:

```bash
lintlang init --github --path AGENTS.md
```

The generated workflow runs the same scanner and can upload SARIF for GitHub Code Scanning.

## Integrations

LintLang fits existing developer workflows rather than requiring a runtime service.

| Integration | Use |
| --- | --- |
| GitHub Action | Scan instruction paths in pull requests and CI |
| GitHub Code Scanning | Upload SARIF findings beside code findings |
| pre-commit | Review instructions before commit |
| Claude Code | Optional non-blocking guidance after supported edits |
| Gemini CLI | Optional non-blocking guidance after supported edits |
| OpenCode | Optional non-blocking post-edit guidance |
| Hermes Agent | Bounded pre-verification of supported edits |
| MegaLinter | Opt-in external plugin for existing MegaLinter users |

See the [integrations and ecosystem guide](docs/integrations.md) for setup instructions and public ecosystem references.

## Results and exit behavior

| Verdict | Meaning |
| --- | --- |
| `PASS` | No remaining `MEDIUM` or higher findings |
| `REVIEW` | At least one `MEDIUM` finding remains |
| `FAIL` | At least one `HIGH` or `CRITICAL` finding remains |
| `ERROR` | A requested input could not be inspected |

Findings are non-blocking by default. Use `--fail-on` to choose a CI threshold. Input errors remain nonzero regardless of that threshold.

Machine-readable JSON and SARIF output are available for automation.

## Where LintLang fits

```text
syntax and schema validation
        ↓
LintLang static instruction checks
        ↓
runtime agent evaluation
        ↓
domain and security review
```

LintLang is an authoring and review control. It does not run models, observe tool selection at runtime, prove semantic correctness, replace evaluation, or establish that an agent is production-safe.

A clean scan means only that the selected static checks found no covered defects in the recognized content.

## Evidence

[Character.AI’s public Larch repository](https://github.com/character-ai/larch) pins a LintLang release in recurring CI. [MegaLinter](https://github.com/oxsecurity/megalinter) catalogs LintLang as the `AI_LINTLANG` external plugin.

See the [integrations and ecosystem guide](docs/integrations.md) for additional public references.

LintLang is an engineering evolution of Hermes Labs’ research into structural epistemic failure modes in language models. See [Research and design lineage](docs/research.md).

## Documentation

| Need | Document |
| --- | --- |
| Detector behavior and rule IDs | [Technical reference](llms-full.txt) |
| Existing-repository adoption | [Baselines](docs/baselines.md) |
| Integrations and ecosystem | [Integration guide](docs/integrations.md) |
| CI and Code Scanning | [GitHub initializer](docs/github.md) |
| Research and design lineage | [Research](docs/research.md) |
| Claude Code | [Plugin guide](integrations/claude-code/README.md) |
| Gemini CLI | [Extension guide](docs/gemini-cli-extension.md) |
| MegaLinter | [Plugin guide](mega-linter-plugin-lintlang/README.md) |
| Product scope and intent | [INTENT.md](INTENT.md) |
| Releases | [CHANGELOG.md](CHANGELOG.md) |
| Contribution | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Security | [SECURITY.md](SECURITY.md) |

## Contributing

Bug reports, disputed findings, reproducible false positives, documentation corrections, and focused contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## License

[Apache License 2.0](LICENSE)

LintLang is maintained by [Hermes Labs](https://hermes-labs.ai).
