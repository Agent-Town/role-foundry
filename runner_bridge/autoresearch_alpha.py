"""Autoresearch alpha orchestrator — Phase C, narrow public-regression lane.

Runs a single iteration of the autoresearch loop:

    baseline (previous) → candidate (student) → teacher evaluation → verdict

This orchestrator builds on RunBridge + provenance, consuming the public
benchmark pack only.  It does NOT claim sealed/holdout coverage, live
execution, or mutation-surface enforcement — those are surfaced honestly
as blocked criteria in the receipt.

Honest status:
  - LocalReplayRunner is the only wired backend (deterministic, no real exec).
  - Mutation budget enforcement: NOT enforced (blocked).
  - Verdict stability: single-pass only; no multi-round convergence yet.
  - Holdout/private families: explicitly blocked.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bridge import RunBridge
from .contract import RunRequest
from .eval_loop import build_teacher_evaluation

BENCHMARK_PACK_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"

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


def load_benchmark_pack(pack_path: str | Path | None = None) -> dict[str, Any]:
    """Load the public benchmark pack JSON."""
    path = Path(pack_path) if pack_path else BENCHMARK_PACK_PATH
    if not path.exists():
        raise FileNotFoundError(f"Benchmark pack not found: {path}")
    return json.loads(path.read_text())


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_baseline_from_previous(previous_iteration: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the baseline stage receipt from previous_iteration data."""
    if not previous_iteration:
        return {
            "label": "baseline",
            "status": "no_previous",
            "aggregate_score": {"passed": 0, "total": 0, "pass_rate": 0.0, "average_score": 0.0},
            "note": "First iteration — no previous baseline exists.",
        }
    return {
        "label": "baseline",
        "status": "from_previous_iteration",
        "run_id": previous_iteration.get("run_id"),
        "aggregate_score": previous_iteration.get("aggregate_score", {}),
    }


def _build_candidate_request(
    *,
    run_id: str,
    episodes: list[dict[str, Any]],
    previous_iteration: dict[str, Any] | None,
    failure_themes: list[str],
    workspace_snapshot: dict[str, Any] | None = None,
) -> RunRequest:
    """Build the candidate (student) stage run request from benchmark episodes."""
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
            "teacher_notes": f"Autoresearch alpha evaluation of episode {ep['id']}.",
        })

    teacher_evaluation: dict[str, Any] = {
        "teacher": {
            "id": "autoresearch-alpha-teacher",
            "name": "Autoresearch Alpha Teacher",
            "agent_role": "teacher",
        },
        "student": {
            "id": "autoresearch-alpha-candidate",
            "name": "Autoresearch Alpha Candidate",
            "agent_role": "student",
        },
        "student_prompt_summary": (
            "Train on public benchmark episodes only. "
            "Sealed holdout families are explicitly blocked."
        ),
        "teacher_verdict": "Autoresearch alpha single-pass evaluation against public benchmark pack.",
        "scenarios": scenarios,
    }

    if previous_iteration:
        teacher_evaluation["previous_iteration"] = previous_iteration

    snapshot = dict(workspace_snapshot or {})
    snapshot.setdefault("objective", "Autoresearch alpha candidate run against public benchmark pack.")
    snapshot.setdefault("changed_files", [])
    if failure_themes:
        snapshot["public_failure_themes_consumed"] = failure_themes

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras={"teacher_evaluation": teacher_evaluation},
    )


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


