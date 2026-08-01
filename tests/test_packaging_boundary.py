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
