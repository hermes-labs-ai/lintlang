#!/usr/bin/env python3
"""Install both distributions into clean environments and exercise installed consumers."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import venv
from pathlib import Path

PROBE = r'''
import importlib.metadata as metadata
import json
from pathlib import Path
import lintlang
from lintlang.gate import FPGate
from lintlang.scanner import scan_file
from lintlang.report import compute_verdict
assert lintlang.__version__ == metadata.version("lintlang") == "0.9.0"
requires = metadata.requires("lintlang")
assert [r.split(";")[0].strip().lower() for r in requires if ";" not in r] == ["pyyaml>=6.0.3"]
assert len(FPGate().feature_names) == 34
assert (Path(lintlang.__file__).parent / "preflight/schema/preflight-result.v1.schema.json").is_file()
path = Path("bad.yaml")
path.write_text('tools:\n  - name: broken\n    description: "Get data"\n')
raw, gated = scan_file(path, gate=False), scan_file(path)
assert any(f.code == "H1.2" for f in raw.structural_findings)
assert compute_verdict(raw) == "FAIL"
assert gated.structural_findings == []
assert gated.raw_findings_count == gated.suppressed_count == len(raw.structural_findings)
assert compute_verdict(gated) == "PASS"
assert gated.gate_status == "evaluated"
kept_path = Path("audit/SKILL.md")
kept_path.parent.mkdir()
kept_path.write_text("---\nname: audit\ndescription: Build MCP servers with the TypeScript SDK, typed tools, resource handlers, prompts, schema validation, HTTP transports and deployment configuration (工具配置指南).\n---\nBody.\n")
kept = scan_file(kept_path)
assert [f.code for f in kept.structural_findings] == ["H1.8"]
assert kept.structural_findings[0].gate_decision == "KEEP"
assert compute_verdict(kept) == "FAIL"
english_path = Path("english-audit/SKILL.md")
english_path.parent.mkdir()
english_path.write_text("---\nname: english-audit\ndescription: Build MCP servers with the TypeScript SDK, typed tools, resource handlers, prompts, schema validation, HTTP transports and deployment configuration.\n---\nBody.\n")
english = scan_file(english_path, gate=False)
assert english.inspected["skill_description"] == 1
assert english.structural_findings == []
assert compute_verdict(english) == "PASS"
print(json.dumps({"version": lintlang.__version__, "raw_findings": len(raw.structural_findings), "kept_findings": len(kept.structural_findings), "english_h18_skipped": True}))
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    args = parser.parse_args()
    artifacts = sorted(args.dist.resolve().glob("lintlang-*.whl")) + sorted(args.dist.resolve().glob("lintlang-*.tar.gz"))
    if len(artifacts) != 2:
        raise SystemExit("Expected exactly one wheel and one sdist")
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="lintlang-artifact-") as directory:
            root = Path(directory)
            environment = root / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / "bin/python"
            subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(artifact)], check=True, cwd=root)
            subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=root)
            subprocess.run([str(python), "-I", "-c", PROBE], check=True, cwd=root)
            raw_result = subprocess.run(
                [str(python), "-I", "-m", "lintlang", "scan", "bad.yaml", "--no-gate", "--format", "json", "--fail-on", "fail"],
                cwd=root, capture_output=True, text=True,
            )
            assert raw_result.returncode == 1, raw_result.stderr
            assert any(finding["code"] == "H1.2" for finding in json.loads(raw_result.stdout)[0]["structural_findings"])
            suppressed_result = subprocess.run(
                [str(python), "-I", "-m", "lintlang", "scan", "bad.yaml", "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )
            assert suppressed_result.returncode == 0, suppressed_result.stderr
            suppressed = json.loads(suppressed_result.stdout)[0]
            assert suppressed["structural_findings"] == []
            assert suppressed["gate"]["raw_findings"] == suppressed["gate"]["suppressed"] > 0
            english_result = subprocess.run(
                [str(python), "-I", "-m", "lintlang", "scan", "english-audit/SKILL.md", "--no-gate", "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )
            assert english_result.returncode == 0, english_result.stderr
            assert json.loads(english_result.stdout)[0]["structural_findings"] == []
            for format_name in ("json", "sarif", "gitlab"):
                result = subprocess.run([str(python), "-I", "-m", "lintlang", "scan", "audit/SKILL.md", "--format", format_name], cwd=root, capture_output=True, text=True)
                assert result.returncode == 1, result.stderr
                report = json.loads(result.stdout)
                if format_name == "json":
                    assert report[0]["verdict"] == "FAIL"
                    assert report[0]["structural_findings"][0]["gate_decision"] == "KEEP"
                elif format_name == "sarif":
                    assert report["runs"][0]["results"][0]["properties"]["lintlangGateDecision"] == "KEEP"
                    assert report["runs"][0]["results"][0]["level"] == "error"
                else:
                    assert "Gate: KEEP" in report[0]["description"]
                    assert report[0]["severity"] == "blocker"
            print(f"PASS {artifact.name}", flush=True)


if __name__ == "__main__":
    main()
