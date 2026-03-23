from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from runner_bridge.backends import backend_contract_for_runner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Contract-first claude_vibecosystem beta backend")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = output_dir / "transcript.ndjson"
    artifact_bundle_path = output_dir / "artifact-bundle.json"
    result_path = output_dir / "result.json"

    backend_contract = _load_backend_contract(request)
    runtime_surface = _build_runtime_surface(request, backend_contract)
    expected_checks = _expected_checks(request)

    events = [
        {
            "ts": _utc_now(),
            "event": "runner.started",
            "message": f"Preparing {request['run_id']} for the claude_vibecosystem beta seam.",
        },
        {
            "ts": _utc_now(),
            "event": "adapter.contract.loaded",
            "message": (
                f"Loaded external-executor beta contract for vibecosystem agent "
                f"{runtime_surface['claude_agent']}."
            ),
        },
        {
            "ts": _utc_now(),
            "event": "adapter.stub.completed",
            "message": (
                "Recorded backend naming, provenance, and honesty boundaries without invoking "
                "Claude Code, vibecosystem hooks, or live network transport."
            ),
        },
    ]
    transcript_path.write_text("".join(json.dumps(event) + "\n" for event in events))

    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": "completed",
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "execution_backend_contract": backend_contract,
        "external_executor_beta": runtime_surface,
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": result_path.name,
        },
    }
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result = {
        "status": "completed",
        "transcript_path": transcript_path.name,
        "artifact_bundle_path": artifact_bundle_path.name,
        "machine_score": 0.0,
        "scorecard": {
            "runner": "claude_vibecosystem",
            "checks": [
                {
                    "name": "backend_contract_captured",
                    "passed": True,
                },
                {
                    "name": "claim_boundary_preserved",
                    "passed": True,
                },
            ],
        },
        "execution_honesty": {
            "backend": "claude_vibecosystem",
            "mode": backend_contract.get("mode", "external_executor_beta"),
            "beta_status": backend_contract.get("beta_status", "adapter_first_contract_stub"),
            "executes_commands": False,
            "executes_checks": False,
            "check_results": [
                {
                    "id": check.get("id", ""),
                    "command": check.get("command", ""),
                    "execution_status": "not_executed",
                    "exit_code": None,
                    "reason": (
                        "claude_vibecosystem beta seam is currently a contract/provenance stub and "
                        "does not invoke live verifier commands in tests"
                    ),
                }
                for check in expected_checks
            ],
            "mutation_enforcement": "not_enforced",
            "path_constraint_enforcement": "not_enforced",
            "external_executor": runtime_surface,
            "claim_boundary": backend_contract.get("claim_boundary", {}),
            "honesty_note": (
                "This claude_vibecosystem beta seam records backend naming, executor intent, and "
                "claim boundaries only. It did not invoke Claude Code, vibecosystem hooks, or the "
                "live Clawith/OpenClaw gateway. It does not claim sealed evaluation, tamper-proofing, "
                "independent executor isolation, or native Clawith parity."
            ),
        },
    }
    result_path.write_text(json.dumps(result, indent=2))
    return 0


def _load_backend_contract(request: dict[str, Any]) -> dict[str, Any]:
    contract = request.get("runner_backend_contract") if isinstance(request.get("runner_backend_contract"), dict) else None
    if not contract:
        packet_runtime = request.get("packet_runtime") if isinstance(request.get("packet_runtime"), dict) else {}
        contract = packet_runtime.get("execution_backend_contract") if isinstance(packet_runtime.get("execution_backend_contract"), dict) else None
    return dict(contract or backend_contract_for_runner("claude_vibecosystem"))


def _build_runtime_surface(request: dict[str, Any], backend_contract: dict[str, Any]) -> dict[str, Any]:
    workspace_snapshot = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    executor = backend_contract.get("executor") if isinstance(backend_contract.get("executor"), dict) else {}
    return {
        "adapter_mode": "contract_stub",
        "live_execution": "not_invoked",
        "runtime": executor.get("runtime", "Claude Code"),
        "agent_selection": executor.get("agent_selection", "vibecosystem"),
        "claude_agent": workspace_snapshot.get("claude_agent") or executor.get("default_agent", "backend-dev"),
        "prompt_transport": executor.get("prompt_transport", "stdin"),
        "workdir": workspace_snapshot.get("workdir") or ".",
        "workdir_mode": executor.get("workdir_mode", "dedicated_workdir_expected"),
        "control_plane_path": (backend_contract.get("control_plane") or {}).get("path", "external_gateway_only"),
    }


def _expected_checks(request: dict[str, Any]) -> list[dict[str, str]]:
    packet_runtime = request.get("packet_runtime") if isinstance(request.get("packet_runtime"), dict) else {}
    raw = packet_runtime.get("expected_checks")
    if not isinstance(raw, list):
        return []
    checks: list[dict[str, str]] = []
    for entry in raw:
        if isinstance(entry, dict):
            checks.append({
                "id": str(entry.get("id", "")),
                "command": str(entry.get("command", "")),
            })
    return checks


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
