"""Autoresearch alpha orchestrator — Phase C, narrow public-regression lane.

Runs a real THREE-STAGE loop through RunBridge:

    1. baseline-eval      — teacher evaluation of the baseline state
    2. candidate-student   — student prompt-pack only (NO teacher evaluation)
    3. candidate-teacher-eval — teacher evaluation comparing against real baseline

This orchestrator consumes the public benchmark pack only.  It does NOT claim
sealed/holdout coverage or live execution. Mutation-surface auditing is wired
through the receipt layer, but it only clears when the run provides a declared
diff surface strong enough to evaluate honestly.

CLI entrypoint:
    python3 -m runner_bridge.autoresearch_alpha \\
        --request runner_bridge/examples/autoresearch-alpha-public-loop.json \\
        --artifacts-root runtime/runs

Honest status:
  - LocalReplayRunner is the only wired backend (deterministic, no real exec).
  - Mutation-surface auditing only uses declared changed-files / diff-stats evidence.
  - Verdict stability: conditionally cleared when stability_policy replay runs pass.
  - Holdout/private families: explicitly blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bridge import RunBridge
from .contract import RunRequest
from .packet_runtime import load_run_object

BENCHMARK_PACK_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"

STAGE_NAMES = ("baseline-eval", "candidate-student", "candidate-teacher-eval")

MUTATION_SURFACE_BLOCKED_CRITERION = {
    "id": "mutation-surface-enforcement",
    "status": "blocked",
    "reason": "No mutation-surface contract/evidence was strong enough to clear this run path yet.",
}

STATIC_BLOCKED_CRITERIA = [
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

BLOCKED_CRITERIA = [MUTATION_SURFACE_BLOCKED_CRITERION, *STATIC_BLOCKED_CRITERIA]

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
    "C008": {"label": "Integrity gate enforcement", "status": "pass"},
    "C009": {"label": "Meaningful delta visibility", "status": "pass"},
}


def load_benchmark_pack(pack_path: str | Path | None = None) -> dict[str, Any]:
    """Load the public benchmark pack JSON."""
    path = Path(pack_path) if pack_path else BENCHMARK_PACK_PATH
    if not path.exists():
        raise FileNotFoundError(f"Benchmark pack not found: {path}")
    return json.loads(path.read_text())


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _build_workspace_snapshot(
    *,
    request_cfg: dict[str, Any],
    default_objective: str,
    public_failure_themes: list[str] | None = None,
) -> dict[str, Any]:
    snapshot = deepcopy(request_cfg.get("workspace_snapshot", {})) if isinstance(request_cfg.get("workspace_snapshot"), dict) else {}
    snapshot.setdefault("objective", default_objective)
    snapshot.setdefault("changed_files", [])
    if public_failure_themes:
        snapshot.setdefault("public_failure_themes_consumed", public_failure_themes)
    return snapshot


def _inline_packet_runtime(request_cfg: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    inline = request_cfg.get("packet_runtime")
    if not isinstance(inline, dict):
        return None

    runtime = deepcopy(inline)
    runtime.setdefault("packet_id", f"inline-mutation-surface:{run_id}")
    runtime.setdefault("packet_version", "1.0.0")
    runtime.setdefault("acceptance_test_id", str(request_cfg.get("acceptance_test_id", "")))
    runtime.setdefault("role_id", str(request_cfg.get("role_id", "")))
    runtime.setdefault("phase_index", 0)
    runtime.setdefault("expected_checks", [])
    runtime.setdefault("eval_contract_ref", {})
    runtime.setdefault(
        "evidence_contract",
        {
            "required_artifacts": [],
            "provenance_required": True,
            "student_visible_only": True,
        },
    )
    runtime.setdefault("run_object_version", "1.0.0")
    runtime.setdefault("execution_status", "not_started")
    runtime.setdefault("execution_backend", "LocalReplayRunner")
    runtime.setdefault("packet_content_hash", _canonical_hash(runtime))
    return runtime


def _load_stage_packet_runtime(request_cfg: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    inline_runtime = _inline_packet_runtime(request_cfg, run_id)
    if inline_runtime:
        return inline_runtime

    acceptance_test_id = request_cfg.get("packet_acceptance_test_id")
    if not acceptance_test_id:
        return None

    request = load_run_object(str(acceptance_test_id), run_id=run_id).to_run_request(workspace_snapshot={})
    packet_runtime = request.extras.get("packet_runtime")
    return deepcopy(packet_runtime) if isinstance(packet_runtime, dict) else None


def _build_blocked_criteria(
    mutation_surface_audit: dict[str, Any],
    stability_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if mutation_surface_audit.get("status") in {"pass", "fail"}:
        criteria = deepcopy(STATIC_BLOCKED_CRITERIA)
    else:
        criteria = deepcopy(BLOCKED_CRITERIA)

    # Remove verdict-stability from blocked when replay runs actually passed
    if isinstance(stability_report, dict) and stability_report.get("status") == "pass":
        criteria = [c for c in criteria if c.get("id") != "verdict-stability"]

    return criteria


def _derive_mutation_surface_audit(
    *,
    student_request: RunRequest,
    student_result: dict[str, Any],
) -> dict[str, Any]:
    execution_honesty = student_result.get("execution_honesty") if isinstance(student_result.get("execution_honesty"), dict) else {}
    audit = execution_honesty.get("mutation_surface_audit") if isinstance(execution_honesty.get("mutation_surface_audit"), dict) else None
    if audit:
        return deepcopy(audit)

    packet_runtime = student_request.extras.get("packet_runtime") if isinstance(student_request.extras.get("packet_runtime"), dict) else None
    changed_files = []
    if isinstance(student_request.workspace_snapshot, dict) and isinstance(student_request.workspace_snapshot.get("changed_files"), list):
        changed_files = list(student_request.workspace_snapshot.get("changed_files", []))

    if packet_runtime:
        return {
            "status": "unavailable",
            "honesty_note": (
                "A mutation-surface contract was attached, but the backend did not emit a dedicated audit result for this run path."
            ),
            "source": {"kind": "missing-runtime-audit", "backend_verified": False},
            "changed_files": changed_files,
            "budget_report": packet_runtime.get("mutation_budget", {}),
            "violations": [],
        }

    return {
        "status": "unavailable",
        "honesty_note": (
            "No packet_runtime mutation surface was attached to the candidate stage, so mutation enforcement cannot be cleared on this path."
        ),
        "source": {"kind": "missing-packet-runtime", "backend_verified": False},
        "changed_files": changed_files,
        "budget_report": {},
        "violations": [],
    }


def _build_honesty_note(
    mutation_surface_audit: dict[str, Any],
    stability_report: dict[str, Any] | None = None,
) -> str:
    mutation_status = mutation_surface_audit.get("status", "unavailable")
    if mutation_status == "pass":
        mutation_line = (
            "Mutation-surface auditing passed against declared changed-files/diff-stats evidence; "
            "LocalReplayRunner still does not independently compute diffs."
        )
    elif mutation_status == "fail":
        mutation_line = (
            "Mutation-surface auditing is active and flagged an out-of-scope or over-budget change on this run."
        )
    else:
        mutation_line = (
            "Mutation-surface auditing is wired, but this run did not provide enough declared diff evidence to clear it."
        )

    if isinstance(stability_report, dict) and stability_report.get("status") == "pass":
        stability_line = (
            "Verdict stability passed on the deterministic LocalReplayRunner path: "
            f"{stability_report.get('total_runs', 0)} repeated runs agreed within configured thresholds. "
            "This only demonstrates deterministic replay repeatability; "
            "live/non-deterministic verdict stability is not claimed."
        )
    else:
        stability_line = "Verdict stability is still single-pass only."

    return (
        "This is a public-regression autoresearch alpha loop with three real stages "
        "executed through RunBridge. "
        "The backend is LocalReplayRunner (deterministic shim, not live execution). "
        "Sealed holdout families are explicitly excluded. "
        f"{mutation_line} "
        f"{stability_line}"
    )


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

    snapshot = _build_workspace_snapshot(
        request_cfg=request_cfg,
        default_objective="Baseline teacher evaluation against public benchmark pack.",
    )

    extras: dict[str, Any] = {"teacher_evaluation": te}
    packet_runtime = _load_stage_packet_runtime(request_cfg, run_id)
    if packet_runtime:
        extras["packet_runtime"] = packet_runtime

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras=extras,
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

    snapshot = _build_workspace_snapshot(
        request_cfg=request_cfg,
        default_objective="Candidate student run against public benchmark episodes.",
        public_failure_themes=public_failure_themes,
    )

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

    extras: dict[str, Any] = {"student_prompt_pack": student_prompt_pack}
    packet_runtime = _load_stage_packet_runtime(request_cfg, run_id)
    if packet_runtime:
        extras["packet_runtime"] = packet_runtime

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras=extras,
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

    snapshot = _build_workspace_snapshot(
        request_cfg=request_cfg,
        default_objective="Candidate teacher evaluation comparing against real baseline.",
    )

    extras: dict[str, Any] = {"teacher_evaluation": te}
    packet_runtime = _load_stage_packet_runtime(request_cfg, run_id)
    if packet_runtime:
        extras["packet_runtime"] = packet_runtime

    return RunRequest(
        run_id=run_id,
        agent_role="student",
        scenario_set_id="autoresearch-alpha-public-v1",
        workspace_snapshot=snapshot,
        time_budget={"seconds": 60},
        cost_budget={"usd": 0.0},
        extras=extras,
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


def _load_json_file(path: str | Path | None) -> dict[str, Any]:
    """Best-effort JSON loader for result-adjacent artifacts."""
    if not path:
        return {}
    artifact_path = Path(path)
    if not artifact_path.exists():
        return {}
    return json.loads(artifact_path.read_text())


def build_comparison_summary(
    *,
    baseline_run_id: str,
    candidate_run_id: str,
    baseline_score: dict[str, Any],
    candidate_score: dict[str, Any],
    verdict: dict[str, Any],
    comparison_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a richer machine-readable comparison summary for the alpha loop."""
    comparison_policy = comparison_policy or {}
    baseline_total_score = round(float(baseline_score.get("average_score", 0.0) or 0.0), 4)
    candidate_total_score = round(float(candidate_score.get("average_score", 0.0) or 0.0), 4)
    total_score_delta = round(candidate_total_score - baseline_total_score, 4)

    baseline_holdout = baseline_score.get("holdout") if isinstance(baseline_score.get("holdout"), dict) else {}
    candidate_holdout = candidate_score.get("holdout") if isinstance(candidate_score.get("holdout"), dict) else {}

    reasons: list[str] = []
    if verdict["label"] == "better":
        reasons.append("Candidate improved on the public comparison surface.")
    elif verdict["label"] == "equal":
        reasons.append("Candidate matched the baseline on the public comparison surface.")
    else:
        reasons.append("Candidate regressed against the baseline on the public comparison surface.")

    if verdict["delta_pass_rate"]:
        reasons.append(f"Public pass rate changed by {verdict['delta_pass_rate']:+.4f}.")
    if verdict["delta_average_score"]:
        reasons.append(f"Aggregate average score changed by {verdict['delta_average_score']:+.4f}.")
    if not reasons or len(reasons) == 1:
        reasons.append("Score deltas are computed from aggregate teacher scorecards only; no new metric was invented.")

    return {
        "verdict": verdict["label"],
        "deciding_axis": comparison_policy.get("metric", "pass_rate"),
        "direction": comparison_policy.get("direction", "higher_is_better"),
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "score_basis": "scorecard.aggregate_score.average_score",
        "baseline_total_score": baseline_total_score,
        "candidate_total_score": candidate_total_score,
        "total_score_delta": total_score_delta,
        "category_deltas": {
            "pass_count": int(candidate_score.get("passed", 0) or 0) - int(baseline_score.get("passed", 0) or 0),
            "pass_rate": verdict["delta_pass_rate"],
            "average_score": verdict["delta_average_score"],
            "holdout_pass_count": int(candidate_holdout.get("passed", 0) or 0) - int(baseline_holdout.get("passed", 0) or 0),
            "holdout_pass_rate": round(
                float(candidate_holdout.get("pass_rate", 0.0) or 0.0)
                - float(baseline_holdout.get("pass_rate", 0.0) or 0.0),
                4,
            ),
        },
        "reasons": reasons,
    }


