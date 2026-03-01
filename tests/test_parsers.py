"""Tests for input parsers."""

import json
from pathlib import Path

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


class TestParseJson:
    def test_openai_function_format(self):
        config = parse_json(json.dumps({
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
        }))
        assert len(config.tools) == 1
        assert config.tools[0].name == "get_weather"

    def test_messages_extraction(self):
        config = parse_json(json.dumps({
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        }))
        assert len(config.messages) == 2
        assert config.system_prompt == "You are helpful."

    def test_anthropic_format(self):
        config = parse_json(json.dumps({
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
        }))
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
