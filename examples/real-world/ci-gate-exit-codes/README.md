# CI gate exit codes

## What real job this models

A pull request check runs `lintlang scan ... --fail-on <level>` and blocks the merge on a nonzero exit. This example shows what each gate does on real inputs. Six commands, all in [commands.txt](commands.txt), with output and exit codes in [expected-output.txt](expected-output.txt).

| Command (abridged) | Result | Exit |
| --- | --- | --- |
| Okta manifest, `--min-severity high --fail-on fail` | HIGH finding trips the gate | 1 |
| Okta manifest, `--patterns H1 --fail-on review` | MEDIUM findings trip the stricter gate | 1 |
| broken SKILL.md, `--fail-on fail` | `H1.1` HIGH trips the gate | 1 |
| fixed SKILL.md, `--fail-on fail` | `PASS — 0 findings` | 0 |
| unreadable manifest, `--fail-on fail` | `ERROR`: input error | 1 |
| unreadable manifest, `--allow-uninspected --fail-on fail` | `SKIPPED — nothing inspected (this is not a PASS)` | 0 |

`--fail-on fail` blocks HIGH and CRITICAL findings; `--fail-on review` also blocks MEDIUM. Without a gate, every scan above would exit `0`.

The last two rows use `input-unrecognized-shape.json`, a real registry file that lists its parameters under `arguments` instead of `inputSchema`, `input_schema` or `parameters`. LintLang found a named, described object it could not read as a tool and refused to call that a pass. Passing `--allow-uninspected` turns the error into an explicit `SKIPPED` that also exits `0`. Use it only when uninspected files are expected, because it lets a file through that no rule looked at.

## Provenance

- `input-unrecognized-shape.json`: <https://github.com/docker/mcp-registry> (MIT), commit `49b643ce3fc73e6ee80bb962719b6e2990e3d397`, file `servers/astro-docs/tools.json`, copied unchanged. sha256 `9756a1e9176917945823cbd2c8d5eb763b4c83e6257235a369474cf079919f33`.
- The other inputs are the ones in [okta-tool-manifest](../okta-tool-manifest/) and [skill-empty-description](../skill-empty-description/). Those commands run from this directory, so their paths start with `../`.

## What this does not tell you

- The exit code reports which gate the findings crossed. It does not rank findings by real-world harm.
- A zero exit on the fixed skill means no selected check fired. It does not mean the skill was reviewed.
- The unreadable file may be a perfectly good tool list for the host that reads it. The error means lintlang does not recognize that shape, not that the file is wrong.
