# LintLang for OpenCode

This native OpenCode plugin runs LintLang after successful file-edit tools and
appends concise repair context to the tool result. It supports OpenCode
`1.18.27` and the legacy plugin contract `tool.execute.after`. The adapter
never rewrites files or blocks a tool call.

## Install

Install the pinned LintLang release so `lintlang` is on `PATH`:

```bash
pipx install lintlang==0.5.3
```

Copy `lintlang.js` into `.opencode/plugins/` (project-local) or
`~/.config/opencode/plugins/` (global). Start OpenCode in the project as usual.

## Behavior and limits

The plugin handles `edit`, `multiedit`, `patch`, `write`, and `apply_patch` when
the post-tool args or metadata identify an explicit `filePath`, `file_path`,
`path`, `file`, or `files` entry. It scans `.yaml`, `.yml`, `.json`, `.txt`,
`.md`, `.prompt`, and `.py`, returning at most eight findings and omitting raw
evidence. Tools without an explicit path (for example a patch whose target is
only embedded in patch text) are skipped because the host does not provide a
reliable changed-file list through this contract.

OpenCode `1.18.27` was verified from the published `@opencode-ai/plugin@1.18.27`
type declarations: `tool.execute.after` receives tool name/args and output
metadata. `file.edited` is not present in that pinned declaration, so this
adapter does not claim support for it. Newer OpenCode releases may expose a
different event API; validate the installed host before upgrading this adapter.

## Local smoke test

```bash
opencode --version                 # expected: 1.18.27 for the tested host
```
