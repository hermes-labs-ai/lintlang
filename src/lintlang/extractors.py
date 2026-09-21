"""Prompt extractors — pull LLM prompts out of non-config source files.

This is the bridge that turns lintlang from an "agent config linter" into
a metatool that can lint any LLM-using code. The key insight:

  lintlang's H1-H7 rules already work on prompts/scaffolds.
  The problem was never the rules — it was the input pipeline.
  If we can extract prompts from Python source, the rules apply unchanged.

Extractors:
  - PythonPromptExtractor: Uses Python AST to find string literals that
    look like LLM prompts (role language, instruction patterns, scaffold
    markers). Also detects uncalibrated confidence thresholds and
    hardcoded magic numbers used in LLM pipelines.

Architecture:
  Extractors produce ExtractedPrompt objects, each carrying the prompt text,
  its source location, and metadata. These are converted to AgentConfig
  objects so the existing scan_config() pipeline works unchanged.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from .patterns import AgentConfig, Finding, Severity, SourceRegion

# ── Prompt detection heuristics ──────────────────────────────────────

# Patterns that strongly indicate a string is an LLM prompt/scaffold
PROMPT_SIGNALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\byou are\b", re.I), "role assignment"),
    (re.compile(r"\bsystem prompt\b", re.I), "system prompt reference"),
    (re.compile(r"\brespond\s+(in|with|as|using)\b", re.I), "output format instruction"),
    (re.compile(r"\banalyze\s+(the|this|each)\b", re.I), "analysis instruction"),
    (re.compile(r"\b(thought|action|observation)\s*:", re.I), "ReAct scaffold marker"),
    (re.compile(r"\brole\s*:", re.I), "role marker"),
    (re.compile(r"\b(answer|reply|respond)\s+(only|exclusively|strictly)\b", re.I), "strict instruction"),
    (
        re.compile(
            r"\b(do not|don't|never|always)\b.*\b(respond|answer|output|generate|hallucinate|fabricate)\b", re.I
        ),
        "behavioral constraint",
    ),
    (re.compile(r"\bJSON\s*(output|format|response|schema)\b", re.I), "output format spec"),
    (re.compile(r"\b(step\s+\d|first|then|finally)\s*[,:]\s*\w", re.I), "sequential instruction"),
    (re.compile(r"#{1,3}\s*(instructions|rules|constraints|guidelines|context|task)\b", re.I), "prompt section header"),
    (re.compile(r"\buser\s*(message|query|question|input|request)\b", re.I), "user input reference"),
    (re.compile(r"\bcontext\s*window\b", re.I), "context reference"),
    (re.compile(r"\bfew.shot\b", re.I), "few-shot reference"),
]

# Minimum length for a string to be considered a potential prompt
MIN_PROMPT_LENGTH = 50

# Minimum signal matches to classify a string as a prompt
MIN_SIGNAL_MATCHES = 1

# ── Threshold detection ──────────────────────────────────────────────

# Variable name patterns that suggest confidence/threshold values
THRESHOLD_NAME_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:confidence|threshold|cutoff|min_score|max_score)", re.I),
    re.compile(r"(?:FLAGSHIP.*THRESHOLD|BOOST_MAX|BOOST_MIN|PENALTY_FACTOR|WEIGHT$)", re.I),
    re.compile(r"(?:_threshold|_cutoff|_confidence)$", re.I),
]

# Patterns that indicate a variable is a counter/accumulator, NOT a threshold
COUNTER_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:_count|_fired|_total|_sum|_acc|_idx|_index)$", re.I),
    re.compile(r"^(?:count|total|sum|idx|index|i|j|k|n)$", re.I),
]


@dataclass
class ExtractedPrompt:
    """A prompt extracted from source code."""

    text: str
    source_file: str
    line_start: int
    line_end: int
    variable_name: str = ""  # e.g., "SYSTEM_PROMPT", or "" if inline
    context: str = ""  # e.g., "argument to client.chat()", "module-level constant"
    signal_matches: list[str] = field(default_factory=list)


@dataclass
class ExtractedThreshold:
    """A hardcoded threshold/confidence value found in source."""

    name: str
    value: float
    source_file: str
    line: int
    has_comment: bool = False  # Whether there's a calibration comment nearby
    comment_text: str = ""


@dataclass
class ExtractedTool:
    """A tool definition written as a literal in Python source."""

    name: str
    description: str
    parameters: dict
    has_schema: bool
    line: int


_TOOL_SCHEMA_KEYWORDS = ("inputSchema", "input_schema", "parameters", "parameters_json_schema", "args_schema")


def _literal_tools(tree: ast.AST) -> list[ExtractedTool]:
    """Tools declared as `Tool(name=..., description=..., inputSchema=...)` calls
    or as dict literals with the same keys — how MCP servers written in Python
    declare them. Only literal names and descriptions are read; nothing runs."""
    found: list[ExtractedTool] = []
    for node in ast.walk(tree):
        fields: dict[str, ast.AST] = {}
        if isinstance(node, ast.Call):
            fields = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        elif isinstance(node, ast.Dict):
            fields = {
                k.value: v for k, v in zip(node.keys, node.values, strict=False)
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
        if "name" not in fields or not any(key in fields for key in _TOOL_SCHEMA_KEYWORDS):
            continue
        name = _get_string_value(fields["name"])
        if not name and isinstance(fields["name"], ast.Attribute):
            name = fields["name"].attr  # GitTools.STATUS
        if not name:
            continue
        description = _get_string_value(fields["description"]) if "description" in fields else ""
        if "description" in fields and description is None:
            continue  # computed description: not readable, so not judged
        schema_node = next(fields[key] for key in _TOOL_SCHEMA_KEYWORDS if key in fields)
        try:
            schema = ast.literal_eval(schema_node)
        except (ValueError, SyntaxError, TypeError):
            schema = {}
        found.append(
            ExtractedTool(
                name=name,
                description=description or "",
                parameters=schema if isinstance(schema, dict) else {},
                has_schema=True,
                line=getattr(node, "lineno", 1),
            )
        )
    return found


@dataclass
class ExtractionResult:
    """Result of extracting prompts and thresholds from a source file."""

    prompts: list[ExtractedPrompt] = field(default_factory=list)
    thresholds: list[ExtractedThreshold] = field(default_factory=list)
    source_file: str = ""
    parse_errors: list[str] = field(default_factory=list)
    tools: list[ExtractedTool] = field(default_factory=list)


def _get_string_value(node: ast.AST) -> str | None:
    """Extract string value from AST node, handling concatenation and f-strings."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # f-string — extract the literal parts
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("{...}")  # placeholder for expressions
        return "".join(parts)
    return None


