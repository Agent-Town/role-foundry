from __future__ import annotations

import argparse
import json
import shlex
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from .bridge import ClawithRunClient, RunBridge
from .contract import ContractError, RunRequest

STAGE_ORDER = (
    ("baseline-eval", {"iteration": 1, "iteration_label": "baseline"}),
    ("candidate-student", {"iteration": 2, "iteration_label": "candidate-student"}),
    ("candidate-teacher-eval", {"iteration": 3, "iteration_label": "candidate"}),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Role Foundry autoresearch alpha loop"
    )
    parser.add_argument("--request", required=True, help="Path to the alpha-loop request JSON")
    parser.add_argument(
        "--artifacts-root",
        default="runtime/autoresearch-alpha",
        help="Directory where stage artifacts and the alpha receipt are written",
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
    backend_command = shlex.split(args.backend_command) if args.backend_command else None

    try:
        receipt = run_alpha_loop(
            request_path=Path(args.request),
            artifacts_root=Path(args.artifacts_root),
            clawith_url=args.clawith_url,
            clawith_secret=args.clawith_secret,
            backend_command=backend_command,
        )
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(receipt, indent=2))
    return 0 if receipt.get("ok") else 1


def run_alpha_loop(
    *,
    request_path: Path,
    artifacts_root: Path,
    clawith_url: str | None = None,
    clawith_secret: str = "",
    backend_command: list[str] | None = None,
) -> dict[str, Any]:
    config = _load_json(request_path)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    pack_path = _resolve_json_path(request_path, config, "public_benchmark_pack")
    registry_path = _resolve_json_path(request_path, config, "family_registry")
    benchmark_pack = _load_json(pack_path)
    family_registry = _load_json(registry_path)
    integrity_gate = _evaluate_integrity_gate(config, benchmark_pack, family_registry)
    if integrity_gate["status"] == "blocked":
        raise ContractError(integrity_gate["summary"])

    (artifacts_root / "autoresearch-alpha.request.json").write_text(json.dumps(config, indent=2))

    control_plane = ClawithRunClient(clawith_url, clawith_secret)
    bridge = RunBridge(
        artifacts_root=artifacts_root,
        control_plane=control_plane,
        backend_command=backend_command,
    )

    baseline_stage_config = _stage_config(config, "baseline-eval")
    baseline_request = baseline_stage_config["request"]
    baseline_result = bridge.run(RunRequest.from_dict(baseline_request))
    baseline_stage = _build_stage_receipt(
        stage_key="baseline-eval",
        stage_config=baseline_stage_config,
        request=baseline_request,
        result=baseline_result,
        artifacts_root=artifacts_root,
        baseline_run_id=None,
        candidate_student_run_id=None,
    )

    candidate_teacher_stage_config = _stage_config(config, "candidate-teacher-eval")
    candidate_student_stage_config = _stage_config(config, "candidate-student")
    candidate_student_request = _prepare_candidate_student_request(
        candidate_student_stage_config,
        candidate_teacher_stage_config,
        baseline_stage,
        benchmark_pack,
    )
    candidate_student_result = bridge.run(RunRequest.from_dict(candidate_student_request))
    candidate_student_stage = _build_stage_receipt(
        stage_key="candidate-student",
        stage_config=candidate_student_stage_config,
        request=candidate_student_request,
        result=candidate_student_result,
        artifacts_root=artifacts_root,
        baseline_run_id=baseline_stage["run_id"],
        candidate_student_run_id=None,
    )

    candidate_teacher_request = _prepare_candidate_teacher_request(
        candidate_teacher_stage_config,
        baseline_stage,
    )
    candidate_teacher_result = bridge.run(RunRequest.from_dict(candidate_teacher_request))
    candidate_teacher_stage = _build_stage_receipt(
        stage_key="candidate-teacher-eval",
        stage_config=candidate_teacher_stage_config,
        request=candidate_teacher_request,
        result=candidate_teacher_result,
        artifacts_root=artifacts_root,
        baseline_run_id=baseline_stage["run_id"],
        candidate_student_run_id=candidate_student_stage["run_id"],
    )

    comparison = _build_comparison(
        baseline_stage=baseline_stage,
        candidate_stage=candidate_teacher_stage,
        comparison_policy=config.get("comparison_policy") if isinstance(config.get("comparison_policy"), dict) else {},
        integrity_gate=integrity_gate,
    )
    artifact_coverage = _build_artifact_coverage(
        artifacts_root,
        {
            "baseline-eval": baseline_stage,
            "candidate-student": candidate_student_stage,
            "candidate-teacher-eval": candidate_teacher_stage,
        },
    )

    receipt = {
        "ok": all(
            stage.get("status") == "completed"
            for stage in (baseline_stage, candidate_student_stage, candidate_teacher_stage)
        )
        and comparison.get("complete", False),
        "flow": "autoresearch-alpha",
        "sequence_id": config.get("sequence_id") or f"{benchmark_pack.get('meta', {}).get('id', 'alpha')}:{artifacts_root.name}",
        "dataset_manifest_id": benchmark_pack.get("meta", {}).get("id"),
        "dataset_version": benchmark_pack.get("meta", {}).get("version"),
        "control_plane_mode": "runner-bridge-local-replay",
        "integrity_gate": integrity_gate,
        "stages": {
            "baseline-eval": baseline_stage,
            "candidate-student": candidate_student_stage,
            "candidate-teacher-eval": candidate_teacher_stage,
        },
        "comparison": comparison,
        "verdict": comparison.get("verdict"),
        "artifact_coverage": artifact_coverage,
        "outputs": {
            "request_copy_path": "autoresearch-alpha.request.json",
            "receipt_path": "autoresearch-alpha.json",
        },
    }
    (artifacts_root / "autoresearch-alpha.json").write_text(json.dumps(receipt, indent=2))
    return receipt


