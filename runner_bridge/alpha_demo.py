from __future__ import annotations

import argparse
import json
from contextlib import nullcontext
from copy import deepcopy
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
        "--flow",
        choices=["baseline-candidate", "request"],
        default="baseline-candidate",
        help="Run either the default two-run iteration slice or one named canonical request",
    )
    parser.add_argument(
        "--request-name",
        choices=["first_live_run", "teacher_eval_baseline", "teacher_eval_loop"],
        default="teacher_eval_loop",
        help="Which canonical request export to execute when --flow=request",
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
    artifacts_root = Path(args.artifacts_root)
    pack = load_pack(args.pack)
    pack_manifest = manifest(pack)
    seed_payload = export_seed_payload(pack)

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

        bridge = RunBridge(
            artifacts_root=artifacts_root,
            control_plane=client,
            backend_command=list(BACKEND_COMMANDS[args.backend]),
        )

        if args.flow == "request":
            run_summary = _execute_request(
                bridge=bridge,
                client=client,
                request_payload=export_request(pack, args.request_name),
                request_name=args.request_name,
                pack_manifest=pack_manifest,
                artifacts_root=artifacts_root,
                flow_name=args.flow,
                register_run=not args.skip_register,
                control_plane_mode=control_plane_mode,
                control_plane_url=control_plane_url,
            )
            summary = {
                "ok": run_summary["result"].get("status") == "completed",
                "flow": args.flow,
                "dataset_manifest_id": pack_manifest.get("id"),
                "control_plane_mode": control_plane_mode,
                "control_plane_url": control_plane_url,
                "request_name": args.request_name,
                "run_id": run_summary["run_id"],
                "status_history": run_summary["status_history"],
                "lineage": run_summary.get("lineage"),
                "artifact_bundle_path": run_summary["result"].get("artifact_bundle_path"),
                "transcript_path": run_summary["result"].get("transcript_path"),
                "control_plane_summary_path": run_summary["control_plane_summary_path"],
            }
        else:
            summary = _execute_baseline_candidate_flow(
                bridge=bridge,
                client=client,
                pack=pack,
                pack_manifest=pack_manifest,
                artifacts_root=artifacts_root,
                control_plane_mode=control_plane_mode,
                control_plane_url=control_plane_url,
                register_run=not args.skip_register,
            )

    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


def _execute_baseline_candidate_flow(
    *,
    bridge: RunBridge,
    client: ClawithRunClient,
    pack: dict[str, Any],
    pack_manifest: dict[str, Any],
    artifacts_root: Path,
    control_plane_mode: str,
    control_plane_url: str,
    register_run: bool,
) -> dict[str, Any]:
    baseline_request = export_request(pack, "teacher_eval_baseline")
    sequence_id = f"{pack_manifest.get('id')}:baseline-candidate"
    baseline_lineage = {
        "sequence_id": sequence_id,
        "root_run_id": baseline_request["run_id"],
        "parent_run_id": None,
        "iteration_index": 1,
        "iteration_label": "baseline",
    }
    baseline_summary = _execute_request(
        bridge=bridge,
        client=client,
        request_payload=baseline_request,
        request_name="teacher_eval_baseline",
        pack_manifest=pack_manifest,
        artifacts_root=artifacts_root,
        flow_name="baseline-candidate",
        register_run=register_run,
        lineage=baseline_lineage,
        control_plane_mode=control_plane_mode,
        control_plane_url=control_plane_url,
    )

    baseline_aggregate = baseline_summary["result"].get("scorecard", {}).get("aggregate_score", {})
    candidate_request = export_request(pack, "teacher_eval_loop")
    candidate_lineage = {
        "sequence_id": sequence_id,
        "root_run_id": baseline_summary["run_id"],
        "parent_run_id": baseline_summary["run_id"],
        "iteration_index": 2,
        "iteration_label": "candidate",
        "derived_previous_iteration_from": baseline_summary["run_id"],
    }
    evaluation = candidate_request.setdefault("teacher_evaluation", {})
    evaluation["previous_iteration"] = {
        "run_id": baseline_summary["run_id"],
        "label": baseline_lineage["iteration_label"],
        "index": baseline_lineage["iteration_index"],
        "aggregate_score": baseline_aggregate,
    }
    candidate_summary = _execute_request(
        bridge=bridge,
        client=client,
        request_payload=candidate_request,
        request_name="teacher_eval_loop",
        pack_manifest=pack_manifest,
        artifacts_root=artifacts_root,
        flow_name="baseline-candidate",
        register_run=register_run,
        lineage=candidate_lineage,
        control_plane_mode=control_plane_mode,
        control_plane_url=control_plane_url,
    )

    sequence_summary_path = artifacts_root / "baseline-candidate-summary.json"
    sequence_summary = {
        "ok": baseline_summary["result"].get("status") == "completed"
        and candidate_summary["result"].get("status") == "completed",
        "flow": "baseline-candidate",
        "sequence_id": sequence_id,
        "dataset_manifest_id": pack_manifest.get("id"),
        "dataset_version": pack_manifest.get("version"),
        "control_plane_mode": control_plane_mode,
        "control_plane_url": control_plane_url,
        "run_ids": [baseline_summary["run_id"], candidate_summary["run_id"]],
        "runs": [
            _public_run_summary(baseline_summary),
            _public_run_summary(candidate_summary),
        ],
        "iteration_history": candidate_summary["result"].get("scorecard", {}).get("iteration_history", []),
        "artifacts": {
            "sequence_summary_path": str(sequence_summary_path),
            "baseline_run_dir": str(baseline_summary["run_dir"]),
            "candidate_run_dir": str(candidate_summary["run_dir"]),
        },
    }
    sequence_summary_path.write_text(json.dumps(sequence_summary, indent=2) + "\n")
    sequence_summary["sequence_summary_path"] = str(sequence_summary_path)
    return sequence_summary


def _execute_request(
    *,
    bridge: RunBridge,
    client: ClawithRunClient,
    request_payload: dict[str, Any],
    request_name: str,
    pack_manifest: dict[str, Any],
    artifacts_root: Path,
    flow_name: str,
    register_run: bool,
    control_plane_mode: str,
    control_plane_url: str,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = deepcopy(request_payload)
    if lineage:
        payload["lineage"] = lineage
        _apply_iteration_metadata(payload, lineage)

    if register_run:
        client.create_run(
            {
                "run_id": payload["run_id"],
                "status": "queued",
                "agent_role": payload["agent_role"],
                "scenario_set_id": payload["scenario_set_id"],
                "dataset_manifest_id": pack_manifest.get("id"),
                "dataset_version": pack_manifest.get("version"),
                "request_name": request_name,
                "flow": flow_name,
                "created_by": "runner_bridge.alpha_demo",
                "created_at": _utc_now(),
                "lineage": lineage,
            }
        )

    result = bridge.run(RunRequest.from_dict(payload))
    run_record = client.get_run(payload["run_id"]) if client.base_url else {}
    run_dir = artifacts_root / payload["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset_manifest_path = run_dir / "dataset-manifest.json"
    manifest_receipt = {
        "dataset_manifest_id": pack_manifest.get("id"),
        "dataset_version": pack_manifest.get("version"),
        "pack_request_name": request_name,
        "flow": flow_name,
        "scenario_set_id": pack_manifest.get("scenario_set_id"),
        "scenario_counts": pack_manifest.get("scenario_counts", {}),
        "student_artifact_policy": pack_manifest.get("student_artifact_policy"),
        "lineage": lineage,
    }
    dataset_manifest_path.write_text(json.dumps(manifest_receipt, indent=2) + "\n")

    control_plane_summary_path = run_dir / "control-plane-summary.json"
    status_history = [entry.get("status") for entry in run_record.get("state_history", [])]
    control_plane_summary = {
        "mode": control_plane_mode if client.base_url else "disabled",
        "base_url": control_plane_url if client.base_url else None,
        "dataset_manifest_id": pack_manifest.get("id"),
        "request_name": request_name,
        "flow": flow_name,
        "run_id": payload["run_id"],
        "lineage": run_record.get("lineage") or lineage,
        "status_history": status_history,
        "run_record": run_record,
        "artifact_groups": _artifact_groups(run_dir, result),
    }
    control_plane_summary_path.write_text(json.dumps(control_plane_summary, indent=2) + "\n")

    return {
        "run_id": payload["run_id"],
        "request_name": request_name,
        "run_dir": run_dir,
        "lineage": run_record.get("lineage") or lineage,
        "status_history": status_history,
        "result": result,
        "run_record": run_record,
        "control_plane_summary_path": str(control_plane_summary_path),
    }


def _public_run_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": summary["run_id"],
        "request_name": summary["request_name"],
        "lineage": summary.get("lineage"),
        "status_history": summary.get("status_history", []),
        "aggregate_score": summary.get("result", {}).get("scorecard", {}).get("aggregate_score"),
        "control_plane_summary_path": summary.get("control_plane_summary_path"),
        "artifact_groups": _artifact_groups(summary["run_dir"], summary["result"]),
    }


def _artifact_groups(run_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "student_safe": {
            "request_path": _path_if_exists(run_dir / "request.json"),
            "student_view_path": _path_if_exists(run_dir / "student-view.json"),
        },
        "judge_safe": {
            "transcript_path": result.get("transcript_path"),
            "artifact_bundle_path": result.get("artifact_bundle_path"),
            "teacher_scorecard_path": _path_if_exists(run_dir / "teacher-scorecard.json"),
            "result_path": _path_if_exists(run_dir / "result.json"),
            "dataset_manifest_path": _path_if_exists(run_dir / "dataset-manifest.json"),
        },
        "teacher_private": {
            "request_private_path": _path_if_exists(run_dir / "request.private.json"),
            "stdout_path": _path_if_exists(run_dir / "stdout.log"),
            "stderr_path": _path_if_exists(run_dir / "stderr.log"),
        },
    }


def _path_if_exists(path: Path) -> str | None:
    return str(path) if path.exists() else None


def _apply_iteration_metadata(payload: dict[str, Any], lineage: dict[str, Any]) -> None:
    evaluation = payload.get("teacher_evaluation")
    if not isinstance(evaluation, dict):
        return
    iteration = evaluation.get("iteration")
    iteration = dict(iteration) if isinstance(iteration, dict) else {}
    if lineage.get("iteration_index") is not None:
        iteration.setdefault("index", lineage["iteration_index"])
    if lineage.get("iteration_label"):
        iteration.setdefault("label", lineage["iteration_label"])
    if lineage.get("sequence_id"):
        iteration.setdefault("sequence_id", lineage["sequence_id"])
    if lineage.get("parent_run_id"):
        iteration.setdefault("parent_run_id", lineage["parent_run_id"])
    if iteration:
        evaluation["iteration"] = iteration


def _seed_control_plane(client: ClawithRunClient, seed_payload: dict[str, Any]) -> None:
    client.post_json("/api/roles", seed_payload["role"])
    for scenario in seed_payload["scenarios"]:
        client.post_json("/api/scenarios", scenario)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
