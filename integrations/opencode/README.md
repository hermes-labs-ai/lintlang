# LintLang for OpenCode

This native plugin appends concise repair context after supported successful
file-edit tools. It targets the OpenCode `1.18.27` legacy
`tool.execute.after` contract. It never rewrites a file or blocks a tool call.
Scanning an instruction file with the standalone CLI does not install this plugin.

## Prerequisites and setup

Install the pinned scanner with Python 3.10+ so `lintlang` is on the host's `PATH`:

```bash
pipx install lintlang==0.6.0
lintlang --version
```

Copy [`lintlang.js`](lintlang.js) into `.opencode/plugins/` (project-local) or
`~/.config/opencode/plugins/` (global). Start OpenCode in the project as usual.

## Verify the contract

```bash
opencode --version                 # documented contract: 1.18.27
```

That command identifies the host version; it is not an end-to-end plugin test.
OpenCode `1.18.27` was checked against the published
`@opencode-ai/plugin@1.18.27` type declarations: `tool.execute.after` receives
tool name/args and output metadata. `file.edited` is absent from that declaration,
so this adapter does not claim to support it. This evidence is distinct from a
live-host compatibility run. Newer releases can expose a different event API.

From a LintLang checkout, exercise the adapter's repository tests:

```bash
python -m pytest -q tests/test_opencode_plugin.py
```

For your installed host, separately confirm a successful supported edit with an
explicit changed path and inspect its result for expected guidance. Do not infer
coverage of every edit tool from a version string or the repository tests alone.

## Behavior and limits

The plugin handles `edit`, `multiedit`, `patch`, `write`, and `apply_patch` when
the post-tool args or metadata identify an explicit `filePath`, `file_path`,
`path`, `file`, or `files` entry. It scans `.yaml`, `.yml`, `.json`, `.txt`,
`.md`, `.prompt`, and `.py`, returning at most eight findings and omitting raw
evidence. Tools without an explicit path, such as a patch whose target is only
embedded in patch text, are skipped: this contract supplies no reliable changed-
file list for that case.

A clean or unsupported input produces no repair guidance. Diagnostics can still
contain source-derived text; the host's provider/network activity is separate
from LintLang's offline scan. Use a separate explicit CI gate for enforcement.

## Troubleshooting and removal

Check `lintlang --version` in the host's environment, the plugin installation
location, the host version, and whether the successful edit actually supplied
an explicit path. Do not broaden path inference to arbitrary patch text merely
to make an unsupported tool appear covered.

To remove the integration, delete only the copied `lintlang.js` from the project
or global plugin directory where you installed it, then restart the host. Leave
unrelated plugins intact.

Related: [integrations](../../docs/integrations.md),
[technical reference](../../llms-full.txt), [README](../../README.md).
