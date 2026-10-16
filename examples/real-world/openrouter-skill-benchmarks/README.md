# A published SKILL.md scan

## What real job this models

A team keeps agent skills in a repository and wants to know whether the `SKILL.md` files pass a static check before merge. This example scans one file from a public skill collection, `openrouter-benchmarks`, and reads the result.

```bash
lintlang scan input/SKILL.md
```

Result: `PASS — 1 LOW`, exit `0`. The single finding is H5 on line 26 (`when relevant` in a table row), a suggestion to state the exact condition. Front matter and body were both inspected (74 lines). See [expected-output.txt](expected-output.txt) for the exact text.

In the same commit, all 19 `SKILL.md` files in the repository scanned as `PASS`. Eighteen reported no findings and this one reported the LOW finding above.

## Provenance

- Repository: <https://github.com/OpenRouterTeam/skills>
- Commit: `33597a44e38b0cdc38ea1256ef8bcf50c2704e3d`
- File: `skills/openrouter-benchmarks/SKILL.md`
- sha256: `6bfc172fe75e95c9b2f9df0510d61f5913663e123f70ae4d94e351a9401940fd`
- License: none declared in that repository, so the file is not copied into this one.

Fetch it and reproduce:

```bash
mkdir -p input
curl -sSL https://raw.githubusercontent.com/OpenRouterTeam/skills/33597a44e38b0cdc38ea1256ef8bcf50c2704e3d/skills/openrouter-benchmarks/SKILL.md -o input/SKILL.md
shasum -a 256 input/SKILL.md
lintlang scan input/SKILL.md
```

`input/` is git-ignored here. `tests/test_real_world_examples.py` compares the output only when that file is present and otherwise skips this example.

## What this does not tell you

- It does not say the skill works, that its description makes a host load it at the right moment, or that the API it documents behaves as written. There is no runtime evaluation.
- `PASS` is a verdict on recognized content only. The coverage line reads `Confidence: LOW (65% coverage proxy)` because the file has no prompt-like framing or input-boundary language. That label is a heuristic about coverage, not a probability that the file is good or bad.
- The result is for the pinned commit and lintlang 0.8.1. A later commit of the skill or a later lintlang release can differ.
