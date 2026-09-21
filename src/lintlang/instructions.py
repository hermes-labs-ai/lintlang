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
* Markdown files directly or indirectly under a ``.github/instructions``
  directory

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

#: File suffixes accepted inside :data:`RECOGNIZED_INSTRUCTION_DIRECTORIES`.
RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES = frozenset({".md"})


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

    if Path(name).suffix in RECOGNIZED_INSTRUCTION_DIRECTORY_SUFFIXES:
        directories = {tuple(entry.split("/")) for entry in RECOGNIZED_INSTRUCTION_DIRECTORIES}
        for directory in directories:
            width = len(directory)
            ancestors = parts[:-1]
            for index in range(len(ancestors) - width + 1):
                if ancestors[index : index + width] == directory:
                    return True

    return False


def discover_instruction_files(root: str | os.PathLike[str]) -> list[Path]:
    """Return every recognized instruction file under ``root``, sorted.

    Traversal reuses :data:`lintlang.scanner.NON_PROMPT_DIRS` pruning (caches,
    vendored dependencies, ``.git``, build output) and never follows symlinked
    directories or scans symlinked files, so discovery cannot escape the tree
    or report the same document twice. A missing or non-directory ``root``
    yields an empty list; callers decide whether that is an error.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return []

    found: list[Path] = []
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
            if candidate.is_symlink():
                continue
            if is_recognized_instruction_path(candidate):
                found.append(candidate)

    return sorted(found, key=str)
