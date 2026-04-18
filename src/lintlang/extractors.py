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
import json
import logging
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .patterns import AgentConfig, Finding, Severity

logger = logging.getLogger(__name__)

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
    (re.compile(r"\b(do not|don't|never|always)\b.*\b(respond|answer|output|generate|hallucinate|fabricate)\b", re.I), "behavioral constraint"),
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
    context: str = ""        # e.g., "argument to client.chat()", "module-level constant"
    signal_matches: list[str] = field(default_factory=list)


@dataclass
class ExtractedThreshold:
    """A hardcoded threshold/confidence value found in source."""
    name: str
    value: float
    source_file: str
    line: int
    has_comment: bool = False    # Whether there's a calibration comment nearby
    comment_text: str = ""


@dataclass
class ExtractionResult:
    """Result of extracting prompts and thresholds from a source file."""
    prompts: list[ExtractedPrompt] = field(default_factory=list)
    thresholds: list[ExtractedThreshold] = field(default_factory=list)
    source_file: str = ""
    parse_errors: list[str] = field(default_factory=list)


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
    calibration_words = {"calibrat", "tuned", "measured", "empirical", "validated", "tested", "experiment", "ablation", "from distribution", "derived"}
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

    # Walk the AST
    for node in ast.walk(tree):
        # ── Extract prompts from string literals ──
        if isinstance(node, (ast.Constant, ast.JoinedStr)):
            text = _get_string_value(node)
            if text is None:
                continue
            signals = _classify_prompt(text)
            if len(signals) >= MIN_SIGNAL_MATCHES:
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
            if isinstance(value_node, ast.Constant) and isinstance(value_node.value, (int, float)) and value_node.value != 0:
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
            findings.append(Finding(
                pattern_id="P1",
                pattern_name="Uncalibrated Threshold",
                severity=Severity.MEDIUM,
                location=f"{t.source_file}:{t.line}" if t.source_file else f"line:{t.line}",
                description=f"Threshold '{t.name} = {t.value}' has no calibration comment. Magic numbers in LLM pipelines cause silent drift.",
                suggestion=f"Add a comment explaining how '{t.name}' was calibrated: distribution analysis, ablation study, or empirical testing. Example: '# Calibrated on 470-question dev set, fires on ~10% of queries'.",
                evidence=f"{t.name} = {t.value}",
            ))
        else:
            # Has comment but check if it's vague
            vague_words = {"todo", "fixme", "arbitrary", "guess", "probably", "maybe"}
            if any(w in t.comment_text.lower() for w in vague_words):
                findings.append(Finding(
                    pattern_id="P1",
                    pattern_name="Uncalibrated Threshold",
                    severity=Severity.LOW,
                    location=f"{t.source_file}:{t.line}" if t.source_file else f"line:{t.line}",
                    description=f"Threshold '{t.name} = {t.value}' has a calibration comment but it suggests uncertainty: '{t.comment_text}'.",
                    suggestion="Replace vague calibration comment with specific evidence (dataset, sample size, measured distribution).",
                    evidence=f"{t.name} = {t.value}  # {t.comment_text}",
                ))
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
            findings.append(Finding(
                pattern_id="P2",
                pattern_name="Embedded Scaffold",
                severity=Severity.MEDIUM,
                location=f"{p.source_file}:{p.line_start}-{p.line_end}" if p.source_file else f"lines:{p.line_start}-{p.line_end}",
                description=f"Large prompt ({char_count} chars, {line_count} lines) embedded in Python source. Signals: {', '.join(p.signal_matches[:3])}.",
                suggestion="Externalize to a .prompt or .txt file, loaded at runtime. Enables independent versioning, A/B testing, and non-engineer editing.",
                evidence=p.text[:120] + "..." if len(p.text) > 120 else p.text,
            ))
        elif char_count > 200:
            findings.append(Finding(
                pattern_id="P2",
                pattern_name="Embedded Scaffold",
                severity=Severity.LOW,
                location=f"{p.source_file}:{p.line_start}-{p.line_end}" if p.source_file else f"lines:{p.line_start}-{p.line_end}",
                description=f"Medium prompt ({char_count} chars) embedded in source. Signals: {', '.join(p.signal_matches[:3])}.",
                suggestion="Consider externalizing if this prompt is expected to change frequently.",
                evidence=p.text[:80] + "..." if len(p.text) > 80 else p.text,
            ))
    return findings


# ── Scaffold quality detection (P3) ─────────────────────────────────
# Uses nomic-embed-text to compare prompt embeddings against a known-good
# scaffold centroid. Based on experiment: 100% separation, 0.16-0.24 gap.

