"""Tests for H1-H7 pattern detectors."""

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

    def test_dont_stop_pattern(self):
        config = AgentConfig(
            system_prompt="Don't stop until the analysis is complete.",
            tools=[ToolDef(name="t", description="test tool for doing things")],
        )
        findings = detect_h2(config)
        assert any(f.severity == Severity.CRITICAL for f in findings)

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

    def test_long_prompt_no_boundaries(self):
        config = AgentConfig(system_prompt="x " * 300)  # Long prompt, no boundary markers
        findings = detect_h4(config)
        assert any("no context boundary" in f.description.lower() for f in findings)

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
        config = AgentConfig(system_prompt="Use the microscope to examine the sample carefully. " * 30)
        findings = detect_h4(config)
        assert any("no context boundary" in f.description.lower() for f in findings)


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


# ── H6: Template Format Contract Violation ─────────────────────────


class TestH6:
    def test_no_prompt_returns_empty(self, empty_config):
        assert detect_h6(empty_config) == []

    def test_multiple_formats(self):
        config = AgentConfig(system_prompt="Respond in JSON for data. Use markdown for text. XML for configs.")
        findings = detect_h6(config)
        assert any("multiple output formats" in f.description for f in findings)

    def test_no_format_spec(self):
        config = AgentConfig(system_prompt="You are an assistant. " * 20)
        findings = detect_h6(config)
        assert any("no explicit output format" in f.description for f in findings)

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