def _stage_config(config: dict[str, Any], stage_key: str) -> dict[str, Any]:
    stages = config.get("stages")
    if not isinstance(stages, dict) or not isinstance(stages.get(stage_key), dict):
        raise ContractError(f"missing stage config: {stage_key}")
    stage_config = deepcopy(stages[stage_key])
    request = stage_config.get("request")
    if not isinstance(request, dict):
        raise ContractError(f"stage {stage_key} is missing request payload")
    stage_config["request"] = deepcopy(request)
    return stage_config


def _prepare_candidate_student_request(
    stage_config: dict[str, Any],
    candidate_teacher_stage_config: dict[str, Any],
    baseline_stage: dict[str, Any],
    benchmark_pack: dict[str, Any],
) -> dict[str, Any]:
    request = deepcopy(stage_config["request"])
    teacher_eval = ((candidate_teacher_stage_config.get("request") or {}).get("teacher_evaluation")) or {}
    if not isinstance(teacher_eval, dict):
        raise ContractError("candidate-teacher-eval request must include teacher_evaluation")

    selected_episode_ids = stage_config.get("prompt_pack_episode_ids")
    if isinstance(selected_episode_ids, list) and selected_episode_ids:
        selected_set = {str(episode_id) for episode_id in selected_episode_ids}
        episodes = [
            episode
            for episode in benchmark_pack.get("episodes", [])
            if isinstance(episode, dict) and str(episode.get("id")) in selected_set
        ]
    else:
        episodes = [
            episode
            for episode in benchmark_pack.get("episodes", [])
            if isinstance(episode, dict)
        ]

    if not episodes:
        raise ContractError("candidate-student prompt pack did not resolve any benchmark episodes")

    baseline_themes = _extract_public_themes(baseline_stage)
    request["student_prompt_pack"] = {
        "actor": teacher_eval.get("student"),
        "sealed_holdout_count": _sealed_holdout_count(teacher_eval),
        "prompt_summary": stage_config.get("prompt_summary")
        or teacher_eval.get("student_prompt_summary")
        or benchmark_pack.get("meta", {}).get("honesty_note")
        or "Train on the public benchmark pack only. Teacher-only evaluation stays separate.",
        "visible_scenarios": [
            {
                "id": episode.get("id"),
                "title": episode.get("title") or episode.get("id"),
                "type": "training",
                "difficulty": episode.get("difficulty"),
                "student_prompt": episode.get("student_prompt") or "",
            }
            for episode in episodes
        ],
        "public_curriculum_themes": baseline_themes,
    }
    return request