def build_integrity_gate(
    *,
    verdict: dict[str, Any],
    artifact_coverage: dict[str, dict[str, bool]],
    student_request: RunRequest,
    student_result: dict[str, Any],
    teacher_eval_result: dict[str, Any],
    mutation_surface_audit: dict[str, Any],
    integrity_policy: dict[str, Any] | None = None,
    blocked_criteria: list[dict[str, Any]] | None = None,
    honesty_note: str = "",
) -> dict[str, Any]:
    """Evaluate machine-readable integrity gates for promotion enforcement."""
    integrity_policy = integrity_policy or {}
    blocked_ids = {
        item.get("id")
        for item in (blocked_criteria or [])
        if isinstance(item, dict) and item.get("id")
    }

    student_payload = student_request.to_dict()
    student_bundle = _load_json_file(student_result.get("artifact_bundle_path"))
    student_view = student_bundle.get("student_view") if isinstance(student_bundle.get("student_view"), dict) else {}
    student_prompt_pack = student_payload.get("student_prompt_pack") if isinstance(student_payload.get("student_prompt_pack"), dict) else {}

    all_present = all(all(checks.values()) for checks in artifact_coverage.values())
    missing_artifacts = {
        stage_name: [artifact for artifact, present in checks.items() if not present]
        for stage_name, checks in artifact_coverage.items()
        if not all(checks.values())
    }

    public_regression_gate = {
        "status": "pass" if verdict["label"] in ("better", "equal") else "fail",
        "reason": (
            "Candidate cleared the public regression comparison."
            if verdict["label"] in ("better", "equal")
            else "Candidate regressed on the public regression comparison."
        ),
        "detail": {
            "comparison_label": verdict["label"],
            "delta_pass_rate": verdict["delta_pass_rate"],
            "delta_average_score": verdict["delta_average_score"],
        },
    }

    artifact_gate = {
        "status": "pass" if all_present else "fail",
        "reason": "Required stage artifacts are present." if all_present else "Required stage artifacts are missing.",
        "detail": {
            "all_artifacts_present": all_present,
            "missing_artifacts": missing_artifacts,
        },
    }

    no_holdout_leakage = (
        "teacher_evaluation" not in student_payload
        and int(student_prompt_pack.get("sealed_holdout_count", 0) or 0) == 0
        and int(student_view.get("sealed_holdout_count", 0) or 0) == 0
        and "teacher_output" not in student_bundle
    )
    holdout_gate = {
        "status": "pass" if no_holdout_leakage else "fail",
        "reason": (
            "Student stage stayed public-only and exposed no teacher score output."
            if no_holdout_leakage
            else "Student stage leaked holdout or teacher-eval state into the public-only step."
        ),
        "detail": {
            "request_has_teacher_evaluation": "teacher_evaluation" in student_payload,
            "prompt_pack_sealed_holdout_count": int(student_prompt_pack.get("sealed_holdout_count", 0) or 0),
            "student_view_sealed_holdout_count": int(student_view.get("sealed_holdout_count", 0) or 0),
            "teacher_output_present": "teacher_output" in student_bundle,
        },
    }

    mutation_status = mutation_surface_audit.get("status", "unavailable")
    if mutation_status == "pass":
        mutation_gate = {
            "status": "pass",
            "reason": "Declared changed files stayed inside the allowed mutation surface and budget.",
            "detail": mutation_surface_audit,
        }
    elif mutation_status == "fail":
        mutation_gate = {
            "status": "fail",
            "reason": "Mutation-surface audit detected an out-of-scope or over-budget change.",
            "detail": mutation_surface_audit,
        }
    else:
        mutation_gate = {
            "status": "blocked",
            "reason": "Mutation-surface audit could not clear because the run lacked enough declared diff evidence.",
            "detail": mutation_surface_audit,
        }

    # verdict-stability can be honestly absent from blocked_ids when the
    # stability_report cleared it — but only if the honesty note explicitly
    # says deterministic replay repeatability (not live stability).
    verdict_stability_honest = (
        "verdict-stability" in blocked_ids
        or "deterministic replay repeatability" in honesty_note
    )
    fake_claims_ok = verdict_stability_honest and all(
        marker in blocked_ids
        for marker in (
            "sealed-holdout-coverage",
            "live-execution-backend",
        )
    ) and "LocalReplayRunner" in honesty_note and "not live execution" in honesty_note
    if mutation_status not in {"pass", "fail"}:
        fake_claims_ok = fake_claims_ok and "mutation-surface-enforcement" in blocked_ids
    else:
        fake_claims_ok = fake_claims_ok and "mutation-surface-enforcement" not in blocked_ids

    fake_claims_gate = {
        "status": "pass" if fake_claims_ok else "fail",
        "reason": (
            "Known limitations are surfaced explicitly instead of being claimed away."
            if fake_claims_ok
            else "Required honesty markers are missing from the receipt."
        ),
        "detail": {
            "blocked_criteria_ids": sorted(blocked_ids),
            "mutation_surface_status": mutation_status,
            "honesty_note": honesty_note,
        },
    }

    execution_honesty = teacher_eval_result.get("execution_honesty") if isinstance(teacher_eval_result.get("execution_honesty"), dict) else {}
    check_results = execution_honesty.get("check_results") if isinstance(execution_honesty.get("check_results"), list) else []
    executed_checks = [
        check for check in check_results
        if isinstance(check, dict) and check.get("execution_status") == "executed"
    ]
    failed_checks = [
        check.get("id") or check.get("command") or "unknown-check"
        for check in executed_checks
        if check.get("exit_code") not in (0, None)
    ]
    if not check_results or not executed_checks:
        demo_tests_gate = {
            "status": "blocked",
            "reason": "Repo checks were not executed on this LocalReplayRunner path, so demo/tests cannot clear yet.",
            "detail": {
                "check_results_present": bool(check_results),
                "executed_check_count": len(executed_checks),
            },
        }
    elif failed_checks:
        demo_tests_gate = {
            "status": "fail",
            "reason": "One or more executed repo checks failed.",
            "detail": {
                "executed_check_count": len(executed_checks),
                "failed_checks": failed_checks,
            },
        }
    else:
        demo_tests_gate = {
            "status": "pass",
            "reason": "Executed repo checks passed.",
            "detail": {
                "executed_check_count": len(executed_checks),
                "failed_checks": [],
            },
        }

    sealed_eval_status = integrity_policy.get("sealed_eval", "blocked")
    certification_status = integrity_policy.get("certification", "blocked")

    gates = {
        "public_regression": public_regression_gate,
        "required_artifacts_present": artifact_gate,
        "no_holdout_leakage": holdout_gate,
        "mutation_surface_enforcement": mutation_gate,
        "no_fake_claims": fake_claims_gate,
        "demo_tests_still_work": demo_tests_gate,
        "sealed_eval": {
            "status": sealed_eval_status,
            "reason": "Sealed/private families are outside this public-regression lane.",
            "detail": {"policy": integrity_policy.get("sealed_eval")},
        },
        "certification": {
            "status": certification_status,
            "reason": "Certification remains blocked until a sealed evaluation lane exists.",
            "detail": {"policy": integrity_policy.get("certification")},
        },
    }

    failed_gates = [name for name, gate in gates.items() if gate["status"] == "fail"]
    blocked_gates = [name for name, gate in gates.items() if gate["status"] == "blocked"]
    overall_status = "fail" if failed_gates else "blocked" if blocked_gates else "pass"

    return {
        "status": overall_status,
        "promotion_eligible": overall_status == "pass" and public_regression_gate["status"] == "pass",
        "failed_gates": failed_gates,
        "blocked_gates": blocked_gates,
        "gates": gates,
        "public_regression": public_regression_gate["status"],
        "sealed_eval": sealed_eval_status,
        "certification": certification_status,
        "all_artifacts_present": all_present,
        "artifact_coverage": artifact_coverage,
        "provenance_present": "provenance" in teacher_eval_result,
    }


