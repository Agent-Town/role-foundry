"""Task-packet → runtime run-object bridge.

Loads a validated curriculum task packet (by acceptance_test_id or raw dict),
cross-references the frozen evaluation contract and role manifest, and produces
a self-contained PacketRunObject that a runner backend can consume without
re-parsing contract files at execution time.

Honest status: this module builds the *input shape* for a run.  Actual
execution still depends on whichever backend is wired (LocalReplayRunner today,
a live executor tomorrow).  The run object carries enough contract metadata
that the backend and receipt layer can enforce mutation budgets, path
constraints, and evidence requirements without reading the registry again.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .contract import ContractError, RunRequest
from .curriculum import (
    EVAL_CONTRACT_PATH,
    FROZEN_DIMENSIONS,
    FROZEN_ROLE_ID,
    FROZEN_ROLE_NAME,
    ROLE_MANIFEST_PATH,
    ROOT,
    SEED_REGISTRY_PATH,
    TASK_SCHEMA_PATH,
    load_evaluation_contract,
    load_registry_task,
    load_role_manifest,
    validate_task_packet,
)


@dataclass(frozen=True)
class MutationBudget:
    """Immutable snapshot of a task packet's mutation budget."""

    tracked_files_max: int
    net_lines_max: int
    overrides_default: bool = False
    override_reason: str | None = None

    @classmethod
    def from_packet(cls, packet: dict[str, Any]) -> MutationBudget:
        raw = packet.get("mutation_budget", {})
        return cls(
            tracked_files_max=raw.get("tracked_files_max", raw.get("max_files", 6)),
            net_lines_max=raw.get("net_lines_max", raw.get("max_lines", 400)),
            overrides_default=bool(raw.get("overrides_default", False)),
            override_reason=raw.get("override_reason"),
        )


@dataclass(frozen=True)
class EvidenceContract:
    """Immutable snapshot of a task packet's evidence requirements."""

    required_artifacts: list[dict[str, Any]]
    provenance_required: bool
    student_visible_only: bool

    @classmethod
    def from_packet(cls, packet: dict[str, Any]) -> EvidenceContract:
        raw = packet.get("evidence_contract", {})
        return cls(
            required_artifacts=list(raw.get("required_artifacts", [])),
            provenance_required=bool(raw.get("provenance_required", True)),
            student_visible_only=bool(raw.get("student_visible_only", True)),
        )


@dataclass(frozen=True)
class EvalContractRef:
    """Pointer to the frozen evaluation contract with its key thresholds."""

    contract_path: str
    version: str
    dimensions: dict[str, float]
    task_pass_weighted_min: float
    task_pass_dimension_floor: float

    @classmethod
    def from_loaded_contract(cls, contract: dict[str, Any]) -> EvalContractRef:
        thresholds = contract.get("thresholds", {})
        task_pass = thresholds.get("task_pass", {})
        return cls(
            contract_path=EVAL_CONTRACT_PATH.relative_to(ROOT).as_posix(),
            version=str(contract.get("version", contract.get("meta", {}).get("version", "1.0.0"))),
            dimensions=dict(FROZEN_DIMENSIONS),
            task_pass_weighted_min=float(task_pass.get("weighted_score_min", 0.80)),
            task_pass_dimension_floor=float(task_pass.get("dimension_floor_min", 0.60)),
        )


def _packet_content_hash(packet: dict[str, Any]) -> str:
    """Stable SHA-256 over the canonical JSON serialisation of a packet."""
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _phase_index(packet: dict[str, Any]) -> int:
    phase = packet.get("phase")
    if isinstance(phase, int):
        return phase
    if isinstance(phase, dict):
        return int(phase.get("index", 0))
    return 0


def _normalise_expected_checks(raw: Any) -> list[dict[str, str]]:
    """Normalise expected_checks to a uniform list-of-dicts shape."""
    if not isinstance(raw, list):
        return []
    result: list[dict[str, str]] = []
    for entry in raw:
        if isinstance(entry, str):
            result.append({"id": entry, "command": entry, "why": ""})
        elif isinstance(entry, dict):
            result.append({
                "id": str(entry.get("id", "")),
                "command": str(entry.get("command", "")),
                "why": str(entry.get("why", "")),
            })
    return result


