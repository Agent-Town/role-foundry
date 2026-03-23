from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .backends import backend_command_for_runner, backend_contract_for_runner, known_runner_backends
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
    parser.add_argument(
        "--runner-backend",
        choices=known_runner_backends(),
        help="Select a named runner backend contract and entrypoint",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.request and not args.packet:
        print("error: one of --request or --packet is required", file=sys.stderr)
        return 1
    if args.runner_backend and args.backend_command:
        print("error: choose either --runner-backend or --backend-command, not both", file=sys.stderr)
        return 1

    try:
        selected_backend = args.runner_backend or None
        if args.packet:
            run_obj = load_run_object(
                args.packet,
                run_id=args.run_id,
                artifacts_root=args.artifacts_root,
                execution_backend=selected_backend or "pending",
                execution_backend_contract=(
                    backend_contract_for_runner(selected_backend) if selected_backend else None
                ),
            )
            request = run_obj.to_run_request()
        else:
            request = RunRequest.load(args.request)
            if selected_backend:
                request = _with_runner_backend_contract(request, selected_backend)

        control_plane = ClawithRunClient(args.clawith_url, args.clawith_secret)
        backend_command = shlex.split(args.backend_command) if args.backend_command else None
        if selected_backend and not backend_command:
            backend_command = backend_command_for_runner(selected_backend)
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


def _with_runner_backend_contract(request: RunRequest, backend_id: str) -> RunRequest:
    payload = request.to_dict()
    payload["runner_backend"] = backend_id
    payload["runner_backend_contract"] = backend_contract_for_runner(backend_id)
    packet_runtime = payload.get("packet_runtime") if isinstance(payload.get("packet_runtime"), dict) else None
    if packet_runtime is not None:
        packet_runtime["execution_backend"] = backend_id
        packet_runtime["execution_backend_contract"] = backend_contract_for_runner(backend_id)
        payload["packet_runtime"] = packet_runtime
    return RunRequest.from_dict(payload)


if __name__ == "__main__":
    raise SystemExit(main())
