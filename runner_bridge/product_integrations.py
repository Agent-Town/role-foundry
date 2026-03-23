"""ERC-8004 + Base / agent0-sdk product-integration writer.

This module owns the *local* integration-artifact layer that Role Foundry
writes after a run completes.  It:

  1.  Hashes receipt/scorecard artifacts that already exist.
  2.  Evaluates local guardrail checks against public/private artifacts.
  3.  Drafts an ERC-8004 registration payload and agent0-sdk wiring plan
      targeting **Base** (Sepolia for review, mainnet for submission).
  4.  Writes a completion template that stays in ``awaiting_wallet_confirmation``
      until a real confirmed tx fills every required field.

Nothing in this module fakes a wallet session, onchain tx, or minting receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEALED_TEXT_KEYS = {"holdout_prompt", "teacher_prompt", "scoring_rubric"}

PUBLIC_SCAN_PATHS = (
    "request.json",
    "artifact-bundle.json",
    "result.json",
    "transcript.ndjson",
    "receipts/manifest.json",
    "receipts/candidate.json",
    "receipts/baseline.json",
    "receipts/evaluation.json",
    "receipts/evidence-index.json",
    "receipts/summary.md",
)

# Base chain config — env-driven, no hardcoded registry/subgraph fakes.
BASE_SEPOLIA_CHAIN_ID = 84532
BASE_MAINNET_CHAIN_ID = 8453

DEFAULT_TARGET_CHAIN = "base_sepolia"

CHAIN_CONFIG: dict[str, dict[str, Any]] = {
    "base_sepolia": {
        "chain_id": BASE_SEPOLIA_CHAIN_ID,
        "label": "Base Sepolia (review/demo default)",
        "rpc_url_env": "BASE_SEPOLIA_RPC_URL",
        "registry_env": "BASE_SEPOLIA_REGISTRY",
        "subgraph_env": "BASE_SEPOLIA_SUBGRAPH_URL",
    },
    "base_mainnet": {
        "chain_id": BASE_MAINNET_CHAIN_ID,
        "label": "Base Mainnet (submission target)",
        "rpc_url_env": "BASE_MAINNET_RPC_URL",
        "registry_env": "BASE_MAINNET_REGISTRY",
        "subgraph_env": "BASE_MAINNET_SUBGRAPH_URL",
    },
}


def _resolve_chain_env(chain_key: str) -> dict[str, Any]:
    """Read chain config from env vars.  Returns what is available, never fakes."""
    cfg = CHAIN_CONFIG.get(chain_key, CHAIN_CONFIG[DEFAULT_TARGET_CHAIN])
    return {
        "chain_id": cfg["chain_id"],
        "label": cfg["label"],
        "rpc_url": os.environ.get(cfg["rpc_url_env"], ""),
        "registry_override": os.environ.get(cfg["registry_env"], ""),
        "subgraph_override": os.environ.get(cfg["subgraph_env"], ""),
        "rpc_url_env": cfg["rpc_url_env"],
        "registry_env": cfg["registry_env"],
        "subgraph_env": cfg["subgraph_env"],
        "wired": bool(os.environ.get(cfg["rpc_url_env"])),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def write_product_integrations(
    run_dir: str | Path,
    request: dict[str, Any],
    result: dict[str, Any],
    *,
    target_chain: str = DEFAULT_TARGET_CHAIN,
) -> dict[str, Any]:
    """Write the honest product-integration bundle for one run.

    This layer stays product-owned and local-first:
    - hashes receipt/scorecard artifacts that already exist
    - evaluates local guardrail checks against public/private artifacts
    - drafts an ERC-8004 registration payload for Base via agent0-sdk
    - writes a completion template without faking activation
    """

    run_dir = Path(run_dir)
    integrations_dir = run_dir / "integrations"
    integrations_dir.mkdir(parents=True, exist_ok=True)

    request_public = _load_json(run_dir / "request.json")
    request_private = _load_json(run_dir / "request.private.json")
    artifact_bundle_path = run_dir / "artifact-bundle.json"
    artifact_bundle = _load_json(artifact_bundle_path)

    chain_env = _resolve_chain_env(target_chain)
    verifiable_receipts = _build_verifiable_receipts(run_dir, result)

    # --- ERC-8004 registration draft (local, not minted) ---
    erc8004_draft = _build_erc8004_registration_draft(
        run_id=request.get("run_id"),
        request=request,
        result=result,
        artifact_bundle=artifact_bundle,
        verifiable_receipts=verifiable_receipts,
        chain_env=chain_env,
    )
    erc8004_draft_path = integrations_dir / "erc8004-registration-draft.json"
    erc8004_draft_path.write_text(json.dumps(erc8004_draft, indent=2))

    # --- Completion template (awaiting wallet) ---
    erc8004_completion_template = _build_erc8004_completion_template(
        run_id=request.get("run_id"),
        draft_path=_relative_path(run_dir, erc8004_draft_path),
        verifiable_receipts=verifiable_receipts,
        chain_env=chain_env,
    )
    erc8004_completion_path = integrations_dir / "erc8004-completion-template.json"
    erc8004_completion_path.write_text(json.dumps(erc8004_completion_template, indent=2))

    # --- Base / agent0-sdk adapter contract ---
    agent0_adapter = _build_agent0_base_adapter_contract(
        run_id=request.get("run_id"),
        chain_env=chain_env,
        draft_path=_relative_path(run_dir, erc8004_draft_path),
        completion_path=_relative_path(run_dir, erc8004_completion_path),
    )
    agent0_adapter_path = integrations_dir / "agent0-base-adapter.json"
    agent0_adapter_path.write_text(json.dumps(agent0_adapter, indent=2))

    # --- Locus guardrails ---
    locus_guardrails = _build_locus_guardrails(
        run_dir=run_dir,
        request_public=request_public,
        request_private=request_private,
        result=result,
        verifiable_receipts=verifiable_receipts,
        erc8004_status="draft_ready",
    )

    status_by_integration = {
        "verifiable_receipts": verifiable_receipts["status"],
        "locus_guardrails": locus_guardrails["status"],
        "erc8004_identity": "draft_ready",
        "agent0_base_adapter": "staged" if not chain_env["wired"] else "ready",
    }
    completion_metrics = _build_completion_metrics(status_by_integration)
    demo_claims = _build_demo_claims(status_by_integration, chain_env)

    trust_bundle: dict[str, Any] = {
        "version": 2,
        "run_id": request.get("run_id"),
        "generated_at": _utc_now(),
        "target_chain": chain_env,
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "verifiable_receipts": verifiable_receipts,
        "locus_guardrails": locus_guardrails,
        "erc8004_identity": {
            "status": "draft_ready",
            "recommended_path": "agent0-sdk",
            "agent0_sdk_recommended": True,
            "target_chain": {
                "chain_id": chain_env["chain_id"],
                "label": chain_env["label"],
                "wired": chain_env["wired"],
            },
            "agent0_adapter": agent0_adapter,
            "registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
            "completion_template_path": _relative_path(run_dir, erc8004_completion_path),
            "draft": {
                "token_uri": _relative_path(run_dir, erc8004_draft_path),
                "registrations": [],
            },
            "blocking_requirements": [
                "A human-approved EIP-1193 wallet session is required for any write.",
                f"A Base RPC URL must be set via {chain_env['rpc_url_env']}.",
                "No onchain claim is allowed until the completion record includes chain_id, registry, agent_id, and tx_hash.",
            ],
        },
        "demo_claims": demo_claims,
        "recommended_implementation_order": [
            "verifiable_receipts",
            "locus_guardrails",
            "erc8004_identity",
            "agent0_base_adapter",
        ],
    }

    trust_bundle_path = integrations_dir / "trust-bundle.json"
    trust_bundle_path.write_text(json.dumps(trust_bundle, indent=2))

    summary_path = integrations_dir / "summary.md"
    summary_path.write_text(_build_summary_markdown(trust_bundle))

    # Patch artifact bundle inline summary
    inline_summary = _build_inline_summary(
        trust_bundle,
        trust_bundle_path=_relative_path(run_dir, trust_bundle_path),
        summary_path=_relative_path(run_dir, summary_path),
    )
    artifact_bundle["integration_bundle"] = inline_summary

    artifact_receipts = artifact_bundle.get("receipts") if isinstance(artifact_bundle.get("receipts"), dict) else {}
    artifact_receipts.update(
        {
            "trust_bundle_path": _relative_path(run_dir, trust_bundle_path),
            "integration_summary_path": _relative_path(run_dir, summary_path),
            "erc8004_registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
            "agent0_base_adapter_path": _relative_path(run_dir, agent0_adapter_path),
        }
    )
    artifact_bundle["receipts"] = artifact_receipts
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    summary = {
        "trust_bundle_path": _relative_path(run_dir, trust_bundle_path),
        "summary_path": _relative_path(run_dir, summary_path),
        "erc8004_registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
        "erc8004_completion_template_path": _relative_path(run_dir, erc8004_completion_path),
        "agent0_base_adapter_path": _relative_path(run_dir, agent0_adapter_path),
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
            "wired": chain_env["wired"],
        },
        "agent0_sdk_recommended": True,
        "erc8004_recommended_path": "agent0-sdk",
    }
    result["integrations"] = summary
    return summary


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _build_verifiable_receipts(run_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    receipt_manifest_path = run_dir / "receipts" / "manifest.json"
    evidence_index_path = run_dir / "receipts" / "evidence-index.json"
    summary_path = run_dir / "receipts" / "summary.md"

    public_artifacts: dict[str, dict[str, Any]] = {}
    for relative in (
        "request.json",
        "artifact-bundle.json",
        "result.json",
        "receipts/manifest.json",
        "receipts/evidence-index.json",
        "receipts/summary.md",
        "receipts/candidate.json",
        "receipts/baseline.json",
        "receipts/evaluation.json",
    ):
        path = run_dir / relative
        if path.exists() and path.is_file():
            public_artifacts[relative] = _hash_file(path)

    scorecard = result.get("scorecard") if isinstance(result.get("scorecard"), dict) else {}
    scorecard_hash = _hash_json(scorecard) if scorecard else None

    checks = [
        {
            "id": "receipt_manifest_present",
            "label": "Receipt manifest present",
            "passed": receipt_manifest_path.exists(),
            "detail": _relative_path(run_dir, receipt_manifest_path) if receipt_manifest_path.exists() else "missing",
        },
        {
            "id": "evidence_index_present",
            "label": "Evidence index present",
            "passed": evidence_index_path.exists(),
            "detail": _relative_path(run_dir, evidence_index_path) if evidence_index_path.exists() else "missing",
        },
        {
            "id": "receipt_summary_present",
            "label": "Human-readable receipt summary present",
            "passed": summary_path.exists(),
            "detail": _relative_path(run_dir, summary_path) if summary_path.exists() else "missing",
        },
        {
            "id": "scorecard_hashed",
            "label": "Teacher scorecard hashed",
            "passed": bool(scorecard_hash),
            "detail": scorecard_hash["sha256"] if scorecard_hash else "missing",
        },
    ]

    status = "demo_usable" if all(check["passed"] for check in checks) else "contract_ready"
    return {
        "status": status,
        "receipt_count": len(public_artifacts),
        "public_artifact_hashes": public_artifacts,
        "scorecard_hash": scorecard_hash,
        "checks": checks,
    }


def _build_erc8004_registration_draft(
    *,
    run_id: str | None,
    request: dict[str, Any],
    result: dict[str, Any],
    artifact_bundle: dict[str, Any],
    verifiable_receipts: dict[str, Any],
    chain_env: dict[str, Any],
) -> dict[str, Any]:
    workspace = request.get("workspace_snapshot") if isinstance(request.get("workspace_snapshot"), dict) else {}
    scorecard = result.get("scorecard") if isinstance(result.get("scorecard"), dict) else {}
    aggregate = scorecard.get("aggregate_score") if isinstance(scorecard.get("aggregate_score"), dict) else {}
    passed = aggregate.get("passed")
    total = aggregate.get("total")
    score_line = f"Teacher score {passed}/{total}." if passed is not None and total is not None else "Teacher score pending."
    objective = workspace.get("objective") or "Role Foundry apprentice run artifact"

    return {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": f"Role Foundry Frontend Apprentice — {run_id}",
        "description": f"{objective} {score_line} This draft is local and not yet minted onchain.",
        "image": "about:blank",
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
        },
        "services": [
            {
                "name": "role-foundry-run",
                "type": "web",
                "endpoint": f"runs/{run_id}",
                "description": "Role Foundry run view for this apprentice iteration.",
            },
            {
                "name": "proof-bundle",
                "type": "receipt-bundle",
                "endpoint": "receipts/summary.md",
                "description": "Human-readable receipt summary for the run.",
            },
            {
                "name": "teacher-scorecard",
                "type": "scorecard",
                "endpoint": "result.json#/scorecard",
                "description": "Normalized teacher scorecard receipt.",
            },
        ],
        "registrations": [],
        "extensions": {
            "role_foundry": {
                "run_id": run_id,
                "agent_role": request.get("agent_role"),
                "scenario_set_id": request.get("scenario_set_id"),
                "receipt_manifest_path": "receipts/manifest.json",
                "scorecard_hash": verifiable_receipts.get("scorecard_hash"),
                "status": artifact_bundle.get("status") or result.get("status"),
            }
        },
    }


def _build_erc8004_completion_template(
    *,
    run_id: str | None,
    draft_path: str,
    verifiable_receipts: dict[str, Any],
    chain_env: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "awaiting_wallet_confirmation",
        "run_id": run_id,
        "recommended_path": "agent0-sdk",
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
        },
        "draft_path": draft_path,
        "required_after_mint": [
            "namespace",
            "chain_id",
            "identity_registry",
            "agent_id",
            "tx_hash",
            "minted_at",
            "minted_by",
        ],
        "write_guardrail": "Do not mark ERC-8004 as registered until all required fields are filled from a confirmed wallet transaction.",
        "links": {
            "scorecard_hash": verifiable_receipts.get("scorecard_hash"),
            "receipt_manifest_path": "receipts/manifest.json",
        },
    }


def _build_agent0_base_adapter_contract(
    *,
    run_id: str | None,
    chain_env: dict[str, Any],
    draft_path: str,
    completion_path: str,
) -> dict[str, Any]:
    """Emit the agent0-sdk + Base adapter contract.

    This describes *how* to mint, not a claim that minting happened.
    """
    return {
        "version": 1,
        "owner": "Role Foundry",
        "adapter_id": "role-foundry.agent0-base-adapter.v1",
        "sdk_module": "agent0-sdk",
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
            "rpc_url_configured": chain_env["wired"],
        },
        "wallet_discovery": "discoverEip6963Providers",
        "wallet_connect": "connectEip1193",
        "mint_method": "registerHTTP",
        "registration_strategy": (
            "Write local registration draft first, then let a human-approved "
            "wallet mint with registerHTTP(tokenUri) on Base."
        ),
        "browser_adapter_path": "app/agent0_base_adapter.mjs",
        "browser_flow": [
            "Import agent0_base_adapter.mjs (Role Foundry-owned thin adapter).",
            "Call discoverProviders() to find EIP-6963 wallets.",
            "Call connectWallet(provider) to establish an EIP-1193 session.",
            f"Call initSDK({{ chainId: {chain_env['chain_id']}, rpcUrl, walletProvider }}).",
            "Call createAgentFromDraft(sdk, registrationDraft) to build the agent profile.",
            "Call mintAgent(agent, tokenUri) which calls agent.registerHTTP(tokenUri).",
            "On confirmed tx, fill the completion template with chain_id, registry, agent_id, tx_hash.",
        ],
        "env_requirements": {
            "rpc_url": chain_env["rpc_url_env"],
            "registry_override": chain_env["registry_env"],
            "subgraph_override": chain_env["subgraph_env"],
        },
        "draft_path": draft_path,
        "completion_path": completion_path,
        "blocking_requirements": [
            "agent0-sdk must be available (npm or vendored ESM bundle).",
            "An EIP-6963/EIP-1193 compatible wallet must be present in the browser.",
            f"RPC URL for chain {chain_env['chain_id']} must be configured.",
            "Human wallet approval is required before any onchain write.",
        ],
    }


def _build_locus_guardrails(
    *,
    run_dir: Path,
    request_public: dict[str, Any],
    request_private: dict[str, Any],
    result: dict[str, Any],
    verifiable_receipts: dict[str, Any],
    erc8004_status: str,
) -> dict[str, Any]:
    sealed_texts = sorted(_extract_sealed_texts(request_private))
    leak_matches = _scan_public_artifacts_for_sealed_texts(run_dir, sealed_texts)
    scorecard_hash = verifiable_receipts.get("scorecard_hash") if isinstance(verifiable_receipts.get("scorecard_hash"), dict) else None

    checks = [
        {
            "id": "sealed_holdout_redaction",
            "label": "Sealed holdout text stays out of public artifacts",
            "passed": len(leak_matches) == 0,
            "detail": "No sealed prompt leakage detected." if not leak_matches else f"Leak detected in {len(leak_matches)} public artifact(s).",
            "evidence": leak_matches,
        },
        {
            "id": "receipt_bundle_complete",
            "label": "Receipt bundle exists for independent inspection",
            "passed": verifiable_receipts.get("status") == "demo_usable",
            "detail": verifiable_receipts.get("status"),
        },
        {
            "id": "scorecard_claim_is_hashed",
            "label": "Scorecard claim is anchored to a content hash",
            "passed": bool(scorecard_hash),
            "detail": scorecard_hash.get("sha256") if scorecard_hash else "missing",
        },
        {
            "id": "erc8004_claim_is_staged",
            "label": "ERC-8004 claim stays in draft state until a confirmed tx exists",
            "passed": erc8004_status == "draft_ready",
            "detail": erc8004_status,
        },
    ]

    status = "demo_usable" if all(check["passed"] for check in checks) else "blocked"
    return {
        "status": status,
        "provider": "Locus",
        "mode": "local-contract",
        "policy_id": "role-foundry.locus-guardrails.v1",
        "checks": checks,
        "sealed_text_count": len(sealed_texts),
        "public_artifact_count": len([p for p in PUBLIC_SCAN_PATHS if (run_dir / p).exists()]),
    }


def _build_completion_metrics(status_by_integration: dict[str, str]) -> dict[str, Any]:
    live = {"demo_usable", "registered", "active", "ready"}
    staged = {"draft_ready", "contract_ready", "staged"}
    return {
        "integration_count": len(status_by_integration),
        "live_now": sum(1 for s in status_by_integration.values() if s in live),
        "staged_now": sum(1 for s in status_by_integration.values() if s in staged),
        "blocked_now": sum(1 for s in status_by_integration.values() if s not in live | staged),
        "status_by_integration": status_by_integration,
    }


def _build_demo_claims(
    status_by_integration: dict[str, str],
    chain_env: dict[str, Any],
) -> dict[str, list[str]]:
    allowed: list[str] = []
    blocked: list[str] = []

    if status_by_integration.get("verifiable_receipts") == "demo_usable":
        allowed.append("Role Foundry emits hashed local receipts and a teacher scorecard judges can inspect.")
    else:
        blocked.append("Role Foundry has a fully verifiable receipt + scorecard bundle for every run.")

    if status_by_integration.get("locus_guardrails") == "demo_usable":
        allowed.append("Role Foundry runs a local Locus-style guardrail contract for redaction, receipt completeness, and staged external claims.")
    else:
        blocked.append("Locus guardrails are fully enforced and passing on this run.")

    # ERC-8004 / Base claims
    chain_label = chain_env["label"]
    if status_by_integration.get("erc8004_identity") == "draft_ready":
        allowed.append(f"Role Foundry can draft an ERC-8004 registration targeting {chain_label} and wire minting through a thin agent0-sdk adapter.")
        blocked.append("This run already minted an ERC-8004 identity onchain.")
    elif status_by_integration.get("erc8004_identity") == "registered":
        allowed.append(f"This run has a confirmed ERC-8004 onchain identity on {chain_label}.")

    # agent0 adapter status
    adapter_status = status_by_integration.get("agent0_base_adapter", "staged")
    if adapter_status == "ready":
        allowed.append(f"The agent0-sdk Base adapter has a configured RPC endpoint for {chain_label}.")
    else:
        allowed.append(f"The agent0-sdk Base adapter contract is staged but the RPC endpoint for {chain_label} is not yet configured.")

    blocked.append("Locus hosted enforcement or partner-managed guardrail SaaS is wired in this repo.")
    return {"allowed": allowed, "blocked": blocked}


def _build_inline_summary(
    trust_bundle: dict[str, Any],
    *,
    trust_bundle_path: str,
    summary_path: str,
) -> dict[str, Any]:
    return {
        "status_by_integration": trust_bundle["status_by_integration"],
        "completion_metrics": trust_bundle["completion_metrics"],
        "target_chain": trust_bundle.get("target_chain", {}),
        "paths": {
            "trust_bundle_path": trust_bundle_path,
            "summary_path": summary_path,
            "registration_draft_path": trust_bundle["erc8004_identity"]["registration_draft_path"],
        },
    }


def _build_summary_markdown(bundle: dict[str, Any]) -> str:
    metrics = bundle.get("completion_metrics") if isinstance(bundle.get("completion_metrics"), dict) else {}
    claims = bundle.get("demo_claims") if isinstance(bundle.get("demo_claims"), dict) else {}
    erc8004 = bundle.get("erc8004_identity") if isinstance(bundle.get("erc8004_identity"), dict) else {}
    chain = bundle.get("target_chain") if isinstance(bundle.get("target_chain"), dict) else {}

    lines = [
        "# Product Integrations Summary",
        "",
        f"- Run id: `{bundle.get('run_id')}`",
        f"- Generated at: `{bundle.get('generated_at')}`",
        f"- Target chain: `{chain.get('label', 'unknown')}` (chain id {chain.get('chain_id', '?')})",
        f"- RPC wired: `{chain.get('wired', False)}`",
        f"- Live now: `{metrics.get('live_now', 0)}` / `{metrics.get('integration_count', 4)}`",
        f"- Staged now: `{metrics.get('staged_now', 0)}`",
        f"- Blocked now: `{metrics.get('blocked_now', 0)}`",
        "",
        "## Status by integration",
        "",
        f"- Verifiable receipts / scorecards: `{bundle.get('status_by_integration', {}).get('verifiable_receipts')}`",
        f"- Locus guardrails: `{bundle.get('status_by_integration', {}).get('locus_guardrails')}`",
        f"- ERC-8004 identity: `{bundle.get('status_by_integration', {}).get('erc8004_identity')}`",
        f"- agent0 Base adapter: `{bundle.get('status_by_integration', {}).get('agent0_base_adapter')}`",
        "",
        "## agent0-sdk / Base wiring",
        "",
        f"- Recommended path: `{erc8004.get('recommended_path')}`",
        f"- Registration draft: `{erc8004.get('registration_draft_path')}`",
        f"- Completion template: `{erc8004.get('completion_template_path')}`",
        "- Mint flow: `discoverEip6963Providers` → `connectEip1193` → `SDK({ chainId, rpcUrl, walletProvider })` → `createAgent(...)` → `registerHTTP(tokenUri)`",
        "",
        "## Allowed demo claims",
        "",
    ]
    for claim in claims.get("allowed", []):
        lines.append(f"- {claim}")
    lines.extend(["", "## Blocked demo claims", ""])
    for claim in claims.get("blocked", []):
        lines.append(f"- {claim}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _extract_sealed_texts(value: Any, key_hint: str | None = None) -> set[str]:
    results: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            results.update(_extract_sealed_texts(item, key_hint=str(key)))
        return results
    if isinstance(value, list):
        for item in value:
            results.update(_extract_sealed_texts(item, key_hint=key_hint))
        return results
    if isinstance(value, str) and key_hint in SEALED_TEXT_KEYS:
        text = value.strip()
        if text:
            results.add(text)
    return results


def _scan_public_artifacts_for_sealed_texts(run_dir: Path, sealed_texts: list[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for relative in PUBLIC_SCAN_PATHS:
        path = run_dir / relative
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(errors="replace")
        hit_count = sum(1 for sealed in sealed_texts if sealed and sealed in text)
        if hit_count:
            matches.append({"path": relative, "match_count": hit_count})
    return matches


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _hash_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _hash_json(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}


def _relative_path(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
