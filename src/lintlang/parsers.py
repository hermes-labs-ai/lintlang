"""Input parsers for agent configs.

Supports:
- YAML (tool definitions, agent configs)
- JSON (OpenAI-style, Anthropic-style)
- Plain text (system prompts)

All parsers normalize to AgentConfig.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .ingestion import DESCRIPTION_KEYS, discover_tools
from .patterns import AgentConfig, SkillMeta, ToolDef, is_localization_reference
from .source_map import SourceMap


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


class _TolerantLoader(yaml.SafeLoader):
    """SafeLoader that reads application tags (`!!python/name:...`, `!Ref`, `!ENV`)
    as plain data instead of failing. Nothing is constructed or executed."""


def _construct_unknown(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


_TolerantLoader.add_multi_constructor("!", _construct_unknown)
_TolerantLoader.add_multi_constructor("tag:yaml.org,2002:python/", _construct_unknown)

_JSONC_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def _strip_jsonc(text: str) -> str:
    without_comments = _JSONC_TOKEN.sub(lambda m: m.group() if m.group().startswith('"') else "", text)
    return re.sub(r",(\s*[}\]])", r"\1", without_comments)


def _mask_jsonc(text: str) -> str:
    """Keep positions stable for syntax marks while preserving parse semantics."""
    without_comments = _JSONC_TOKEN.sub(
        lambda m: m.group() if m.group().startswith('"') else re.sub(r"[^\n]", " ", m.group()), text
    )
    return re.sub(r",(?=\s*[}\]])", " ", without_comments)


def _source_map(text: str, data: object) -> SourceMap | None:
    try:
        root = yaml.compose(text, Loader=_TolerantLoader)
    except yaml.YAMLError:
        return None
    return SourceMap(text, root, data) if root is not None else None


def parse_yaml(text: str, source_file: str = "") -> AgentConfig:
    """Parse YAML agent config."""
    data = yaml.load(text, Loader=_TolerantLoader)  # noqa: S506 - SafeLoader subclass
    locations = _source_map(text, data)
    if isinstance(data, list):
        return _normalize({}, source_file, document=data, source_map=locations)
    if not isinstance(data, dict):
        return AgentConfig(system_prompt=text, source_file=source_file, raw={}, kind="prompt")
    return _normalize(data, source_file, source_map=locations)


def parse_json(text: str, source_file: str = "") -> AgentConfig:
    """Parse JSON agent config."""
    marked_text = text
    try:
        data = json.loads(text)
    except json.JSONDecodeError as strict_error:
        # JSON with comments / trailing commas (.vscode/*.json, tsconfig.json).
        try:
            data = json.loads(_strip_jsonc(text))
            marked_text = _mask_jsonc(text)
        except json.JSONDecodeError:
            raise strict_error from None
    if isinstance(data, list):
        return _normalize({}, source_file, document=data, source_map=_source_map(marked_text, data))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object or an array")
    return _normalize(data, source_file, source_map=_source_map(marked_text, data))


_FRONT_MATTER = re.compile(r"\A(?:\ufeff)?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown", ".mdc"})
_INSTRUCTION_BASENAMES = frozenset({"AGENTS.md", "CLAUDE.md", "GEMINI.md", "SKILL.md"})
_CHAT_PROMPT_HEADING = re.compile(r"(?im)^\s{0,3}#{1,6}\s*(?:(?:system|developer|assistant)\s+)?prompt\b")
_CHAT_ROLE_OPENING = re.compile(
    r"\A(?:\s{0,3}#{1,6}[^\n]*\n+)?\s*(?:you are|act as|your role is)\b",
    re.IGNORECASE,
)


def _is_documented_instruction_path(source_file: str) -> bool:
    """Return whether a Markdown path names a documented instruction surface."""
    path = Path(source_file)
    if path.name in _INSTRUCTION_BASENAMES:
        return True
    parts = path.parts
    if parts[-2:] == (".github", "copilot-instructions.md"):
        return True
    return path.name.endswith(".instructions.md") and any(
        parts[index : index + 2] == (".github", "instructions") for index in range(len(parts) - 1)
    )


def _is_selection_metadata_path(source_file: str) -> bool:
    """Recognize selection definitions, without inheriting a directory's assets."""
    path = Path(source_file)
    if path.name == "SKILL.md":
        return True
    if path.suffix.lower() not in _MARKDOWN_SUFFIXES:
        return False
    parts = path.parts
    if parts[-3:-1] == (".claude", "agents"):
        return True
    if any(parts[index:index + 2] == (".claude", "commands") for index in range(len(parts) - 2)):
        return True
    return path.suffix.lower() == ".mdc" and parts[-3:-1] == (".cursor", "rules")


def _markdown_is_chat_prompt(body: str) -> bool:
    """Recognize explicit chat-prompt evidence without relying on a filename."""
    return bool(_CHAT_PROMPT_HEADING.search(body) or _CHAT_ROLE_OPENING.search(body))


