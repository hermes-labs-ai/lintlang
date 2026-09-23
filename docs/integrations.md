# Integrations and ecosystem

Choose where to run the same static checks: local review, a commit/CI gate, or
bounded feedback inside an agent host. Scanning `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`, or Copilot instructions with the CLI does not install a native
plugin, validate every host-specific setting, or establish provider compatibility.

## Choose a workflow

| Integration/workflow | Trigger | Prerequisite | Advisory or blocking | Setup and limits |
| --- | --- | --- | --- | --- |
| GitHub Actions | Pull request or configured CI event | Actions enabled; committed input path | Action defaults to blocking HIGH/CRITICAL | [GitHub guide](github.md) |
| GitHub Code Scanning | SARIF upload after a scan | Eligible repository, feature enabled, upload permissions | Scan gate and upload outcome are separate | [Code scanning](github.md#code-scanning) |
| pre-commit | Commit hook or explicit run | pre-commit and a configured input path | Advisory by default; opt-in severity gate | [pre-commit setup](#pre-commit) |
| Claude Code | Supported `Write`/`Edit`; named-file audit on request | Claude Code plugin support; scanner runner | Non-blocking guidance; no file rewriting | [Claude Code guide](../integrations/claude-code/README.md) |
| Cursor | Named-file audit on request | Cursor marketplace plugin support; scanner runner | Advisory verdict; no file rewriting | [Cursor setup](../integrations/claude-code/README.md#use-in-cursor) |
| GitHub Copilot CLI | Named-file audit on request | Copilot CLI plugin support; scanner runner | Advisory verdict; no file rewriting | [Copilot CLI guide](../integrations/copilot-cli/README.md) |
| Pi | Named-file scan on request | Pi skill support; installed scanner on PATH | Advisory verdict; no file rewriting | [Pi skill](../skills/lintlang/SKILL.md) |
| Gemini CLI | Successful `write_file` or `replace` | Configured Gemini CLI, uv, installed extension source | Non-blocking guidance; no file rewriting | [Gemini extension](gemini-cli-extension.md) |
| OpenCode | Supported post-edit event with an explicit changed path | Documented legacy host contract and scanner on PATH | Non-blocking guidance; no file rewriting | [OpenCode guide](../integrations/opencode/README.md) |
| Hermes Agent | First coding-turn `pre_verify` attempt | Plugin-capable host; LintLang in its Python environment | One continuation for eligible FAIL/ERROR inputs | [Hermes Agent setup](#hermes-agent) |
| MegaLinter | Existing MegaLinter run | External descriptor and `AI_LINTLANG` enabled | FAIL blocks; REVIEW is advisory | [MegaLinter guide](../mega-linter-plugin-lintlang/README.md) |

The CLI itself reports findings without blocking unless a threshold is requested;
input errors remain nonzero. Host hooks are not a substitute for a CI gate.
The scanner makes no model or network calls during a scan, but installation can
download dependencies and host applications retain their own provider/network
behavior. Diagnostics returned to a host are not a promise that source-derived
text never leaves that host.

## GitHub CI and Code Scanning

From the repository root, generate a pinned workflow for a known path:

```bash
lintlang init --github --path AGENTS.md
```

Use the [GitHub guide](github.md) for path detection, overwrite protection,
thresholds, SARIF, permissions, and fork restrictions. The maintained complete
workflow lives in [the canonical example](../examples/github-code-scanning.yml).
For an existing backlog, review [baseline adoption](baselines.md) before enabling
a stricter gate.

## pre-commit

Add this entry to the `repos` list in `.pre-commit-config.yaml`, preserving any
other hooks:

```yaml
repos:
  - repo: https://github.com/hermes-labs-ai/lintlang
    rev: v0.7.1
    hooks:
      - id: lintlang
```

Then install and exercise the hook:

```bash
pre-commit install
pre-commit run lintlang
pre-commit run lintlang --all-files
```

The hook natively selects pre-commit's own changed-file list, filtered to a
conservative `files:` regex that matches only recognized agent-instruction
paths: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or `SKILL.md` at any depth;
`agent.yaml`/`.yml`/`.json`; `.github/copilot-instructions.md`; and
`*.instructions.md` under `.github/instructions/`. It runs — and scans every changed file that
matches — only when a commit or `--all-files` touches one of those paths; it
does not run unconditionally on unrelated commits, and it does not need a
configured path for that default behavior.

An explicit `args:` entry is optional, and it is not a way to override the
hook's selection. pre-commit appends the changed
filenames *after* `args`, so adding a path there does not replace the hook's
selection — it scans that path **in addition to** each changed file, and a
flag placed after a path still applies to the whole invocation. To pin
the hook to one fixed path regardless of what changed, set all three
settings, which is useful when your repository's canonical instructions live
somewhere the `files:` regex does not match:

```yaml
hooks:
  - id: lintlang
    args: [AGENTS.md]
    pass_filenames: false
    always_run: true
```

Findings are advisory by default: **a FAIL verdict does not block the
commit.** Without `--fail-on`, the scan prints the verdict and its findings
and exits 0 whatever it found, so pre-commit records the hook as passed and
the commit proceeds. Only an input error — a missing, unreadable, or
unparseable file — is nonzero without that flag. A hook that prints `FAIL`
and lets the commit through is configured, not broken.

To block HIGH or CRITICAL findings, add a
`--fail-on` argument. On the default changed-file hook, pass only the flag,
since the filenames arrive on their own:

```yaml
args: [--fail-on, fail]
```

On a pinned single-path hook like the one above, keep the explicit path
first:

```yaml
args: [AGENTS.md, --fail-on, fail]
```

Use `review` instead of `fail` to include MEDIUM findings. Configured input
errors remain blocking either way. The [baseline guide](baselines.md) explains
how to acknowledge an existing backlog without broad rule suppression.

When a hook appears not to run, check that pre-commit is installed for this
checkout and run it explicitly. Reproduce a finding with the same standalone
CLI path and flags. To remove this integration, remove only the LintLang entry
from `.pre-commit-config.yaml`; do not uninstall other hooks that the repository
still uses.

## Native host integrations

Install the native integration only when you want feedback inside that host.
The linked guides own their installation commands, payload boundaries,
verification, and removal; scanning a host's Markdown instruction file requires
none of these plugins.

The [Claude Code plugin](../integrations/claude-code/README.md) has two distinct
surfaces: an on-demand `lintlang-audit` skill for a named file and an automatic
`PostToolUse` hook for supported edits. The
[Cursor marketplace package](../integrations/claude-code/README.md#use-in-cursor)
exposes that portable audit skill on request. The
[GitHub Copilot CLI plugin](../integrations/copilot-cli/README.md) provides an
on-demand `lintlang-audit` skill for a named file. The
[Pi skill](../skills/lintlang/SKILL.md) invokes an installed scanner for a
selected file. The
[Gemini extension](gemini-cli-extension.md) runs bundled source in an isolated uv
environment; its recorded installation remains LintLang 0.5.3 with Gemini CLI
0.32.1. That historical tested pair is not a pin to bulk-update with the package.

The [OpenCode adapter](../integrations/opencode/README.md) targets the documented
`1.18.27` legacy `tool.execute.after` contract. It needs an explicit changed-file
path in arguments or metadata and does not infer a path hidden inside patch
text. Published type-contract evidence is not a live-host compatibility claim
for every release.

## Hermes Agent

Install LintLang with the Python interpreter for the environment that runs
Hermes Agent, then check plugin discovery:

```bash
python -m pip install lintlang==0.7.1
hermes plugins list
```

The package registers the `hermes_agent.plugins` entry point. An isolated
installation in some other Python environment does not make that entry point
available to the host. This route requires a host supporting the documented
`pre_verify` hook; it is not a claim about all Hermes Agent releases.

The hook checks existing changed files whose names or locations identify agent
instructions, prompts, skills, tools, or agent configuration. It is not a scan of
every changed source file. It runs only for a coding turn's first verification
attempt. PASS and REVIEW do not interrupt that turn; FAIL or ERROR on an eligible
file requests one continuation with a reproduction command. Later attempts do
not repeatedly hold the turn open.

For a missing plugin, check the host's actual Python environment and entry-point
discovery before changing scan rules. For a reported issue, run
`lintlang scan <path> --fail-on fail` on the named input. Use the host's plugin
controls to disable only LintLang, or uninstall LintLang from that environment
when it is no longer used. The implementation boundary is recorded in
[the adapter](../src/lintlang/integrations/hermes_agent.py) and
[its tests](../tests/test_hermes_agent_integration.py).

## MegaLinter

The external plugin is opt-in for an existing MegaLinter installation. Add its
descriptor and `AI_LINTLANG` to your existing configuration as shown in the
[MegaLinter guide](../mega-linter-plugin-lintlang/README.md). The guide owns default
filename selection, deliberate scope overrides, runtime package installation,
and failure behavior. Its in-process tests and recorded real-container trials
are separate evidence; neither establishes runtime agent correctness.

## Public ecosystem references

These are observations of public artifacts, checked on 18 September 2026. Usage,
packaging, and catalog entries are different kinds of evidence. None is an
endorsement, an accuracy measurement, or a claim of broad production adoption.
Historical third-party pins are evidence of those artifacts, not installation
recommendations for the current package.

| Public source | Observed evidence | Boundary |
| --- | --- | --- |
| Character.AI Larch [CI requirements](https://github.com/character-ai/larch/blob/ef7ee4b7f946f29fa51981f5422a1a93e83c79a7/.github/workflows/requirements-agent-linters.txt) and [linting reference](https://github.com/character-ai/larch/blob/210d08a8f6c1b0dd14c27b709c66471bd31a5636/docs/linting.md) | Pins `lintlang==0.3.1`; documents recurring agent-instruction CI with a HIGH/CRITICAL gate | Public repository usage, not an organization-wide deployment claim |
| MegaLinter [plugin catalog](https://github.com/oxsecurity/megalinter/blob/baf2c7a3432b670096a293dc7512848b5e5db349/docs/plugins.md) | Lists the LintLang external plugin as `AI_LINTLANG` | Catalog inclusion, not a built-in default or endorsement |
| [Awesome Gemini CLI](https://github.com/Piebald-AI/awesome-gemini-cli/blob/19ee73879458321ea19803d5349bc1341a972eff/README.md) | Lists LintLang and its Gemini CLI extension | Discovery listing, not additional host verification |
| [Best of Python Dev](https://github.com/ml-tooling/best-of-python-dev/blob/71e4fe7dbc62d3f6fa2ed5ef7f43245fb5f15349/projects.yaml) | Includes LintLang in its linter catalog | Catalog record, not evidence of detector quality |
| [Awesome Hermes Skills](https://github.com/ZeroPointRepo/awesome-hermes-skills/blob/786e092c02e428a09aff61b0381fc11395b7e0a0/README.md) | Includes a LintLang reference | Community listing, separate from the native hook contract above |
| [Haven overlay metadata](https://github.com/thehaven/haven-overlay/blob/d052d950b05389fcd7c8f22939033319a5aec348/dev-util/lintlang/metadata.xml) | Package metadata names this repository as upstream | An unofficial Gentoo overlay, not official Gentoo distribution support |

Research provenance is a separate question; see [Research and design lineage](research.md).
For detector behavior and machine-readable contracts, use the
[technical reference](../llms-full.txt). Return to the [README](../README.md) for
product scope and the main documentation index.
