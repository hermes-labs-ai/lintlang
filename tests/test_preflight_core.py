from __future__ import annotations

import hashlib
import json
import re
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
    Override,
    PreflightPolicy,
    PreflightRequest,
    Status,
    apply_correction,
    boundary_error,
    preflight_text,
)

_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?: .*)?\n$"
)
_NO_NEWLINE_MARKER = "\\ No newline at end of file\n"


def _apply_unified_diff(source: str, diff: str, *, reverse: bool = False) -> str:
    """Apply the bounded single-file diff format emitted by preflight."""

    source_lines = source.splitlines(keepends=True)
    diff_lines = diff.splitlines(keepends=True)
    if diff_lines[:2] != ["--- prompt\n", "+++ corrected\n"]:
        raise AssertionError("unexpected unified diff headers")

    output: list[str] = []
    source_index = 0
    index = 2
    while index < len(diff_lines):
        header = _HUNK_HEADER.fullmatch(diff_lines[index])
        if header is None:
            raise AssertionError("invalid unified diff hunk header")
        old_start = int(header.group("old_start"))
        new_start = int(header.group("new_start"))
        old_count = int(header.group("old_count") or 1)
        new_count = int(header.group("new_count") or 1)
        input_start = new_start if reverse else old_start
        input_count = new_count if reverse else old_count
        input_index = input_start if input_count == 0 else input_start - 1
        output.extend(source_lines[source_index:input_index])
        source_index = input_index
        index += 1

        old_seen = 0
        new_seen = 0
        while index < len(diff_lines) and not diff_lines[index].startswith("@@"):
            line = diff_lines[index]
            if line == _NO_NEWLINE_MARKER or line[:1] not in {" ", "-", "+"}:
                raise AssertionError("invalid unified diff record")
            prefix = line[0]
            payload = line[1:]
            if index + 1 < len(diff_lines) and diff_lines[index + 1] == _NO_NEWLINE_MARKER:
                if not payload.endswith("\n"):
                    raise AssertionError("newline marker has no synthetic newline")
                payload = payload[:-1]
                index += 1

            old_seen += prefix in {" ", "-"}
            new_seen += prefix in {" ", "+"}
            consumes = prefix in ({" ", "+"} if reverse else {" ", "-"})
            emits = prefix in ({" ", "-"} if reverse else {" ", "+"})
            if consumes:
                if source_index >= len(source_lines) or source_lines[source_index] != payload:
                    raise AssertionError("unified diff does not match source bytes")
                source_index += 1
            if emits:
                output.append(payload)
            index += 1

        if (old_seen, new_seen) != (old_count, new_count):
            raise AssertionError("unified diff hunk counts do not match records")

    output.extend(source_lines[source_index:])
    return "".join(output)


