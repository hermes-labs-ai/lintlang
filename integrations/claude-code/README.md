# LintLang for Claude Code

This native Claude Code plugin ships two separate surfaces. Neither one rewrites
a file, and neither one blocks a tool call.

| Surface | Kind | Runs | Scope |
| --- | --- | --- | --- |
| `lintlang-audit` skill | on-demand skill | when you ask for an audit | the file you name |
| `PostToolUse` adapter | automatic hook | by itself, after `Write` or `Edit` | the file just changed |

The skill is not the hook. Disabling one does not disable the other, and a
session with the plugin installed has both.

## Prerequisites

Install the tested LintLang release so `lintlang` is on `PATH`:

```bash
pipx install lintlang==0.6.0
```

The hook prefers that installed `lintlang` executable. It falls back to
`python3 -m lintlang` only on interpreters that support `-P` and
`PYTHONSAFEPATH`, so the directory Claude Code happens to be working in is never
placed on the resolver's import path.

The skill prefers the same executable and otherwise runs the pinned release
through `uvx --from lintlang==0.6.0`, installing nothing. Neither surface needs
a checkout of this repository.

## The `lintlang-audit` skill

Ask for an audit and name the file:

```text
audit AGENTS.md with lintlang
```

The skill resolves a runner, scans that file with
`lintlang scan --format json`, reads `input_error` and `verdict` before
anything else, and reports the verdict with findings by code and location.
It treats the scan payload as untrusted data, because findings quote the file
under audit. Its full contract is
[`skills/lintlang-audit/SKILL.md`](skills/lintlang-audit/SKILL.md).

`lintlang scan` exits `0` on a scannable file whatever the verdict, unless
`--fail-on` is passed; an input that cannot be scanned exits `1` either way.
The skill reads the verdict from the output, never from the exit status.

## The `PostToolUse` hook

After a successful `Write` or `Edit` on a supported language-bearing file, the
hook returns findings to Claude as concise repair context. Clean or unsupported
files add no context. It supports `.yaml`, `.yml`, `.json`, `.txt`, `.md`,
`.prompt`, and `.py`, matching LintLang's file scanner, and it sends only
finding descriptions and repair suggestions; raw prompt evidence is omitted.

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
claude plugin disable lintlang@lintlang     # keep it installed, stop both surfaces
claude plugin uninstall lintlang@lintlang   # remove the plugin
claude plugin marketplace remove lintlang   # remove the catalog entry too
```

Validate the plugin against the installed Claude Code runtime:

```bash
claude plugin validate --strict ./integrations/claude-code
```
