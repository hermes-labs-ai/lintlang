# Changelog

## Unreleased

### Added

- On-demand `lintlang-audit` skill in the Claude Code plugin
  (`integrations/claude-code/skills/lintlang-audit/`), plugin version `0.2.0`.
  It audits the file a user names, resolving the released CLI from `PATH` or
  through `uvx --from lintlang==0.6.0`, so it needs no checkout of this
  repository. Previously the plugin shipped only the automatic `PostToolUse`
  hook, which covers just the file Claude Code has already changed; there was
  no way to ask for an audit. The two surfaces are separate: the skill is not
  a hook, and the plugin README and manifest descriptions now say so.
- `lintlang scan --discover [ROOT]` opts in to repository discovery of
  recognized agent-instruction files anywhere under `ROOT` (default `.`):
  `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `SKILL.md`, `agent.yaml`/`.yml`/
  `.json`, `.github/copilot-instructions.md`, and `*.instructions.md` under
  `.github/instructions/`, matched case-sensitively at any depth — that
  directory's documented spelling, so a README or a scratch note kept beside
  the real instruction files is not scanned as one. Editor and host layouts
  (`.cursor/rules`, `.claude/agents`, `.windsurfrules`) are known omissions,
  not discovery targets; pass such a file as an explicit argument. Symlinks
  are not followed, as in a directory scan, but a recognized instruction file
  skipped for that reason is now named on stderr instead of silently dropping
  out of the scanned set; an excluded one is not reported. Explicit
  file arguments remain canonical; `--discover` unions its discovered set
  with them, deduplicated. `--exclude` globs and a repository's
  `.lintlangignore` filter discovered files exactly as they filter a directory
  scan, so a repository that keeps deliberately broken instruction fixtures can
  keep them out of its own repository-mode gate. Generic directory scanning
  (`lintlang scan <dir>`) is unchanged and keeps its own broader,
  extension-based sweep.
- `lintlang scan - --stdin-filename <virtual-path>` scans exactly one document
  from standard input. The virtual path drives parsing (including `.py` AST
  extraction), reported locations, JSON/SARIF identity, and baseline matching;
  the path itself is never opened. `-` without `--stdin-filename`, more than
  one `-`, `--stdin-filename` without a `-` input, and `-` combined with
  `--discover` are all rejected with a usage error (exit 2). One invocation
  takes one unambiguous source of files: a generator scans what it generated, a
  repository gate scans the repository. Released 0.6.0 rejected a bare `-` as a
  missing file (exit 1), so a wrapper that branches on that exit code sees 2
  instead.
- `lintlang init --github` also recognizes a root `SKILL.md` as an automatic
  candidate, checked last in the existing detection order so no previously
  auto-selected repository changes which file it picks. An explicit `--path`
  still wins over every candidate.

### Changed

- **A scan that inspects zero files is an input/coverage error on every
  channel.** Released 0.6.0 already exited 1 for it and said so on stderr
  (`Error: No files were successfully scanned.`) and in SARIF, which reported
  `executionSuccessful: false` with an `LL_INPUT_ERROR` notification but no
  `ERROR` result; JSON alone still printed `[]`, so the JSON report
  contradicted the process status. The scan now exits 1 with a matching
  `ERROR` result on every output channel (terminal, JSON, SARIF). New
  `--allow-empty` is the opt-out for a caller that intentionally scans an
  input that may sometimes be empty: it exits 0 with a stderr note, `[]` for
  JSON, and an empty SARIF run reporting `executionSuccessful: true`. Report
  and exit status now agree in both directions. An interim change on `main`
  after the 0.6.0 tag made a zero-file scan exit 0; it was never released, so
  no published version behaved that way and an upgrade from 0.6.0 sees only
  the added channels and the new flag. The first-party GitHub Action runs the
  same CLI over its `path` input, so a path that inspects zero files now fails
  the step with exit 1; the Action exposes no input that forwards
  `--allow-empty`, so a workflow that needs the opt-out has to call the CLI
  directly. `--write-baseline`'s pre-existing empty-scan error, which already
  refused to write a baseline, is unchanged.
- **Breaking: the pre-commit hook now consumes pre-commit's own changed-file
  selection instead of a hard-coded path.** `args: [AGENTS.md]`,
  `pass_filenames: false`, and `always_run: true` are gone from
  `.pre-commit-hooks.yaml`; the hook now declares a conservative `files:`
  regex matching exactly the recognized instruction set above, so it fires
  only on changed files that are themselves agent instructions, across
  however many such files changed in one commit. A repository that relied on
  the hook always running regardless of which files changed should instead
  run `pre-commit run lintlang --all-files`. Reproducing the exact old
  single-path behavior takes all three settings in its own
  `.pre-commit-config.yaml` — `args: [AGENTS.md]`, `pass_filenames: false`,
  and `always_run: true` — because pre-commit appends the changed filenames
  after `args`, so `args:` alone adds a fixed path rather than replacing the
  selection. The pre-commit guide now states that consequence and the
  advisory default it sits next to: without `--fail-on`, a FAIL verdict does
  not block the commit, because the scan exits 0 whatever it found and only
  an input error is nonzero.
- **Behavior change: `--exclude` and `.lintlangignore` globs are now anchored
  and translated correctly.** The previous translator rewrote the pattern by
  sequential string replacement and matched it unanchored, with two
  consequences: `**/` became a mandatory rather than an optional path segment,
  so `**/*.md` matched `docs/a.md` but not a root-level `a.md`; and any
  pattern matched anywhere in a path, so `docs/**` also excluded
  `notdocs/a.md` and `*.md` also excluded `myfoo.md.bak`. Both are fixed.
  Following gitignore, a pattern containing no `/` still matches at any depth,
  so `CHANGELOG.md` and `*.md` keep excluding nested files. A repository whose
  exclusion happened to depend on the over-broad matching will now scan those
  previously skipped files. The same translator backs `--discover` filtering.
- H5's per-negative-instruction LOW notices
  (`Negative instruction '…' could be reframed positively.`) are removed. The
  aggregated MEDIUM density finding for a prompt with many instructions and no
  explicit priority ordering is unchanged.

### Fixed

- **Verdict change, in both directions.** H2 no longer reports an
  unbounded-behavior phrase that the prompt forbids. `Do not continue
  indefinitely; stop at the first terminal result.` was reported as
  `Unbounded continuation` (CRITICAL) and scanned FAIL; it now carries no H2
  finding. One guard covers every H2 unbounded-behavior phrase (`keep trying
  until`, `retry until`, `loop until`, `loop over` / `loop through`,
  `continue until` / `continue indefinitely`). The negator (`never`, `do not`,
  `don't`, `should not`, `must not`, their contractions, and `cannot` /
  `can't` after a subject) must sit directly on the phrase, with at most two
  adverbs from a closed list between them. A file whose only CRITICAL findings
  were such prohibitions now scans REVIEW or PASS. The guard replaces the
  narrower negation check that `retry until` has had since 0.6.0 and is
  stricter than it: a `never retry until …` that carries a trailing condition
  (`unless`, `if`, `when`, `except`), is asked as a question, is doubly
  negated, or is split from the phrase by a tab or a blank line is now
  reported where 0.6.0 was silent, so a file relying on one of those forms
  can move to FAIL. An interrupted or delegated prohibition (`Do not, under
  any circumstances, …`, `Do not let the agent …`) is still reported; put the
  negator directly on the phrase. A stop condition in a clause coordinated
  after the prohibition — `Do not continue indefinitely and stop when the queue
  drains.` — does not make the prohibition conditional, so the corrected
  wording a user writes after being flagged is not flagged again; a condition
  attached to the forbidden behaviour itself (`Do not keep trying until it
  works when the credentials are wrong.`) still is. The guard reads the
  negator's own clause: to its left a comma opens that clause only when it
  closes a fronted condition (`When the push fails, do not retry until …`) or
  starts a coordinated one (`…, and do not retry until success`), so a
  parenthetical or a complement cannot hide an earlier negative
  (`It is not true, however, that you must never retry until it works.` is
  reported); an earlier negative counts with or without its apostrophe (`wont`
  as well as `won't`); and a condition introduced after the phrase
  (`…, if the queue is non-empty`) defeats the prohibition exactly as an
  unpunctuated one does, whether the condition is introduced by a comma, a
  dash, or a parenthesis (`Do not retry until it works (if the queue is
  non-empty).` is reported, as its comma form is). A parenthesis that opens
  anything other than an `if` / `when` / `whenever` condition is an aside or
  the author's own bound and leaves the prohibition whole
  (`Do not retry indefinitely (see the runbook).`,
  `Do not continue indefinitely (stop after ten items).`). Only a *trailing*
  condition does this. A condition **fronted** before the negator is read as
  closing its own clause, so the prohibition stays whole and H2 stays silent:
  `If the queue is non-empty, do not retry until it works.` and
  `When the queue is non-empty, do not continue indefinitely.` carry no H2
  finding, while the same conditions placed after the phrase are reported. This
  asymmetry is a known limitation rather than a judgement that a fronted
  condition bounds the behaviour, and a test asserts the behaviour H2 should
  have and is expected to fail until it does. It is
  also a verdict change relative to 0.6.0 in the silent direction:
  `When the queue is non-empty, do not continue indefinitely.` was CRITICAL in
  released 0.6.0 and now reports nothing, so a file relying on that form to
  fail a gate can move from FAIL to REVIEW or PASS. A second known limitation
  sits next to it: a trailing condition is only recognized when its `if` /
  `when` / `whenever` is the first word after the comma, dash, or parenthesis,
  so a modifier in front of it (`Do not retry until it works, only if the
  queue is non-empty.`) hides the condition and the prohibition is read as a
  bound, and a test asserts the behaviour H2 should have there too. Finding
  descriptions and evidence text are unchanged, so existing baseline entries
  still match.
- **Verdict change carried over from unreleased work after the 0.6.0 tag.** H2
  no longer reports a `loop over` / `loop through` traversal that carries no
  indefinite-continuation word: `Loop through all search results and analyze
  each one.` was CRITICAL in released 0.6.0 and now reports nothing, while
  `Loop over the queue indefinitely.` is still CRITICAL. The bundled
  `samples/bad_agent_config.json` moves from 4 CRITICAL findings to 3 for the
  same reason. This narrowing is not part of the H2 prohibition guard below; it
  landed between the 0.6.0 tag and this release and is recorded here so an
  upgrade from 0.6.0 accounts for it.
- H4's `Long system prompt with no context boundary markers` (MEDIUM) now also
  requires the prompt to demonstrate cross-context statefulness — carrying
  state, memory, or history across turns, tasks, or sessions — before it
  reports. A long, single-shot reference prompt that never asks the agent to
  carry anything between turns no longer reports this finding on length
  alone; the other H4 erosion patterns are unchanged. The statefulness signal
  is a recognizer, so a prompt that asks for carry-over in wording it does not
  list (`Keep the running tally from earlier questions in mind.`) is a known
  miss.
- H6's `System prompt references multiple output formats (…)` (MEDIUM) now
  requires each named format to carry its own output-format instruction, not
  a bare mention. A prompt that names two formats only while describing which
  file types a tool reads no longer reports this finding. An imperative taking
  the format as a direct object (`Always output JSON.`, `Return JSON only.`,
  `Emit XML.`) counts as an output instruction; a descriptive third-person
  clause (`The upstream service returns JSON.`) does not. That negative is
  correct only when the clause describes what some other system emits. A
  two-format *delivery of the agent's own reply* stated in the third person
  (`The agent's reply is delivered as JSON to the API and as Markdown to the
  UI.`) is exactly the competing contract this rule exists to surface, and the
  narrowing misses it: that is a known limitation, recorded by a test that
  asserts the behaviour the rule should have and is expected to fail until it
  does.
- H6's `System prompt has no explicit output format specification or example.`
  (LOW) no longer reports on a prompt that does specify one in an ordinary
  spelling. `Return Markdown only.` and `Return a plan as Markdown.` were both
  missed because the verb had to be immediately followed by `in`/`as`/`with`/
  `using`. The recognizer is deliberately not widened to arbitrary words before
  the format name, so `Output exactly one Markdown document.` is a known
  remaining miss — as is any wording that puts an unlisted word between the
  connector and the format name (`Reply using the YAML shape below.`) or uses
  an unlisted verb (`Produce a single JSON object.`). Each documented miss for
  the narrowed H4 and H6 rules now has a test that asserts the behaviour the
  rule should have and is expected to fail until the miss is fixed, so closing
  one of these gaps is a visible decision rather than a silent change.
- HERM recognizes explicit prose priority statements such as
  `Priority order is: … then …` without treating absence or uncertainty
  language as an ordering. A public-safe machine-readable case and scanner
  fixture preserve this boundary.

## [0.6.0] - 2026-09-12

### Added

- Opt-in baselines for incremental adoption: `scan --write-baseline FILE`
  records reviewed structural findings; `scan --baseline FILE` reports and
  gates remaining findings. Exact repository-relative identities and occurrence
  counts prevent file-wide or rule-wide suppression. Invalid inputs remain
  fatal, and baseline creation refuses to overwrite existing paths.
- Optional first-party GitHub Action `baseline` input for both terminal and
  SARIF output, with protection against a SARIF report overwriting the baseline.
  Reports disclose the acknowledged finding count; HERM scores are unchanged.
- The Claude Code hook now resolves LintLang without putting the edited
  project's directory on the import path. It prefers the installed `lintlang`
  executable, and uses `python3 -m lintlang` only with `-P` and
  `PYTHONSAFEPATH=1` on interpreters that support them. Previously the `-m`
  probe ran before the pinned version was compared, so a `lintlang.py` in an
  opened project could be executed by the hook.
- Root Claude Code marketplace manifest (`.claude-plugin/marketplace.json`)
  cataloging the existing `integrations/claude-code` plugin. Claude Code cannot
  install a plugin that no marketplace lists, so the adapter previously required
  a local checkout and `--plugin-dir`; `/plugin marketplace add
  hermes-labs-ai/lintlang` then `/plugin install lintlang@lintlang` now works
  from the repository. The marketplace is named `lintlang` rather than
  `hermes-labs`, which is already taken by the published
  `hermes-labs-ai/agent-signage` catalog.
- External MegaLinter plugin exposing the pinned LintLang scanner as
  `AI_LINTLANG`, with an exact configuration guide and clean/failing fixture
  coverage. Verified end to end in `oxsecurity/megalinter-python:v9.4.0`: the
  descriptor loads, `lintlang==0.5.3` installs at run time, a failing fixture
  exits 1, and a clean-only workspace exits 0.

### Fixed

- H2 recognizes explicit local verification bounds and negated retry
  prohibitions, reducing false positives for those instruction patterns.

## [0.5.3] - 2026-09-02

### Added

- Native Gemini CLI `AfterTool` extension that returns bounded LintLang repair
  context after successful `write_file` and `replace` edits.
- Native Claude Code `PostToolUse` plugin for successful `Write` and `Edit`
  operations, with shell-safe paths and an exact scanner-version contract.
- Native OpenCode 1.18.27 `tool.execute.after` adapter that scans explicit
  changed-file paths and skips ambiguous patch operations.

The Gemini extension passed a copied-install live host run and bundles the
repository source with a pinned runtime dependency. All three adapters are
non-blocking and never rewrite the changed file.

## [0.5.2] - 2026-09-02

### Added

- Native Hermes Agent `pre_verify` integration that scans changed
  instruction-bearing files once before a coding turn finishes. `PASS` and
  `REVIEW` remain non-blocking; `FAIL` or input `ERROR` reopens the turn with
  the exact local scan command.

## [0.5.1] - 2026-09-02

### Fixed

- Generated GitHub Code Scanning workflows now isolate SARIF upload permission
  in a second job, disable persisted checkout credentials, and preserve failed
  scan results through an artifact handoff.

## [0.5.0] - 2026-08-24

### Added

- `lintlang init --github` creates an idempotent, pinned GitHub Code Scanning
  workflow for an existing repository-owned instruction file. It auto-detects
  common agent-instruction paths, supports an explicit repository-relative
  `--path`, uploads native SARIF, and refuses silent overwrite unless `--force`
  is supplied.

## [0.4.1] - 2026-08-15

### Changed

- PyPI Homepage and Documentation links now point to the dedicated LintLang
  product page at https://hermes-labs.ai/lintlang. This is a metadata-only
  release; LintLang's scan behavior and GitHub Action interface are unchanged.

## [0.4.0] - 2026-08-13

### Added

- Deterministic SARIF 2.1.0 output for `lintlang scan --format sarif`, validated
  offline against the hash-frozen OASIS errata-01 schema. Findings use their
  most specific stable code as `ruleId`; severity maps to SARIF `level` without
  security metadata or custom fingerprints.
- Repository-relative, URI-encoded artifact locations. AST-extracted Python
  findings include evidence-supported line spans; structured YAML, JSON, and
  text findings remain file-level rather than inventing line or column data.
- An optional `sarif-file` input for the first-party composite Action and a
  least-privilege example that uploads the generated file with GitHub's
  immutable `upload-sarif` Action pin, even when verdict gating returns nonzero.

### Changed

- Release publication now checks out the GitHub Release tag, verifies that its
  `vX.Y.Z` value matches the package version and checked-out commit, runs Twine
  metadata checks, and uses immutable Action SHAs before trusted publishing.

### Fixed

- Quoted detector examples, inline code, fenced code, and metalinguistic
  descriptions no longer trigger H2, H4, or H5 merely by mentioning detector
  phrases. Live directives remain reportable, and scope-classification failures
  preserve prior reporting. This post-0.3.8 fix was merged separately in PR #41
  and remains regression-covered.

## [0.3.8] - 2026-08-05

### Added

- `H1.6`, a sub-code of H1 that reports tool pairs carrying no *differentia* —
  where every meaning-bearing term in one description also appears, or has a
  synonym, in the other. A description states what a tool is; a diagnosis states
  what distinguishes it from its nearest neighbour. An individually accurate
  description can still fail to distinguish its tool from a neighbouring tool.
  H1.6 reports that relational ambiguity before runtime. Schema validation
  cannot reach it because each colliding tool is individually valid.
- Detection uses a curated synonym lexicon, so it reaches some pairs that word
  overlap cannot. `Search the documentation` and `Search through the docs`
  score 0.25 on H1.5's Jaccard measure while carrying no distinguishing term
  under H1.6's model.
- Two shapes are distinguished. *Mutual* — neither tool distinguishes itself.
  *Domination* — one tool's every analysed term is covered by the other, so the
  finding identifies the less-specific description to repair.
- `Finding.sub_id` and `Finding.code`, so a finding can be cited precisely
  ("that's an H1.6") without renaming the pattern IDs already in use. JSON
  output gains a `code` field. `pattern_id` is unchanged.

### Changed

- Some pairs reported in 0.3.2 are now silent by design: a pair whose
  descriptions reference each other by name is treated as self-disambiguating
  and skipped, unless one of them declares itself an alias. Diffing findings
  across versions will show this.
- H1.6 findings are MEDIUM, not HIGH, so they inform a build rather than break
  one. `--fail-on fail` keys on CRITICAL/HIGH and is unaffected; use
  `--fail-on review` to gate on them. This is deliberate while the check's
  recall is unmeasured against a labelled corpus.
- H1.6 comparisons are scoped to tool definitions extracted from one parsed
  input. Directory scans do not aggregate definitions across files or infer
  that separate files share a selection namespace.

### Fixed

- Descriptions in non-Latin scripts are no longer reported as redundant.
  Tokenization matched ASCII only, so Chinese, Japanese, Korean, Cyrillic and
  Arabic descriptions produced no terms at all — and set containment holds
  vacuously for an empty set, so such a tool read as "dominated by" whatever it
  sat beside, with advice to delete it. Tokenization is now Unicode-aware, and a
  tool carrying too little analysable text is skipped rather than compared. The
  lexicon remains English, so synonyms in other languages are not detected.
- A tool whose description declares it an alias of another is now reported as a
  collision. Detection matches a fixed list of phrasings (`Compatibility alias
  for X`, `Deprecated. Use X`, `Superseded by X`); the same relationship phrased
  differently is still missed, the same way the synonym lexicon is finite.
- A tool named with an ordinary English word — `access`, `configure` — no
  longer suppresses findings against its neighbours merely because that word
  appears in their descriptions. Only an identifier-shaped name counts as one
  tool naming another.

Note for anyone diffing the source: several entries that appeared here during
development described defects introduced and fixed within this unreleased
branch, not behaviour any 0.3.2 user encountered. They have been removed. The
cardinality and name-suppression problems never shipped.

## [0.3.2] - 2026-08-04

### Added

- A first-party composite GitHub Action that installs LintLang from the selected
  action ref and preserves the CLI's verdict-based exit status.
- CI smoke coverage for successful and failing action invocations.
- A native pre-commit hook that visibly reviews explicit repository-owned
  instruction paths without blocking on heuristic verdicts by default.

### Changed

- The GitHub Actions quick start now uses `hermes-labs-ai/lintlang@v0.3.2`.
- The quick start now includes exercised `uvx` and isolated `pipx` paths.
- Repositories can opt into blocking pre-commit `FAIL` findings after reviewing
  their baseline.

## [0.3.1] - 2026-07-19

### Changed

- Python source scanning uses AST extraction for embedded prompts and the P1/P2 pipeline checks while preserving the offline, deterministic scan contract.
- An unsupported embedding experiment was removed from the candidate before release because an unavailable backend could not be distinguished from a clean result.

### Added

- **Provider-neutral preflight candidate:** deterministic analysis of one present
  instruction plus typed explicit context, with PF001-PF005 exact evidence,
  `ALLOW | NOTICE | HOLD | UNAVAILABLE | ERROR`, redacted-by-default JSON, and
  explicit source-bound correction previews. It never retrieves history or sends to a provider.
- **Version-of-record consistency gate** (`tests/test_version_consistency.py`): asserts `lintlang.__version__` equals `pyproject.toml`'s `[project].version`, reading source directly so it holds in a fresh clone. Fixes and guards against the prior drift where `__version__` reported `0.2.1` while the published artifact was `0.2.2`. This is the "separate gate" that `test_docs_consistency.py` names as out of its scope.
- **Fatal input-integrity channel:** missing, unreadable, or malformed requested inputs now produce explicit `ERROR` results in the CLI, `scan_file()`, and `scan_directory()`, and the CLI exits 1 regardless of `--fail-on`; another valid input can no longer mask omitted coverage.
- `compute_verdict(result)` and the public terminal/Markdown formatters preserve that `ERROR` state instead of treating an unread input with zero findings as clean; passing a findings list remains compatible after successful input.
- JSON output includes `input_error` for every path and uses `verdict: ERROR` for input failures instead of converting parse errors to INFO/PASS lint findings.
- README examples now report 0.3.1, and verdict/detector language is scoped to
  structural findings rather than runtime guarantees.
- Documentation consistency checks now forbid brittle suite-size claims and
  scope the bundled samples as regression fixtures rather than accuracy evidence.

### Notes

- Zero runtime dependency change — `pyyaml` remains the only runtime dependency.
- `0.3.0` was never published to PyPI or created as a GitHub Release. A public
  `v0.3.0` Git tag already points to an older, pre-fix commit, so this release
  advances to `0.3.1` rather than moving or reusing that immutable tag.

## [0.2.2] - 2026-04-26

### Added

- **`INTENT.md`** at repo root — Hermes Labs convention; one-page invariants doc covering accepts/refuses/non-goals + verification contract.
- **`evals/sample-detection-rate.sh`** — runnable regression check that scans the bundled samples and asserts the expected outcomes. This fixture is not an external accuracy evaluation.
- **`tests/test_docs_consistency.py`** — mechanical CI gate (three assertions) that fails the build if the README opener / latest CHANGELOG entry / `pytest --collect-only` count drift apart. Catches the fabrication-class pattern where a chisel pass updates one surface but leaves a stale figure on another. Replaces manual eyeball-grep audits with `pip install lintlang && pytest tests/test_docs_consistency.py`-checkable invariant.

### Changed

- **README refreshed for Hermes Labs Flagship Standard v1.** Added detector scope, a comparison with model-based review, explicit non-goals, and a reproduce-yourself line pointing at `evals/sample-detection-rate.sh`.

### Notes

- Chisel pass — README + structural docs only. No detector changes.
- Tier B coverage against `flagship-standard.md`: 6/7 (B6 plugin path is the acknowledged miss; queued for v0.3 when a formal `Protocol`/`register()` extension surface lands).
- Experimental E-series detector work was not shipped. Any future integration requires a public evidence corpus, hard-negative tests, and an explicit opt-in contract before it can affect existing CI results.

## [0.2.1] - 2026-04-13

### Added
- **H5 layered exemption system** — three-layer filtering reduces false positives on negatives:
  - Layer 1: Structural exemptions (HTML comments, code blocks, generated-file markers)
  - Layer 2: Phrase-level exemptions (privacy disclaimers, UI labels, descriptive text, idiomatic expressions)
  - Layer 3: Safety-context keyword window (existing behavior, now the fallback)
- **Expanded vague qualifier detection** — catches figurative verbs (`lean into`, `err on the side of`, `double down on`, `keep it simple`), broader ambiguous conditionals (`if appropriate`, `when possible`)
- **H6 code-aware format detection** — strips fenced code blocks, inline code, filenames, and CLI flags before counting format keywords (prevents `--json` flag from triggering mixed-format warnings)
- **Multi-file summary table** — box-drawing table with per-file verdict, findings breakdown, and scan timing (terminal output only, shown when >1 file scanned)
- **Vague qualifier deduplication** — identical matches within a file are reported once

### Changed
- Development status upgraded from Alpha to Production/Stable
- Author metadata updated.

## [0.2.0] - 2026-03-25

### Changed
- **Breaking: Replaced numeric HERM score with PASS/REVIEW/FAIL verdict** in terminal and markdown output
  - ❌ FAIL — any CRITICAL or HIGH finding
  - ⚠️ REVIEW — any MEDIUM finding
  - ✅ PASS — only LOW/INFO findings or none
- Terminal output now leads with verdict + severity summary instead of dimension bars
- Markdown report restructured around verdict + findings (no score in header)
- JSON output: verdict at top level, HERM score moved under `herm` key (preserved for programmatic use)
- `patterns` command simplified to show H1-H7 detectors only

### Added
- `--fail-on fail|review` CLI flag for verdict-based CI gating
- `compute_verdict()` function in public API
- `test_verdict.py` with 10 dedicated verdict logic tests
- `.md` extension support in `scan_directory` (SKILL.md files were silently skipped)
- Expanded `is_prompt_like` regex to recognize SKILL.md format (description/purpose/role patterns)

### Fixed
- SKILL.md files now get proper coverage instead of defaulting to 65% (low confidence)
- Scanning directories with .md instruction files now includes them automatically

### Deprecated
- `--fail-under` (HERM score threshold) still works but `--fail-on` is preferred

## [0.1.2] - 2026-03-02

### Changed
- Updated project URLs for PyPI backlinks (Homepage, Documentation, Repository, Bug Tracker, Changelog)

## [0.1.1] - 2026-03-02

### Fixed
- Standardized package metadata for Hermes Labs.
- Fixed publish workflow to use API token authentication
- Added community health files (CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md)
- Added dependabot configuration

## [0.1.0] — 2026-03-01

First public release.

### Core
- HERM v1.1 scoring engine (6 dimensions, 8 signal categories, coverage/confidence)
- H1-H7 structural detectors with Finding dataclass
- YAML, JSON, and plain text parsers with auto-detection
- Terminal (ANSI), Markdown, and JSON output formats
- `--fail-under` flag for CI gating

### CLI
- `lintlang scan` — scan files or directories
- `lintlang patterns` — list available patterns and dimensions
- `python -m lintlang` support via `__main__.py`
- `--format`, `--patterns`, `--min-severity`, `--no-suggestions` flags
- Dynamic pattern choices from registry

### Detectors
- **H1**: Empty/short/vague tool descriptions, duplicate names, word overlap (Jaccard + stopwords)
- **H2**: Missing constraint scaffolding, unbounded retry loops
- **H3**: Phantom required fields, missing param descriptions, generic names, nested object inspection
- **H4**: Context boundary erosion, missing scope signals
- **H5**: Negative instruction density, vague qualifiers
- **H6**: Mixed output formats, missing format specs, template variable detection
- **H7**: System message placement, consecutive roles, orphan tool results

### Programmatic API
- `scan_file()`, `scan_directory()`, `scan_config()`
- `ScanResult`, `HermResult`, `AgentConfig`, `Finding`, `Severity` exports
- PEP 561 `py.typed` marker
