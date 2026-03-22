from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic local replay runner for Milestone 4")
    parser.add_argument("--request", required=True, help="Path to the run request JSON")
    parser.add_argument("--output-dir", required=True, help="Where to write transcript + artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request = json.loads(Path(args.request).read_text())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    simulate_failure = bool(request.get("workspace_snapshot", {}).get("simulate_failure"))
    transcript_path = output_dir / "transcript.ndjson"
    artifact_bundle_path = output_dir / "artifact-bundle.json"
    result_path = output_dir / "result.json"

    events = [
        {
            "ts": _utc_now(),
            "event": "runner.started",
            "message": f"Starting {request['run_id']} for {request['agent_role']} on {request['scenario_set_id']}",
        },
        {
            "ts": _utc_now(),
            "event": "runner.objective",
            "message": request.get("workspace_snapshot", {}).get(
                "objective", "No explicit objective provided."
            ),
        },
    ]

    if simulate_failure:
        events.append(
            {
                "ts": _utc_now(),
                "event": "runner.failed",
                "message": "Rejected by LocalReplayRunner because workspace_snapshot.simulate_failure=true",
            }
        )
        status = "failed"
        machine_score = 0.0
        error = "simulated failure requested by workspace_snapshot"
    else:
        events.append(
            {
                "ts": _utc_now(),
                "event": "runner.completed",
                "message": "LocalReplayRunner produced transcript and artifact receipts.",
            }
        )
        status = "completed"
        machine_score = 0.8
        error = None

    transcript_path.write_text("".join(json.dumps(event) + "\n" for event in events))

    artifact_bundle = {
        "run_id": request["run_id"],
        "agent_role": request["agent_role"],
        "scenario_set_id": request["scenario_set_id"],
        "status": status,
        "workspace_snapshot": request.get("workspace_snapshot", {}),
        "receipts": {
            "transcript_path": transcript_path.name,
            "result_path": result_path.name,
        },
    }
    if error:
        artifact_bundle["error"] = error
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    result = {
        "status": status,
        "transcript_path": transcript_path.name,
        "artifact_bundle_path": artifact_bundle_path.name,
        "machine_score": machine_score,
        "scorecard": {
            "runner": "LocalReplayRunner",
            "checks": [
                {
                    "name": "artifact_bundle_present",
                    "passed": True,
                },
                {
                    "name": "failure_is_honest",
                    "passed": bool(error),
                }
                if error
                else {
                    "name": "transcript_has_completion_event",
                    "passed": True,
                },
            ],
        },
    }
    if error:
        result["error"] = error
    result_path.write_text(json.dumps(result, indent=2))

    return 1 if error else 0


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
