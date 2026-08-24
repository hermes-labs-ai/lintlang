"""Tests for the one-command GitHub Actions initializer."""

from __future__ import annotations

from pathlib import Path

import yaml

from lintlang.cli import main


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("# Agent instructions\n", encoding="utf-8")
    return root


def test_init_github_creates_pinned_sarif_workflow(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path)
    nested = root / "packages" / "worker"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert main(["init", "--github"]) == 0

    workflow = root / ".github" / "workflows" / "lintlang.yml"
    text = workflow.read_text(encoding="utf-8")
    yaml.safe_load(text)
    assert (
        "hermes-labs-ai/lintlang@6be2907d557e534732865d3a3a3c55ea5f1a0ec9 # v0.4.1"
        in text
    )
    assert "path: \"AGENTS.md\"" in text
    assert "fail-on: fail" in text
    assert "sarif-file: lintlang.sarif" in text
    assert "security-events: write" in text
    assert "github.actor != 'dependabot[bot]'" in text
    assert "Created: .github/workflows/lintlang.yml" in capsys.readouterr().out


def test_init_github_is_idempotent(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path)
    monkeypatch.chdir(root)

    assert main(["init", "--github"]) == 0
    first = (root / ".github/workflows/lintlang.yml").read_bytes()
    capsys.readouterr()
    assert main(["init", "--github"]) == 0

    assert (root / ".github/workflows/lintlang.yml").read_bytes() == first
    assert "Up to date" in capsys.readouterr().out


def test_init_github_refuses_to_overwrite_without_force(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path)
    workflow = root / ".github/workflows/lintlang.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: existing\n", encoding="utf-8")
    monkeypatch.chdir(root)

    assert main(["init", "--github"]) == 1

    assert workflow.read_text(encoding="utf-8") == "name: existing\n"
    assert "already exists and differs" in capsys.readouterr().err


def test_init_github_force_replaces_known_destination(tmp_path, monkeypatch):
    root = _repository(tmp_path)
    workflow = root / ".github/workflows/lintlang.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: existing\n", encoding="utf-8")
    monkeypatch.chdir(root)

    assert main(["init", "--github", "--force"]) == 0

    assert "name: LintLang" in workflow.read_text(encoding="utf-8")


def test_init_github_accepts_explicit_repository_relative_path(tmp_path, monkeypatch):
    root = _repository(tmp_path)
    config = root / "config" / "agent contract.yaml"
    config.parent.mkdir()
    config.write_text("system_prompt: Be concise.\n", encoding="utf-8")
    monkeypatch.chdir(root)

    assert main(["init", "--github", "--path", "config/agent contract.yaml"]) == 0

    text = (root / ".github/workflows/lintlang.yml").read_text(encoding="utf-8")
    assert 'path: "config/agent contract.yaml"' in text


def test_init_github_rejects_path_outside_repository(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path)
    outside = tmp_path / "private.yaml"
    outside.write_text("system_prompt: private\n", encoding="utf-8")
    monkeypatch.chdir(root)

    assert main(["init", "--github", "--path", str(outside)]) == 1

    assert not (root / ".github/workflows/lintlang.yml").exists()
    assert "must stay inside" in capsys.readouterr().err


def test_init_github_requires_real_scan_input(tmp_path, monkeypatch, capsys):
    root = tmp_path / "repository"
    root.mkdir()
    (root / ".git").mkdir()
    monkeypatch.chdir(root)

    assert main(["init", "--github"]) == 1

    assert not (root / ".github/workflows/lintlang.yml").exists()
    assert "rerun with --path" in capsys.readouterr().err


def test_init_github_requires_git_repository(tmp_path, monkeypatch, capsys):
    (tmp_path / "AGENTS.md").write_text("# Agent instructions\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["init", "--github"]) == 1

    assert "must run inside a Git repository" in capsys.readouterr().err
