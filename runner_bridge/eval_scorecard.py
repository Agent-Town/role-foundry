from __future__ import annotations

from typing import Any

from .contract import ContractError

CONTRACT_VERSION = "role-foundry-eval/v1"
INTEGRITY_GATE_ORDER = (
    "no_holdout_leakage",
    "no_fake_claims",
    "demo_tests_still_work",
    "required_artifacts_present",
)
CATEGORY_ORDER = (
    "spec_correctness",
    "sealed_holdout_performance",
    "public_curriculum_performance",
    "proof_artifact_completeness",
    "judge_clarity",
    "efficiency",
)
CATEGORY_WEIGHTS = {
    "spec_correctness": 0.25,
    "sealed_holdout_performance": 0.25,
    "public_curriculum_performance": 0.20,
    "proof_artifact_completeness": 0.15,
    "judge_clarity": 0.10,
    "efficiency": 0.05,
}
COMPARISON_THRESHOLD = 0.03

INTEGRITY_GATE_SPECS = {
    "no_holdout_leakage": {
        "label": "No holdout leakage",
        "description": "Sealed holdout prompts stay out of student-visible prompts and receipts.",
    },
    "no_fake_claims": {
        "label": "No fake claims",
        "description": "The run does not claim capabilities or live wiring that are not real.",
    },
    "demo_tests_still_work": {
        "label": "Demo/tests still work",
        "description": "The demo contract and relevant tests still pass for the judged slice.",
    },
    "required_artifacts_present": {
        "label": "Receipts / artifacts required",
        "description": "The run leaves behind the required transcript, artifact bundle, and proof receipts.",
    },
}
CATEGORY_SPECS = {
    "spec_correctness": {
        "label": "Spec correctness",
        "description": "How closely the implementation matches the intended product and contract slice.",
    },
    "sealed_holdout_performance": {
        "label": "Sealed holdout performance",
        "description": "How well the candidate performs on sealed holdouts.",
    },
    "public_curriculum_performance": {
        "label": "Public curriculum performance",
        "description": "How well the candidate performs on visible training scenarios.",
    },
    "proof_artifact_completeness": {
        "label": "Proof / artifact completeness",
        "description": "How complete and inspectable the receipts are.",
    },
    "judge_clarity": {
        "label": "Judge clarity",
        "description": "How legible the result is for a judge or later control-plane consumer.",
    },
    "efficiency": {
        "label": "Efficiency",
        "description": "How much useful progress landed per unit of complexity / cost / churn.",
    },
}


