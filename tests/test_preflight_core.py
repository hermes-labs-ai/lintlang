from __future__ import annotations

import hashlib
import json
import unittest

from lintlang.preflight import (
    ActionId,
    BoundaryErrorCode,
    ConstraintKind,
    ContextBinding,
    ContextConstraint,
    ContextContract,
    ContextRequirement,
    ContextSource,
    CorrectionError,
    Delivery,
    PreflightPolicy,
    PreflightRequest,
    Status,
    apply_correction,
    boundary_error,
    preflight_text,
)


class StatusAndRuleTests(unittest.TestCase):
    def test_status_precedence_and_exit_codes(self) -> None:
        cases = (
            (PreflightRequest("   "), Status.ERROR, 2),
            (PreflightRequest("Hello", language="fr"), Status.UNAVAILABLE, 3),
            (
                PreflightRequest(
                    "Create the asset.",
                    context=ContextContract(
                        requirements=(ContextRequirement("usual_format"),)
                    ),
                ),
                Status.HOLD,
                1,
            ),
            (PreflightRequest("Is it true that alligators fly?"), Status.NOTICE, 0),
            (PreflightRequest("Summarize the supplied evidence."), Status.ALLOW, 0),
        )
        for request, expected_status, expected_exit in cases:
            with self.subTest(expected_status=expected_status):
                result = preflight_text(request)
                self.assertIs(result.status, expected_status)
                self.assertEqual(result.exit_code, expected_exit)
                self.assertEqual(len(result.actions), 4)

    def test_pf001_exact_original_unicode_span(self) -> None:
        prompt = "🐊 e\N{COMBINING ACUTE ACCENT} — Is it true that wetlands help?"
        result = preflight_text(PreflightRequest(prompt))
        finding = result.findings[0]
        self.assertEqual(finding.rule_id, "PF001")
        span = finding.trigger.span
        self.assertEqual(prompt[span.start : span.end], "Is it true that")
        self.assertEqual(span.start, prompt.index("Is"))

    def test_pf002_presupposed_causality_is_notice(self) -> None:
        result = preflight_text(PreflightRequest("Why does rain cause flooding?"))
        self.assertIs(result.status, Status.NOTICE)
        self.assertEqual([item.rule_id for item in result.findings], ["PF002"])

    def test_pf003_resolves_only_with_explicit_binding(self) -> None:
        prompt = "Make a video in our usual format."
        unresolved = preflight_text(PreflightRequest(prompt))
        self.assertEqual([item.rule_id for item in unresolved.findings], ["PF003"])
        resolved = preflight_text(
            PreflightRequest(
                prompt,
                context=ContextContract(
                    bindings=(
                        ContextBinding(
                            "usual_format",
                            "16:9 with captions",
                            ContextSource.USER,
                            Delivery.SIDE_CHANNEL,
                        ),
                    )
                ),
            )
        )
        self.assertIs(resolved.status, Status.ALLOW)

    def test_pf004_missing_uses_context_pointer_not_fake_prompt_span(self) -> None:
        result = preflight_text(
            PreflightRequest(
                "Create a video.",
                context=ContextContract(
                    requirements=(ContextRequirement("usual_format"),)
                ),
            )
        )
        finding = result.findings[0]
        serialized = result.to_dict()["findings"][0]
        self.assertEqual(finding.rule_id, "PF004")
        self.assertEqual(serialized["trigger"]["source"], "context")
        self.assertEqual(serialized["trigger"]["json_pointer"], "/requirements/0/key")
        self.assertNotIn("span", serialized["trigger"])

    def test_pf004_materialization_is_notice_with_patch(self) -> None:
        context = ContextContract(
            requirements=(ContextRequirement("usual_format"),),
            bindings=(
                ContextBinding(
                    "usual_format",
                    "16:9 with captions",
                    ContextSource.USER,
                    Delivery.IN_PROMPT,
                ),
            ),
        )
        result = preflight_text(PreflightRequest("Create a video.", context=context))
        self.assertIs(result.status, Status.NOTICE)
        self.assertEqual(result.findings[0].rule_id, "PF004")
        self.assertEqual(len(result.corrections), 1)

    def test_pf005_typed_constraint_has_prompt_and_context_evidence(self) -> None:
        context = ContextContract(
            constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),)
        )
        result = preflight_text(PreflightRequest("Return JSON.", context=context))
        self.assertIs(result.status, Status.HOLD)
        finding = result.to_dict()["findings"][0]
        self.assertEqual(finding["trigger"]["source"], "prompt")
        self.assertEqual(finding["proposition"]["source"], "context")
        self.assertEqual(finding["proposition"]["json_pointer"], "/constraints/0/value")

    def test_pf005_intrinsic_structural_conflict(self) -> None:
        result = preflight_text(
            PreflightRequest("Use exactly one sentence and at least three paragraphs.")
        )
        self.assertIs(result.status, Status.HOLD)
        self.assertEqual([item.rule_id for item in result.findings], ["PF005"])


