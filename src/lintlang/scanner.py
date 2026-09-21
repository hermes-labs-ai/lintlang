"""Core scanning engine — HERM v1.1 hermeneutical scoring + structural detectors."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .herm import HermResult, score_text
from .parsers import parse_file, parse_source
from .patterns import PATTERNS, AgentConfig, Finding, SourceRegion

# Pipeline detectors (P-series) — registered lazily to avoid circular imports
_PIPELINE_DETECTORS_LOADED = False

# H1 (Tool Description Ambiguity), H3 (Schema-Intent Mismatch), and H7 all
# reason over an agent config's declared schema/tool surface, which Python
# AST extraction does not produce — scan_python_file() below skips them for
# every extracted prompt. Exposed here (rather than inlined as a literal in
# scan_python_file) so callers, such as the CLI, can warn when a user's
# --patterns selection is entirely made up of patterns that never run on
# .py inputs instead of silently reporting zero findings.
PYTHON_EXTRACTION_EXCLUDED_PATTERNS = frozenset({"H1", "H3", "H7"})

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
    re.compile(r"licen[sc]e|(?:^|[-_.])ofl(?:[-_.]|$)|^notice|third[-_ ]?party|^copying|^patents|^pull_request_template", re.I),
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
    "issue_template",
    "pull_request_template",
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


def _glob_to_regex(pattern: str) -> re.Pattern | None:
    """Compile one gitignore-style glob into an anchored regex.

    Translated in a single pass over the pattern rather than by sequential
    string replacement. Substituting ``**/`` with a regex fragment first and
    then rewriting every remaining ``*`` and ``?`` also rewrote that fragment's
    own metacharacters, which silently turned the optional ``(.*/)?`` into a
    mandatory group — so ``**/*.md`` matched ``docs/a.md`` but not a
    root-level ``a.md``.

    The result is anchored, because an unanchored search made ``docs/**``
    match ``notdocs/a.md`` and ``*.md`` match ``myfoo.md.bak``. Following
    gitignore, a pattern containing no ``/`` matches at any depth, so
    ``CHANGELOG.md`` and ``*.md`` keep excluding nested files as before.
    """
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:[^/]+/)*")
            index += 3
        elif pattern.startswith("**", index):
            parts.append(".*")
            index += 2
        elif pattern[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            parts.append("[^/]")
            index += 1
        else:
            parts.append(re.escape(pattern[index]))
            index += 1

    body = "".join(parts)
    prefix = "" if "/" in pattern else "(?:.*/)?"
    try:
        return re.compile(rf"\A{prefix}{body}\Z")
    except re.error:
        return None


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
        compiled = _glob_to_regex(line)
        if compiled is not None:
            patterns.append(compiled)
    return patterns


def _matches(filepath: Path, base_dir: Path, patterns: list[re.Pattern]) -> bool:
    """Check if filepath, relative to base_dir, matches any compiled pattern."""
    if not patterns:
        return False
    try:
        relative = str(filepath.relative_to(base_dir))
    except ValueError:
        relative = str(filepath)
    return any(p.search(relative) for p in patterns)


def _is_ignored(filepath: Path, base_dir: Path, patterns: list[re.Pattern]) -> bool:
    """Check if filepath matches any .lintlangignore pattern."""
    return _matches(filepath, base_dir, patterns)


def build_input_filter(base_dir: Path, exclude: list[str] | None = None) -> Callable[[Path], bool]:
    """Return a predicate answering "should this input be filtered out?".

    ``--exclude`` globs and a repository's ``.lintlangignore`` describe which
    files a user does not want inspected. That is a property of the input, not
    of how the input was found, so generic directory scanning and opt-in
    repository discovery (``--discover``) share this one filter instead of each
    converting globs for themselves.
    """
    ignore_patterns = _load_ignore_patterns(base_dir)
    exclude_patterns = [compiled for pattern in (exclude or []) if (compiled := _glob_to_regex(pattern)) is not None]

    def filtered(filepath: Path) -> bool:
        return _matches(filepath, base_dir, ignore_patterns) or _matches(filepath, base_dir, exclude_patterns)

    return filtered


