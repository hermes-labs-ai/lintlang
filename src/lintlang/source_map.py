"""Parser-backed source positions for normalized YAML and JSON values.

The data parser remains authoritative for values. A YAML syntax tree supplies
marks only for paths whose shape agrees with those parsed values. Aliases keep
their anchor's mark; duplicate mapping keys keep the last value's mark, just as
the data loader keeps the last value.
"""

from __future__ import annotations

import json
from collections import defaultdict

import yaml

from .models import SourceRegion


class SourceMap:
    def __init__(self, text: str, root: yaml.Node, data: object) -> None:
        self.text = text
        self.nodes: dict[str, yaml.Node] = {}
        self.keys: dict[str, yaml.ScalarNode] = {}
        self._path_parts: dict[str, tuple[str | int, ...]] = {}
        self._ambiguous: set[str] = set()
        self.identity_paths: dict[int, list[str]] = defaultdict(list)
        self._walk(root, data, "", set(), ())

    def _walk(
        self, node: yaml.Node, value: object, path: str,
        ancestors: set[int], parts: tuple[str | int, ...],
    ) -> None:
        if path in self._path_parts and self._path_parts[path] != parts:
            self._ambiguous.add(path)
        else:
            self._path_parts[path] = parts
            self.nodes[path] = node
        if isinstance(value, (dict, list)):
            self.identity_paths[id(value)].append(path)
        if id(node) in ancestors:
            return  # recursive YAML alias
        ancestors = ancestors | {id(node)}
        if isinstance(node, yaml.MappingNode) and isinstance(value, dict):
            for key_node, child_node in node.value:
                if not isinstance(key_node, yaml.ScalarNode):
                    continue
                key = key_node.value
                if key not in value:
                    continue
                child_path = f"{path}.{key}" if path else key
                self.keys[child_path] = key_node
                self._walk(child_node, value[key], child_path, ancestors, (*parts, key))
        elif isinstance(node, yaml.SequenceNode) and isinstance(value, list):
            for index, child_node in enumerate(node.value[: len(value)]):
                self._walk(child_node, value[index], f"{path}[{index}]", ancestors, (*parts, index))

    def region(self, path: str) -> SourceRegion | None:
        if path in self._ambiguous:
            return None
        node = self.nodes.get(path)
        if node is None:
            return None
        start = node.start_mark.line + 1
        # PyYAML end marks are exclusive. At column zero the previous physical
        # line was the last line belonging to this construct.
        end = max(start, node.end_mark.line + (1 if node.end_mark.column else 0))
        return SourceRegion(start, end)

    def key_region(self, path: str) -> SourceRegion | None:
        if path in self._ambiguous:
            return None
        key = self.keys.get(path)
        return SourceRegion(key.start_mark.line + 1, key.start_mark.line + 1) if key else None

    def path_for_value(self, value: object, under: str = "") -> str:
        """Find the exact parsed container within an owning tool or schema."""
        candidates = self.identity_paths.get(id(value), ())
        return next(
            (path for path in candidates if path not in self._ambiguous
             and (path.startswith(f"{under}.") or path == under)),
            "",
        )

    def scalar_region(self, path: str, value: str, offset: int | None = None) -> SourceRegion | None:
        """Locate a scalar, refining literal block offsets to their content line.

        Folded and escaped scalars cannot be mapped by counting decoded newlines:
        their source layout differs. Their full source span remains the honest region.
        """
        if path in self._ambiguous:
            return None
        node = self.nodes.get(path)
        if not isinstance(node, yaml.ScalarNode):
            return None
        if node.value != value:
            # PyYAML leaves a JSON UTF-16 surrogate pair as two code points,
            # while json.loads combines it. Verify the exact source token with
            # JSON's own decoder before using its node mark.
            raw = self.text[node.start_mark.index : node.end_mark.index]
            try:
                if json.loads(raw) != value:
                    return None
            except (ValueError, UnicodeError):
                return None
        if offset is None:
            return self.region(path)
        if 0 <= offset < len(value) and node.style == "|":
            line = node.start_mark.line + 2 + value.count("\n", 0, offset)
            return SourceRegion(line, line)
        # Folded, plain, and quoted multiline YAML can change line breaks in
        # their decoded value. Give their actual source span rather than an
        # invented token line. JSON strings occupy one physical line.
        return self.region(path)
