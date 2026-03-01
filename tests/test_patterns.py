"""Tests for H1-H7 pattern detectors."""

import pytest

from lintlang.patterns import (
    AgentConfig,
    Finding,
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
        config = AgentConfig(tools=[ToolDef(name="handler", description="Handle the user request and process it accordingly")])
        findings = detect_h1(config)
        assert any("vague verb" in f.description for f in findings)

    def test_overlapping_descriptions(self):
        config = AgentConfig(tools=[
            ToolDef(name="get_user", description="Get user data from the database system"),
            ToolDef(name="fetch_user", description="Get user data from the database"),
        ])
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
        config = AgentConfig(tools=[
            ToolDef(name="search", description="Search for users in the database by email"),
            ToolDef(name="search", description="Search for products in the catalog by name"),
        ])
        findings = detect_h1(config)
        assert any("duplicate" in f.description.lower() and f.severity == Severity.CRITICAL for f in findings)

    def test_stopwords_dont_inflate_overlap(self):
        """Common stopwords should not inflate overlap score."""
        config = AgentConfig(tools=[
            ToolDef(name="create_user", description="Create a new user in the system database"),
            ToolDef(name="delete_user", description="Delete an existing user from the system database"),
        ])
        findings = detect_h1(config)
        overlap_findings = [f for f in findings if "overlap" in f.description.lower()]
        assert len(overlap_findings) == 0


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
        config = AgentConfig(tools=[
            ToolDef(name="tool", description="A tool", parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            }),
        ])
        findings = detect_h3(config)
        assert any("no description" in f.description for f in findings)

    def test_generic_param_names(self):
        config = AgentConfig(tools=[
            ToolDef(name="tool", description="A tool", parameters={
                "type": "object",
                "properties": {"data": {"type": "string"}},
            }),
        ])
        findings = detect_h3(config)
        assert any("generic name" in f.description for f in findings)

    def test_undescribed_anyof_variants(self):
        config = AgentConfig(tools=[
            ToolDef(name="tool", description="A tool", parameters={
                "type": "object",
                "properties": {
                    "input": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "object"},
                        ],
                    },
                },
            }),
        ])
        findings = detect_h3(config)
        assert any("anyOf" in f.description and "undescribed" in f.description for f in findings)

    def test_nested_object_properties_checked(self):
        """Nested object properties should also be checked for missing descriptions."""
        config = AgentConfig(tools=[
            ToolDef(name="tool", description="A tool", parameters={
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
            }),
        ])
        findings = detect_h3(config)
        assert any("data" in f.description and "generic" in f.description for f in findings)
        assert any("data" in f.description and "no description" in f.description for f in findings)

    def test_phantom_required_field(self):
        """Required field not in properties should be flagged."""
        config = AgentConfig(tools=[
            ToolDef(name="tool", description="A tool", parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "User name"}},
                "required": ["name", "ghost_field"],
            }),
        ])
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
        config = AgentConfig(system_prompt="Use all conversation history to maintain context and provide better answers.")
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
        assert any("boundary marker" in f.description.lower() or "no task boundary" in f.description.lower() for f in findings)

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
        config = AgentConfig(messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Thanks"},
            {"role": "assistant", "content": "You're welcome!"},
        ])
        findings = detect_h7(config)
        assert len(findings) == 0
