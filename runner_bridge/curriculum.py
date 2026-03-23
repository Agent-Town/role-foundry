"""Validator module for the spec-014 curriculum contract.

Provides validation functions for task packets, scorecards, and the
evaluation contract itself. All constants are derived from the frozen
spec and the checked-in evaluation-contract.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Frozen constants from spec 014 ──────────────────────────────────

FROZEN_DIMENSIONS = {
    "task_outcome": 0.30,
    "regression_safety": 0.25,
    "mutation_discipline": 0.15,
    "evidence_quality": 0.15,
    "honesty_boundary_discipline": 0.15,
}

TASK_PASS_THRESHOLD = 0.80
TASK_MIN_DIMENSION = 0.60

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


def validate_task_packet(packet: dict[str, Any]) -> None:
    """Validate a task packet against the required field contract.

    Raises ValueError if any required field is missing or if structural
    constraints are violated.
    """
    missing = [f for f in REQUIRED_TASK_FIELDS if f not in packet]
    if missing:
        raise ValueError(f"Task packet missing required fields: {', '.join(missing)}")

    if not isinstance(packet.get("allowed_paths"), list) or len(packet["allowed_paths"]) == 0:
        raise ValueError("allowed_paths must be a non-empty list")

    if not isinstance(packet.get("blocked_paths"), list):
        raise ValueError("blocked_paths must be a list")

    if not isinstance(packet.get("expected_checks"), list) or len(packet["expected_checks"]) == 0:
        raise ValueError("expected_checks must be a non-empty list")

    if not isinstance(packet.get("evidence_contract"), dict):
        raise ValueError("evidence_contract must be a dict")

    ec = packet["evidence_contract"]
    if "required_artifacts" not in ec:
        raise ValueError("evidence_contract must contain required_artifacts")


def validate_scorecard(scores: dict[str, float]) -> None:
    """Validate that a scorecard has all required dimensions.

    Raises ValueError if any dimension is missing.
    """
    missing = [d for d in FROZEN_DIMENSIONS if d not in scores]
    if missing:
        raise ValueError(f"Scorecard missing dimensions: {', '.join(missing)}")


def check_task_pass(scores: dict[str, float]) -> bool:
    """Check whether a scorecard passes the task threshold.

    Returns True if the weighted score >= 0.80 AND no individual
    dimension is below 0.60.
    """
    validate_scorecard(scores)

    for dim, score in scores.items():
        if dim in FROZEN_DIMENSIONS and score < TASK_MIN_DIMENSION:
            return False

    weighted = sum(
        scores[dim] * weight
        for dim, weight in FROZEN_DIMENSIONS.items()
    )
    return weighted >= TASK_PASS_THRESHOLD


def validate_evaluation_contract(contract: dict[str, Any]) -> None:
    """Validate the evaluation contract against frozen spec values.

    Raises ValueError if dimensions or weights have been tampered with.
    """
    dims = contract.get("dimensions", {})

    missing = [d for d in FROZEN_DIMENSIONS if d not in dims]
    if missing:
        raise ValueError(f"Contract missing dimensions: {', '.join(missing)}")

    total = 0.0
    for dim_key, expected_weight in FROZEN_DIMENSIONS.items():
        actual_weight = dims[dim_key].get("weight", 0)
        if abs(actual_weight - expected_weight) > 0.001:
            raise ValueError(
                f"Dimension '{dim_key}' weight mismatch: "
                f"expected {expected_weight}, got {actual_weight}"
            )
        total += actual_weight

    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Dimension weights sum to {total}, expected 1.0")


def load_task_packet(path: str | Path) -> dict[str, Any]:
    """Load and validate a task packet from disk."""
    packet = json.loads(Path(path).read_text())
    validate_task_packet(packet)
    return packet
