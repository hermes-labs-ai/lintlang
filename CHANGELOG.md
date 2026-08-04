# Changelog

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