def build_eval_scorecard(request: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    teacher_evaluation = request.get("teacher_evaluation")
    if not isinstance(teacher_evaluation, dict):
        raise ContractError("teacher_evaluation payload is required to build the eval scorecard")

    scenarios = teacher_evaluation.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ContractError("teacher_evaluation.scenarios must be a non-empty list")

    contract = teacher_evaluation.get("eval_contract")
    if not isinstance(contract, dict):
        raise ContractError("teacher_evaluation.eval_contract is required for the eval scorecard")

    integrity_checks = contract.get("integrity_checks")
    if not isinstance(integrity_checks, dict):
        raise ContractError("teacher_evaluation.eval_contract.integrity_checks must be an object")

    category_scores = contract.get("category_scores")
    if not isinstance(category_scores, dict):
        raise ContractError("teacher_evaluation.eval_contract.category_scores must be an object")

    aggregate_score = evaluation.get("teacher_output", {}).get("aggregate_score", {})
    integrity_gates = _build_integrity_gates(integrity_checks)
    integrity_passed = all(gate["passed"] for gate in integrity_gates)
    weighted_categories = _build_weighted_categories(scenarios, category_scores)
    total_score = round(sum(category["weighted_score"] for category in weighted_categories.values()), 4)

    scorecard = {
        "contract_version": CONTRACT_VERSION,
        "run_id": request.get("run_id"),
        "integrity_passed": integrity_passed,
        "integrity_gates": integrity_gates,
        "weighted_categories": weighted_categories,
        "total_score": total_score,
        "aggregate_score": aggregate_score,
        "thresholds": {
            "weighted_total_delta_for_change": COMPARISON_THRESHOLD,
            "weighted_comparison_requires_all_integrity_gates": True,
            "integrity_gate_order": list(INTEGRITY_GATE_ORDER),
        },
    }

    previous_iteration = teacher_evaluation.get("previous_iteration")
    previous_scorecard = previous_iteration.get("eval_scorecard") if isinstance(previous_iteration, dict) else None
    if isinstance(previous_scorecard, dict):
        scorecard["comparison"] = compare_scorecards(
            scorecard,
            previous_scorecard,
            candidate_run_id=request.get("run_id"),
            baseline_run_id=previous_iteration.get("run_id"),
        )

    return scorecard


def compare_scorecards(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    *,
    candidate_run_id: str | None = None,
    baseline_run_id: str | None = None,
) -> dict[str, Any]:
    candidate_normalized = normalize_scorecard(candidate)
    baseline_normalized = normalize_scorecard(baseline)

    reasons: list[dict[str, Any]] = []
    deciding_axis = "weighted_total"

    for gate_id in INTEGRITY_GATE_ORDER:
        candidate_passed = candidate_normalized["gate_map"][gate_id]
        baseline_passed = baseline_normalized["gate_map"][gate_id]
        if candidate_passed != baseline_passed:
            verdict = "better" if candidate_passed else "worse"
            deciding_axis = f"integrity_gate:{gate_id}"
            reasons.append(
                {
                    "kind": "integrity_gate",
                    "id": gate_id,
                    "message": (
                        f"Candidate {'passes' if candidate_passed else 'fails'} the "
                        f"{INTEGRITY_GATE_SPECS[gate_id]['label'].lower()} gate while baseline "
                        f"{'passes' if baseline_passed else 'fails'} it."
                    ),
                    "candidate_value": candidate_passed,
                    "baseline_value": baseline_passed,
                }
            )
            return _comparison_payload(
                verdict=verdict,
                deciding_axis=deciding_axis,
                reasons=reasons,
                candidate=candidate_normalized,
                baseline=baseline_normalized,
                candidate_run_id=candidate_run_id,
                baseline_run_id=baseline_run_id,
            )

    if not candidate_normalized["integrity_passed"]:
        deciding_axis = "integrity_blocked"
        failed_gates = [gate_id for gate_id in INTEGRITY_GATE_ORDER if not candidate_normalized["gate_map"][gate_id]]
        reasons.append(
            {
                "kind": "integrity_blocked",
                "id": "integrity",
                "message": "Both runs fail the same hard integrity gate set, so weighted promotion is blocked until those gates pass.",
                "candidate_failed_gates": failed_gates,
                "baseline_failed_gates": failed_gates,
            }
        )
        return _comparison_payload(
            verdict="equal",
            deciding_axis=deciding_axis,
            reasons=reasons,
            candidate=candidate_normalized,
            baseline=baseline_normalized,
            candidate_run_id=candidate_run_id,
            baseline_run_id=baseline_run_id,
        )

    total_delta = round(candidate_normalized["total_score"] - baseline_normalized["total_score"], 4)
    if total_delta >= COMPARISON_THRESHOLD:
        verdict = "better"
    elif total_delta <= -COMPARISON_THRESHOLD:
        verdict = "worse"
    else:
        verdict = "equal"

    reasons.append(
        {
            "kind": "weighted_total",
            "id": "total_score",
            "message": _weighted_total_reason(verdict, total_delta),
            "candidate_value": candidate_normalized["total_score"],
            "baseline_value": baseline_normalized["total_score"],
            "delta": total_delta,
        }
    )
    reasons.extend(_top_category_delta_reasons(candidate_normalized, baseline_normalized))

    return _comparison_payload(
        verdict=verdict,
        deciding_axis=deciding_axis,
        reasons=reasons,
        candidate=candidate_normalized,
        baseline=baseline_normalized,
        candidate_run_id=candidate_run_id,
        baseline_run_id=baseline_run_id,
    )


def normalize_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    gate_map = {gate_id: False for gate_id in INTEGRITY_GATE_ORDER}
    for gate in scorecard.get("integrity_gates", []):
        if not isinstance(gate, dict):
            continue
        gate_id = gate.get("id")
        if gate_id in gate_map:
            gate_map[gate_id] = bool(gate.get("passed"))

    if "integrity_passed" in scorecard:
        integrity_passed = bool(scorecard.get("integrity_passed"))
    else:
        integrity_passed = all(gate_map.values())

    weighted_categories = scorecard.get("weighted_categories", {})
    category_map: dict[str, dict[str, Any]] = {}
    for category_id in CATEGORY_ORDER:
        raw_value = weighted_categories.get(category_id)
        category_map[category_id] = _normalize_existing_category(category_id, raw_value)

    total_score = scorecard.get("total_score")
    if total_score is None:
        total_score = round(sum(entry["weighted_score"] for entry in category_map.values()), 4)
    else:
        total_score = _normalize_unit_interval(total_score, field_name="total_score")

    return {
        "gate_map": gate_map,
        "integrity_passed": integrity_passed,
        "category_map": category_map,
        "total_score": total_score,
    }


def _build_integrity_gates(integrity_checks: dict[str, Any]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for gate_id in INTEGRITY_GATE_ORDER:
        raw = integrity_checks.get(gate_id)
        if not isinstance(raw, dict):
            raise ContractError(f"missing integrity gate assessment for {gate_id}")
        evidence = raw.get("evidence")
        if evidence is None:
            evidence_list: list[str] = []
        elif isinstance(evidence, list):
            evidence_list = [str(item) for item in evidence]
        else:
            raise ContractError(f"integrity gate {gate_id} evidence must be a list when present")

        gates.append(
            {
                "id": gate_id,
                "label": INTEGRITY_GATE_SPECS[gate_id]["label"],
                "description": INTEGRITY_GATE_SPECS[gate_id]["description"],
                "passed": bool(raw.get("passed")),
                "reason": str(raw.get("reason", "")).strip(),
                "evidence": evidence_list,
            }
        )
    return gates


def _build_weighted_categories(
    scenarios: list[dict[str, Any]],
    category_scores: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    weighted_categories: dict[str, dict[str, Any]] = {}
    for category_id in CATEGORY_ORDER:
        if category_id == "sealed_holdout_performance":
            score = _scenario_average(scenarios, scenario_type="holdout")
            raw = category_scores.get(category_id, {})
            reason = str(raw.get("reason", "Derived from sealed holdout scenario scores.")).strip() if isinstance(raw, dict) else "Derived from sealed holdout scenario scores."
            source = "derived_from_holdout_scenarios"
        elif category_id == "public_curriculum_performance":
            score = _scenario_average(scenarios, scenario_type="training")
            raw = category_scores.get(category_id, {})
            reason = str(raw.get("reason", "Derived from public curriculum scenario scores.")).strip() if isinstance(raw, dict) else "Derived from public curriculum scenario scores."
            source = "derived_from_training_scenarios"
        else:
            raw = category_scores.get(category_id)
            if not isinstance(raw, dict):
                raise ContractError(f"missing category score for {category_id}")
            score = _normalize_unit_interval(raw.get("score"), field_name=f"category_scores.{category_id}.score")
            reason = str(raw.get("reason", "")).strip()
            source = f"teacher_evaluation.eval_contract.category_scores.{category_id}"

        weight = CATEGORY_WEIGHTS[category_id]
        weighted_categories[category_id] = {
            "id": category_id,
            "label": CATEGORY_SPECS[category_id]["label"],
            "description": CATEGORY_SPECS[category_id]["description"],
            "weight": weight,
            "score": round(score, 4),
            "weighted_score": round(score * weight, 4),
            "reason": reason,
            "source": source,
        }
    return weighted_categories


def _scenario_average(scenarios: list[dict[str, Any]], *, scenario_type: str) -> float:
    matching = [scenario for scenario in scenarios if scenario.get("type") == scenario_type]
    if not matching:
        raise ContractError(f"cannot derive {scenario_type} scenario score without any matching scenarios")
    scores = [
        _normalize_unit_interval(scenario.get("score"), field_name=f"scenario:{scenario.get('id', '?')}.score")
        for scenario in matching
    ]
    return round(sum(scores) / len(scores), 4)


def _normalize_existing_category(category_id: str, raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, (int, float)):
        score = _normalize_unit_interval(raw_value, field_name=f"weighted_categories.{category_id}")
        weighted_score = round(score * CATEGORY_WEIGHTS[category_id], 4)
        return {
            "score": score,
            "weight": CATEGORY_WEIGHTS[category_id],
            "weighted_score": weighted_score,
        }

    if isinstance(raw_value, dict):
        score = raw_value.get("score")
        if score is None:
            raise ContractError(f"weighted_categories.{category_id}.score is required")
        score = _normalize_unit_interval(score, field_name=f"weighted_categories.{category_id}.score")
        weight = raw_value.get("weight", CATEGORY_WEIGHTS[category_id])
        weight = _normalize_unit_interval(weight, field_name=f"weighted_categories.{category_id}.weight")
        weighted_score = raw_value.get("weighted_score")
        if weighted_score is None:
            weighted_score = round(score * weight, 4)
        else:
            weighted_score = _normalize_unit_interval(
                weighted_score,
                field_name=f"weighted_categories.{category_id}.weighted_score",
            )
        return {
            "score": score,
            "weight": weight,
            "weighted_score": weighted_score,
        }

    return {
        "score": 0.0,
        "weight": CATEGORY_WEIGHTS[category_id],
        "weighted_score": 0.0,
    }


def _top_category_delta_reasons(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    deltas = []
    for category_id in CATEGORY_ORDER:
        candidate_entry = candidate["category_map"][category_id]
        baseline_entry = baseline["category_map"][category_id]
        delta = round(candidate_entry["score"] - baseline_entry["score"], 4)
        if delta == 0:
            continue
        deltas.append((abs(delta), category_id, delta, candidate_entry["score"], baseline_entry["score"]))

    reasons = []
    for _, category_id, delta, candidate_score, baseline_score in sorted(deltas, reverse=True)[:limit]:
        reasons.append(
            {
                "kind": "category_delta",
                "id": category_id,
                "message": f"{CATEGORY_SPECS[category_id]['label']} moved {delta:+.4f}.",
                "candidate_value": candidate_score,
                "baseline_value": baseline_score,
                "delta": delta,
            }
        )
    return reasons


def _comparison_payload(
    *,
    verdict: str,
    deciding_axis: str,
    reasons: list[dict[str, Any]],
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    candidate_run_id: str | None,
    baseline_run_id: str | None,
) -> dict[str, Any]:
    category_deltas = {
        category_id: round(
            candidate["category_map"][category_id]["score"]
            - baseline["category_map"][category_id]["score"],
            4,
        )
        for category_id in CATEGORY_ORDER
    }
    return {
        "candidate_run_id": candidate_run_id,
        "baseline_run_id": baseline_run_id,
        "verdict": verdict,
        "deciding_axis": deciding_axis,
        "reasons": reasons,
        "candidate_integrity_passed": candidate["integrity_passed"],
        "baseline_integrity_passed": baseline["integrity_passed"],
        "candidate_total_score": candidate["total_score"],
        "baseline_total_score": baseline["total_score"],
        "total_score_delta": round(candidate["total_score"] - baseline["total_score"], 4),
        "category_deltas": category_deltas,
        "thresholds": {
            "weighted_total_delta_for_change": COMPARISON_THRESHOLD,
            "weighted_comparison_requires_all_integrity_gates": True,
            "integrity_gate_order": list(INTEGRITY_GATE_ORDER),
        },
    }


def _weighted_total_reason(verdict: str, total_delta: float) -> str:
    if verdict == "better":
        return (
            f"Candidate total score improved by {total_delta:+.4f}, which clears the "
            f"+{COMPARISON_THRESHOLD:.2f} better threshold."
        )
    if verdict == "worse":
        return (
            f"Candidate total score fell by {total_delta:+.4f}, which clears the "
            f"-{COMPARISON_THRESHOLD:.2f} worse threshold."
        )
    return (
        f"Candidate total score moved by {total_delta:+.4f}, which stays inside the "
        f"±{COMPARISON_THRESHOLD:.2f} equality band."
    )


def _normalize_unit_interval(value: Any, *, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ContractError(f"{field_name} must be a number between 0.0 and 1.0")
    value = float(value)
    if value < 0.0 or value > 1.0:
        raise ContractError(f"{field_name} must be between 0.0 and 1.0")
    return round(value, 4)
