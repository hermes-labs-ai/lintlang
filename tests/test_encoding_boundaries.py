"""Encoding diagnostics must preserve existing input and location contracts."""

import io
import json
from types import SimpleNamespace

import pytest

from lintlang.cli import main
from lintlang.parsers import (
    UnicodeDecodeErrorWithHint,
    decode_file_bytes,
    parse_file,
    parse_source,
)
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
    result = scan_file(path)
    expected = scan_source(source, path)
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
    assert scan_file(path).input_error is None


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

    assert main(["scan", *inputs, "--format", "json"]) == 0
    [result] = json.loads(capsys.readouterr().out)
    assert result["file"] == "agent.yaml"
    assert result["input_error"] is None
    assert result["inspected"]["system_prompt"] == 1


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
def test_bomless_utf16_and_utf32_are_rejected(encoding):
    """A BOM-less wide encoding is mostly NULs and decodes as UTF-8.

    Without this guard the detectors inspect ``Y\\x00o\\x00u\\x00...`` and match
    nothing, so a broken prompt reports PASS on a ``--fail-on fail`` gate.
    """
    raw = "You are a helpful assistant.\nKeep trying until it works.\n".encode(encoding)

    with pytest.raises(UnicodeDecodeErrorWithHint, match="without a byte-order mark"):
        decode_file_bytes(raw)


def test_bomless_utf16_does_not_report_clean(tmp_path, monkeypatch, capsys):
    """The false-clean from the issue: a BOM-less UTF-16 prompt must be ERROR."""
    raw = "You are a helpful assistant.\nKeep trying until it works.\n".encode("utf-16-le")
    (tmp_path / "prompt.txt").write_bytes(raw)
    monkeypatch.chdir(tmp_path)

    assert main(["scan", "prompt.txt", "--format", "json"]) == 1
    [result] = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "ERROR"
    assert "without a byte-order mark" in result["input_error"]
    assert result["structural_findings"] == []


def test_sparse_nul_in_real_world_sized_utf8_text_still_scans(tmp_path):
    """One literal NUL in a large valid skill is content, not an encoding signal."""
    # Mirrors the measured size and NUL position of the public
    # Claude-BugHunter hunt-auth-bypass skill without copying its text.
    size = 32_855
    nul_offset = 23_277
    prefix = b"# Instructions\n\n"
    suffix = b"\nKeep trying until it works.\n"
    raw = bytearray((b"Review records safely.\n" * ((size // 23) + 1))[:size])
    raw[: len(prefix)] = prefix
    raw[-len(suffix) :] = suffix
    raw[nul_offset] = 0
    assert len(raw) == size

    path = tmp_path / "SKILL.md"
    path.write_bytes(raw)
    result = scan_file(path)

    assert decode_file_bytes(bytes(raw)) == raw.decode("utf-8")
    assert result.input_error is None
    assert any(f.pattern_id == "H2" for f in result.structural_findings)


def test_isolated_nul_inside_detection_sample_is_preserved():
    raw = bytearray(b"Review records safely.\n" * 100)
    raw[127] = 0

    assert decode_file_bytes(bytes(raw)) == raw.decode("utf-8")


@pytest.mark.parametrize(
    "raw",
    [b"\x00" * 1024, (b"\x00" * 512) + (b"x" * 512)],
    ids=["all-nul", "clustered-nul"],
)
def test_nul_dense_text_is_rejected_instead_of_reporting_clean(raw):
    with pytest.raises(UnicodeDecodeErrorWithHint, match="without a byte-order mark"):
        decode_file_bytes(raw)


def test_ordinary_multilingual_utf8_still_decodes():
    source = "Check café, 日本語, العربية, and 🐍 records.\nBe concise.\n"
    assert decode_file_bytes(source.encode("utf-8")) == source


@pytest.mark.parametrize(
    ("raw", "hint", "filename"),
    [
        (
            b"\xff\xfe" + "system_prompt: Be concise.\n".encode("utf-16-le"),
            "appears to be UTF-16 encoded",
            "agent.yaml",
        ),
        (
            b"\xfe\xff" + "system_prompt: Be concise.\n".encode("utf-16-be"),
            "appears to be UTF-16 encoded",
            "agent.yaml",
        ),
        (
            "You are a helper.\nKeep trying until it works.\n".encode("utf-16-le"),
            "without a byte-order mark",
            "prompt.txt",
        ),
        (b"system_prompt: \x80\x81\xff\n", "File is not valid UTF-8", "agent.yaml"),
    ],
    ids=["utf16-le", "utf16-be", "bomless-utf16-le", "invalid-utf8"],
)
@pytest.mark.parametrize("input_kind", ["file", "directory", "stdin"])
@pytest.mark.parametrize("output_format", ["terminal", "markdown", "json", "sarif", "gitlab"])
def test_encoding_errors_fail_all_cli_input_and_output_paths(
    tmp_path, monkeypatch, capsys, raw, hint, filename, input_kind, output_format
):
    monkeypatch.chdir(tmp_path)
    if input_kind == "stdin":
        monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
        inputs = ["-", "--stdin-filename", filename]
    else:
        (tmp_path / filename).write_bytes(raw)
        inputs = [filename if input_kind == "file" else "."]

    assert main(["scan", *inputs, "--format", output_format]) == 1
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
    elif output_format == "gitlab":
        assert json.loads(captured.out) == []
        assert filename in captured.err
        assert hint in captured.err
    else:
        assert filename in captured.out
        assert hint in captured.out
        assert "UTF-8" in captured.out
        assert filename in captured.err
        assert hint in captured.err
        if output_format == "json":
            [result] = json.loads(captured.out)
            assert result["verdict"] == "ERROR"
            assert hint in result["input_error"]
        elif output_format == "markdown":
            assert "# Lintlang Input Error" in captured.out
        else:
            assert "ERROR" in captured.out


def test_text_stdin_unicode_errors_remain_input_errors(monkeypatch, capsys):
    class UnreadableTextStream:
        def read(self):
            raise UnicodeError("text stream decoding failed")

    monkeypatch.setattr("sys.stdin", UnreadableTextStream())
    assert main(["scan", "-", "--stdin-filename", "agent.yaml", "--format", "json"]) == 1
    [result] = json.loads(capsys.readouterr().out)
    assert result["verdict"] == "ERROR"
    assert result["input_error"] == "Failed to read standard input: text stream decoding failed"


@pytest.mark.parametrize("scan", [scan_file, scan_python_file])
def test_python_file_keeps_existing_tolerant_extraction(tmp_path, scan):
    path = tmp_path / "pipeline.py"
    path.write_bytes(b"# Legacy comment: \xff\nCONFIDENCE_THRESHOLD = 0.75\n")

    result = scan(path)
    assert result.input_error is None
    assert any(f.pattern_id == "P1" for f in result.structural_findings)
