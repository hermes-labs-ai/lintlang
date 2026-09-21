"""Precision boundaries for concise, self-explanatory real manifest shapes."""
import json

import pytest

from lintlang.parsers import parse_json
from lintlang.patterns import AgentConfig, ToolDef, detect_h1, detect_h3
from lintlang.scanner import scan_config


@pytest.mark.parametrize("description", ["Execute Python code", "List all VLANs", "Create a new user"])
def test_concrete_short_description_is_not_ambiguous(description):
    assert not any(f.code == "H1.2" for f in detect_h1(AgentConfig(tools=[ToolDef("operation", description)])))


def test_generic_short_description_still_needs_detail():
    assert any(f.code == "H1.2" for f in detect_h1(AgentConfig(tools=[ToolDef("operation", "Get data")])))


def test_generic_and_preset_operations_are_distinguishable():
    tools = [
        ToolDef("create_rule", "Create a firewall rule", {"properties": {"port": {"type": "integer"}}}),
        ToolDef("create_rule_preset", "Create a firewall rule from a preset", {
            "properties": {"preset": {"type": "string", "enum": ["web", "ssh"]}},
        }),
    ]
    assert not any(f.code == "H1.6" for f in detect_h1(AgentConfig(tools=tools)))


def test_distinct_input_schemas_disambiguate_one_sided_overlap():
    tools = [
        ToolDef("create_user", "Create a user record", {"properties": {"email": {"type": "string"}}}),
        ToolDef("add_user", "Create a user account", {"properties": {"invitation": {"type": "string"}}}),
    ]
    assert not any(f.code == "H1.6" for f in detect_h1(AgentConfig(tools=tools)))


def test_schema_and_context_explain_parameters_but_not_arbitrary_role():
    tool = ToolDef("write_file", "Write text content to a file on disk", {"properties": {
        "path": {"type": "string"}, "content": {"type": "string"},
        "email": {"type": "string", "format": "email"},
        "mode": {"type": "string", "enum": ["append", "replace"]},
        "include_disabled": {"type": "boolean"}, "role": {"type": "string"},
    }})
    findings = detect_h3(AgentConfig(tools=[tool]))
    assert [f.location for f in findings] == ["tool:write_file.parameters.role"]


def test_server_instructions_are_inspected_without_host_prompt_requirements():
    data = {
        "server": {"command": "example"},
        "tools": [{"name": "read_file", "description": "Read a UTF-8 file from disk", "inputSchema": {
            "type": "object", "properties": {"path": {"type": "string"}},
        }}],
        "instructions": "The service reads files. " * 12,
    }
    result = scan_config(parse_json(json.dumps(data)))
    assert result.inspected["system_prompt"] == 1
    assert result.structural_findings == []
    data["instructions"] = "Keep trying until it works."
    assert any(f.pattern_id == "H2" for f in scan_config(parse_json(json.dumps(data))).structural_findings)


def test_localization_keys_are_not_counted_as_inspected_descriptions():
    result = scan_config(parse_json(json.dumps({"tools": [{
        "name": "search", "modelDescription": "%tool.search.description%",
        "inputSchema": {"properties": {"query": {"type": "string", "description": "%tool.query%"}}},
    }]})))
    assert result.inspected["tools"] == 1
    assert result.inspected["tools_described"] == 0
    assert len(result.notes) == 2
    assert all("Localized description not inspected" in note for note in result.notes)
    assert result.structural_findings == []


def test_skill_catalog_skip_does_not_hide_tool_definitions():
    from lintlang.scanner import scan_source

    catalog = [{"name": "format-code", "description": "Format source code", "repo": "org/repo", "skillPath": "SKILL.md"}]
    result = scan_source(json.dumps(catalog), "catalog.json", explicit=True)
    assert result.input_error is None
    assert "skill source catalog" in result.skipped
    catalog.append({"name": "broken", "inputSchema": {"type": "object"}})
    result = scan_source(json.dumps(catalog), "catalog.json", explicit=True)
    assert result.inspected["tools"] == 1
    assert any(f.code == "H1.1" for f in result.structural_findings)


@pytest.mark.parametrize("description", ["Count", "Validate", "Get all", "Delete all", "List everything", "Read anything"])
def test_action_without_domain_object_remains_ambiguous(description):
    assert any(f.code == "H1.2" for f in detect_h1(AgentConfig(tools=[ToolDef("operation", description)])))


@pytest.mark.parametrize("value", [False, 0, ""])
def test_falsy_constant_explains_parameter(value):
    tool = ToolDef("operation", "Perform an operation", {"properties": {"mode": {"const": value}}})
    assert detect_h3(AgentConfig(tools=[tool])) == []
