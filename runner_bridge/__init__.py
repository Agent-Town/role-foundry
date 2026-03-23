"""Role Foundry runner bridge package."""

from .contract import ContractError, RunRequest
from .bridge import RunBridge, ClawithRunClient
from .packet_runtime import (
    EvalContractRef,
    EvidenceContract,
    MutationBudget,
    PacketRunObject,
    build_run_object,
    load_all_run_objects,
    load_run_object,
)
from .promotion_gates import (
    DataAvailability,
    GateStatus,
    GateVerdict,
    PromotionReport,
    build_promotion_report,
    evaluate_holdout_gate,
    evaluate_regression_gate,
    evaluate_stability_gate,
)

__all__ = [
    "ClawithRunClient",
    "ContractError",
    "DataAvailability",
    "EvalContractRef",
    "EvidenceContract",
    "GateStatus",
    "GateVerdict",
    "MutationBudget",
    "PacketRunObject",
    "PromotionReport",
    "RunBridge",
    "RunRequest",
    "build_promotion_report",
    "build_run_object",
    "evaluate_holdout_gate",
    "evaluate_regression_gate",
    "evaluate_stability_gate",
    "load_all_run_objects",
    "load_run_object",
]
