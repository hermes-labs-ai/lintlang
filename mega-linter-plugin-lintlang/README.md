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

MegaLinter's plugin loader runs the descriptor's `install` step at run time
(`pip install --no-cache-dir lintlang==0.5.3`) inside the existing MegaLinter
image, then invokes:

```console
lintlang scan --fail-on fail <selected files>
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
  oxsecurity/megalinter-python:v9.4.0
```

Observed on `oxsecurity/megalinter-python:v9.4.0`
(digest `sha256:e83df3697c0547024b3a21938f19125564627d86a1ffe6f6a18747c0dfd80d69`):

- `[Plugins] Successful initialization of AI plugins`
- `- Using [lintlang v0.5.3] https://lintlang.ai/`
- `- Command: [lintlang scan --fail-on fail .mega-linter.yml agent-bad.yaml
  agent-clean.yaml mega-linter-plugin-lintlang/lintlang.megalinter-descriptor.yml]`
- `agent-bad.yaml` → `FAIL` (1 critical, 2 high, 7 medium, 3 low);
  `agent-clean.yaml` → `PASS`
- MegaLinter reported `1` error and exited **1**

Removing `agent-bad.yaml` and rerunning the same command yields
`Successfully linted all files without errors` and exit **0**, confirming the
nonzero exit is caused by the LintLang `FAIL` verdict and not by the plugin
load or install path.

The same descriptor was also exercised in the full `oxsecurity/megalinter:v8`
image (MegaLinter 8.8.0) with `docker run --rm -v "$PWD:/tmp/lint"
oxsecurity/megalinter:v8`, adding unrelated `README.md`, `notes.txt`,
`package.json`, and `src/app.py` files to the workspace. The plugin loader
reported `[Plugins] Install command: pip install --no-cache-dir
lintlang==0.5.3`, the version probe returned `lintlang 0.5.3`, only the bad
fixture produced `FAIL`, the unrelated files passed clean, MegaLinter counted
one error, and the container exited 1; without the bad fixture it exited 0.

The descriptor also validates against MegaLinter's published
[descriptor JSON schema](https://github.com/oxsecurity/megalinter/blob/main/megalinter/descriptors/schemas/megalinter-descriptor.jsonschema.json).

MegaLinter passes every matching file to LintLang, including `.mega-linter.yml`
and this descriptor. Both scan clean; use `FILTER_REGEX_EXCLUDE` if you prefer
to keep them out of the file list.
