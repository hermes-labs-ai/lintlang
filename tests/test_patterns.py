"""Tests for H1-H7 pattern detectors."""

import json
from pathlib import Path

import pytest

from lintlang.patterns import (
    AgentConfig,
    Severity,
    ToolDef,
    detect_h1,
    detect_h2,
    detect_h3,
    detect_h4,
    detect_h5,
    detect_h6,
    detect_h7,
)
from lintlang.scanner import scan_file

ROOT = Path(__file__).parent.parent
CORPUS_PATH = ROOT / "evals" / "corpus" / "cases.jsonl"
SAMPLES_DIR = ROOT / "samples"

# LintLang's own shipped instruction surfaces, used as hard negatives for the
# applicability-free H4/H5/H6 heuristics narrowed per RESEARCH.md section 5.
_LINTLANG_INSTRUCTION_SURFACES = (
    "AGENTS.md",
    ".agents/skills/lintlang/SKILL.md",
    "integrations/claude-code/skills/lintlang-audit/SKILL.md",
)

# Long AND demonstrably stateful: the positive control for H4's length rule.
_LONG_STATEFUL_PROMPT = (
    "You are a support agent for an order system. Answer billing questions. "
    "Look up orders with the order tool. Explain refund timelines plainly. "
    "Offer the self-service portal when the customer can use it. "
    "Escalate a chargeback to a human. Quote the order id in every reply. "
    "Remember everything the customer tells you and reuse it later. "
    "Carry over state between tasks so the customer never repeats themselves. "
    "Use the conversation history to decide what to say next. "
    "Name the refund window in days rather than calling it fast. "
    "Cite the policy clause you applied for every decision you report. "
)


def _repo_text(relative_path: str) -> str:
    """Read one of LintLang's own instruction surfaces as prompt text."""
    return (ROOT / relative_path).read_text(encoding="utf-8")

# ── H1: Tool Description Ambiguity ─────────────────────────────────


class TestH1:
    def test_no_tools_returns_empty(self, empty_config):
        assert detect_h1(empty_config) == []

    def test_clean_tools_no_critical(self, clean_tools_config):
        findings = detect_h1(clean_tools_config)
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert len(critical) == 0

    def test_empty_description(self):
        config = AgentConfig(tools=[ToolDef(name="broken", description="")])
        findings = detect_h1(config)
        assert any(f.severity == Severity.CRITICAL and "no description" in f.description for f in findings)

    def test_short_description(self):
        config = AgentConfig(tools=[ToolDef(name="short", description="Get data")])
        findings = detect_h1(config)
        assert any(f.severity == Severity.HIGH and "very short" in f.description for f in findings)

    def test_vague_leading_verb(self):
        config = AgentConfig(
            tools=[ToolDef(name="handler", description="Handle the user request and process it accordingly")]
        )
        findings = detect_h1(config)
        assert any("vague verb" in f.description for f in findings)

    def test_overlapping_descriptions(self):
        config = AgentConfig(
            tools=[
                ToolDef(name="get_user", description="Get user data from the database system"),
                ToolDef(name="fetch_user", description="Get user data from the database"),
            ]
        )
        findings = detect_h1(config)
        assert any("overlap" in f.description.lower() for f in findings)

    def test_well_differentiated_tools_no_overlap(self, clean_tools_config):
        findings = detect_h1(clean_tools_config)
        overlap_findings = [f for f in findings if "overlap" in f.description.lower()]
        assert len(overlap_findings) == 0

    def test_vague_verb_with_punctuation(self):
        """Vague verb followed by colon/punctuation should still be detected."""
        config = AgentConfig(tools=[ToolDef(name="handler", description="Handle: the user request and process it")])
        findings = detect_h1(config)
        assert any("vague verb" in f.description for f in findings)

    def test_duplicate_tool_names(self):
        """Two tools with the same name should be flagged as CRITICAL."""
        config = AgentConfig(
            tools=[
                ToolDef(name="search", description="Search for users in the database by email"),
                ToolDef(name="search", description="Search for products in the catalog by name"),
            ]
        )
        findings = detect_h1(config)
        assert any("duplicate" in f.description.lower() and f.severity == Severity.CRITICAL for f in findings)

    def test_stopwords_dont_inflate_overlap(self):
        """Common stopwords should not inflate overlap score."""
        config = AgentConfig(
            tools=[
                ToolDef(name="create_user", description="Create a new user in the system database"),
                ToolDef(name="delete_user", description="Delete an existing user from the system database"),
            ]
        )
        findings = detect_h1(config)
        overlap_findings = [f for f in findings if "overlap" in f.description.lower()]
        assert len(overlap_findings) == 0


