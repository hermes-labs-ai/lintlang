"""Focused preflight CLI, first-use, failure-state, and privacy gates."""

from __future__ import annotations

import hashlib
import io
import json
import sys

import pytest

from lintlang.cli import main

PROMPT_CANARY = "PRIVATE_PROMPT_CANARY_7d912"
CONTEXT_CANARY = "PRIVATE_CONTEXT_CANARY_8a441"


def _stdin(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(value))


def test_cli_hero_and_matched_hard_negative(monkeypatch, capsys):
    _stdin(monkeypatch, "Is it true that remote work always reduces productivity?")
    notice_exit = main(["preflight", "-", "--format", "json"])
    notice = json.loads(capsys.readouterr().out)

    _stdin(
        monkeypatch,
        "What evidence supports or refutes whether remote work always reduces productivity?",
    )
    allow_exit = main(["preflight", "-", "--format", "json"])
    allow = json.loads(capsys.readouterr().out)

    assert notice_exit == 0
    assert notice["status"] == "NOTICE"
    assert [finding["rule_id"] for finding in notice["findings"]] == ["PF001"]
    assert allow_exit == 0
    assert allow["status"] == "ALLOW"
    assert allow["findings"] == []


def test_cli_default_redacts_canary_and_opt_in_reveals_it(monkeypatch, capsys):
    prompt = f"Is it true that {PROMPT_CANARY} is correct?"
    _stdin(monkeypatch, prompt)
    assert main(["preflight", "-"]) == 0
    terminal_default = capsys.readouterr()

    _stdin(monkeypatch, prompt)
    assert main(["preflight", "-", "--format", "json"]) == 0
    default = capsys.readouterr()

    _stdin(monkeypatch, prompt)
    assert main(["preflight", "-", "--format", "json", "--include-snippets"]) == 0
    disclosed = capsys.readouterr()

    assert PROMPT_CANARY not in terminal_default.out + terminal_default.err
    assert PROMPT_CANARY not in default.out + default.err
    assert PROMPT_CANARY in disclosed.out