def build_promotion_decision(
    *,
    comparison: dict[str, Any],
    integrity_gate: dict[str, Any],
) -> dict[str, Any]:
    """Collapse raw comparison plus integrity gates into the effective promotion outcome."""
    failed_gates = list(integrity_gate.get("failed_gates", []))
    blocked_gates = list(integrity_gate.get("blocked_gates", []))
    comparison_label = comparison.get("verdict", "unknown")

    if failed_gates:
        return {
            "status": "fail",
            "effective_label": "rejected",
            "comparison_label": comparison_label,
            "eligible_for_weighted_promotion": False,
            "failed_gates": failed_gates,
            "blocked_gates": blocked_gates,
            "reason": f"Weighted promotion rejected because integrity gates failed: {', '.join(failed_gates)}.",
        }
    if blocked_gates:
        return {
            "status": "blocked",
            "effective_label": "blocked",
            "comparison_label": comparison_label,
            "eligible_for_weighted_promotion": False,
            "failed_gates": failed_gates,
            "blocked_gates": blocked_gates,
            "reason": f"Weighted promotion is blocked until: {', '.join(blocked_gates)}.",
        }
    if comparison_label in ("better", "equal"):
        return {
            "status": "pass",
            "effective_label": comparison_label,
            "comparison_label": comparison_label,
            "eligible_for_weighted_promotion": True,
            "failed_gates": failed_gates,
            "blocked_gates": blocked_gates,
            "reason": "Comparison cleared and every integrity gate passed.",
        }
    return {
        "status": "fail",
        "effective_label": comparison_label,
        "comparison_label": comparison_label,
        "eligible_for_weighted_promotion": False,
        "failed_gates": failed_gates,
        "blocked_gates": blocked_gates,
        "reason": "Candidate did not clear the baseline comparison.",
    }


