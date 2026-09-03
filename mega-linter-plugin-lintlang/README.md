# LintLang for MegaLinter

This external plugin adds `AI_LINTLANG` to MegaLinter. It scans agent
instructions, tool definitions, prompts, and Python files containing embedded
agent language. The plugin is deterministic and makes no LLM calls.

## Configure

Add the descriptor URL and enable the linter in `.mega-linter.yml`:

```yaml
PLUGINS:
  - https://raw.githubusercontent.com/hermes-labs-ai/lintlang/main/mega-linter-plugin-lintlang/lintlang.megalinter-descriptor.yml

ENABLE_LINTERS:
  - AI_LINTLANG
```

For a local checkout, replace the HTTPS URL with:

```yaml
PLUGINS:
  - file://mega-linter-plugin-lintlang/lintlang.megalinter-descriptor.yml
```

MegaLinter installs the pinned LintLang release and runs the equivalent of:

```console
lintlang scan <selected files> --fail-on fail
```

A LintLang `FAIL` verdict makes the linter exit nonzero. `REVIEW` remains
advisory. MegaLinter's normal file filtering and exclusion settings determine
which `.json`, `.md`, `.py`, `.txt`, `.yaml`, and `.yml` files are passed to
LintLang.

## Verify locally

From the LintLang repository root:

```console
python -m pytest -q tests/test_megalinter_plugin.py
```

The test validates the descriptor contract and proves that the descriptor's
arguments pass `samples/clean_config.yaml` while failing
`samples/bad_tool_descriptions.yaml`.
