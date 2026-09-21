"""Tool discovery by shape, and the never-silently-clean contract."""

from __future__ import annotations

import json

import pytest

from lintlang.cli import main
from lintlang.ingestion import discover_tools
from lintlang.parsers import parse_json, parse_yaml
from lintlang.report import compute_verdict
from lintlang.scanner import scan_file

SCHEMA = {"type": "object", "properties": {"q": {"type": "string", "description": "Query text"}}}


def names(data) -> list[str]:
    return [t.name for t in discover_tools(data).tools]


class TestShapes:
    def test_root_array_of_openai_function_wrappers(self):
        data = [{"type": "function", "function": {"name": "a", "description": "d", "parameters": SCHEMA}}]
        assert names(data) == ["a"]
        assert [t.name for t in parse_json(json.dumps(data)).tools] == ["a"]

    def test_root_array_of_mcp_tools(self):
        assert names([{"name": "a", "description": "d", "inputSchema": SCHEMA}]) == ["a"]

    def test_root_array_of_named_described_objects_is_not_claimed(self):
        found = discover_tools([{"name": "server", "description": "A server", "repository": "x"}])
        assert found.tools == []
        assert found.unclaimed == ["[0]"]

    @pytest.mark.parametrize(
        "key", ["inputSchema", "input_schema", "parameters", "parametersJsonSchema", "parameters_json_schema"]
    )
    def test_every_schema_key_spelling_is_read(self, key):
        tool = discover_tools({"tools": [{"name": "a", "description": "d", key: SCHEMA}]}).tools[0]
        assert tool.has_schema and tool.parameters == SCHEMA

    def test_vendor_key_at_depth(self):
        data = {"contributes": {"languageModelTools": [{"name": "a", "modelDescription": "Model text", "inputSchema": SCHEMA}]}}
        tool = discover_tools(data).tools[0]
        assert tool.path == "contributes.languageModelTools[0]"
        assert tool.description == "Model text"

    def test_mcp_servers_tools_carry_their_server(self):
        data = {"mcpServers": {"git": {"command": "uvx", "tools": [{"name": "status", "description": "d", "inputSchema": {}}]}}}
        tool = discover_tools(data).tools[0]
        assert (tool.owner, tool.name) == ("git", "status")

    def test_launch_only_mcp_servers_have_no_tools(self):
        assert names({"mcpServers": {"x": {"command": "npx", "args": ["-y", "pkg"]}}}) == []

    def test_name_keyed_tool_map(self):
        data = {"tools": {"get_weather": {"description": "Weather", "inputSchema": SCHEMA}, "ping": {"description": "Ping"}}}
        assert names(data) == ["get_weather", "ping"]

    def test_unknown_key_map_needs_homogeneous_schemas(self):
        assert names({"fns": {"a": {"parameters": {"type": "object"}}, "b": {"input_schema": {}}}}) == ["a", "b"]
        assert names({"handlers": {"a": {"parameters": {"type": "object"}}, "b": {"timeout": 5}}}) == []

    def test_gemini_function_declarations(self):
        data = {"tools": [{"functionDeclarations": [{"name": "a", "description": "d", "parameters": SCHEMA}]}]}
        assert names(data) == ["a"]

    def test_tools_result_envelope(self):
        assert names({"result": {"tools": [{"name": "a", "description": "d"}]}}) == ["a"]

    def test_yaml_root_list(self):
        config = parse_yaml("- name: a\n  description: d\n  inputSchema: {type: object}\n")
        assert [t.name for t in config.tools] == ["a"]

    def test_same_tool_listed_twice_is_read_once(self):
        data = {
            "tools": [{"name": "a", "description": "d"}],
            "_meta": {"static": {"tools": [{"name": "a", "description": "d", "inputSchema": SCHEMA}]}},
        }
        tools = discover_tools(data).tools
        assert len(tools) == 1 and tools[0].has_schema


