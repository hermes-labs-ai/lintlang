"""Tests for input parsers."""

import json
from pathlib import Path

import pytest

from lintlang.parsers import parse_file, parse_json, parse_text, parse_yaml

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class TestParseYaml:
    def test_parse_tools(self):
        config = parse_yaml("""
tools:
  - name: search
    description: "Search for documents"
    parameters:
      type: object
      properties:
        query:
          type: string
          description: "Search query"
      required: [query]
""")
        assert len(config.tools) == 1
        assert config.tools[0].name == "search"
        assert config.tools[0].description == "Search for documents"

    def test_parse_system_prompt(self):
        config = parse_yaml("""
system_prompt: "You are a helpful assistant."
""")
        assert config.system_prompt == "You are a helpful assistant."

    def test_parse_plain_string(self):
        config = parse_yaml("just a string")
        assert config.system_prompt == "just a string"

    def test_rejects_non_string_tool_name(self):
        with pytest.raises(
            ValueError,
            match=r"tools\[0\]\.name must be a string, got boolean",
        ):
            parse_yaml("""
tools:
  - name: false
    description: "Look up status"
    parameters:
      type: object
""")

    def test_non_string_tool_name_under_functions_key_names_that_key(self):
        with pytest.raises(
            ValueError,
            match=r"functions\[1\]\.name must be a string, got integer",
        ):
            parse_yaml("""
functions:
  - name: lookup
    description: "Look up status"
  - name: 42
    description: "Look up status"
""")

    @pytest.mark.parametrize(
        ("raw_name", "yaml_type"),
        [
            ("2024-01-01", "timestamp"),
            ("2024-01-01T10:00:00", "timestamp"),
            ("!!binary aGk=", "binary"),
        ],
    )
    def test_non_string_tool_name_reports_yaml_type(self, raw_name, yaml_type):
        with pytest.raises(
            ValueError,
            match=rf"tools\[0\]\.name must be a string, got {yaml_type}$",
        ):
            parse_yaml(f"""
tools:
  - name: {raw_name}
    description: "Look up status"
""")


class TestParseJson:
    def test_openai_function_format(self):
        config = parse_json(
            json.dumps(
                {
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "description": "Get current weather",
                                "parameters": {"type": "object", "properties": {}},
                            },
                        }
                    ],
                }
            )
        )
        assert len(config.tools) == 1
        assert config.tools[0].name == "get_weather"

    def test_messages_extraction(self):
        config = parse_json(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "You are helpful."},
                        {"role": "user", "content": "Hello"},
                    ],
                }
            )
        )
        assert len(config.messages) == 2
        assert config.system_prompt == "You are helpful."

    def test_anthropic_format(self):
        config = parse_json(
            json.dumps(
                {
                    "system": "You are a coding assistant.",
                    "tools": [
                        {
                            "name": "run_code",
                            "description": "Execute Python code in a sandbox",
                            "input_schema": {
                                "type": "object",
                                "properties": {"code": {"type": "string"}},
                            },
                        }
                    ],
                }
            )
        )
        assert config.system_prompt == "You are a coding assistant."
        assert len(config.tools) == 1
        assert config.tools[0].name == "run_code"


class TestParseText:
    def test_parse_plain_text(self):
        config = parse_text("You are a helpful assistant. Be concise.")
        assert config.system_prompt == "You are a helpful assistant. Be concise."
        assert len(config.tools) == 0


class TestParseFile:
    def test_yaml_extension(self):
        config = parse_file(SAMPLES_DIR / "clean_config.yaml")
        assert len(config.tools) == 2
        assert "weather" in config.system_prompt.lower()

    def test_json_extension(self):
        config = parse_file(SAMPLES_DIR / "bad_agent_config.json")
        assert len(config.tools) == 2
        assert len(config.messages) == 10

    def test_text_extension(self):
        config = parse_file(SAMPLES_DIR / "bad_system_prompt.txt")
        assert "helpful AI assistant" in config.system_prompt

    def test_utf16_with_bom_rejected_with_actionable_error(self, tmp_path):
        utf16_le = tmp_path / "prompt_le.txt"
        utf16_le.write_bytes(b"\xff\xfe" + "You are a helpful assistant.\n".encode("utf-16-le"))

        with pytest.raises(UnicodeDecodeError) as exc_info:
            parse_file(utf16_le)

        err_msg = str(exc_info.value)
        assert "LintLang reads UTF-8" in err_msg
        assert "appears to be UTF-16 encoded" in err_msg
        assert "save or convert the file as UTF-8" in err_msg

        # Also test UTF-16 BE BOM
        utf16_be = tmp_path / "prompt_be.txt"
        utf16_be.write_bytes(b"\xfe\xff" + "You are a helpful assistant.\n".encode("utf-16-be"))

        with pytest.raises(UnicodeDecodeError) as exc_info_be:
            parse_file(utf16_be)

        err_msg_be = str(exc_info_be.value)
        assert "LintLang reads UTF-8" in err_msg_be
        assert "appears to be UTF-16 encoded" in err_msg_be

    def test_arbitrary_non_utf8_bytes_rejected_with_clear_error(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_bytes(b"\x80\x81\x82\xff\xfe_not_bom")

        with pytest.raises(UnicodeDecodeError) as exc_info:
            parse_file(bad_file)

        err_msg = str(exc_info.value)
        assert "File is not valid UTF-8" in err_msg
        assert "LintLang requires UTF-8 encoding" in err_msg
