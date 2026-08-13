"""Core scanning engine — HERM v1.1 hermeneutical scoring + structural detectors."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .herm import HermResult, score_text
from .parsers import parse_file
from .patterns import PATTERNS, AgentConfig, Finding

# Pipeline detectors (P-series) — registered lazily to avoid circular imports
_PIPELINE_DETECTORS_LOADED = False

# Files that are never agent configs — skip during directory scans
NON_PROMPT_FILENAMES = {
    "changelog.md",
    "changes.md",
    "history.md",
    "readme.md",
    "readme.txt",
    "contributing.md",
    "contributors.md",
    "code_of_conduct.md",
    "conduct.md",
    "security.md",
    "security.txt",
    "license.md",
    "license.txt",
    "license",
    "authors.md",
    "authors.txt",
    "thanks.md",
    "acknowledgments.md",
    "funding.md",
    "sponsors.md",
    "todo.md",
    "todo.txt",
    "requirements.txt",
    "setup.cfg",
    "manifest.in",
    "sources.txt",
    "dependency_links.txt",
    "top_level.txt",
    "requires.txt",
}

# Regex patterns for filenames that are clearly non-prompt
NON_PROMPT_PATTERNS = [
    re.compile(r"^changelog", re.I),
    re.compile(r"^readme", re.I),
    re.compile(r"^license", re.I),
    re.compile(r"^contributing", re.I),
    re.compile(r"^code.of.conduct", re.I),
    re.compile(r"^security", re.I),
]

# Directory paths that indicate non-prompt content
NON_PROMPT_DIRS = {
    "egg-info",
    ".pytest_cache",
    "node_modules",
    "__pycache__",
    ".git",
    ".tox",
    ".venv",
    "venv",
    "site-packages",
    "__pypackages__",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "htmlcov",
}


def _is_non_prompt_file(filepath: Path) -> bool:
    """Heuristic: is this file clearly NOT an agent prompt/config?"""
    name_lower = filepath.name.lower()

    # Check exact filename matches
    if name_lower in NON_PROMPT_FILENAMES:
        return True

    # Check filename patterns
    for pattern in NON_PROMPT_PATTERNS:
        if pattern.match(name_lower):
            return True

    # Check if in a non-prompt directory
    return any(part.lower() in NON_PROMPT_DIRS or part.lower().endswith(".egg-info") for part in filepath.parts)


def _load_ignore_patterns(directory: Path) -> list[re.Pattern]:
    """Load .lintlangignore from directory (gitignore-style globs)."""
    ignore_file = directory / ".lintlangignore"
    if not ignore_file.exists():
        return []

    patterns = []
    for line in ignore_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Convert glob to regex
        regex = line.replace(".", r"\.").replace("**/", "(.*/)?").replace("*", "[^/]*").replace("?", "[^/]")
        try:
            patterns.append(re.compile(regex))
        except re.error:
            continue
    return patterns


def _is_ignored(filepath: Path, base_dir: Path, patterns: list[re.Pattern]) -> bool:
    """Check if filepath matches any .lintlangignore pattern."""
    if not patterns:
        return False
    relative = str(filepath.relative_to(base_dir))
    return any(p.search(relative) for p in patterns)


@dataclass
class ScanResult:
    """Combined HERM score + structural findings for a file."""

    file: str
    score: float  # HERM hermeneutical score (0-100)
    herm: HermResult  # Full HERM result
    structural_findings: list[Finding] = field(default_factory=list)
    input_error: str | None = None  # Fatal load/parse failure, separate from lint severity


def input_error_result(path: str | Path, message: str) -> ScanResult:
    """Build a result for an input that could not be loaded or parsed."""
    source = str(path)
    herm = score_text("", source_path=source)
    return ScanResult(file=source, score=herm.score, herm=herm, input_error=message)


def _build_scoring_text(config: AgentConfig) -> str:
    """Assemble text corpus for HERM scoring from parsed AgentConfig."""
    parts: list[str] = []
    if config.system_prompt:
        parts.append(config.system_prompt)
    for tool in config.tools:
        if tool.description:
            parts.append(tool.description)
    for msg in config.messages:
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            parts.append(content)
    return "\n\n".join(parts)


def scan_config(
    config: AgentConfig,
    patterns: list[str] | None = None,
) -> ScanResult:
    """Score a config with HERM v1.1 + run structural detectors.

    Args:
        config: Normalized agent configuration.
        patterns: Optional list of structural pattern IDs (H1-H7).

    Returns:
        ScanResult with HERM score and structural findings.
    """
    # HERM scoring on assembled text
    text = _build_scoring_text(config)
    herm = score_text(text, source_path=config.source_file)

    # Structural detectors (H1-H7) as supplementary findings
    structural: list[Finding] = []
    pattern_ids = patterns or list(PATTERNS.keys())
    for pid in pattern_ids:
        if pid not in PATTERNS:
            continue
        detector = PATTERNS[pid]["detect"]
        structural.extend(detector(config))

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    structural.sort(key=lambda f: severity_order.get(f.severity.value, 5))

    return ScanResult(
        file=config.source_file,
        score=herm.score,
        herm=herm,
        structural_findings=structural,
    )


def scan_file(path: str | Path, patterns: list[str] | None = None) -> ScanResult:
    """Parse a file and produce a full scan result.

    Uses HERM v1.1 as the primary scorer with structural detectors
    (H1-H7) providing supplementary findings. Input failures are returned on
    the fatal ``input_error`` channel rather than raised or reported as clean.
    """
    path = Path(path)
    if not path.exists():
        return input_error_result(path, "File not found")
    if not path.is_file():
        return input_error_result(path, f"File scan requires a file: {path}")

    try:
        if path.suffix == ".py":
            return scan_python_file(path, patterns=patterns)
        config = parse_file(path)
        return scan_config(config, patterns=patterns)
    except Exception as error:
        return input_error_result(path, f"Failed to parse: {error}")


def scan_directory(
    directory: str | Path,
    patterns: list[str] | None = None,
    extensions: tuple[str, ...] = (".yaml", ".yml", ".json", ".txt", ".md", ".prompt", ".py"),
    exclude: list[str] | None = None,
) -> dict[str, ScanResult]:
    """Scan all matching files in a directory.

    Args:
        directory: Path to scan recursively.
        patterns: Optional list of structural pattern IDs (H1-H7).
        extensions: File extensions to include.
        exclude: Glob patterns to exclude (e.g., ["CHANGELOG.md", "docs/**"]).

    Automatically skips:
        - Non-prompt files (README, CHANGELOG, LICENSE, etc.)
        - .lintlangignore patterns (gitignore-style, from directory root)
        - Files matching --exclude patterns

    Returns:
        Dict mapping file paths to ScanResults.
    """
    directory = Path(directory)
    if not directory.exists():
        message = f"Directory not found: {directory}"
        return {str(directory): input_error_result(directory, message)}
    if not directory.is_dir():
        message = f"Directory scan requires a directory: {directory}"
        return {str(directory): input_error_result(directory, message)}

    results: dict[str, ScanResult] = {}

    # Load .lintlangignore
    ignore_patterns = _load_ignore_patterns(directory)

    # Compile --exclude patterns
    exclude_patterns: list[re.Pattern] = []
    if exclude:
        for pattern in exclude:
            regex = pattern.replace(".", r"\.").replace("**/", "(.*/)?").replace("*", "[^/]*").replace("?", "[^/]")
            try:
                exclude_patterns.append(re.compile(regex))
            except re.error:
                continue

    extension_set = set(extensions)
    candidates: list[Path] = []
    traversal_errors: list[OSError] = []

    def record_traversal_error(error: OSError) -> None:
        traversal_errors.append(error)

    for root, dirnames, filenames in os.walk(directory, followlinks=False, onerror=record_traversal_error):
        # Prune dependency/cache trees before traversal. File-level rejection
        # alone would still enumerate every file in a local virtualenv.
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name.lower() not in NON_PROMPT_DIRS
            and not name.lower().endswith(".egg-info")
            and not (Path(root) / name).is_symlink()
        )
        for filename in sorted(filenames):
            filepath = Path(root) / filename
            if filepath.suffix in extension_set and not filepath.is_symlink():
                candidates.append(filepath)

    for filepath in sorted(candidates, key=str):
        # Skip non-prompt files (CHANGELOG, README, etc.)
        if _is_non_prompt_file(filepath):
            continue

        # Skip .lintlangignore matches
        if _is_ignored(filepath, directory, ignore_patterns):
            continue

        # Skip --exclude matches
        if exclude_patterns:
            relative = str(filepath.relative_to(directory))
            if any(p.search(relative) for p in exclude_patterns):
                continue

        try:
            if filepath.suffix == ".py":
                results[str(filepath)] = scan_python_file(filepath, patterns=patterns)
            else:
                results[str(filepath)] = scan_file(filepath, patterns=patterns)
        except Exception as e:
            results[str(filepath)] = input_error_result(filepath, f"Failed to parse: {e}")

    for error in sorted(traversal_errors, key=lambda item: str(item.filename or directory)):
        failed_path = Path(error.filename) if error.filename else directory
        results[str(failed_path)] = input_error_result(failed_path, f"Failed to traverse: {error}")

    return {path: results[path] for path in sorted(results)}


def compute_health_score(findings: list[Finding]) -> float:
    """Legacy penalty-based scorer. Kept for backward compatibility.

    For new code, use scan_file().score (HERM v1.1) instead.
    """
    if not findings:
        return 100.0
    total_penalty = sum(f.severity.score for f in findings)
    capped = min(total_penalty, 100)
    return max(0.0, 100.0 - capped)


# ── Python/Pipeline scanning (metatool extension) ─────────────────────


def scan_python_file(
    path: str | Path,
    patterns: list[str] | None = None,
) -> ScanResult:
    """Scan a Python file for embedded prompts, thresholds, and pipeline issues.

    This is lintlang's metatool mode: instead of treating the whole file as a
    prompt (which gives meaningless results), it:
    1. Uses AST to extract embedded prompts from string literals
    2. Runs H1-H7 on each extracted prompt
    3. Runs P1-P2 pipeline detectors on thresholds and embedded scaffolds
    4. Scores the concatenated prompts with HERM

    Args:
        path: Path to the Python file to scan.
        patterns: Optional list of structural pattern IDs (H1-H7) to run.

    Returns a single ScanResult aggregating all findings.
    """
    from .extractors import (
        detect_scaffold_in_code,
        detect_uncalibrated_thresholds,
        extract_from_python_file,
        extracted_prompts_to_configs,
    )

    path = Path(path)
    extraction = extract_from_python_file(path)

    # Pipeline-specific detectors (P1, P2)
    all_findings: list[Finding] = []
    all_findings.extend(detect_uncalibrated_thresholds(extraction))
    all_findings.extend(detect_scaffold_in_code(extraction))

    # Run H1-H7 on each extracted prompt
    configs = extracted_prompts_to_configs(extraction)
    prompt_texts: list[str] = []
    pattern_ids = patterns or list(PATTERNS.keys())

    for config in configs:
        prompt_texts.append(config.system_prompt)
        for pid in pattern_ids:
            if pid not in PATTERNS:
                continue
            # Only run prompt-relevant detectors (H2, H4, H5, H6 — not H1/H3/H7)
            if pid in ("H1", "H3", "H7"):
                continue
            detector = PATTERNS[pid]["detect"]
            findings = detector(config)
            # Prefix location with the extraction source
            for f in findings:
                if config.source_file and not f.location.startswith(config.source_file):
                    f.location = f"{config.source_file} > {f.location}"
                f.source_region = config.source_region
            all_findings.extend(findings)

    # HERM scoring on concatenated extracted prompts
    combined_text = "\n\n".join(prompt_texts) if prompt_texts else ""
    herm = score_text(combined_text, source_path=str(path))

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_findings.sort(key=lambda f: severity_order.get(f.severity.value, 5))

    return ScanResult(
        file=str(path),
        score=herm.score,
        herm=herm,
        structural_findings=all_findings,
        input_error=(
            "; ".join(f"Python parse error: {err}" for err in extraction.parse_errors)
            if extraction.parse_errors
            else None
        ),
    )