class TestHardNegatives:
    def test_pipeline_parameters_are_not_a_schema(self):
        assert names({"steps": [{"name": "build", "parameters": {"image": "x"}}]}) == []

    def test_package_json_tools_map_of_versions(self):
        assert names({"name": "pkg", "tools": {"eslint": "^9"}, "dependencies": {"a": "1"}}) == []

    def test_sbom_components(self):
        data = {"bomFormat": "CycloneDX", "components": [{"type": "library", "name": "x", "description": "y"}]}
        assert discover_tools(data).veto == "a software bill of materials"

    def test_json_schema_document(self):
        data = {"$schema": "https://json-schema.org/draft-07/schema", "properties": {"tools": {"type": "array"}}}
        assert discover_tools(data).veto == "a JSON Schema document"

    def test_schema_editor_hint_alone_is_not_a_veto(self):
        assert names({"$schema": "x", "tools": [{"name": "a", "description": "d"}]}) == ["a"]

    def test_sbom_metadata_tools_are_not_agent_tools(self):
        assert names({"metadata": {"tools": [{"vendor": "v", "name": "syft", "version": "1"}]}}) == []

    def test_two_servers_may_share_a_tool_name(self, tmp_path):
        tool = {"name": "search", "description": "Search the issue tracker for matching tickets", "inputSchema": {}}
        other = {"name": "search", "description": "Full-text query over the wiki pages of one space", "inputSchema": {}}
        path = tmp_path / "mcp.json"
        path.write_text(json.dumps({"mcpServers": {"jira": {"tools": [tool]}, "wiki": {"tools": [other]}}}))
        assert [f.code for f in scan_file(path).structural_findings if f.code == "H1.4"] == []


class TestNeverSilentlyClean:
    def test_result_says_what_it_inspected(self, tmp_path):
        path = tmp_path / "tools.json"
        path.write_text(json.dumps([{"name": "a", "description": "", "inputSchema": SCHEMA}]))
        result = scan_file(path)
        assert result.inspected == {"tools": 1, "tools_described": 0, "tools_with_schema": 1}
        assert compute_verdict(result) == "FAIL"

    def test_file_with_nothing_to_inspect_is_skipped_not_pass(self, tmp_path):
        path = tmp_path / "package.json"
        path.write_text('{"name": "pkg", "version": "1.0.0"}')
        result = scan_file(path)
        assert compute_verdict(result) == "SKIPPED"
        assert result.skipped

    def test_python_file_without_prompts_is_skipped(self, tmp_path):
        path = tmp_path / "app.py"
        path.write_text("print('hello')\n")
        assert compute_verdict(scan_file(path)) == "SKIPPED"

    def test_scan_that_inspected_nothing_exits_nonzero(self, tmp_path, capsys):
        path = tmp_path / "sbom.json"
        path.write_text('{"bomFormat": "CycloneDX", "components": []}')
        assert main(["scan", str(path)]) == 1
        assert "software bill of materials" in capsys.readouterr().err
        assert main(["scan", str(path), "--allow-uninspected"]) == 0

    def test_named_file_with_unreadable_tool_like_content_is_an_error(self, tmp_path, capsys):
        path = tmp_path / "registry.json"
        path.write_text(json.dumps([{"name": "a", "description": "does a"}, {"name": "b", "description": "does b"}]))
        good = tmp_path / "AGENTS.md"
        good.write_text("Run the tests before committing.\n")
        assert main(["scan", str(good), str(path), "--format", "json"]) == 1
        rows = {row["file"]: row for row in json.loads(capsys.readouterr().out)}
        assert rows[str(path)]["verdict"] == "ERROR"
        assert "2 named, described objects" in rows[str(path)]["input_error"]
        assert rows[str(good)]["verdict"] == "PASS"

    def test_skipped_file_beside_an_inspected_one_does_not_fail_the_scan(self, tmp_path, capsys):
        good = tmp_path / "AGENTS.md"
        good.write_text("Run the tests before committing.\n")
        other = tmp_path / "package.json"
        other.write_text('{"name": "pkg"}')
        assert main(["scan", str(good), str(other), "--format", "json"]) == 0
        rows = {row["file"]: row for row in json.loads(capsys.readouterr().out)}
        assert rows[str(other)]["verdict"] == "SKIPPED"
        assert rows[str(good)]["inspected"]["instructions"] == 1

    def test_boolean_property_schema_does_not_crash(self, tmp_path):
        path = tmp_path / "tools.json"
        path.write_text(json.dumps({"tools": [{"name": "a", "description": "Reads one record by its identifier", "inputSchema": {"type": "object", "properties": {"x": True}}}]}))
        assert scan_file(path).input_error is None


