"""lintlang — Linguistic linter for AI agent systems.

Catches vague tool descriptions, missing constraints, schema mismatches,
and other language-level failures in AI agent configurations.

Quick start::

    from lintlang import scan_file, compute_verdict

    result = scan_file("config.yaml")
    verdict = compute_verdict(result.structural_findings)
    print(f"Verdict: {verdict}")  # PASS, REVIEW, or FAIL
    for f in result.structural_findings:
        print(f"  [{f.severity.value}] {f.description}")
"""

__version__ = "0.2.0"

from lintlang.herm import HermResult, score_text
from lintlang.patterns import AgentConfig, Finding, Severity
from lintlang.report import compute_verdict
from lintlang.scanner import ScanResult, scan_config, scan_directory, scan_file

__all__ = [
    "__version__",
    "scan_file",
    "scan_directory",
    "scan_config",
    "compute_verdict",
    "ScanResult",
    "HermResult",
    "AgentConfig",
    "Finding",
    "Severity",
    "score_text",
]