@dataclass(frozen=True)
class PacketRunObject:
    """A validated, self-contained runtime input derived from a task packet.

    This is the bridge artifact: everything a runner backend needs to know
    about the task, its constraints, and the evaluation contract — without
    needing to re-read the registry or contract files.

    Honest note: this object describes what the run *should* do and what
    constraints apply.  It does NOT claim that execution has happened.
    """

    # --- identity ---
    packet_id: str
    packet_version: str
    packet_content_hash: str
    acceptance_test_id: str
    title: str

    # --- role ---
    role_id: str
    role_name: str
    role_manifest_path: str

    # --- phase ---
    phase_index: int
    phase_label: str

    # --- scope ---
    objective: str
    allowed_paths: list[str]
    blocked_paths: list[str]

    # --- budget ---
    mutation_budget: MutationBudget
    time_budget_minutes: int

    # --- checks ---
    expected_checks: list[dict[str, str]]

    # --- evaluation ---
    eval_contract_ref: EvalContractRef
    evidence_contract: EvidenceContract

    # --- receipt / output ---
    run_id: str
    receipt_output_dir: str  # relative to artifacts_root
    run_object_version: str = "1.0.0"

    # --- honesty ---
    execution_status: str = "not_started"
    execution_backend: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_run_request(
        self,
        workspace_snapshot: dict[str, Any] | None = None,
        cost_budget_usd: float = 1.50,
    ) -> RunRequest:
        """Convert this run object into a RunRequest the bridge can execute."""
        snapshot = dict(workspace_snapshot or {})
        snapshot.setdefault("objective", self.objective)
        snapshot.setdefault("changed_files", [])

        extras: dict[str, Any] = {
            "packet_runtime": {
                "packet_id": self.packet_id,
                "packet_version": self.packet_version,
                "packet_content_hash": self.packet_content_hash,
                "acceptance_test_id": self.acceptance_test_id,
                "role_id": self.role_id,
                "phase_index": self.phase_index,
                "mutation_budget": asdict(self.mutation_budget),
                "allowed_paths": self.allowed_paths,
                "blocked_paths": self.blocked_paths,
                "expected_checks": self.expected_checks,
                "eval_contract_ref": asdict(self.eval_contract_ref),
                "evidence_contract": asdict(self.evidence_contract),
                "run_object_version": self.run_object_version,
                "execution_status": self.execution_status,
                "execution_backend": self.execution_backend,
            },
        }

        return RunRequest(
            run_id=self.run_id,
            agent_role="student",
            scenario_set_id=f"packet:{self.acceptance_test_id}",
            workspace_snapshot=snapshot,
            time_budget={"minutes": self.time_budget_minutes},
            cost_budget={"usd": cost_budget_usd},
            extras=extras,
        )


def load_run_object(
    acceptance_test_id: str,
    *,
    run_id: str | None = None,
    artifacts_root: str = "runtime/runs",
) -> PacketRunObject:
    """Load a task packet by acceptance_test_id, validate it, cross-reference
    the evaluation contract, and return a ready-to-execute PacketRunObject.

    Raises ContractError if the packet or contract fails validation.
    """
    if not re.match(r"^[A-E]\d{3}$", acceptance_test_id):
        raise ContractError(
            f"acceptance_test_id must match [A-E]NNN, got: {acceptance_test_id!r}"
        )

    try:
        packet = load_registry_task(acceptance_test_id)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc

    return build_run_object(
        packet,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )


def build_run_object(
    packet: dict[str, Any],
    *,
    run_id: str | None = None,
    artifacts_root: str = "runtime/runs",
) -> PacketRunObject:
    """Build a PacketRunObject from a validated task packet dict.

    This is the lower-level entry point when you already have the packet
    in memory (e.g. from a custom loader or test fixture).
    """
    try:
        validate_task_packet(packet)
    except ValueError as exc:
        raise ContractError(f"packet validation failed: {exc}") from exc

    contract = load_evaluation_contract()

    resolved_run_id = run_id or f"pkt-{packet.get('acceptance_test_id', 'unknown')}-{uuid.uuid4().hex[:8]}"
    receipt_dir = f"{artifacts_root}/{resolved_run_id}/receipts"

    phase = packet.get("phase", {})
    phase_label = phase.get("label", "") if isinstance(phase, dict) else f"Phase {phase}"

    role_manifest = load_role_manifest()
    role_name = role_manifest.get("role", {}).get("name", FROZEN_ROLE_NAME)

    return PacketRunObject(
        packet_id=str(packet.get("task_id", "")),
        packet_version=str(packet.get("packet_version", "1.0.0")),
        packet_content_hash=_packet_content_hash(packet),
        acceptance_test_id=str(packet.get("acceptance_test_id", "")),
        title=str(packet.get("title", "")),
        role_id=str(packet.get("role_id", FROZEN_ROLE_ID)),
        role_name=role_name,
        role_manifest_path=ROLE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
        phase_index=_phase_index(packet),
        phase_label=phase_label,
        objective=str(packet.get("objective", "")),
        allowed_paths=list(packet.get("allowed_paths", [])),
        blocked_paths=list(packet.get("blocked_paths", [])),
        mutation_budget=MutationBudget.from_packet(packet),
        time_budget_minutes=int(packet.get("time_budget_minutes", 60)),
        expected_checks=_normalise_expected_checks(packet.get("expected_checks")),
        eval_contract_ref=EvalContractRef.from_loaded_contract(contract),
        evidence_contract=EvidenceContract.from_packet(packet),
        run_id=resolved_run_id,
        receipt_output_dir=receipt_dir,
    )


def load_all_run_objects(
    *,
    artifacts_root: str = "runtime/runs",
) -> list[PacketRunObject]:
    """Load every task in the public seed registry as a PacketRunObject.

    Useful for batch validation or curriculum-wide runtime checks.
    """
    from .curriculum import load_public_seed_registry

    registry = load_public_seed_registry()
    objects: list[PacketRunObject] = []
    for task in registry.get("tasks", []):
        test_id = task.get("acceptance_test_id", "")
        objects.append(
            build_run_object(
                task,
                run_id=f"pkt-{test_id}-batch",
                artifacts_root=artifacts_root,
            )
        )
    return objects


__all__ = [
    "EvalContractRef",
    "EvidenceContract",
    "MutationBudget",
    "PacketRunObject",
    "build_run_object",
    "load_all_run_objects",
    "load_run_object",
]