@dataclass
class ScanResult:
    """Combined HERM score + structural findings for a file."""

    file: str
    score: float  # HERM hermeneutical score (0-100)
    herm: HermResult  # Full HERM result
    structural_findings: list[Finding] = field(default_factory=list)
    input_error: str | None = None  # Fatal load/parse failure, separate from lint severity
    inspected: dict[str, int] = field(default_factory=dict)
    """What the scan actually read: counts of tools, prompts, messages, schemas.

    A verdict only covers this content. It is reported beside every verdict so a
    clean result on an unread file cannot look like a clean result on a read one."""
    notes: list[str] = field(default_factory=list)
    """Coverage notices: tool-like content the parser saw and did not inspect."""
    skipped: str | None = None
    """Why nothing was inspected, when nothing was (never a PASS)."""


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" + ("" if count == 1 else "s")


def describe_inspected(inspected: dict[str, int]) -> str:
    """One line naming what a verdict covers, e.g. '12 tools (11 described, 12 with a schema)'."""
    parts: list[str] = []
    tools = inspected.get("tools", 0)
    if tools:
        parts.append(
            f"{_plural(tools, 'tool')} ({inspected.get('tools_described', 0)} described, "
            f"{inspected.get('tools_with_schema', 0)} with a schema)"
        )
    if inspected.get("skill_description"):
        parts.append("skill front matter")
    if inspected.get("nested_prompts"):
        parts.append(_plural(inspected["nested_prompts"], "prompt") + " under nested keys")
    elif inspected.get("system_prompt"):
        parts.append("system prompt")
    if inspected.get("instructions"):
        parts.append(f"instruction text ({_plural(inspected.get('lines', 0), 'line')})")
    if inspected.get("messages"):
        parts.append(_plural(inspected["messages"], "message"))
    if inspected.get("schemas"):
        parts.append(_plural(inspected["schemas"], "output schema"))
    if inspected.get("python_prompts"):
        parts.append(_plural(inspected["python_prompts"], "embedded prompt"))
    if inspected.get("python_thresholds"):
        parts.append(_plural(inspected["python_thresholds"], "threshold"))
    return ", ".join(parts) if parts else "nothing"


def _coverage(config: AgentConfig) -> tuple[dict[str, int], list[str], str | None]:
    """Return (inspected counts, notices, skip reason) for a parsed config."""
    inspected: dict[str, int] = {}
    if config.tools:
        inspected["tools"] = len(config.tools)
        inspected["tools_described"] = sum(1 for t in config.tools if t.description.strip())
        inspected["tools_with_schema"] = sum(1 for t in config.tools if t.has_schema or t.parameters)
    if config.skill is not None:
        inspected["skill_description"] = 1
    if config.system_prompt.strip():
        key = "instructions" if config.kind in ("instructions", "prompt") else "system_prompt"
        inspected[key] = 1
        if config.prompt_paths:
            inspected["nested_prompts"] = len(config.prompt_paths)
        if key == "instructions":
            inspected["lines"] = config.system_prompt.count("\n") + 1
    messages = sum(1 for m in config.messages if isinstance(m, dict))
    if messages:
        inspected["messages"] = messages
    if config.schemas:
        inspected["schemas"] = len(config.schemas)

    notes: list[str] = []
    # Only when no tool was read: beside real tools, a stray {name, description}
    # object (an MCP resource, a chat participant) is not an unread tool.
    if config.unclaimed and not config.tools:
        shown = ", ".join(config.unclaimed[:3]) + (", ..." if len(config.unclaimed) > 3 else "")
        notes.append(
            f"{_plural(len(config.unclaimed), 'named, described object')} not inspected as tools "
            f"(no parameter schema, and not under a 'tools' key): {shown}"
        )
    if config.dropped:
        shown = ", ".join(config.dropped[:3]) + (", ..." if len(config.dropped) > 3 else "")
        notes.append(f"{_plural(len(config.dropped), 'entry')} in a tool container could not be read as a tool: {shown}")

    skipped = None
    if not inspected:
        if config.not_agent_content:
            skipped = f"this is {config.not_agent_content}, not agent-facing content"
        elif config.kind in ("instructions", "prompt"):
            skipped = "the file is empty"
        else:
            skipped = "no tool definitions, system prompt, messages or output schema were recognised"
    return inspected, notes, skipped


