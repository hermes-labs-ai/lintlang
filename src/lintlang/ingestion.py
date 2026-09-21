"""Structural tool discovery for parsed JSON / YAML documents.

A tool definition is recognised by its SHAPE, never by the file name and never
by an allowlist of container keys: real manifests keep tools under a root
array, under ``tools`` at any depth, under vendor keys such as
``contributes.languageModelTools``, under ``mcpServers.<server>.tools``, or as a
name-keyed map. A parser that only reads root ``tools`` silently reports such
files as clean, which is the worst thing a linter can do.

Two signatures:

- STRONG: a mapping with a string ``name`` and a schema key (see
  ``SCHEMA_KEYS``), or an OpenAI ``{"type": "function", "function": {...}}`` /
  ``{"type": "custom", "custom": {...}}`` wrapper. Claimed wherever it sits.
- WEAK: a mapping with a string ``name`` and no schema. Claimed only inside a
  container that names tools (``tools``, ``functions``, ...), because a bare
  ``{name, description}`` pair elsewhere is just as likely a package, a server
  or an SBOM component.

Everything that looks tool-like but is not claimed is counted in
``unclaimed`` so the report can say so instead of staying silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Schema-key spellings, in lookup order. ``parameters`` is guarded because CI
# pipeline templates (Argo, Tekton, Azure Pipelines) use the same key for value
# maps and value lists.
SCHEMA_KEYS: tuple[str, ...] = (
    "inputSchema",
    "input_schema",
    "parameters",
    "parametersJsonSchema",
    "parameters_json_schema",
)

# Keys whose value is a container of tools.
_TOOL_CONTAINER_KEYS = frozenset(
    {"tools", "functions", "functionDeclarations", "function_declarations"}
)

# Maps that are never tool containers, whatever their members look like.
_NEVER_CLAIMED_KEYS = frozenset(
    {
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
        "scripts",
        "engines",
        "properties",
        "patternProperties",
        "$defs",
        "definitions",
        "components",
        "packages",
    }
)

# Maps whose KEYS name an owner (an MCP server) for the tools beneath them.
_OWNER_MAP_KEYS = frozenset({"mcpServers", "servers", "mcp_servers"})


@dataclass
class DiscoveredTool:
    """One tool unit found in a document."""

    name: str
    description: str
    parameters: dict
    path: str  # JSON path of the tool object, e.g. "mcpServers.git.tools[0]"
    group: str  # path of the enclosing container; tools are compared within a group
    owner: str = ""  # server / namespace that owns the tool, when one is named
    has_schema: bool = False


@dataclass
class Discovery:
    """Everything tool discovery learned about one document."""

    tools: list[DiscoveredTool] = field(default_factory=list)
    unclaimed: list[str] = field(default_factory=list)  # paths of tool-like objects not inspected
    dropped: list[str] = field(default_factory=list)  # members of a tool container that could not be read
    veto: str = ""  # why the whole document is not an agent file, when it is not


def schema_of(node: dict) -> tuple[str, dict] | None:
    """Return ``(key, schema)`` for the first schema key whose guard holds."""
    for key in SCHEMA_KEYS:
        value = node.get(key)
        if not isinstance(value, dict):
            continue
        if key == "parameters" and value and not any(k in value for k in ("type", "properties", "$schema")):
            continue
        return key, value
    return None


def _wrapper_inner(node: dict) -> dict | None:
    for kind in ("function", "custom"):
        if node.get("type") == kind and isinstance(node.get(kind), dict):
            return node[kind]
    return None


def is_strong(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if _wrapper_inner(node) is not None:
        return True
    return isinstance(node.get("name"), str) and schema_of(node) is not None


def root_veto(data: Any) -> str:
    """Name the well-known non-agent document type, or return ''."""
    if isinstance(data, list) and data and all(
        isinstance(item, dict) and isinstance(item.get("repo"), str)
        and isinstance(item.get("skillPath"), str) and not is_strong(item)
        for item in data
    ):
        return "a skill source catalog (skill bodies are not present)"
    if not isinstance(data, dict):
        return ""
    if "$schema" in data and any(k in data for k in ("properties", "$defs", "definitions")):
        return "a JSON Schema document"
    if "openapi" in data or "swagger" in data:
        return "an OpenAPI document"
    if "lockfileVersion" in data:
        return "a package lockfile"
    if "bomFormat" in data or "spdxVersion" in data or "SPDXID" in data:
        return "a software bill of materials"
    if "predicate" in data and "subject" in data:
        return "an in-toto attestation"
    return ""


# Spellings of the model-facing description, most specific first. VS Code
# `languageModelTools` and OpenAI plugin manifests keep the text a model reads
# under a dedicated key; reading only `description` reports those tools as
# undescribed, which is false.
DESCRIPTION_KEYS: tuple[str, ...] = (
    "modelDescription",
    "model_description",
    "description_for_model",
    "description",
)


def _description_of(*nodes: dict) -> str:
    for node in nodes:
        for key in DESCRIPTION_KEYS:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _make_tool(node: dict, path: str, group: str, owner: str, fallback_name: str = "") -> DiscoveredTool:
    inner = _wrapper_inner(node)
    body = inner if inner is not None else node
    name = body.get("name")
    if not isinstance(name, str) or not name:
        # A flat ``{"type": "function", "name": ...}`` (Responses API) keeps the
        # name beside the wrapper discriminator.
        outer_name = node.get("name")
        name = outer_name if isinstance(outer_name, str) and outer_name else (fallback_name or "unnamed")
    found = schema_of(body) or schema_of(node)
    description = _description_of(body, node)
    return DiscoveredTool(
        name=name,
        description=description,
        parameters=found[1] if found else {},
        path=path,
        group=group,
        owner=owner,
        has_schema=found is not None,
    )


def _qualifies_as_keyed_tool(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if _wrapper_inner(value) is not None or schema_of(value) is not None:
        return True
    description = value.get("description")
    return isinstance(description, str) and bool(description.strip())


class _Walker:
    def __init__(self) -> None:
        self.found = Discovery()
        self._seen: set[int] = set()

    # -- containers -------------------------------------------------------

    def container(self, value: Any, path: str, owner: str, *, at_root: bool) -> None:
        """Read the value of a ``tools``-like key."""
        if isinstance(value, list):
            for index, member in enumerate(value):
                member_path = f"{path}[{index}]"
                if not isinstance(member, dict):
                    continue  # a list of tool NAMES (allowlist) carries no language
                if any(isinstance(member.get(k), list) for k in ("functionDeclarations", "function_declarations")):
                    self.walk(member, member_path, owner)
                    continue
                named = isinstance(member.get("name"), str)
                if is_strong(member) or (named and (at_root or any(k in member for k in DESCRIPTION_KEYS))):
                    self.claim(member, member_path, path, owner)
                    if member.get("type") == "namespace" and "tools" in member:
                        self.container(member["tools"], f"{member_path}.tools", member.get("name", owner), at_root=True)
                elif named:
                    self.found.unclaimed.append(member_path)
                elif "type" in member and len(member) <= 3:
                    continue  # built-in tool reference such as {"type": "web_search"}
                else:
                    self.found.dropped.append(member_path)
        elif isinstance(value, dict):
            qualifying = {k: v for k, v in value.items() if _qualifies_as_keyed_tool(v)}
            if not qualifying:
                self.walk(value, path, owner)
                return
            for key, member in value.items():
                member_path = f"{path}.{key}"
                if key in qualifying:
                    self.claim(member, member_path, path, owner, fallback_name=str(key))
                elif isinstance(member, dict):
                    self.found.dropped.append(member_path)

    def claim(self, node: dict, path: str, group: str, owner: str, fallback_name: str = "") -> None:
        if id(node) in self._seen:
            return
        self._seen.add(id(node))
        self.found.tools.append(_make_tool(node, path, group, owner, fallback_name))

    # -- generic traversal ------------------------------------------------

    def walk(self, node: Any, path: str, owner: str, *, is_root: bool = False) -> None:
        if isinstance(node, list):
            for index, member in enumerate(node):
                member_path = f"{path}[{index}]"
                if is_strong(member):
                    self.claim(member, member_path, path or "<root>", owner)
                elif isinstance(member, dict):
                    if (
                        isinstance(member.get("name"), str)
                        and isinstance(member.get("description"), str)
                        and not any(k in member for k in _TOOL_CONTAINER_KEYS)
                    ):
                        self.found.unclaimed.append(member_path)
                    member_owner = member.get("name") if isinstance(member.get("name"), str) else owner
                    self.walk(member, member_path, member_owner)
                elif isinstance(member, list):
                    self.walk(member, member_path, owner)
            return

        if not isinstance(node, dict):
            return

        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if key in _NEVER_CLAIMED_KEYS:
                continue
            if key in _TOOL_CONTAINER_KEYS:
                self.container(value, child, owner, at_root=is_root or path.endswith("result") or bool(owner))
                continue
            if key in _OWNER_MAP_KEYS and isinstance(value, dict):
                for server, config in value.items():
                    if isinstance(config, dict):
                        self.walk(config, f"{child}.{server}", str(server))
                continue
            if isinstance(value, dict):
                if is_strong(value):
                    self.claim(value, child, path or "<root>", owner, fallback_name=str(key))
                    continue
                members = list(value.values())
                homogeneous = len(members) >= 2 and all(
                    isinstance(m, dict) and (schema_of(m) is not None or _wrapper_inner(m) is not None)
                    for m in members
                )
                if homogeneous:
                    for member_key, member in value.items():
                        self.claim(member, f"{child}.{member_key}", child, owner, fallback_name=str(member_key))
                    continue
                self.walk(value, child, owner)
            elif isinstance(value, list):
                self.walk(value, child, owner)


def discover_tools(data: Any) -> Discovery:
    """Find every tool unit in a parsed JSON / YAML document."""
    veto = root_veto(data)
    if veto:
        return Discovery(veto=veto)
    walker = _Walker()
    if is_strong(data):
        # The whole document is ONE tool (a per-tool snapshot file).
        walker.claim(data, "<root>", "<root>", "")
    else:
        walker.walk(data, "", "", is_root=True)
    found = walker.found
    # A manifest often lists the same tool twice: a short `tools` declaration and
    # a full `tools/list` response. Keep the fuller copy; reporting both doubles
    # every finding and reads the pair as a name collision.
    best: dict[tuple[str, str], DiscoveredTool] = {}
    for tool in found.tools:
        key = (tool.owner, tool.name)
        kept = best.get(key)
        if kept is None or kept.group != tool.group and tool.has_schema and not kept.has_schema:
            best[key] = tool
    found.tools = [
        t for t in found.tools if best[(t.owner, t.name)] is t or best[(t.owner, t.name)].group == t.group
    ]
    return found
