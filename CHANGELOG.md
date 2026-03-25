# Changelog

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
