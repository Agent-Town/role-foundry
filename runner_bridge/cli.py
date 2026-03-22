from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .bridge import ClawithRunClient, RunBridge
from .contract import ContractError, RunRequest

BACKEND_COMMANDS = {
    "local-replay": [sys.executable, "-m", "runner_bridge.backends.local_replay"],
    "claude-vibe": [sys.executable, "-m", "runner_bridge.backends.claude_vibe"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Role Foundry runner-bridge job")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument(
        "--artifacts-root",
        default="runtime/runs",
        help="Directory where transcripts and artifact bundles are stored",
    )
    parser.add_argument("--clawith-url", help="Clawith-compatible control plane base URL")
    parser.add_argument("--clawith-secret", default="", help="Machine-to-machine bridge secret")
    parser.add_argument(
        "--backend",
        choices=sorted(BACKEND_COMMANDS),
        default="local-replay",
        help="Select a first-class backend adapter",
    )
    parser.add_argument(
        "--backend-command",
        help="Override backend command, for example: 'python3 -m runner_bridge.backends.local_replay'",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        request = RunRequest.load(args.request)
        control_plane = ClawithRunClient(args.clawith_url, args.clawith_secret)
        backend_command = (
            shlex.split(args.backend_command)
            if args.backend_command
            else list(BACKEND_COMMANDS[args.backend])
        )
        bridge = RunBridge(
            artifacts_root=Path(args.artifacts_root),
            control_plane=control_plane,
            backend_command=backend_command,
        )
        result = bridge.run(request)
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