class ScopeTests(unittest.TestCase):
    def test_nonoperative_quote_code_hypothetical_and_metalinguistic(self) -> None:
        prompts = (
            'Discuss the quote "Is it true that X?"',
            "Use this example: `Is it true that X?`",
            "```\nIs it true that X?\n```",
            "Hypothetically, is it true that X?",
            "Analyze the phrase is it true that in this sentence.",
            "Do not ask is it true that X?",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertIs(
                    preflight_text(PreflightRequest(prompt)).status, Status.ALLOW
                )

    def test_unbalanced_scope_is_unavailable_never_allow(self) -> None:
        for prompt in ('"Is it true that X?', "```Is it true that X?", "Explain (this"):
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt))
                self.assertIs(result.status, Status.UNAVAILABLE)
                self.assertEqual(result.diagnostics[0].code, "UNSAFE_SCOPE")
                self.assertFalse(
                    next(
                        item
                        for item in result.actions
                        if item.id is ActionId.PASS_AS_IS
                    ).available
                )

    def test_contractions_and_possessives_are_not_unbalanced_quotes(self) -> None:
        prompts = (
            "Don't change users' preferences; summarize the evidence.",
            "Don’t change users’ preferences; summarize the evidence.",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertIs(
                    preflight_text(PreflightRequest(prompt)).status, Status.ALLOW
                )


class PrivacyAndDeterminismTests(unittest.TestCase):
    def test_default_wire_and_repr_redact_prompt_context_replacement_and_diff(
        self,
    ) -> None:
        prompt_secret = "PROMPT_SECRET_3e1ad"
        context_secret = "CONTEXT_SECRET_9b7fa"
        request = PreflightRequest(
            f"Is it true that {prompt_secret}?",
            context=ContextContract(
                requirements=(ContextRequirement("usual_format"),),
                bindings=(
                    ContextBinding(
                        "usual_format",
                        context_secret,
                        ContextSource.USER,
                        Delivery.IN_PROMPT,
                    ),
                ),
            ),
        )
        result = preflight_text(request)
        wire = result.to_json()
        representation = repr(result)
        for secret in (prompt_secret, context_secret):
            self.assertNotIn(secret, wire)
            self.assertNotIn(secret, representation)
        revealed = result.to_json(include_snippets=True)
        self.assertIn(prompt_secret, revealed)
        self.assertIn(context_secret, revealed)

    def test_policy_opt_in_is_explicit(self) -> None:
        secret = "PROMPT_SECRET_7b3c"
        result = preflight_text(
            PreflightRequest(
                f"Is it true that {secret}?",
                policy=PreflightPolicy(include_snippets=True),
            )
        )
        self.assertIn(secret, result.to_json())
        self.assertNotIn(secret, result.to_json(include_snippets=False))

    def test_results_ids_and_canonical_json_are_repeatable(self) -> None:
        request = PreflightRequest("Is it true that wetlands help?")
        first = preflight_text(request)
        for _ in range(20):
            repeated = preflight_text(request)
            self.assertEqual(repeated.fingerprint, first.fingerprint)
            self.assertEqual(repeated.to_json(), first.to_json())
            self.assertEqual(
                repeated.findings[0].finding_id, first.findings[0].finding_id
            )

    def test_network_and_storage_are_explicitly_false(self) -> None:
        result = preflight_text(PreflightRequest("Summarize this."))
        self.assertFalse(result.network_attempted)
        self.assertFalse(result.storage_persisted)
        self.assertEqual(result.to_dict()["network"], {"attempted": False})
        self.assertEqual(result.to_dict()["storage"], {"persisted": False})


class CorrectionTests(unittest.TestCase):
    def test_hash_bound_patch_and_single_relint(self) -> None:
        request = PreflightRequest("Is it true that X? Is it true that Y?")
        result = preflight_text(request)
        corrected, relint = apply_correction(
            request, result, result.corrections[0].correction_id
        )
        self.assertNotEqual(corrected, request.prompt)
        self.assertEqual(relint.parent_fingerprint, result.fingerprint)
        self.assertEqual(relint.relint_depth, 1)
        self.assertEqual(len(relint.corrections), 1)
        with self.assertRaisesRegex(CorrectionError, "only one"):
            apply_correction(
                PreflightRequest(corrected),
                relint,
                relint.corrections[0].correction_id,
            )

    def test_changed_source_and_unknown_id_fail_closed(self) -> None:
        request = PreflightRequest("Is it true that X?")
        result = preflight_text(request)
        with self.assertRaisesRegex(CorrectionError, "source hash"):
            apply_correction(
                PreflightRequest("Is it true that changed?"),
                result,
                result.corrections[0].correction_id,
            )
        with self.assertRaisesRegex(CorrectionError, "unknown correction"):
            apply_correction(request, result, "pc_00000000000000000000")


class InvalidAndBoundaryTests(unittest.TestCase):
    def test_invalid_or_oversize_inputs_are_error(self) -> None:
        oversize = "🐊" * (32 * 1024 // 4 + 1)
        self.assertIs(preflight_text(PreflightRequest(oversize)).status, Status.ERROR)
        self.assertIs(preflight_text(PreflightRequest("\ud800")).status, Status.ERROR)

    def test_invalid_typed_context_is_error(self) -> None:
        bad_constraint = ContextContract(constraints=("output_format:json",))  # type: ignore[arg-type]
        result = preflight_text(
            PreflightRequest("Return JSON.", context=bad_constraint)
        )
        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "INVALID_CONSTRAINT")

    def test_unequal_duplicate_bindings_are_error(self) -> None:
        context = ContextContract(
            bindings=(
                ContextBinding(
                    "usual_format", "A", ContextSource.USER, Delivery.SIDE_CHANNEL
                ),
                ContextBinding(
                    "usual_format", "B", ContextSource.USER, Delivery.SIDE_CHANNEL
                ),
            )
        )
        result = preflight_text(PreflightRequest("Create it.", context=context))
        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "CONFLICTING_BINDINGS")

    def test_boundary_error_uses_static_redacted_message(self) -> None:
        raw = b"\xffTOP_SECRET"
        result = boundary_error(
            BoundaryErrorCode.INVALID_UTF8,
            input_sha256=hashlib.sha256(raw).hexdigest(),
            input_utf8_bytes=len(raw),
        )
        payload = json.loads(result.to_json())
        self.assertEqual(payload["status"], "ERROR")
        self.assertEqual(payload["diagnostics"][0]["code"], "INVALID_UTF8")
        self.assertNotIn("TOP_SECRET", result.to_json())
        self.assertEqual(len(payload["actions"]), 4)
        self.assertFalse(any(item["available"] for item in payload["actions"]))


if __name__ == "__main__":
    unittest.main()
