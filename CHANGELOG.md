# Changelog

## [0.2.2] - 2026-04-26

### Added

- **`INTENT.md`** at repo root — Hermes Labs convention; one-page invariants doc covering accepts/refuses/non-goals + verification contract.
- **`evals/sample-detection-rate.sh`** — runnable detection-rate check that scans the bundled samples and asserts the expected outcome (4 known-bad files flagged, 1 known-clean file passes). The smallest reproducible eval surface for the README's flagship claims.
- **`tests/test_docs_consistency.py`** — mechanical CI gate (three assertions) that fails the build if the README opener / latest CHANGELOG entry / `pytest --collect-only` count drift apart. Catches the fabrication-class pattern where a chisel pass updates one surface but leaves a stale figure on another. Replaces manual eyeball-grep audits with `pip install lintlang && pytest tests/test_docs_consistency.py`-checkable invariant.

### Changed

- **README chiseled to Hermes Labs Flagship Standard v1.** Quantified opener with named benchmarks (154 tests, 7 H1–H7 detectors, 6 HERM v1.1 dimensions, validated against 28 comparison files, ~2ms per file scan). Added a "How it differs from LLM-based config review" anti-pattern section with concrete cost/time/determinism comparison. Expanded "When NOT to use" to 5 named scenarios. Added a reproduce-yourself line pointing at `evals/sample-detection-rate.sh`.

### Notes

- Chisel pass — README + structural docs only. No detector changes.
- Tier B coverage against `flagship-standard.md`: 6/7 (B6 plugin path is the acknowledged miss; queued for v0.3 when a formal `Protocol`/`register()` extension surface lands).
- An in-progress E1–E5 epistemic-failure detector set lives on local branch `wip/eseries-integration` (commit `b199987`, session `0214f811` 2026-04-22). Merge into v0.3 requires (a) porting six broader E1 sycophancy patterns from the older `epistemic.py` into the canonical `detectors_epistemic.py`, (b) stripping the in-session-invented "B09 adversarial-school / attack V16" framework references from code comments (they reference no external corpus), (c) adding a `--include-epistemic` opt-in flag so existing CIs are not surprised by new default detectors.

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
- Author email updated to rbosch@lpci.ai

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
- Standardized package metadata (author: Hermes Labs, email: lpcisystems@gmail.com)
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
