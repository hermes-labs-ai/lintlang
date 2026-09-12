# LintLang for Claude Code

This native Claude Code plugin runs LintLang after successful `Write` and
`Edit` tool calls. For supported language-bearing files, findings are returned
to Claude as concise repair context. Clean or unsupported files add no context.
The adapter never rewrites files and never blocks a tool call.

## Prerequisites

Install the adapter's tested LintLang release so `lintlang` is on `PATH`:

```bash
pipx install lintlang==0.6.0
```

The hook prefers that installed `lintlang` executable. It falls back to
`python3 -m lintlang` only on interpreters that support `-P` and
`PYTHONSAFEPATH`, so the directory Claude Code happens to be working in is never
placed on the resolver's import path.

## Try the plugin from this checkout

```bash
claude --plugin-dir ./integrations/claude-code
```

Claude Code also accepts a plugin ZIP through `--plugin-dir` or a hosted ZIP
through `--plugin-url`.

## Install it as a plugin

The repository root is a Claude Code marketplace
(`.claude-plugin/marketplace.json`) that catalogs this directory, so no local
checkout is needed:

```text
/plugin marketplace add hermes-labs-ai/lintlang
/plugin install lintlang@lintlang
```

The same two steps are available outside a session as
`claude plugin marketplace add hermes-labs-ai/lintlang` and
`claude plugin install lintlang@lintlang`.

To turn it off again, use the `/plugin` menu or the exact counterparts:

```bash
claude plugin disable lintlang@lintlang     # keep it installed, stop the hook
claude plugin uninstall lintlang@lintlang   # remove the plugin
claude plugin marketplace remove lintlang   # remove the catalog entry too
```

Validate the plugin against the installed Claude Code runtime:

```bash
claude plugin validate --strict ./integrations/claude-code
```

The hook supports `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.prompt`, and `.py`,
matching LintLang's file scanner. It sends only finding descriptions and repair
suggestions back to Claude; raw prompt evidence is omitted.
