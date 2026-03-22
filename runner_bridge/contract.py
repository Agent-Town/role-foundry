from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "run_id",
    "agent_role",
    "scenario_set_id",
    "workspace_snapshot",
    "time_budget",
    "cost_budget",
)


class ContractError(ValueError):
    """Raised when a run request or result violates the bridge contract."""


@dataclass
class RunRequest:
    run_id: str
    agent_role: str
    scenario_set_id: str
    workspace_snapshot: Any
    time_budget: Any
    cost_budget: Any
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunRequest":
        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            raise ContractError(f"missing required field(s): {', '.join(missing)}")

        values = {field: payload[field] for field in REQUIRED_FIELDS}
        extras = {k: v for k, v in payload.items() if k not in REQUIRED_FIELDS}
        return cls(**values, extras=extras)

    @classmethod
    def load(cls, path: str | Path) -> "RunRequest":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "run_id": self.run_id,
            "agent_role": self.agent_role,
            "scenario_set_id": self.scenario_set_id,
            "workspace_snapshot": self.workspace_snapshot,
            "time_budget": self.time_budget,
            "cost_budget": self.cost_budget,
        }
        payload.update(self.extras)
        return payload

    def timeout_seconds(self, default: int = 60) -> int:
        budget = self.time_budget
        if isinstance(budget, (int, float)):
            return max(1, int(budget))
        if isinstance(budget, dict):
            if "seconds" in budget:
                return max(1, int(budget["seconds"]))
            if "minutes" in budget:
                return max(1, int(float(budget["minutes"]) * 60))
        return default
