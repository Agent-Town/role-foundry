"""Role Foundry runner bridge package."""

from .bridge import ClawithRunClient, RunBridge
from .contract import ContractError, RunRequest
from .eval_scorecard import build_eval_scorecard, compare_scorecards

__all__ = [
    "ContractError",
    "RunRequest",
    "RunBridge",
    "ClawithRunClient",
    "build_eval_scorecard",
    "compare_scorecards",
]