class TestToolCheckPrecision:
    def _codes(self, tmp_path, tools):
        path = tmp_path / "tools.json"
        path.write_text(json.dumps({"tools": tools}))
        return [f.code for f in scan_file(path).structural_findings]

    def test_precise_verbs_are_not_vague(self, tmp_path):
        tools = [
            {"name": "get_time", "description": "Get the current time in a specific timezone or UTC."},
            {"name": "run_sql", "description": "Execute a read-only SQL query against the analytics replica."},
        ]
        assert "H1.3" not in self._codes(tmp_path, tools)

    def test_vague_verb_still_reported(self, tmp_path):
        assert "H1.3" in self._codes(tmp_path, [{"name": "x", "description": "Handle user data for the application"}])

    def test_domination_needs_a_shared_domain_term(self, tmp_path):
        tools = [
            {"name": "data_entity_info", "description": "Retrieve entity info"},
            {"name": "auth_me", "description": "Get the current user"},
        ]
        assert "H1.6" not in self._codes(tmp_path, tools)

    def test_domination_needs_the_same_verb(self, tmp_path):
        tools = [
            {"name": "git_commit", "description": "Records changes to the repository"},
            {"name": "git_diff_staged", "description": "Shows changes that are staged for commit"},
        ]
        assert "H1.6" not in self._codes(tmp_path, tools)

    def test_real_domination_still_reported(self, tmp_path):
        tools = [
            {"name": "create_firewall_rule", "description": "Create a new firewall rule"},
            {"name": "create_firewall_preset", "description": "Create a firewall rule from a preset"},
        ]
        assert "H1.6" in self._codes(tmp_path, tools)

    def test_scalar_union_is_not_an_undescribed_choice(self, tmp_path):
        schema = {"type": "object", "properties": {"id": {"description": "Row id", "anyOf": [{"type": "string"}, {"type": "number"}]}}}
        path = tmp_path / "t.json"
        path.write_text(json.dumps({"tools": [{"name": "read_row", "description": "Read one row of the orders table by id", "inputSchema": schema}]}))
        assert not [f for f in scan_file(path).structural_findings if "anyOf" in f.description]


def test_document_that_is_one_tool():
    assert names({"name": "create_gist", "description": "Create a new gist", "inputSchema": SCHEMA}) == ["create_gist"]


def test_prompts_under_nested_config_keys_are_read(tmp_path):
    path = tmp_path / "agent.yaml"
    path.write_text(
        "agent:\n  templates:\n    system_template: |-\n      You are a helpful assistant that can interact with a computer.\n"
        "    instance_template: |-\n      If the tests fail, keep trying until they pass, whatever it takes to get there.\n"
    )
    result = scan_file(path)
    assert result.inspected["nested_prompts"] == 2
    assert any(f.pattern_id == "H2" for f in result.structural_findings)


def test_jsonc_and_tagged_yaml_parse(tmp_path):
    jsonc = tmp_path / "t.json"
    jsonc.write_text('{\n // comment\n "tools": [{"name": "a", "description": "Reads one record by identifier", "inputSchema": {},},],\n}\n')
    assert scan_file(jsonc).inspected["tools"] == 1
    tagged = tmp_path / "mkdocs.yml"
    tagged.write_text("a: !!python/name:foo.bar\nb: !Ref x\n")
    assert compute_verdict(scan_file(tagged)) == "SKIPPED"


def test_tool_findings_carry_the_line_of_the_tool(tmp_path):
    path = tmp_path / "tools.json"
    path.write_text(json.dumps({"tools": [
        {"name": "alpha", "description": "Reads one record from the orders table by id", "inputSchema": {}},
        {"name": "beta", "description": "", "inputSchema": {}},
    ]}, indent=2))
    finding = next(f for f in scan_file(path).structural_findings if f.code == "H1.1")
    assert finding.source_region.start_line == 9


def test_python_literal_tool_definitions_are_read(tmp_path):
    path = tmp_path / "server.py"
    path.write_text(
        "tools = [\n    Tool(name='checkout', description='Switches', inputSchema={'type': 'object'}),\n"
        "    Tool(name='log', description='Show the commit log of the repository, newest first', inputSchema=Log.schema()),\n]\n"
    )
    result = scan_file(path)
    assert result.inspected["tools"] == 2
    finding = next(f for f in result.structural_findings if f.code == "H1.2")
    assert finding.source_region.start_line == 2
