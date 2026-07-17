"""Provider-neutral preflight CLI integration.

This module is additive: the existing repository ``scan`` command keeps its
parser, output, and exit behavior. Boundary failures use static diagnostic codes
so raw input, context, and exception text cannot leak into default output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from .preflight import (
    BoundaryErrorCode,
    ConstraintKind,
    ContextBinding,
    ContextConstraint,
    ContextContract,
    ContextRequirement,
    ContextSource,
    CorrectionError,
    Delivery,
    Override,
    PreflightPolicy,
    PreflightRequest,
    PreflightResult,
    apply_correction,
    boundary_error,
    preflight_text,
)
from .preflight.models import MAX_CONTEXT_UTF8_BYTES, MAX_PROMPT_UTF8_BYTES


class _ContextDecodeError(ValueError):
    pass


def configure_preflight_parser(subparsers: argparse._SubParsersAction) -> None:
    """Add the isolated preflight command without changing scan arguments."""

    parser = subparsers.add_parser(
        "preflight",
        help="Inspect one prompt plus explicit context before an agent sees it",
    )
    parser.add_argument(
        "source",
        nargs="?",
        default="-",
        help="UTF-8 prompt file, or '-' for standard input (default: '-')",
    )
    parser.add_argument(
        "--context",
        type=Path,
        default=None,
        help="Provider-neutral context contract as UTF-8 JSON",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Declared prompt language (v1 required coverage supports 'en')",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=("terminal", "json"),
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--include-snippets",
        action="store_true",
        help="Explicitly include raw evidence, context values, replacements, and diffs",
    )
    parser.add_argument(
        "--apply",
        metavar="CORRECTION_ID",
        help="Apply one source-hash-bound correction in memory and print corrected text",
    )
    parser.add_argument(
        "--override",
        metavar="FINDING_ID",
        help="Record an intentional pass override without erasing the finding or status",
    )
    parser.add_argument(
        "--reason",
        help="Non-empty reason required with --override; only its SHA-256 is serialized",
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_limited(stream: BinaryIO | TextIO, limit: int) -> bytes:
    """Read at most one byte beyond the governed limit.

    The engine owns the resulting oversized-input ERROR. Not consuming an
    unbounded stream protects the CLI boundary from attacker-controlled memory.
    """

    data = stream.read(limit + 1)
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def _read_prompt(source: str) -> tuple[bytes, BoundaryErrorCode | None]:
    if source == "-":
        if sys.stdin.isatty():
            return b"", BoundaryErrorCode.INPUT_READ_FAILED
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        try:
            return _read_limited(stream, MAX_PROMPT_UTF8_BYTES), None
        except (OSError, UnicodeError):
            return b"", BoundaryErrorCode.INPUT_READ_FAILED

    path = Path(source)
    try:
        with path.open("rb") as stream:
            return _read_limited(stream, MAX_PROMPT_UTF8_BYTES), None
    except OSError:
        return b"", BoundaryErrorCode.INPUT_READ_FAILED


def _read_context(path: Path | None) -> tuple[bytes, BoundaryErrorCode | None]:
    if path is None:
        return b"", None
    try:
        with path.open("rb") as stream:
            return _read_limited(stream, MAX_CONTEXT_UTF8_BYTES), None
    except OSError:
        return b"", BoundaryErrorCode.CONTEXT_READ_FAILED


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _ContextDecodeError("duplicate JSON object key")
        result[key] = value
    return result


def _expect_object(value: Any, *, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed:
        raise _ContextDecodeError("invalid context object shape")
    return value


def _context_from_json(raw: bytes) -> ContextContract:
    if not raw:
        return ContextContract()
    if len(raw) > MAX_CONTEXT_UTF8_BYTES:
        raise _ContextDecodeError("context exceeds byte limit")
    try:
        decoded = raw.decode("utf-8", errors="strict")
        value = json.loads(decoded, object_pairs_hook=_reject_duplicate_object_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, _ContextDecodeError) as exc:
        raise _ContextDecodeError("invalid context JSON") from exc

    root = _expect_object(value, allowed={"requirements", "bindings", "constraints"})
    requirements_raw = root.get("requirements", [])
    bindings_raw = root.get("bindings", [])
    constraints_raw = root.get("constraints", [])
    if not all(isinstance(item, list) for item in (requirements_raw, bindings_raw, constraints_raw)):
        raise _ContextDecodeError("context collections must be arrays")

    requirements: list[ContextRequirement] = []
    for item in requirements_raw:
        obj = _expect_object(item, allowed={"key", "required", "description"})
        key = obj.get("key")
        required = obj.get("required", True)
        description = obj.get("description")
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(required, bool)
            or (description is not None and not isinstance(description, str))
        ):
            raise _ContextDecodeError("invalid context requirement")
        requirements.append(ContextRequirement(key=key, required=required, description=description))

    bindings: list[ContextBinding] = []
    for item in bindings_raw:
        obj = _expect_object(item, allowed={"key", "value", "source", "delivery"})
        key = obj.get("key")
        binding_value = obj.get("value")
        if not isinstance(key, str) or not key.strip() or not isinstance(binding_value, str):
            raise _ContextDecodeError("invalid context binding")
        try:
            source = ContextSource(obj.get("source", ContextSource.CALLER.value))
            delivery = Delivery(obj.get("delivery", Delivery.SIDE_CHANNEL.value))
        except ValueError as exc:
            raise _ContextDecodeError("invalid binding enum") from exc
        bindings.append(
            ContextBinding(
                key=key,
                value=binding_value,
                source=source,
                delivery=delivery,
            )
        )

    constraints: list[ContextConstraint] = []
    for item in constraints_raw:
        obj = _expect_object(item, allowed={"kind", "value"})
        kind_raw = obj.get("kind")
        constraint_value = obj.get("value")
        if not isinstance(kind_raw, str) or not isinstance(constraint_value, str):
            raise _ContextDecodeError("invalid context constraint")
        try:
            kind = ConstraintKind(kind_raw.upper())
        except ValueError as exc:
            raise _ContextDecodeError("invalid constraint kind") from exc
        constraints.append(ContextConstraint(kind=kind, value=constraint_value))

    return ContextContract(
        requirements=tuple(requirements),
        bindings=tuple(bindings),
        constraints=tuple(constraints),
    )


def _boundary_result(
    code: BoundaryErrorCode,
    *,
    prompt_bytes: bytes,
    context_bytes: bytes,
    language: str,
) -> PreflightResult:
    return boundary_error(
        code,
        input_sha256=_sha256(prompt_bytes),
        input_utf8_bytes=len(prompt_bytes),
        context_sha256=_sha256(context_bytes),
        context_utf8_bytes=len(context_bytes),
        language=language,
    )


def _location_label(evidence: dict[str, Any]) -> str:
    if evidence["source"] == "prompt":
        span = evidence["span"]
        return f"{span['start']}:{span['end']}"
    return evidence["json_pointer"]


def _render_terminal(result: PreflightResult, *, include_snippets: bool) -> str:
    payload = result.to_dict(include_snippets=include_snippets)
    lines = [payload["status"]]
    for finding in payload["findings"]:
        location = _location_label(finding["trigger"])
        lines.append(f"{finding['rule_id']} {finding['label']} [{location}] {finding['finding_id']}")
        lines.append(f"  Risk: {finding['risk']}")
        lines.append(f"  Suggestion: {finding['suggestion']}")
        if include_snippets:
            trigger = finding["trigger"]
            raw = trigger.get("snippet", trigger.get("value"))
            if raw is not None:
                lines.append(f"  Evidence: {raw}")
    for correction in payload["corrections"]:
        lines.append(f"Correction {correction['correction_id']} (meaning preservation unverified)")
        if include_snippets:
            lines.append(correction["diff"]["text"])
        else:
            lines.append("  Preview redacted; rerun with --include-snippets to disclose it locally.")
    for diagnostic in payload["diagnostics"]:
        lines.append(f"{diagnostic['severity']} {diagnostic['code']}: {diagnostic['message']}")
    for action in payload["actions"]:
        availability = "available" if action["available"] else "unavailable"
        lines.append(f"{action['id']}: {availability}")
    return "\n".join(lines)


def _emit_result(result: PreflightResult, *, output_format: str, include_snippets: bool) -> None:
    if output_format == "json":
        print(result.to_json(include_snippets=include_snippets, indent=2))
    else:
        print(_render_terminal(result, include_snippets=include_snippets))


def _run_request(args: argparse.Namespace, prompt_bytes: bytes, context_bytes: bytes) -> int:
    try:
        prompt = prompt_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        result = _boundary_result(
            BoundaryErrorCode.INVALID_UTF8,
            prompt_bytes=prompt_bytes,
            context_bytes=context_bytes,
            language=args.language,
        )
        _emit_result(result, output_format=args.format, include_snippets=False)
        return result.exit_code

    try:
        context = _context_from_json(context_bytes)
    except _ContextDecodeError:
        result = _boundary_result(
            BoundaryErrorCode.INVALID_CONTEXT_JSON,
            prompt_bytes=prompt_bytes,
            context_bytes=context_bytes,
            language=args.language,
        )
        _emit_result(result, output_format=args.format, include_snippets=False)
        return result.exit_code

    if bool(args.override) != bool(args.reason and args.reason.strip()):
        print(
            "Error: --override and a non-empty --reason must be provided together.",
            file=sys.stderr,
        )
        return 2

    overrides = ()
    if args.override:
        overrides = (Override(finding_id=args.override, reason=args.reason.strip()),)
    policy = PreflightPolicy(
        include_snippets=args.include_snippets,
        overrides=overrides,
    )
    request = PreflightRequest(
        prompt=prompt,
        language=args.language,
        context=context,
        policy=policy,
    )
    result = preflight_text(request)

    if args.apply:
        try:
            corrected, post_result = apply_correction(request, result, args.apply)
        except CorrectionError:
            print(
                "Error: correction failed a closed applicability check.",
                file=sys.stderr,
            )
            return 2
        sys.stdout.write(corrected)
        print(
            f"Post-apply preflight: {post_result.status.value} {post_result.fingerprint}",
            file=sys.stderr,
        )
        return post_result.exit_code

    _emit_result(
        result,
        output_format=args.format,
        include_snippets=args.include_snippets,
    )
    return result.exit_code


def run_preflight(args: argparse.Namespace) -> int:
    """Run one bounded preflight operation and return its documented exit."""

    prompt_bytes, prompt_error = _read_prompt(args.source)
    context_bytes, context_error = _read_context(args.context)
    boundary_code = prompt_error or context_error
    if boundary_code is not None:
        result = _boundary_result(
            boundary_code,
            prompt_bytes=prompt_bytes,
            context_bytes=context_bytes,
            language=args.language,
        )
        _emit_result(result, output_format=args.format, include_snippets=False)
        return result.exit_code
    return _run_request(args, prompt_bytes, context_bytes)
