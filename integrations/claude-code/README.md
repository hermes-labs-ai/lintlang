# LintLang agent plugin

The package contains one portable Agent Plugins skill plus a Claude Code
post-edit adapter. Neither rewrites a file or blocks a tool call.

| Surface | Hosts | Runs | Scope |
| --- | --- | --- | --- |
| `lintlang-audit` skill | Agent Plugins hosts, including Cursor; Claude Code | When you ask for an audit | The file you name |
| `PostToolUse` adapter | Claude Code only | After supported `Write` or `Edit` | The file just changed |

The skill is not the hook. Disabling one does not disable the other; installing
the plugin provides both. Scanning `CLAUDE.md` with the standalone CLI does not
require installing this plugin.

## Prerequisites

Use Claude Code with plugin support. Install the tested scanner release with
Python 3.10+ so `lintlang` is on the host's `PATH`:

```bash
pipx install lintlang==0.7.0
lintlang --version
```

The hook prefers the installed executable. It falls back to `python3 -m lintlang`
only on interpreters supporting `-P` and `PYTHONSAFEPATH`, keeping the working
directory off the resolver's import path. The skill prefers the same executable
and otherwise runs the pinned release through `uvx --from lintlang==0.7.0`.
That fallback uses an isolated cached environment, not a persistent LintLang
installation; it can download packages on a cache miss. Neither installed route
needs a checkout of this repository.

## Install in Claude Code from the marketplace

The repository root is a Claude Code marketplace
(`.claude-plugin/marketplace.json`) that catalogs this plugin directory:

```text
/plugin marketplace add hermes-labs-ai/lintlang
/plugin install lintlang@lintlang
```

The same steps are available outside a session:

```bash
claude plugin marketplace add hermes-labs-ai/lintlang
claude plugin install lintlang@lintlang
```

## Use in Cursor

The repository-level `.cursor-plugin/marketplace.json` points Cursor at this
package. Cursor resolves `.cursor-plugin/plugin.json` there, whose `skills`
field exposes the existing `lintlang-audit` skill rather than copying it.
The root Agent Plugins manifest remains the portable package contract.

For a local checkout, copy the package into Cursor's local plugin directory,
reload Cursor, and confirm that `lintlang-audit` appears under Customize:

```bash
mkdir -p ~/.cursor/plugins/local
cp -R integrations/claude-code ~/.cursor/plugins/local/lintlang
```

Then ask Cursor to `audit AGENTS.md with lintlang`. Cursor's Agent Plugins
support covers skills and MCP servers, not hooks. It therefore loads the audit
skill but does not run the Claude-specific `PostToolUse` adapter automatically.
The published Cursor listing uses that narrower, demonstrated capability.

## Try and validate a local checkout with Claude Code

From this repository's root:

```bash
claude plugin validate --strict ./integrations/claude-code
claude --plugin-dir ./integrations/claude-code
```

Validation checks the plugin against the installed Claude Code runtime; it is
not a claim that every host version has been tested. The repository records the
scanner pin above, not a universal Claude Code compatibility range.

## Verify and use the audit skill

Ask for an audit and name the file:

```text
audit AGENTS.md with lintlang
```

The skill resolves a runner, scans that file with `lintlang scan --format json`,
reads `input_error` and `verdict` first, and reports findings by code and location.
It treats the payload as untrusted data because findings quote the audited file.
Its complete contract is
[`skills/lintlang-audit/SKILL.md`](skills/lintlang-audit/SKILL.md).

A scannable input exits 0 whatever its verdict unless a gate is requested;
an uninspectable input exits 1. The skill reads the verdict from output, never
infers it from the exit status, and does not silently rewrite the input.

## Automatic hook behavior and limits

After a successful `Write` or `Edit` on a supported language-bearing file, the
hook returns concise repair context. Clean or unsupported files add no context.
Supported extensions are `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.prompt`, and
`.py`. The hook omits raw prompt `evidence` and returns finding descriptions and
repair suggestions. Those diagnostics can still be source-derived; omitting an
evidence field does not promise that no source-derived text reaches the host.

The scanner itself makes no model or network calls. Claude Code's provider and
network behavior is separate. Neither hook feedback nor a clean scan certifies
agent safety; use the [GitHub guide](../../docs/github.md) for an explicit CI gate.

## Troubleshooting and removal

For a missing runner, check `lintlang --version` in the environment that launches
Claude Code. Confirm `PATH`, or availability of uvx for the skill's fallback.
For missing automatic guidance, confirm the plugin is enabled and that a
successful supported edit occurred; a named-file audit and a post-edit hook
have different triggers. No guidance on a clean or unsupported input is expected,
not evidence that every configuration structure was analyzed.

Use the `/plugin` menu or these commands to remove only this integration:

```bash
claude plugin disable lintlang@lintlang     # keep installed, stop both surfaces
claude plugin uninstall lintlang@lintlang   # remove the plugin
claude plugin marketplace remove lintlang   # remove its catalog entry
```

Related: [integrations](../../docs/integrations.md),
[technical reference](../../llms-full.txt), [README](../../README.md).