class StatusAndRuleTests(unittest.TestCase):
    def test_status_precedence_and_exit_codes(self) -> None:
        cases = (
            (PreflightRequest("   "), Status.ERROR, 2),
            (PreflightRequest("Hello", language="fr"), Status.UNAVAILABLE, 3),
            (
                PreflightRequest(
                    "Create the asset.",
                    context=ContextContract(requirements=(ContextRequirement("usual_format"),)),
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
                context=ContextContract(requirements=(ContextRequirement("usual_format"),)),
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
        context = ContextContract(constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),))
        result = preflight_text(PreflightRequest("Return JSON.", context=context))
        self.assertIs(result.status, Status.HOLD)
        finding = result.to_dict()["findings"][0]
        self.assertEqual(finding["trigger"]["source"], "prompt")
        self.assertEqual(finding["proposition"]["source"], "context")
        self.assertEqual(finding["proposition"]["json_pointer"], "/constraints/0/value")

    def test_pf005_checks_every_format_mention_in_both_orders(self) -> None:
        cases = (
            ("Return JSON, then markdown.", "markdown", ("JSON",)),
            ("Return markdown, then JSON.", "json", ("markdown",)),
        )
        for prompt, expected_format, conflicting_mentions in cases:
            with self.subTest(prompt=prompt):
                result = preflight_text(
                    PreflightRequest(
                        prompt,
                        context=ContextContract(
                            constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, expected_format),)
                        ),
                    )
                )
                self.assertIs(result.status, Status.HOLD)
                self.assertEqual([item.rule_id for item in result.findings], ["PF005"])
                self.assertEqual(
                    tuple(prompt[item.trigger.span.start : item.trigger.span.end] for item in result.findings),
                    conflicting_mentions,
                )

    def test_pf005_accepts_typed_format_that_resolves_an_explicit_alternative(self) -> None:
        cases = (
            ("Return JSON or markdown.", "markdown"),
            ("Return markdown or JSON.", "json"),
            ("Return either JSON, or markdown.", "markdown"),
            ("Either return markdown or return JSON.", "json"),
            ("Return JSON and/or markdown.", "markdown"),
            ("Return markdown/JSON.", "json"),
        )
        for prompt, expected_format in cases:
            with self.subTest(prompt=prompt, expected_format=expected_format):
                result = preflight_text(
                    PreflightRequest(
                        prompt,
                        context=ContextContract(
                            constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, expected_format),)
                        ),
                    )
                )
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual(result.findings, ())

    def test_pf005_alternatives_do_not_mask_conjoined_or_sequential_conflicts(self) -> None:
        cases = (
            ("Return JSON and markdown.", ("JSON",)),
            ("Return JSON, then markdown.", ("JSON",)),
            ("Return JSON, markdown.", ("JSON",)),
            ("Return JSON or markdown, then JSON.", ("JSON",)),
            ("Return JSON or YAML, then markdown.", ("JSON",)),
        )
        context = ContextContract(constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),))
        for prompt, conflicting_mentions in cases:
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt, context=context))
                self.assertIs(result.status, Status.HOLD)
                self.assertEqual(
                    tuple(prompt[item.trigger.span.start : item.trigger.span.end] for item in result.findings),
                    conflicting_mentions,
                )

    def test_pf005_preserves_repeated_conflicting_format_spans(self) -> None:
        prompt = "Return JSON, JSON, then markdown, then JSON."
        result = preflight_text(
            PreflightRequest(
                prompt,
                context=ContextContract(constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),)),
            )
        )

        self.assertIs(result.status, Status.HOLD)
        self.assertEqual([item.rule_id for item in result.findings], ["PF005", "PF005", "PF005"])
        self.assertEqual(
            [prompt[item.trigger.span.start : item.trigger.span.end] for item in result.findings],
            ["JSON", "JSON", "JSON"],
        )
        self.assertEqual(
            [(item.trigger.span.start, item.trigger.span.end) for item in result.findings],
            [(7, 11), (13, 17), (39, 43)],
        )

    def test_pf005_stops_at_clause_boundaries_and_ignores_nonoperative_examples(self) -> None:
        controls = (
            'Return JSON. Discuss the phrase "Return markdown."',
            "Return JSON. Use this example: `Return markdown.`",
            "Return JSON. Do not return markdown.",
            "Return JSON. Analyze markdown as a format name.",
            "Return JSON.\nMention markdown in the explanation.",
        )
        context = ContextContract(constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "json"),))
        for prompt in controls:
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt, context=context))
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual(result.findings, ())

    def test_pf005_intrinsic_structural_conflict(self) -> None:
        result = preflight_text(PreflightRequest("Use exactly one sentence and at least three paragraphs."))
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
                self.assertIs(preflight_text(PreflightRequest(prompt)).status, Status.ALLOW)

    def test_unbalanced_scope_is_unavailable_never_allow(self) -> None:
        for prompt in ('"Is it true that X?', "```Is it true that X?", "Explain (this"):
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt))
                self.assertIs(result.status, Status.UNAVAILABLE)
                self.assertEqual(result.diagnostics[0].code, "UNSAFE_SCOPE")
                self.assertFalse(next(item for item in result.actions if item.id is ActionId.PASS_AS_IS).available)

    def test_zero_enabled_and_required_rules_skip_scope_parser(self) -> None:
        policy = PreflightPolicy(enabled_rules=(), required_rules=())
        for prompt in ("`", '"', "Explain (this"):
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt, policy=policy))
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual(result.diagnostics, ())
                self.assertTrue(all(not item.required for item in result.coverage))
                self.assertTrue(all(item.state.value == "NOT_REQUIRED" for item in result.coverage))

    def test_enabled_optional_rules_report_parser_loss_without_unavailable(self) -> None:
        policy = PreflightPolicy(enabled_rules=("PF001",), required_rules=())
        for prompt in ("`", '"', "Explain (this"):
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt, policy=policy))
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual([item.code for item in result.diagnostics], ["UNSAFE_SCOPE"])
                self.assertEqual(result.diagnostics[0].severity.value, "WARNING")
                scope_coverage = next(item for item in result.coverage if item.component == "scope-parser")
                rule_coverage = next(item for item in result.coverage if item.component == "PF001")
                self.assertFalse(scope_coverage.required)
                self.assertFalse(rule_coverage.required)
                self.assertEqual(scope_coverage.state.value, "NONE")
                self.assertEqual(rule_coverage.state.value, "NONE")

    def test_enabled_optional_rules_report_language_loss_without_unavailable(self) -> None:
        policy = PreflightPolicy(enabled_rules=("PF001",), required_rules=())
        result = preflight_text(PreflightRequest("Assess the evidence.", language="fr", policy=policy))

        self.assertIs(result.status, Status.ALLOW)
        self.assertEqual([item.code for item in result.diagnostics], ["UNSUPPORTED_LANGUAGE"])
        self.assertEqual(result.diagnostics[0].severity.value, "WARNING")
        scope_coverage = next(item for item in result.coverage if item.component == "scope-parser")
        rule_coverage = next(item for item in result.coverage if item.component == "PF001")
        self.assertFalse(scope_coverage.required)
        self.assertFalse(rule_coverage.required)
        self.assertEqual(scope_coverage.state.value, "NONE")
        self.assertEqual(rule_coverage.state.value, "NONE")

    def test_required_rules_keep_genuine_scope_loss_unavailable(self) -> None:
        policy = PreflightPolicy(enabled_rules=("PF001",), required_rules=("PF001",))
        for prompt in ("`", '"', "Explain (this"):
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt, policy=policy))
                self.assertIs(result.status, Status.UNAVAILABLE)
                self.assertEqual(result.diagnostics[0].code, "UNSAFE_SCOPE")
                scope_coverage = next(item for item in result.coverage if item.component == "scope-parser")
                rule_coverage = next(item for item in result.coverage if item.component == "PF001")
                self.assertTrue(scope_coverage.required)
                self.assertTrue(rule_coverage.required)
                self.assertEqual(scope_coverage.state.value, "NONE")
                self.assertEqual(rule_coverage.state.value, "NONE")

    def test_contractions_and_possessives_are_not_unbalanced_quotes(self) -> None:
        prompts = (
            "Don't change users' preferences; summarize the evidence.",
            "Don’t change users’ preferences; summarize the evidence.",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertIs(preflight_text(PreflightRequest(prompt)).status, Status.ALLOW)

    def test_counterfactual_and_negated_requirements_are_not_operational(self) -> None:
        prompts = (
            "If the seed vault inventory were required to use exactly one sentence and at least three paragraphs, identify why that hypothetical requirement would be inconsistent.",
            "Do not require exactly one sentence or at least three paragraphs for canoe launch guide; those are prohibited examples.",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt))
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual(result.findings, ())

    def test_bounded_requirement_scope_keeps_direct_conflicts_operative(self) -> None:
        prompts = (
            "If possible, use exactly one sentence and at least three paragraphs.",
            "If the title were required, use exactly one sentence and at least three paragraphs.",
            "Do not require a title; use exactly one sentence and at least three paragraphs.",
            "Do not require a title, but use exactly one sentence and at least three paragraphs.",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = preflight_text(PreflightRequest(prompt))
                self.assertIs(result.status, Status.HOLD)
                self.assertEqual([item.rule_id for item in result.findings], ["PF005"])

        result = preflight_text(
            PreflightRequest(
                "Do not require a title; return JSON.",
                context=ContextContract(constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),)),
            )
        )
        self.assertIs(result.status, Status.HOLD)
        self.assertEqual([item.rule_id for item in result.findings], ["PF005"])

    def test_negated_output_format_clauses_are_not_operational(self) -> None:
        cases = (
            ("Do not return JSON. Return markdown.", "markdown"),
            ("Don't respond with JSON; return markdown.", "markdown"),
            ("Never output JSON, but return markdown.", "markdown"),
            ("Do not format the answer as JSON\nReturn markdown.", "markdown"),
            ("Do not return markdown; return JSON.", "json"),
        )
        for prompt, expected_format in cases:
            with self.subTest(prompt=prompt):
                result = preflight_text(
                    PreflightRequest(
                        prompt,
                        context=ContextContract(
                            constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, expected_format),)
                        ),
                    )
                )
                self.assertIs(result.status, Status.ALLOW)
                self.assertEqual(result.findings, ())

    def test_later_output_format_conflicts_remain_operational(self) -> None:
        prompts = (
            "Do not return JSON; return JSON.",
            "Do not return JSON, but return JSON.",
            "Do not return JSON. Return JSON.",
            "Do not return JSON\nReturn JSON.",
            "Do not format markdown; respond with JSON.",
            "Return a concise, valid JSON object.",
        )
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                result = preflight_text(
                    PreflightRequest(
                        prompt,
                        context=ContextContract(
                            constraints=(ContextConstraint(ConstraintKind.OUTPUT_FORMAT, "markdown"),)
                        ),
                    )
                )
                self.assertIs(result.status, Status.HOLD)
                self.assertEqual([item.rule_id for item in result.findings], ["PF005"])
                span = result.findings[0].trigger.span
                self.assertEqual((span.start, span.end), (prompt.rindex("JSON"), prompt.rindex("JSON") + 4))


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
            self.assertEqual(repeated.findings[0].finding_id, first.findings[0].finding_id)

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
        corrected, relint = apply_correction(request, result, result.corrections[0].correction_id)
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

    def test_unterminated_correction_diff_is_canonical_and_round_trips(self) -> None:
        prompt = "Is it true that X?"
        request = PreflightRequest(prompt)
        result = preflight_text(request)
        correction = result.corrections[0]
        corrected, _ = apply_correction(request, result, correction.correction_id)
        serialized = result.to_dict(include_snippets=True)["corrections"][0]["diff"]
        diff = serialized["text"]

        self.assertEqual(correction.correction_id, "pc_fab390648096b9fed140")
        self.assertEqual(
            diff,
            "--- prompt\n"
            "+++ corrected\n"
            "@@ -1 +1 @@\n"
            "-Is it true that X?\n"
            "\\ No newline at end of file\n"
            "+What evidence supports or refutes whether X?\n"
            "\\ No newline at end of file\n",
        )
        self.assertEqual(_apply_unified_diff(prompt, diff), corrected)
        self.assertEqual(_apply_unified_diff(corrected, diff, reverse=True), prompt)
        self.assertEqual(serialized["sha256"], hashlib.sha256(diff.encode()).hexdigest())
        self.assertEqual(serialized["utf8_bytes"], len(diff.encode()))

    def test_terminated_and_multiline_unicode_diffs_preserve_exact_bytes(self) -> None:
        prompts = ("Is it true that X?\n", "Header\nIs it true that 🐊?")
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                request = PreflightRequest(prompt)
                result = preflight_text(request)
                correction = result.corrections[0]
                corrected, _ = apply_correction(request, result, correction.correction_id)
                serialized = result.to_dict(include_snippets=True)["corrections"][0]["diff"]
                diff = serialized["text"]

                self.assertEqual(_apply_unified_diff(prompt, diff).encode(), corrected.encode())
                self.assertEqual(_apply_unified_diff(corrected, diff, reverse=True).encode(), prompt.encode())
                self.assertEqual(serialized["sha256"], hashlib.sha256(diff.encode()).hexdigest())
                self.assertEqual(serialized["utf8_bytes"], len(diff.encode()))
                if prompt.endswith("\n"):
                    self.assertNotIn(_NO_NEWLINE_MARKER, diff)
                else:
                    self.assertEqual(diff.count(_NO_NEWLINE_MARKER), 2)


