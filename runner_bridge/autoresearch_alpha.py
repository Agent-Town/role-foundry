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

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_HOLDOUT_DIR = ROOT / "benchmarks" / "private-holdout-pack"
PRIVATE_HOLDOUT_REQUIRED_KEYS = {
    "id",
    "family_id",
    "title",
    "teacher_prompt",
    "scoring_rubric",
    "difficulty",
}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


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
    private_holdout_pack = _load_private_holdout_pack(
        request_path,
        config,
        blocked_family_ids=benchmark_pack.get("blocked_family_ids", []),
    )
    integrity_gate = _evaluate_integrity_gate(
        config,
        benchmark_pack,
        family_registry,
        private_holdout_pack=private_holdout_pack,
    )
    if integrity_gate["status"] == "blocked":
        raise ContractError(integrity_gate["summary"])

    (artifacts_root / "autoresearch-alpha.request.json").write_text(json.dumps(config, indent=2))

    control_plane = ClawithRunClient(clawith_url, clawith_secret)
    bridge = RunBridge(
        artifacts_root=artifacts_root,
        control_plane=control_plane,
        backend_command=backend_command,
    )

    execution_policy = benchmark_pack.get("execution_policy") or {}
    loop_verifier_commands = execution_policy.get("recommended_verifier_commands")
    if not isinstance(loop_verifier_commands, list) or not loop_verifier_commands:
        loop_verifier_commands = None

    pack_meta = benchmark_pack.get("meta") if isinstance(benchmark_pack.get("meta"), dict) else {}
    loop_sequence_id = config.get("sequence_id") or f"{pack_meta.get('id', 'alpha')}:{artifacts_root.name}"

    baseline_stage_config = _stage_config(config, "baseline-eval")
    baseline_request = _prepare_teacher_stage_request(
        stage_key="baseline-eval",
        stage_config=baseline_stage_config,
        benchmark_pack=benchmark_pack,
        loop_sequence_id=loop_sequence_id,
        private_holdout_pack=private_holdout_pack,
    )
    baseline_result = bridge.run(RunRequest.from_dict(baseline_request))
    _patch_provenance_receipt_verifier_gates(
        artifacts_root / str(baseline_request.get("run_id")),
        loop_verifier_commands,
        "LocalReplayRunner",
    )
    baseline_stage = _build_stage_receipt(
        stage_key="baseline-eval",
        stage_config=baseline_stage_config,
        request=baseline_request,
        result=baseline_result,
        artifacts_root=artifacts_root,
        baseline_run_id=None,
        candidate_student_run_id=None,
        verifier_commands_override=loop_verifier_commands,
        loop_sequence_id=loop_sequence_id,
        benchmark_pack_meta=pack_meta,
    )

    candidate_teacher_stage_config = _stage_config(config, "candidate-teacher-eval")
    candidate_student_stage_config = _stage_config(config, "candidate-student")
    candidate_student_request = _prepare_candidate_student_request(
        candidate_student_stage_config,
        candidate_teacher_stage_config,
        baseline_stage,
        benchmark_pack,
        loop_sequence_id=loop_sequence_id,
    )
    candidate_student_result = bridge.run(RunRequest.from_dict(candidate_student_request))
    _patch_provenance_receipt_verifier_gates(
        artifacts_root / str(candidate_student_request.get("run_id")),
        loop_verifier_commands,
        "LocalReplayRunner",
    )
    candidate_student_stage = _build_stage_receipt(
        stage_key="candidate-student",
        stage_config=candidate_student_stage_config,
        request=candidate_student_request,
        result=candidate_student_result,
        artifacts_root=artifacts_root,
        baseline_run_id=baseline_stage["run_id"],
        candidate_student_run_id=None,
        verifier_commands_override=loop_verifier_commands,
        loop_sequence_id=loop_sequence_id,
        benchmark_pack_meta=pack_meta,
    )

    candidate_teacher_request = _prepare_teacher_stage_request(
        stage_key="candidate-teacher-eval",
        stage_config=candidate_teacher_stage_config,
        benchmark_pack=benchmark_pack,
        loop_sequence_id=loop_sequence_id,
        baseline_stage=baseline_stage,
        private_holdout_pack=private_holdout_pack,
    )
    candidate_teacher_result = bridge.run(RunRequest.from_dict(candidate_teacher_request))
    _patch_provenance_receipt_verifier_gates(
        artifacts_root / str(candidate_teacher_request.get("run_id")),
        loop_verifier_commands,
        "LocalReplayRunner",
    )
    candidate_teacher_stage = _build_stage_receipt(
        stage_key="candidate-teacher-eval",
        stage_config=candidate_teacher_stage_config,
        request=candidate_teacher_request,
        result=candidate_teacher_result,
        artifacts_root=artifacts_root,
        baseline_run_id=baseline_stage["run_id"],
        candidate_student_run_id=candidate_student_stage["run_id"],
        verifier_commands_override=loop_verifier_commands,
        loop_sequence_id=loop_sequence_id,
        benchmark_pack_meta=pack_meta,
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

    verifier_gate_summary = _build_verifier_gate_summary({
        "baseline-eval": baseline_stage,
        "candidate-student": candidate_student_stage,
        "candidate-teacher-eval": candidate_teacher_stage,
    })

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
        "verifier_gate": verifier_gate_summary,
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
    *,
    loop_sequence_id: str,
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
    visible_scenarios = []
    for episode in episodes:
        scenario = {
            "id": episode.get("id"),
            "title": episode.get("title") or episode.get("id"),
            "type": "training",
            "difficulty": episode.get("difficulty"),
            "student_prompt": episode.get("student_prompt") or "",
        }
        repo_task_meta = _extract_repo_task_meta(episode)
        if repo_task_meta:
            scenario["repo_task_meta"] = repo_task_meta
        visible_scenarios.append(scenario)

    pack_meta = benchmark_pack.get("meta") or {}
    execution_policy = benchmark_pack.get("execution_policy") or {}
    repo_task_pack: dict[str, Any] = {
        "role_scope": pack_meta.get("role_scope") or pack_meta.get("role") or "unknown",
        "dataset_id": pack_meta.get("id"),
        "dataset_version": pack_meta.get("version"),
        "episode_count": len(visible_scenarios),
        "episode_ids": [scenario.get("id") for scenario in visible_scenarios if scenario.get("id")],
        "family_ids": sorted({episode.get("family_id") for episode in episodes if episode.get("family_id")}),
        "honesty_note": "Repo-task metadata is derived from the public benchmark pack. "
        "This is still local replay / public-regression alpha unless a private holdout manifest is used.",
    }
    recommended_verifier_commands = execution_policy.get("recommended_verifier_commands")
    if isinstance(recommended_verifier_commands, list) and recommended_verifier_commands:
        repo_task_pack["recommended_verifier_commands"] = list(recommended_verifier_commands)

    request["student_prompt_pack"] = {
        "actor": teacher_eval.get("student"),
        "sealed_holdout_count": _sealed_holdout_count(teacher_eval),
        "prompt_summary": stage_config.get("prompt_summary")
        or teacher_eval.get("student_prompt_summary")
        or benchmark_pack.get("meta", {}).get("honesty_note")
        or "Train on the public benchmark pack only. Teacher-only evaluation stays separate.",
        "visible_scenarios": visible_scenarios,
        "public_curriculum_themes": baseline_themes,
        "repo_task_pack": repo_task_pack,
    }
    _apply_stage_traceability(
        request,
        stage_key="candidate-student",
        loop_sequence_id=loop_sequence_id,
        benchmark_pack=benchmark_pack,
        visible_episodes=episodes,
        sealed_holdout_count=_sealed_holdout_count(teacher_eval),
    )
    return request


def _prepare_teacher_stage_request(
    *,
    stage_key: str,
    stage_config: dict[str, Any],
    benchmark_pack: dict[str, Any],
    loop_sequence_id: str,
    baseline_stage: dict[str, Any] | None = None,
    private_holdout_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = deepcopy(stage_config["request"])
    teacher_eval = request.get("teacher_evaluation")
    if not isinstance(teacher_eval, dict):
        raise ContractError(f"{stage_key} request must include teacher_evaluation")

    teacher_eval["scenarios"] = _hydrate_teacher_scenarios(
        teacher_eval.get("scenarios"),
        private_holdout_pack=private_holdout_pack,
    )

    if baseline_stage is not None:
        baseline_score = baseline_stage.get("aggregate_score")
        if not isinstance(baseline_score, dict):
            raise ContractError("baseline stage did not produce an aggregate score")
        teacher_eval["previous_iteration"] = {
            "run_id": baseline_stage["run_id"],
            "label": "baseline",
            "aggregate_score": baseline_score,
        }

    request["teacher_evaluation"] = teacher_eval
    _apply_stage_traceability(
        request,
        stage_key=stage_key,
        loop_sequence_id=loop_sequence_id,
        benchmark_pack=benchmark_pack,
        teacher_scenarios=teacher_eval.get("scenarios") if isinstance(teacher_eval.get("scenarios"), list) else [],
    )
    return request


def _apply_stage_traceability(
    request: dict[str, Any],
    *,
    stage_key: str,
    loop_sequence_id: str,
    benchmark_pack: dict[str, Any],
    visible_episodes: list[dict[str, Any]] | None = None,
    teacher_scenarios: list[dict[str, Any]] | None = None,
    sealed_holdout_count: int | None = None,
) -> None:
    pack_meta = benchmark_pack.get("meta") if isinstance(benchmark_pack.get("meta"), dict) else {}
    episodes: dict[str, Any] = {}
    visible_episodes = visible_episodes if isinstance(visible_episodes, list) else []
    teacher_scenarios = teacher_scenarios if isinstance(teacher_scenarios, list) else []

    if visible_episodes:
        episodes["visible_episode_ids"] = [
            episode.get("id") for episode in visible_episodes if isinstance(episode, dict) and episode.get("id")
        ]
        family_ids = sorted(
            {
                episode.get("family_id")
                for episode in visible_episodes
                if isinstance(episode, dict) and episode.get("family_id")
            }
        )
        if family_ids:
            episodes["family_ids"] = family_ids

    if teacher_scenarios:
        training_episode_ids = [
            scenario.get("id")
            for scenario in teacher_scenarios
            if isinstance(scenario, dict) and scenario.get("type") != "holdout" and scenario.get("id")
        ]
        if training_episode_ids:
            episodes["training_episode_ids"] = training_episode_ids
        holdout_total = len(
            [scenario for scenario in teacher_scenarios if isinstance(scenario, dict) and scenario.get("type") == "holdout"]
        )
        if holdout_total:
            episodes["holdout_count"] = holdout_total
            episodes["holdout_episode_ids"] = {
                "status": "withheld",
                "honesty_note": "Teacher-side holdout episode ids are intentionally withheld from student-facing traceability exports.",
            }

    if sealed_holdout_count is not None:
        episodes["sealed_holdout_count"] = int(sealed_holdout_count)

    request["traceability"] = {
        "sequence_id": loop_sequence_id,
        "stage_key": stage_key,
        "benchmark_pack": {
            "id": pack_meta.get("id"),
            "version": pack_meta.get("version"),
            "role_scope": pack_meta.get("role_scope") or pack_meta.get("role"),
        },
        "episodes": episodes,
    }


def _hydrate_teacher_scenarios(
    scenarios: Any,
    *,
    private_holdout_pack: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(scenarios, list):
        raise ContractError("teacher_evaluation.scenarios must be a list")

    hydrated = []
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ContractError(f"teacher_evaluation.scenarios[{index}] must be an object")
        hydrated.append(
            _hydrate_teacher_scenario(
                scenario,
                private_holdout_pack=private_holdout_pack,
            )
        )
    return hydrated


def _hydrate_teacher_scenario(
    scenario: dict[str, Any],
    *,
    private_holdout_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    scenario_type = scenario.get("type")
    if scenario_type != "holdout":
        return deepcopy(scenario)

    holdout_ref = _private_holdout_reference_id(scenario)
    if private_holdout_pack and holdout_ref and holdout_ref in private_holdout_pack["episodes_by_id"]:
        episode = private_holdout_pack["episodes_by_id"][holdout_ref]
        hydrated = deepcopy(scenario)
        hydrated["id"] = episode.get("id")
        hydrated["family_id"] = episode.get("family_id")
        hydrated["title"] = episode.get("title")
        hydrated["type"] = "holdout"
        hydrated["difficulty"] = episode.get("difficulty")
        hydrated["teacher_prompt"] = episode.get("teacher_prompt")
        hydrated["scoring_rubric"] = deepcopy(episode.get("scoring_rubric", {}))
        if isinstance(episode.get("tags"), list):
            hydrated["tags"] = deepcopy(episode.get("tags"))
        return hydrated

    if scenario.get("teacher_prompt") or scenario.get("holdout_prompt"):
        return deepcopy(scenario)

    holdout_label = holdout_ref or scenario.get("id") or "unknown-holdout"
    if private_holdout_pack:
        raise ContractError(
            f"holdout scenario '{holdout_label}' was not found in private_holdout_manifest and does not include inline teacher_prompt"
        )
    raise ContractError(
        f"holdout scenario '{holdout_label}' is missing teacher_prompt; configure private_holdout_manifest or provide the prompt inline"
    )


def _private_holdout_reference_id(scenario: dict[str, Any]) -> str | None:
    value = scenario.get("holdout_episode_id") or scenario.get("id")
    return str(value) if value else None


def _load_private_holdout_pack(
    request_path: Path,
    config: dict[str, Any],
    *,
    blocked_family_ids: list[Any],
) -> dict[str, Any] | None:
    raw = config.get("private_holdout_manifest")
    if not raw:
        return None

    manifest_path = Path(str(raw))
    if not manifest_path.is_absolute():
        manifest_path = (request_path.parent / manifest_path).resolve()

    _validate_private_holdout_location(manifest_path)
    manifest = _load_json(manifest_path)
    meta = manifest.get("meta")
    if not isinstance(meta, dict):
        raise ContractError("private_holdout_manifest.meta must be an object")
    if meta.get("visibility") != "teacher_only":
        raise ContractError("private_holdout_manifest.meta.visibility must be 'teacher_only'")
    if meta.get("public_repo_safe") is not False:
        raise ContractError("private_holdout_manifest.meta.public_repo_safe must be false")

    episodes = manifest.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ContractError("private_holdout_manifest must contain at least one episode")

    blocked_family_set = {str(family_id) for family_id in blocked_family_ids}
    episodes_by_id: dict[str, dict[str, Any]] = {}
    family_ids: list[str] = []
    for index, episode in enumerate(episodes):
        if not isinstance(episode, dict):
            raise ContractError(f"private_holdout_manifest.episodes[{index}] must be an object")
        missing = PRIVATE_HOLDOUT_REQUIRED_KEYS - set(episode.keys())
        if missing:
            raise ContractError(
                f"private_holdout_manifest episode '{episode.get('id', index)}' missing keys: {sorted(missing)}"
            )
        if episode.get("_placeholder") or "REPLACE-ME" in str(episode.get("id", "")):
            raise ContractError("private_holdout_manifest still contains placeholder episodes")

        episode_id = str(episode.get("id"))
        family_id = str(episode.get("family_id"))
        if episode_id in episodes_by_id:
            raise ContractError(f"duplicate private holdout episode id: {episode_id}")
        if family_id in blocked_family_set:
            raise ContractError(
                f"private holdout episode '{episode_id}' reuses blocked public family '{family_id}'"
            )
        if episode.get("difficulty") not in VALID_DIFFICULTIES:
            raise ContractError(
                f"private holdout episode '{episode_id}' has invalid difficulty '{episode.get('difficulty')}'"
            )
        prompt = str(episode.get("teacher_prompt") or "")
        if not prompt or "REPLACE-ME" in prompt:
            raise ContractError(f"private holdout episode '{episode_id}' has placeholder teacher_prompt")
        rubric = episode.get("scoring_rubric")
        if not isinstance(rubric, dict) or not rubric:
            raise ContractError(f"private holdout episode '{episode_id}' has empty scoring_rubric")

        episodes_by_id[episode_id] = deepcopy(episode)
        family_ids.append(family_id)

    return {
        "path": manifest_path,
        "manifest": manifest,
        "meta": meta,
        "episodes_by_id": episodes_by_id,
        "episode_ids": sorted(episodes_by_id.keys()),
        "family_ids": sorted(set(family_ids)),
    }


def _validate_private_holdout_location(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return

    try:
        resolved.relative_to(PRIVATE_HOLDOUT_DIR)
    except ValueError as exc:
        raise ContractError(
            "private_holdout_manifest must live under benchmarks/private-holdout-pack/ when stored inside the repo"
        ) from exc


def _build_stage_receipt(
    *,
    stage_key: str,
    stage_config: dict[str, Any],
    request: dict[str, Any],
    result: dict[str, Any],
    artifacts_root: Path,
    baseline_run_id: str | None,
    candidate_student_run_id: str | None,
    verifier_commands_override: list[str] | None = None,
    loop_sequence_id: str | None = None,
    benchmark_pack_meta: dict[str, Any] | None = None,
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

    receipt_completeness = _build_stage_receipt_completeness(run_dir, artifact_bundle, stored_result)

    verifier_contract = _build_verifier_contract(
        stage_key=stage_key,
        request=request,
        artifact_bundle=artifact_bundle,
        runner=scorecard.get("runner") if isinstance(scorecard, dict) else "LocalReplayRunner",
        verifier_commands_override=verifier_commands_override,
    )

    request_traceability = request.get("traceability") if isinstance(request.get("traceability"), dict) else {}
    lineage: dict[str, Any] = {
        "sequence_id": request_traceability.get("sequence_id") or loop_sequence_id or request.get("scenario_set_id"),
        "scenario_set_id": request.get("scenario_set_id"),
        "root_run_id": baseline_run_id or run_id,
        "parent_run_id": baseline_run_id if stage_key == "candidate-student" else candidate_student_run_id,
        "iteration_index": stage_meta["iteration"],
        "iteration_label": stage_meta["iteration_label"],
    }
    if stage_key == "candidate-teacher-eval" and candidate_student_run_id and baseline_run_id:
        lineage["student_run_id"] = candidate_student_run_id
        lineage["derived_previous_iteration_from"] = baseline_run_id

    traceability = _build_stage_traceability_export(
        request=request,
        artifact_bundle=artifact_bundle,
        request_traceability=request_traceability,
        benchmark_pack_meta=benchmark_pack_meta,
    )

    # audit_bundle_path from provenance
    audit_bundle_path = None
    provenance = stored_result.get("provenance") if isinstance(stored_result.get("provenance"), dict) else {}
    if provenance.get("audit_bundle_path"):
        audit_bundle_path = provenance["audit_bundle_path"]

    stage = {
        "run_id": run_id,
        "status": result.get("status"),
        "total_score": export_result.get("machine_score"),
        "aggregate_score": aggregate_score,
        "verifier_contract": verifier_contract,
        "lineage": lineage,
        "traceability": traceability,
        "audit_bundle_path": audit_bundle_path,
        "export": {
            "run": export_run,
            "result": export_result,
            "artifact_bundle": artifact_bundle,
            "transcript_excerpt": transcript_excerpt,
            "receipt_completeness": receipt_completeness,
        },
    }
    return stage


def _build_stage_traceability_export(
    *,
    request: dict[str, Any],
    artifact_bundle: dict[str, Any],
    request_traceability: dict[str, Any],
    benchmark_pack_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    benchmark_pack_meta = benchmark_pack_meta if isinstance(benchmark_pack_meta, dict) else {}
    traceability = {
        "sequence_id": request_traceability.get("sequence_id"),
        "stage_key": request_traceability.get("stage_key"),
        "benchmark_pack": {
            "id": request_traceability.get("benchmark_pack", {}).get("id")
            if isinstance(request_traceability.get("benchmark_pack"), dict)
            else benchmark_pack_meta.get("id"),
            "version": request_traceability.get("benchmark_pack", {}).get("version")
            if isinstance(request_traceability.get("benchmark_pack"), dict)
            else benchmark_pack_meta.get("version"),
            "role_scope": request_traceability.get("benchmark_pack", {}).get("role_scope")
            if isinstance(request_traceability.get("benchmark_pack"), dict)
            else benchmark_pack_meta.get("role_scope") or benchmark_pack_meta.get("role"),
        },
        "episodes": deepcopy(request_traceability.get("episodes"))
        if isinstance(request_traceability.get("episodes"), dict)
        else {},
    }

    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    repo_task_pack = student_view.get("repo_task_pack") if isinstance(student_view.get("repo_task_pack"), dict) else {}
    episodes = traceability["episodes"]
    if repo_task_pack.get("episode_ids") and not episodes.get("visible_episode_ids"):
        episodes["visible_episode_ids"] = list(repo_task_pack.get("episode_ids"))
    if repo_task_pack.get("family_ids") and not episodes.get("family_ids"):
        episodes["family_ids"] = list(repo_task_pack.get("family_ids"))
    if student_view.get("sealed_holdout_count") is not None and not episodes.get("sealed_holdout_count"):
        episodes["sealed_holdout_count"] = int(student_view.get("sealed_holdout_count") or 0)
    return traceability


def _build_verifier_contract(
    *,
    stage_key: str,
    request: dict[str, Any],
    artifact_bundle: dict[str, Any],
    runner: str,
    verifier_commands_override: list[str] | None = None,
) -> dict[str, Any]:
    """Build an honest verifier-contract block for a stage receipt.

    In the local-replay alpha path, verifier commands are never actually
    executed.  This function surfaces the required commands and marks each
    one as ``not_executed`` so downstream consumers can distinguish a real
    green gate from a replay that never ran the checks.
    """
    is_local_replay = runner == "LocalReplayRunner"

    required_commands = _extract_required_verifier_commands(
        request, artifact_bundle, verifier_commands_override=verifier_commands_override,
    )

    command_results = []
    for command in required_commands:
        command_results.append({
            "command": command,
            "execution_status": "not_executed" if is_local_replay else "unknown",
            "exit_code": None,
            "honesty_note": (
                "Local-replay alpha path does not execute verifier commands."
                if is_local_replay
                else "Execution status was not captured by the runner."
            ),
        })

    has_commands = len(required_commands) > 0
    all_executed = has_commands and all(
        cr["execution_status"] == "executed" for cr in command_results
    )
    all_passed = all_executed and all(
        cr.get("exit_code") == 0 for cr in command_results
    )

    if is_local_replay:
        gate_status = "not_executed"
        gate_honesty_note = (
            "The local-replay runner produces deterministic receipts without "
            "executing verifier commands. Gate status will become meaningful "
            "when a live-execution backend is wired."
        )
    elif not has_commands:
        gate_status = "no_commands"
        gate_honesty_note = "No verifier commands were specified for this stage."
    elif all_passed:
        gate_status = "pass"
        gate_honesty_note = "All verifier commands executed and returned exit code 0."
    elif all_executed:
        gate_status = "fail"
        gate_honesty_note = "One or more verifier commands returned a non-zero exit code."
    else:
        gate_status = "incomplete"
        gate_honesty_note = "Not all verifier commands have execution results."

    return {
        "stage_key": stage_key,
        "runner": runner,
        "required_commands": required_commands,
        "command_results": command_results,
        "gate_status": gate_status,
        "honesty_note": gate_honesty_note,
    }


def _extract_required_verifier_commands(
    request: dict[str, Any],
    artifact_bundle: dict[str, Any],
    *,
    verifier_commands_override: list[str] | None = None,
) -> list[str]:
    """Collect verifier commands from the request, artifact bundle, or override.

    Teacher stages (baseline-eval, candidate-teacher-eval) do not carry a
    ``student_prompt_pack``, so their request/artifact_bundle will not contain
    verifier commands.  The ``verifier_commands_override`` parameter lets the
    caller inject the commands from the benchmark-pack execution policy so
    that every stage receipt surfaces the same contract.
    """
    commands: list[str] = []
    seen: set[str] = set()

    for source in (
        ((request.get("student_prompt_pack") or {}).get("repo_task_pack") or {}).get("recommended_verifier_commands"),
        ((artifact_bundle.get("student_view") or {}).get("repo_task_pack") or {}).get("recommended_verifier_commands"),
        verifier_commands_override,
    ):
        if isinstance(source, list):
            for cmd in source:
                cmd_str = str(cmd)
                if cmd_str not in seen:
                    seen.add(cmd_str)
                    commands.append(cmd_str)

    return commands


def _patch_provenance_receipt_verifier_gates(
    run_dir: Path,
    verifier_commands: list[str] | None,
    runner: str,
) -> None:
    """Add ``verifier_gate`` to baseline.json and evaluation.json receipts.

    The provenance writer (called by the bridge) creates these files but does
    not have access to the benchmark-pack execution policy.  This post-hoc
    patch adds the gate so that every provenance receipt surfaces the same
    verifier-command contract.  ``candidate.json`` already has the gate from
    the provenance writer, so it is left untouched.
    """
    receipts_dir = run_dir / "receipts"
    if not receipts_dir.is_dir():
        return

    commands = verifier_commands if isinstance(verifier_commands, list) else []
    is_local_replay = runner == "LocalReplayRunner"

    if commands:
        gate = {
            "status": "not_executed" if is_local_replay else "unknown",
            "required_commands": list(commands),
            "executed_count": 0 if is_local_replay else None,
            "honesty_note": (
                "Local-replay alpha path does not execute verifier commands. "
                "These commands should be run by a live-execution backend to "
                "produce a meaningful gate result."
                if is_local_replay
                else "Verifier command execution status was not captured."
            ),
        }
    else:
        gate = {
            "status": "no_commands",
            "required_commands": [],
            "executed_count": 0,
            "honesty_note": "No verifier commands were specified in the execution policy.",
        }

    for receipt_name in ("baseline.json", "evaluation.json"):
        receipt_path = receipts_dir / receipt_name
        if not receipt_path.exists():
            continue
        try:
            receipt = json.loads(receipt_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if "verifier_gate" not in receipt:
            receipt["verifier_gate"] = gate
            receipt_path.write_text(json.dumps(receipt, indent=2))


def _build_stage_receipt_completeness(
    run_dir: Path,
    artifact_bundle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    receipts_dir = run_dir / "receipts"
    receipt_files = {
        "manifest.json": (receipts_dir / "manifest.json").exists(),
        "evidence-index.json": (receipts_dir / "evidence-index.json").exists(),
        "summary.md": (receipts_dir / "summary.md").exists(),
        "candidate.json": (receipts_dir / "candidate.json").exists(),
    }
    for optional in ("evaluation.json", "baseline.json"):
        path = receipts_dir / optional
        if path.exists():
            receipt_files[optional] = True

    provenance_pointers = _check_provenance_pointers(artifact_bundle, result)

    all_receipt_files_present = all(receipt_files.values())
    all_provenance_pointers_valid = all(provenance_pointers.values())

    return {
        "complete": all_receipt_files_present and all_provenance_pointers_valid,
        "receipt_files": receipt_files,
        "provenance_pointers": provenance_pointers,
    }


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
        if integrity_gate.get("mode") == "local_private_holdout":
            reasons.append(
                "Integrity gate still blocks sealed-eval and sealed-certification claims. This run proves a local private-holdout lane with fresh hidden holdouts kept outside the public repo and student-visible artifacts."
            )
        else:
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


def _build_verifier_gate_summary(
    stages: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build an aggregate verifier gate across all stages."""
    stage_statuses: dict[str, str] = {}
    total_commands = 0
    executed_commands = 0

    for stage_key, stage in stages.items():
        vc = stage.get("verifier_contract") or {}
        gate_status = vc.get("gate_status", "unknown")
        stage_statuses[stage_key] = gate_status
        for cr in vc.get("command_results", []):
            total_commands += 1
            if cr.get("execution_status") == "executed":
                executed_commands += 1

    all_not_executed = all(s == "not_executed" for s in stage_statuses.values())
    any_fail = any(s == "fail" for s in stage_statuses.values())

    if all_not_executed:
        aggregate_status = "not_executed"
        honesty_note = (
            "All stages used the local-replay runner. No verifier commands were "
            "actually executed. This alpha loop proves receipt structure and "
            "evaluation-contract wiring, not real code execution."
        )
    elif any_fail:
        aggregate_status = "fail"
        honesty_note = "One or more stages had failing verifier commands."
    elif all(s == "pass" for s in stage_statuses.values()):
        aggregate_status = "pass"
        honesty_note = "All verifier commands across all stages passed."
    else:
        aggregate_status = "incomplete"
        honesty_note = "Not all stages have complete verifier execution results."

    return {
        "aggregate_status": aggregate_status,
        "stage_statuses": stage_statuses,
        "total_commands": total_commands,
        "executed_commands": executed_commands,
        "honesty_note": honesty_note,
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
            "receipts/evidence-index.json": run_dir / "receipts" / "evidence-index.json",
            "receipts/summary.md": run_dir / "receipts" / "summary.md",
            "receipts/audit-bundle.json": run_dir / "receipts" / "audit-bundle.json",
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

        provenance_pointers = _check_provenance_pointers(artifact_bundle, result)
        checks.update(provenance_pointers)

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


def _check_provenance_pointers(
    artifact_bundle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    bundle_provenance = artifact_bundle.get("provenance") if isinstance(artifact_bundle.get("provenance"), dict) else {}
    bundle_receipts = artifact_bundle.get("receipts") if isinstance(artifact_bundle.get("receipts"), dict) else {}
    bundle_paths = set()
    if bundle_provenance.get("receipt_manifest_path"):
        bundle_paths.add(bundle_provenance["receipt_manifest_path"])
    if bundle_provenance.get("evidence_index_path"):
        bundle_paths.add(bundle_provenance["evidence_index_path"])
    if bundle_provenance.get("summary_path"):
        bundle_paths.add(bundle_provenance["summary_path"])
    if bundle_provenance.get("audit_bundle_path"):
        bundle_paths.add(bundle_provenance["audit_bundle_path"])
    for key in ("receipt_manifest_path", "evidence_index_path", "summary_path", "audit_bundle_path"):
        if bundle_receipts.get(key):
            bundle_paths.add(bundle_receipts[key])
    checks["bundle_provenance_has_manifest"] = "receipts/manifest.json" in bundle_paths
    checks["bundle_provenance_has_evidence_index"] = "receipts/evidence-index.json" in bundle_paths
    checks["bundle_provenance_has_summary"] = "receipts/summary.md" in bundle_paths
    checks["bundle_provenance_has_audit_bundle"] = "receipts/audit-bundle.json" in bundle_paths

    result_provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    result_paths = set()
    if result_provenance.get("receipt_manifest_path"):
        result_paths.add(result_provenance["receipt_manifest_path"])
    if result_provenance.get("evidence_index_path"):
        result_paths.add(result_provenance["evidence_index_path"])
    if result_provenance.get("summary_path"):
        result_paths.add(result_provenance["summary_path"])
    if result_provenance.get("audit_bundle_path"):
        result_paths.add(result_provenance["audit_bundle_path"])
    checks["result_provenance_has_manifest"] = "receipts/manifest.json" in result_paths
    checks["result_provenance_has_evidence_index"] = "receipts/evidence-index.json" in result_paths
    checks["result_provenance_has_summary"] = "receipts/summary.md" in result_paths
    checks["result_provenance_has_audit_bundle"] = "receipts/audit-bundle.json" in result_paths

    return checks


def _evaluate_integrity_gate(
    config: dict[str, Any],
    benchmark_pack: dict[str, Any],
    family_registry: dict[str, Any],
    *,
    private_holdout_pack: dict[str, Any] | None,
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

    public_regression_ok = bool(benchmark_pack.get("execution_policy", {}).get("student_visible_only"))
    baseline_usage = _stage_private_holdout_usage(config, "baseline-eval", private_holdout_pack)
    candidate_usage = _stage_private_holdout_usage(config, "candidate-teacher-eval", private_holdout_pack)
    local_private_holdout_ok = bool(
        private_holdout_pack
        and baseline_usage["all_holdouts_private"]
        and candidate_usage["all_holdouts_private"]
    )
    fresh_hidden_holdout_claim_ok = local_private_holdout_ok
    local_private_holdout_claim_ok = local_private_holdout_ok
    sealed_eval_claim_ok = False
    certification_claim_ok = False

    claims_allowed = [
        "public better/equal/worse comparison",
        "artifact-complete baseline → candidate → teacher-eval receipts",
        "public curriculum prompt-pack execution",
    ]
    claims_blocked: list[str] = ["sealed-eval claims", "sealed certification"]
    mode = "public_regression"

    if local_private_holdout_ok:
        mode = "local_private_holdout"
        claims_allowed.append("local private-holdout alpha-loop execution")
        claims_allowed.append("fresh hidden holdouts loaded from a local private manifest")
        claims_allowed.append("fresh teacher-only holdout scoring kept out of student-visible artifacts")
    else:
        claims_blocked.append("fresh hidden holdout integrity claims")

    if require_sealed_holdout and not local_private_holdout_ok:
        summary = "Integrity gate blocked: a truly local private-holdout alpha path is not configured yet. Author fresh teacher-only episodes outside the public repo and reference them via private_holdout_manifest first."
        status = "blocked"
    elif local_private_holdout_ok:
        summary = "Integrity gate passed for a local private-holdout alpha loop. The run may claim fresh hidden holdouts loaded from a local private manifest and kept out of tracked or student-visible artifacts, but sealed-eval and sealed-certification claims remain blocked."
        status = "pass"
    else:
        summary = "Integrity gate passed for a public-regression alpha loop; sealed-eval claims remain blocked pending teacher-only family rewrite."
        status = "pass"

    return {
        "status": status,
        "mode": mode,
        "summary": summary,
        "public_regression_ok": public_regression_ok,
        "fresh_hidden_holdout_claim_ok": fresh_hidden_holdout_claim_ok,
        "local_private_holdout_claim_ok": local_private_holdout_claim_ok,
        "sealed_eval_claim_ok": sealed_eval_claim_ok,
        "certification_claim_ok": certification_claim_ok,
        "require_sealed_holdout": require_sealed_holdout,
        "dataset_manifest_id": benchmark_pack.get("meta", {}).get("id"),
        "dataset_version": benchmark_pack.get("meta", {}).get("version"),
        "blocked_family_ids": blocked_ids,
        "blocked_reasons": blocked_reasons,
        "private_holdout_manifest_id": private_holdout_pack.get("meta", {}).get("id") if private_holdout_pack else None,
        "private_holdout_family_ids": private_holdout_pack.get("family_ids", []) if private_holdout_pack else [],
        "private_holdout_usage": {
            "baseline-eval": baseline_usage,
            "candidate-teacher-eval": candidate_usage,
        },
        "claims_allowed": claims_allowed,
        "claims_blocked": claims_blocked,
    }


def _stage_private_holdout_usage(
    config: dict[str, Any],
    stage_key: str,
    private_holdout_pack: dict[str, Any] | None,
) -> dict[str, Any]:
    stage_config = _stage_config(config, stage_key)
    request = stage_config.get("request") or {}
    teacher_eval = request.get("teacher_evaluation")
    if not isinstance(teacher_eval, dict):
        return {
            "holdout_count": 0,
            "manifest_match_count": 0,
            "manifest_episode_ids": [],
            "inline_holdout_ids": [],
            "unresolved_holdout_ids": [],
            "all_holdouts_private": False,
        }

    matched: list[str] = []
    inline: list[str] = []
    unresolved: list[str] = []
    holdout_count = 0
    for scenario in teacher_eval.get("scenarios", []):
        if not isinstance(scenario, dict) or scenario.get("type") != "holdout":
            continue
        holdout_count += 1
        holdout_ref = _private_holdout_reference_id(scenario) or f"holdout-{holdout_count}"
        if private_holdout_pack and holdout_ref in private_holdout_pack["episodes_by_id"]:
            matched.append(holdout_ref)
        elif scenario.get("teacher_prompt") or scenario.get("holdout_prompt"):
            inline.append(str(holdout_ref))
        else:
            unresolved.append(str(holdout_ref))

    return {
        "holdout_count": holdout_count,
        "manifest_match_count": len(matched),
        "manifest_episode_ids": sorted(set(matched)),
        "inline_holdout_ids": inline,
        "unresolved_holdout_ids": unresolved,
        "all_holdouts_private": bool(holdout_count) and len(matched) == holdout_count,
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


def _extract_repo_task_meta(episode: dict[str, Any]) -> dict[str, Any] | None:
    """Pull repo-task-shaped metadata from a benchmark episode.

    Only includes fields that actually exist on the episode so the shape
    stays honest about what was authored vs. inferred.
    """
    meta: dict[str, Any] = {}
    for key in ("family_id", "mutation_budget", "constraints", "suggested_files", "artifacts_required", "public_checks", "tags"):
        value = episode.get(key)
        if value is not None:
            meta[key] = deepcopy(value) if isinstance(value, (list, dict)) else value
    return meta if meta else None


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ContractError(f"expected JSON object at {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
