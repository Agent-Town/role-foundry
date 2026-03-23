"""Promotion gate evaluation for the frozen Frontend/Product Engineer curriculum.

This module defines the contract surface for D002 (private-holdout gate),
D003 (repeated-run stability gate), and D004 (regression gate).

HONESTY BOUNDARY
----------------
These helpers evaluate gate *artifacts* — scorecards, run-object lists,
regression-pack receipts — that a teacher or automated pipeline supplies.
They do NOT:
  - Execute live runs (that is the runner bridge's job).
  - Track real private-holdout values in git (those are teacher-only, local).
  - Automate repeated-run scheduling (future runtime work).

The module produces machine-readable GateVerdict and PromotionReport
objects so that downstream tooling can decide promotion without parsing
prose.  Every verdict carries an ``availability`` field that honestly
reports whether the underlying data was actually supplied or is still
placeholder/unavailable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .curriculum import (
    FROZEN_DIMENSIONS,
    PROMOTION_CRITICAL_FLOOR,
    PROMOTION_HOLDOUT_THRESHOLD,
    PROMOTION_PUBLIC_THRESHOLD,
    TASK_MIN_DIMENSION,
    TASK_PASS_THRESHOLD,
    check_task_pass,
    score_map_from_scorecard,
    validate_scorecard,
)


# ---------------------------------------------------------------------------
# Gate status vocabulary
# ---------------------------------------------------------------------------

class GateStatus(str, Enum):
    """Machine-readable outcome of a single promotion gate check."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"  # data was not supplied
    NOT_EXECUTED = "not_executed"  # gate logic exists but was never run


class DataAvailability(str, Enum):
    """Honest marker for whether gate input data is real."""

    LIVE = "live"  # came from actual execution
    SAMPLE = "sample"  # illustrative fixture / example_only
    MISSING = "missing"  # not provided at all


# ---------------------------------------------------------------------------
# Gate verdicts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateVerdict:
    """Result of evaluating a single promotion gate."""

    gate_id: str
    status: GateStatus
    availability: DataAvailability
    detail: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


# ---------------------------------------------------------------------------
# D002 — Private-holdout promotion gate
# ---------------------------------------------------------------------------

def evaluate_holdout_gate(
    public_scorecard: dict[str, Any] | None,
    holdout_scorecard: dict[str, Any] | None,
) -> GateVerdict:
    """Evaluate D002: private-holdout scoring gate.

    Returns a GateVerdict that is UNAVAILABLE when holdout data is missing
    (the honest default — we never fake holdout scores).
    """
    if public_scorecard is None:
        return GateVerdict(
            gate_id="D002",
            status=GateStatus.UNAVAILABLE,
            availability=DataAvailability.MISSING,
            reason="Public scorecard not provided.",
        )

    public_scores = score_map_from_scorecard(public_scorecard)
    public_weighted = _weighted_score(public_scores)
    public_met = public_weighted >= PROMOTION_PUBLIC_THRESHOLD

    # Critical-dimension floors on public side
    critical_ok, critical_detail = _check_critical_floors(public_scores)

    if holdout_scorecard is None:
        is_example = public_scorecard.get("meta", {}).get("example_only", False)
        return GateVerdict(
            gate_id="D002",
            status=GateStatus.UNAVAILABLE,
            availability=DataAvailability.SAMPLE if is_example else DataAvailability.MISSING,
            detail={
                "public_weighted_score": round(public_weighted, 4),
                "public_threshold_met": public_met,
                "critical_floors": critical_detail,
                "holdout_weighted_score": None,
                "holdout_threshold_met": None,
            },
            reason=(
                "Private-holdout scorecard not provided. "
                "Promotion cannot proceed without holdout evaluation."
            ),
        )

    holdout_scores = score_map_from_scorecard(holdout_scorecard)
    holdout_weighted = _weighted_score(holdout_scores)
    holdout_met = holdout_weighted >= PROMOTION_HOLDOUT_THRESHOLD

    holdout_critical_ok, holdout_critical_detail = _check_critical_floors(holdout_scores)

    all_passed = public_met and holdout_met and critical_ok and holdout_critical_ok

    is_example = (
        public_scorecard.get("meta", {}).get("example_only", False)
        or holdout_scorecard.get("meta", {}).get("example_only", False)
    )

    return GateVerdict(
        gate_id="D002",
        status=GateStatus.PASSED if all_passed else GateStatus.FAILED,
        availability=DataAvailability.SAMPLE if is_example else DataAvailability.LIVE,
        detail={
            "public_weighted_score": round(public_weighted, 4),
            "public_threshold_met": public_met,
            "holdout_weighted_score": round(holdout_weighted, 4),
            "holdout_threshold_met": holdout_met,
            "public_critical_floors": critical_detail,
            "holdout_critical_floors": holdout_critical_detail,
        },
        reason="" if all_passed else "One or more promotion thresholds not met.",
    )


