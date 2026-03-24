"""Runner backend implementations and named backend registry for Role Foundry."""

from __future__ import annotations

import copy
import sys
from typing import Any

_DEFAULT_BACKEND = "local_replay"

_BACKEND_SPECS: dict[str, dict[str, Any]] = {
    "local_replay": {
        "backend_id": "local_replay",
        "entrypoint": "python3 -m runner_bridge.backends.local_replay",
        "module": "runner_bridge.backends.local_replay",
        "mode": "zero_secret_replay",
        "claim_boundary": {
            "executes_commands": "false",
            "native_clawith_parity": "not_claimed",
            "independent_executor_isolation": "not_claimed",
        },
    },
    "claude_vibecosystem": {
        "backend_id": "claude_vibecosystem",
        "surface_version": "0.2.0-beta",
        "entrypoint": "python3 -m runner_bridge.backends.claude_vibecosystem",
        "module": "runner_bridge.backends.claude_vibecosystem",
        "mode": "external_executor_beta",
        "beta_status": "live_public_smoke_available",
        "live_public_smoke": {
            "available": True,
            "cli_flag": "--live-public-smoke",
            "description": (
                "Opt-in mode that creates an isolated git worktree, captures honest runtime artifacts, "
                "and executes real verifier commands. When a student_prompt_pack is present, it also "
                "invokes a real Claude Code student step before running the verifiers."
            ),
        },
        "executor": {
            "runtime": "Claude Code",
            "agent_selection": "vibecosystem",
            "default_agent": "backend-dev",
            "prompt_transport": "stdin",
            "workdir_mode": "dedicated_workdir_expected",
        },
        "control_plane": {
            "path": "external_gateway_only",
            "proof_reference": "docs/clawith-vibecosystem-real-path.md",
        },
        "claim_boundary": {
            "native_clawith_parity": "not_claimed",
            "sealed_evaluation": "not_claimed",
            "tamper_proofing": "not_claimed",
            "independent_executor_isolation": "not_claimed",
        },
    },
}


def default_runner_backend() -> str:
    return _DEFAULT_BACKEND


def known_runner_backends() -> tuple[str, ...]:
    return tuple(sorted(_BACKEND_SPECS))


def backend_contract_for_runner(backend_id: str) -> dict[str, Any]:
    try:
        return copy.deepcopy(_BACKEND_SPECS[backend_id])
    except KeyError as exc:
        raise ValueError(f"unknown runner backend: {backend_id}") from exc


def backend_command_for_runner(backend_id: str) -> list[str]:
    spec = backend_contract_for_runner(backend_id)
    return [sys.executable, "-m", str(spec["module"])]


__all__ = [
    "backend_command_for_runner",
    "backend_contract_for_runner",
    "default_runner_backend",
    "known_runner_backends",
]
