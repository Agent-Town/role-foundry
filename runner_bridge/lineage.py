"""Phase 5 lineage and weekly-cycle contract helpers.

Loads and validates generation-lineage registries and weekly training-cycle
receipts against the frozen curriculum contract surface.  All public artifacts
checked into git are sample/fixture-only unless explicitly marked otherwise.

Honest status:
- Generation lineage entries are fixture artifacts, not proof of live promotions.
- Weekly cycle receipts are fixture artifacts, not proof of live automation.
- Private holdout scores are referenced by availability only; values are never
  stored in public artifacts.
- Run-object references are marked available=false when no real run artifact
  exists in git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .curriculum import (
    EVAL_CONTRACT_PATH,
    FROZEN_ROLE_ID,
    PROMOTION_CRITICAL_FLOOR,
    PROMOTION_HOLDOUT_THRESHOLD,
    PROMOTION_PUBLIC_THRESHOLD,
    ROOT,
    SEED_REGISTRY_PATH,
    TASK_PASS_THRESHOLD,
)

LINEAGE_REGISTRY_PATH = (
    ROOT / "data" / "curriculum"
    / "frontend-product-engineer-generation-lineage.v1.json"
)
LINEAGE_SCHEMA_PATH = (
    ROOT / "data" / "curriculum"
    / "generation-lineage-registry.schema.v1.json"
)
WEEKLY_CYCLE_PATH = (
    ROOT / "data" / "curriculum"
    / "frontend-product-engineer-sample-weekly-cycle.v1.json"
)
WEEKLY_CYCLE_SCHEMA_PATH = (
    ROOT / "data" / "curriculum"
    / "weekly-training-cycle-receipt.schema.v1.json"
)


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


# ---------------------------------------------------------------------------
# Generation lineage helpers
# ---------------------------------------------------------------------------

def load_lineage_registry() -> dict[str, Any]:
    """Load and validate the generation lineage registry."""
    registry = _load_json(LINEAGE_REGISTRY_PATH)
    validate_lineage_registry(registry)
    return registry


def validate_lineage_registry(registry: dict[str, Any]) -> None:
    """Validate a generation lineage registry against contract rules."""
    meta = registry.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("lineage registry must have a meta object")
    if meta.get("role_id") != FROZEN_ROLE_ID:
        raise ValueError(f"lineage registry role_id must be {FROZEN_ROLE_ID}")
    if meta.get("schema_version") != "1.0.0":
        raise ValueError("lineage registry schema_version must be 1.0.0")

    generations = registry.get("generations")
    if not isinstance(generations, list) or not generations:
        raise ValueError("lineage registry must contain at least one generation")

    seen_ids: set[str] = set()
    for i, gen in enumerate(generations):
        _validate_generation_entry(gen, i, seen_ids)
        seen_ids.add(gen["generation_id"])


_GENERATION_REQUIRED = (
    "generation_id", "generation_index", "promoted", "example_only",
    "parent_generation_id", "task_packet_version",
    "evaluation_contract_version", "promotion_decision",
    "curriculum_contract_ref", "run_object_ref", "regression_gate",
    "created_at",
)


def _validate_generation_entry(
    gen: dict[str, Any], index: int, seen_ids: set[str]
) -> None:
    missing = [f for f in _GENERATION_REQUIRED if f not in gen]
    if missing:
        raise ValueError(
            f"generation[{index}] missing fields: {', '.join(missing)}"
        )

    if gen["generation_index"] != index + 1:
        raise ValueError(
            f"generation[{index}] index must be {index + 1}, "
            f"got {gen['generation_index']}"
        )

    parent = gen["parent_generation_id"]
    if index == 0 and parent is not None:
        raise ValueError("first generation must have null parent_generation_id")
    if index > 0 and parent not in seen_ids:
        raise ValueError(
            f"generation[{index}] parent_generation_id '{parent}' "
            "not found in prior generations"
        )

    decision = gen["promotion_decision"]
    if not isinstance(decision, dict):
        raise ValueError(f"generation[{index}] promotion_decision must be a dict")
    if decision.get("decision") not in ("promoted", "not_promoted", "deferred"):
        raise ValueError(f"generation[{index}] invalid promotion decision")

    contract_ref = gen["curriculum_contract_ref"]
    if not isinstance(contract_ref, dict):
        raise ValueError(f"generation[{index}] curriculum_contract_ref must be a dict")
    expected_registry = SEED_REGISTRY_PATH.relative_to(ROOT).as_posix()
    expected_contract = EVAL_CONTRACT_PATH.relative_to(ROOT).as_posix()
    if contract_ref.get("seed_registry_path") != expected_registry:
        raise ValueError(
            f"generation[{index}] seed_registry_path must be {expected_registry}"
        )
    if contract_ref.get("evaluation_contract_path") != expected_contract:
        raise ValueError(
            f"generation[{index}] evaluation_contract_path must be {expected_contract}"
        )

    run_ref = gen["run_object_ref"]
    if not isinstance(run_ref, dict):
        raise ValueError(f"generation[{index}] run_object_ref must be a dict")
    if "available" not in run_ref:
        raise ValueError(f"generation[{index}] run_object_ref must declare available")

    reg_gate = gen["regression_gate"]
    if not isinstance(reg_gate, dict) or "enforced" not in reg_gate:
        raise ValueError(f"generation[{index}] regression_gate must declare enforced")


# ---------------------------------------------------------------------------
# Weekly training-cycle receipt helpers
# ---------------------------------------------------------------------------

def load_weekly_cycle() -> dict[str, Any]:
    """Load and validate the sample weekly cycle receipt."""
    receipt = _load_json(WEEKLY_CYCLE_PATH)
    validate_weekly_cycle(receipt)
    return receipt


_CYCLE_REQUIRED = (
    "cycle_id", "cycle_week", "example_only",
    "task_selection", "baseline", "candidate", "teacher_review",
    "promotion_decision", "regression_gate", "curriculum_update",
    "generation_ref",
)


def validate_weekly_cycle(receipt: dict[str, Any]) -> None:
    """Validate a weekly training cycle receipt."""
    meta = receipt.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("weekly cycle must have a meta object")
    if meta.get("role_id") != FROZEN_ROLE_ID:
        raise ValueError(f"weekly cycle role_id must be {FROZEN_ROLE_ID}")
    if meta.get("schema_version") != "1.0.0":
        raise ValueError("weekly cycle schema_version must be 1.0.0")

    cycle = receipt.get("cycle")
    if not isinstance(cycle, dict):
        raise ValueError("weekly cycle must have a cycle object")

    missing = [f for f in _CYCLE_REQUIRED if f not in cycle]
    if missing:
        raise ValueError(f"cycle missing fields: {', '.join(missing)}")

    # Task selection
    sel = cycle["task_selection"]
    if not isinstance(sel, dict) or not sel.get("task_ids"):
        raise ValueError("cycle task_selection must have task_ids")

    # Baseline and candidate
    for run_key in ("baseline", "candidate"):
        run = cycle[run_key]
        if not isinstance(run, dict) or "available" not in run:
            raise ValueError(f"cycle {run_key} must declare available")

    # Teacher review
    review = cycle["teacher_review"]
    if not isinstance(review, dict) or "reviewed" not in review:
        raise ValueError("cycle teacher_review must declare reviewed")

    # Promotion decision
    pd = cycle["promotion_decision"]
    if not isinstance(pd, dict):
        raise ValueError("cycle promotion_decision must be a dict")
    if pd.get("decision") not in ("promoted", "not_promoted", "deferred"):
        raise ValueError("invalid promotion decision in weekly cycle")

    # Regression gate
    rg = cycle["regression_gate"]
    if not isinstance(rg, dict) or "enforced" not in rg:
        raise ValueError("cycle regression_gate must declare enforced")

    # Curriculum update
    cu = cycle["curriculum_update"]
    if not isinstance(cu, dict) or "updates_made" not in cu:
        raise ValueError("cycle curriculum_update must declare updates_made")

    # Generation ref
    gr = cycle["generation_ref"]
    if not isinstance(gr, dict) or "generation_id" not in gr:
        raise ValueError("cycle generation_ref must declare generation_id")


# ---------------------------------------------------------------------------
# Cross-artifact linkage helpers
# ---------------------------------------------------------------------------

def check_promoted_score_threshold(public_score: float | None) -> bool:
    """Return True if a public score clears the promotion threshold."""
    if public_score is None:
        return False
    return public_score >= PROMOTION_PUBLIC_THRESHOLD


def verify_lineage_cycle_linkage(
    lineage: dict[str, Any], cycle: dict[str, Any]
) -> list[str]:
    """Verify that a weekly cycle receipt links correctly to the lineage.

    Returns a list of linkage issues (empty = all good).
    """
    issues: list[str] = []
    cycle_data = cycle.get("cycle", {})
    gen_ref = cycle_data.get("generation_ref", {})
    gen_id = gen_ref.get("generation_id")

    if gen_id is None:
        issues.append("weekly cycle generation_ref.generation_id is null")
        return issues

    generations = {
        g["generation_id"]: g for g in lineage.get("generations", [])
    }
    if gen_id not in generations:
        issues.append(
            f"weekly cycle references generation '{gen_id}' "
            "which is not in the lineage registry"
        )
        return issues

    gen = generations[gen_id]

    # Score consistency
    cycle_score = cycle_data.get("promotion_decision", {}).get("public_score")
    gen_score = gen.get("promotion_decision", {}).get("public_score")
    if cycle_score is not None and gen_score is not None:
        if abs(cycle_score - gen_score) > 0.001:
            issues.append(
                f"public_score mismatch: cycle={cycle_score}, gen={gen_score}"
            )

    # Decision consistency
    cycle_decision = cycle_data.get("promotion_decision", {}).get("decision")
    gen_decision = gen.get("promotion_decision", {}).get("decision")
    if cycle_decision != gen_decision:
        issues.append(
            f"promotion decision mismatch: cycle={cycle_decision}, gen={gen_decision}"
        )

    return issues


__all__ = [
    "LINEAGE_REGISTRY_PATH",
    "LINEAGE_SCHEMA_PATH",
    "WEEKLY_CYCLE_PATH",
    "WEEKLY_CYCLE_SCHEMA_PATH",
    "check_promoted_score_threshold",
    "load_lineage_registry",
    "load_weekly_cycle",
    "validate_lineage_registry",
    "validate_weekly_cycle",
    "verify_lineage_cycle_linkage",
]
