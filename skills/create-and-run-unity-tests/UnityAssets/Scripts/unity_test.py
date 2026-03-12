#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAEMON_ROOT = PROJECT_ROOT / "Library" / "TestDaemon"
PENDING_PATH = DAEMON_ROOT / "run-tests.pending"
FILTER_PATH = DAEMON_ROOT / "run-tests.filter"
CANCEL_PATH = DAEMON_ROOT / "run-tests.cancel"
STATUS_PATH = DAEMON_ROOT / "status.json"
RESULTS_PATH = DAEMON_ROOT / "results.json"
EVENTS_PATH = DAEMON_ROOT / "events.ndjson"
BATCHMODE_LOCK_MESSAGE = (
    "It looks like another Unity instance is running with this project open."
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filesystem client for the Unity persistent test runner."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Request an Edit Mode test run.")
    run_parser.add_argument(
        "filter", nargs="?", help="Optional assembly/namespace/fixture/test filter."
    )

    subparsers.add_parser("cancel", help="Request cancellation of the active test run.")
    subparsers.add_parser("status", help="Print status.json.")
    subparsers.add_parser("results", help="Print results.json.")
    subparsers.add_parser("events", help="Print events.ndjson.")
    subparsers.add_parser("path", help="Print the daemon directory.")

    watch_parser = subparsers.add_parser(
        "watch", help="Run `watchexec -e cs ./unity-test run` from the project root."
    )
    watch_parser.add_argument(
        "filter", nargs="?", help="Optional filter passed through to `unity-test run`."
    )

    args = parser.parse_args()

    if args.command == "run":
        return run_command(args.filter)
    if args.command == "cancel":
        return cancel_command()
    if args.command == "status":
        return print_file(STATUS_PATH)
    if args.command == "results":
        return print_file(RESULTS_PATH)
    if args.command == "events":
        return print_file(EVENTS_PATH)
    if args.command == "path":
        print(DAEMON_ROOT)
        return 0
    if args.command == "watch":
        return watch_command(args.filter)

    parser.error(f"unknown command: {args.command}")
    return 2


def run_command(filter_text: str | None) -> int:
    ensure_root()
    persist_filter(filter_text)

    if CANCEL_PATH.exists():
        CANCEL_PATH.unlink()

    batchmode_result = try_run_batchmode(filter_text)
    if batchmode_result.kind == "locked":
        PENDING_PATH.touch()
        print(
            json.dumps(
                {"requested": True, "filter": filter_text or "", "mode": "daemon"}
            )
        )
        return 0

    print(
        json.dumps(
            {
                "requested": True,
                "filter": filter_text or "",
                "mode": "batchmode",
                "exitCode": batchmode_result.exit_code,
            }
        )
    )
    return batchmode_result.exit_code


def cancel_command() -> int:
    ensure_root()
    CANCEL_PATH.touch()
    print(json.dumps({"cancelRequested": True}))
    return 0


def print_file(path: Path) -> int:
    if not path.exists():
        print(f"{path.relative_to(PROJECT_ROOT)} does not exist", file=sys.stderr)
        return 1

    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def watch_command(filter_text: str | None) -> int:
    watchexec = shutil.which("watchexec")
    if watchexec is None:
        print("watchexec is required for watch mode", file=sys.stderr)
        return 1

    command = [watchexec, "-e", "cs", "./unity-test", "run"]
    if filter_text:
        command.append(filter_text)

    return subprocess.call(command, cwd=PROJECT_ROOT)


def ensure_root() -> None:
    DAEMON_ROOT.mkdir(parents=True, exist_ok=True)


def persist_filter(filter_text: str | None) -> None:
    if filter_text:
        FILTER_PATH.write_text(filter_text.strip() + "\n", encoding="utf-8")
        return

    delete_if_exists(FILTER_PATH)


def try_run_batchmode(filter_text: str | None) -> "BatchmodeResult":
    unity_binary = resolve_unity_binary()
    if unity_binary is None:
        raise SystemExit(
            "Could not resolve the Unity Editor binary from ProjectSettings/ProjectVersion.txt"
        )

    started_at = utc_now()
    reset_run_artifacts(clear_filter=False)
    write_status(
        {
            "state": "running",
            "startedAt": started_at,
            "updatedAt": started_at,
            "finishedAt": "",
            "filter": filter_text or "",
            "message": "Executing Edit Mode tests via Unity batchmode",
            "cancelRequested": False,
        }
    )

    with tempfile.NamedTemporaryFile(
        prefix="unity-test-log-", suffix=".log", delete=False
    ) as log_handle:
        log_path = Path(log_handle.name)

    try:
        exit_code = stream_command(build_batchmode_command(unity_binary), log_path)

        if batchmode_reported_project_lock(log_path):
            write_status(
                {
                    "state": "idle",
                    "startedAt": "",
                    "updatedAt": utc_now(),
                    "finishedAt": "",
                    "filter": "",
                    "message": "Unity batchmode reported the project is already open; waiting for run-tests.pending",
                    "cancelRequested": False,
                }
            )
            reset_run_artifacts(clear_filter=False)
            return BatchmodeResult(kind="locked", exit_code=0)

        finished_at = utc_now()
        if not has_protocol_results():
            results_document = build_missing_results_document(
                filter_text=filter_text,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                log_path=log_path,
            )
            write_results(results_document)
            append_event(
                {
                    "event": "runFinished",
                    "status": "failed",
                    "message": results_document["failures"][0]["message"],
                }
            )
            write_status(
                {
                    "state": "finished",
                    "startedAt": started_at,
                    "updatedAt": finished_at,
                    "finishedAt": finished_at,
                    "filter": filter_text or "",
                    "message": results_document["failures"][0]["message"],
                    "cancelRequested": False,
                }
            )

        return BatchmodeResult(kind="completed", exit_code=exit_code)
    finally:
        log_path.unlink(missing_ok=True)