# ---------------------------------------------------------------------------
# D003 — Repeated-run stability gate
# ---------------------------------------------------------------------------

STABILITY_REQUIRED_RUNS = 3
STABILITY_MIN_PASSING = 2
STABILITY_MAX_SPREAD = 0.10


def evaluate_stability_gate(
    run_scorecards: list[dict[str, Any]] | None,
) -> GateVerdict:
    """Evaluate D003: repeated-run stability gate.

    Expects a list of 3 scorecards from reruns of the same candidate ×
    same task packet × same contract version.  Returns UNAVAILABLE when
    the list is missing or has fewer than STABILITY_REQUIRED_RUNS entries.
    """
    if not run_scorecards:
        return GateVerdict(
            gate_id="D003",
            status=GateStatus.UNAVAILABLE,
            availability=DataAvailability.MISSING,
            reason=(
                f"Stability gate requires {STABILITY_REQUIRED_RUNS} run scorecards; "
                f"0 provided."
            ),
        )

    if len(run_scorecards) < STABILITY_REQUIRED_RUNS:
        return GateVerdict(
            gate_id="D003",
            status=GateStatus.UNAVAILABLE,
            availability=DataAvailability.MISSING,
            detail={"runs_provided": len(run_scorecards)},
            reason=(
                f"Stability gate requires {STABILITY_REQUIRED_RUNS} run scorecards; "
                f"{len(run_scorecards)} provided."
            ),
        )

    is_example = any(
        sc.get("meta", {}).get("example_only", False) for sc in run_scorecards
    )

    scores_per_run: list[dict[str, float]] = []
    weighted_scores: list[float] = []
    passing_count = 0

    for sc in run_scorecards[:STABILITY_REQUIRED_RUNS]:
        scores = score_map_from_scorecard(sc)
        ws = _weighted_score(scores)
        scores_per_run.append(scores)
        weighted_scores.append(ws)
        if check_task_pass(scores):
            passing_count += 1

    spread = max(weighted_scores) - min(weighted_scores)
    enough_passing = passing_count >= STABILITY_MIN_PASSING
    spread_ok = spread <= STABILITY_MAX_SPREAD

    # Critical-dimension flip detection
    critical_flip = _detect_critical_flip(scores_per_run)

    all_passed = enough_passing and spread_ok and not critical_flip

    return GateVerdict(
        gate_id="D003",
        status=GateStatus.PASSED if all_passed else GateStatus.FAILED,
        availability=DataAvailability.SAMPLE if is_example else DataAvailability.LIVE,
        detail={
            "runs_evaluated": len(weighted_scores),
            "passing_count": passing_count,
            "passing_required": STABILITY_MIN_PASSING,
            "weighted_scores": [round(w, 4) for w in weighted_scores],
            "spread": round(spread, 4),
            "spread_max": STABILITY_MAX_SPREAD,
            "critical_dimension_flip": critical_flip,
        },
        reason="" if all_passed else _stability_failure_reason(
            enough_passing, spread_ok, critical_flip
        ),
    )


# ---------------------------------------------------------------------------
# D004 — Regression gate
# ---------------------------------------------------------------------------

REGRESSION_MIN_PASS_RATE = 0.90


