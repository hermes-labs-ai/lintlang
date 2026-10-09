# LintLang for Claude Code

![LintLang logo](assets/lintlang-mark.svg)

LintLang scans and lints the interfaces AI agents use: instructions and system
prompts, MCP and function-tool definitions, parameter schemas, and supported
agent configuration files. It finds ambiguous tool choices, missing bounds,
schema gaps, and other inspectable setup defects using local, deterministic
static analysis. In Claude Code, ask it to audit a named file or receive concise,
advisory repair guidance after supported edits.

The plugin combines an on-demand audit skill with a post-edit advisory hook.
Findings identify patterns such as ambiguous tool descriptions, missing stop
conditions, and schema gaps. Neither component rewrites a file or blocks a
tool call. LintLang is developed by [Hermes Labs](https://hermes-labs.ai/).

| Surface | Hosts | Runs | Scope |
| --- | --- | --- | --- |
| `lintlang-audit` skill | Agent Plugins hosts, including Cursor; Claude Code | When you ask for an audit | The file you name |
| `PostToolUse` adapter | Claude Code only | After supported `Write` or `Edit` | The file just changed |

The skill is not the hook. Disabling one does not disable the other; installing
the plugin provides both. Scanning `CLAUDE.md` with the standalone CLI does not
require installing this plugin.

## Prerequisites

**Unpublished 0.9.0 candidate:** install from this private checkout with
`python -m pip install .` and use its `lintlang` executable for local validation.
The registry commands below are draft release examples; use them after publication.

Use Claude Code with plugin support. After publication, install the pinned
scanner with Python 3.10+ so `lintlang` is on the host's `PATH`:

```bash
pipx install lintlang==0.9.0
lintlang --version
```

The hook prefers the installed executable and accepts version 0.9.0 or newer.
It falls back to the installed Python module and runs from its own handler
directory, keeping the edited project's directory off the resolver's import
path. On Python 3.11+, it also uses `-P` and `PYTHONSAFEPATH`. The skill prefers
the same executable
and otherwise runs the pinned release through `uvx --from lintlang==0.9.0`.
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

Three example requests, using files that exist in your project:

| Request | What LintLang inspects |
| --- | --- |
| `audit AGENTS.md with lintlang` | Agent instructions: missing bounds, unclear priorities, and supported language patterns. |
| `audit mcp-tools.json with lintlang` | Saved MCP tool definitions or a `tools/list` response: tool descriptions, selection boundaries, and parameter schemas. |
| `audit pipeline.py with lintlang` | Supported embedded prompts, literal tool definitions, and pipeline thresholds extracted from Python source. |

LintLang does not connect to a live MCP server to discover its tools. A
launch-only server configuration contains no tool definitions to inspect;
provide definitions or a saved response instead.

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

## Data handling

LintLang reads the files you ask it to audit, or the supported file Claude Code
just changed. The scanner makes no model calls, sends no telemetry, and makes
no network requests during a scan. This plugin creates no audit database and
does not retain file contents or findings itself.

The Python hook inherits the local process environment to launch the installed
scanner. LintLang does not send that environment off the machine.

The audit skill returns findings to the conversation. The hook returns concise
diagnostics to Claude Code; these can contain source-derived names or fragments
even though raw evidence is omitted. Claude Code's provider, conversation
storage, and network behavior are separate. No account, API key, or remote
connector is required by LintLang. The optional pinned uvx fallback can download
LintLang and its dependencies from the package registry before scanning.

Neither hook feedback nor a clean scan certifies agent safety. Use the
[GitHub guide](https://github.com/hermes-labs-ai/lintlang/blob/main/docs/github.md)
for an explicit CI gate.

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

For help or a reproducible false positive, open a
[GitHub issue](https://github.com/hermes-labs-ai/lintlang/issues) with the
LintLang version, invocation, and a minimal redacted example. Report security
issues through the
[security policy](https://github.com/hermes-labs-ai/lintlang/blob/main/SECURITY.md).

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

Then ask Cursor to `audit AGENTS.md with lintlang`. The Cursor manifest points
at the skill directory and explicitly disables hook discovery, so the shared
Claude-specific `PostToolUse` adapter does not run in Cursor. The Cursor
integration provides on-demand audits only.

Related: [integrations](https://github.com/hermes-labs-ai/lintlang/blob/main/docs/integrations.md),
[technical reference](https://github.com/hermes-labs-ai/lintlang/blob/main/llms-full.txt),
[project README](https://github.com/hermes-labs-ai/lintlang/blob/main/README.md).
