# LintLang for MegaLinter

This external plugin adds `AI_LINTLANG` to MegaLinter. By default, it selects
conventionally named agent-instruction, prompt, tool, skill, and system files
for LintLang's deterministic, local scan. The plugin makes no LLM calls.

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

MegaLinter's plugin loader runs the descriptor's `install` step at run time
(`pip install --no-cache-dir lintlang==0.5.3`) inside the existing MegaLinter
image, then invokes:

```console
lintlang scan --fail-on fail <selected files>
```

A LintLang `FAIL` verdict makes the linter exit nonzero. `REVIEW` remains
advisory. By default, the descriptor selects conventional agent-language names
(`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot `*.instructions.md`, and files
whose names contain `agent`, `prompt`, `tool`, `skill`, `system`, or
`instruction`) rather than every Markdown, YAML, JSON, or Python file.

To deliberately broaden a repository's scope, configure MegaLinter's normal
per-linter override with the file extensions you own:

```yaml
AI_LINTLANG_FILE_EXTENSIONS:
  - .yaml
  - .yml
  - .json
```

## Verify locally

From the LintLang repository root:

```console
python -m pytest -q tests/test_megalinter_plugin.py
```

The test validates the descriptor contract and proves that the descriptor's
arguments pass `samples/clean_config.yaml` while failing
`samples/bad_tool_descriptions.yaml`. It exercises the CLI in-process; it does
not exercise MegaLinter's loader.

## Verify against a real MegaLinter container

The checks above are in-process. To prove the loader, the run-time install, and
the exit code, run the plugin inside a real MegaLinter image.

Build a scratch workspace containing `.mega-linter.yml`, this plugin directory,
and two fixtures copied from `samples/` — `agent-clean.yaml`
(`clean_config.yaml`) and `agent-bad.yaml` (`bad_tool_descriptions.yaml`):

```yaml
# .mega-linter.yml
PLUGINS:
  - file://mega-linter-plugin-lintlang/lintlang.megalinter-descriptor.yml
ENABLE_LINTERS:
  - AI_LINTLANG
VALIDATE_ALL_CODEBASE: true
LOG_LEVEL: INFO
```

```console
docker run --rm --platform linux/amd64 \
  -v "$PWD:/tmp/lint:rw" -e DEFAULT_WORKSPACE=/tmp/lint \
  oxsecurity/megalinter:v8
```

The current selector was exercised in MegaLinter 8.8.0 with a workspace
containing `AGENTS.md`, `bad-agent.yaml`, and unrelated repository metadata.
The loader initialized `AI_LINTLANG`, installed LintLang 0.5.3, and selected
only the two conventionally named instruction surfaces. The bad fixture
produced the expected `FAIL`; after removing it, MegaLinter selected only
`AGENTS.md` and exited 0. This is loader and selector compatibility evidence,
not a claim about a repository's agent behavior or adoption.

The descriptor also validates against MegaLinter's published
[descriptor JSON schema](https://github.com/oxsecurity/megalinter/blob/main/megalinter/descriptors/schemas/megalinter-descriptor.jsonschema.json).

MegaLinter passes every matching file to LintLang. Use its normal
`FILTER_REGEX_EXCLUDE` or `AI_LINTLANG_FILE_NAMES_REGEX` controls when a
repository needs a still narrower or differently named scope.
