from __future__ import annotations

import argparse
import json
import socket
import uuid

from client import SchedulerClient, dumps_pretty
from repo_detect import detect_from_git_remote
from result_schema import load_result_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("claim")

    heartbeat = sub.add_parser("heartbeat")
    heartbeat.add_argument("task_id")
    heartbeat.add_argument("--session-id", required=True)
    heartbeat.add_argument("--phase", required=True)
    heartbeat.add_argument("--message", default="")

    report = sub.add_parser("report")
    report.add_argument("task_id")
    report.add_argument("--session-id", required=True)
    report.add_argument("--file", required=True)

    release = sub.add_parser("release")
    release.add_argument("task_id")
    release.add_argument("--session-id", required=True)
    release.add_argument("--reason", required=True)
    release.add_argument("--status", default="queued")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = SchedulerClient()

    if args.command == "claim":
        identity = detect_from_git_remote()
        payload = {
            "repo_key": identity["repo_key"],
            "agent_user": "gds-agent",
            "worker_host": socket.gethostname(),
            "session_id": f"local-{uuid.uuid4().hex[:12]}",
        }
        result = client.claim(payload)
        print("" if result is None else dumps_pretty(result))
        return 0

    if args.command == "heartbeat":
        result = client.heartbeat(
            {
                "task_id": args.task_id,
                "session_id": args.session_id,
                "phase": args.phase,
                "message": args.message,
            }
        )
        print(dumps_pretty(result))
        return 0

    if args.command == "report":
        payload = load_result_payload(args.file)
        payload["task_id"] = args.task_id
        payload["session_id"] = args.session_id
        result = client.report(payload)
        print(dumps_pretty(result))
        return 0

    if args.command == "release":
        result = client.release(
            {
                "task_id": args.task_id,
                "session_id": args.session_id,
                "reason": args.reason,
                "status": args.status,
            }
        )
        print(dumps_pretty(result))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
