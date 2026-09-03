# LintLang for Claude Code

This native Claude Code plugin runs LintLang after successful `Write` and
`Edit` tool calls. For supported language-bearing files, findings are returned
to Claude as concise repair context. Clean or unsupported files add no context.
The adapter never rewrites files and never blocks a tool call.

## Prerequisites

Install LintLang so `lintlang` is on `PATH`:

```bash
pipx install lintlang
```

## Try the plugin from this checkout

```bash
claude --plugin-dir ./integrations/claude-code
```

Claude Code also accepts a plugin ZIP through `--plugin-dir` or a hosted ZIP
through `--plugin-url`. A marketplace may point at this plugin directory when
the repository is released; users can then install it with
`claude plugin install lintlang@<marketplace-name>`.

Validate the plugin against the installed Claude Code runtime:

```bash
claude plugin validate --strict ./integrations/claude-code
```

The hook supports `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.prompt`, and `.py`,
matching LintLang's file scanner. It sends only finding descriptions and repair
suggestions back to Claude; raw prompt evidence is omitted.
