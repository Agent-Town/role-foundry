from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .bridge import ClawithRunClient, RunBridge
from .contract import ContractError, RunRequest
from .packet_runtime import load_run_object


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Role Foundry runner-bridge job")
    parser.add_argument("--request", help="Path to the run request JSON")
    parser.add_argument(
        "--packet",
        help="Load a task packet by acceptance_test_id (e.g. A001) and run it through the bridge",
    )
    parser.add_argument("--run-id", help="Override run_id (used with --packet)")
    parser.add_argument(
        "--artifacts-root",
        default="runtime/runs",
        help="Directory where transcripts and artifact bundles are stored",
    )
    parser.add_argument("--clawith-url", help="Clawith-compatible control plane base URL")
    parser.add_argument("--clawith-secret", default="", help="Machine-to-machine bridge secret")
    parser.add_argument(
        "--backend-command",
        help="Override backend command, for example: 'python3 -m runner_bridge.backends.local_replay'",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.request and not args.packet:
        print("error: one of --request or --packet is required", file=sys.stderr)
        return 1

    try:
        if args.packet:
            run_obj = load_run_object(
                args.packet,
                run_id=args.run_id,
                artifacts_root=args.artifacts_root,
            )
            request = run_obj.to_run_request()
        else:
            request = RunRequest.load(args.request)

        control_plane = ClawithRunClient(args.clawith_url, args.clawith_secret)
        backend_command = shlex.split(args.backend_command) if args.backend_command else None
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