NOTHING_INSPECTED_HINT = (
    "LintLang reads a tool when it has a string 'name' plus a parameter schema (inputSchema, "
    "input_schema, parameters), or sits under a 'tools' / 'functions' key. Pass "
    "--allow-uninspected to report this file as SKIPPED instead of failing."
)


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

    # Give every finding that knows where its evidence sits a file line. Only
    # text inputs: a prompt embedded in YAML/JSON has no recoverable line here.
    if config.kind in ("instructions", "prompt"):
        for finding in structural:
            if finding.offset is not None and finding.source_region is None:
                line = config.prompt_line_offset + config.system_prompt.count("\n", 0, finding.offset) + 1
                finding.source_region = SourceRegion(line, line)
                # Quote the offending line, whole: a fixed character window cuts
                # words in half and drags in the neighbouring lines.
                prompt = config.system_prompt
                start = prompt.rfind("\n", 0, finding.offset) + 1
                end = prompt.find("\n", finding.offset)
                text_line = prompt[start : end if end != -1 else len(prompt)].strip()
                if text_line:
                    finding.evidence = text_line if len(text_line) <= 200 else text_line[:197] + "..."

    inspected, notes, skipped = _coverage(config)
    return ScanResult(
        file=config.source_file,
        score=herm.score,
        herm=herm,
        structural_findings=structural,
        inspected=inspected,
        notes=notes,
        skipped=skipped,
    )


def _locate_tool_findings(result: ScanResult, text: str) -> None:
    """Give a tool finding the line on which the tool's name is declared.

    Only when that name is declared exactly once in the file, so the line is a
    fact and not a guess."""
    if re.search(r"(?:^|[\s:\[,-])[&*][A-Za-z_][\w-]*\s*(?:$|[\s,\]}])", text, re.MULTILINE) and not text.lstrip().startswith(("{", "[")):
        return  # YAML anchors/aliases: the defective text may live on another line
    cache: dict[str, int | None] = {}
    for finding in result.structural_findings:
        if finding.source_region is not None or not finding.location.startswith("tool:"):
            continue
        name = finding.location.removeprefix("tool:").split(" vs ")[0].split(".parameters")[0]
        if name not in cache:
            declared = [
                m.start()
                for m in re.finditer(rf"""["']?name["']?\s*[:=]\s*["']?{re.escape(name)}["']?\s*(?:,|$)""", text, re.MULTILINE)
            ]
            cache[name] = text.count("\n", 0, declared[0]) + 1 if len(declared) == 1 else None
        if cache[name] is not None:
            finding.source_region = SourceRegion(cache[name], cache[name])


def _enforce_explicit(result: ScanResult, explicit: bool) -> ScanResult:
    """Fail loudly when a NAMED file holds tool-like content none of which was read.

    A named file with nothing agent-facing in it (a package.json handed over by a
    batch wrapper) is SKIPPED, which is visible and is never a PASS. A named file
    that does hold tool-like objects, none of which could be inspected, is the
    dangerous case — the author believes it is covered — so it is an input error.
    """
    if explicit and result.skipped and result.notes and result.input_error is None:
        result.input_error = (
            f"Tool-like content was found but none of it could be inspected: {'; '.join(result.notes)}. "
            f"{NOTHING_INSPECTED_HINT}"
        )
    return result


def scan_file(path: str | Path, patterns: list[str] | None = None, explicit: bool = False) -> ScanResult:
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
            return _enforce_explicit(scan_python_file(path, patterns=patterns), explicit)
        text = path.read_text(encoding="utf-8")
        config = parse_source(text, path)
        result = scan_config(config, patterns=patterns)
        _locate_tool_findings(result, text)
        return _enforce_explicit(result, explicit)
    except Exception as error:
        return input_error_result(path, f"Failed to parse: {error}")


def scan_source(
    text: str, path: str | Path, patterns: list[str] | None = None, explicit: bool = False
) -> ScanResult:
    """Scan in-memory source text as if it had been read from ``path``.

    ``path`` is never opened: it selects the parser (or Python extraction) and
    supplies the source identity used by locations, JSON/SARIF output, and
    baseline matching. A document handed to LintLang over standard input under
    a virtual path therefore produces the same result as the identical file on
    disk.
    """
    path = Path(path)
    try:
        if path.suffix == ".py":
            return _enforce_explicit(scan_python_source(text, path, patterns=patterns), explicit)
        config = parse_source(text, path)
        result = scan_config(config, patterns=patterns)
        _locate_tool_findings(result, text)
        return _enforce_explicit(result, explicit)
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

    # .lintlangignore plus --exclude, compiled once and shared with --discover
    is_filtered = build_input_filter(directory, exclude)

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

        # Skip .lintlangignore and --exclude matches
        if is_filtered(filepath):
            continue

        try:
            if filepath.suffix == ".py":
                result = scan_python_file(filepath, patterns=patterns)
            else:
                result = _scan_walked_file(filepath, patterns)
        except Exception as e:
            result = input_error_result(filepath, f"Failed to parse: {e}")
        results[str(filepath)] = result

    for error in sorted(traversal_errors, key=lambda item: str(item.filename or directory)):
        failed_path = Path(error.filename) if error.filename else directory
        results[str(failed_path)] = input_error_result(failed_path, f"Failed to traverse: {error}")

    return {path: results[path] for path in sorted(results)}


