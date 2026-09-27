"""GitLab Code Quality serialization for source-located repository findings."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import unquote

from .models import Finding, Severity
from .sarif import repository_artifact_uri
from .scanner import ScanResult

_SEVERITIES = {
    Severity.CRITICAL: "blocker",
    Severity.HIGH: "critical",
    Severity.MEDIUM: "major",
    Severity.LOW: "minor",
    Severity.INFO: "info",
}


def format_gitlab(
    results: Mapping[str, ScanResult],
    *,
    repository_root: str | Path,
    source_base: str | Path | None = None,
    show_suggestions: bool = True,
) -> tuple[str, int]:
    """Return a Code Quality JSON array and the count lacking a source line.

    GitLab requires an integer line. An unlocated finding remains part of the
    scanner verdict, but cannot honestly be represented in this report.
    """
    located: list[tuple[str, Finding, str]] = []
    omitted = 0
    seen_paths: set[str] = set()
    for key, result in results.items():
        if result.input_error is not None:
            continue
        path = unquote(repository_artifact_uri(
            result.file or key,
            repository_root=repository_root,
            source_base=source_base,
        ))
        if path in seen_paths:
            continue
        seen_paths.add(path)
        for finding in result.structural_findings:
            if finding.source_region is None:
                omitted += 1
                continue
            # Python extractor locations carry the invocation path and source
            # line. Neither belongs in a fingerprint that tracks an unchanged
            # violation after preceding source lines move.
            location = finding.location
            if Path(result.file).suffix.lower() == ".py" and location.startswith(f"{result.file}:"):
                location = "python-source"
            located.append((path, finding, location))

    located.sort(key=lambda item: (
        item[0], item[1].source_region.start_line, item[1].code,
        item[1].description, item[2],
    ))
    occurrences: Counter[tuple[str, str, str, str]] = Counter()
    entries: list[dict[str, object]] = []
    for path, finding, location in located:
        line = finding.source_region.start_line
        base = (path, finding.code, location, finding.description)
        ordinal = occurrences[base]
        occurrences[base] += 1
        identity = json.dumps(
            [*base, ordinal],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        description = finding.description
        if show_suggestions and finding.suggestion:
            description += f" Suggested action: {finding.suggestion}"
        entries.append({
            "description": description,
            "check_name": finding.code,
            "fingerprint": hashlib.sha256(identity).hexdigest(),
            "severity": _SEVERITIES[finding.severity],
            "location": {"path": path, "lines": {"begin": line}},
        })
    return json.dumps(entries, indent=2) + "\n", omitted