def evaluate_regression_gate(
    regression_results: list[dict[str, Any]] | None,
    promoted_baseline_pass_rate: float | None = None,
) -> GateVerdict:
    """Evaluate D004: regression gate.

    ``regression_results`` is a list of per-task results from re-running
    the regression pack (last 10 promoted public tasks, or all if < 10).
    Each entry must have at minimum:
        {"task_id": str, "passed": bool, "critical_regression": bool}

    Returns UNAVAILABLE when regression results are missing.
    """
    if not regression_results:
        return GateVerdict(
            gate_id="D004",
            status=GateStatus.UNAVAILABLE,
            availability=DataAvailability.MISSING,
            reason="No regression-pack results provided.",
        )

    is_example = any(
        r.get("example_only", False) for r in regression_results
    )

    total = len(regression_results)
    passed = sum(1 for r in regression_results if r.get("passed", False))
    critical_regressions = sum(
        1 for r in regression_results if r.get("critical_regression", False)
    )
    pass_rate = passed / total if total > 0 else 0.0

    no_critical = critical_regressions == 0
    rate_ok = pass_rate >= REGRESSION_MIN_PASS_RATE
    baseline_ok = (
        promoted_baseline_pass_rate is None
        or pass_rate >= promoted_baseline_pass_rate
    )

    all_passed = no_critical and rate_ok and baseline_ok

    return GateVerdict(
        gate_id="D004",
        status=GateStatus.PASSED if all_passed else GateStatus.FAILED,
        availability=DataAvailability.SAMPLE if is_example else DataAvailability.LIVE,
        detail={
            "total_tasks": total,
            "passed": passed,
            "critical_regressions": critical_regressions,
            "pass_rate": round(pass_rate, 4),
            "pass_rate_min": REGRESSION_MIN_PASS_RATE,
            "promoted_baseline_pass_rate": promoted_baseline_pass_rate,
            "baseline_non_regression": baseline_ok,
        },
        reason="" if all_passed else _regression_failure_reason(
            no_critical, rate_ok, baseline_ok, critical_regressions, pass_rate
        ),
    )


# ---------------------------------------------------------------------------
# Promotion report — combines all gates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PromotionReport:
    """Aggregated promotion decision from all gates."""

    role_id: str
    evaluation_contract_id: str
    evaluation_contract_version: str
    candidate_id: str
    gates: list[GateVerdict]
    promotion_ready: bool
    reason: str
    honesty_notice: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "evaluation_contract_id": self.evaluation_contract_id,
            "evaluation_contract_version": self.evaluation_contract_version,
            "candidate_id": self.candidate_id,
            "gates": [
                {
                    "gate_id": g.gate_id,
                    "status": g.status.value,
                    "availability": g.availability.value,
                    "detail": g.detail,
                    "reason": g.reason,
                }
                for g in self.gates
            ],
            "promotion_ready": self.promotion_ready,
            "reason": self.reason,
            "honesty_notice": self.honesty_notice,
        }

    def content_hash(self) -> str:
        """Stable hash for deduplication / provenance."""
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


