"""One conservative definition of a repository agent-instruction input.

LintLang integrations (CI recipes, the GitHub initializer, pre-commit, editor
hosts) previously each reimplemented "which repository files are agent
instructions". This module owns that single definition so every surface can
agree without copying filename lists.

What is recognized
------------------
Only exact, documented instruction surfaces:

* root-or-nested basenames: ``AGENTS.md``, ``CLAUDE.md``, ``GEMINI.md``,
  ``SKILL.md``, ``agent.yaml``, ``agent.yml``, ``agent.json``
* the two-segment layout ``.github/copilot-instructions.md``
* ``*.instructions.md`` files directly or indirectly under a
  ``.github/instructions`` directory — the spelling the vendor documents for
  that layout, not every Markdown file that happens to live there

Case policy
-----------
Basenames and layout segments are matched **case-sensitively, exactly as the
respective vendors document them**. ``agents.md`` and ``Claude.MD`` are *not*
recognized. Case-insensitive matching would make discovery depend on whether
the host filesystem folds case, which would break determinism between macOS
and Linux CI runs; a project that wants an unusual spelling scanned can always
pass it as an explicit input, which remains canonical.

What is deliberately *not* recognized
-------------------------------------
Arbitrary Markdown, prose documentation, prompts with other names, and any
file that merely has a supported extension. Generic directory scanning
(``scanner.scan_directory``) keeps its separate, broader extension sweep; this
module never changes it.

Known omissions
---------------
Editor and host layouts that are not recognized, deliberately: ``.cursor/rules``,
``.claude/agents``, and ``.windsurfrules``. Each would need its own file-shape
decision (a rules directory is not one instruction document, and an agent
definition is not a prompt file), and adding a surface here widens discovery,
the pre-commit ``files:`` regex, and ``lintlang init`` at once. Pass such a file
as an explicit scan argument, which is always canonical.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from .scanner import NON_PROMPT_DIRS

__all__ = [
    "RECOGNIZED_INSTRUCTION_BASENAMES",
    "RECOGNIZED_INSTRUCTION_RELATIVE_PATHS",
    "RECOGNIZED_INSTRUCTION_DIRECTORIES",
    "RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES",
    "discover_instruction_files",
    "is_recognized_instruction_path",
]

#: Exact file basenames that name an agent instruction surface anywhere in a
#: repository. Case-sensitive (see module docstring).
RECOGNIZED_INSTRUCTION_BASENAMES = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "GEMINI.md",
        "SKILL.md",
        "agent.yaml",
        "agent.yml",
        "agent.json",
    }
)

#: Exact multi-segment layouts, matched against the tail of a path.
RECOGNIZED_INSTRUCTION_RELATIVE_PATHS = frozenset({".github/copilot-instructions.md"})

#: Directory layouts whose contained files are instruction surfaces.
RECOGNIZED_INSTRUCTION_DIRECTORIES = frozenset({".github/instructions"})

#: Filename suffixes accepted inside :data:`RECOGNIZED_INSTRUCTION_DIRECTORIES`.
#: Matched against the whole basename, so a bare ``notes.md`` sitting in that
#: directory is not an instruction file; ``.instructions.md`` is the spelling
#: the layout documents.
RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES = frozenset({".instructions.md"})


def _parts(path: str | os.PathLike[str]) -> tuple[str, ...]:
    """Normalized, separator-independent path segments."""
    return PurePosixPath(Path(path).as_posix()).parts


def is_recognized_instruction_path(path: str | os.PathLike[str]) -> bool:
    """Is ``path`` a documented agent-instruction surface?

    This is a purely lexical decision: the filesystem is never consulted, so
    the same answer holds for changed-file lists, virtual stdin paths, and
    real files. See the module docstring for the exact recognized set and the
    case-sensitivity policy.

    A path that is not in normal form — one ending in a separator, or carrying
    a doubled separator — is rejected rather than normalized. ``pathlib`` would
    silently turn ``AGENTS.md/`` into ``AGENTS.md`` and ``.github//instructions``
    into ``.github/instructions``, which the pre-commit ``files:`` regex, being
    a literal string match, would not; answering the same question two
    different ways depending on the caller is worse than declining the
    malformed spelling.

    Note that this lexical answer does not prune vendored or cache directories.
    :func:`discover_instruction_files` applies ``NON_PROMPT_DIRS`` pruning on
    top of it, and the pre-commit ``files:`` regex applies none, so the three
    surfaces are deliberately ordered from broadest to narrowest.
    """
    raw = os.fspath(path)
    if raw.endswith(("/", "\\")) or "//" in raw.replace("\\", "/"):
        return False

    parts = _parts(path)
    if not parts:
        return False

    name = parts[-1]
    if name in RECOGNIZED_INSTRUCTION_BASENAMES:
        return True

    tail = "/".join(parts[-2:])
    if tail in RECOGNIZED_INSTRUCTION_RELATIVE_PATHS:
        return True

    if any(
        len(name) > len(suffix) and name.endswith(suffix) for suffix in RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES
    ):
        directories = {tuple(entry.split("/")) for entry in RECOGNIZED_INSTRUCTION_DIRECTORIES}
        for directory in directories:
            width = len(directory)
            ancestors = parts[:-1]
            for index in range(len(ancestors) - width + 1):
                if ancestors[index : index + width] == directory:
                    return True

    return False


def discover_instruction_files(
    root: str | os.PathLike[str],
    *,
    skipped_symlinks: list[Path] | None = None,
) -> list[Path]:
    """Return every recognized instruction file under ``root``, sorted.

    Traversal reuses :data:`lintlang.scanner.NON_PROMPT_DIRS` pruning (caches,
    vendored dependencies, ``.git``, build output) and never follows symlinked
    directories or scans symlinked files, so discovery cannot escape the tree
    or report the same document twice — the same rule
    :func:`lintlang.scanner.scan_directory` applies to a directory scan. A
    missing or non-directory ``root`` yields an empty list; callers decide
    whether that is an error.

    Not following a symlink is a coverage gap the caller cannot see in the
    returned list. Pass ``skipped_symlinks`` to collect the recognized
    instruction files that were skipped for that reason, sorted, so the caller
    can say so instead of reporting a silently smaller scan. A symlinked
    *directory* is pruned without inspection and is therefore not collected:
    deciding whether it holds instruction files would mean following it.
    """
    root_path = Path(root)
    if root_path.is_symlink() or not root_path.is_dir():
        return []

    found: list[Path] = []
    skipped: list[Path] = []
    for current, dirnames, filenames in os.walk(root_path, followlinks=False):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name.lower() not in NON_PROMPT_DIRS
            and not name.lower().endswith(".egg-info")
            and not (Path(current) / name).is_symlink()
        )
        for filename in sorted(filenames):
            candidate = Path(current) / filename
            if not is_recognized_instruction_path(candidate):
                continue
            if candidate.is_symlink():
                skipped.append(candidate)
                continue
            found.append(candidate)

    if skipped_symlinks is not None:
        skipped_symlinks.extend(sorted(skipped, key=str))
    return sorted(found, key=str)