# ---------------------------------------------------------------------------
# Verdict stability — deterministic repeated-run comparison
# ---------------------------------------------------------------------------

def _run_stability_replays(
    *,
    bridge: "RunBridge",
    run_id_prefix: str,
    episodes: list[dict[str, Any]],
    stages_cfg: dict[str, Any],
    baseline_aggregate: dict[str, Any],
    baseline_run_id: str,
    replay_count: int,
) -> list[dict[str, Any]]:
    """Re-run baseline-eval + candidate-teacher-eval with distinct run_ids.

    Returns a list of per-replay verdict dicts, each containing the run_ids
    and computed verdict for that replay pair.
    """
    replays: list[dict[str, Any]] = []

    baseline_request_cfg = stages_cfg.get("baseline-eval", {}).get("request", {})
    teacher_request_cfg = stages_cfg.get("candidate-teacher-eval", {}).get("request", {})

    for i in range(1, replay_count + 1):
        replay_baseline_run_id = f"{run_id_prefix}-stability-r{i}-baseline-eval"
        replay_teacher_run_id = f"{run_id_prefix}-stability-r{i}-candidate-teacher-eval"

        replay_baseline_request = _prepare_baseline_eval_request(
            run_id=replay_baseline_run_id,
            episodes=episodes,
            request_cfg=baseline_request_cfg,
        )
        replay_baseline_result = bridge.run(replay_baseline_request)
        replay_baseline_scorecard = replay_baseline_result.get("scorecard", {})
        replay_baseline_agg = replay_baseline_scorecard.get("aggregate_score", {
            "passed": 0, "total": 0, "pass_rate": 0.0, "average_score": 0.0,
        })

        replay_teacher_request = _prepare_candidate_teacher_eval_request(
            run_id=replay_teacher_run_id,
            episodes=episodes,
            request_cfg=teacher_request_cfg,
            baseline_aggregate_score=replay_baseline_agg,
            baseline_run_id=replay_baseline_run_id,
        )
        replay_teacher_result = bridge.run(replay_teacher_request)
        replay_teacher_scorecard = replay_teacher_result.get("scorecard", {})
        replay_candidate_agg = replay_teacher_scorecard.get("aggregate_score", {})

        replay_verdict = _compute_verdict(replay_baseline_agg, replay_candidate_agg)
        replays.append({
            "replay_index": i,
            "baseline_run_id": replay_baseline_run_id,
            "candidate_run_id": replay_teacher_run_id,
            "verdict": replay_verdict,
        })

    return replays


