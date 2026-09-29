# Real-world examples

Five worked examples, each a directory with stable paths, so any of them can be linked on its own. Every example has `commands.txt` (the exact `lintlang` invocations), `expected-output.txt` (combined output and exit code, captured with lintlang 0.8.1) and a `README.md` (the job it models, where the input came from, and what the scan cannot tell you). `tests/test_real_world_examples.py` re-runs every `commands.txt` and compares the result to `expected-output.txt`.

| Example | Input | Shows |
| --- | --- | --- |
| [openrouter-skill-benchmarks](openrouter-skill-benchmarks/) | A published `SKILL.md`, pinned by commit | A clean PASS with one LOW finding on a real skill file |
| [okta-tool-manifest](okta-tool-manifest/) | A 108-tool MCP manifest | A HIGH H1.2 and two MEDIUM H1.6 findings with file and line locations |
| [skill-empty-description](skill-empty-description/) | A `SKILL.md` with an empty `description:` | HIGH H1.1, the exit code, and the one-line fix |
| [ci-gate-exit-codes](ci-gate-exit-codes/) | The two examples above plus an unreadable manifest | What `--fail-on` does to the exit code, and why an input error is never a pass |
| [baseline-tool-manifest](baseline-tool-manifest/) | A 15-tool MCP manifest | Adopting a gate on existing findings with `--write-baseline` and `--baseline` |

Third-party inputs are listed with their commit, path, license and sha256 in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Refresh the transcripts after an intentional output change with `python tests/test_real_world_examples.py --regenerate`, then read the diff.

A clean scan in any of these examples reports what selected checks found in recognized content. It is not evidence that a tool or skill is correct or safe.
