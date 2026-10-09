"""Encoding diagnostics must preserve existing input and location contracts."""

import io
import json
from types import SimpleNamespace

import pytest

from lintlang.cli import main
from lintlang.parsers import decode_file_bytes, parse_file, parse_source
from lintlang.scanner import scan_file, scan_python_file, scan_source


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
@pytest.mark.parametrize(
    ("filename", "source"),
    [
        (
            "SKILL.md",
            "---\nname: lookup\ndescription: Use when searching café records.\n---\n"
            "Check 日本語 records.\nKeep trying until it works.\n",
        ),
        ("agent.yaml", "system_prompt: |\n  Check 日本語 records.\n  Keep trying until it works.\n"),
        ("agent.json", '{\n  "system_prompt": "Check 日本語 records. Keep trying until it works."\n}\n'),
    ],
    ids=["skill", "yaml", "json"],
)
def test_file_newlines_preserve_metadata_and_finding_locations(tmp_path, newline, filename, source):
    path = tmp_path / filename
    path.write_bytes(source.replace("\n", newline).encode("utf-8"))

    assert parse_file(path) == parse_source(source, path)
    result = scan_file(path, gate=False)
    expected = scan_source(source, path, gate=False)
    assert result.input_error is None
    assert any(f.pattern_id == "H2" and f.source_region is not None for f in expected.structural_findings)
    assert result.structural_findings == expected.structural_findings


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_byte_decoder_preserves_multilingual_text_and_newlines(newline):
    source = f"Check café, 日本語, العربية, and 🐍 records.{newline}Be concise.{newline}"
    assert decode_file_bytes(source.encode("utf-8")) == source


@pytest.mark.parametrize(
    ("filename", "source"),
    [
        ("agent.yaml", "system_prompt: Check café and 日本語 records.\n"),
        ("SKILL.md", "---\nname: lookup\ndescription: Use when searching café records.\n---\nBe concise.\n"),
    ],
    ids=["yaml", "skill"],
)
def test_supported_utf8_bom_preserves_parsed_content(tmp_path, filename, source):
    path = tmp_path / filename
    path.write_bytes(b"\xef\xbb\xbf" + source.encode("utf-8"))
    assert parse_file(path) == parse_source(source, path)
    assert scan_file(path, gate=False).input_error is None


def test_json_utf8_bom_keeps_existing_parser_rejection(tmp_path):
    path = tmp_path / "agent.json"
    path.write_bytes(b'\xef\xbb\xbf{"system_prompt": "Be concise."}')
    with pytest.raises(json.JSONDecodeError, match="BOM"):
        parse_file(path)


@pytest.mark.parametrize("input_kind", ["file", "directory", "stdin"])
def test_valid_multilingual_utf8_cli_input(tmp_path, monkeypatch, capsys, input_kind):
    monkeypatch.chdir(tmp_path)
    raw = "system_prompt: Check café, 日本語, العربية, and 🐍 records.\n".encode()
    if input_kind == "stdin":
        monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
        inputs = ["-", "--stdin-filename", "agent.yaml"]
    else:
        (tmp_path / "agent.yaml").write_bytes(raw)
        inputs = ["agent.yaml" if input_kind == "file" else "."]

    assert main(["scan", "--no-gate", *inputs, "--format", "json"]) == 0
    [result] = json.loads(capsys.readouterr().out)
    assert result["file"] == "agent.yaml"
    assert result["input_error"] is None
    assert result["inspected"]["system_prompt"] == 1


@pytest.mark.parametrize(
    ("raw", "hint"),
    [
        (
            "system_prompt: Be concise.\n".encode("utf-16-le"),
            "contains a NUL byte",
        ),
        (
            "system_prompt: Be concise.\n".encode("utf-16-be"),
            "contains a NUL byte",
        ),
        (
            "system_prompt: Be concise.\n".encode("utf-32-le"),
            "contains a NUL byte",
        ),
        (
            "system_prompt: Be concise.\n".encode("utf-32-be"),
            "contains a NUL byte",
        ),
        (b"\xff\xfe" + "system_prompt: Be concise.\n".encode("utf-16-le"), "appears to be UTF-16 encoded"),
        (b"\xfe\xff" + "system_prompt: Be concise.\n".encode("utf-16-be"), "appears to be UTF-16 encoded"),
        (b"system_prompt: \x80\x81\xff\n", "File is not valid UTF-8"),
    ],
    ids=[
        "utf16-le-no-bom",
        "utf16-be-no-bom",
        "utf32-le-no-bom",
        "utf32-be-no-bom",
        "utf16-le",
        "utf16-be",
        "invalid-utf8",
    ],
)
@pytest.mark.parametrize("input_kind", ["file", "directory", "stdin"])
@pytest.mark.parametrize("output_format", ["terminal", "json", "sarif"])
def test_encoding_errors_fail_all_cli_input_and_output_paths(
    tmp_path, monkeypatch, capsys, raw, hint, input_kind, output_format
):
    monkeypatch.chdir(tmp_path)
    if input_kind == "stdin":
        monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
        inputs = ["-", "--stdin-filename", "agent.yaml"]
    else:
        (tmp_path / "agent.yaml").write_bytes(raw)
        inputs = ["agent.yaml" if input_kind == "file" else "."]

    assert main(["scan", "--no-gate", *inputs, "--format", output_format]) == 1
    captured = capsys.readouterr()
    if output_format == "sarif":
        [run] = json.loads(captured.out)["runs"]
        assert run["results"] == []
        [invocation] = run["invocations"]
        assert invocation["executionSuccessful"] is False
        [notification] = invocation["toolExecutionNotifications"]
        assert notification["level"] == "error"
        # SARIF intentionally omits filenames and raw diagnostic text.
        assert notification["message"]["text"] == "Input could not be inspected"
    else:
        assert "agent.yaml" in captured.out
        assert hint in captured.out
        assert "UTF-8" in captured.out
        assert "agent.yaml" in captured.err
        assert hint in captured.err
        if output_format == "json":
            [result] = json.loads(captured.out)
            assert result["verdict"] == "ERROR"
            assert hint in result["input_error"]
        else:
            assert "ERROR" in captured.out


def test_text_stdin_unicode_errors_remain_input_errors(monkeypatch, capsys):
    class UnreadableTextStream:
        def read(self):
            raise UnicodeError("text stream decoding failed")

    monkeypatch.setattr("sys.stdin", UnreadableTextStream())
    assert main(["scan", "--no-gate", "-", "--stdin-filename", "agent.yaml", "--format", "json"]) == 1
    [result] = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "ERROR"
    assert result["input_error"] == "Failed to read standard input: text stream decoding failed"


@pytest.mark.parametrize("scan", [scan_file, scan_python_file])
def test_python_file_keeps_existing_tolerant_extraction(tmp_path, scan):
    path = tmp_path / "pipeline.py"
    path.write_bytes(b"# Legacy comment: \xff\nCONFIDENCE_THRESHOLD = 0.75\n")

    result = scan(path, gate=False)
    assert result.input_error is None
    assert any(f.pattern_id == "P1" for f in result.structural_findings)