def parse_text(text: str, source_file: str = "") -> AgentConfig:
    """Parse a text file an agent reads.

    Markdown instruction documents (AGENTS.md, CLAUDE.md, a SKILL.md body) are
    distinct from Markdown that explicitly presents itself as a chat prompt.
    Chat-prompt shape checks apply only when the content supplies that evidence.

    YAML front matter carrying ``name`` / ``description`` on a selection
    definition path is the selection-time metadata of a skill or sub-agent. It is read as such and kept out of the
    body, so its keys are neither linted as prose nor silently ignored.
    """
    suffix = Path(source_file).suffix.lower()
    body = text
    skill = None
    offset = 0

    match = _FRONT_MATTER.match(text)
    if match:
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            meta = None
        if isinstance(meta, dict):
            offset = text[: match.end()].count("\n")
            body = text[match.end() :]
            # Selection metadata belongs to an explicit definition path;
            # description/name keys in docs and nested assets are ordinary metadata.
            if _is_selection_metadata_path(source_file) and ("description" in meta or "name" in meta):
                skill = _skill_meta(meta, match.group(1), source_file)

    kind = "prompt"
    if suffix in _MARKDOWN_SUFFIXES:
        kind = "instructions"
        if skill is None and not _is_documented_instruction_path(source_file) and _markdown_is_chat_prompt(body):
            kind = "prompt"

    leading = len(body) - len(body.lstrip())
    offset += body[:leading].count("\n")
    stripped = body.strip()
    return AgentConfig(
        system_prompt=stripped,
        source_file=source_file,
        raw={"system_prompt": stripped},
        kind=kind,
        skill=skill,
        prompt_line_offset=offset,
    )


def _skill_meta(meta: dict, raw_front_matter: str, source_file: str) -> SkillMeta:
    def line_of(key: str) -> int:
        for number, line in enumerate(raw_front_matter.splitlines(), start=2):
            if re.match(rf"{re.escape(key)}\s*:", line):
                return number
        return 1

    name = meta.get("name")
    description = meta.get("description")
    path = Path(source_file)
    return SkillMeta(
        name=name if isinstance(name, str) else "",
        description=description if isinstance(description, str) else "",
        has_name="name" in meta,
        has_description="description" in meta,
        name_line=line_of("name"),
        description_line=line_of("description"),
        dir_name=path.parent.name if path.name == "SKILL.md" else "",
    )


def _set_prompt_parts(config: AgentConfig, parts: list[tuple[str, str]]) -> None:
    position = 0
    segments: list[tuple[int, int, str]] = []
    for index, (path, value) in enumerate(parts):
        if index:
            position += 2  # the two newlines inserted by normalization
        segments.append((position, position + len(value), path))
        position += len(value)
    config.system_prompt = "\n\n".join(value for _, value in parts)
    config.prompt_segments = segments


