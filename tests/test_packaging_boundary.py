from pathlib import Path


def test_common_virtualenv_directories_are_excluded_from_source_builds() -> None:
    repo_root = Path(__file__).parents[1]
    ignored = {
        line.strip()
        for line in (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {".venv/", "venv/"} <= ignored
