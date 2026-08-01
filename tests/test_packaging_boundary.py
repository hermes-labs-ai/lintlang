import shutil
import sys
import tarfile
from pathlib import Path

from hatchling.build import build_sdist


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
    (virtualenv_bin / "python").symlink_to(sys.executable)

    output = tmp_path / "dist"
    output.mkdir()
    monkeypatch.chdir(source)
    artifact = output / build_sdist(str(output), {})

    with tarfile.open(artifact) as archive:
        names = archive.getnames()

    assert not any("/venv/" in name for name in names)
