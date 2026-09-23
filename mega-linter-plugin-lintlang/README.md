# LintLang for MegaLinter

This external plugin adds `AI_LINTLANG` to an existing MegaLinter installation.
By default, it selects conventionally named agent-instruction, prompt, tool,
skill, and system files for LintLang's deterministic local scan. The scanner
makes no LLM calls; loading the plugin and installing its package can use the network.

## Configure

Add the descriptor URL and linter to your existing `.mega-linter.yml`. Preserve
other entries in `PLUGINS` and `ENABLE_LINTERS`; replacing those lists can disable
unrelated checks.

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

The `main` descriptor URL is mutable even though the descriptor pins its scanner
package. Review descriptor changes separately from package upgrades; those are
different parts of the installation chain.

MegaLinter's loader runs the descriptor's installation step at run time
(`pip install --no-cache-dir lintlang==0.7.1`) inside the existing image, then invokes:

```console
lintlang scan --fail-on fail <selected files>
```

FAIL makes the linter exit nonzero; REVIEW remains advisory. Input errors also
remain nonzero. Default selection covers conventional agent-language names
(`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, Copilot `*.instructions.md`, and names
containing `agent`, `prompt`, `tool`, `skill`, `system`, or `instruction`) rather
than every Markdown, YAML, JSON, or Python file.

To deliberately broaden your scope, configure the per-linter override with the
file extensions you own:

```yaml
AI_LINTLANG_FILE_EXTENSIONS:
  - .yaml
  - .yml
  - .json
```

MegaLinter passes matching files to LintLang. Use its normal
`FILTER_REGEX_EXCLUDE` or `AI_LINTLANG_FILE_NAMES_REGEX` controls for a narrower
or differently named scope. Inspect the selected file list; no findings is not
proof that the intended files were selected.

## Verify in-process

From the LintLang repository root:

```console
python -m pytest -q tests/test_megalinter_plugin.py
```

These tests validate the descriptor contract and prove that its arguments pass
`samples/clean_config.yaml` while failing `samples/bad_tool_descriptions.yaml`.
They exercise the CLI in-process, not MegaLinter's loader.

## Verify against a real container

To verify the loader, runtime installation, and exit behavior, use a scratch
workspace containing `.mega-linter.yml`, this plugin directory, and two fixtures
copied from `samples/`: `agent-clean.yaml` from `clean_config.yaml`, and
`agent-bad.yaml` from `bad_tool_descriptions.yaml`. The renamed files match the
plugin's default selector.

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

Confirm selection and the expected FAIL with the bad fixture present. Remove
that fixture and rerun to check the clean outcome. The `v8` image tag is mutable;
record the actual image version and scanner version for your trial.

The recorded MegaLinter 8.8.0 trial installed LintLang 0.5.3 and exercised the
current selector in a workspace containing `AGENTS.md`, `bad-agent.yaml`, and
unrelated metadata. It initialized `AI_LINTLANG` and selected only the two
conventionally named instruction surfaces. The bad fixture produced FAIL; after
removing it, only `AGENTS.md` was selected and the process exited 0. This is
historical loader/selector evidence, not a new real-container test of the current
0.7.1 package, nor a claim about agent behavior or adoption.

The descriptor also validates against MegaLinter's published
[descriptor JSON schema](https://github.com/oxsecurity/megalinter/blob/main/megalinter/descriptors/schemas/megalinter-descriptor.jsonschema.json).

## Troubleshooting and removal

For an absent linter, inspect descriptor loading and `ENABLE_LINTERS`. For absent
files, inspect the selector and overrides before broadening scope. For installation
errors, check the container's package-download access; a scanner's offline
analysis does not make runtime package installation offline.

Remove only the LintLang descriptor entry and `AI_LINTLANG`-specific configuration
to disable this integration. Preserve unrelated plugins and linters.

Related: [integrations](../docs/integrations.md), [GitHub CI](../docs/github.md),
[technical reference](../llms-full.txt), [README](../README.md).
