# A SKILL.md with an empty description

## What real job this models

A repository lints its `SKILL.md` files in CI with `lintlang scan --discover . --fail-on fail`. A contributor adds a skill whose front matter has `name:` but an empty `description:`. The description is the text a host shows a model when it decides whether to load the skill, so a skill without one gives the model nothing to decide on.

```bash
lintlang scan broken/release-notes-drafter/SKILL.md --fail-on fail   # exit 1
lintlang scan fixed/release-notes-drafter/SKILL.md --fail-on fail    # exit 0
```

The broken file reports `FAIL — 1 HIGH`: `H1.1` at line 3, `frontmatter.description`. Without `--fail-on` the same scan exits `0`, because reporting and gating are separate. The fix is one line: say what the skill does and when to use it. The fixed file reports `PASS — 0 findings`. See [expected-output.txt](expected-output.txt).

## Provenance

The two skill files were written for this repository. They are a minimal reproduction and not a copy of any public skill. The shape matches the fixture `samples/frontmatter-boundary/missing-description/SKILL.md` in this repository. All 19 `SKILL.md` files in OpenRouterTeam/skills at commit `33597a44e38b0cdc38ea1256ef8bcf50c2704e3d` have descriptions, so no public file was available to use as the failing input. The directory name matches the skill `name` because lintlang checks that too (H1.9).

## What this does not tell you

- It checks that a description exists and how it is phrased. It does not tell you whether a host will load the skill at the right time.
- The fixed description passes because it is present and states a purpose and a trigger. A vague but non-empty description could pass too.
- `PASS` here still carries `Confidence: LOW (65% coverage proxy)`, a heuristic about how much prompt-like structure the file has.