class InvalidAndBoundaryTests(unittest.TestCase):
    def test_invalid_or_oversize_inputs_are_error(self) -> None:
        oversize = "🐊" * (32 * 1024 // 4 + 1)
        self.assertIs(preflight_text(PreflightRequest(oversize)).status, Status.ERROR)
        self.assertIs(preflight_text(PreflightRequest("\ud800")).status, Status.ERROR)

    def test_invalid_typed_context_is_error(self) -> None:
        bad_constraint = ContextContract(constraints=("output_format:json",))  # type: ignore[arg-type]
        result = preflight_text(PreflightRequest("Return JSON.", context=bad_constraint))
        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "INVALID_CONSTRAINT")

    def test_unequal_duplicate_bindings_are_error(self) -> None:
        context = ContextContract(
            bindings=(
                ContextBinding("usual_format", "A", ContextSource.USER, Delivery.SIDE_CHANNEL),
                ContextBinding("usual_format", "B", ContextSource.USER, Delivery.SIDE_CHANNEL),
            )
        )
        result = preflight_text(PreflightRequest("Create it.", context=context))
        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "CONFLICTING_BINDINGS")

    def test_all_duplicate_binding_keys_are_error_without_order_dependence(self) -> None:
        user_side = ContextBinding("usual_format", "A", ContextSource.USER, Delivery.SIDE_CHANNEL)
        user_prompt = ContextBinding("usual_format", "A", ContextSource.USER, Delivery.IN_PROMPT)
        host_side = ContextBinding("usual_format", "A", ContextSource.HOST, Delivery.SIDE_CHANNEL)
        cases = (
            (user_side, user_side),
            (user_side, user_prompt),
            (user_prompt, user_side),
            (user_side, host_side),
        )
        for bindings in cases:
            with self.subTest(bindings=bindings):
                result = preflight_text(
                    PreflightRequest(
                        "Create it.",
                        context=ContextContract(
                            requirements=(ContextRequirement("usual_format"),),
                            bindings=bindings,
                        ),
                    )
                )
                self.assertIs(result.status, Status.ERROR)
                self.assertEqual(result.diagnostics[0].code, "CONFLICTING_BINDINGS")
                self.assertEqual(result.diagnostics[0].context_pointer, "/bindings/1")

        distinct = ContextContract(
            bindings=(
                ContextBinding("usual_format", "A", ContextSource.USER, Delivery.SIDE_CHANNEL),
                ContextBinding("video_format", "A", ContextSource.USER, Delivery.SIDE_CHANNEL),
            )
        )
        self.assertIs(preflight_text(PreflightRequest("Create it.", context=distinct)).status, Status.ALLOW)

    def test_unpaired_surrogate_binding_is_deterministic_redacted_error(self) -> None:
        canary = "PRIVATE_CONTEXT_CANARY_0f31a"
        context = ContextContract(
            requirements=(ContextRequirement("usual_format"),),
            bindings=(
                ContextBinding(
                    "usual_format",
                    canary + "\ud800",
                    ContextSource.USER,
                    Delivery.IN_PROMPT,
                ),
            ),
        )
        request = PreflightRequest("Create a video.", context=context)
        result = preflight_text(request)
        repeated = preflight_text(request)

        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.diagnostics[0].code, "INVALID_BINDING")
        self.assertEqual(result.fingerprint, repeated.fingerprint)
        self.assertTrue(all(not item.available for item in result.actions))
        for wire in (result.to_json(), result.to_json(include_snippets=True)):
            self.assertNotIn(canary, wire)
            self.assertNotIn("\\ud800", wire)

    def test_invalid_language_uses_schema_safe_wire_metadata(self) -> None:
        result = preflight_text(PreflightRequest("Assess the evidence.", language=""))
        payload = result.to_dict()

        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "INVALID_LANGUAGE")
        self.assertEqual(payload["input"]["language"], "und")

        boundary = boundary_error(BoundaryErrorCode.INPUT_READ_FAILED, language="")
        self.assertEqual(boundary.to_dict()["input"]["language"], "und")

    def test_invalid_override_fields_return_error_without_crashing(self) -> None:
        invalid_overrides = (
            Override(123, "reason"),  # type: ignore[arg-type]
            Override("pf_00000000000000000000", "\ud800"),
        )
        for override in invalid_overrides:
            with self.subTest(override=override):
                result = preflight_text(
                    PreflightRequest(
                        "Assess the evidence.",
                        policy=PreflightPolicy(overrides=(override,)),
                    )
                )
                self.assertIs(result.status, Status.ERROR)
                self.assertEqual(result.diagnostics[0].code, "INVALID_OVERRIDE")
                self.assertTrue(all(not item.available for item in result.actions))
                result.to_json()

    def test_unhashable_policy_rule_selection_returns_error(self) -> None:
        policy = PreflightPolicy(enabled_rules=(["PF001"],))  # type: ignore[arg-type,list-item]
        result = preflight_text(PreflightRequest("Assess the evidence.", policy=policy))

        self.assertIs(result.status, Status.ERROR)
        self.assertEqual(result.diagnostics[0].code, "UNKNOWN_RULE")

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