def _source_child(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _normalize(
    data: dict, source_file: str, document: object = None, source_map: SourceMap | None = None
) -> AgentConfig:
    """Normalize various config formats to AgentConfig.

    ``document`` is the parsed root when it is not a mapping (a root array of
    tools, messages, or prompt-bearing records); ``data`` is then empty.
    """
    config = AgentConfig(raw=data, source_file=source_file)
    config.source_map = source_map
    root_prompt_path = ""

    # Extract system prompt
    for key in ("system_prompt", "system", "systemPrompt", "instructions", "prompt"):
        if key in data and isinstance(data[key], str):
            config.system_prompt = data[key]
            root_prompt_path = key
            # An MCP server's instructions describe its interface; they are
            # not the host agent's complete system prompt or execution budget.
            if key == "instructions" and isinstance(data.get("server"), dict) and "tools" in data:
                config.kind = "server"
            break

    # Prompts kept under nested keys (`agent.templates.system_template`,
    # `agents[].instructions`, `llm.system_prompt`) are prompts too.
    has_root_prompt = bool(config.system_prompt)
    nested = _nested_prompts(data if document is None else document)
    if nested:
        parts = [(root_prompt_path, config.system_prompt)] if config.system_prompt else []
        parts += [(path, text) for path, text in nested if text != config.system_prompt]
        _set_prompt_parts(config, parts)
        config.prompt_paths = [path for path, _ in nested]
        # Several templates joined together are not ONE chat prompt: counting
        # "instructions" or demanding one output contract across them is
        # meaningless. A top-level system prompt keeps its chat-prompt role,
        # even when the same config also contains subordinate templates.
        if not has_root_prompt:
            config.kind = "templates"
    elif config.system_prompt:
        _set_prompt_parts(config, [(root_prompt_path, config.system_prompt)])

    # Extract tools — by shape, wherever they sit (see ingestion.py)
    _validate_root_tool_names(data)
    found = discover_tools(document if document is not None else data)
    config.not_agent_content = found.veto
    config.unclaimed = found.unclaimed
    config.dropped = found.dropped
    for item in found.tools:
        source_path = "" if item.path == "<root>" else item.path
        schema_path = source_map.path_for_value(item.parameters, under=source_path) if source_map else ""
        # Missing descriptions belong to this declaration, while described
        # tools can point to the prose the detector actually inspected.
        tool_region = None
        if source_map:
            for name_path in (
                _source_child(source_path, "function.name"),
                _source_child(source_path, "custom.name"),
                _source_child(source_path, "name"),
            ):
                tool_region = source_map.scalar_region(name_path, item.name)
                if tool_region:
                    break
            if tool_region is None:
                tool_region = source_map.key_region(source_path) or source_map.region(source_path)
        description_region = None
        if source_map and item.description:
            for prefix in (
                _source_child(source_path, "function"),
                _source_child(source_path, "custom"),
                source_path,
            ):
                for key in DESCRIPTION_KEYS:
                    description_region = source_map.scalar_region(_source_child(prefix, key), item.description)
                    if description_region:
                        break
                if description_region:
                    break
        tool = ToolDef(
            name=item.name,
            description=item.description,
            parameters=item.parameters,
            path=item.path,
            group=item.group,
            owner=item.owner,
            has_schema=item.has_schema,
        )
        tool.source_path = source_path
        tool.schema_path = schema_path
        tool.source_region = tool_region
        tool.description_region = description_region
        config.tools.append(tool)

    for item in found.tools:
        if is_localization_reference(item.description):
            config.uninspected_text.append(f"{item.path}.description")
        config.uninspected_text.extend(_localized_descriptions(item.parameters, f"{item.path}.parameters"))

    # Extract messages
    messages_data = _root_message_sequence(document) if document is not None else data.get("messages", [])
    if isinstance(messages_data, list):
        config.messages = messages_data
        config.message_collection_path = "" if document is not None else "messages"
        config.message_paths = [
            f"{config.message_collection_path}[{index}]" for index in range(len(messages_data))
        ]
        # Also extract system prompt from messages if not already found
        if not config.system_prompt:
            for index, msg in enumerate(messages_data):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        _set_prompt_parts(config, [(f"{config.message_paths[index]}.content", content)])
                    break

    # Extract schemas (structured output definitions)
    for key in ("response_format", "output_schema", "schema", "schemas"):
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                config.schemas.append(val)
                config.schema_paths.append(key)
            elif isinstance(val, list):
                for index, member in enumerate(val):
                    if isinstance(member, dict):
                        config.schemas.append(member)
                        config.schema_paths.append(f"{key}[{index}]")

    # Extract constraints
    for key in ("constraints", "config", "settings", "parameters"):
        if key in data and isinstance(data[key], dict):
            config.constraints.update(data[key])

    return config


_MESSAGE_ROLES = frozenset({"system", "developer", "user", "assistant", "tool"})


def _root_message_sequence(document: object) -> list[dict] | None:
    """Return a root array only when every member has message-envelope shape."""
    if not isinstance(document, list) or not document:
        return None
    if not all(
        isinstance(member, dict)
        and member.get("role") in _MESSAGE_ROLES
        and "content" in member
        and isinstance(member["content"], (str, list))
        for member in document
    ):
        return None
    return document


_PROMPT_KEY = re.compile(
    r"^(?:system|system[_-]?(?:prompt|message|template|instructions?)|instructions?|"
    r"[\w-]*prompt(?:[_-]?template)?|(?:instance|task|user|developer)[_-]template|persona|preamble|backstory|goal)$",
    re.IGNORECASE,
)
_PROMPT_MIN_CHARS = 40


def _nested_prompts(data: object, path: str = "", depth: int = 0) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if depth > 8:
        return found
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{path}.{key}" if path else str(key)
            if isinstance(value, str):
                if depth > 0 and _PROMPT_KEY.match(str(key)) and len(value.strip()) >= _PROMPT_MIN_CHARS:
                    found.append((child, value))
            elif str(key) not in ("properties", "inputSchema", "input_schema", "parameters", "messages"):
                found.extend(_nested_prompts(value, child, depth + 1))
    elif isinstance(data, list):
        for index, member in enumerate(data):
            found.extend(_nested_prompts(member, f"{path}[{index}]", depth + 1))
    return found


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


def _localized_descriptions(value: object, path: str) -> list[str]:
    """List unresolved schema-description keys without fetching sibling files."""
    paths: list[str] = []
    if isinstance(value, dict):
        for key, member in value.items():
            child = f"{path}.{key}"
            if key == "description" and isinstance(member, str) and is_localization_reference(member):
                paths.append(child)
            elif isinstance(member, (dict, list)):
                paths.extend(_localized_descriptions(member, child))
    elif isinstance(value, list):
        for index, member in enumerate(value):
            paths.extend(_localized_descriptions(member, f"{path}[{index}]"))
    return paths
