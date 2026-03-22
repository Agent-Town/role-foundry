from __future__ import annotations

import argparse
import json
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bridge import ClawithRunClient, RunBridge
from .cli import BACKEND_COMMANDS
from .contract import RunRequest
from .control_plane_shim import start_shim_server
from .dataset_pack import (
    DEFAULT_PACK_PATH,
    check_holdout_exclusion,
    export_request,
    export_seed_payload,
    load_pack,
    manifest,
    validate_seed_payload,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Frontend Apprentice alpha path against a Clawith-compatible seam")
    parser.add_argument("--pack", default=str(DEFAULT_PACK_PATH), help="Canonical dataset pack to use")
    parser.add_argument(
        "--request-name",
        choices=["first_live_run", "teacher_eval_loop"],
        default="teacher_eval_loop",
        help="Which canonical request export to execute",
    )
    parser.add_argument(
        "--artifacts-root",
        default="runtime/alpha-runs",
        help="Where to write bridge artifacts",
    )
    parser.add_argument(
        "--data-dir",
        default="runtime/control-plane-shim",
        help="Where the bundled control-plane shim should persist state",
    )
    parser.add_argument(
        "--backend",
        choices=sorted(BACKEND_COMMANDS),
        default="local-replay",
        help="Runner backend to execute for the alpha demo",
    )
    parser.add_argument("--clawith-url", help="Optional external Clawith-compatible base URL. If omitted, a local shim is started.")
    parser.add_argument("--clawith-secret", default="alpha-secret", help="Machine-to-machine bridge secret")
    parser.add_argument("--skip-seed", action="store_true", help="Skip POSTing the role/scenario seed payload")
    parser.add_argument("--skip-register", action="store_true", help="Skip creating the queued run record before bridge execution")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pack = load_pack(args.pack)
    pack_manifest = manifest(pack)
    seed_payload = export_seed_payload(pack)
    request_payload = export_request(pack, args.request_name)

    errors = validate_seed_payload(seed_payload)
    if errors:
        raise SystemExit("\n".join(errors))

    leaked = check_holdout_exclusion(seed_payload)
    if leaked:
        raise SystemExit(f"holdout titles leaked into student payload: {leaked}")

    if args.clawith_url:
        shim_context = nullcontext(None)
        control_plane_url = args.clawith_url.rstrip("/")
        control_plane_mode = "external-clawith-compatible-endpoint"
    else:
        shim_context = start_shim_server(args.data_dir, port=0, secret=args.clawith_secret)
        control_plane_url = shim_context.base_url
        control_plane_mode = "bundled-clawith-compatible-shim"

    with shim_context:
        client = ClawithRunClient(control_plane_url, args.clawith_secret)

        if not args.skip_seed:
            _seed_control_plane(client, seed_payload)

        if not args.skip_register:
            client.create_run(
                {
                    "run_id": request_payload["run_id"],
                    "status": "queued",
                    "agent_role": request_payload["agent_role"],
                    "scenario_set_id": request_payload["scenario_set_id"],
                    "dataset_manifest_id": pack_manifest.get("id"),
                    "dataset_version": pack_manifest.get("version"),
                    "request_name": args.request_name,
                    "created_by": "runner_bridge.alpha_demo",
                    "created_at": _utc_now(),
                }
            )

        bridge = RunBridge(
            artifacts_root=Path(args.artifacts_root),
            control_plane=client,
            backend_command=list(BACKEND_COMMANDS[args.backend]),
        )
        result = bridge.run(RunRequest.from_dict(request_payload))
        run_record = client.get_run(request_payload["run_id"])

    run_dir = Path(args.artifacts_root) / request_payload["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_receipt = {
        "dataset_manifest_id": pack_manifest.get("id"),
        "dataset_version": pack_manifest.get("version"),
        "pack_path": str(Path(args.pack)),
        "request_name": args.request_name,
        "scenario_counts": pack_manifest.get("scenario_counts", {}),
        "student_artifact_policy": pack_manifest.get("student_artifact_policy"),
    }
    (run_dir / "dataset-manifest.json").write_text(json.dumps(manifest_receipt, indent=2) + "\n")

    control_plane_summary = {
        "mode": control_plane_mode,
        "base_url": control_plane_url,
        "dataset_manifest_id": pack_manifest.get("id"),
        "request_name": args.request_name,
        "run_id": request_payload["run_id"],
        "status_history": [entry.get("status") for entry in run_record.get("state_history", [])],
        "run_record": run_record,
        "artifacts": {
            "run_dir": str(run_dir),
            "transcript_path": result.get("transcript_path"),
            "artifact_bundle_path": result.get("artifact_bundle_path"),
            "dataset_manifest_path": str(run_dir / "dataset-manifest.json"),
        },
    }
    (run_dir / "control-plane-summary.json").write_text(json.dumps(control_plane_summary, indent=2) + "\n")

    summary = {
        "ok": result.get("status") == "completed",
        "dataset_manifest_id": pack_manifest.get("id"),
        "request_name": args.request_name,
        "control_plane_mode": control_plane_mode,
        "control_plane_url": control_plane_url,
        "run_id": request_payload["run_id"],
        "status_history": control_plane_summary["status_history"],
        "artifact_bundle_path": result.get("artifact_bundle_path"),
        "transcript_path": result.get("transcript_path"),
        "control_plane_summary_path": str(run_dir / "control-plane-summary.json"),
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


def _seed_control_plane(client: ClawithRunClient, seed_payload: dict[str, Any]) -> None:
    client.post_json("/api/roles", seed_payload["role"])
    for scenario in seed_payload["scenarios"]:
        client.post_json("/api/scenarios", scenario)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