def _classify_prompt(text: str) -> list[str]:
    """Check if a string looks like an LLM prompt. Returns list of matched signals."""
    if len(text) < MIN_PROMPT_LENGTH:
        return []
    matches = []
    for pattern, label in PROMPT_SIGNALS:
        if pattern.search(text):
            matches.append(label)
    return matches


def _get_assignment_target(node: ast.Assign) -> str:
    """Get the variable name from an assignment, if simple."""
    if len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
    return ""


def _has_calibration_comment(source_lines: list[str], line_idx: int) -> tuple[bool, str]:
    """Check if there's a calibration/justification comment near a threshold assignment."""
    calibration_words = {
        "calibrat",
        "tuned",
        "measured",
        "empirical",
        "validated",
        "tested",
        "experiment",
        "ablation",
        "from distribution",
        "derived",
    }
    # Check 3 lines before and the line itself
    for offset in range(-3, 2):
        idx = line_idx + offset
        if 0 <= idx < len(source_lines):
            line = source_lines[idx]
            comment_match = re.search(r"#\s*(.+)", line)
            if comment_match:
                comment = comment_match.group(1).lower()
                if any(w in comment for w in calibration_words):
                    return True, comment_match.group(1)
    return False, ""


_PROMPT_NAME = re.compile(
    r"prompt|system|instruction|template|persona|preamble|scaffold|few_?shot|guideline|rubric|^content$", re.I
)
_NOT_PROMPT_NAME = re.compile(r"^(?:help|description|doc|epilog|usage|msg|message|reason|error|warning|title|label|summary)$", re.I)
_NOT_PROMPT_CALL = re.compile(
    r"^(?:print|log|debug|info|warn|warning|error|exception|critical|fail|skip|add_argument|add_parser|"
    r"ArgumentParser|echo|secho|option|argument|command|Field|deprecated|write|format_exc)$|Error$|Exception$|Warning$"
)