def test_cli_context_is_typed_and_redacted_by_default(monkeypatch, capsys, tmp_path):
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "requirements": [{"key": "video_format", "required": True, "description": "House format"}],
                "bindings": [
                    {
                        "key": "video_format",
                        "value": CONTEXT_CANARY,
                        "source": "user",
                        "delivery": "IN_PROMPT",
                    }
                ],
                "constraints": [],
            }
        ),
        encoding="utf-8",
    )
    _stdin(monkeypatch, "Make a video about alligators.")

    exit_code = main(["preflight", "-", "--context", str(context), "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "NOTICE"
    assert [finding["rule_id"] for finding in payload["findings"]] == ["PF004"]
    assert CONTEXT_CANARY not in captured.out
    assert CONTEXT_CANARY not in captured.err


def test_cli_apply_is_explicit_in_memory_and_stdout_only(monkeypatch, capsys):
    prompt = "Is it true that wetlands help?"
    _stdin(monkeypatch, prompt)
    assert main(["preflight", "-", "--format", "json"]) == 0
    initial = json.loads(capsys.readouterr().out)
    correction_id = initial["corrections"][0]["correction_id"]

    _stdin(monkeypatch, prompt)
    exit_code = main(["preflight", "-", "--apply", correction_id])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "What evidence supports or refutes whether wetlands help?"
    assert "Post-apply preflight: ALLOW" in captured.err
    assert prompt not in captured.err


@pytest.mark.parametrize(
    ("prompt", "extra_args", "expected_status", "expected_exit"),
    [
        ("Assess the evidence for and against X.", [], "ALLOW", 0),
        ("   ", [], "ERROR", 2),
        ("¿Es verdad que X?", ["--language", "es"], "UNAVAILABLE", 3),
        ("Analyze “Is it true that X?", [], "UNAVAILABLE", 3),
    ],
)
def test_cli_status_exit_mapping(
    monkeypatch,
    capsys,
    prompt,
    extra_args,
    expected_status,
    expected_exit,
):
    _stdin(monkeypatch, prompt)
    exit_code = main(["preflight", "-", "--format", "json", *extra_args])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == expected_exit
    assert payload["status"] == expected_status
    assert payload["exit_code"] == expected_exit


def test_cli_missing_required_context_holds(monkeypatch, capsys, tmp_path):
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "requirements": [{"key": "video_provider", "required": True, "description": "Chosen provider"}],
                "bindings": [],
                "constraints": [],
            }
        ),
        encoding="utf-8",
    )
    _stdin(monkeypatch, "Make a video about alligators.")

    exit_code = main(["preflight", "-", "--context", str(context), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "HOLD"
    assert [finding["rule_id"] for finding in payload["findings"]] == ["PF004"]


def test_invalid_utf8_is_schema_coherent_redacted_error(capsys, tmp_path):
    prompt = tmp_path / "invalid.prompt"
    prompt.write_bytes(b"\xff\xfe" + PROMPT_CANARY.encode())

    exit_code = main(["preflight", str(prompt), "--format", "json", "--include-snippets"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "ERROR"
    assert payload["input"]["snippets_included"] is False
    assert all(not action["available"] for action in payload["actions"])
    assert PROMPT_CANARY not in captured.out
    assert PROMPT_CANARY not in captured.err


def test_context_surrogate_is_schema_coherent_redacted_error(monkeypatch, capsys, tmp_path):
    context = tmp_path / "surrogate-context.json"
    context.write_text(
        json.dumps(
            {
                "requirements": [{"key": "usual_format", "required": True}],
                "bindings": [
                    {
                        "key": "usual_format",
                        "value": CONTEXT_CANARY + "\ud800",
                        "source": "user",
                        "delivery": "IN_PROMPT",
                    }
                ],
                "constraints": [],
            }
        ),
        encoding="utf-8",
    )
    _stdin(monkeypatch, "Make a video about alligators.")

    exit_code = main(
        [
            "preflight",
            "-",
            "--context",
            str(context),
            "--format",
            "json",
            "--include-snippets",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["status"] == "ERROR"
    assert payload["diagnostics"][0]["code"] == "INVALID_BINDING"
    assert all(not action["available"] for action in payload["actions"])
    assert CONTEXT_CANARY not in captured.out + captured.err
    assert "\\ud800" not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err


def test_empty_language_is_schema_coherent_error(monkeypatch, capsys):
    _stdin(monkeypatch, "Assess the evidence for and against X.")

    exit_code = main(["preflight", "-", "--language", "", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "ERROR"
    assert payload["diagnostics"][0]["code"] == "INVALID_LANGUAGE"
    assert payload["input"]["language"] == "und"


def test_context_read_error_preserves_valid_prompt_metadata(monkeypatch, capsys, tmp_path):
    prompt = "🐊hello"
    missing_context = tmp_path / "missing-context.json"
    _stdin(monkeypatch, prompt)

    exit_code = main(["preflight", "-", "--context", str(missing_context), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "ERROR"
    assert payload["diagnostics"][0]["code"] == "CONTEXT_READ_FAILED"
    assert payload["input"]["sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert payload["input"]["codepoints"] == len(prompt)
    assert payload["input"]["utf8_bytes"] == len(prompt.encode())


def test_scan_and_preflight_help_remain_separate(capsys):
    with pytest.raises(SystemExit) as preflight_help:
        main(["preflight", "--help"])
    preflight_output = capsys.readouterr().out

    with pytest.raises(SystemExit) as scan_help:
        main(["scan", "--help"])
    scan_output = capsys.readouterr().out

    assert preflight_help.value.code == 0
    assert scan_help.value.code == 0
    assert "--include-snippets" in preflight_output
    assert "--include-snippets" not in scan_output
    assert "--fail-on" in scan_output