def _scan_walked_file(filepath: Path, patterns: list[str] | None) -> ScanResult:
    """Scan a file the walk met. A loose .txt is a prompt only if it reads like one."""
    if filepath.suffix == ".txt":
        from .extractors import PROMPT_SIGNALS

        try:
            text = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return scan_file(filepath, patterns=patterns)
        if not any(pattern.search(text) for pattern, _ in PROMPT_SIGNALS):
            herm = score_text("", source_path=str(filepath))
            return ScanResult(
                file=str(filepath), score=herm.score, herm=herm,
                skipped="no prompt language was recognised in this text file (name it explicitly to scan it anyway)",
            )
    return scan_file(filepath, patterns=patterns)


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
    from .extractors import extract_from_python_file

    path = Path(path)
    return _scan_python_extraction(extract_from_python_file(path), path, patterns=patterns)


def scan_python_source(
    text: str,
    path: str | Path,
    patterns: list[str] | None = None,
) -> ScanResult:
    """Run Python extraction over in-memory source attributed to ``path``."""
    from .extractors import extract_from_python

    path = Path(path)
    return _scan_python_extraction(extract_from_python(text, source_file=str(path)), path, patterns=patterns)


def _scan_python_extraction(
    extraction,
    path: Path,
    patterns: list[str] | None = None,
) -> ScanResult:
    """Shared Python-extraction scoring for file and in-memory sources."""
    from .extractors import (
        detect_scaffold_in_code,
        detect_uncalibrated_thresholds,
        extracted_prompts_to_configs,
    )

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
            if pid in PYTHON_EXTRACTION_EXCLUDED_PATTERNS:
                continue
            detector = PATTERNS[pid]["detect"]
            findings = detector(config)
            # Prefix location with the extraction source
            for f in findings:
                if config.source_file and not f.location.startswith(config.source_file):
                    f.location = f"{config.source_file} > {f.location}"
                f.source_region = config.source_region
            all_findings.extend(findings)

    # Tool definitions written as literals: H1/H3 apply to them as to any tool.
    if extraction.tools:
        from .patterns import ToolDef

        tool_config = AgentConfig(
            tools=[
                ToolDef(name=t.name, description=t.description, parameters=t.parameters,
                        group="python", has_schema=t.has_schema)
                for t in extraction.tools
            ],
            source_file=str(path),
            kind="python",
        )
        lines = {t.name: t.line for t in extraction.tools}
        for pid in ("H1", "H3"):
            if pid in pattern_ids:
                for f in PATTERNS[pid]["detect"](tool_config):
                    first = f.location.removeprefix("tool:").split(" vs ")[0].split(".")[0]
                    if first in lines:
                        f.source_region = SourceRegion(lines[first], lines[first])
                    all_findings.append(f)

    # HERM scoring on concatenated extracted prompts
    combined_text = "\n\n".join(prompt_texts) if prompt_texts else ""
    herm = score_text(combined_text, source_path=str(path))

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_findings.sort(key=lambda f: severity_order.get(f.severity.value, 5))

    inspected: dict[str, int] = {}
    if extraction.prompts:
        inspected["python_prompts"] = len(extraction.prompts)
    if extraction.thresholds:
        inspected["python_thresholds"] = len(extraction.thresholds)
    if extraction.tools:
        inspected["tools"] = len(extraction.tools)
        inspected["tools_described"] = sum(1 for t in extraction.tools if t.description.strip())
        inspected["tools_with_schema"] = len(extraction.tools)

    return ScanResult(
        file=str(path),
        score=herm.score,
        herm=herm,
        structural_findings=all_findings,
        inspected=inspected,
        skipped=(
            None
            if inspected or extraction.parse_errors
            else "no embedded prompt literals or threshold assignments were found in this Python file"
        ),
        input_error=(
            "; ".join(f"Python parse error: {err}" for err in extraction.parse_errors)
            if extraction.parse_errors
            else None
        ),
    )
