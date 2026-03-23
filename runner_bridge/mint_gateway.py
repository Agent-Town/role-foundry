"""Server-side ERC-8004 mint gateway for promoted student generations.

This module wraps the Node.js mint helper (app/mint_student_erc8004.mjs) and
provides a Python-callable entry point for the Role Foundry bridge.

Safety model:
  - Live minting is OFF by default.
  - Requires ROLE_FOUNDRY_LIVE_MINT=1 plus SIGNER_PRIVATE_KEY in env.
  - Only promoted/public generations should be minted — caller enforces this.
  - Returns structured result; never fakes onchain state.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MINT_SCRIPT = ROOT / "app" / "mint_student_erc8004.mjs"


def is_live_mint_enabled() -> bool:
    """Check if live minting is explicitly enabled via env."""
    return os.environ.get("ROLE_FOUNDRY_LIVE_MINT", "").strip() in ("1", "true", "yes")


def check_mint_prerequisites() -> dict[str, Any]:
    """Return a diagnostic of what is configured vs missing for live mint."""
    target_chain = os.environ.get("TARGET_CHAIN", "base_sepolia")
    rpc_env = f"BASE_{'MAINNET' if target_chain == 'base_mainnet' else 'SEPOLIA'}_RPC_URL"
    registry_env = f"BASE_{'MAINNET' if target_chain == 'base_mainnet' else 'SEPOLIA'}_REGISTRY"

    checks = {
        "live_mint_enabled": is_live_mint_enabled(),
        "signer_private_key_set": bool(os.environ.get("SIGNER_PRIVATE_KEY")),
        "rpc_url_set": bool(os.environ.get(rpc_env)),
        "registry_set": bool(os.environ.get(registry_env)),
        "mint_script_exists": MINT_SCRIPT.exists(),
        "node_available": _check_node_available(),
        "target_chain": target_chain,
    }
    checks["ready"] = all(checks.values())
    return checks


def mint_student_identity(
    draft_path: str | Path,
    *,
    completion_out: str | Path | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Invoke the Node.js mint helper for a promoted student generation.

    Args:
        draft_path: Path to the ERC-8004 registration draft JSON.
        completion_out: Optional path to write the completion record.
        timeout_seconds: Max time for the mint transaction.

    Returns:
        dict with {ok, data} on success or {ok, error} on failure.

    Raises nothing — always returns a structured result dict.
    """
    if not is_live_mint_enabled():
        return {
            "ok": False,
            "error": "Live minting is disabled. Set ROLE_FOUNDRY_LIVE_MINT=1 to enable.",
            "gated": True,
        }

    if not os.environ.get("SIGNER_PRIVATE_KEY"):
        return {
            "ok": False,
            "error": "SIGNER_PRIVATE_KEY env var is required for server-side minting.",
        }

    draft_path = Path(draft_path)
    if not draft_path.exists():
        return {"ok": False, "error": f"Draft not found: {draft_path}"}

    if not MINT_SCRIPT.exists():
        return {"ok": False, "error": f"Mint script not found: {MINT_SCRIPT}"}

    cmd = ["node", str(MINT_SCRIPT), "--draft", str(draft_path)]
    if completion_out:
        cmd.extend(["--completion-out", str(completion_out)])

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(ROOT),
        )
    except FileNotFoundError:
        return {"ok": False, "error": "Node.js not found on PATH."}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Mint timed out after {timeout_seconds}s."}

    stdout = completed.stdout.strip()
    if not stdout:
        return {
            "ok": False,
            "error": f"Mint script produced no output. stderr: {completed.stderr[:500]}",
        }

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": f"Mint script returned invalid JSON: {stdout[:300]}",
        }

    return result


def _check_node_available() -> bool:
    try:
        subprocess.run(
            ["node", "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
