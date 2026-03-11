#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAEMON_ROOT = PROJECT_ROOT / "Library" / "TestDaemon"
PENDING_PATH = DAEMON_ROOT / "run-tests.pending"
FILTER_PATH = DAEMON_ROOT / "run-tests.filter"
CANCEL_PATH = DAEMON_ROOT / "run-tests.cancel"
STATUS_PATH = DAEMON_ROOT / "status.json"
RESULTS_PATH = DAEMON_ROOT / "results.json"
EVENTS_PATH = DAEMON_ROOT / "events.ndjson"


def main() -> int:
    parser = argparse.ArgumentParser(description="Filesystem client for the Unity persistent test runner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Request an Edit Mode test run.")
    run_parser.add_argument("filter", nargs="?", help="Optional assembly/namespace/fixture/test filter.")

    subparsers.add_parser("cancel", help="Request cancellation of the active test run.")
    subparsers.add_parser("status", help="Print status.json.")
    subparsers.add_parser("results", help="Print results.json.")
    subparsers.add_parser("events", help="Print events.ndjson.")
    subparsers.add_parser("path", help="Print the daemon directory.")

    watch_parser = subparsers.add_parser("watch", help="Run `watchexec -e cs ./unity-test run` from the project root.")
    watch_parser.add_argument("filter", nargs="?", help="Optional filter passed through to `unity-test run`.")

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

    if filter_text:
        FILTER_PATH.write_text(filter_text.strip() + "\n", encoding="utf-8")
    elif FILTER_PATH.exists():
        FILTER_PATH.unlink()

    if CANCEL_PATH.exists():
        CANCEL_PATH.unlink()

    PENDING_PATH.touch()
    print(json.dumps({"requested": True, "filter": filter_text or ""}))
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
