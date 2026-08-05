import re
import shutil
import sys
import tarfile
from pathlib import Path

from hatchling.build import build_sdist

# A published artifact must not describe the machine it was built on. Absolute
# home-directory paths and the names of unrelated private repositories mean
# nothing to someone who downloaded a tarball, and they leak more than they
# help.
#
# This guards the class rather than a filename. The first version of this fix
# excluded one document by name; a second document carrying the same paths was
# already shipping beside it, and the exclusion did not catch it because it was
# written against the example rather than the rule.
_LOCAL_PATH = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")
_PRIVATE_REFERENCES = ("ai-infra", "Documents/HAL", "Documents/Codex")


def test_common_virtualenv_directories_are_excluded_from_source_builds(
    tmp_path: Path, monkeypatch,
) -> None:
    repo_root = Path(__file__).parents[1]
    source = tmp_path / "source"
    shutil.copytree(
        repo_root,
        source,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "build", "dist", "*.egg-info"
        ),
    )
    virtualenv_bin = source / "venv" / "bin"
    virtualenv_bin.mkdir(parents=True)
    interpreter = virtualenv_bin / "python"
    try:
        interpreter.symlink_to(sys.executable)
    except OSError:
        # Windows commonly denies symlink creation without Developer Mode.
        interpreter.write_text("virtualenv interpreter placeholder")
    for directory in ("env", "ENV"):
        candidate = source / directory / "bin"
        candidate.mkdir(parents=True, exist_ok=True)
        (candidate / "python").write_text("virtualenv interpreter placeholder")

    output = tmp_path / "dist"
    output.mkdir()
    monkeypatch.chdir(source)
    artifact = output / build_sdist(str(output), {})

    with tarfile.open(artifact) as archive:
        names = archive.getnames()

    assert not any(
        f"/{directory}/" in name
        for name in names
        for directory in ("venv", "env", "ENV")
    )


def _sdist_members(tmp_path: Path, monkeypatch) -> dict[str, str]:
    """Build an sdist from the working tree and return {name: text}."""
    repo_root = Path(__file__).parents[1]
    source = tmp_path / "source"
    shutil.copytree(
        repo_root,
        source,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "venv", "build", "dist", "*.egg-info"
        ),
    )
    output = tmp_path / "dist"
    output.mkdir()
    monkeypatch.chdir(source)
    artifact = output / build_sdist(str(output), {})

    contents: dict[str, str] = {}
    with tarfile.open(artifact) as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            # This module names the very strings it searches for, so scanning
            # itself reports a leak that is only the definition of the rule.
            if member.name.endswith(Path(__file__).name):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            contents[member.name] = handle.read().decode("utf-8", errors="replace")
    return contents


def test_sdist_contains_no_local_filesystem_paths(tmp_path: Path, monkeypatch) -> None:
    offenders = {
        name: match.group(0)
        for name, text in _sdist_members(tmp_path, monkeypatch).items()
        if (match := _LOCAL_PATH.search(text))
    }
    assert not offenders, (
        "published source distribution describes the machine it was built on: "
        + ", ".join(f"{name} ({path})" for name, path in sorted(offenders.items()))
    )


def test_sdist_names_no_private_repositories(tmp_path: Path, monkeypatch) -> None:
    offenders = {
        name: reference
        for name, text in _sdist_members(tmp_path, monkeypatch).items()
        for reference in _PRIVATE_REFERENCES
        if reference in text
    }
    assert not offenders, (
        "published source distribution references unrelated private repositories: "
        + ", ".join(f"{name} ({ref})" for name, ref in sorted(offenders.items()))
    )