def build_promotion_report(
    *,
    role_id: str,
    evaluation_contract_id: str,
    evaluation_contract_version: str,
    candidate_id: str,
    public_scorecard: dict[str, Any] | None = None,
    holdout_scorecard: dict[str, Any] | None = None,
    stability_scorecards: list[dict[str, Any]] | None = None,
    regression_results: list[dict[str, Any]] | None = None,
    promoted_baseline_pass_rate: float | None = None,
) -> PromotionReport:
    """Build a full promotion report by evaluating all three gates.

    Any gate whose input data is missing will be reported as UNAVAILABLE
    rather than silently skipped.  promotion_ready is True only when
    every gate is PASSED.
    """
    d002 = evaluate_holdout_gate(public_scorecard, holdout_scorecard)
    d003 = evaluate_stability_gate(stability_scorecards)
    d004 = evaluate_regression_gate(regression_results, promoted_baseline_pass_rate)

    gates = [d002, d003, d004]
    all_passed = all(g.status == GateStatus.PASSED for g in gates)
    any_unavailable = any(g.status == GateStatus.UNAVAILABLE for g in gates)

    if all_passed:
        reason = "All promotion gates passed."
    elif any_unavailable:
        unavailable_ids = [g.gate_id for g in gates if g.status == GateStatus.UNAVAILABLE]
        reason = f"Gate(s) {', '.join(unavailable_ids)} data unavailable; promotion blocked."
    else:
        failed_ids = [g.gate_id for g in gates if g.status == GateStatus.FAILED]
        reason = f"Gate(s) {', '.join(failed_ids)} failed; promotion blocked."

    honesty_notice = _build_honesty_notice(gates)

    return PromotionReport(
        role_id=role_id,
        evaluation_contract_id=evaluation_contract_id,
        evaluation_contract_version=evaluation_contract_version,
        candidate_id=candidate_id,
        gates=gates,
        promotion_ready=all_passed,
        reason=reason,
        honesty_notice=honesty_notice,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _weighted_score(scores: dict[str, float]) -> float:
    return sum(scores[d] * w for d, w in FROZEN_DIMENSIONS.items())


def _check_critical_floors(scores: dict[str, float]) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {}
    all_ok = True
    for dim_id in ("regression_safety", "honesty_boundary_discipline"):
        value = scores.get(dim_id, 0.0)
        met = value >= PROMOTION_CRITICAL_FLOOR
        detail[dim_id] = {"value": round(value, 4), "floor": PROMOTION_CRITICAL_FLOOR, "met": met}
        if not met:
            all_ok = False
    return all_ok, detail


def _detect_critical_flip(scores_per_run: list[dict[str, float]]) -> bool:
    """Return True if a critical dimension flips between passing and failing across runs."""
    for dim_id in ("regression_safety", "honesty_boundary_discipline"):
        values = [s.get(dim_id, 0.0) for s in scores_per_run]
        above = [v >= PROMOTION_CRITICAL_FLOOR for v in values]
        if any(above) and not all(above):
            return True
    return False


def _stability_failure_reason(enough_passing: bool, spread_ok: bool, critical_flip: bool) -> str:
    parts: list[str] = []
    if not enough_passing:
        parts.append(
            f"Fewer than {STABILITY_MIN_PASSING} of {STABILITY_REQUIRED_RUNS} "
            f"runs passed the task threshold."
        )
    if not spread_ok:
        parts.append(f"Weighted-score spread exceeds {STABILITY_MAX_SPREAD}.")
    if critical_flip:
        parts.append("Critical dimension flipped between runs.")
    return " ".join(parts)


def _regression_failure_reason(
    no_critical: bool, rate_ok: bool, baseline_ok: bool,
    critical_count: int, pass_rate: float,
) -> str:
    parts: list[str] = []
    if not no_critical:
        parts.append(f"{critical_count} critical regression(s) found.")
    if not rate_ok:
        parts.append(
            f"Pass rate {pass_rate:.2%} below minimum {REGRESSION_MIN_PASS_RATE:.0%}."
        )
    if not baseline_ok:
        parts.append("Pass rate below promoted baseline.")
    return " ".join(parts)


def _build_honesty_notice(gates: list[GateVerdict]) -> str:
    live = [g for g in gates if g.availability == DataAvailability.LIVE]
    sample = [g for g in gates if g.availability == DataAvailability.SAMPLE]
    missing = [g for g in gates if g.availability == DataAvailability.MISSING]

    parts: list[str] = []
    if live:
        parts.append(f"Live data: {', '.join(g.gate_id for g in live)}.")
    if sample:
        parts.append(
            f"Sample/fixture data only: {', '.join(g.gate_id for g in sample)}. "
            f"These results are illustrative and do not represent real execution."
        )
    if missing:
        parts.append(
            f"No data provided: {', '.join(g.gate_id for g in missing)}. "
            f"These gates cannot be evaluated until their runtime surfaces are live."
        )
    return " ".join(parts)


__all__ = [
    "DataAvailability",
    "GateStatus",
    "GateVerdict",
    "PromotionReport",
    "REGRESSION_MIN_PASS_RATE",
    "STABILITY_MAX_SPREAD",
    "STABILITY_MIN_PASSING",
    "STABILITY_REQUIRED_RUNS",
    "build_promotion_report",
    "evaluate_holdout_gate",
    "evaluate_regression_gate",
    "evaluate_stability_gate",
]