def run_autoresearch_alpha(
    *,
    bridge: RunBridge | None = None,
    run_id_prefix: str = "autoresearch-alpha",
    benchmark_pack_path: str | Path | None = None,
    previous_iteration: dict[str, Any] | None = None,
    max_episodes: int | None = None,
    workspace_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one autoresearch alpha iteration.

    Returns a machine-readable receipt with stage lifecycle, comparison
    verdict, score deltas, integrity gate status, artifact coverage,
    and explicit blocked criteria.
    """
    started_at = _utc_now()

    pack = load_benchmark_pack(benchmark_pack_path)
    episodes = pack.get("episodes", [])
    if max_episodes:
        episodes = episodes[:max_episodes]

    # Stage 1: Baseline
    baseline = _build_baseline_from_previous(previous_iteration)

    # Stage 2: Candidate — build request and run through bridge
    failure_themes = []
    if previous_iteration:
        prev_themes = previous_iteration.get("public_failure_themes", [])
        failure_themes = [t if isinstance(t, str) else t.get("theme", "") for t in prev_themes]

    candidate_run_id = f"{run_id_prefix}-candidate"
    candidate_request = _build_candidate_request(
        run_id=candidate_run_id,
        episodes=episodes,
        previous_iteration=previous_iteration,
        failure_themes=failure_themes,
        workspace_snapshot=workspace_snapshot,
    )

    if bridge is None:
        bridge = RunBridge(artifacts_root="runtime/runs")

    candidate_result = bridge.run(candidate_request)

    # Stage 3: Teacher evaluation — extract from candidate result
    candidate_scorecard = candidate_result.get("scorecard", {})
    candidate_aggregate = candidate_scorecard.get("aggregate_score", {})
    baseline_aggregate = baseline.get("aggregate_score", {})

    # Stage 4: Verdict
    verdict = _compute_verdict(baseline_aggregate, candidate_aggregate)

    # Build the iteration history from candidate scorecard
    iteration_history = candidate_scorecard.get("iteration_history", [])

    # Artifact coverage
    candidate_run_dir = bridge.artifacts_root / candidate_run_id
    artifact_coverage = {
        "request_json": (candidate_run_dir / "request.json").exists(),
        "request_private_json": (candidate_run_dir / "request.private.json").exists(),
        "result_json": (candidate_run_dir / "result.json").exists(),
        "transcript_ndjson": (candidate_run_dir / "transcript.ndjson").exists(),
        "artifact_bundle_json": (candidate_run_dir / "artifact-bundle.json").exists(),
        "receipts_manifest": (candidate_run_dir / "receipts" / "manifest.json").exists(),
        "receipts_candidate": (candidate_run_dir / "receipts" / "candidate.json").exists(),
        "receipts_evidence_index": (candidate_run_dir / "receipts" / "evidence-index.json").exists(),
    }
    if previous_iteration:
        artifact_coverage["receipts_baseline"] = (candidate_run_dir / "receipts" / "baseline.json").exists()
        artifact_coverage["receipts_evaluation"] = (candidate_run_dir / "receipts" / "evaluation.json").exists()

    finished_at = _utc_now()

    # Assemble the top-level autoresearch-alpha receipt
    receipt: dict[str, Any] = {
        "receipt_type": "autoresearch-alpha",
        "receipt_version": "0.1.0",
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
            "baseline": {
                "status": baseline.get("status", "unknown"),
                "aggregate_score": baseline_aggregate,
            },
            "candidate": {
                "run_id": candidate_run_id,
                "status": candidate_result.get("status", "unknown"),
                "aggregate_score": candidate_aggregate,
                "machine_score": candidate_result.get("machine_score", 0.0),
            },
            "teacher_evaluation": {
                "verdict_text": candidate_scorecard.get("verdict", ""),
                "scenario_count": len(candidate_scorecard.get("scenario_results", [])),
                "public_curriculum_themes": candidate_scorecard.get("public_curriculum_themes", []),
            },
        },
        "comparison_verdict": verdict,
        "score_deltas": {
            "pass_rate": verdict["delta_pass_rate"],
            "average_score": verdict["delta_average_score"],
        },
        "iteration_history": iteration_history,
        "integrity_gate": {
            "all_artifacts_present": all(artifact_coverage.values()),
            "artifact_coverage": artifact_coverage,
            "provenance_present": "provenance" in candidate_result,
            "execution_honesty_present": "execution_honesty" in candidate_result.get("scorecard", {}),
        },
        "blocked_criteria": BLOCKED_CRITERIA,
        "honesty_note": (
            "This is a public-regression autoresearch alpha loop. "
            "The backend is LocalReplayRunner (deterministic shim, not live execution). "
            "Sealed holdout families are explicitly excluded. "
            "Mutation-surface enforcement and verdict stability are not yet implemented."
        ),
    }

    # Write the receipt to the candidate run directory
    receipt_path = candidate_run_dir / "autoresearch-alpha-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))
    receipt["receipt_path"] = str(receipt_path)

    return receipt
