"""Conservative rewrites for the first instruction under an explicit heading."""

from __future__ import annotations

import difflib
import os
import re
import stat
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from .preflight.scope import analyze_scope

_VERBOSITY_NEGATIVE = re.compile(r"Don't be verbose(?P<period>\.)?|Don’t be verbose(?P<curly_period>\.)?")
_SUPPORTED_SUFFIXES = {".md", ".txt", ".prompt"}


def _html_comment_ranges(text: str) -> list[tuple[int, int]]:
    """Return comment spans, treating an unclosed comment as lasting to EOF."""
    ranges: list[tuple[int, int]] = []
    cursor = 0
    while (start := text.find("<!--", cursor)) >= 0:
        close = text.find("-->", start + 4)
        end = len(text) if close < 0 else close + 3
        ranges.append((start, end))
        cursor = end
        if close < 0:
            break
    return ranges


def _has_explicit_instruction_context(text: str, line_start: int) -> bool:
    """Require the first body line of a top-level ``# Instructions`` section."""
    prefix = text[:line_start]
    active_headings: list[tuple[int, str, int]] = []
    for match in re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$", prefix):
        level = len(match.group(1))
        title = match.group(2).rstrip("#").strip()
        while active_headings and active_headings[-1][0] >= level:
            active_headings.pop()
        active_headings.append((level, title, match.end()))
    if (
        len(active_headings) != 1
        or active_headings[0][0] != 1
        or active_headings[0][1] != "Instructions"
    ):
        return False
    section_body_start = active_headings[-1][2]
    return not text[section_body_start:line_start].strip()


class AutoFixError(ValueError):
    """The requested automatic rewrite cannot be applied safely."""


@dataclass(frozen=True, slots=True)
class PreparedFix:
    path: Path
    original: bytes
    updated: bytes
    diff: str
    backup_path: Path
    file_mode: int
    device: int
    inode: int
    rewrite_count: int


def prepare_fix(path: str | Path, *, backup: bool = False) -> PreparedFix:
    """Prepare a byte-preserving rewrite without changing the input file."""
    source = Path(path)
    try:
        metadata = source.lstat()
    except OSError as error:
        raise AutoFixError(f"Cannot inspect {source}: {error}") from error

    if stat.S_ISLNK(metadata.st_mode):
        raise AutoFixError("Automatic fixes do not follow symbolic links.")
    if not stat.S_ISREG(metadata.st_mode):
        raise AutoFixError("Automatic fixes require one regular file.")
    if metadata.st_nlink > 1:
        raise AutoFixError("Automatic fixes do not modify hard-linked files.")
    if source.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise AutoFixError("Automatic fixes support only .md, .txt, and .prompt files.")

    try:
        original = source.read_bytes()
        text = original.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise AutoFixError(f"Cannot read UTF-8 input {source}: {error}") from error

    # An incomplete or malformed scope map is not evidence that any phrase is
    # live instruction text, so fail closed for the whole file.
    scope = analyze_scope(text)
    if scope.unavailable_reason is not None:
        raise AutoFixError(f"Cannot establish instruction scope: {scope.unavailable_reason}.")

    lines = text.splitlines(keepends=True)
    comments = _html_comment_ranges(text)
    offset = 0
    changed = False
    rewrite_count = 0
    updated_lines: list[str] = []
    for line in lines:
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        match = _VERBOSITY_NEGATIVE.fullmatch(content)
        in_comment = any(start <= offset < end for start, end in comments)
        if (
            match is not None
            and not in_comment
            and _has_explicit_instruction_context(text, offset)
            and scope.is_direct(offset, offset + len(content))
        ):
            period = "." if match.group("period") or match.group("curly_period") else ""
            updated_lines.append(f"Be concise{period}{newline}")
            changed = True
            rewrite_count += 1
        else:
            updated_lines.append(line)
        offset += len(line)

    updated = "".join(updated_lines).encode("utf-8") if changed else original
    backup_path = source.with_name(f"{source.name}.lintlang.bak")
    if changed and backup and backup_path.exists():
        raise AutoFixError(f"Backup already exists; refusing to overwrite {backup_path}.")

    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            updated.decode("utf-8").splitlines(keepends=True),
            fromfile=str(source),
            tofile=f"{source} (fixed)",
        )
    )
    return PreparedFix(
        source,
        original,
        updated,
        diff,
        backup_path,
        stat.S_IMODE(metadata.st_mode),
        metadata.st_dev,
        metadata.st_ino,
        rewrite_count,
    )


def write_fix(prepared: PreparedFix, *, backup: bool = False) -> None:
    """Persist a prepared rewrite atomically, optionally preserving exact bytes."""
    if prepared.updated == prepared.original:
        return

    def ensure_unchanged() -> None:
        current_metadata = prepared.path.lstat()
        if (
            not stat.S_ISREG(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or current_metadata.st_nlink > 1
            or current_metadata.st_dev != prepared.device
            or current_metadata.st_ino != prepared.inode
            or stat.S_IMODE(current_metadata.st_mode) != prepared.file_mode
            or prepared.path.read_bytes() != prepared.original
        ):
            raise AutoFixError("Input changed after the diff was prepared; refusing to overwrite it.")

    try:
        ensure_unchanged()
    except OSError as error:
        raise AutoFixError(f"Cannot recheck {prepared.path} before writing: {error}") from error

    if backup:
        backup_created = False
        try:
            with prepared.backup_path.open("xb") as backup_file:
                backup_created = True
                backup_file.write(prepared.original)
                backup_file.flush()
                os.fsync(backup_file.fileno())
        except OSError as error:
            if backup_created:
                with suppress(OSError):
                    prepared.backup_path.unlink(missing_ok=True)
            raise AutoFixError(f"Cannot create backup {prepared.backup_path}: {error}") from error

    try:
        ensure_unchanged()
    except OSError as error:
        raise AutoFixError(f"Cannot recheck {prepared.path} before writing: {error}") from error

    temp_path: Path | None = None
    try:
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{prepared.path.name}.lintlang-",
            dir=prepared.path.parent,
        )
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as temp_file:
            temp_file.write(prepared.updated)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.chmod(temp_path, prepared.file_mode)
        ensure_unchanged()
        os.replace(temp_path, prepared.path)
    except OSError as error:
        raise AutoFixError(f"Cannot write fixed file {prepared.path}: {error}") from error
    finally:
        if temp_path is not None:
            with suppress(OSError):
                temp_path.unlink(missing_ok=True)
