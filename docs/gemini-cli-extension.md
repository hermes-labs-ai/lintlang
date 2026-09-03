# Gemini CLI extension

LintLang's repository root is a Gemini CLI extension. Its `AfterTool` hook runs
after successful `write_file` and `replace` calls, scans supported
language-bearing files, and appends concise repair guidance to the tool result.
It does not block or rewrite the file. Clean and unsupported files add no
context.

## Install

The extension requires [uv](https://docs.astral.sh/uv/) on `PATH`. The hook runs
the source bundled in the installed extension and asks uv for exactly
`PyYAML==6.0.3` in an isolated cached environment. It does not depend on an
ambient `lintlang` installation. The first scan may download that pinned wheel;
later scans reuse uv's cache.

From a checkout:

```bash
gemini extensions validate .
gemini extensions install . --consent
```

Once the root manifest is released, users can instead install the GitHub
repository URL. Gemini CLI copies the extension, including `src/lintlang`, into
its extension directory.

## Behavior

The hook handles `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.prompt`, and `.py`.
It returns at most eight findings plus an omitted count, includes stable codes,
locations, severities, descriptions, and repair suggestions, and omits the raw
`evidence` field. Hook execution is capped at 30 seconds.