def _docstring_nodes(tree: ast.AST) -> set[ast.AST]:
    """String nodes that are documentation for a human, not a prompt for a model."""
    found: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(body[0].value)
        # A bare string statement anywhere (attribute docstring, commented-out block)
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            found.add(node.value)
    return found


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_prompt_in_context(node: ast.AST, parents: dict[ast.AST, ast.AST], text: str, signals: list[str]) -> bool:
    """Decide whether a signal-bearing string is used as a prompt.

    Prose that mentions "the user input" or "first, ..." is everywhere in Python:
    docstrings, help text, log and exception messages. A string is a prompt when
    the code treats it as one — it is bound to a prompt-like name, keyword or
    dict key — or when it addresses a model directly ("You are ...") . Text handed
    to logging, argparse or an exception is never a prompt.
    """
    child: ast.AST = node
    parent = parents.get(child)
    # Look through concatenation, formatting and implicit wrapping.
    while isinstance(parent, (ast.BinOp, ast.FormattedValue, ast.JoinedStr, ast.Tuple, ast.List, ast.IfExp)) or (
        isinstance(parent, ast.Call)
        and isinstance(parent.func, ast.Attribute)
        and parent.func.value is child
    ) or (isinstance(parent, ast.Attribute) and parent.value is child):
        child, parent = parent, parents.get(parent)

    name = ""
    if isinstance(parent, ast.keyword):
        name = parent.arg or ""
        call = parents.get(parent)
        if isinstance(call, ast.Call) and _NOT_PROMPT_CALL.search(_call_name(call)):
            return False
    elif isinstance(parent, ast.Assign):
        name = _get_assignment_target(parent)
    elif isinstance(parent, ast.AnnAssign) and isinstance(parent.target, (ast.Name, ast.Attribute)):
        name = parent.target.id if isinstance(parent.target, ast.Name) else parent.target.attr
    elif isinstance(parent, ast.Dict):
        for key, value in zip(parent.keys, parent.values, strict=False):
            if value is child and isinstance(key, ast.Constant) and isinstance(key.value, str):
                name = key.value
    elif isinstance(parent, ast.Call):
        if _NOT_PROMPT_CALL.search(_call_name(parent)):
            return False
    elif isinstance(parent, ast.Raise):
        return False

    if name and _NOT_PROMPT_NAME.search(name):
        return False
    if name and _PROMPT_NAME.search(name):
        return True
    addresses_model = bool(re.search(r"\byou are\b|\byour (?:task|job|role|goal)\b|\byou (?:must|should|will)\b", text, re.I))
    return addresses_model or len(signals) >= 3


