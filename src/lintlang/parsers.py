"""Input parsers for agent configs.

Supports:
- YAML (tool definitions, agent configs)
- JSON (OpenAI-style, Anthropic-style)
- Plain text (system prompts)

All parsers normalize to AgentConfig.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .patterns import AgentConfig, ToolDef


def parse_file(path: str | Path) -> AgentConfig:
    """Parse a file into an AgentConfig based on extension."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        return parse_yaml(text, source_file=str(path))
    elif path.suffix == ".json":
        return parse_json(text, source_file=str(path))
    elif path.suffix in (".txt", ".md", ".prompt"):
        return parse_text(text, source_file=str(path))
    else:
        # Try JSON, then YAML, then plain text
        try:
            return parse_json(text, source_file=str(path))
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            return parse_yaml(text, source_file=str(path))
        except yaml.YAMLError:
            pass
        return parse_text(text, source_file=str(path))


def parse_yaml(text: str, source_file: str = "") -> AgentConfig:
    """Parse YAML agent config."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return AgentConfig(system_prompt=text, source_file=source_file, raw={})
    return _normalize(data, source_file)


def parse_json(text: str, source_file: str = "") -> AgentConfig:
    """Parse JSON agent config."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return _normalize(data, source_file)


def parse_text(text: str, source_file: str = "") -> AgentConfig:
    """Parse plain text as a system prompt."""
    return AgentConfig(
        system_prompt=text.strip(),
        source_file=source_file,
        raw={"system_prompt": text.strip()},
    )


def _normalize(data: dict, source_file: str) -> AgentConfig:
    """Normalize various config formats to AgentConfig."""
    config = AgentConfig(raw=data, source_file=source_file)

    # Extract system prompt
    for key in ("system_prompt", "system", "systemPrompt", "instructions", "prompt"):
        if key in data and isinstance(data[key], str):
            config.system_prompt = data[key]
            break

    # Extract tools
    tools_data = data.get("tools", data.get("functions", []))
    if isinstance(tools_data, list):
        for index, td in enumerate(tools_data):
            if isinstance(td, dict):
                tool = _parse_tool(td, index=index)
                if tool:
                    config.tools.append(tool)

    # Extract messages
    messages_data = data.get("messages", [])
    if isinstance(messages_data, list):
        config.messages = messages_data
        # Also extract system prompt from messages if not already found
        if not config.system_prompt:
            for msg in messages_data:
                if isinstance(msg, dict) and msg.get("role") == "system":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        config.system_prompt = content
                    break

    # Extract schemas (structured output definitions)
    for key in ("response_format", "output_schema", "schema", "schemas"):
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                config.schemas.append(val)
            elif isinstance(val, list):
                config.schemas.extend(v for v in val if isinstance(v, dict))

    # Extract constraints
    for key in ("constraints", "config", "settings", "parameters"):
        if key in data and isinstance(data[key], dict):
            config.constraints.update(data[key])

    return config


def _parse_tool(data: dict, index: int | None = None) -> ToolDef | None:
    """Parse a tool definition from various formats."""
    # OpenAI function calling format
    if data.get("type") == "function" and "function" in data:
        func = data["function"]
        return ToolDef(
            name=func.get("name", "unnamed"),
            description=func.get("description", ""),
            parameters=func.get("parameters", {}),
        )

    # Direct format (name + description at top level)
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str):
            location = f"tools[{index}].name" if index is not None else "tools.name"
            yaml_type = {
                bool: "boolean",
                int: "integer",
                float: "number",
                type(None): "null",
                list: "array",
                dict: "object",
            }.get(type(name), type(name).__name__)
            raise ValueError(f"{location} must be a string, got {yaml_type}")
        return ToolDef(
            name=name,
            description=data.get("description", ""),
            parameters=data.get("parameters", data.get("input_schema", {})),
        )

    return None
