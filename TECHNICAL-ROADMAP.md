# lingdiag Technical Roadmap

**Version:** 1.0 | **Date:** 2026-02-27 | **Status:** Architecture Design

---

## Table of Contents

1. [Current Architecture Assessment](#1-current-architecture-assessment)
2. [Plugin System Design](#2-plugin-system-design)
3. [LLM Integration Architecture](#3-llm-integration-architecture)
4. [CI/CD Integration](#4-cicd-integration)
5. [Data Pipeline](#5-data-pipeline)
6. [Testing Strategy](#6-testing-strategy)
7. [Phased Implementation Plan](#7-phased-implementation-plan)

---

## 1. Current Architecture Assessment

### 1.1 Codebase Summary

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `patterns.py` | 605 | Data models (Severity, Finding, AgentConfig, ToolDef) + 7 detector functions + pattern registry |
| `cli.py` | 155 | argparse CLI with `scan` and `patterns` subcommands |
| `parsers.py` | 138 | YAML/JSON/text parsing, normalizing to AgentConfig |
| `scanner.py` | 95 | Orchestration: runs detectors, sorts findings, computes health score |
| `report.py` | 183 | Terminal (ANSI) and Markdown report formatters |
| `__init__.py` | 3 | Version string |
| **Tests** | 672 | 75 tests across 4 test files, all passing |
| **Total** | 1,851 | |

### 1.2 Current Architecture Diagram

```
                    CLI (cli.py)
                        |
           +------------+------------+
           |                         |
     parse_file()              format_terminal()
     (parsers.py)              format_markdown()
           |                   (report.py)
           v                         ^
      AgentConfig                    |
           |                         |
           v                         |
      scan_config() -----> [Finding, ...]
      (scanner.py)
           |
           v
    PATTERNS registry  -->  detect_h1() ... detect_h7()
    (patterns.py)           (patterns.py)
```

### 1.3 Extensibility Assessment

**Pattern Detection System: MODERATE extensibility**

Adding H8, H9, etc. requires:
1. Write a `detect_hN(config: AgentConfig) -> list[Finding]` function in `patterns.py`
2. Add an entry to the `PATTERNS` dict at the bottom
3. Update the `--patterns` choices in `cli.py` (line 30: hardcoded `["H1"..."H7"]`)

**Problems:**
- The `PATTERNS` dict is the only registry, and it lives in the same file as data models AND all detection logic. `patterns.py` is already 605 lines and will grow linearly with every new pattern.
- The CLI hardcodes pattern IDs in `choices=["H1"..."H7"]`, which means adding H8 requires touching both `patterns.py` AND `cli.py`.
- No pattern metadata beyond `name` and `detect`. Missing: description, category/tag, severity range, version added, documentation URL, author.
- No mechanism for pattern dependencies (the H1->H2 causal chain documented in the taxonomy is not encoded).

**Parser System: LOW extensibility**

Adding a new config format (e.g., TOML, OpenAPI) requires editing `parse_file()` directly (adding another `elif` branch). The `_normalize()` function is a single monolith that handles all key-name variations for system prompts, tools, messages, schemas, and constraints. New formats that don't fit this normalization model (e.g., multi-agent orchestration configs, MCP server definitions) would require either overloading `_normalize()` or bypassing it entirely.

**Separation of Concerns: FAIR, with one critical violation**

`patterns.py` conflates three distinct responsibilities:
1. **Data models** (Severity, Finding, AgentConfig, ToolDef) -- should be standalone
2. **Detection logic** (detect_h1 through detect_h7) -- should be per-pattern modules
3. **Pattern registry** (PATTERNS dict) -- should be a proper registry with discovery

The parser/scanner/report/cli separation is clean and well-structured.

### 1.4 Performance Characteristics

**Current profile:**
- 75 tests execute in 0.06s -- extremely fast baseline
- Each detector is regex-based with O(n*m) behavior (n = text length, m = pattern count)
- H1's cross-tool overlap uses O(k^2) pairwise Jaccard similarity (k = number of tools)
- All operations are single-threaded, synchronous, in-memory

**Scaling assessment for 1,000 files:**

| Operation | Current Perf | At 1,000 files | Bottleneck? |
|-----------|-------------|----------------|-------------|
| File I/O (read) | Negligible | ~50ms (SSD) | No |
| YAML parsing | ~0.5ms/file | ~500ms | No |
| JSON parsing | ~0.1ms/file | ~100ms | No |
| H1-H7 regex scans | ~0.3ms/config | ~300ms | No |
| H1 pairwise overlap | O(k^2) | Depends on tools/file | Unlikely unless >100 tools/config |
| Directory walk (rglob) | Negligible | ~20ms | No |
| **Projected total** | | **~1-2 seconds** | **No bottleneck** |

The current regex-based approach will handle 1,000 files easily. Performance only becomes a concern at:
- 10,000+ files (parallelization would help)
- Configs with 100+ tools (H1 pairwise degrades)
- LLM integration (network I/O dominates -- see Section 3)

**Bug in `scan_directory`:** Line 75 of `scanner.py` references `findings` in the except handler before it may be assigned. If `parse_file()` or `scan_file()` raises before any findings are generated, the Severity import fallback is also problematic (uses runtime `__import__` in exception handler). This will crash on parse errors.

---

## 2. Plugin System Design

### 2.1 Design Goals

1. Third parties can ship pattern detectors as pip-installable packages
2. Framework-specific parsers can be added without modifying core
3. Plugins are discovered automatically via entry points (no manual registration)
4. Type safety via Protocol classes (no ABC inheritance tax)

### 2.2 Architecture

```
                         lingdiag (core)
                              |
              +---------------+---------------+
              |               |               |
         models.py      registry.py      interfaces.py
         (Severity,     (discover,       (PatternDetector,
          Finding,       register,        ConfigParser
          AgentConfig,   list_patterns)   protocols)
          ToolDef)
              |
   +----------+----------+
   |          |          |
parsers/   patterns/   reporters/
  __init__   __init__    __init__
  yaml_.py   h1.py       terminal.py
  json_.py   h2.py       markdown.py
  text_.py   ...         json_.py
  toml_.py   h7.py       sarif.py
             custom/
              __init__


        Third-Party Plugin Package
        (e.g., lingdiag-langchain)
              |
        pyproject.toml:
          [project.entry-points."lingdiag.patterns"]
          LC1 = "lingdiag_langchain.patterns:LangChainRouterDetector"
          LC2 = "lingdiag_langchain.patterns:LangChainMemoryDetector"
```

### 2.3 Interface Definitions

```python
# src/lingdiag/interfaces.py

from __future__ import annotations
from typing import Protocol, runtime_checkable
from .models import AgentConfig, Finding


@runtime_checkable
class PatternDetector(Protocol):
    """Protocol for pattern detection plugins.

    Any class with these attributes/methods qualifies -- no inheritance needed.
    """

    id: str                    # e.g., "H1", "LC1", "CUSTOM-001"
    name: str                  # Human-readable name
    description: str           # What this pattern detects
    category: str              # "tool", "prompt", "schema", "context", "role", "format"
    version: str               # Semver: "1.0.0"
    default_severity: str      # Default severity level for this pattern

    def detect(self, config: AgentConfig) -> list[Finding]:
        """Run detection against a config. Returns findings."""
        ...

    def supports(self, config: AgentConfig) -> bool:
        """Optional: return False to skip this detector for configs
        that don't apply (e.g., skip H7 for configs with no messages).
        Default implementation returns True.
        """
        ...


@runtime_checkable
class ConfigParser(Protocol):
    """Protocol for config format parsers."""

    extensions: tuple[str, ...]   # e.g., (".yaml", ".yml")
    format_name: str              # e.g., "yaml", "openapi"

    def can_parse(self, text: str, path: str) -> bool:
        """Sniff whether this parser can handle the input."""
        ...

    def parse(self, text: str, source_file: str) -> AgentConfig:
        """Parse the text into an AgentConfig."""
        ...


@runtime_checkable
class Reporter(Protocol):
    """Protocol for output format reporters."""

    format_name: str              # e.g., "terminal", "sarif", "github"

    def format(
        self,
        findings: list[Finding],
        source_file: str = "",
        show_suggestions: bool = True,
    ) -> str:
        """Format findings into output string."""
        ...
```

### 2.4 Registry and Discovery

```python
# src/lingdiag/registry.py

from __future__ import annotations
import importlib.metadata
from typing import Any
from .interfaces import PatternDetector, ConfigParser, Reporter

_patterns: dict[str, PatternDetector] = {}
_parsers: dict[str, ConfigParser] = {}
_reporters: dict[str, Reporter] = {}


def discover_plugins() -> None:
    """Load plugins from entry points.

    Entry point groups:
      - lingdiag.patterns  -> PatternDetector instances
      - lingdiag.parsers   -> ConfigParser instances
      - lingdiag.reporters -> Reporter instances
    """
    for group, registry in [
        ("lingdiag.patterns", _patterns),
        ("lingdiag.parsers", _parsers),
        ("lingdiag.reporters", _reporters),
    ]:
        for ep in importlib.metadata.entry_points(group=group):
            try:
                obj = ep.load()
                # Support both class-based (instantiate) and instance-based
                if isinstance(obj, type):
                    instance = obj()
                else:
                    instance = obj
                key = getattr(instance, "id", None) or getattr(instance, "format_name", ep.name)
                registry[key] = instance
            except Exception as exc:
                import warnings
                warnings.warn(
                    f"Failed to load lingdiag plugin {ep.name!r} from {ep.group!r}: {exc}",
                    stacklevel=2,
                )


def register_pattern(detector: PatternDetector) -> None:
    """Manually register a pattern detector (for programmatic use)."""
    _patterns[detector.id] = detector


def register_parser(parser: ConfigParser) -> None:
    _parsers[parser.format_name] = parser


def register_reporter(reporter: Reporter) -> None:
    _reporters[reporter.format_name] = reporter


def get_patterns() -> dict[str, PatternDetector]:
    return dict(_patterns)


def get_parsers() -> dict[str, ConfigParser]:
    return dict(_parsers)


def get_reporters() -> dict[str, Reporter]:
    return dict(_reporters)
```

### 2.5 Entry Point Configuration (Third-Party Example)

```toml
# Third-party package: lingdiag-langchain/pyproject.toml

[project.entry-points."lingdiag.patterns"]
LC1 = "lingdiag_langchain.patterns.router:RouterDetector"
LC2 = "lingdiag_langchain.patterns.memory:MemoryDetector"

[project.entry-points."lingdiag.parsers"]
langchain_yaml = "lingdiag_langchain.parsers:LangChainYamlParser"
```

### 2.6 Refactored Pattern Example (H1 as a class)

```python
# src/lingdiag/patterns/h1.py

from __future__ import annotations
import re
from ..models import AgentConfig, Finding, Severity, ToolDef

VAGUE_WORDS = {
    "handle", "process", "manage", "do", "run", "execute",
    "perform", "deal", "work", "use", "make", "get", "set",
}


class H1ToolAmbiguity:
    id = "H1"
    name = "Tool Description Ambiguity"
    description = "Detects vague, overlapping, or missing tool descriptions"
    category = "tool"
    version = "1.0.0"
    default_severity = "high"

    def supports(self, config: AgentConfig) -> bool:
        return len(config.tools) > 0

    def detect(self, config: AgentConfig) -> list[Finding]:
        findings: list[Finding] = []
        # ... (existing detect_h1 logic, unchanged)
        return findings
```

### 2.7 Migration Path

The plugin system can be introduced without breaking existing API:

1. Extract `Severity`, `Finding`, `AgentConfig`, `ToolDef` into `models.py`
2. Create `interfaces.py` with Protocol definitions
3. Wrap existing `detect_hN` functions in lightweight classes that conform to `PatternDetector`
4. Register them via the core package's own entry points
5. The existing `PATTERNS` dict becomes a compatibility shim that delegates to the registry

---

## 3. LLM Integration Architecture

### 3.1 Design Principle: Heuristic-First, LLM-Second

```
Input Config
     |
     v
+------------------+
| Heuristic Scan   |  <-- Always runs (fast, free, deterministic)
| H1-H7 detectors  |
+------------------+
     |
     v
 [Findings]
     |
     +---- severity >= threshold? ----+
     |             |                  |
     No            Yes                |
     |             |                  |
  Report        +--v-----------+      |
  as-is         | LLM Enricher |      |
                | (optional)   |      |
                +--------------+      |
                     |                |
                     v                |
              [Enriched Findings] <---+
                     |
                     v
                  Report
```

The LLM is never in the critical path. It enriches findings that the heuristic flagged, providing:
- **Semantic analysis** ("These two tools genuinely overlap because...")
- **Rewrite suggestions** ("Here is a better tool description: ...")
- **Confidence scoring** ("This is likely a false positive because...")
- **Cross-pattern reasoning** ("This H1 issue will likely cause H2 loops because...")

### 3.2 When to Call the LLM

| Trigger | What to Send | Expected Value |
|---------|-------------|---------------|
| H1: Overlap > 0.5 but < 0.8 | Both tool descriptions + names | Disambiguate real overlap vs coincidental word sharing |
| H1: Short description | Tool name + parameters schema | Generate a better description |
| H2: Dangerous pattern found | System prompt excerpt (500 char window) | Classify severity: rhetorical vs literal |
| H3: Union types without descriptions | Full parameter schema | Generate variant descriptions |
| H5: Vague qualifier detected | Instruction in context | Rewrite as procedural instruction |
| H6: Multiple formats referenced | Full system prompt | Determine if formats are properly scoped per use case |
| Any: Confidence < threshold | Finding + evidence + context | "Is this a true positive?" triage |

### 3.3 Provider Abstraction

```python
# src/lingdiag/llm/provider.py

from __future__ import annotations
from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cached: bool = False
    cost_usd: float = 0.0


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider backends."""

    name: str                          # "anthropic", "openai", "ollama"

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...

    def is_available(self) -> bool:
        """Check if the provider is configured (API key present, etc.)."""
        ...

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given token count."""
        ...
```

### 3.4 Provider Implementations

```python
# src/lingdiag/llm/anthropic_.py

class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def is_available(self) -> bool:
        return self.api_key is not None

    def complete(self, prompt, system="", max_tokens=1024, temperature=0.0):
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return LLMResponse(
            content=response.content[0].text,
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=self.estimated_cost(
                response.usage.input_tokens, response.usage.output_tokens
            ),
        )

    def estimated_cost(self, input_tokens, output_tokens):
        # Sonnet 4 pricing as of Feb 2026
        return (input_tokens * 3.0 / 1_000_000) + (output_tokens * 15.0 / 1_000_000)


# Similarly: OpenAIProvider, OllamaProvider
```

### 3.5 Enrichment Engine

```python
# src/lingdiag/llm/enricher.py

from __future__ import annotations
from dataclasses import dataclass
from .provider import LLMProvider, LLMResponse
from .cache import ResponseCache
from ..models import Finding, AgentConfig

ENRICHMENT_SYSTEM = """You are a linguistic diagnostics expert specializing in AI agent
configuration analysis. You analyze tool descriptions, system prompts, and schemas
for language-to-action boundary failures.

When given a finding from a heuristic detector, you provide:
1. CONFIDENCE: 0-100 score for whether this is a true positive
2. ANALYSIS: 1-2 sentence explanation of WHY this matters
3. REWRITE: If applicable, a concrete fix for the issue
4. CROSS_PATTERN: Any connections to other H-pattern failures

Respond in JSON format."""


@dataclass
class EnrichedFinding:
    original: Finding
    confidence: int           # 0-100, LLM-assessed
    analysis: str             # Semantic explanation
    rewrite: str | None       # Suggested fix text
    cross_patterns: list[str] # Related pattern IDs
    llm_model: str
    llm_cost_usd: float


class FindingEnricher:
    def __init__(
        self,
        provider: LLMProvider,
        cache: ResponseCache | None = None,
        confidence_threshold: int = 50,
        max_batch_size: int = 10,
        budget_usd: float = 1.0,
    ):
        self.provider = provider
        self.cache = cache or ResponseCache()
        self.confidence_threshold = confidence_threshold
        self.max_batch_size = max_batch_size
        self.budget_usd = budget_usd
        self._spent_usd = 0.0

    def should_enrich(self, finding: Finding) -> bool:
        """Determine if a finding is worth LLM enrichment."""
        # Always skip INFO-level
        if finding.severity.value == "info":
            return False
        # Always enrich CRITICAL
        if finding.severity.value == "critical":
            return True
        # Enrich HIGH if budget remains
        if finding.severity.value == "high" and self._spent_usd < self.budget_usd:
            return True
        # Enrich MEDIUM only for ambiguous cases (overlap in 0.5-0.8 range, etc.)
        if finding.severity.value == "medium" and "overlap" in finding.description.lower():
            return self._spent_usd < self.budget_usd * 0.5
        return False

    def enrich_batch(
        self,
        findings: list[Finding],
        config: AgentConfig,
    ) -> list[EnrichedFinding]:
        """Enrich multiple findings in a single LLM call (cost optimization)."""
        to_enrich = [f for f in findings if self.should_enrich(f)]
        if not to_enrich:
            return []

        # Batch up to max_batch_size findings per LLM call
        results = []
        for batch_start in range(0, len(to_enrich), self.max_batch_size):
            batch = to_enrich[batch_start:batch_start + self.max_batch_size]
            if self._spent_usd >= self.budget_usd:
                break

            prompt = self._build_batch_prompt(batch, config)
            cache_key = self.cache.key(prompt)
            cached = self.cache.get(cache_key)

            if cached:
                response = cached
            else:
                response = self.provider.complete(
                    prompt=prompt,
                    system=ENRICHMENT_SYSTEM,
                    max_tokens=2048,
                )
                self.cache.put(cache_key, response)
                self._spent_usd += response.cost_usd

            enriched = self._parse_batch_response(response, batch)
            results.extend(enriched)

        return results

    def _build_batch_prompt(self, findings: list[Finding], config: AgentConfig) -> str:
        # Builds a structured prompt with findings + relevant config context
        # Truncates context to keep within token budget
        ...

    def _parse_batch_response(self, response: LLMResponse, findings: list[Finding]) -> list[EnrichedFinding]:
        # Parses JSON response, maps back to original findings
        ...
```

### 3.6 Caching Strategy

```python
# src/lingdiag/llm/cache.py

import hashlib
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict


class ResponseCache:
    """Disk-based LLM response cache.

    Cache key: SHA-256 of (prompt + system + model).
    TTL: 7 days (findings for the same config don't change frequently).
    Location: ~/.cache/lingdiag/llm/
    """

    def __init__(self, cache_dir: Path | None = None, ttl_seconds: int = 7 * 86400):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "lingdiag" / "llm"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def key(self, prompt: str, system: str = "", model: str = "") -> str:
        content = f"{model}::{system}::{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, cache_key: str) -> LLMResponse | None:
        path = self.cache_dir / f"{cache_key}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        if time.time() - data.get("timestamp", 0) > self.ttl_seconds:
            path.unlink()
            return None
        response = LLMResponse(**{k: v for k, v in data.items() if k != "timestamp"})
        response.cached = True
        return response

    def put(self, cache_key: str, response: LLMResponse) -> None:
        path = self.cache_dir / f"{cache_key}.json"
        data = asdict(response)
        data["timestamp"] = time.time()
        path.write_text(json.dumps(data))
```

### 3.7 Cost Optimization Summary

| Strategy | Mechanism | Expected Savings |
|----------|-----------|-----------------|
| Heuristic gate | Only call LLM for flagged findings | 80-95% of configs need zero LLM calls |
| Severity filter | Skip INFO, gate MEDIUM | ~40% fewer LLM calls on flagged configs |
| Batching | Combine up to 10 findings per call | 5-10x fewer API calls |
| Response cache | SHA-256 keyed, 7-day TTL | Near-zero cost on re-scans |
| Budget cap | Hard USD limit per scan | Prevents runaway costs |
| Provider choice | Sonnet for enrichment, Haiku for triage | 3-6x cost reduction vs Opus |

**Estimated cost per scan:**
- Clean config (0 findings): $0.00 (no LLM calls)
- Typical bad config (5-15 findings, 3-5 worth enriching): $0.01-0.05
- Worst case (50+ findings, 10 enriched in batch): $0.10-0.25

---

## 4. CI/CD Integration

### 4.1 GitHub Action Design

```yaml
# .github/actions/lingdiag/action.yml

name: "Linguistic Diagnostics"
description: "Scan AI agent configs for H1-H7 language-to-action boundary failures"
branding:
  icon: "search"
  color: "orange"

inputs:
  files:
    description: "Glob pattern for config files to scan"
    required: false
    default: "**/*.yaml **/*.yml **/*.json"
  patterns:
    description: "Comma-separated pattern IDs to check (default: all)"
    required: false
    default: ""
  fail-under:
    description: "Minimum health score (0-100). Fails the check if below."
    required: false
    default: "0"
  min-severity:
    description: "Minimum severity to report (critical, high, medium, low, info)"
    required: false
    default: "info"
  llm-enrich:
    description: "Enable LLM enrichment for flagged findings"
    required: false
    default: "false"
  anthropic-api-key:
    description: "Anthropic API key for LLM enrichment (use secrets)"
    required: false
  annotate:
    description: "Add inline annotations to PR files"
    required: false
    default: "true"
  baseline-file:
    description: "Path to baseline scores for regression detection"
    required: false
    default: ".lingdiag-baseline.json"

outputs:
  health-score:
    description: "Overall health score (0-100)"
  finding-count:
    description: "Total number of findings"
  critical-count:
    description: "Number of critical findings"
  report-json:
    description: "Full JSON report (base64-encoded)"
```

### 4.2 GitHub Action Implementation Sketch

```yaml
# Workflow usage: .github/workflows/lingdiag.yml

name: Agent Config Diagnostics
on:
  pull_request:
    paths:
      - "**/*.yaml"
      - "**/*.yml"
      - "**/*.json"
      - "prompts/**"

permissions:
  checks: write
  pull-requests: write
  contents: read

jobs:
  lingdiag:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: roli-lpci/lingdiag-action@v1
        id: scan
        with:
          files: "agent-configs/**/*.yaml prompts/**/*.txt"
          fail-under: 70
          min-severity: medium
          annotate: true

      - name: Comment on PR
        if: steps.scan.outputs.finding-count > 0
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Linguistic Diagnostics\n\nHealth Score: **${process.env.HEALTH_SCORE}/100**\n\nFindings: ${process.env.FINDING_COUNT} (${process.env.CRITICAL_COUNT} critical)`
            })
```

### 4.3 Annotation Output Format (GitHub Checks API)

```
                    PR Diff View
    +-----------------------------------------+
    | agent_config.yaml                       |
    +-----------------------------------------+
    |  tools:                                 |
    |    - name: get_data                     |
    |      description: "Get data"     <------+-- [warning] H1: Tool Description
    |                                  |         Ambiguity: Very short description
    |                                  |         (8 chars). Expand to include
    |                                  |         purpose, when to use, expected
    |                                  |         input shape, output behavior.
    |                                  |
    |    - name: fetch_data            |
    |      description: "Get data      <------+-- [warning] H1: 78% word overlap
    |        from the system"          |         with 'get_data'. Differentiate
    |                                  |         by adding WHEN to use each.
    +-----------------------------------------+
```

Annotations are generated by mapping findings back to source file line numbers. This requires the parser to track line offsets during parsing, which the current parser does not do. Adding line tracking is a prerequisite for annotation support.

### 4.4 Pre-commit Hook Design

```yaml
# .pre-commit-config.yaml (user's repo)

repos:
  - repo: https://github.com/roli-lpci/lingdiag
    rev: v0.2.0
    hooks:
      - id: lingdiag
        name: Linguistic Diagnostics
        entry: lingdiag scan --fail-under 70 --min-severity medium --format terminal
        language: python
        types_or: [yaml, json]
        files: "(agent|tool|prompt|config).*\\.(yaml|yml|json|txt)$"
```

Implementation in `cli.py` -- no separate hook code needed. The existing CLI with `--fail-under` already provides the correct exit codes (0 = pass, 1 = fail).

### 4.5 Regression Tracking (Score Trending)

```python
# src/lingdiag/baseline.py

"""Track health scores over time for regression detection.

Baseline file format (.lingdiag-baseline.json):
{
  "version": 1,
  "generated": "2026-02-27T12:00:00Z",
  "files": {
    "agent_config.yaml": {
      "health_score": 85,
      "finding_count": 3,
      "findings_by_pattern": {"H1": 1, "H5": 2},
      "sha256": "abc123..."
    }
  }
}
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


def generate_baseline(scan_results: dict[str, list], output_path: Path) -> None:
    """Generate a baseline file from scan results."""
    baseline = {
        "version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }
    for filepath, findings in scan_results.items():
        content_hash = hashlib.sha256(Path(filepath).read_bytes()).hexdigest()
        baseline["files"][filepath] = {
            "health_score": compute_health_score(findings),
            "finding_count": len(findings),
            "findings_by_pattern": _count_by_pattern(findings),
            "sha256": content_hash,
        }
    output_path.write_text(json.dumps(baseline, indent=2))


def check_regression(
    current_results: dict[str, list],
    baseline_path: Path,
    tolerance: float = 5.0,
) -> list[dict]:
    """Compare current scan against baseline, return regressions."""
    if not baseline_path.exists():
        return []  # No baseline = no regression check

    baseline = json.loads(baseline_path.read_text())
    regressions = []

    for filepath, findings in current_results.items():
        current_score = compute_health_score(findings)
        baseline_entry = baseline.get("files", {}).get(filepath)
        if not baseline_entry:
            continue  # New file, no baseline

        baseline_score = baseline_entry["health_score"]
        if current_score < baseline_score - tolerance:
            regressions.append({
                "file": filepath,
                "baseline_score": baseline_score,
                "current_score": current_score,
                "delta": current_score - baseline_score,
                "new_patterns": _diff_patterns(
                    baseline_entry.get("findings_by_pattern", {}),
                    _count_by_pattern(findings),
                ),
            })

    return regressions
```

---

## 5. Data Pipeline

### 5.1 Architecture Overview

```
  User Scans (opt-in)
         |
         v
  +----------------+       +-------------------+
  | Anonymizer     | ----> | Collection Server |
  | (local)        |       | (API endpoint)    |
  +----------------+       +-------------------+
    - strip file paths            |
    - strip org names             v
    - hash tool names      +-------------------+
    - keep patterns +      | PostgreSQL / Neon  |
      structure only       | (findings DB)      |
                           +-------------------+
                                  |
                    +-------------+-------------+
                    |                           |
             +------v------+           +--------v-------+
             | Research     |           | Benchmark      |
             | Queries      |           | Framework      |
             | (analytics)  |           | (FP/FN rates)  |
             +-------------+           +----------------+
```

### 5.2 Anonymization Protocol

```python
# src/lingdiag/telemetry.py

from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, asdict
from .models import Finding, AgentConfig


@dataclass
class AnonymizedFinding:
    """A finding stripped of identifying information."""
    pattern_id: str
    severity: str
    location_type: str       # "tool", "system_prompt", "messages", "schema"
    description_template: str # Parameterized: "Tool has {n} char description"
    tool_count: int
    prompt_length_bucket: str # "short", "medium", "long", "very_long"
    message_count_bucket: str # "none", "few", "many", "excessive"
    config_format: str       # "yaml", "json", "text"
    lingdiag_version: str


def anonymize_finding(finding: Finding, config: AgentConfig) -> AnonymizedFinding:
    """Strip PII and identifying data from a finding."""
    # Determine location type without exposing names
    if finding.location.startswith("tool:"):
        location_type = "tool"
    elif "system_prompt" in finding.location:
        location_type = "system_prompt"
    elif "messages" in finding.location:
        location_type = "messages"
    else:
        location_type = "other"

    # Bucket prompt length (don't expose exact length)
    prompt_len = len(config.system_prompt)
    if prompt_len == 0:
        length_bucket = "none"
    elif prompt_len < 200:
        length_bucket = "short"
    elif prompt_len < 1000:
        length_bucket = "medium"
    elif prompt_len < 5000:
        length_bucket = "long"
    else:
        length_bucket = "very_long"

    # Bucket message count
    msg_count = len(config.messages)
    if msg_count == 0:
        msg_bucket = "none"
    elif msg_count < 10:
        msg_bucket = "few"
    elif msg_count < 50:
        msg_bucket = "many"
    else:
        msg_bucket = "excessive"

    # Templatize description (remove specific names/values)
    desc = re.sub(r"'[^']*'", "'{name}'", finding.description)
    desc = re.sub(r"\d+", "{n}", desc)

    return AnonymizedFinding(
        pattern_id=finding.pattern_id,
        severity=finding.severity.value,
        location_type=location_type,
        description_template=desc,
        tool_count=len(config.tools),
        prompt_length_bucket=length_bucket,
        message_count_bucket=msg_bucket,
        config_format="unknown",  # Set by caller
        lingdiag_version="0.1.0",
    )
```

### 5.3 Tool Description Corpus

For building a "good vs bad" training database:

```
  +-----------------------------------------------+
  |  Tool Description Corpus (Neon PostgreSQL)     |
  +-----------------------------------------------+
  | id          | SERIAL PRIMARY KEY               |
  | description | TEXT NOT NULL                     |
  | quality     | ENUM('good','bad','ambiguous')    |
  | tool_name   | TEXT (anonymized/hashed)          |
  | source      | ENUM('sample','wild','synthetic') |
  | h1_score    | FLOAT (0-1, ambiguity score)      |
  | word_count  | INT                               |
  | has_when    | BOOL (mentions when to use)       |
  | has_vs      | BOOL (mentions alternatives)      |
  | has_params  | BOOL (describes parameters)       |
  | has_output  | BOOL (describes output)           |
  | created_at  | TIMESTAMPTZ                       |
  | labels      | JSONB (manual annotation tags)    |
  +-----------------------------------------------+
```

Population strategy:
1. **Seed from samples/**: The existing 4 sample files contain 13 tool descriptions (5 good, 8 bad)
2. **Scrape open-source configs**: Parse tool definitions from public GitHub repos (LangChain, CrewAI, etc.)
3. **Synthetic generation**: Use LLM to generate bad/good pairs for each tool category
4. **Community contribution**: Accept PRs with new samples (anonymized)

### 5.4 Benchmark Framework

```python
# src/lingdiag/benchmark.py

"""Systematic false positive/negative measurement.

Golden files: tests/golden/
Each golden file is a config + expected findings manifest.

Manifest format (YAML sidecar):
  # tests/golden/h1_overlap.yaml.expect
  expected_findings:
    - pattern: H1
      severity: high
      location_contains: "get_data vs fetch_data"
    - pattern: H1
      severity: critical
      location_contains: "no_desc_tool"

  expected_clean:
    - pattern: H1
      location_contains: "search_knowledge_base"

  metadata:
    description: "Tests H1 overlap detection and missing description"
    version: "1.0"
    author: "roli"
"""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import yaml

from .scanner import scan_file
from .models import Finding


@dataclass
class BenchmarkResult:
    file: str
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float


def run_benchmark(golden_dir: Path) -> list[BenchmarkResult]:
    """Run all golden files and compute precision/recall/F1."""
    results = []
    for config_path in golden_dir.glob("*"):
        if config_path.suffix == ".expect":
            continue  # Skip manifest files

        expect_path = config_path.with_suffix(config_path.suffix + ".expect")
        if not expect_path.exists():
            continue

        manifest = yaml.safe_load(expect_path.read_text())
        findings = scan_file(config_path)
        result = _evaluate(config_path, findings, manifest)
        results.append(result)

    return results


def _evaluate(path: Path, findings: list[Finding], manifest: dict) -> BenchmarkResult:
    """Compare actual findings against expected manifest."""
    expected = manifest.get("expected_findings", [])
    expected_clean = manifest.get("expected_clean", [])

    tp = 0  # Expected finding present
    fn = 0  # Expected finding missing
    fp = 0  # Unexpected finding present
    tn = 0  # Expected clean, actually clean

    for exp in expected:
        matched = any(
            f.pattern_id == exp["pattern"]
            and f.severity.value == exp.get("severity", f.severity.value)
            and exp.get("location_contains", "") in f.location
            for f in findings
        )
        if matched:
            tp += 1
        else:
            fn += 1

    for exp_clean in expected_clean:
        false_flag = any(
            f.pattern_id == exp_clean["pattern"]
            and exp_clean.get("location_contains", "") in f.location
            for f in findings
        )
        if false_flag:
            fp += 1
        else:
            tn += 1

    # Count unexpected findings as FP
    expected_sigs = {
        (e["pattern"], e.get("location_contains", ""))
        for e in expected
    }
    for f in findings:
        if not any(
            f.pattern_id == sig[0] and sig[1] in f.location
            for sig in expected_sigs
        ):
            # Check if it's expected to be clean
            is_expected_clean = any(
                f.pattern_id == ec["pattern"]
                and ec.get("location_contains", "") in f.location
                for ec in expected_clean
            )
            if not is_expected_clean:
                fp += 1  # Truly unexpected

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return BenchmarkResult(
        file=str(path),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        f1=f1,
    )
```

---

## 6. Testing Strategy

### 6.1 Current Coverage Assessment

| Area | Tests | Coverage | Gaps |
|------|-------|----------|------|
| Pattern detectors | 27 | Good for happy path | No edge cases for regex boundaries, Unicode, very large inputs |
| Parsers | 10 | Covers YAML/JSON/text | No malformed input tests, no TOML/OpenAPI |
| Scanner | 8 | Basic flow covered | `scan_directory` has a bug (untested exception path), no parallel scan tests |
| CLI | 11 | Good end-to-end | No test for `--version`, no invalid argument tests |
| Report | 0 (indirect only) | Via CLI tests | No direct format_terminal/format_markdown unit tests |
| Health score | 4 | Good | No boundary value tests (score exactly 0, exactly 100) |

### 6.2 Property-Based Testing (Parsers)

```python
# tests/test_parsers_property.py

"""Property-based tests: any valid YAML/JSON should parse without crash."""

from hypothesis import given, strategies as st, settings
import yaml
import json

from lingdiag.parsers import parse_yaml, parse_json, parse_text
from lingdiag.patterns import AgentConfig


# Strategy: arbitrary valid YAML strings
yaml_text = st.one_of(
    st.text(min_size=0, max_size=10000),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P"))),
        values=st.recursive(
            st.one_of(st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text()),
            lambda children: st.lists(children, max_size=5) | st.dictionaries(
                st.text(min_size=1, max_size=20), children, max_size=5
            ),
        ),
        max_size=10,
    ).map(yaml.dump),
)


@given(text=yaml_text)
@settings(max_examples=500, deadline=2000)
def test_parse_yaml_never_crashes(text):
    """Any input to parse_yaml should either return AgentConfig or raise yaml.YAMLError."""
    try:
        result = parse_yaml(text)
        assert isinstance(result, AgentConfig)
    except yaml.YAMLError:
        pass  # Expected for invalid YAML


@given(data=st.dictionaries(
    keys=st.text(min_size=1, max_size=30),
    values=st.recursive(
        st.one_of(st.none(), st.booleans(), st.integers(), st.text()),
        lambda children: st.lists(children, max_size=3) | st.dictionaries(
            st.text(min_size=1, max_size=10), children, max_size=3
        ),
    ),
    max_size=10,
))
@settings(max_examples=500, deadline=2000)
def test_parse_json_never_crashes(data):
    """Any valid JSON object should parse into AgentConfig."""
    text = json.dumps(data)
    result = parse_json(text)
    assert isinstance(result, AgentConfig)


@given(text=st.text(min_size=0, max_size=50000))
@settings(max_examples=200, deadline=1000)
def test_parse_text_never_crashes(text):
    """Any text input should parse into AgentConfig."""
    result = parse_text(text)
    assert isinstance(result, AgentConfig)
    assert result.system_prompt == text.strip()


@given(text=st.text(min_size=0, max_size=50000))
@settings(max_examples=200, deadline=1000)
def test_all_detectors_handle_arbitrary_text(text):
    """No detector should crash on arbitrary text input."""
    from lingdiag.patterns import PATTERNS
    config = AgentConfig(system_prompt=text)
    for pid, info in PATTERNS.items():
        findings = info["detect"](config)
        assert isinstance(findings, list)
        for f in findings:
            assert f.pattern_id == pid
```

### 6.3 Adversarial Testing

```python
# tests/test_adversarial.py

"""Configs designed to break detectors."""

import pytest
from lingdiag.patterns import AgentConfig, ToolDef, detect_h1, detect_h2, detect_h5
from lingdiag.scanner import scan_config, compute_health_score


class TestAdversarialH1:
    """Edge cases for tool description ambiguity detection."""

    def test_unicode_tool_description(self):
        """Non-Latin tool descriptions should not crash."""
        config = AgentConfig(tools=[
            ToolDef(name="search", description="Buscar datos en la base de datos del sistema"),
        ])
        findings = detect_h1(config)
        # Should not flag as "short" (40+ chars)
        assert not any("very short" in f.description for f in findings)

    def test_thousand_tools(self):
        """H1 pairwise comparison should handle 1000 tools without timeout."""
        tools = [
            ToolDef(name=f"tool_{i}", description=f"Unique description for tool number {i} doing specific thing {i}")
            for i in range(1000)
        ]
        config = AgentConfig(tools=tools)
        findings = detect_h1(config)
        # Should complete (performance test)
        assert isinstance(findings, list)

    def test_identical_tools(self):
        """Two tools with byte-identical descriptions."""
        desc = "Search the database for user records"
        config = AgentConfig(tools=[
            ToolDef(name="search_v1", description=desc),
            ToolDef(name="search_v2", description=desc),
        ])
        findings = detect_h1(config)
        assert any("overlap" in f.description.lower() for f in findings)

    def test_empty_string_vs_whitespace(self):
        """Whitespace-only description should be treated as missing."""
        config = AgentConfig(tools=[
            ToolDef(name="ghost", description="   \t\n  "),
        ])
        findings = detect_h1(config)
        assert any(f.severity.value == "critical" for f in findings)

    def test_description_is_just_the_name(self):
        """Description that just repeats the tool name."""
        config = AgentConfig(tools=[
            ToolDef(name="get_user", description="get user"),
        ])
        findings = detect_h1(config)
        assert any("short" in f.description.lower() or "vague" in f.description.lower() for f in findings)


class TestAdversarialH2:
    """Edge cases for constraint scaffolding detection."""

    def test_constraint_in_comments(self):
        """Constraint keyword in a code comment should still count."""
        config = AgentConfig(
            system_prompt="# max_iterations: 5\nDo the thing.",
            tools=[ToolDef(name="t", description="A tool for doing specific operations")],
        )
        findings = detect_h2(config)
        missing = [f for f in findings if "no termination" in f.description.lower()]
        assert len(missing) == 0  # Should recognize the constraint

    def test_negated_constraint(self):
        """'there is no max_iterations' should NOT count as having a constraint."""
        config = AgentConfig(
            system_prompt="There is no max_iterations limit. Keep going forever.",
            tools=[ToolDef(name="t", description="A tool for doing specific operations")],
        )
        findings = detect_h2(config)
        # Current implementation will incorrectly match -- this is a known limitation
        # to document as a future improvement (requires NLP negation detection)


class TestAdversarialRegex:
    """Regex edge cases that could cause ReDoS or false matches."""

    def test_nested_braces_in_template(self):
        """Deeply nested braces should not cause catastrophic backtracking."""
        prompt = "{{{{" * 100 + "}}}}" * 100
        config = AgentConfig(system_prompt=prompt)
        findings = scan_config(config)  # Should complete quickly
        assert isinstance(findings, list)

    def test_very_long_single_line(self):
        """A single line of 1MB should not cause issues."""
        prompt = "a" * 1_000_000
        config = AgentConfig(system_prompt=prompt)
        findings = scan_config(config)
        assert isinstance(findings, list)

    def test_null_bytes_in_prompt(self):
        """Null bytes should not crash regex."""
        prompt = "You are helpful.\x00Do not crash.\x00"
        config = AgentConfig(system_prompt=prompt)
        findings = scan_config(config)
        assert isinstance(findings, list)
```

### 6.4 Golden File (Regression) Tests

```python
# tests/test_golden.py

"""Golden file tests: expected findings for each sample file.

Each sample in samples/ has a corresponding .expect sidecar defining
exact expected findings. If detector logic changes, golden files
surface regressions immediately.
"""

import json
import yaml
import pytest
from pathlib import Path

from lingdiag.scanner import scan_file
from lingdiag.patterns import Finding

SAMPLES_DIR = Path(__file__).parent.parent / "samples"
GOLDEN_DIR = Path(__file__).parent / "golden"


def load_expectation(config_name: str) -> dict:
    """Load the expected findings manifest for a sample file."""
    expect_path = GOLDEN_DIR / f"{config_name}.expect.yaml"
    if not expect_path.exists():
        pytest.skip(f"No golden file: {expect_path}")
    return yaml.safe_load(expect_path.read_text())


@pytest.mark.parametrize("sample_file", [
    "clean_config.yaml",
    "bad_tool_descriptions.yaml",
    "bad_agent_config.json",
    "bad_system_prompt.txt",
    "mixed_issues.yaml",
])
def test_golden_findings(sample_file):
    """Verify findings match golden expectations."""
    findings = scan_file(SAMPLES_DIR / sample_file)
    manifest = load_expectation(sample_file)

    expected = manifest.get("expected_findings", [])
    for exp in expected:
        matched = any(
            f.pattern_id == exp["pattern"]
            and f.severity.value == exp.get("severity", f.severity.value)
            and exp.get("location_contains", "") in f.location
            for f in findings
        )
        assert matched, (
            f"Expected finding not found: pattern={exp['pattern']}, "
            f"severity={exp.get('severity')}, "
            f"location_contains={exp.get('location_contains')}\n"
            f"Actual findings: {[(f.pattern_id, f.severity.value, f.location) for f in findings]}"
        )

    # Verify no findings for expected-clean items
    expected_clean = manifest.get("expected_clean", [])
    for ec in expected_clean:
        false_flag = any(
            f.pattern_id == ec["pattern"]
            and ec.get("location_contains", "") in f.location
            for f in findings
        )
        assert not false_flag, (
            f"False positive: pattern={ec['pattern']} found at "
            f"location containing '{ec.get('location_contains')}' "
            f"but was expected to be clean"
        )
```

### 6.5 Testing Pyramid Summary

```
                    /\
                   /  \          Integration (CI):
                  / CI  \        - GitHub Action E2E
                 / Tests \       - Pre-commit hook
                /----------\
               /  Golden    \    Regression:
              /   File       \   - 5+ samples with .expect manifests
             /    Tests       \  - Catches detector logic changes
            /------------------\
           /   Property-Based   \  Robustness:
          /    (Hypothesis)      \ - 1500+ generated inputs
         /                        \ - Parser crash resistance
        /                          \ - Detector crash resistance
       /----------------------------\
      /      Unit Tests (pytest)     \  Core logic:
     /        75 existing tests       \ - Each H-pattern
    /          + adversarial suite      \ - Parsers, scanner, CLI
   /------------------------------------\
```

---

## 7. Phased Implementation Plan

### Phase 0: Foundation Fixes (1-2 days)

**Priority: Fix bugs and prep for extension**

| Task | File | Effort |
|------|------|--------|
| Fix `scan_directory` exception handler bug (line 75) | `scanner.py` | 15 min |
| Extract `Severity`, `Finding`, `AgentConfig`, `ToolDef` into `models.py` | `patterns.py` -> `models.py` | 30 min |
| Remove hardcoded pattern choices from CLI (derive from PATTERNS keys) | `cli.py` line 30 | 15 min |
| Add direct unit tests for `format_terminal` and `format_markdown` | `test_report.py` (new) | 45 min |
| Add line number tracking to parsers (prep for annotations) | `parsers.py` | 2 hrs |

### Phase 1: Plugin Architecture (3-5 days)

**Priority: Make the pattern system extensible**

| Task | New File | Effort |
|------|----------|--------|
| Create `interfaces.py` with Protocol definitions | `interfaces.py` | 1 hr |
| Create `registry.py` with entry point discovery | `registry.py` | 2 hrs |
| Split `patterns.py` into `patterns/h1.py`...`patterns/h7.py` | `patterns/` dir | 3 hrs |
| Wrap existing detectors in PatternDetector classes | `patterns/*.py` | 2 hrs |
| Wire scanner to use registry instead of PATTERNS dict | `scanner.py` | 1 hr |
| Register built-in patterns via own entry points | `pyproject.toml` | 30 min |
| Add pattern metadata: description, category, version | `patterns/*.py` | 1 hr |
| Update tests for new structure | `tests/` | 2 hrs |

Deliverable: `pip install lingdiag-yourplugin` works.

### Phase 2: Testing Infrastructure (2-3 days)

**Priority: Confidence to refactor and extend**

| Task | Effort |
|------|--------|
| Add `hypothesis` to dev dependencies | 15 min |
| Write property-based parser tests | 2 hrs |
| Write adversarial detector tests | 3 hrs |
| Create golden file expectations for all 5 samples | 2 hrs |
| Set up `tests/golden/` directory with `.expect.yaml` files | 1 hr |
| Add benchmark runner (`lingdiag benchmark`) CLI subcommand | 2 hrs |
| Add `pytest --benchmark` performance regression tests | 1 hr |

Deliverable: `pytest tests/` runs 200+ tests including property-based.

### Phase 3: CI/CD Integration (2-3 days)

**Priority: Make lingdiag usable in pipelines**

| Task | Effort |
|------|--------|
| Add SARIF output format (GitHub Code Scanning) | 3 hrs |
| Add `--baseline` and `--update-baseline` CLI flags | 2 hrs |
| Implement `baseline.py` for regression tracking | 2 hrs |
| Create GitHub Action (`action.yml` + Dockerfile) | 3 hrs |
| Add pre-commit hook configuration | 1 hr |
| Write GitHub Action integration tests | 2 hrs |
| Publish to GitHub Marketplace | 1 hr |

Deliverable: Users can add `lingdiag` to their CI in 5 minutes.

### Phase 4: LLM Enrichment (5-7 days)

**Priority: Premium feature, differentiated value**

| Task | Effort |
|------|--------|
| Create `llm/` subpackage with provider protocol | 1 hr |
| Implement AnthropicProvider | 3 hrs |
| Implement OpenAIProvider | 2 hrs |
| Implement OllamaProvider (local models) | 2 hrs |
| Build response cache (`~/.cache/lingdiag/llm/`) | 2 hrs |
| Build FindingEnricher with batching + budget | 4 hrs |
| Add `--llm-enrich`, `--llm-provider`, `--llm-budget` CLI flags | 1 hr |
| Write enrichment prompt templates (per pattern) | 3 hrs |
| Test with real configs, calibrate thresholds | 4 hrs |
| Add `anthropic`, `openai`, `ollama` as optional dependencies | 30 min |

Deliverable: `lingdiag scan config.yaml --llm-enrich --llm-provider anthropic`

### Phase 5: Data Pipeline & Research (3-5 days)

**Priority: Long-term intelligence gathering**

| Task | Effort |
|------|--------|
| Implement anonymization protocol | 2 hrs |
| Create Neon DB schema for findings corpus | 1 hr |
| Create Neon DB schema for tool description corpus | 1 hr |
| Build opt-in telemetry (`--telemetry` flag, disabled by default) | 3 hrs |
| Seed tool description corpus from samples/ | 2 hrs |
| Build corpus scraper for public GitHub repos | 4 hrs |
| Build benchmark dashboard (FP/FN rates over time) | 3 hrs |

Deliverable: Research database with 1000+ tool descriptions.

### Phase 6: New Patterns (ongoing)

**Priority: Expanding diagnostic coverage**

| Pattern | Description | Complexity |
|---------|-------------|------------|
| H8: Instruction-Schema Conflict | System prompt says one thing, schema implies another | Medium |
| H9: Tool Parameter Overload | Too many parameters without grouping/description | Easy |
| H10: Circular Tool Dependencies | Tool A says "use B first", B says "use A first" | Medium |
| H11: Temperature-Sensitive Instructions | Instructions that only work at temp=0 but config uses temp>0 | Hard (needs config context) |
| H12: Context Window Budget Estimation | Prompt + tools + schema approaching model's context limit | Medium |
| E1-E4: Epistemic Failure Patterns | Model-level reasoning failures (from taxonomy) | Hard (may need LLM integration) |

---

## Summary: Module Dependency Graph (Target State)

```
                         lingdiag
                            |
         +------------------+------------------+
         |                  |                  |
      models.py        interfaces.py      registry.py
    (data types)       (Protocol defs)   (plugin discovery)
         |                  |                  |
         +--------+---------+---------+--------+
                  |                   |
            patterns/             parsers/
          h1.py ... h7.py       yaml_.py, json_.py
          (PatternDetector)     text_.py, toml_.py
                |              (ConfigParser)
                |                   |
                +--------+--------+
                         |
                    scanner.py
                  (orchestration)
                    |         |
              report/       llm/
            terminal.py   provider.py
            markdown.py   anthropic_.py
            sarif.py      openai_.py
            (Reporter)    enricher.py
                |         cache.py
                +----+----+
                     |
                  cli.py
                (user interface)
                     |
              +-----------+
              |           |
          baseline.py  telemetry.py
         (regression)  (anonymized
          tracking)     collection)
```

---

## Appendix A: Known Bugs

1. **`scanner.py:75`** -- Exception handler references `findings` before assignment. If `parse_file()` raises, the variable is unbound. The `__import__` fallback for Severity is also fragile.

2. **`cli.py:30`** -- Pattern choices are hardcoded as `["H1"..."H7"]`. Adding H8 requires editing this list manually. Should derive from `PATTERNS.keys()`.

3. **`patterns.py:453-454`** -- H6 template variable detection finds `{var}` patterns but the subsequent type-hint check has a dead `pass` branch that does nothing. Either implement the check or remove the dead code.

## Appendix B: Design Decisions

| Decision | Rationale |
|----------|-----------|
| Protocol over ABC | No inheritance required. Third-party plugins just implement the shape. Structural subtyping aligns with Python's "duck typing" philosophy. |
| Entry points over config files | Standard Python packaging mechanism. Users `pip install` a plugin and it auto-registers. No YAML/JSON config to maintain. |
| Disk cache over memory cache | LLM responses persist across CLI invocations. CI pipelines can mount a cache volume. 7-day TTL prevents stale results. |
| SARIF over custom format | SARIF is the GitHub Code Scanning standard. One format gets both GitHub annotations AND VS Code integration for free. |
| Anonymized telemetry | Privacy-first. No file paths, no tool names, no prompt content. Only structural metadata (counts, buckets, pattern IDs). Opt-in only. |
| Neon for corpus DB | Already in the stack (MCP integration available). Branching model useful for A/B testing detector changes against the corpus. |