class TestH16Differentia:
    """H1.6 — a description that does not distinguish its tool from a sibling.

    The defect these cover is not "these two are worded alike" (that is H1.5).
    It is "neither description names anything that would let a reader choose
    one over the other" — which can be true even when the two share almost no
    vocabulary, because the differing words are synonyms.
    """

    @staticmethod
    def _codes(t1: tuple[str, str], t2: tuple[str, str]) -> list[str]:
        config = AgentConfig(tools=[ToolDef(*t1), ToolDef(*t2)])
        return [f.code for f in detect_h1(config) if f.code in ("H1.5", "H1.6")]

    def test_generic_verbs_are_not_a_differentia(self):
        """'handles' vs 'does' are the same instruction to a reader."""
        assert "H1.6" in self._codes(
            ("handle_ticket", "handles a ticket"),
            ("do_ticket", "does the ticket thing"),
        )

    def test_morphological_variants_are_not_a_differentia(self):
        """'documentation' and 'docs' are the same word."""
        assert "H1.6" in self._codes(
            ("search_docs", "Search the documentation"),
            ("find_docs", "Search through the docs"),
        )

    def test_generic_payload_nouns_are_not_a_differentia(self):
        """'info' vs 'data', and 'from the system' narrows nothing."""
        assert "H1.6" in self._codes(
            ("get_user_info", "Get user info"),
            ("get_user_data", "Get user data from the system"),
        )

    def test_synonymous_verbs_are_not_a_differentia(self):
        """Two names for one operation do not distinguish it.

        Cardinality is held constant on purpose. An earlier version of this test
        paired a singular tool against a plural one and expected a finding —
        which was wrong: returning one record and returning many is a real
        difference, and treating it as noise produced a "remove one"
        recommendation on `get_user` / `get_users`.
        """
        assert "H1.6" in self._codes(
            ("lookup_order", "Look up an order in the system"),
            ("search_order", "Search for an order"),
        )

    def test_cardinality_is_a_differentia(self):
        """Singular and plural are different operations, not two spellings.

        `get_X` / `get_Xs` is among the most common naming conventions there is.
        Collapsing number to catch morphological variants flagged these as
        redundant and advised deleting one.
        """
        for pair in (
            (("get_order", "Returns the order record matching the given identifier."),
             ("get_orders", "Returns the order records matching the given identifiers.")),
            (("get_user", "Return the user by id"),
             ("get_users", "Return the users by ids")),
        ):
            assert self._codes(*pair) == [], f"{pair[0][0]} vs {pair[1][0]} are distinct"

    def test_cross_reference_suppresses_h16_but_not_h15(self):
        """Naming a sibling answers one question and not the other.

        It explains how the two differ, so there is a differentia and H1.6 must
        stay quiet. It does not make the surrounding prose any less
        near-duplicate, which is all H1.5 measures. Skipping the pair outright
        meant a bare "See check_status." appended to an otherwise identical
        description silenced both.
        """
        codes = self._codes(
            ("get_status",
             "Return the current status of a ticket for the requesting user. See check_status."),
            ("check_status",
             "Return the current status of a ticket for the requesting user."),
        )
        assert "H1.5" in codes
        assert "H1.6" not in codes

    def test_a_common_word_name_is_not_a_cross_reference(self):
        """Only an identifier-shaped name counts as naming a tool.

        A tool called `access` occurs inside "Manage Discord channel access",
        and reading that as a deliberate pointer suppressed genuinely
        near-duplicate descriptions across an entire plugin family.
        """
        codes = self._codes(
            ("access", "Manage Discord channel access — approve pairings, edit allowlists."),
            ("access", "Manage Telegram channel access — approve pairings, edit allowlists."),
        )
        assert "H1.5" in codes

    def test_unreadable_descriptions_are_never_dominated(self):
        """A tool we cannot analyse is not a tool that duplicates another.

        Containment holds vacuously for an empty set, so a description yielding
        no analysable terms was reported as "dominated by" whatever it happened
        to sit next to — with advice to delete it. Before tokenization became
        Unicode-aware this fired on any non-Latin description, meaning an
        ordinary internationalized config got told to remove its tools.
        """
        pairs = [
            # Different languages, unrelated meanings.
            (ToolDef("获取订单", "获取指定标识符的订单记录"),
             ToolDef("obtenir_commande", "Obtenir une commande par identifiant")),
            (ToolDef("получить_заказ", "Получить заказ по идентификатору"),
             ToolDef("get_order", "Return the order by identifier")),
            # No analysable content at all.
            (ToolDef("tool_a", "..."), ToolDef("tool_b", "...")),
        ]
        for pair in pairs:
            findings = detect_h1(AgentConfig(tools=list(pair)))
            assert [f for f in findings if f.code == "H1.6"] == [], (
                f"{pair[0].name} vs {pair[1].name} must not be reported"
            )

    def test_non_latin_text_yields_terms(self):
        """Tokenization must not silently discard whole writing systems."""
        from lintlang.patterns import _meaning_terms

        assert _meaning_terms(ToolDef("获取订单", "获取指定标识符的订单记录"))
        assert "récupère" in _meaning_terms(
            ToolDef("recuperer", "Récupère une commande par identifiant")
        )

    def test_declared_alias_is_reported(self):
        """A description admitting it duplicates another tool is the surest collision.

        The alias notice must not be read as self-disambiguation: naming the
        sibling here concedes the two are the same, rather than explaining how
        they differ.
        """
        codes = self._codes(
            ("fidelis_recall", "Compatibility alias for cogito_recall. Recall stored facts."),
            ("cogito_recall", "Recall stored facts from memory."),
        )
        assert "H1.6" in codes

    def test_alias_detection_is_a_phrase_list_not_a_concept(self):
        """Documents the limit so nobody cites the fix as broader than it is.

        The same relationship phrased outside the list is missed. This asserts
        the current shortfall deliberately: if it starts passing, detection has
        become semantic and the README's disclosure should be updated to match.
        """
        for phrasing in (
            "This does the same thing as cogito_recall, kept for backward compatibility.",
            "Older entry point. Prefer cogito_recall in new code.",
        ):
            assert self._codes(
                ("fidelis_recall", phrasing),
                ("cogito_recall", "Recall stored facts from memory."),
            ) == [], f"now detected, update the README disclosure: {phrasing!r}"

    def test_pointing_at_a_sibling_is_not_an_alias_notice(self):
        """'use X instead' is ordinary disambiguation and must stay quiet.

        This project's own `samples/clean_config.yaml` says "Do NOT use for
        forecasts — use get_forecast instead", which is a well-written tool
        doing the right thing.
        """
        assert self._codes(
            ("get_current_weather",
             "Retrieve real-time weather conditions. Do NOT use for forecasts — use get_forecast instead."),
            ("get_forecast",
             "Retrieve a multi-day forecast. Do NOT use for current conditions — use get_current_weather instead."),
        ) == []

    def test_jaccard_would_have_missed_these(self):
        """Regression guard on the reason H1.6 exists.

        Every pair above scores well under H1.5's 0.7 overlap threshold, so a
        similarity test cannot reach them. If someone ever "simplifies" H1.6
        back into an overlap check, this fails.
        """
        from lintlang.patterns import _word_overlap

        pairs = [
            ("handles a ticket", "does the ticket thing"),
            ("Search the documentation", "Search through the docs"),
            ("Get user info", "Get user data from the system"),
            ("Look up an order", "Search for orders in the system"),
        ]
        assert all(_word_overlap(a, b) <= 0.7 for a, b in pairs)

    def test_distinct_domains_do_not_fire(self):
        """Two search tools over genuinely different subject matter are fine."""
        assert self._codes(
            ("search_kb", "Search the knowledge base for help articles"),
            ("search_orders", "Search for customer orders by id"),
        ) == []

    def test_opposed_verbs_do_not_fire(self):
        """Create and delete are not interchangeable."""
        assert self._codes(
            ("create_user", "Create a new user account"),
            ("delete_user", "Permanently remove a user account"),
        ) == []

    def test_namespace_prefix_is_a_differentia_for_h16(self):
        """A namespace prefix answers H1.6's question, but not H1.5's.

        H1.6 asks "does anything distinguish these tools" — `asana_search` and
        `jira_search` are distinguished by their prefix, which is the pattern
        Anthropic's guidance recommends, so H1.6 must stay quiet.

        H1.5 asks a narrower question: "are these two descriptions nearly the
        same text?" Here they are byte-identical, and that is worth saying —
        the description is doing no work at all. An earlier version suppressed
        H1.5 whenever the names differed, which silently stopped reporting
        `get_invoice_pdf` vs `get_receipt_pdf` with identical descriptions.
        Name-awareness belongs in H1.6 only.
        """
        codes = self._codes(
            ("asana_search", "Search tasks"),
            ("jira_search", "Search tasks"),
        )
        assert "H1.6" not in codes
        assert "H1.5" in codes

    def test_clean_config_stays_clean(self, clean_tools_config):
        findings = detect_h1(clean_tools_config)
        assert [f for f in findings if f.code == "H1.6"] == []

    def test_short_tokens_still_differentiate(self):
        """Version tags, numeric qualifiers and short abbreviations are real.

        A length floor in the informative-terms filter discarded these, making
        genuinely different tools look identical — and then recommending that
        one of them be deleted. For a `v1`/`v2` pair that is the worst possible
        advice delivered in the most confident voice.
        """
        pairs = [
            (ToolDef("get_po", "Fetch a PO by identifier"),
             ToolDef("get_so", "Fetch a SO by identifier")),
            (ToolDef("search_v1", "Search the legacy v1 index"),
             ToolDef("search_v2", "Search the v2 index")),
            (ToolDef("get_top_10_results", "Return the top 10 results"),
             ToolDef("get_top_100_results", "Return the top 100 results")),
        ]
        for pair in pairs:
            findings = detect_h1(AgentConfig(tools=list(pair)))
            offenders = [f for f in findings if f.code == "H1.6"]
            assert offenders == [], (
                f"{pair[0].name} vs {pair[1].name} are distinguishable: "
                f"{offenders[0].description if offenders else ''}"
            )

    def test_domination_is_reported(self):
        """One-sided emptiness is a defect too, and names which tool to repair.

        If every term in A already appears in B, a model has no reason to ever
        select A. Checking only for *mutual* emptiness silently drops this, which
        is the more common and more actionable shape.
        """
        config = AgentConfig(
            tools=[
                ToolDef("create_user", "Create a new user record"),
                ToolDef("add_user", "Create a new user account"),
            ]
        )
        h16 = [f for f in detect_h1(config) if f.code == "H1.6"]
        assert h16, "domination must be reported"
        assert "dominated by" in h16[0].description
        assert "create_user" in h16[0].description

    def test_list_search_and_read_are_distinct_operations(self):
        """`list` enumerates, `search` filters, `read` fetches by identity.

        These are the most common tool-pair shapes in an MCP server. Treating
        them as synonyms fires on almost every real server.
        """
        for pair in (
            (ToolDef("list_issues", "List all issues"), ToolDef("search_issues", "Search the issues")),
            (ToolDef("list_files", "List files"), ToolDef("read_file", "Read the file")),
        ):
            findings = detect_h1(AgentConfig(tools=list(pair)))
            assert [f for f in findings if f.code == "H1.6"] == []

    def test_store_is_a_verb_not_a_container(self):
        """`store` must not canonicalize into the low-information container class.

        If it does, `fidelis_store` loses its only verb and looks dominated by
        `fidelis_recall`.
        """
        config = AgentConfig(
            tools=[
                ToolDef("fidelis_recall", "Recall facts from memory"),
                ToolDef("fidelis_store", "Store a fact into memory"),
            ]
        )
        assert [f for f in detect_h1(config) if f.code == "H1.6"] == []

    def test_explicit_cross_reference_is_not_a_defect(self):
        """A pair that disambiguates itself inline is already correct.

        Naming the sibling also pulls the sibling's vocabulary into this tool's
        term set, so without this guard the best-written pairs are the ones
        flagged — the measure inverts exactly where it should stay quiet.
        """
        config = AgentConfig(
            tools=[
                ToolDef(
                    "get_weather",
                    "Retrieve current weather. Use get_forecast for future predictions.",
                ),
                ToolDef(
                    "get_forecast",
                    "Retrieve a multi-day forecast. Use get_weather for current conditions.",
                ),
            ]
        )
        assert [f for f in detect_h1(config) if f.code == "H1.6"] == []

    def test_prose_is_not_a_cross_reference(self):
        """Only a verbatim identifier counts as naming a sibling.

        "Get user data from the database" opens with the exact word sequence of
        a tool named `get_user`, and that is prose, not a reference.
        """
        config = AgentConfig(
            tools=[
                ToolDef("get_user", "Get user data from the database system"),
                ToolDef("fetch_user", "Get user data from the database"),
            ]
        )
        codes = [f.code for f in detect_h1(config)]
        assert "H1.5" in codes or "H1.6" in codes

    def test_sub_id_does_not_change_pattern_id(self):
        """Sub-codes narrow a finding; they must not renumber it."""
        config = AgentConfig(
            tools=[
                ToolDef("get_user_info", "Get user info"),
                ToolDef("get_user_data", "Get user data from the system"),
            ]
        )
        h16 = [f for f in detect_h1(config) if f.code == "H1.6"]
        assert h16 and all(f.pattern_id == "H1" for f in h16)


