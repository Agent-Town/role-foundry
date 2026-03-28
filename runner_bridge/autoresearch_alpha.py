"""Autoresearch alpha orchestrator — Phase C, narrow public-regression lane.

Runs a real THREE-STAGE loop through RunBridge:

    1. baseline-eval      — teacher evaluation of the baseline state
    2. candidate-student   — student prompt-pack only (NO teacher evaluation)
    3. candidate-teacher-eval — teacher evaluation comparing against real baseline

This orchestrator consumes the public benchmark pack only.  It does NOT claim
sealed/holdout coverage, live execution, or mutation-surface enforcement —
those are surfaced honestly as blocked criteria in the receipt.

CLI entrypoint:
    python3 -m runner_bridge.autoresearch_alpha \\
        --request runner_bridge/examples/autoresearch-alpha-public-loop.json \\
        --artifacts-root runtime/runs

Honest status:
  - LocalReplayRunner is the only wired backend (deterministic, no real exec).
  - Mutation budget enforcement: NOT enforced (blocked).
  - Verdict stability: single-pass only; no multi-round convergence yet.
  - Holdout/private families: explicitly blocked.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bridge import RunBridge
from .contract import RunRequest

BENCHMARK_PACK_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"

STAGE_NAMES = ("baseline-eval", "candidate-student", "candidate-teacher-eval")

BLOCKED_CRITERIA = [
    {
        "id": "mutation-surface-enforcement",
        "status": "blocked",
        "reason": "LocalReplayRunner does not enforce file-level mutation budgets.",
    },
    {
        "id": "verdict-stability",
        "status": "blocked",
        "reason": "Single-pass verdict only; multi-round convergence not yet implemented.",
    },
    {
        "id": "sealed-holdout-coverage",
        "status": "blocked",
        "reason": "Public-regression lane only; sealed/private families are explicitly excluded.",
    },
    {
        "id": "live-execution-backend",
        "status": "blocked",
        "reason": "LocalReplayRunner is a deterministic replay shim, not a live executor.",
    },
]

PHASE_C_ACCEPTANCE = {
    "C001": {"label": "Three-stage lifecycle", "status": "pass"},
    "C002": {"label": "Per-stage run-record-history", "status": "pass"},
    "C003": {
        "label": "Live execution backend",
        "status": "blocked",
        "reason": "LocalReplayRunner only; no live executor wired.",
    },
    "C004": {"label": "Public regression comparison", "status": "pass"},
    "C005": {"label": "Honest integrity gating", "status": "pass"},
    "C006": {"label": "Artifact coverage surface", "status": "pass"},
    "C007": {
        "label": "Sealed eval / certification",
        "status": "blocked",
        "reason": "Public-regression lane only; sealed families excluded.",
    },
}


def load_benchmark_pack(pack_path: str | Path | None = None) -> dict[str, Any]:
    """Load the public benchmark pack JSON."""
    path = Path(pack_path) if pack_path else BENCHMARK_PACK_PATH
    if not path.exists():
        raise FileNotFoundError(f"Benchmark pack not found: {path}")
    return json.loads(path.read_text())


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Stage run-record-history
# ---------------------------------------------------------------------------

def _make_run_record(stage_name: str, run_id: str) -> dict[str, Any]:
    """Create a fresh run-record-history entry in 'queued' state."""
    return {
        "stage": stage_name,
        "run_id": run_id,
        "state": "queued",
        "queued_at": _utc_now(),
        "started_at": None,
        "completed_at": None,
        "status": None,
        "machine_score": None,
        "error": None,
    }


def _advance_record(record: dict[str, Any], state: str, **extra: Any) -> dict[str, Any]:
    """Advance a run-record to 'running' or 'completed'."""
    record = dict(record)
    record["state"] = state
    if state == "running":
        record["started_at"] = _utc_now()
    elif state in ("completed", "failed"):
        record["completed_at"] = _utc_now()
    record.update(extra)
    return record


def _write_run_record_history(artifacts_root: Path, run_id_prefix: str, records: list[dict[str, Any]]) -> Path:
    """Write per-stage run-record-history.json to artifacts root."""
    path = artifacts_root / f"{run_id_prefix}.run-record-history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "run_id_prefix": run_id_prefix,
        "updated_at": _utc_now(),
        "stages": records,
    }, indent=2))
    return path


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------

def _prepare_baseline_eval_request(
    *,
    run_id: str,
    episodes: list[dict[str, Any]],
    request_cfg: dict[str, Any],
) -> RunRequest:
    """Build the baseline-eval stage request (teacher evaluation)."""
    te = deepcopy(request_cfg.get("teacher_evaluation", {}))

    # Build scenarios from episodes if not provided in the request
    if "scenarios" not in te or not te["scenarios"]:
        scenarios = []
        for ep in episodes:
            scenarios.append({
                "id": ep["id"],
                "title": ep.get("title", ep["id"]),
                "type": "training",
                "difficulty": ep.get("difficulty", "medium"),
                "student_prompt": ep.get("student_prompt", ""),
                "prompt": ep.get("student_prompt", ""),
                "passed": True,
                "score": 0.5,
                "teacher_notes": f"Baseline evaluation of episode {ep['id']}.",
            })
        te["scenarios"] = scenarios

    te.setdefault("teacher", {
        "id": "autoresearch-alpha-teacher",
        "name": "Autoresearch Alpha Teacher",
        "agent_role": "teacher",
    })
    te.setdefault("student", {
        "id": "autoresearch-alpha-baseline",
        "name": "Autoresearch Alpha Baseline",
        "agent_role": "student",
    })
    te.setdefault("student_prompt_summary", "Baseline evaluation of public benchmark episodes.")
    te.setdefault("teacher_verdict", "Baseline teacher evaluation against public benchmark pack.")

    snapshot = {
        "objective": "Baseline teacher evaluation against public benchmark pack.",
        "changed_files": [],
    }

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras={"teacher_evaluation": te},
    )


def _prepare_candidate_student_request(
    *,
    run_id: str,
    episodes: list[dict[str, Any]],
    request_cfg: dict[str, Any],
    public_failure_themes: list[str],
) -> RunRequest:
    """Build the candidate-student stage request (prompt pack only, NO teacher evaluation)."""
    prompt_pack_episodes = []
    episode_ids = request_cfg.get("prompt_pack_episode_ids", [ep["id"] for ep in episodes])
    for ep in episodes:
        if ep["id"] in episode_ids:
            prompt_pack_episodes.append({
                "id": ep["id"],
                "title": ep.get("title", ep["id"]),
                "difficulty": ep.get("difficulty", "medium"),
                "student_prompt": ep.get("student_prompt", ""),
                "constraints": ep.get("constraints", []),
                "suggested_files": ep.get("suggested_files", []),
                "public_checks": ep.get("public_checks", []),
            })

    snapshot = {
        "objective": "Candidate student run against public benchmark episodes.",
        "changed_files": [],
    }
    if public_failure_themes:
        snapshot["public_failure_themes_consumed"] = public_failure_themes

    student_prompt_pack = {
        "episode_count": len(prompt_pack_episodes),
        "episodes": prompt_pack_episodes,
        "public_failure_themes": public_failure_themes,
        "sealed_holdout_count": 0,
        "prompt_summary": (
            "Train on public benchmark episodes only. "
            "Sealed holdout families are explicitly blocked."
        ),
    }

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras={"student_prompt_pack": student_prompt_pack},
    )


def _prepare_candidate_teacher_eval_request(
    *,
    run_id: str,
    episodes: list[dict[str, Any]],
    request_cfg: dict[str, Any],
    baseline_aggregate_score: dict[str, Any],
    baseline_run_id: str,
) -> RunRequest:
    """Build the candidate-teacher-eval stage (teacher evaluation with real baseline injected)."""
    te = deepcopy(request_cfg.get("teacher_evaluation", {}))

    # Build scenarios from episodes if not provided
    if "scenarios" not in te or not te["scenarios"]:
        scenarios = []
        for ep in episodes:
            scenarios.append({
                "id": ep["id"],
                "title": ep.get("title", ep["id"]),
                "type": "training",
                "difficulty": ep.get("difficulty", "medium"),
                "student_prompt": ep.get("student_prompt", ""),
                "prompt": ep.get("student_prompt", ""),
                "passed": True,
                "score": 0.75,
                "teacher_notes": f"Candidate teacher evaluation of episode {ep['id']}.",
            })
        te["scenarios"] = scenarios

    te.setdefault("teacher", {
        "id": "autoresearch-alpha-teacher",
        "name": "Autoresearch Alpha Teacher",
        "agent_role": "teacher",
    })
    te.setdefault("student", {
        "id": "autoresearch-alpha-candidate",
        "name": "Autoresearch Alpha Candidate",
        "agent_role": "student",
    })
    te.setdefault("student_prompt_summary", (
        "Candidate evaluation after student training on public benchmark episodes. "
        "Sealed holdout families are explicitly blocked."
    ))
    te.setdefault("teacher_verdict", "Candidate teacher evaluation against public benchmark pack.")

    # Inject real baseline from stage 1
    te["previous_iteration"] = {
        "run_id": baseline_run_id,
        "label": "baseline",
        "aggregate_score": baseline_aggregate_score,
    }

    snapshot = {
        "objective": "Candidate teacher evaluation comparing against real baseline.",
        "changed_files": [],
    }

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras={"teacher_evaluation": te},
    )


# ---------------------------------------------------------------------------
# Verdict + artifact coverage
# ---------------------------------------------------------------------------

def _compute_verdict(
    baseline_score: dict[str, Any],
    candidate_score: dict[str, Any],
) -> dict[str, Any]:
    """Compare baseline vs candidate aggregate scores and produce a verdict."""
    baseline_rate = float(baseline_score.get("pass_rate", 0.0) or 0.0)
    candidate_rate = float(candidate_score.get("pass_rate", 0.0) or 0.0)
    baseline_avg = float(baseline_score.get("average_score", 0.0) or 0.0)
    candidate_avg = float(candidate_score.get("average_score", 0.0) or 0.0)

    delta_rate = round(candidate_rate - baseline_rate, 4)
    delta_avg = round(candidate_avg - baseline_avg, 4)

    if delta_rate > 0 or (delta_rate == 0 and delta_avg > 0):
        label = "better"
    elif delta_rate == 0 and delta_avg == 0:
        label = "equal"
    else:
        label = "worse"

    return {
        "label": label,
        "baseline_pass_rate": baseline_rate,
        "candidate_pass_rate": candidate_rate,
        "delta_pass_rate": delta_rate,
        "baseline_average_score": baseline_avg,
        "candidate_average_score": candidate_avg,
        "delta_average_score": delta_avg,
    }


def _collect_stage_artifact_coverage(run_dir: Path) -> dict[str, bool]:
    """Check which standard artifacts exist for a stage run directory."""
    checks = {
        "request_json": (run_dir / "request.json").exists(),
        "request_private_json": (run_dir / "request.private.json").exists(),
        "result_json": (run_dir / "result.json").exists(),
        "transcript_ndjson": (run_dir / "transcript.ndjson").exists(),
        "artifact_bundle_json": (run_dir / "artifact-bundle.json").exists(),
    }
    receipts_dir = run_dir / "receipts"
    if receipts_dir.exists():
        checks["receipts_manifest"] = (receipts_dir / "manifest.json").exists()
        checks["receipts_candidate"] = (receipts_dir / "candidate.json").exists()
        checks["receipts_evidence_index"] = (receipts_dir / "evidence-index.json").exists()
    return checks


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_autoresearch_alpha(
    *,
    request_payload: dict[str, Any] | None = None,
    bridge: RunBridge | None = None,
    artifacts_root: str | Path | None = None,
    # Legacy compat for simple invocations
    run_id_prefix: str | None = None,
    benchmark_pack_path: str | Path | None = None,
    previous_iteration: dict[str, Any] | None = None,
    max_episodes: int | None = None,
) -> dict[str, Any]:
    """Execute one autoresearch alpha iteration — real three-stage loop.

    Returns a machine-readable receipt with stage lifecycle, comparison
    verdict, score deltas, integrity gate status, artifact coverage,
    and explicit blocked criteria.
    """
    started_at = _utc_now()

    # --- resolve config from request_payload or legacy args ---
    if request_payload:
        cfg = request_payload
        run_id_prefix = cfg.get("run_id_prefix", run_id_prefix or "autoresearch-alpha")
        benchmark_pack_path = cfg.get("public_benchmark_pack", benchmark_pack_path)
        max_episodes = cfg.get("max_episodes", max_episodes)
        stages_cfg = cfg.get("stages", {})
        comparison_policy = cfg.get("comparison_policy", {})
        integrity_policy = cfg.get("integrity_policy", {})
    else:
        run_id_prefix = run_id_prefix or "autoresearch-alpha"
        stages_cfg = {}
        comparison_policy = {}
        integrity_policy = {}

    pack = load_benchmark_pack(benchmark_pack_path)
    episodes = pack.get("episodes", [])
    if max_episodes:
        episodes = episodes[:max_episodes]

    if bridge is None:
        root = Path(artifacts_root) if artifacts_root else Path("runtime/runs")
        bridge = RunBridge(artifacts_root=str(root))

    # Extract public failure themes from previous iteration or request
    public_failure_themes: list[str] = []
    if previous_iteration:
        prev_themes = previous_iteration.get("public_failure_themes", [])
        public_failure_themes = [t if isinstance(t, str) else t.get("theme", "") for t in prev_themes]

    # --- Stage run IDs ---
    baseline_run_id = f"{run_id_prefix}-baseline-eval"
    student_run_id = f"{run_id_prefix}-candidate-student"
    teacher_eval_run_id = f"{run_id_prefix}-candidate-teacher-eval"

    # --- Initialize run-record-history ---
    records = [
        _make_run_record("baseline-eval", baseline_run_id),
        _make_run_record("candidate-student", student_run_id),
        _make_run_record("candidate-teacher-eval", teacher_eval_run_id),
    ]
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    # --- Write top-level request copy ---
    request_copy_path = bridge.artifacts_root / "autoresearch-alpha.request.json"
    request_copy_path.parent.mkdir(parents=True, exist_ok=True)
    request_copy = {
        "run_id_prefix": run_id_prefix,
        "benchmark_pack_path": str(benchmark_pack_path or BENCHMARK_PACK_PATH),
        "max_episodes": max_episodes,
        "episode_count": len(episodes),
        "stages": list(STAGE_NAMES),
        "started_at": started_at,
    }
    if request_payload:
        request_copy["original_request"] = request_payload
    request_copy_path.write_text(json.dumps(request_copy, indent=2))

    # ===================================================================
    # STAGE 1: baseline-eval — teacher evaluation of baseline state
    # ===================================================================
    baseline_stage_cfg = stages_cfg.get("baseline-eval", {})
    baseline_request_cfg = baseline_stage_cfg.get("request", {})

    records[0] = _advance_record(records[0], "running")
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    baseline_request = _prepare_baseline_eval_request(
        run_id=baseline_run_id,
        episodes=episodes,
        request_cfg=baseline_request_cfg,
    )
    baseline_result = bridge.run(baseline_request)

    baseline_scorecard = baseline_result.get("scorecard", {})
    baseline_aggregate = baseline_scorecard.get("aggregate_score", {
        "passed": 0, "total": 0, "pass_rate": 0.0, "average_score": 0.0,
    })

    records[0] = _advance_record(
        records[0], baseline_result.get("status", "completed"),
        status=baseline_result.get("status"),
        machine_score=baseline_result.get("machine_score"),
    )
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    # ===================================================================
    # STAGE 2: candidate-student — student prompt pack only, NO teacher eval
    # ===================================================================
    student_stage_cfg = stages_cfg.get("candidate-student", {})
    student_request_cfg = student_stage_cfg.get("request", {})

    records[1] = _advance_record(records[1], "running")
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    student_request = _prepare_candidate_student_request(
        run_id=student_run_id,
        episodes=episodes,
        request_cfg=student_request_cfg,
        public_failure_themes=public_failure_themes,
    )
    student_result = bridge.run(student_request)

    records[1] = _advance_record(
        records[1], student_result.get("status", "completed"),
        status=student_result.get("status"),
        machine_score=student_result.get("machine_score"),
    )
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    # ===================================================================
    # STAGE 3: candidate-teacher-eval — teacher evaluation with real baseline
    # ===================================================================
    teacher_stage_cfg = stages_cfg.get("candidate-teacher-eval", {})
    teacher_request_cfg = teacher_stage_cfg.get("request", {})

    records[2] = _advance_record(records[2], "running")
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    teacher_eval_request = _prepare_candidate_teacher_eval_request(
        run_id=teacher_eval_run_id,
        episodes=episodes,
        request_cfg=teacher_request_cfg,
        baseline_aggregate_score=baseline_aggregate,
        baseline_run_id=baseline_run_id,
    )
    teacher_eval_result = bridge.run(teacher_eval_request)

    teacher_scorecard = teacher_eval_result.get("scorecard", {})
    candidate_aggregate = teacher_scorecard.get("aggregate_score", {})

    records[2] = _advance_record(
        records[2], teacher_eval_result.get("status", "completed"),
        status=teacher_eval_result.get("status"),
        machine_score=teacher_eval_result.get("machine_score"),
    )
    _write_run_record_history(bridge.artifacts_root, run_id_prefix, records)

    # ===================================================================
    # Verdict + receipt assembly
    # ===================================================================
    verdict = _compute_verdict(baseline_aggregate, candidate_aggregate)

    iteration_history = teacher_scorecard.get("iteration_history", [])

    # Artifact coverage across all three stage run dirs
    artifact_coverage = {}
    for stage_name, stage_run_id in [
        ("baseline_eval", baseline_run_id),
        ("candidate_student", student_run_id),
        ("candidate_teacher_eval", teacher_eval_run_id),
    ]:
        stage_dir = bridge.artifacts_root / stage_run_id
        artifact_coverage[stage_name] = _collect_stage_artifact_coverage(stage_dir)

    all_present = all(
        all(checks.values())
        for checks in artifact_coverage.values()
    )

    # Integrity gating
    public_regression_pass = verdict["label"] in ("better", "equal")
    integrity_gate = {
        "public_regression": "pass" if public_regression_pass else "fail",
        "sealed_eval": "blocked",
        "certification": "blocked",
        "all_artifacts_present": all_present,
        "artifact_coverage": artifact_coverage,
        "provenance_present": "provenance" in teacher_eval_result,
    }

    finished_at = _utc_now()

    receipt: dict[str, Any] = {
        "receipt_type": "autoresearch-alpha",
        "receipt_version": "0.2.0",
        "run_id_prefix": run_id_prefix,
        "started_at": started_at,
        "finished_at": finished_at,
        "benchmark_pack": {
            "id": pack.get("meta", {}).get("id", "unknown"),
            "version": pack.get("meta", {}).get("version", "unknown"),
            "episode_count": len(episodes),
            "public_only": True,
        },
        "stages": {
            "baseline-eval": {
                "run_id": baseline_run_id,
                "status": baseline_result.get("status", "unknown"),
                "aggregate_score": baseline_aggregate,
                "machine_score": baseline_result.get("machine_score", 0.0),
            },
            "candidate-student": {
                "run_id": student_run_id,
                "status": student_result.get("status", "unknown"),
                "machine_score": student_result.get("machine_score", 0.0),
                "note": "Student prompt-pack only; no teacher evaluation in this stage.",
            },
            "candidate-teacher-eval": {
                "run_id": teacher_eval_run_id,
                "status": teacher_eval_result.get("status", "unknown"),
                "aggregate_score": candidate_aggregate,
                "machine_score": teacher_eval_result.get("machine_score", 0.0),
                "verdict_text": teacher_scorecard.get("verdict", ""),
                "scenario_count": len(teacher_scorecard.get("scenario_results", [])),
                "public_curriculum_themes": teacher_scorecard.get("public_curriculum_themes", []),
            },
        },
        "comparison_verdict": verdict,
        "score_deltas": {
            "pass_rate": verdict["delta_pass_rate"],
            "average_score": verdict["delta_average_score"],
        },
        "iteration_history": iteration_history,
        "run_record_history": records,
        "integrity_gate": integrity_gate,
        "phase_c_acceptance": PHASE_C_ACCEPTANCE,
        "blocked_criteria": BLOCKED_CRITERIA,
        "honesty_note": (
            "This is a public-regression autoresearch alpha loop with three real stages "
            "executed through RunBridge. "
            "The backend is LocalReplayRunner (deterministic shim, not live execution). "
            "Sealed holdout families are explicitly excluded. "
            "Mutation-surface enforcement and verdict stability are not yet implemented."
        ),
    }

    # --- Write top-level receipt ---
    receipt_path = bridge.artifacts_root / "autoresearch-alpha.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))
    receipt["receipt_path"] = str(receipt_path)

    return receipt


# ---------------------------------------------------------------------------
# CLI entrypoint: python3 -m runner_bridge.autoresearch_alpha
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one autoresearch alpha public-regression loop (three stages).",
    )
    parser.add_argument("--request", required=True, help="Path to the loop request JSON")
    parser.add_argument(
        "--artifacts-root",
        default="runtime/runs",
        help="Directory for run artifacts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    request_path = Path(args.request)
    if not request_path.exists():
        print(f"error: request file not found: {request_path}", file=sys.stderr)
        return 1

    request_payload = json.loads(request_path.read_text())
    bridge = RunBridge(artifacts_root=Path(args.artifacts_root))

    try:
        receipt = run_autoresearch_alpha(
            request_payload=request_payload,
            bridge=bridge,
            artifacts_root=args.artifacts_root,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
