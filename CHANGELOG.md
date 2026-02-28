# Changelog

## [0.2.0] — 2026-02-27

### Fixed
- **P0 CRASH**: `scan_directory` error handler referenced unbound `findings` variable — `UnboundLocalError` on any malformed file
- **P0 CI GATE BYPASS**: CLI returned exit 0 when all input files were missing, letting CI gates silently pass
- **H1**: Vague verb detection failed when description started with punctuation (e.g., "Handle: request")
- **H2**: Constraint signal detection used substring matching — "limited" falsely suppressed "no limit" warning
- **H4**: Boundary signal detection used substring matching — "microscope" falsely suppressed "no scope" warning
- **H5**: Instruction count inflated by URLs, decimals, abbreviations (now uses sentence-ending detection)
- **H6**: Version marker regex triggered on URLs like `api/v2/users` (now requires `vX.Y` format)
- **H6**: Dead code in template variable detection removed
- **Report**: Hardcoded version string now uses `__version__` from package

### Added
- **H1**: Duplicate tool name detection (CRITICAL severity)
- **H1**: Stopwords excluded from overlap calculation (reduces false positives)
- **H3**: Nested object property inspection (recurses into `type: object` schemas)
- **H3**: Phantom required field detection (required fields not in properties)
- **CLI**: Dynamic pattern choices from registry (no more hardcoded H1-H7 list)
- **CLI**: `python -m lingdiag` support via `__main__.py`
- **Tests**: `scan_directory` tests (crash recovery, malformed files, directory scanning)
- **Tests**: New heuristic tests (word boundary, punctuation, stopwords, nested schemas, phantom required, CI gate bypass)
- **GTM**: Go-to-market plan, competitive landscape analysis, ICP profiles, prospect research (25 companies)

### Changed
- H2/H4 constraint and boundary signal matching now uses word-boundary regex (`\b...\b`)
- H1 word overlap uses Jaccard similarity with stopword exclusion
- Test count: 75 → 87

## [0.1.0] — 2026-02-27

### Added
- Initial MVP: H1-H7 pattern detection engine
- CLI with `scan` and `patterns` subcommands
- YAML, JSON, and plain text parsers with auto-detection
- Terminal (ANSI), Markdown, and JSON output formats
- Health score (0-100) with severity weighting
- 5 sample configs (clean, bad tools, bad prompt, bad agent, mixed)
- 75 tests, all passing
- `pyproject.toml` with hatchling build, Apache 2.0 license
