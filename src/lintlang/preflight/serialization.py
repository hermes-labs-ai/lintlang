"""Canonical, privacy-safe serialization for preflight results."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    ContextEvidence,
    Evidence,
    Finding,
    PreflightResult,
    PromptEvidence,
)


def _evidence_to_dict(evidence: Evidence, include_snippets: bool) -> dict[str, Any]:
    if isinstance(evidence, PromptEvidence):
        payload: dict[str, Any] = {
            "source": "prompt",
            "span": {"start": evidence.span.start, "end": evidence.span.end},
            "sha256": evidence.sha256,
            "codepoints": evidence.codepoints,
            "utf8_bytes": evidence.utf8_bytes,
        }
        if include_snippets:
            payload["snippet"] = evidence._snippet
        return payload
    if isinstance(evidence, ContextEvidence):
        payload = {
            "source": "context",
            "json_pointer": evidence.json_pointer,
            "sha256": evidence.sha256,
            "codepoints": evidence.codepoints,
            "utf8_bytes": evidence.utf8_bytes,
        }
        if include_snippets:
            payload["value"] = evidence._value
        return payload
    raise TypeError("unsupported evidence type")


def _finding_to_dict(finding: Finding, include_snippets: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "finding_id": finding.finding_id,
        "rule_id": finding.rule_id,
        "rule_version": finding.rule_version,
        "label": finding.label,
        "scope": finding.scope.value,
        "trigger_kind": finding.trigger_kind,
        "trigger": _evidence_to_dict(finding.trigger, include_snippets),
        "proposition_kind": finding.proposition_kind,
        "proposition": None
        if finding.proposition is None
        else _evidence_to_dict(finding.proposition, include_snippets),
        "additional_evidence": [_evidence_to_dict(item, include_snippets) for item in finding.additional_evidence],
        "risk": finding.risk,
        "explanation": finding.explanation,
        "suggestion": finding.suggestion,
        "confidence": finding.confidence.value,
        "maturity": finding.maturity.value,
        "enforcement": finding.enforcement.value,
        "related_output_modes": [
            {"mode": mode, "relationship": "inspired_by_not_equivalent"} for mode in finding.related_output_modes
        ],
        "correction_ids": list(finding.correction_ids),
        "overridden": finding.overridden,
    }
    if finding.override_reason_sha256 is not None:
        payload["override_reason_sha256"] = finding.override_reason_sha256
    return payload


def result_to_dict(
    result: PreflightResult,
    *,
    include_snippets: bool = False,
    include_fingerprint: bool = True,
) -> dict[str, Any]:
    """Return the wire object without timestamps or implicit raw text."""

    corrections: list[dict[str, Any]] = []
    for correction in result.corrections:
        edits: list[dict[str, Any]] = []
        for edit in correction.edits:
            serialized_edit: dict[str, Any] = {
                "start": edit.start,
                "end": edit.end,
                "replacement_sha256": edit.replacement_sha256,
                "replacement_codepoints": edit.replacement_codepoints,
                "replacement_utf8_bytes": edit.replacement_utf8_bytes,
            }
            if include_snippets:
                serialized_edit["replacement"] = edit._replacement
            edits.append(serialized_edit)
        serialized_diff: dict[str, Any] = {
            "sha256": correction.diff_sha256,
            "utf8_bytes": correction.diff_utf8_bytes,
        }
        if include_snippets:
            serialized_diff["text"] = correction._diff
        corrections.append(
            {
                "correction_id": correction.correction_id,
                "finding_id": correction.finding_id,
                "source_sha256": correction.source_sha256,
                "result_sha256": correction.result_sha256,
                "schema_version": correction.schema_version,
                "engine_version": correction.engine_version,
                "rule_bundle_version": correction.rule_bundle_version,
                "edits": edits,
                "diff": serialized_diff,
                "meaning_preservation": correction.meaning_preservation.value,
                "requires_relint": correction.requires_relint,
            }
        )

    payload: dict[str, Any] = {
        "schema_id": result.schema_id,
        "schema_version": result.schema_version,
        "engine_version": result.engine_version,
        "rule_bundle_version": result.rule_bundle_version,
        "status": result.status.value,
        "exit_code": result.exit_code,
        "input": {
            "sha256": result.input.sha256,
            "codepoints": result.input.codepoints,
            "utf8_bytes": result.input.utf8_bytes,
            "context_sha256": result.input.context_sha256,
            "context_utf8_bytes": result.input.context_utf8_bytes,
            "language": result.input.language,
            "snippets_included": include_snippets,
        },
        "coverage": [
            {
                "component": item.component,
                "required": item.required,
                "state": item.state.value,
                "reason": item.reason,
            }
            for item in result.coverage
        ],
        "findings": [_finding_to_dict(finding, include_snippets) for finding in result.findings],
        "corrections": corrections,
        "actions": [
            {
                "id": action.id.value,
                "available": action.available,
                "precondition": action.precondition,
            }
            for action in result.actions
        ],
        "diagnostics": [
            {
                **{
                    "code": diagnostic.code,
                    "severity": diagnostic.severity.value,
                    "message": diagnostic.message,
                },
                **({"context_pointer": diagnostic.context_pointer} if diagnostic.context_pointer is not None else {}),
            }
            for diagnostic in result.diagnostics
        ],
        "lineage": {
            "parent_fingerprint": result.parent_fingerprint,
            "applied_correction_id": result.applied_correction_id,
            "relint_depth": result.relint_depth,
        },
        "network": {"attempted": result.network_attempted},
        "storage": {"persisted": result.storage_persisted},
    }
    if include_fingerprint:
        payload["fingerprint"] = result.fingerprint
    return payload


def result_to_json(
    result: PreflightResult,
    *,
    include_snippets: bool = False,
    indent: int | None = None,
) -> str:
    separators = None if indent is not None else (",", ":")
    return json.dumps(
        result_to_dict(result, include_snippets=include_snippets),
        sort_keys=True,
        separators=separators,
        ensure_ascii=False,
        indent=indent,
    )