def _prepare_candidate_teacher_request(
    stage_config: dict[str, Any],
    baseline_stage: dict[str, Any],
) -> dict[str, Any]:
    request = deepcopy(stage_config["request"])
    teacher_eval = request.get("teacher_evaluation")
    if not isinstance(teacher_eval, dict):
        raise ContractError("candidate-teacher-eval request must include teacher_evaluation")

    baseline_score = baseline_stage.get("aggregate_score")
    if not isinstance(baseline_score, dict):
        raise ContractError("baseline stage did not produce an aggregate score")

    teacher_eval["previous_iteration"] = {
        "run_id": baseline_stage["run_id"],
        "label": "baseline",
        "aggregate_score": baseline_score,
    }
    request["teacher_evaluation"] = teacher_eval
    return request


def _build_stage_receipt(
    *,
    stage_key: str,
    stage_config: dict[str, Any],
    request: dict[str, Any],
    result: dict[str, Any],
    artifacts_root: Path,
    baseline_run_id: str | None,
    candidate_student_run_id: str | None,
) -> dict[str, Any]:
    stage_meta = dict(STAGE_ORDER)[stage_key]
    run_id = str(request.get("run_id"))
    run_dir = artifacts_root / run_id
    artifact_bundle = _load_json(run_dir / "artifact-bundle.json")
    stored_result = _load_json(run_dir / "result.json")
    transcript_excerpt = _transcript_excerpt(run_dir / "transcript.ndjson")

    scorecard = stored_result.get("scorecard") if isinstance(stored_result.get("scorecard"), dict) else None
    aggregate_score = scorecard.get("aggregate_score") if isinstance(scorecard, dict) and isinstance(scorecard.get("aggregate_score"), dict) else None

    export_run = {
        "id": run_id,
        "label": stage_config.get("label") or stage_key,
        "status": result.get("status"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_sec": _duration_seconds(result.get("started_at"), result.get("finished_at")),
        "cost_usd": _extract_cost_usd(request),
        "runner": scorecard.get("runner") if isinstance(scorecard, dict) else "LocalReplayRunner",
        "iteration": stage_meta["iteration"],
        "stage_label": stage_meta["iteration_label"],
        "comparison_run_id": baseline_run_id if stage_key == "candidate-teacher-eval" else None,
    }

    export_result = deepcopy(stored_result)
    for path_key in ("transcript_path", "artifact_bundle_path"):
        if export_result.get(path_key):
            export_result[path_key] = _relative_to_root(artifacts_root, Path(export_result[path_key]))

    stage = {
        "run_id": run_id,
        "status": result.get("status"),
        "total_score": export_result.get("machine_score"),
        "aggregate_score": aggregate_score,
        "lineage": {
            "sequence_id": request.get("scenario_set_id"),
            "root_run_id": baseline_run_id or run_id,
            "parent_run_id": baseline_run_id if stage_key == "candidate-student" else candidate_student_run_id,
            "iteration_index": stage_meta["iteration"],
            "iteration_label": stage_meta["iteration_label"],
            **(
                {
                    "student_run_id": candidate_student_run_id,
                    "derived_previous_iteration_from": baseline_run_id,
                }
                if stage_key == "candidate-teacher-eval" and candidate_student_run_id and baseline_run_id
                else {}
            ),
        },
        "export": {
            "run": export_run,
            "result": export_result,
            "artifact_bundle": artifact_bundle,
            "transcript_excerpt": transcript_excerpt,
        },
    }
    return stage


def _build_comparison(
    *,
    baseline_stage: dict[str, Any],
    candidate_stage: dict[str, Any],
    comparison_policy: dict[str, Any],
    integrity_gate: dict[str, Any],
) -> dict[str, Any]:
    epsilon = float(comparison_policy.get("epsilon", 0.0001) or 0.0001)
    deciding_axis = comparison_policy.get("deciding_axis") or "machine_score"

    baseline_score = _comparison_score(baseline_stage, deciding_axis)
    candidate_score = _comparison_score(candidate_stage, deciding_axis)
    if baseline_score is None or candidate_score is None:
        raise ContractError("comparison requires scored baseline and candidate teacher-eval stages")

    delta = round(candidate_score - baseline_score, 4)
    if delta > epsilon:
        verdict = "better"
    elif delta < -epsilon:
        verdict = "worse"
    else:
        verdict = "equal"

    baseline_aggregate = baseline_stage.get("aggregate_score") or {}
    candidate_aggregate = candidate_stage.get("aggregate_score") or {}

    reasons = [
        f"Pass count moved {baseline_aggregate.get('passed', 0)}/{baseline_aggregate.get('total', 0)} → {candidate_aggregate.get('passed', 0)}/{candidate_aggregate.get('total', 0)}.",
        f"Holdout pass count moved {baseline_aggregate.get('holdout', {}).get('passed', 0)}/{baseline_aggregate.get('holdout', {}).get('total', 0)} → {candidate_aggregate.get('holdout', {}).get('passed', 0)}/{candidate_aggregate.get('holdout', {}).get('total', 0)}.",
    ]
    if integrity_gate.get("claims_blocked"):
        reasons.append(
            "Integrity gate still blocks sealed-eval claims until the blocked teacher-only families are rewritten outside the public repo."
        )

    return {
        "complete": True,
        "verdict": verdict,
        "deciding_axis": deciding_axis,
        "baseline_run_id": baseline_stage.get("run_id"),
        "candidate_run_id": candidate_stage.get("run_id"),
        "baseline_total_score": baseline_score,
        "candidate_total_score": candidate_score,
        "total_score_delta": delta,
        "category_deltas": {
            "pass_count": candidate_aggregate.get("passed", 0) - baseline_aggregate.get("passed", 0),
            "pass_rate": round(
                float(candidate_aggregate.get("pass_rate", 0.0) or 0.0)
                - float(baseline_aggregate.get("pass_rate", 0.0) or 0.0),
                4,
            ),
            "holdout_pass_count": candidate_aggregate.get("holdout", {}).get("passed", 0)
            - baseline_aggregate.get("holdout", {}).get("passed", 0),
            "holdout_pass_rate": round(
                float(candidate_aggregate.get("holdout", {}).get("pass_rate", 0.0) or 0.0)
                - float(baseline_aggregate.get("holdout", {}).get("pass_rate", 0.0) or 0.0),
                4,
            ),
        },
        "reasons": reasons,
    }


def _build_artifact_coverage(
    artifacts_root: Path,
    stages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    coverage = {}
    for stage_key, stage in stages.items():
        run_dir = artifacts_root / stage["run_id"]
        required_paths = {
            "request.json": run_dir / "request.json",
            "request.private.json": run_dir / "request.private.json",
            "transcript.ndjson": run_dir / "transcript.ndjson",
            "artifact-bundle.json": run_dir / "artifact-bundle.json",
            "result.json": run_dir / "result.json",
            "receipts/manifest.json": run_dir / "receipts" / "manifest.json",
            "receipts/candidate.json": run_dir / "receipts" / "candidate.json",
        }
        if stage_key != "candidate-student":
            required_paths["receipts/evaluation.json"] = run_dir / "receipts" / "evaluation.json"
        if stage_key == "candidate-teacher-eval":
            required_paths["receipts/baseline.json"] = run_dir / "receipts" / "baseline.json"

        artifact_bundle = _load_json(run_dir / "artifact-bundle.json")
        result = _load_json(run_dir / "result.json")
        checks = {
            name: path.exists() for name, path in required_paths.items()
        }
        checks["artifact_bundle_has_student_view"] = isinstance(artifact_bundle.get("student_view"), dict)
        checks["teacher_verdict_present"] = bool((result.get("scorecard") or {}).get("verdict"))
        if stage_key == "candidate-student":
            checks["teacher_verdict_present"] = False

        coverage[stage_key] = {
            "run_id": stage["run_id"],
            "complete": all(checks.values()) if stage_key != "candidate-student" else all(
                value for key, value in checks.items() if key != "teacher_verdict_present"
            ),
            "checks": checks,
            "paths": {
                name: path.relative_to(artifacts_root).as_posix() for name, path in required_paths.items()
            },
        }

    return coverage


def _evaluate_integrity_gate(
    config: dict[str, Any],
    benchmark_pack: dict[str, Any],
    family_registry: dict[str, Any],
) -> dict[str, Any]:
    policy = config.get("integrity_policy") if isinstance(config.get("integrity_policy"), dict) else {}
    require_sealed_holdout = bool(policy.get("require_sealed_holdout"))
    blocked_ids = [str(family_id) for family_id in benchmark_pack.get("blocked_family_ids", [])]
    families_by_id = {
        str(family.get("id")): family
        for family in family_registry.get("families", [])
        if isinstance(family, dict) and family.get("id")
    }
    blocked_reasons = [
        families_by_id[family_id].get("blocked_reason") or f"Blocked family: {family_id}"
        for family_id in blocked_ids
        if family_id in families_by_id
    ]

    sealed_eval_claim_ok = not blocked_ids
    public_regression_ok = bool(benchmark_pack.get("execution_policy", {}).get("student_visible_only"))
    claims_blocked = []
    if not sealed_eval_claim_ok:
        claims_blocked.extend(
            [
                "sealed certification",
                "fresh hidden holdout integrity claims",
            ]
        )

    summary = (
        "Integrity gate passed for a public-regression alpha loop; sealed-eval claims remain blocked pending teacher-only family rewrite."
        if public_regression_ok and not require_sealed_holdout
        else "Integrity gate blocked: a truly sealed holdout path does not exist yet. Rewrite the blocked teacher-only families outside the public repo first."
    )

    return {
        "status": "blocked" if require_sealed_holdout and not sealed_eval_claim_ok else "pass",
        "mode": "public_regression",
        "summary": summary,
        "public_regression_ok": public_regression_ok,
        "sealed_eval_claim_ok": sealed_eval_claim_ok,
        "require_sealed_holdout": require_sealed_holdout,
        "dataset_manifest_id": benchmark_pack.get("meta", {}).get("id"),
        "dataset_version": benchmark_pack.get("meta", {}).get("version"),
        "blocked_family_ids": blocked_ids,
        "blocked_reasons": blocked_reasons,
        "claims_allowed": [
            "public better/equal/worse comparison",
            "artifact-complete baseline → candidate → teacher-eval receipts",
            "public curriculum prompt-pack execution",
        ],
        "claims_blocked": claims_blocked,
    }


def _extract_public_themes(stage: dict[str, Any]) -> list[dict[str, Any]]:
    result_scorecard = ((stage.get("export") or {}).get("result") or {}).get("scorecard") or {}
    themes = result_scorecard.get("public_curriculum_themes")
    if isinstance(themes, list):
        return deepcopy(themes)

    artifact_bundle = ((stage.get("export") or {}).get("artifact_bundle")) or {}
    themes = artifact_bundle.get("public_curriculum_themes")
    if isinstance(themes, list):
        return deepcopy(themes)
    return []


def _comparison_score(stage: dict[str, Any], deciding_axis: str) -> float | None:
    if deciding_axis == "machine_score":
        score = stage.get("total_score")
        return float(score) if isinstance(score, (int, float)) else None

    aggregate = stage.get("aggregate_score") or {}
    score = aggregate.get(deciding_axis)
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _duration_seconds(started_at: Any, finished_at: Any) -> int | None:
    from datetime import datetime

    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        finished = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds()))


def _extract_cost_usd(request: dict[str, Any]) -> float | None:
    budget = request.get("cost_budget")
    if isinstance(budget, dict) and isinstance(budget.get("usd"), (int, float)):
        return float(budget["usd"])
    return None


def _sealed_holdout_count(teacher_eval: dict[str, Any]) -> int:
    return len(
        [
            scenario
            for scenario in teacher_eval.get("scenarios", [])
            if isinstance(scenario, dict) and scenario.get("type") == "holdout"
        ]
    )


def _transcript_excerpt(path: Path, limit: int = 4) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = []
    for raw_line in path.read_text().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        payload = json.loads(raw_line)
        if isinstance(payload, dict):
            lines.append(payload)
    if len(lines) <= limit:
        return lines
    return [*lines[:2], *lines[-2:]]


def _relative_to_root(root: Path, path: Path) -> str:
    path = path.resolve()
    root = root.resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_json_path(request_path: Path, config: dict[str, Any], key: str) -> Path:
    raw = config.get(key)
    if not raw:
        raise ContractError(f"missing {key} in alpha-loop request")
    path = Path(str(raw))
    if not path.is_absolute():
        path = (request_path.parent / path).resolve()
    return path


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ContractError(f"expected JSON object at {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