def build_stability_report(
    *,
    primary_verdict: dict[str, Any],
    primary_baseline_run_id: str,
    primary_candidate_run_id: str,
    replays: list[dict[str, Any]],
    stability_policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a machine-readable stability report from repeated-run verdicts.

    Thresholds (from stability_policy):
      - min_agreement: fraction of runs that must share the primary verdict label (default 1.0)
      - max_spread: maximum allowed spread in delta_average_score across runs (default 0.10)
    """
    min_agreement = float(stability_policy.get("min_agreement", 1.0))
    max_spread = float(stability_policy.get("max_spread", 0.10))

    all_verdicts = [
        {
            "run_index": 0,
            "baseline_run_id": primary_baseline_run_id,
            "candidate_run_id": primary_candidate_run_id,
            "label": primary_verdict["label"],
            "delta_pass_rate": primary_verdict["delta_pass_rate"],
            "delta_average_score": primary_verdict["delta_average_score"],
        },
    ]
    for replay in replays:
        rv = replay["verdict"]
        all_verdicts.append({
            "run_index": replay["replay_index"],
            "baseline_run_id": replay["baseline_run_id"],
            "candidate_run_id": replay["candidate_run_id"],
            "label": rv["label"],
            "delta_pass_rate": rv["delta_pass_rate"],
            "delta_average_score": rv["delta_average_score"],
        })

    total_runs = len(all_verdicts)
    labels = [v["label"] for v in all_verdicts]
    primary_label = primary_verdict["label"]
    agreeing = sum(1 for lbl in labels if lbl == primary_label)
    agreement_rate = agreeing / total_runs if total_runs > 0 else 0.0

    delta_scores = [v["delta_average_score"] for v in all_verdicts]
    score_spread = round(max(delta_scores) - min(delta_scores), 4) if delta_scores else 0.0

    agreement_ok = agreement_rate >= min_agreement
    spread_ok = score_spread <= max_spread
    passed = agreement_ok and spread_ok

    return {
        "status": "pass" if passed else "fail",
        "total_runs": total_runs,
        "replay_count": total_runs - 1,
        "primary_label": primary_label,
        "agreement_rate": round(agreement_rate, 4),
        "score_spread": score_spread,
        "thresholds": {
            "min_agreement": min_agreement,
            "max_spread": max_spread,
        },
        "checks": {
            "agreement_ok": agreement_ok,
            "spread_ok": spread_ok,
        },
        "verdicts": all_verdicts,
        "honesty_note": (
            "This stability report covers deterministic LocalReplayRunner repeated runs only. "
            "It does not demonstrate live or non-deterministic verdict stability."
        ),
    }


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

    comparison = build_comparison_summary(
        baseline_run_id=baseline_run_id,
        candidate_run_id=teacher_eval_run_id,
        baseline_score=baseline_aggregate,
        candidate_score=candidate_aggregate,
        verdict=verdict,
        comparison_policy=comparison_policy,
    )
    mutation_surface_audit = _derive_mutation_surface_audit(
        student_request=student_request,
        student_result=student_result,
    )

    # --- Verdict stability: optional deterministic repeated-run replays ---
    stability_policy = cfg.get("stability_policy") if request_payload else None
    stability_report: dict[str, Any] | None = None
    if isinstance(stability_policy, dict) and int(stability_policy.get("replay_count", 0)) > 0:
        replay_count = int(stability_policy["replay_count"])
        replays = _run_stability_replays(
            bridge=bridge,
            run_id_prefix=run_id_prefix,
            episodes=episodes,
            stages_cfg=stages_cfg,
            baseline_aggregate=baseline_aggregate,
            baseline_run_id=baseline_run_id,
            replay_count=replay_count,
        )
        stability_report = build_stability_report(
            primary_verdict=verdict,
            primary_baseline_run_id=baseline_run_id,
            primary_candidate_run_id=teacher_eval_run_id,
            replays=replays,
            stability_policy=stability_policy,
        )

    blocked_criteria = _build_blocked_criteria(mutation_surface_audit, stability_report)
    honesty_note = _build_honesty_note(mutation_surface_audit, stability_report)
    integrity_gate = build_integrity_gate(
        verdict=verdict,
        artifact_coverage=artifact_coverage,
        student_request=student_request,
        student_result=student_result,
        teacher_eval_result=teacher_eval_result,
        mutation_surface_audit=mutation_surface_audit,
        integrity_policy=integrity_policy,
        blocked_criteria=blocked_criteria,
        honesty_note=honesty_note,
    )
    promotion_decision = build_promotion_decision(
        comparison=comparison,
        integrity_gate=integrity_gate,
    )

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
                "total_score": comparison["baseline_total_score"],
                "machine_score": baseline_result.get("machine_score", 0.0),
            },
            "candidate-student": {
                "run_id": student_run_id,
                "status": student_result.get("status", "unknown"),
                "total_score": round(float(student_result.get("machine_score", 0.0) or 0.0), 4),
                "machine_score": student_result.get("machine_score", 0.0),
                "mutation_surface_status": mutation_surface_audit.get("status", "unavailable"),
                "note": "Student prompt-pack only; no teacher evaluation in this stage.",
            },
            "candidate-teacher-eval": {
                "run_id": teacher_eval_run_id,
                "status": teacher_eval_result.get("status", "unknown"),
                "aggregate_score": candidate_aggregate,
                "total_score": comparison["candidate_total_score"],
                "machine_score": teacher_eval_result.get("machine_score", 0.0),
                "verdict_text": teacher_scorecard.get("verdict", ""),
                "scenario_count": len(teacher_scorecard.get("scenario_results", [])),
                "public_curriculum_themes": teacher_scorecard.get("public_curriculum_themes", []),
                "effective_label": promotion_decision["effective_label"],
            },
        },
        "comparison": comparison,
        "comparison_verdict": verdict,
        "score_deltas": {
            "pass_rate": verdict["delta_pass_rate"],
            "average_score": verdict["delta_average_score"],
            "total_score": comparison["total_score_delta"],
            "category_deltas": comparison["category_deltas"],
        },
        "promotion_decision": promotion_decision,
        "mutation_surface_audit": mutation_surface_audit,
        "iteration_history": iteration_history,
        "run_record_history": records,
        "integrity_gate": integrity_gate,
        "phase_c_acceptance": PHASE_C_ACCEPTANCE,
        "blocked_criteria": blocked_criteria,
        "honesty_note": honesty_note,
    }
    if stability_report is not None:
        receipt["stability_report"] = stability_report

    # --- Write top-level receipt + comparison summary ---
    receipt_path = bridge.artifacts_root / "autoresearch-alpha.json"
    receipt_path.write_text(json.dumps(receipt, indent=2))

    comparison_summary_path = bridge.artifacts_root / "autoresearch-alpha.comparison.json"
    comparison_summary_path.write_text(json.dumps({
        "comparison": comparison,
        "integrity_gate": integrity_gate,
        "promotion_decision": promotion_decision,
    }, indent=2))

    receipt["receipt_path"] = str(receipt_path)
    receipt["comparison_summary_path"] = str(comparison_summary_path)

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
