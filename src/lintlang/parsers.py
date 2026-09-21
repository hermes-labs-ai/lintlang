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

from .ingestion import discover_tools
from .patterns import AgentConfig, ToolDef


def parse_file(path: str | Path) -> AgentConfig:
    """Parse a file into an AgentConfig based on extension."""
    path = Path(path)
    return parse_source(path.read_text(encoding="utf-8"), path)


def parse_source(text: str, path: str | Path) -> AgentConfig:
    """Parse in-memory source text as if it had been read from ``path``.

    ``path`` is used only for suffix dispatch and source identity; it is never
    opened, so a virtual path (for example a document arriving on standard
    input) selects the same parser and reports the same locations as the real
    file would.
    """
    path = Path(path)

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
    if isinstance(data, list):
        return _normalize({}, source_file, document=data)
    if not isinstance(data, dict):
        return AgentConfig(system_prompt=text, source_file=source_file, raw={}, kind="prompt")
    return _normalize(data, source_file)


def parse_json(text: str, source_file: str = "") -> AgentConfig:
    """Parse JSON agent config."""
    data = json.loads(text)
    if isinstance(data, list):
        return _normalize({}, source_file, document=data)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object or an array")
    return _normalize(data, source_file)


def parse_text(text: str, source_file: str = "") -> AgentConfig:
    """Parse plain text as a system prompt."""
    return AgentConfig(
        system_prompt=text.strip(),
        source_file=source_file,
        raw={"system_prompt": text.strip()},
    )


def _normalize(data: dict, source_file: str, document: object = None) -> AgentConfig:
    """Normalize various config formats to AgentConfig.

    ``document`` is the parsed root when it is not a mapping (a root array of
    tools); ``data`` is then empty and only tool discovery applies.
    """
    config = AgentConfig(raw=data, source_file=source_file)

    # Extract system prompt
    for key in ("system_prompt", "system", "systemPrompt", "instructions", "prompt"):
        if key in data and isinstance(data[key], str):
            config.system_prompt = data[key]
            break

    # Extract tools — by shape, wherever they sit (see ingestion.py)
    _validate_root_tool_names(data)
    found = discover_tools(document if document is not None else data)
    config.not_agent_content = found.veto
    config.unclaimed = found.unclaimed
    config.dropped = found.dropped
    for item in found.tools:
        config.tools.append(
            ToolDef(
                name=item.name,
                description=item.description,
                parameters=item.parameters,
                path=item.path,
                group=item.group,
                owner=item.owner,
                has_schema=item.has_schema,
            )
        )

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


def _validate_root_tool_names(data: dict) -> None:
    """Reject a root tool whose ``name`` is not a string, naming its location."""
    tools_data = data.get("tools", data.get("functions", []))
    if not isinstance(tools_data, list):
        return
    for index, td in enumerate(tools_data):
        if not isinstance(td, dict) or "name" not in td or isinstance(td["name"], str):
            continue
        if td.get("type") == "function" and "function" in td:
            continue
        name = td["name"]
        yaml_type = {
            bool: "boolean",
            int: "integer",
            float: "number",
            type(None): "null",
            list: "array",
            dict: "object",
        }.get(type(name), type(name).__name__)
        raise ValueError(f"tools[{index}].name must be a string, got {yaml_type}")