def extract_from_python(source: str, source_file: str = "") -> ExtractionResult:
    """Extract LLM prompts and thresholds from Python source code.

    Uses AST parsing to find:
    1. String literals > 50 chars that match prompt signal patterns
    2. Numeric assignments to threshold/confidence-named variables
    3. String arguments to known LLM API call patterns

    Args:
        source: Python source code as string.
        source_file: Optional file path for error reporting.

    Returns:
        ExtractionResult with extracted prompts, thresholds, and any parse errors.
    """
    result = ExtractionResult(source_file=source_file)
    source_lines = source.splitlines()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        result.parse_errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")
        return result

    result.tools = _literal_tools(tree)

    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    docstrings = _docstring_nodes(tree)

    # Walk the AST
    for node in ast.walk(tree):
        # ── Extract prompts from string literals ──
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            if node in docstrings or isinstance(parents.get(node), ast.JoinedStr):
                continue
            text = _get_string_value(node)
            if text is None:
                continue
            signals = _classify_prompt(text)
            if len(signals) >= MIN_SIGNAL_MATCHES and _is_prompt_in_context(node, parents, text, signals):
                prompt = ExtractedPrompt(
                    text=text,
                    source_file=source_file,
                    line_start=getattr(node, "lineno", 0),
                    line_end=getattr(node, "end_lineno", 0),
                    signal_matches=signals,
                )
                result.prompts.append(prompt)

        # ── Extract thresholds from numeric assignments ──
        if isinstance(node, ast.Assign):
            target_name = _get_assignment_target(node)
            if not target_name:
                continue

            # Check if name matches threshold patterns (and is NOT a counter)
            is_threshold = any(p.search(target_name) for p in THRESHOLD_NAME_PATTERNS)
            is_counter = any(p.search(target_name) for p in COUNTER_PATTERNS)
            if not is_threshold or is_counter:
                continue

            # Check if value is a non-zero number (0.0 is typically an initializer)
            value_node = node.value
            if (
                isinstance(value_node, ast.Constant)
                and isinstance(value_node.value, (int, float))
                and value_node.value != 0
            ):
                line_idx = (node.lineno or 1) - 1
                has_cal, cal_text = _has_calibration_comment(source_lines, line_idx)
                threshold = ExtractedThreshold(
                    name=target_name,
                    value=float(value_node.value),
                    source_file=source_file,
                    line=node.lineno or 0,
                    has_comment=has_cal,
                    comment_text=cal_text,
                )
                result.thresholds.append(threshold)

    # Deduplicate prompts by text content (same string may appear multiple times in AST walk)
    seen_texts: set[str] = set()
    unique_prompts: list[ExtractedPrompt] = []
    for p in result.prompts:
        key = p.text[:200]  # First 200 chars as dedup key
        if key not in seen_texts:
            seen_texts.add(key)
            unique_prompts.append(p)
    result.prompts = unique_prompts

    return result


def extract_from_python_file(path: str | Path) -> ExtractionResult:
    """Extract LLM prompts and thresholds from a Python file."""
    path = Path(path)
    source = path.read_text(encoding="utf-8", errors="ignore")
    return extract_from_python(source, source_file=str(path))


# ── Pipeline-specific detectors ──────────────────────────────────────
# These produce Finding objects directly, complementing H1-H7.


def detect_uncalibrated_thresholds(result: ExtractionResult) -> list[Finding]:
    """P1: Detect hardcoded thresholds without calibration justification.

    Magic numbers in LLM pipelines (confidence cutoffs, score thresholds,
    boost multipliers) are a common source of silent failures. This detector
    flags threshold-like assignments that lack a calibration comment.
    """
    findings: list[Finding] = []
    for t in result.thresholds:
        if not t.has_comment:
            findings.append(
                Finding(
                    pattern_id="P1",
                    pattern_name="Uncalibrated Threshold",
                    severity=Severity.MEDIUM,
                    location=f"{t.source_file}:{t.line}" if t.source_file else f"line:{t.line}",
                    description=f"Threshold '{t.name} = {t.value}' has no calibration comment. Magic numbers in LLM pipelines cause silent drift.",
                    suggestion=f"Add a comment explaining how '{t.name}' was calibrated: distribution analysis, ablation study, or empirical testing. Example: '# Calibrated on 470-question dev set, fires on ~10% of queries'.",
                    evidence=f"{t.name} = {t.value}",
                    source_region=SourceRegion(t.line, t.line),
                )
            )
        else:
            # Has comment but check if it's vague
            vague_words = {"todo", "fixme", "arbitrary", "guess", "probably", "maybe"}
            if any(w in t.comment_text.lower() for w in vague_words):
                findings.append(
                    Finding(
                        pattern_id="P1",
                        pattern_name="Uncalibrated Threshold",
                        severity=Severity.LOW,
                        location=f"{t.source_file}:{t.line}" if t.source_file else f"line:{t.line}",
                        description=f"Threshold '{t.name} = {t.value}' has a calibration comment but it suggests uncertainty: '{t.comment_text}'.",
                        suggestion="Replace vague calibration comment with specific evidence (dataset, sample size, measured distribution).",
                        evidence=f"{t.name} = {t.value}  # {t.comment_text}",
                        source_region=SourceRegion(t.line, t.line),
                    )
                )
    return findings