# Five known-good scaffold fragments used to compute the centroid.
# These are representative of well-structured, high-quality scaffolds.
GOOD_SCAFFOLD_EXEMPLARS: list[str] = [
    "You are a code review assistant. For each file, analyze: 1) correctness of logic, "
    "2) edge case handling, 3) naming clarity, 4) test coverage gaps. Output a structured "
    "JSON report with severity levels for each finding. Never fabricate issues.",
    "thought: Reason step by step about the user's query before acting. "
    "action: Select exactly one tool from the available set. Provide required parameters. "
    "observation: Read the tool output carefully. If incomplete, re-plan. "
    "answer: Synthesize a final response grounded only in observations.",
    "You are a data extraction agent. Your task is to parse the input document and extract "
    "all entities matching the schema below. Return valid JSON only. If a field cannot be "
    "determined from the source text, set it to null. Do not hallucinate values. "
    "Schema: {name: string, role: string, organization: string, confidence: float}",
    "## Instructions\nAnalyze the user's question against the retrieved context passages. "
    "For each claim you make, cite the passage number [1]-[N]. If the context does not "
    "contain sufficient information, state that explicitly rather than guessing. "
    "Respond in markdown with headers for each section of your analysis.",
    "You are a security audit agent. Scan the provided configuration for: "
    "1) hardcoded secrets or API keys, 2) overly permissive IAM policies, "
    "3) unencrypted data at rest, 4) missing rate limits. "
    "Classify each finding as critical/high/medium/low. Provide remediation steps. "
    "Output format: JSON array of {finding, severity, location, remediation}.",
]

# Similarity threshold: prompts below this are flagged as low quality.
# Calibrated from free-experiments-20260418: good scaffolds cluster at 0.6-0.8,
# bad scaffolds at 0.3-0.5. Threshold 0.5 gives 100% separation in experiment.
P3_SIMILARITY_THRESHOLD = 0.5

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Cache for the good-scaffold centroid (computed once per process)
_good_centroid_cache: list[float] | None = None


def _embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Embed texts via Ollama nomic-embed-text. Returns None if Ollama is down."""
    try:
        payload = json.dumps({"model": OLLAMA_EMBED_MODEL, "input": texts}).encode()
        req = urllib.request.Request(
            OLLAMA_EMBED_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) == len(texts):
            return embeddings
        return None
    except Exception:
        logger.debug("Ollama embedding unavailable, skipping P3 scaffold quality check")
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_good_centroid() -> list[float] | None:
    """Compute (and cache) the centroid of known-good scaffold embeddings."""
    global _good_centroid_cache
    if _good_centroid_cache is not None:
        return _good_centroid_cache

    embeddings = _embed_texts(GOOD_SCAFFOLD_EXEMPLARS)
    if embeddings is None:
        return None

    dim = len(embeddings[0])
    centroid = [0.0] * dim
    for emb in embeddings:
        for i, v in enumerate(emb):
            centroid[i] += v
    n = len(embeddings)
    centroid = [c / n for c in centroid]
    _good_centroid_cache = centroid
    return centroid


def detect_scaffold_quality(result: ExtractionResult) -> list[Finding]:
    """P3: Detect low-quality scaffolds using embedding similarity.

    Embeds each extracted prompt (>50 chars) with nomic-embed-text and
    compares to a centroid computed from 5 known-good scaffolds. Prompts
    with similarity < 0.5 are flagged as LOW_QUALITY_SCAFFOLD.

    Fails open: if Ollama is unavailable, returns no findings.
    """
    # Filter to prompts worth checking
    candidates = [p for p in result.prompts if len(p.text) > MIN_PROMPT_LENGTH]
    if not candidates:
        return []

    # Get the good-scaffold centroid
    centroid = _get_good_centroid()
    if centroid is None:
        return []  # Fail open

    # Embed all candidate prompts
    candidate_texts = [p.text for p in candidates]
    embeddings = _embed_texts(candidate_texts)
    if embeddings is None:
        return []  # Fail open

    findings: list[Finding] = []
    for prompt, emb in zip(candidates, embeddings, strict=False):
        sim = _cosine_similarity(emb, centroid)
        if sim < P3_SIMILARITY_THRESHOLD:
            location = (
                f"{prompt.source_file}:{prompt.line_start}-{prompt.line_end}"
                if prompt.source_file
                else f"lines:{prompt.line_start}-{prompt.line_end}"
            )
            findings.append(Finding(
                pattern_id="P3",
                pattern_name="Low Quality Scaffold",
                severity=Severity.MEDIUM,
                location=location,
                description=(
                    f"Scaffold similarity to known-good exemplars is {sim:.2f} "
                    f"(threshold: {P3_SIMILARITY_THRESHOLD}). "
                    f"Low similarity correlates with vague instructions, missing constraints, "
                    f"or lack of structure."
                ),
                suggestion=(
                    "Improve scaffold quality: add explicit output format, "
                    "behavioral constraints (never/always), step-by-step structure, "
                    "and grounding instructions. See known-good exemplars for patterns."
                ),
                evidence=prompt.text[:120] + "..." if len(prompt.text) > 120 else prompt.text,
            ))
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
        )
        configs.append(config)
    return configs