# ── H2: Missing Constraint Scaffolding ─────────────────────────────


class TestH2:
    def test_no_prompt_returns_empty(self, empty_config):
        assert detect_h2(empty_config) == []

    def test_clean_config_with_constraints(self, clean_tools_config):
        findings = detect_h2(clean_tools_config)
        # Should not flag missing constraints since the config has them
        critical = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical) == 0

    def test_unbounded_retry(self):
        config = AgentConfig(
            system_prompt="If the task fails, keep trying until it succeeds.",
            tools=[ToolDef(name="t", description="test tool for doing things")],
        )
        findings = detect_h2(config)
        assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_retry_until_still_flags_an_unbounded_retry(self):
        config = AgentConfig(system_prompt="If push fails, resolve and retry until it succeeds.")

        findings = detect_h2(config)

        assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_negated_retry_prohibition_does_not_flag(self):
        for prompt in (
            "Never retry until the prompt stops appearing.",
            "Do not retry until the user updates the input.",
            "Don't retry until the test is red again.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))

            assert not any(f.severity == Severity.CRITICAL for f in findings)

    def test_dont_stop_pattern(self):
        config = AgentConfig(
            system_prompt="Don't stop until the analysis is complete.",
            tools=[ToolDef(name="t", description="test tool for doing things")],
        )
        findings = detect_h2(config)
        assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_bounded_verification_loop_with_explicit_criteria_and_checks(self):
        """A verification loop is bounded when its local exit is concrete."""
        config = AgentConfig(
            system_prompt=(
                "## Goal-Driven Execution\n\n"
                "Define success criteria. Loop until verified.\n\n"
                "Transform tasks into verifiable goals: write tests for invalid inputs, "
                "then make them pass.\n"
            )
        )

        assert not any(f.severity == Severity.CRITICAL for f in detect_h2(config))

    def test_bare_or_retry_loop_remains_critical_despite_success_criteria(self):
        for prompt in (
            "Define success criteria. Loop until verified.",
            "Define success criteria. Loop until verified. Transform tasks into verifiable goals.",
            "Define success criteria. Keep trying until it succeeds. Write tests and make them pass.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_loop_over_through_finite_collection_does_not_flag(self):
        """'Loop over/through' describing ordinary enumeration is not an infinite-loop risk."""
        for prompt in (
            "Loop through each file in the folder, appending its contents to the report.",
            "Loop over the search results and extract the title of each one.",
            "Loop through every brick and check if the ball's center is within its bounds.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert not any(f.severity == Severity.CRITICAL for f in findings)

    def test_loop_over_through_with_indefinite_signal_still_flags(self):
        """An explicit indefinite-continuation signal keeps 'loop over/through' as a real risk."""
        for prompt in (
            "Loop over the queue indefinitely, processing new items as they arrive.",
            "Loop through the task list forever until told otherwise.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert any(f.severity == Severity.CRITICAL for f in findings)

    def test_loop_over_through_signal_in_later_clause_does_not_flag(self):
        """An indefinite signal in a later sentence or clause does not qualify the traversal."""
        for prompt in (
            "Loop through the files in the folder. Continuously monitor the log for errors.",
            "Loop over the results; the service runs continuously.",
            "Loop through each file, then continuously watch for new uploads.",
            "Loop over the rows\nRun the scheduler forever.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert not any(f.severity == Severity.CRITICAL for f in findings), prompt

    def test_loop_over_through_signal_in_same_clause_still_flags(self):
        """Clause scoping keeps same-clause signals and ignores negations in earlier sentences."""
        for prompt in (
            "Loop over incoming events, continuously polling for new ones.",
            "Do not stop early. Loop over the queue indefinitely.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert any(f.severity == Severity.CRITICAL for f in findings), prompt

    def test_negated_indefinite_loop_traversal_does_not_flag(self):
        """A prohibition against indefinite traversal is not an unbounded-loop instruction."""
        for prompt in (
            "Do not loop over the queue indefinitely.",
            "Never loop through the task list forever.",
            "Don't continuously loop over the queue indefinitely.",
            "Never ever loop through the task list forever.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert not any(f.severity == Severity.CRITICAL for f in findings), prompt

    def test_negation_not_attached_to_traversal_still_flags(self):
        """A negator separated from the traversal by non-adverbs or a clause break is not a prohibition."""
        for prompt in (
            "Never give up and loop over tasks forever.",
            "Do not stop, just loop over the queue indefinitely.",
            "Never stop; loop over the queue forever.",
            "Don't only loop over the queue indefinitely.",
        ):
            findings = detect_h2(AgentConfig(system_prompt=prompt))
            assert any(f.severity == Severity.CRITICAL for f in findings), prompt

    # ── One negation guard for every unbounded-behavior pattern ────
    #
    # H2 findings are CRITICAL, so these tests hold the guard to one rule: a
    # prohibition it can positively recognize becomes clean, and everything it
    # cannot stays reported.

    @staticmethod
    def _critical(prompt: str) -> list:
        return [f for f in detect_h2(AgentConfig(system_prompt=prompt)) if f.severity == Severity.CRITICAL]

    def test_reported_false_positive_a_prohibition_is_not_an_unbounded_instruction(self):
        """Regression: this prompt forbids unbounded continuation and scanned FAIL."""
        prompt = "You are a queue monitor. Do not continue indefinitely; stop at the first terminal result."

        assert detect_h2(AgentConfig(system_prompt=prompt)) == []

    def test_each_pattern_is_clean_when_negated_and_reported_when_not(self):
        """Every ``DANGEROUS_PATTERNS`` entry, once negated and once as an instruction."""
        for negated, instructed in (
            ("Do not keep trying until it works; make one attempt and report.", "Keep trying until it works."),
            ("Never retry until success.", "Retry until success."),
            ("Do not retry as many times as you like.", "Retry as many times as it takes."),
            ("Don't loop until the API responds. Poll at most three times.", "Loop until the API responds."),
            ("Do not loop over the queue indefinitely.", "Loop over the queue indefinitely."),
            ("Never loop through the task list forever.", "Loop through the task list forever."),
            ("Pause and do not continue until the operator approves.", "Continue until every ticket is closed."),
            ("Never continue indefinitely.", "Continue indefinitely."),
        ):
            assert not self._critical(negated), negated
            assert self._critical(instructed), instructed

        # ``don't stop until`` is itself a negative instruction to keep going.
        # A negator in front of it is a double negation, not a prohibition.
        assert self._critical("Don't stop until the queue is empty.")
        assert self._critical("Never don't stop until the queue is empty.")

    def test_negated_prohibition_corpus_boundary(self):
        cases = [json.loads(line) for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        case = next(case for case in cases if case["case_id"] == "LL-H2-NEGATION-001")

        for variant in case["variants"]:
            assert len(self._critical(variant["text"])) == variant["expect"]["h2_critical"], variant["variant_id"]

    def test_negated_prohibition_scanner_fixture(self):
        result = scan_file(SAMPLES_DIR / "h2_negated_prohibition.yaml")

        assert result.input_error is None
        assert [f for f in result.structural_findings if f.pattern_id == "H2"] == []

    def test_negator_vocabulary_case_and_apostrophes(self):
        for prompt in (
            "Never continue indefinitely.",
            "Do not continue indefinitely.",
            "Don't continue indefinitely.",
            "Dont continue indefinitely.",
            "DON’T continue indefinitely.",
            "DO NOT CONTINUE INDEFINITELY.",
            "You should not continue until every record is processed; stop after 50 records.",
            "The agent shouldn't keep trying until it works.",
            "The agent shouldn’t keep trying until it works.",
            "You must not continue indefinitely.",
            "MUST NOT continue indefinitely.",
            "You mustn't retry until success.",
            "You cannot continue indefinitely.",
            "The worker can't loop until the API responds.",
        ):
            assert not self._critical(prompt), prompt

    def test_unbounded_instruction_with_a_negation_elsewhere_still_flags(self):
        """A negator that does not sit directly on the behavior forbids something else."""
        for prompt in (
            "Do not stop; continue indefinitely.",
            "Never stop retrying. Keep trying until it works.",
            "Never give up and keep trying until the deploy succeeds.",
            "Do not pause, continue until every ticket is closed.",
            "Do not skip records and continue indefinitely.",
            "Never idle\ncontinue indefinitely",
            "You should not hesitate to keep trying until it works.",
            "never mind the limit, continue indefinitely",
            "I said never. Continue until done.",
            "Never reveal credentials. Keep trying until the deployment succeeds.",
            "Never assume failure is final: retry until the service answers.",
            "If the user says never mind, continue until finished anyway.",
            "Do not quietly abort - really keep trying until it succeeds.",
            "Never stop: loop until done.",
        ):
            assert self._critical(prompt), prompt

    def test_double_negation_still_flags(self):
        for prompt in (
            "Do not refuse to keep trying until it works.",
            "Do not fail to continue until completion.",
            "Never not continue until done.",
            "Do not never retry until success.",
            "You can't not keep trying until it works.",
            "There is no reason you should not continue indefinitely.",
            "It is not true that you must not continue indefinitely.",
            "Nobody said you can't; you cannot not retry until success.",
        ):
            assert self._critical(prompt), prompt

        # Sibling prohibitions in separate clauses are each still a prohibition,
        # and "without" in the subject does not negate the prohibition.
        assert not self._critical("Do not continue indefinitely, and do not retry until success.")
        assert not self._critical("Agents without approval must not continue indefinitely.")

    def test_a_parenthetical_comma_does_not_hide_an_earlier_negative(self):
        """A comma only starts a new left-hand clause when it closes a fronted
        condition or opens a coordinated clause.

        Reported: taking the last comma let a parenthetical or a complement
        clause hide the earlier negative, so a double negation scanned clean.
        """
        for prompt in (
            "It is not true, however, that you must never retry until it works.",
            "It is not true, in general, that you must not continue indefinitely.",
            "There is no reason, the runbook says, that you should not continue indefinitely.",
        ):
            assert self._critical(prompt), prompt

        # HARD NEGATIVES: a coordinated sibling clause closes the clause, so
        # the earlier prohibition is not read as an earlier negative and these
        # stay silent.
        for prompt in (
            "Do not continue indefinitely, and do not retry until success.",
            "Stop at the first error, and never retry until it works.",
        ):
            assert not self._critical(prompt), prompt

    def test_apostrophe_less_negatives_count_like_their_contractions(self):
        """An earlier negative is read the same way with or without its apostrophe."""
        for with_apostrophe, without_apostrophe in (
            ("It won't help to never retry until success.", "It wont help to never retry until success."),
            (
                "It doesn't say you must not continue indefinitely.",
                "It doesnt say you must not continue indefinitely.",
            ),
            (
                "It didn't say you must not continue indefinitely.",
                "It didnt say you must not continue indefinitely.",
            ),
            (
                "It isn't true that you must never retry until it works.",
                "It isnt true that you must never retry until it works.",
            ),
        ):
            assert self._critical(with_apostrophe), with_apostrophe
            assert self._critical(without_apostrophe), without_apostrophe

        # HARD NEGATIVES: the apostrophe-less forms are whole words, not
        # substrings of ordinary ones, and an unnegated clause stays silent.
        for prompt in (
            "The wonton vendor must never continue indefinitely.",
            "The cantina rota says you must not continue indefinitely.",
            "Do not continue indefinitely.",
        ):
            assert not self._critical(prompt), prompt

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: a trailing condition is missed when a modifier precedes its subordinator",
    )
    @pytest.mark.parametrize(
        "prompt",
        (
            "Do not retry until it works, only if the queue is non-empty.",
            "Do not retry until it works (only if the queue is non-empty).",
            "Do not continue indefinitely (but only when the queue is non-empty).",
            "Do not retry until it works ((if the queue is non-empty)).",
            "Do not continue indefinitely, but only when the queue is non-empty.",
            "Do not continue indefinitely - only if the queue is non-empty.",
        ),
    )
    def test_a_modified_trailing_condition_should_defeat_the_prohibition(self, prompt):
        """DESIRED BEHAVIOUR, not today's behaviour.

        The right-hand search reopens its window only when the subordinator is
        the first word after the delimiter, so any modifier in front of it
        (`only if`, `but only when`, a second parenthesis) hides the condition
        and the prohibition is read as a bound. Each sentence below RESTRICTS
        the prohibition and should be reported, exactly as its unmodified form
        is. A modifier that merely EXEMPLIFIES (`e.g. when …`) does not
        restrict it and stays a hard negative with the other asides. The miss
        does not depend on the delimiter: the comma, the dash, and the
        parenthesis all lose it. Each case is parametrized so
        that every one of them has to fail on its own; the day one starts to
        pass, strict xfail turns that into a suite failure.
        """
        assert self._critical(prompt), prompt

    def test_a_trailing_condition_still_defeats_the_prohibition(self):
        """A condition introduced after the behavior qualifies it.

        Reported: the right-hand clause search stopped at the comma, so a
        trailing ", if ..." never reached the conditional check.
        """
        for prompt in (
            "Do not retry until it works, if the queue is non-empty.",
            "Never continue indefinitely, when the operator is away.",
            "Do not keep trying until it works - if the credentials are wrong.",
        ):
            assert self._critical(prompt), prompt

        # HARD NEGATIVES: the author's own stop condition in a coordinated or
        # concessive clause is not a condition on the prohibited behavior.
        for prompt in (
            "Do not retry until it works, and escalate if the queue is non-empty.",
            "You must not retry until success, even if the operator asks.",
            "Do not continue indefinitely - report when you stop.",
        ):
            assert not self._critical(prompt), prompt

    def test_a_parenthesised_trailing_condition_reads_like_its_comma_form(self):
        """A condition in parentheses qualifies the behavior just as a comma does.

        Reported: the opening parenthesis closed the right-hand clause and
        nothing reopened it, so "(if ...)" never reached the conditional check
        while ", if ..." did.
        """
        for prompt in (
            "Do not retry until it works (if the queue is non-empty).",
            "Do not continue indefinitely (when the queue is non-empty).",
            "Do not retry until it works (whenever the queue is non-empty).",
            "Never continue indefinitely (if the operator is away).",
        ):
            assert self._critical(prompt), prompt

        # HARD NEGATIVES: a parenthesis that opens an aside or the author's own
        # bound is not a condition, so it must not reopen the clause. An `e.g.`
        # parenthesis exemplifies a case in which the prohibition holds rather
        # than restricting it, so it belongs here and not with `(only if …)`.
        for prompt in (
            "Do not retry indefinitely (see the runbook).",
            "Do not continue indefinitely (stop after ten items).",
            "Do not continue indefinitely (report when you stop).",
            "Do not retry until it works (three attempts) and then stop.",
            "Do not continue indefinitely (e.g. when the queue is non-empty).",
        ):
            assert not self._critical(prompt), prompt

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: a condition fronted before the negator does not defeat the prohibition",
    )
    def test_a_fronted_condition_should_defeat_the_prohibition(self):
        """DESIRED BEHAVIOUR, not today's behaviour.

        A condition placed after the behaviour makes the prohibition
        conditional and is reported; the same condition moved in front of the
        negator is read as closing its own clause and reports nothing. The two
        say the same thing, so both should be reported. The changelog records
        the asymmetry as a known limitation and as a verdict change relative to
        0.6.0, which reported the fronted form. The day it is reported again,
        this test passes, strict xfail turns that into a suite failure, and the
        marker and the changelog note come off together.

        This covers every fronted condition, whichever negator follows it. A
        coordinated sibling clause (`Do not continue indefinitely, and do not
        retry until success.`) is a different shape and stays a hard negative.
        """
        for prompt in (
            "If the queue is non-empty, do not retry until it works.",
            "When the queue is non-empty, do not continue indefinitely.",
            "When the push fails, do not retry until the conflict is resolved.",
            "If the queue is empty, never continue indefinitely.",
        ):
            assert self._critical(prompt), prompt

    def test_only_listed_adverbs_may_sit_between_negator_and_behavior(self):
        for prompt in (
            "Don't continuously loop over the queue indefinitely.",
            "Never ever retry until success.",
            "Do NOT ever continue until told otherwise; ask after each step.",
            "You should not blindly loop until the API responds.",
            "Never ever endlessly keep trying until it works.",
        ):
            assert not self._critical(prompt), prompt

        # Verbs that merely end in "ly", restrictive adverbs, and a third modifier.
        for prompt in (
            "Never reply early keep trying until it works",
            "Do not comply partially continue until all items are handled",
            "Never reply\nKeep trying until the user answers.",
            "Do not apply retry until success",
            "Do not rely continue until done",
            "Do not supply continue indefinitely",
            "Do not only continue until the first error; process everything.",
            "Do not merely continue until the first error; process everything.",
            "Do not simply loop until done - verify as well, however long it takes.",
            "Do not solely retry until success; also alert the operator.",
            "Don't just keep trying until it works; log each try.",
            "Do not ever blindly repeatedly retry until success.",
        ):
            assert self._critical(prompt), prompt

    def test_conditional_or_interrogative_negation_still_flags(self):
        """An exception licenses the unbounded run; a question is not a prohibition."""
        for prompt in (
            "Do not continue indefinitely unless the operator sets RUN_FOREVER.",
            "Do not continue indefinitely, unless the operator sets RUN_FOREVER.",
            "Unless the operator sets RUN_FOREVER, do not continue indefinitely.",
            "Except for idempotent calls, never retry until success.",
            "Do not continue indefinitely; except when directed otherwise.",
            "Do not continue indefinitely. Unless the operator sets RUN_FOREVER.",
            "Do not retry until success except for idempotent calls.",
            "Data is lost if you don't keep trying until it succeeds.",
            "If you do not continue until the end, the job is lost, so keep going.",
            "Why don't you keep trying until it works?",
            "Why should you never retry until it works?",
            "Is it true that you must not continue indefinitely?",
            "Should the agent never retry until success?",
        ):
            assert self._critical(prompt), prompt

        # A licensing exception belonging to a neighbouring sentence does not
        # reach the prohibition.
        for prompt in (
            "Escalate unless the operator declines. Do not continue indefinitely.",
            "Retry twice, except on 5xx. Never loop over the queue indefinitely.",
        ):
            assert not self._critical(prompt), prompt

    def test_stop_condition_in_a_coordinated_clause_does_not_defeat_the_prohibition(self):
        """The corrected wording a user writes after being flagged — a
        prohibition plus their own stop condition — must not stay CRITICAL."""
        for prompt in (
            "Do not continue indefinitely and stop when the queue drains.",
            "Never loop over the queue indefinitely, and escalate if the backlog grows.",
            "You must not retry until success, even if the operator asks.",
            "Do not continue indefinitely - report when you stop.",
            "Do not continue indefinitely (report when you stop).",
            "- Never continue indefinitely, and say why when you stop",
        ):
            assert not self._critical(prompt), prompt

        # A condition attached to the prohibited behaviour itself still makes
        # the prohibition conditional, so it stays reported.
        for prompt in (
            "Do not keep trying until it works when the credentials are wrong.",
            "Never continue indefinitely if the operator is watching.",
        ):
            assert self._critical(prompt), prompt

    def test_line_breaks_between_negator_and_behavior(self):
        """Hard-wrapped prose is one sentence; a blank line, list marker, or tab is not."""
        for prompt in (
            "The deploy agent should never\nretry until the endpoint answers.",
            "Do not\n  continue indefinitely.",
            "Do not\r\ncontinue indefinitely.",
            "- Do not keep trying until it works\n- Make one attempt",
        ):
            assert not self._critical(prompt), prompt

        for prompt in (
            "Do not\n\nContinue until the user is satisfied.",
            "- Do not\n- continue indefinitely",
            "Do not\tcontinue indefinitely",
        ):
            assert self._critical(prompt), prompt

    def test_second_unbounded_match_in_the_same_sentence_still_flags(self):
        for prompt in (
            "Do not continue until the operator approves, then continue indefinitely.",
            "Do not continue indefinitely, but keep trying until the lock is acquired.",
        ):
            assert len(self._critical(prompt)) == 1, prompt

        assert not self._critical("Do not continue indefinitely, and do not retry until success.")

    def test_negated_continuation_signal_uses_the_same_guard(self):
        assert not self._critical("Loop over the items but never indefinitely.")
        # Words between the negator and the signal leave the meaning open.
        assert self._critical("Loop over the queue and do not stop processing forever.")

    def test_known_limitations_stay_reported(self):
        """Prohibitions the guard does not recognize. They stay CRITICAL by design.

        An interrupted negator, a delegated one, and a subjectless "Cannot" are
        left reported rather than guessed at. Rewording them with the negator
        directly on the behavior ("Never continue indefinitely.") scans clean.
        """
        for prompt in (
            "Do not, under any circumstances, continue indefinitely.",
            "Never, ever continue indefinitely.",
            "Do not let the agent continue indefinitely.",
            "Do not allow it to keep trying until it works.",
            "Cannot continue indefinitely: cap the run at 10 steps.",
        ):
            assert self._critical(prompt), prompt

    def test_reported_description_and_evidence_are_unchanged(self):
        """Baselines fingerprint description and evidence; the guard must not move them."""
        expected = {
            "If the task fails, keep trying until it succeeds.": (
                "Unbounded retry loop — 'keep trying until' needs an explicit limit.",
                "If the task fails, keep trying until it succeeds.",
            ),
            "If push fails, resolve and retry until it succeeds.": (
                "Unbounded retry — add max_retries or a fallback.",
                "fails, resolve and retry until it succeeds.",
            ),
            "Don't stop until the analysis is complete.": (
                "Negative termination condition — rephrase as a positive bound.",
                "Don't stop until the analysis is complete.",
            ),
            "Define success criteria. Loop until verified.": (
                "Potential infinite loop — ensure a max iteration count.",
                "e success criteria. Loop until verified.",
            ),
            "Loop over the queue indefinitely, processing new items as they arrive.": (
                "Potential infinite loop — ensure a max iteration count.",
                "Loop over the queue indefinitely, processing new",
            ),
            "Do not stop; continue indefinitely.": (
                "Unbounded continuation — add an explicit termination condition.",
                "Do not stop; continue indefinitely.",
            ),
        }
        for prompt, (description, evidence) in expected.items():
            (finding,) = self._critical(prompt)
            assert (finding.description, finding.evidence) == (description, evidence), prompt

    def test_missing_constraints_with_tools(self):
        config = AgentConfig(
            system_prompt="You are an assistant. Use the tools to help.",
            tools=[ToolDef(name="search", description="Search the database for records matching a query")],
        )
        findings = detect_h2(config)
        assert any(f.severity == Severity.HIGH and "no termination" in f.description.lower() for f in findings)

    def test_has_max_iterations(self):
        config = AgentConfig(
            system_prompt="You have a max_iterations of 5. Use tools wisely.",
            tools=[ToolDef(name="search", description="Search the database for records matching a query")],
        )
        findings = detect_h2(config)
        missing = [f for f in findings if "no termination" in f.description.lower()]
        assert len(missing) == 0

    def test_suggested_numeric_budget_clears_missing_constraint_finding(self):
        config = AgentConfig(
            system_prompt=(
                "You have a maximum of 5 tool calls per task. "
                "If no progress after 2 attempts, stop and report the issue."
            ),
            tools=[ToolDef(name="search", description="Search the database for records matching a query")],
        )

        findings = detect_h2(config)

        assert not any("no termination" in finding.description.lower() for finding in findings)

    def test_substring_false_negative_limited(self):
        """Word 'limited' should NOT suppress constraint warning (it's not 'limit')."""
        config = AgentConfig(
            system_prompt="You have limited knowledge. Use the tools to help.",
            tools=[ToolDef(name="search", description="Search the database for records matching a query")],
        )
        findings = detect_h2(config)
        assert any("no termination" in f.description.lower() for f in findings)


# ── H3: Schema-Intent Mismatch ─────────────────────────────────────


class TestH3:
    def test_no_tools_returns_empty(self, empty_config):
        assert detect_h3(empty_config) == []

    def test_clean_tools_minimal_findings(self, clean_tools_config):
        findings = detect_h3(clean_tools_config)
        # Clean config should have described parameters
        critical = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(critical) == 0

    def test_missing_param_description(self):
        config = AgentConfig(
            tools=[
                ToolDef(
                    name="tool",
                    description="A tool",
                    parameters={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                ),
            ]
        )
        findings = detect_h3(config)
        assert any("no description" in f.description for f in findings)

    def test_generic_param_names(self):
        config = AgentConfig(
            tools=[
                ToolDef(
                    name="tool",
                    description="A tool",
                    parameters={
                        "type": "object",
                        "properties": {"data": {"type": "string"}},
                    },
                ),
            ]
        )
        findings = detect_h3(config)
        assert any("generic name" in f.description for f in findings)

    def test_undescribed_anyof_variants(self):
        config = AgentConfig(
            tools=[
                ToolDef(
                    name="tool",
                    description="A tool",
                    parameters={
                        "type": "object",
                        "properties": {
                            "input": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "object"},
                                ],
                            },
                        },
                    },
                ),
            ]
        )
        findings = detect_h3(config)
        assert any("anyOf" in f.description and "undescribed" in f.description for f in findings)

    def test_nested_object_properties_checked(self):
        """Nested object properties should also be checked for missing descriptions."""
        config = AgentConfig(
            tools=[
                ToolDef(
                    name="tool",
                    description="A tool",
                    parameters={
                        "type": "object",
                        "properties": {
                            "filter": {
                                "type": "object",
                                "description": "Filter criteria",
                                "properties": {
                                    "data": {"type": "string"},  # generic + no description
                                },
                            },
                        },
                    },
                ),
            ]
        )
        findings = detect_h3(config)
        assert any("data" in f.description and "generic" in f.description for f in findings)
        assert any("data" in f.description and "no description" in f.description for f in findings)

    def test_phantom_required_field(self):
        """Required field not in properties should be flagged."""
        config = AgentConfig(
            tools=[
                ToolDef(
                    name="tool",
                    description="A tool",
                    parameters={
                        "type": "object",
                        "properties": {"name": {"type": "string", "description": "User name"}},
                        "required": ["name", "ghost_field"],
                    },
                ),
            ]
        )
        findings = detect_h3(config)
        assert any("ghost_field" in f.description and "does not exist" in f.description for f in findings)


# ── H4: Context Boundary Erosion ───────────────────────────────────


class TestH4:
    def test_no_prompt_returns_empty(self, empty_config):
        assert detect_h4(empty_config) == []

    def test_clean_config_no_erosion(self, clean_tools_config):
        findings = detect_h4(clean_tools_config)
        assert len(findings) == 0

    def test_remember_everything_pattern(self):
        config = AgentConfig(system_prompt="Remember everything the user tells you across the conversation.")
        findings = detect_h4(config)
        assert any("unbounded memory" in f.description.lower() for f in findings)

    def test_use_all_history_pattern(self):
        config = AgentConfig(
            system_prompt="Use all conversation history to maintain context and provide better answers."
        )
        findings = detect_h4(config)
        assert any("entire history" in f.description.lower() for f in findings)

    def test_always_persist_domain_invariant_does_not_flag(self):
        """'Always keep/maintain/remember' over a domain object is not context-boundary erosion."""
        for prompt in (
            "Always maintain respect for the author's voice while improving clarity.",
            "Always maintain backward compatibility.",
            "Always keep responses under 200 words.",
            "Always maintain state consistency.",
            "Always keep results sorted.",
        ):
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert not any("persistence without scope" in f.description.lower() for f in findings)

    def test_always_persist_bare_temporal_or_later_clause_does_not_flag(self):
        """Bare temporal words and context nouns in a later clause are not persistence evidence."""
        for prompt in (
            "Always keep results sorted before returning them.",
            "Always keep responses short. Previous messages are irrelevant.",
            "Always maintain a formal tone; the conversation history is handled elsewhere.",
            "Always keep answers concise, and never reuse past context.",
        ):
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert not any("persistence without scope" in f.description.lower() for f in findings), prompt

    def test_always_persist_contextual_prior_phrases_still_flag(self):
        """Temporal words tied to a prior-state object in the same clause remain erosion risk."""
        for prompt in (
            "Always remember details from before.",
            "Always keep the prior session's decisions in mind.",
            "Always maintain consistency with previous answers.",
        ):
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert any("persistence without scope" in f.description.lower() for f in findings), prompt

    def test_always_persist_cross_context_still_flags(self):
        """'Always keep/maintain/remember' naming context/history/prior state is still erosion risk."""
        for prompt in (
            "Always keep track of what the user said before.",
            "Always remember the full conversation history so nothing is lost between requests.",
            "Always maintain the previous session's state across tasks.",
        ):
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert any("persistence without scope" in f.description.lower() for f in findings)

    def test_long_prompt_no_boundaries(self):
        """POSITIVE CONTROL: a long, stateful prompt with no boundary vocabulary still flags."""
        config = AgentConfig(system_prompt=_LONG_STATEFUL_PROMPT)
        assert len(_LONG_STATEFUL_PROMPT) > 500
        findings = detect_h4(config)
        assert any("no context boundary" in f.description.lower() for f in findings)

    def test_long_prompt_without_statefulness_is_not_reported(self):
        """HARD NEGATIVE: length alone is no longer evidence of boundary erosion."""
        config = AgentConfig(system_prompt="x " * 300)  # Long prompt, no boundary markers
        findings = detect_h4(config)
        assert not any("no context boundary" in f.description.lower() for f in findings)

    def test_long_single_shot_reference_prose_is_not_reported(self):
        """HARD NEGATIVE: a long stateless reference document has no boundary to erode."""
        prompt = (
            "You are a release checklist reader for a Python packaging repository. "
            "Report the version recorded in the project metadata. "
            "Report the wheel and sdist artifact names. "
            "Report whether the license file is present. "
            "Report the declared minimum interpreter version. "
            "Quote the exact line you used for each answer. "
            "If a field is absent, say that it is absent and name the file you looked in. "
            "Do not infer a value that the metadata does not state. "
            "Answer each question with one sentence and one quoted line. "
        ) * 2
        assert len(prompt) > 500
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert not any("no context boundary" in f.description.lower() for f in findings)

    def test_length_alone_never_reports(self):
        """HARD NEGATIVE: length is not sufficient evidence of boundary erosion.

        The CHANGELOG records that this finding now requires demonstrated
        cross-context statefulness. A long, single-shot prompt that never asks
        the agent to carry anything between turns has nothing to erode, so
        silence here is the rule working, not a miss. Changing this assertion
        is a decision to widen the rule again, not a fix.
        """
        prompt = "Summarize the attached invoice line by line. " * 40
        assert len(prompt) > 500
        assert "\n" not in prompt  # no headings, no separators, no boundary vocabulary
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert not any("no context boundary" in f.description.lower() for f in findings)

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: the statefulness gate is a recognizer and misses unlisted wording",
    )
    def test_unrecognized_statefulness_phrasing_should_be_reported(self):
        """DESIRED BEHAVIOUR, not today's behaviour.

        These prompts do ask the agent to carry something between turns, but
        they say so in wording the gate does not recognize, so the finding is
        missed. Each is an ordinary way to write the risky instruction, so the
        rule should report them. The day it does, this test passes, strict
        xfail turns that into a suite failure, and the marker and the changelog
        note both come off — a visible decision rather than a silent drift.
        """
        for tail in (
            "Keep the running tally from earlier questions in mind.",
            "Build on what the customer told you a moment ago.",
            "Your notes from the last ticket stay relevant.",
        ):
            prompt = ("Answer support questions about billing. " * 20) + tail
            assert len(prompt) > 500
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert any("no context boundary" in f.description.lower() for f in findings), tail

    @pytest.mark.parametrize("relative_path", _LINTLANG_INSTRUCTION_SURFACES)
    def test_lintlang_own_instruction_prose_is_not_boundary_erosion(self, relative_path):
        """HARD NEGATIVE: LintLang's own shipped AGENTS/SKILL prose (RESEARCH.md section 5)."""
        prompt = _repo_text(relative_path)
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert not any("no context boundary" in f.description.lower() for f in findings), relative_path

    def test_statefulness_gate_recognizes_cross_context_instructions(self):
        """POSITIVE CONTROL: each demonstrated statefulness signal keeps the rule live."""
        for tail in (
            "Use the conversation history when you answer.",
            "Carry over state between tasks.",
            "Reuse the previous turn's results.",
            "Remember everything the operator types.",
            "Maintain full context across requests.",
        ):
            prompt = ("Answer support questions about billing. " * 20) + tail
            assert len(prompt) > 500
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert any("no context boundary" in f.description.lower() for f in findings), tail

    def test_many_messages_no_boundaries(self):
        messages = [{"role": "system", "content": "You are helpful."}]
        for i in range(14):
            role = "user" if i % 2 == 0 else "assistant"
            messages.append({"role": role, "content": f"msg {i}"})
        config = AgentConfig(messages=messages)
        findings = detect_h4(config)
        assert any(
            "boundary marker" in f.description.lower() or "no task boundary" in f.description.lower() for f in findings
        )

    def test_substring_false_negative_microscope(self):
        """Word 'microscope' should NOT suppress boundary warning (it's not 'scope')."""
        config = AgentConfig(
            system_prompt=("Use the microscope to examine the sample carefully. " * 30)
            + "Remember everything the operator reports."
        )
        findings = detect_h4(config)
        assert any("no context boundary" in f.description.lower() for f in findings)

    def test_cross_session_carryover_instruction_still_flags(self):
        """POSITIVE CONTROL (RESEARCH.md gap): ordinary English cross-session carryover.

        No closed-vocabulary word like 'maintain state' or 'context window' appears;
        the instruction is phrased as carrying behaviour into a future request from
        the same person, even in a brand new chat window.
        """
        prompt = (
            ("You are a helpful assistant for a support desk. " * 30)
            + "Once you learn a customer's account preferences, keep applying them "
            "automatically to every future request from that same person without "
            "asking again, even in a brand new chat window."
        )
        assert len(prompt) > 500
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert any("no context boundary" in f.description.lower() for f in findings)

    def test_cross_session_phrasing_signals_recognized_individually(self):
        """POSITIVE CONTROL: each widened cross-session phrasing keeps the rule live."""
        for tail in (
            "Apply the same settings to every future request the customer sends.",
            "Keep using those preferences from that same customer going forward.",
            "Next time they ask a question, reuse what you learned about them.",
            "Carry the preference forward even in a brand new chat window.",
        ):
            prompt = ("Answer support questions about billing. " * 20) + tail
            assert len(prompt) > 500
            findings = detect_h4(AgentConfig(system_prompt=prompt))
            assert any("no context boundary" in f.description.lower() for f in findings), tail

    def test_future_request_and_chat_mention_without_persistence_is_not_reported(self):
        """HARD NEGATIVE: mentioning 'request' and 'chat' with no persistence instruction."""
        prompt = (
            "Handle each request politely and answer questions in the chat. "
            "Every request should be answered within one reply. "
        ) * 15
        assert len(prompt) > 500
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert not any("no context boundary" in f.description.lower() for f in findings)

    def test_generic_future_and_new_session_mentions_without_instruction_are_not_reported(self):
        """HARD NEGATIVE: 'future' and 'new session' as plain vocabulary, not an instruction."""
        prompt = (
            "This document describes future plans for the support desk product. "
            "A new session begins whenever the operator opens the console. "
            "Sessions are independent and nothing here asks the agent to carry "
            "anything between them. "
        ) * 6
        assert len(prompt) > 500
        findings = detect_h4(AgentConfig(system_prompt=prompt))
        assert not any("no context boundary" in f.description.lower() for f in findings)


# ── H5: Implicit Instruction Failure ───────────────────────────────


class TestH5:
    def test_no_prompt_returns_empty(self, empty_config):
        assert detect_h5(empty_config) == []

    def test_clean_config_minimal_findings(self, clean_tools_config):
        findings = detect_h5(clean_tools_config)
        # Clean config uses positive, explicit instructions
        high_or_above = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(high_or_above) == 0

    def test_many_negatives(self):
        config = AgentConfig(system_prompt="Don't do this. Never do that. Avoid this. Do not do the other thing.")
        findings = detect_h5(config)
        assert any("negative instruction" in f.description.lower() for f in findings)

    def test_vague_qualifiers(self):
        config = AgentConfig(system_prompt="Be concise and helpful. Use common sense when responding.")
        findings = detect_h5(config)
        assert any("vague" in f.description.lower() or "inference" in f.description.lower() for f in findings)

    def test_no_priority_with_many_instructions(self, bad_prompt_config):
        findings = detect_h5(bad_prompt_config)
        assert any("priority" in f.description.lower() for f in findings)

    def test_per_negative_low_notices_are_not_emitted(self):
        """The per-negative LOW notices were removed; only the density MEDIUM remains."""
        prompt = (
            "Do not install anything persistently on the user's machine.\n"
            "Don't rewrite the user's file.\n"
            "Never invent a finding that the tool did not report.\n"
            "Avoid offering this skill for general linting.\n"
            "Do not guess a runner that is not installed.\n"
        )
        findings = detect_h5(AgentConfig(system_prompt=prompt))
        assert not any("could be reframed positively" in f.description for f in findings)

    def test_negative_density_medium_survives(self):
        """POSITIVE CONTROL: the aggregated >3-negatives density MEDIUM is unchanged."""
        prompt = "Don't do this. Never do that. Avoid this. Do not do the other thing."
        findings = detect_h5(AgentConfig(system_prompt=prompt))
        density = [f for f in findings if "negative instructions" in f.description]
        assert len(density) == 1
        assert density[0].severity == Severity.MEDIUM
        assert density[0].location == "system_prompt"
        assert density[0].description == (
            "System prompt has 4 negative instructions ('don't', 'never', 'avoid'). "
            "Models follow positive instructions more reliably."
        )

    @pytest.mark.parametrize("relative_path", _LINTLANG_INSTRUCTION_SURFACES)
    def test_lintlang_own_instruction_prose_has_no_per_negative_notice(self, relative_path):
        """HARD NEGATIVE: legitimate negative directives no longer produce LOW notices."""
        findings = detect_h5(AgentConfig(system_prompt=_repo_text(relative_path)))
        assert not any("could be reframed positively" in f.description for f in findings), relative_path


# ── H6: Template Format Contract Violation ─────────────────────────


class TestH6:
    def test_no_prompt_returns_empty(self, empty_config):
        assert detect_h6(empty_config) == []

    def test_multiple_formats(self):
        """POSITIVE CONTROL: three competing output-format instructions, description unchanged."""
        config = AgentConfig(system_prompt="Respond in JSON for data. Use markdown for text. XML for configs.")
        findings = detect_h6(config)
        assert any("multiple output formats" in f.description for f in findings)
        mixed = [f for f in findings if "multiple output formats" in f.description]
        assert mixed[0].description == (
            "System prompt references multiple output formats (JSON, Markdown, XML) "
            "— model may produce hybrid output."
        )
        assert mixed[0].severity == Severity.MEDIUM

    def test_coordinated_output_format_instruction_still_flags(self):
        """POSITIVE CONTROL: one instruction naming both formats keeps its identity."""
        findings = detect_h6(AgentConfig(system_prompt="Respond in JSON and Markdown."))
        mixed = [f for f in findings if "multiple output formats" in f.description]
        assert len(mixed) == 1
        assert mixed[0].severity == Severity.MEDIUM
        assert mixed[0].location == "system_prompt"
        assert mixed[0].description == (
            "System prompt references multiple output formats (JSON, Markdown) "
            "— model may produce hybrid output."
        )
        assert mixed[0].evidence == ""

    def test_mere_format_mention_is_not_a_contract_violation(self):
        """HARD NEGATIVE: naming formats as accepted inputs is not a competing contract."""
        for prompt in (
            "Audit a named config file (YAML, JSON, Markdown, text, or Python) with the CLI.",
            "LintLang reads JSON and Markdown instruction files. Respond in JSON.",
            "Configs can be syntactically valid YAML/JSON while the Markdown docs disagree.",
            "The report is Markdown. It summarises the XML schema the tool validates.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert not any("multiple output formats" in f.description for f in findings), prompt

    def test_two_real_output_instructions_still_flag(self):
        """POSITIVE CONTROL: two genuine output instructions still report at MEDIUM."""
        config = AgentConfig(
            system_prompt="Return the answer as markdown. Output format: JSON for every structured field."
        )
        findings = detect_h6(config)
        mixed = [f for f in findings if "multiple output formats" in f.description]
        assert len(mixed) == 1
        assert mixed[0].severity == Severity.MEDIUM

    def test_schema_conformance_and_write_verb_instructions_still_flag(self):
        """POSITIVE CONTROL (RESEARCH.md gap): ordinary phrasing the closed verb/shape

        list previously missed — a schema-conformance clause ('responses conform
        to this JSON schema') and an output verb outside the original list
        ('write your reply as ... Markdown').
        """
        prompt = (
            "All API responses conform to this JSON schema: {result: string, confidence: number}. "
            "When talking to end users in chat, write your reply as friendly Markdown text with "
            "headings, not the raw JSON object, since users find raw JSON confusing to read."
        )
        findings = detect_h6(AgentConfig(system_prompt=prompt))
        mixed = [f for f in findings if "multiple output formats" in f.description]
        assert len(mixed) == 1
        assert mixed[0].severity == Severity.MEDIUM
        assert "JSON" in mixed[0].description and "Markdown" in mixed[0].description

    def test_widened_output_shapes_recognized_individually(self):
        """POSITIVE CONTROL: each widened output-instruction shape keeps the rule live."""
        for prompt in (
            "Write the summary as clean Markdown. Responses conform to this JSON schema.",
            "Write your answer in plain XML. Output adheres to the Markdown template.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert any("multiple output formats" in f.description for f in findings), prompt

    def test_widened_shapes_do_not_become_bare_mention_counting(self):
        """HARD NEGATIVE: naming formats without an output instruction is still not a violation."""
        for prompt in (
            "The scanner reads JSON and Markdown files.",
            "Supported inputs are YAML, JSON, and Markdown.",
            "This document conforms to the house style guide, which covers JSON and Markdown examples.",
            "Write a summary of the JSON and Markdown files in the repository.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert not any("multiple output formats" in f.description for f in findings), prompt

    @pytest.mark.parametrize("relative_path", _LINTLANG_INSTRUCTION_SURFACES)
    def test_lintlang_own_instruction_prose_has_no_format_conflict(self, relative_path):
        """HARD NEGATIVE: LintLang's own shipped AGENTS/SKILL prose (RESEARCH.md section 5)."""
        findings = detect_h6(AgentConfig(system_prompt=_repo_text(relative_path)))
        assert not any("multiple output formats" in f.description for f in findings), relative_path

    def test_bare_imperative_output_instruction_still_flags(self):
        """POSITIVE CONTROL: the most ordinary way to state an output contract is
        an imperative taking the format as a direct object. The narrowing must
        not cost this true positive."""
        for prompt in (
            "Always output JSON. Also respond in Markdown. Use XML tags when convenient.",
            "Return JSON only. Write the explanation as Markdown.",
            "Emit XML. Respond in Markdown for the human-readable summary.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert any("multiple output formats" in f.description for f in findings), prompt

    def test_bare_imperative_hard_negatives(self):
        """HARD NEGATIVE: a third-person clause about ANOTHER system's output.

        None of these describes the agent's own reply, so there is no competing
        contract to surface. The third person alone is not what makes them
        silent — see the xfail below, where the third person does describe the
        agent's own delivery and the miss is real.
        """
        for prompt in (
            "The upstream service returns JSON. Our docs are written in Markdown.",
            "This tool outputs JSON. Some legacy feeds use XML.",
            "Write JSON to disk under build/. Parse the JSON payload before use.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert not any("multiple output formats" in f.description for f in findings), prompt

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: a two-format delivery of the agent's own reply is missed in the third person",
    )
    def test_descriptive_two_format_delivery_should_be_reported(self):
        """DESIRED BEHAVIOUR, not today's behaviour.

        Both prompts describe two delivery formats for the AGENT'S OWN reply,
        which is the competing contract the rule exists to surface, but they
        describe it in the third person instead of instructing it, so the
        narrowed rule misses them. That is the line: a third-person clause
        about another system's output is a correct hard negative above; a
        third-person clause about the agent's own output is this miss. The
        changelog states it as a known limitation. The day the rule reports
        them, this test passes, strict xfail turns that into a suite failure,
        and the marker and the changelog note both come off.
        """
        for prompt in (
            "The agent's reply is delivered as JSON to the API and as Markdown to the UI.",
            "Responses are serialized to JSON. The changelog entry is Markdown.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert any("multiple output formats" in f.description for f in findings), prompt

    def test_no_format_spec(self):
        config = AgentConfig(system_prompt="You are an assistant. " * 20)
        findings = detect_h6(config)
        assert any("no explicit output format" in f.description for f in findings)

    def test_stated_output_format_is_not_reported_as_missing(self):
        """HARD NEGATIVE: the LOW must not contradict the document it reports on.
        Both spellings below do specify a format."""
        for prompt in (
            "You are a release agent. " * 12 + "Return Markdown only. Use ## for the release heading.",
            "You are a planning agent. " * 12 + "Return a plan as Markdown.",
            "You are an API agent. " * 12 + "Always output JSON.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert not any("no explicit output format" in f.description for f in findings), prompt

    def test_output_format_recognizer_is_not_widened_to_bare_mentions(self):
        """HARD NEGATIVE: the LOW still fires when a long prompt only names a
        format in passing, so the recognizer has not become mention-counting."""
        prompt = "You are an assistant. " * 20 + "The repository stores its notes in Markdown files."
        findings = detect_h6(AgentConfig(system_prompt=prompt))
        assert any("no explicit output format" in f.description for f in findings)

    @pytest.mark.xfail(
        strict=True,
        reason="documented limitation: a stated output format is missed when an unlisted word or verb carries it",
    )
    def test_words_between_verb_and_format_should_not_report_a_missing_format(self):
        """DESIRED BEHAVIOUR, not today's behaviour.

        The recognizer takes a listed verb followed by the format name,
        optionally through `in`/`as`/`with`/`using` and a short list of
        adjectives. Each prompt below does state an output format and is still
        reported as stating none: an unlisted word sits between the connector
        and the format name (`exactly one`, `the ... shape`), or the verb
        itself is not listed (`produce`). The LOW should not contradict the
        document it reports on. Any widening must keep the mere-mention hard
        negative above silent, which is why this is a decision and not a
        one-line change.
        """
        for prompt in (
            "You are a release agent. " * 12 + "Output exactly one Markdown document.",
            "You are a release agent. " * 12 + "Produce a single JSON object.",
            "You are a release agent. " * 12 + "Reply using the YAML shape below.",
        ):
            findings = detect_h6(AgentConfig(system_prompt=prompt))
            assert not any("no explicit output format" in f.description for f in findings), prompt

    def test_long_prompt_no_version(self):
        config = AgentConfig(system_prompt="Some instructions. " * 40)
        findings = detect_h6(config)
        assert any("no version marker" in f.description for f in findings)

    def test_versioned_prompt_ok(self):
        config = AgentConfig(system_prompt="# Assistant v2.1\n\nYou are an assistant. " * 40)
        findings = detect_h6(config)
        version_findings = [f for f in findings if "version" in f.description.lower()]
        assert len(version_findings) == 0


# ── H7: Role Confusion ────────────────────────────────────────────


class TestH7:
    def test_no_messages_returns_empty(self, empty_config):
        assert detect_h7(empty_config) == []

    def test_multiple_system_messages(self, bad_messages_config):
        findings = detect_h7(bad_messages_config)
        assert any("system messages" in f.description.lower() and f.severity == Severity.HIGH for f in findings)

    def test_consecutive_same_role(self, bad_messages_config):
        findings = detect_h7(bad_messages_config)
        assert any("consecutive" in f.description.lower() for f in findings)

    def test_missing_role(self, bad_messages_config):
        findings = detect_h7(bad_messages_config)
        assert any("no 'role' field" in f.description for f in findings)

    def test_system_not_at_start(self, bad_messages_config):
        findings = detect_h7(bad_messages_config)
        assert any("not at the start" in f.description for f in findings)

    def test_tool_result_without_tool_use(self, bad_messages_config):
        findings = detect_h7(bad_messages_config)
        assert any("tool result" in f.description.lower() and "without" in f.description.lower() for f in findings)

    def test_clean_messages(self):
        config = AgentConfig(
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "Thanks"},
                {"role": "assistant", "content": "You're welcome!"},
            ]
        )
        findings = detect_h7(config)
        assert len(findings) == 0


# ── Baseline identity for the findings that survive the narrowing ──


class TestNarrowedDetectorBaselineIdentity:
    """Pin code, severity, location, description, and evidence for surviving positives.

    docs/baselines.md:86-100 makes those five fields a baseline entry's identity, so a
    surviving positive whose message changed would reopen every baseline that recorded
    it. Removing a false positive is compatible; rewording a true one is not. These are
    the H4/H5/H6 findings that the RESEARCH.md section 5 narrowing must leave untouched.
    """

    @staticmethod
    def _identities(prompt: str) -> set[tuple[str, str, str, str, str]]:
        config = AgentConfig(system_prompt=prompt)
        findings = detect_h4(config) + detect_h5(config) + detect_h6(config)
        return {(f.code, f.severity.name, f.location, f.description, f.evidence) for f in findings}

    def test_bad_system_prompt_sample_identities_are_unchanged(self):
        identities = self._identities((SAMPLES_DIR / "bad_system_prompt.txt").read_text(encoding="utf-8"))
        expected = {
            (
                "H4",
                "MEDIUM",
                "system_prompt",
                "Long system prompt with no context boundary markers.",
                "",
            ),
            (
                "H5",
                "MEDIUM",
                "system_prompt",
                "System prompt has ~25 instructions with no explicit priority ordering.",
                "",
            ),
            (
                "H6",
                "MEDIUM",
                "system_prompt",
                "System prompt references multiple output formats (JSON, Markdown, XML) "
                "— model may produce hybrid output.",
                "",
            ),
        }
        assert expected <= identities

    def test_removed_findings_are_gone_everywhere_they_were_false(self):
        """The narrowing removes findings; it never reworks a surviving one."""
        for relative_path in _LINTLANG_INSTRUCTION_SURFACES:
            identities = self._identities(_repo_text(relative_path))
            descriptions = {description for _, _, _, description, _ in identities}
            assert "Long system prompt with no context boundary markers." not in descriptions, relative_path
            assert not any("multiple output formats" in d for d in descriptions), relative_path
            assert not any("could be reframed positively" in d for d in descriptions), relative_path
