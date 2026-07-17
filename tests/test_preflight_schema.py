"""Packaged preflight wire and privacy contract tests.

Full JSON Schema validation is a release verifier; these dependency-free tests
protect package inclusion, constants, exact evidence, and default redaction.
"""

from __future__ import annotations

import importlib.resources
import json

import lintlang
from lintlang.preflight import PreflightRequest, Status, preflight_text

PROMPT_CANARY = "PRIVATE_PROMPT_CANARY_7d912"


def _schema() -> dict:
    resource = importlib.resources.files("lintlang.preflight").joinpath("schema/preflight-result.v1.schema.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def test_public_root_exports_small_preflight_seam():
    assert lintlang.PreflightRequest is not None
    assert lintlang.PreflightResult is not None
    assert lintlang.ContextContract is not None
    assert lintlang.preflight_text is not None
    assert lintlang.apply_correction is not None


def test_stable_urn_schema_is_packaged_and_matches_wire_constants():
    schema = _schema()
    result = preflight_text(PreflightRequest(prompt="Assess the evidence for and against X."))
    payload = result.to_dict()

    assert schema["$id"] == "urn:lintlang:schema:preflight-result:v1"
    assert schema["properties"]["schema_id"]["const"] == payload["schema_id"]
    assert schema["properties"]["schema_version"]["const"] == payload["schema_version"]
    assert schema["properties"]["engine_version"]["const"] == payload["engine_version"]
    assert schema["properties"]["rule_bundle_version"]["const"] == payload["rule_bundle_version"]
    assert set(schema["required"]) == set(payload)


def test_exact_codepoint_span_and_stable_finding_id():
    prompt = f"Is it true that {PROMPT_CANARY} is correct?"
    request = PreflightRequest(prompt=prompt)

    first = preflight_text(request)
    second = preflight_text(request)

    assert first.status is Status.NOTICE
    assert first.fingerprint == second.fingerprint
    assert first.findings[0].finding_id == second.findings[0].finding_id
    span = first.findings[0].trigger.span
    assert prompt[span.start : span.end] == "Is it true that"


def test_default_wire_redacts_raw_evidence_replacement_and_diff():
    prompt = f"Is it true that {PROMPT_CANARY} is correct?"
    result = preflight_text(PreflightRequest(prompt=prompt))

    payload = result.to_json()

    assert PROMPT_CANARY not in payload
    assert '"snippet"' not in payload
    assert '"replacement"' not in payload
    assert '"text"' not in payload
    assert '"snippets_included":false' in payload


def test_explicit_snippet_opt_in_reveals_local_patch():
    prompt = f"Is it true that {PROMPT_CANARY} is correct?"
    result = preflight_text(PreflightRequest(prompt=prompt))

    payload = result.to_json(include_snippets=True)

    assert PROMPT_CANARY in payload
    assert '"snippet"' in payload
    assert '"replacement"' in payload
    assert '"text"' in payload
    assert '"snippets_included":true' in payload


def test_every_status_keeps_four_ordered_action_descriptors():
    cases = (
        PreflightRequest(prompt="Assess evidence for and against X."),
        PreflightRequest(prompt="Is it true that X?"),
        PreflightRequest(prompt="   "),
        PreflightRequest(prompt="¿Es verdad que X?", language="es"),
    )
    expected = ["PASS_AS_IS", "APPLY_PATCH", "ADD_CONTEXT", "HOLD_AND_DISCUSS"]

    for request in cases:
        payload = preflight_text(request).to_dict()
        assert [action["id"] for action in payload["actions"]] == expected
        if payload["status"] == "ERROR":
            assert all(not action["available"] for action in payload["actions"])


def test_invalid_language_error_respects_schema_minimum_length():
    schema = _schema()
    result = preflight_text(PreflightRequest(prompt="Assess evidence.", language=""))
    payload = result.to_dict()
    minimum = schema["properties"]["input"]["properties"]["language"]["minLength"]

    assert result.status is Status.ERROR
    assert result.diagnostics[0].code == "INVALID_LANGUAGE"
    assert payload["input"]["language"] == "und"
    assert len(payload["input"]["language"]) >= minimum