def detect_scaffold_in_code(result: ExtractionResult) -> list[Finding]:
    """P2: Detect scaffolds embedded in code that should be externalized.

    Long prompts hardcoded in Python source are:
    - Hard to version independently
    - Hard to A/B test
    - Invisible to non-engineer prompt authors
    - Token-costly when they're dead code
    """
    findings: list[Finding] = []
    for p in result.prompts:
        char_count = len(p.text)
        line_count = p.line_end - p.line_start + 1

        if char_count > 500:
            findings.append(
                Finding(
                    pattern_id="P2",
                    pattern_name="Embedded Scaffold",
                    # LOW, not MEDIUM: keeping a prompt in source is a common, deliberate
                    # choice, not a defect. At MEDIUM this made every Python file
                    # that holds a real prompt a REVIEW on length alone.
                    severity=Severity.LOW,
                    location=f"{p.source_file}:{p.line_start}-{p.line_end}"
                    if p.source_file
                    else f"lines:{p.line_start}-{p.line_end}",
                    description=f"Large prompt ({char_count} chars, {line_count} lines) embedded in Python source. Signals: {', '.join(p.signal_matches[:3])}.",
                    suggestion="Externalize to a .prompt or .txt file, loaded at runtime. Enables independent versioning, A/B testing, and non-engineer editing.",
                    evidence=p.text[:120] + "..." if len(p.text) > 120 else p.text,
                    source_region=SourceRegion(p.line_start, p.line_end),
                )
            )
        elif char_count > 200:
            findings.append(
                Finding(
                    pattern_id="P2",
                    pattern_name="Embedded Scaffold",
                    severity=Severity.INFO,
                    location=f"{p.source_file}:{p.line_start}-{p.line_end}"
                    if p.source_file
                    else f"lines:{p.line_start}-{p.line_end}",
                    description=f"Medium prompt ({char_count} chars) embedded in source. Signals: {', '.join(p.signal_matches[:3])}.",
                    suggestion="Consider externalizing if this prompt is expected to change frequently.",
                    evidence=p.text[:80] + "..." if len(p.text) > 80 else p.text,
                    source_region=SourceRegion(p.line_start, p.line_end),
                )
            )
    return findings


def extracted_prompts_to_configs(result: ExtractionResult) -> list[AgentConfig]:
    """Convert extracted prompts to AgentConfig objects for H1-H7 scanning.

    This is the bridge: each extracted prompt becomes an AgentConfig with
    the prompt text as system_prompt, enabling all existing detectors to
    run unchanged.
    """
    configs: list[AgentConfig] = []
    for prompt in result.prompts:
        loc = f"{prompt.source_file}:{prompt.line_start}" if prompt.source_file else f"line:{prompt.line_start}"
        config = AgentConfig(
            system_prompt=prompt.text,
            source_file=loc,
            source_region=SourceRegion(prompt.line_start, prompt.line_end),
            kind="python",
        )
        configs.append(config)
    return configs
