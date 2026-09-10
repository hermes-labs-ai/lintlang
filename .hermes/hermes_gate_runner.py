"""Self-contained deterministic repository runner; copied byte-for-byte by init."""

from __future__ import annotations

import fnmatch
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# The copied runner has the same minimum runtime as the installed CLI.
if sys.version_info < (3, 11):
    raise SystemExit("Hermes Gate runner requires Python 3.11 or newer; use that interpreter to run this file.")

import tomllib

RUNNER_VERSION = "0.1.2"
OUTPUT_CAP = 65536


def _root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError("not a Git repository")
    return Path(result.stdout.strip()).resolve()


def _changed(root: Path) -> list[str]:
    values: set[str] = set()
    for args in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
        values.update(x.decode("utf-8", "surrogateescape") for x in proc.stdout.split(b"\0") if x)
    return sorted(values)


def _match(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or (
        pattern.startswith("**/") and fnmatch.fnmatch(path, pattern[3:])
    )


def run(
    mode: str, *, root: Path | None = None, files: list[str] | None = None
) -> dict[str, object]:
    started = time.monotonic()
    root = (root or _root()).resolve()
    config_path = root / ".hermes" / "gate.toml"
    if not config_path.is_file():
        return _result(mode, "NOT_CONFIGURED", started, [], "run hermes-gate init")
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _result(mode, "ERROR", started, [], f"invalid profile: {exc}")
    paths = list(files) if files is not None else _changed(root)
    paths = [path for path in paths if os.path.lexists(root / path)]
    exclusions = config.get("gate", {}).get("exclusions", [])
    paths = [path for path in paths if not any(_match(path, pattern) for pattern in exclusions)]
    if mode == "fast" and not paths:
        return _result(mode, "NOT_APPLICABLE", started, [], "no changed files")
    commands = list(config.get(mode, []))
    if not commands:
        return _result(mode, "NOT_CONFIGURED", started, [], f"no [[{mode}]] commands")
    budget = (
        float(config.get("gate", {}).get("fast_budget_seconds", 8.0)) if mode == "fast" else None
    )
    checks: list[dict[str, object]] = []
    for spec in commands:
        globs = spec.get("globs", ["**/*"])
        selected = [path for path in paths if any(_match(path, pattern) for pattern in globs)]
        if mode == "fast" and not selected:
            continue
        argv: list[str] = []
        for part in spec.get("argv", []):
            argv.extend(selected if part == "{files}" else [part])
        if not argv or any(not isinstance(part, str) for part in argv):
            return _result(mode, "ERROR", started, checks, "argv must be a non-empty string array")
        elapsed = time.monotonic() - started
        timeout = float(spec.get("timeout_seconds", 8.0))
        if budget is not None:
            timeout = min(timeout, max(0.01, budget - elapsed))
        check = _execute(argv, root, timeout, str(spec.get("name", argv[0])))
        checks.append(check)
        if check["status"] != "PASS":
            return _result(mode, "FAIL", started, checks, str(check.get("reason", "check failed")))
        if budget is not None and time.monotonic() - started >= budget:
            return _result(mode, "FAIL", started, checks, "fast budget exhausted")
    if not checks:
        return _result(mode, "NOT_APPLICABLE", started, [], "no commands matched changed files")
    return _result(mode, "PASS", started, checks, "")


def _execute(argv: list[str], root: Path, timeout: float, name: str) -> dict[str, object]:
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            argv,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError:
        return {"name": name, "argv": argv, "status": "FAIL", "reason": "executable unavailable"}

    stdout_capture: dict[str, object] = {"data": b"", "total": 0}
    stderr_capture: dict[str, object] = {"data": b"", "total": 0}
    assert proc.stdout is not None
    assert proc.stderr is not None
    threads = [
        threading.Thread(
            target=_drain_bounded,
            args=(proc.stdout, OUTPUT_CAP // 2, stdout_capture),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_bounded,
            args=(proc.stderr, OUTPUT_CAP // 2, stderr_capture),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    deadline = started + timeout
    while proc.poll() is None or any(thread.is_alive() for thread in threads):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.01, remaining))
    timed_out = proc.poll() is None or any(thread.is_alive() for thread in threads)
    if timed_out:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if proc.poll() is None:
            proc.wait()
        for thread in threads:
            thread.join(timeout=0.5)
        return {"name": name, "argv": argv, "status": "FAIL", "reason": "timeout"}

    for thread in threads:
        thread.join()
    stdout = bytes(stdout_capture["data"])
    stderr = bytes(stderr_capture["data"])
    total_output = int(stdout_capture["total"]) + int(stderr_capture["total"])
    return {
        "name": name,
        "argv": argv,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "returncode": proc.returncode,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
        "output_truncated": total_output > len(stdout) + len(stderr),
    }


def _drain_bounded(pipe, cap: int, capture: dict[str, object]) -> None:
    kept = bytearray()
    total = 0
    try:
        while chunk := pipe.read(65536):
            total += len(chunk)
            remaining = cap - len(kept)
            if remaining > 0:
                kept.extend(chunk[:remaining])
    finally:
        pipe.close()
        capture["data"] = bytes(kept)
        capture["total"] = total


def _diff_check(root: Path, paths: list[str]) -> int:
    """Check selected worktree, index and untracked bytes using Git's whitespace rules."""
    if not paths:
        return 0
    git = ["git", "--literal-pathspecs", "-C", str(root)]
    for flags in ([], ["--cached"]):
        result = subprocess.run([*git, "diff", *flags, "--check", "--", *paths], check=False)
        if result.returncode:
            return result.returncode
    untracked = subprocess.run(
        [*git, "ls-files", "--others", "--exclude-standard", "-z", "--", *paths],
        capture_output=True, check=False,
    )
    if untracked.returncode:
        sys.stderr.buffer.write(untracked.stderr)
        return untracked.returncode
    for raw in untracked.stdout.split(b"\0"):
        if not raw:
            continue
        path = root / os.fsdecode(raw)
        # Git stores a symlink target, not the contents of its destination.
        if path.is_symlink() or not path.is_file():
            continue
        result = subprocess.run(
            [*git, "diff", "--no-index", "--check", "--", os.devnull, str(path)],
            check=False,
        )
        # --no-index implies --exit-code: 1 means a clean new-file diff;
        # --check reports whitespace errors with bit 2 set.
        if result.returncode not in (0, 1):
            return result.returncode
    return 0


def _result(
    mode: str, status: str, started: float, checks: list[dict[str, object]], reason: str
) -> dict[str, object]:
    return {
        "schema": "hermes-gate/runner-v1",
        "runner_version": RUNNER_VERSION,
        "command": mode,
        "status": status,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "checks": checks,
        "reason": reason,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "diff-check":
        return _diff_check(_root(), args[1:])
    if not args or args[0] not in {"fast", "full"}:
        print(json.dumps({"status": "ERROR", "reason": "usage: runner.py fast|full"}))
        return 2
    result = run(args[0])
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"PASS", "NOT_APPLICABLE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
