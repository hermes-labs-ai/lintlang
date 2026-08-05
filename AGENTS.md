# AGENTS.md

`lintlang` is a static linter for AI agent configs, tool definitions, and system prompts.

## Workspace identity

- The canonical upstream is `https://github.com/hermes-labs-ai/lintlang.git`.
- Treat `git worktree list` as the authority for active linked worktrees.
- Never assume the checked-out local branch matches public `origin/main`; verify the remote, branch, status, and intended base before editing.
- Maintainers: `WORKSPACE.md` in the git checkout records which local clone is
  canonical. It is not part of the published package and is not needed to work
  on the code.

## Use it for

- linting tool descriptions before agents start choosing the wrong tools
- checking prompts and configs for missing constraints, schema mismatches, and role confusion
- running a zero-LLM CI gate over YAML, JSON, prompt text, and Python source files
- scanning `.py` files to find embedded prompts and uncalibrated thresholds (P1/P2 detectors)
- preflighting one present instruction plus explicit typed context before a host sends it

## Do not use it for

- runtime evaluation
- dynamic agent testing
- proving an agent is safe in production
- retrieving preferences from history, deciding truth, or silently rewriting/sending prompts

## Minimal commands

```bash
pip install -e ".[dev]"
lintlang --help
lintlang scan samples/bad_tool_descriptions.yaml
printf '%s' 'Is it true that X?' | lintlang preflight - --format json
pytest -q
ruff check src/ tests/
```

## Output shape

- repository scan outcomes: `ERROR`, `PASS`, `REVIEW`, or `FAIL`
- structural findings by pattern `H1` through `H7`, plus Python pipeline findings `P1` and `P2`
- JSON output for CI via `--format json`
- preflight states: `ALLOW`, `NOTICE`, `HOLD`, `UNAVAILABLE`, or `ERROR`
- preflight evidence uses exact code-point spans and stable `PF001`-`PF005` IDs

## Success means

- the same config file produces the same verdict and findings
- scan output points to concrete locations and rewrite guidance
- tests and sample self-scan pass offline
- unavailable preflight coverage is explicit and default output contains no raw prompt/context/patch text

## Common failure cases

- users expect lintlang to judge runtime model behavior
- configs are syntactically valid but still underspecified for their intended use
- teams gate only on syntax and do not review language-level instruction risks

## Maintainer notes

- keep detector language aligned with the exact patterns exercised by the samples
- keep CLI examples and severity semantics aligned with README
- keep the tool fully offline and deterministic
- keep repository `scan` and in-flight `preflight` result types and exit semantics separate
- keep heuristic preflight findings notice-only; only exact contract/conflict rules may hold
