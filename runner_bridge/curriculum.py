"""Curriculum contract helpers for the frozen Frontend/Product Engineer role.

This module intentionally points at the versioned, role-specific curriculum
artifacts checked into the repo. We keep one truthful public contract surface
instead of maintaining generic aliases that can drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROLE_MANIFEST_PATH = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
EVAL_CONTRACT_PATH = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
TASK_SCHEMA_PATH = ROOT / "data" / "curriculum" / "frontend-product-engineer-task-packet.schema.v1.json"
SEED_REGISTRY_PATH = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"

FROZEN_ROLE_ID = "role-frontend-product-engineer"
FROZEN_ROLE_NAME = "Frontend/Product Engineer"

FROZEN_DIMENSIONS = {
    "task_outcome": 0.30,
    "regression_safety": 0.25,
    "mutation_discipline": 0.15,
    "evidence_quality": 0.15,
    "honesty_boundary_discipline": 0.15,
}

TASK_PASS_THRESHOLD = 0.80
TASK_MIN_DIMENSION = 0.60
PROMOTION_PUBLIC_THRESHOLD = 0.85
PROMOTION_HOLDOUT_THRESHOLD = 0.75
PROMOTION_CRITICAL_FLOOR = 0.90

REQUIRED_TASK_FIELDS = (
    "task_id",
    "role_id",
    "phase",
    "objective",
    "context",
    "allowed_paths",
    "blocked_paths",
    "expected_checks",
    "rubric_ref",
    "time_budget_minutes",
    "evidence_contract",
)

DEFAULT_MAX_FILES = 6
DEFAULT_MAX_LINES = 400


def _repo_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def load_role_manifest() -> dict[str, Any]:
    return _load_json(ROLE_MANIFEST_PATH)


def load_evaluation_contract() -> dict[str, Any]:
    contract = _load_json(EVAL_CONTRACT_PATH)
    validate_evaluation_contract(contract)
    return contract


def load_public_seed_registry() -> dict[str, Any]:
    registry = _load_json(SEED_REGISTRY_PATH)
    tasks = registry.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("public seed registry must contain tasks")
    return registry


def load_task_packet(path: str | Path) -> dict[str, Any]:
    packet = _load_json(path)
    validate_task_packet(packet)
    return packet


def load_registry_task(acceptance_test_id: str) -> dict[str, Any]:
    registry = load_public_seed_registry()
    for task in registry.get("tasks", []):
        if task.get("acceptance_test_id") == acceptance_test_id:
            validate_task_packet(task)
            return task
    raise ValueError(f"unknown acceptance_test_id: {acceptance_test_id}")


def _contract_dimension_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dims = contract.get("dimensions")
    if isinstance(dims, dict):
        return {str(key): value for key, value in dims.items() if isinstance(value, dict)}
    if isinstance(dims, list):
        mapped: dict[str, dict[str, Any]] = {}
        for entry in dims:
            if isinstance(entry, dict) and entry.get("id"):
                mapped[str(entry["id"])] = entry
        return mapped
    raise ValueError("contract dimensions must be a dict or list")


def _threshold_bundle(contract: dict[str, Any]) -> tuple[float, float, float, float, dict[str, float]]:
    thresholds = contract.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("contract thresholds must be a dict")

    task_pass = thresholds.get("task_pass")
    if isinstance(task_pass, dict):
        task_pass_threshold = float(task_pass.get("weighted_score_min"))
        task_min_dimension = float(task_pass.get("dimension_floor_min"))
        promotion_gate = thresholds.get("promotion_gate")
        if not isinstance(promotion_gate, dict):
            raise ValueError("contract promotion_gate must be a dict")
        public_threshold = float(promotion_gate.get("public_weighted_score_min"))
        holdout_threshold = float(promotion_gate.get("private_holdout_weighted_score_min"))
        critical_dimensions_raw = promotion_gate.get("critical_dimension_floors")
        if not isinstance(critical_dimensions_raw, dict):
            raise ValueError("contract critical_dimension_floors must be a dict")
        critical_dimensions = {
            str(key): float(value) for key, value in critical_dimensions_raw.items()
        }
        return (
            task_pass_threshold,
            task_min_dimension,
            public_threshold,
            holdout_threshold,
            critical_dimensions,
        )

    critical_dimensions = {
        str(key): float(thresholds.get("promotion_critical_floor"))
        for key in thresholds.get("critical_dimensions", [])
    }
    return (
        float(task_pass),
        float(thresholds.get("task_min_dimension")),
        float(thresholds.get("promotion_public")),
        float(thresholds.get("promotion_holdout")),
        critical_dimensions,
    )


def _validate_phase(phase: Any) -> None:
    if isinstance(phase, int):
        if phase < 1 or phase > 5:
            raise ValueError("phase must be between 1 and 5")
        return

    if not isinstance(phase, dict):
        raise ValueError("phase must be an integer or dict")

    for key in ("id", "label", "index"):
        if key not in phase:
            raise ValueError(f"phase missing {key}")

    index = phase.get("index")
    if not isinstance(index, int) or index < 1 or index > 5:
        raise ValueError("phase.index must be an integer between 1 and 5")


def _validate_expected_checks(expected_checks: Any) -> None:
    if not isinstance(expected_checks, list) or not expected_checks:
        raise ValueError("expected_checks must be a non-empty list")

    if all(isinstance(check, str) and check.strip() for check in expected_checks):
        return

    for check in expected_checks:
        if not isinstance(check, dict):
            raise ValueError("expected_checks entries must be strings or dicts")
        missing = [key for key in ("id", "command", "why") if not check.get(key)]
        if missing:
            raise ValueError(
                "expected_checks entry missing required fields: " + ", ".join(missing)
            )


def _validate_mutation_budget(mutation_budget: Any) -> None:
    if not isinstance(mutation_budget, dict):
        raise ValueError("mutation_budget must be a dict")

    tracked_files = mutation_budget.get("tracked_files_max", mutation_budget.get("max_files"))
    net_lines = mutation_budget.get("net_lines_max", mutation_budget.get("max_lines"))

    if not isinstance(tracked_files, int) or tracked_files < 1:
        raise ValueError("mutation_budget tracked_files_max/max_files must be a positive integer")
    if not isinstance(net_lines, int) or net_lines < 1:
        raise ValueError("mutation_budget net_lines_max/max_lines must be a positive integer")


def validate_task_packet(packet: dict[str, Any]) -> None:
    """Validate a public seed task packet against the frozen contract."""
    missing = [field for field in REQUIRED_TASK_FIELDS if field not in packet]
    if missing:
        raise ValueError(f"Task packet missing required fields: {', '.join(missing)}")

    if packet.get("role_id") != FROZEN_ROLE_ID:
        raise ValueError(
            f"task packet role_id must be {FROZEN_ROLE_ID}, got {packet.get('role_id')}"
        )

    _validate_phase(packet.get("phase"))

    context = packet.get("context")
    if not isinstance(context, dict) or not str(context.get("summary", "")).strip():
        raise ValueError("context.summary must be a non-empty string")

    allowed_paths = packet.get("allowed_paths")
    if not isinstance(allowed_paths, list) or not allowed_paths:
        raise ValueError("allowed_paths must be a non-empty list")

    blocked_paths = packet.get("blocked_paths")
    if not isinstance(blocked_paths, list) or not blocked_paths:
        raise ValueError("blocked_paths must be a non-empty list")

    _validate_expected_checks(packet.get("expected_checks"))
    _validate_mutation_budget(packet.get("mutation_budget", {}))

    rubric_ref = packet.get("rubric_ref")
    if isinstance(rubric_ref, dict):
        contract_path = rubric_ref.get("contract_path")
        if contract_path != _repo_rel(EVAL_CONTRACT_PATH):
            raise ValueError("rubric_ref.contract_path must point at the canonical evaluation contract")
    elif not isinstance(rubric_ref, str) or "evaluation-contract" not in rubric_ref:
        raise ValueError("rubric_ref must be a contract-path string or object")

    evidence_contract = packet.get("evidence_contract")
    if not isinstance(evidence_contract, dict):
        raise ValueError("evidence_contract must be a dict")
    required_artifacts = evidence_contract.get("required_artifacts")
    if not isinstance(required_artifacts, list) or not required_artifacts:
        raise ValueError("evidence_contract.required_artifacts must be a non-empty list")


def score_map_from_scorecard(scorecard: dict[str, Any]) -> dict[str, float]:
    """Extract a dimension->score map from a scorecard object."""
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("scorecard dimensions must be a non-empty list")

    scores: dict[str, float] = {}
    for entry in dimensions:
        if not isinstance(entry, dict) or "id" not in entry or "score" not in entry:
            raise ValueError("scorecard dimensions entries must contain id and score")
        scores[str(entry["id"])] = float(entry["score"])
    validate_scorecard(scores)
    return scores


def validate_scorecard(scores: dict[str, float]) -> None:
    """Validate that a scorecard exposes every frozen dimension."""
    missing = [dimension for dimension in FROZEN_DIMENSIONS if dimension not in scores]
    if missing:
        raise ValueError(f"Scorecard missing dimensions: {', '.join(missing)}")


def check_task_pass(scores: dict[str, float]) -> bool:
    """Return True when the scorecard clears the frozen task threshold."""
    validate_scorecard(scores)

    for dimension, score in scores.items():
        if dimension in FROZEN_DIMENSIONS and score < TASK_MIN_DIMENSION:
            return False

    weighted = sum(scores[dimension] * weight for dimension, weight in FROZEN_DIMENSIONS.items())
    return weighted >= TASK_PASS_THRESHOLD


def validate_evaluation_contract(contract: dict[str, Any]) -> None:
    """Validate the frozen evaluation contract against Spec 014 constants."""
    dimensions = _contract_dimension_map(contract)
    missing = [dimension for dimension in FROZEN_DIMENSIONS if dimension not in dimensions]
    if missing:
        raise ValueError(f"Contract missing dimensions: {', '.join(missing)}")

    total_weight = 0.0
    for dimension, expected_weight in FROZEN_DIMENSIONS.items():
        actual_weight = float(dimensions[dimension].get("weight", 0))
        if abs(actual_weight - expected_weight) > 0.001:
            raise ValueError(
                f"Dimension '{dimension}' weight mismatch: expected {expected_weight}, got {actual_weight}"
            )
        total_weight += actual_weight

    if abs(total_weight - 1.0) > 0.001:
        raise ValueError(f"Dimension weights sum to {total_weight}, expected 1.0")

    (
        task_pass_threshold,
        task_min_dimension,
        promotion_public_threshold,
        promotion_holdout_threshold,
        critical_dimensions,
    ) = _threshold_bundle(contract)

    if abs(task_pass_threshold - TASK_PASS_THRESHOLD) > 0.001:
        raise ValueError("task_pass threshold does not match frozen spec")
    if abs(task_min_dimension - TASK_MIN_DIMENSION) > 0.001:
        raise ValueError("task_min_dimension threshold does not match frozen spec")
    if abs(promotion_public_threshold - PROMOTION_PUBLIC_THRESHOLD) > 0.001:
        raise ValueError("promotion public threshold does not match frozen spec")
    if abs(promotion_holdout_threshold - PROMOTION_HOLDOUT_THRESHOLD) > 0.001:
        raise ValueError("promotion holdout threshold does not match frozen spec")

    for critical_dimension in ("regression_safety", "honesty_boundary_discipline"):
        actual_floor = float(critical_dimensions.get(critical_dimension, 0))
        if abs(actual_floor - PROMOTION_CRITICAL_FLOOR) > 0.001:
            raise ValueError(
                f"critical floor for {critical_dimension} does not match frozen spec"
            )

    defaults = contract.get("mutation_budget_defaults")
    if not isinstance(defaults, dict):
        raise ValueError("contract mutation_budget_defaults must be a dict")
    if defaults.get("tracked_files_max", defaults.get("max_files")) != DEFAULT_MAX_FILES:
        raise ValueError("default tracked-files budget does not match frozen spec")
    if defaults.get("net_lines_max", defaults.get("max_lines")) != DEFAULT_MAX_LINES:
        raise ValueError("default net-lines budget does not match frozen spec")

    required_fields = contract.get("required_task_packet_fields")
    if isinstance(required_fields, list):
        for field in REQUIRED_TASK_FIELDS:
            if field not in required_fields:
                raise ValueError(f"contract missing required task field declaration: {field}")


__all__ = [
    "DEFAULT_MAX_FILES",
    "DEFAULT_MAX_LINES",
    "EVAL_CONTRACT_PATH",
    "FROZEN_DIMENSIONS",
    "FROZEN_ROLE_ID",
    "FROZEN_ROLE_NAME",
    "PROMOTION_CRITICAL_FLOOR",
    "PROMOTION_HOLDOUT_THRESHOLD",
    "PROMOTION_PUBLIC_THRESHOLD",
    "REQUIRED_TASK_FIELDS",
    "ROLE_MANIFEST_PATH",
    "ROOT",
    "SEED_REGISTRY_PATH",
    "TASK_MIN_DIMENSION",
    "TASK_PASS_THRESHOLD",
    "TASK_SCHEMA_PATH",
    "check_task_pass",
    "load_evaluation_contract",
    "load_public_seed_registry",
    "load_registry_task",
    "load_role_manifest",
    "load_task_packet",
    "score_map_from_scorecard",
    "validate_evaluation_contract",
    "validate_scorecard",
    "validate_task_packet",
]