def resolve_unity_binary() -> Path | None:
    project_version_path = PROJECT_ROOT / "ProjectSettings" / "ProjectVersion.txt"
    if not project_version_path.exists():
        return None

    prefix = "m_EditorVersion: "
    editor_version = ""
    for line in project_version_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            editor_version = line[len(prefix) :].strip()
            break

    if not editor_version:
        return None

    unity_binary = (
        Path("/Applications/Unity/Hub/Editor")
        / editor_version
        / "Unity.app"
        / "Contents"
        / "MacOS"
        / "Unity"
    )
    if not os.access(unity_binary, os.X_OK):
        return None

    return unity_binary


def build_batchmode_command(unity_binary: Path) -> list[str]:
    return [
        str(unity_binary),
        "-batchmode",
        "-quit",
        "-nographics",
        "-accept-apiupdate",
        "-projectPath",
        str(PROJECT_ROOT),
        "-executeMethod",
        "UnityTdd.TestDaemon.BatchmodeTestRunner.Run",
        "-logFile",
        "-",
    ]


def stream_command(command: list[str], log_path: Path) -> int:
    import threading
    import time

    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None

        exit_called = threading.Event()

        def reader_thread():
            for line in process.stdout:
                sys.stdout.write(line)
                log_file.write(line)
                if "BatchmodeTestRunner calling EditorApplication.Exit" in line:
                    exit_called.set()

        thread = threading.Thread(target=reader_thread)
        thread.start()

        # Wait for reader to finish OR for Exit to be called + timeout
        while thread.is_alive():
            thread.join(timeout=0.5)
            if exit_called.is_set():
                # Give Unity 1 second to exit gracefully after EditorApplication.Exit
                time.sleep(1)
                if process.poll() is None:
                    print(
                        "\n[unity-test] Unity did not exit after 1s, forcing termination..."
                    )
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                break

        thread.join()
        return process.returncode if process.returncode is not None else 1


def batchmode_reported_project_lock(log_path: Path) -> bool:
    if not log_path.exists():
        return False

    return BATCHMODE_LOCK_MESSAGE in log_path.read_text(
        encoding="utf-8", errors="replace"
    )


def build_missing_results_document(
    *,
    filter_text: str | None,
    started_at: str,
    finished_at: str,
    exit_code: int,
    log_path: Path,
) -> dict[str, object]:
    diagnostics = [
        "Unity batchmode did not write Library/TestDaemon/results.json.",
        f"Unity process exit code: {exit_code}.",
    ]

    log_excerpt = extract_log_excerpt(log_path)
    if log_excerpt:
        diagnostics.append(f"Batchmode log excerpt:\n{log_excerpt}")

    return {
        "state": "finished",
        "total": 0,
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "duration": 0.0,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "filter": filter_text or "",
        "canceled": False,
        "failures": [
            {
                "name": "UnityBatchmodeTestRun",
                "message": " ".join(diagnostics[:2]),
                "stackTrace": "\n\n".join(diagnostics[2:]),
            }
        ],
    }


def extract_log_excerpt(log_path: Path) -> str:
    if not log_path.exists():
        return ""

    lines = [
        line.rstrip()
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    ]
    interesting = [
        line
        for line in lines
        if "executeMethod" in line
        or "BatchmodeTestRunner" in line
        or "runSynchronously" in line
        or "Running tests" in line
        or "Test Run" in line
        or "Batchmode quit" in line
        or "Exiting batchmode" in line
    ]

    excerpt = interesting[-12:] if interesting else lines[-12:]
    return "\n".join(excerpt)


def reset_run_artifacts(clear_filter: bool = True) -> None:
    write_text_atomic(EVENTS_PATH, "")
    delete_if_exists(RESULTS_PATH)
    delete_if_exists(PENDING_PATH)
    delete_if_exists(CANCEL_PATH)
    if clear_filter:
        delete_if_exists(FILTER_PATH)


def delete_if_exists(path: Path) -> None:
    path.unlink(missing_ok=True)


def write_status(document: dict[str, object]) -> None:
    write_json_atomic(STATUS_PATH, document)


def write_results(document: dict[str, object]) -> None:
    write_json_atomic(RESULTS_PATH, document)


def append_event(document: dict[str, object]) -> None:
    event = {
        "event": document.get("event", ""),
        "name": document.get("name", ""),
        "status": document.get("status", ""),
        "timestamp": utc_now(),
        "message": document.get("message", ""),
    }
    with EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def has_protocol_results() -> bool:
    return RESULTS_PATH.exists() and RESULTS_PATH.stat().st_size > 0


def write_json_atomic(path: Path, document: dict[str, object]) -> None:
    write_text_atomic(path, json.dumps(document, indent=2) + "\n")


def write_text_atomic(path: Path, contents: str) -> None:
    ensure_root()
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(contents, encoding="utf-8")
    temp_path.replace(path)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


class BatchmodeResult:
    def __init__(self, kind: str, exit_code: int) -> None:
        self.kind = kind
        self.exit_code = exit_code


if __name__ == "__main__":
    raise SystemExit(main())
