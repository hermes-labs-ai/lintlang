# Gemini CLI extension

LintLang's repository root is a Gemini CLI extension. Its `AfterTool` hook runs
after successful `write_file` and `replace` calls, scans supported
language-bearing files, and appends concise repair guidance to the tool result.
It does not block or rewrite the file. Clean and unsupported files add no
context. Scanning `GEMINI.md` with the standalone CLI does not require this extension.

## Prerequisites

Use an already configured Gemini CLI and [uv](https://docs.astral.sh/uv/) on the
host's `PATH`. The hook runs source bundled in the installed extension and asks
uv for exactly `PyYAML==6.0.3` in an isolated cached environment. It does not use
an ambient `lintlang` installation. The first invocation may download dependencies;
a cache miss can therefore need network access. The scanner itself is offline.

## Install and verify

Install the historically verified LintLang 0.5.3 source:

```bash
gemini extensions install https://github.com/hermes-labs-ai/lintlang --ref=f89c3b0b8986fad162859dca052a8d5fe227eede
gemini extensions list
```

Review the installation consent prompt. The source commit pins
[v0.5.3](https://github.com/hermes-labs-ai/lintlang/releases/tag/v0.5.3).
This command was verified with Gemini CLI 0.32.1; the extension list reports
`lintlang (0.5.3)` as enabled, with `Type: git` and the source commit above.
Restart an active Gemini CLI session to load the installed extension.

This is a recorded tested pair, not a claim that a newer scanner/host combination
has been verified. Gemini CLI copies the extension, including `src/lintlang`,
into its extension directory. No separate LintLang installation is required.

## Behavior and limits

The hook handles `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.prompt`, and `.py`.
It returns at most eight findings plus an omitted count, includes stable codes,
locations, severities, descriptions, and repair suggestions, and omits the raw
`evidence` field. Hook execution is capped at 30 seconds.

Guidance is advisory, not a CI gate or runtime validation. Source-derived
information can still appear in diagnostics returned to Gemini; the host's own
provider behavior is outside the local scanner's network contract.

## Local development

From a repository checkout:

```bash
gemini extensions validate .
gemini extensions install . --consent
```

`--consent` skips the confirmation prompt: review the local source before using
it. Restart the session after installation. A local checkout is a different
source from the historical release pin above and needs its own verification.

## Troubleshooting and removal

Check `gemini extensions list` for the source and enabled state, confirm uv is
available in the host's environment, and restart the session after changes.
Only successful `write_file`/`replace` edits on supported files trigger the hook.
No added context can mean a clean or unsupported input; it does not establish
that all vendor-specific content was extracted. For cache/download failures,
inspect the hook error rather than assuming that an ambient pip installation
will supply the bundled runner's dependencies.

Use the host's terminal extension controls, then restart the session:

```bash
gemini extensions disable lintlang
gemini extensions uninstall lintlang
```

See the [Gemini CLI extension reference](https://geminicli.com/docs/extensions/reference/)
for host management semantics; removal does not require uninstalling other
extensions or the Gemini CLI itself.

Related: [integrations](integrations.md), [technical reference](../llms-full.txt),
[README](../README.md).
