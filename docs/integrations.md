# Integrations and ecosystem

LintLang is provider-neutral: it scans local instruction-bearing files and
does not require a model API or host-specific runtime. These entry points make
that scanner convenient in common workflows.

## Native adapters

| Host or workflow | Entry point | Behavior |
| --- | --- | --- |
| GitHub Actions | [`action.yml`](../action.yml) | Runs scans and can emit SARIF for Code Scanning |
| Claude Code | [`integrations/claude-code`](../integrations/claude-code/) | Non-blocking `PostToolUse` repair guidance |
| Gemini CLI | [`docs/gemini-cli-extension.md`](gemini-cli-extension.md) | Non-blocking `AfterTool` repair guidance |
| OpenCode | [`integrations/opencode`](../integrations/opencode/) | Non-blocking post-edit repair guidance |
| Hermes Agent | [`src/lintlang/integrations/hermes_agent.py`](../src/lintlang/integrations/hermes_agent.py) | Pre-verification gate for changed instruction files |
| pre-commit | [`.pre-commit-hooks.yaml`](../.pre-commit-hooks.yaml) | Scans configured paths during local or CI hooks |

## External ecosystem references

These projects have publicly referenced or integrated LintLang. A reference or
plugin listing is not an adoption claim or endorsement.

| Project | Reference |
| --- | --- |
| [MegaLinter](https://github.com/oxsecurity/megalinter) | [`AI_LINTLANG` external plugin](https://github.com/oxsecurity/megalinter/blob/main/docs/plugins.md) |
| [Character.AI Larch](https://github.com/character-ai/larch) | [Recurring CI pin](https://github.com/character-ai/larch/blob/ef7ee4b7f946f29fa51981f5422a1a93e83c79a7/.github/workflows/requirements-agent-linters.txt) and [linting guide](https://github.com/character-ai/larch/blob/210d08a8f6c1b0dd14c27b709c66471bd31a5636/docs/linting.md) |
| [Piebald-AI/awesome-gemini-cli](https://github.com/Piebald-AI/awesome-gemini-cli) | [Merged catalog entry](https://github.com/Piebald-AI/awesome-gemini-cli/pull/124) |
| [ZeroPointRepo/awesome-hermes-skills](https://github.com/ZeroPointRepo/awesome-hermes-skills) | [Merged catalog entry](https://github.com/ZeroPointRepo/awesome-hermes-skills/pull/37) |

For release and merge dates, see the [Listed in](../README.md#listed-in)
section of the README.
