"""ERC-8004 + Base / agent0-sdk Python product-integration writer.

This module owns the *local* integration-artifact layer that Role Foundry
writes after a run completes. It:

  1.  Hashes stable receipt/scorecard artifacts that already exist.
  2.  Drafts an ERC-8004 registration payload plus a Python agent0-sdk mint
      contract targeting **Base** (Sepolia for review, mainnet for submission).
  3.  Writes a completion template that stays staged/off until a real confirmed
      transaction fills every required field.

Nothing in this module fakes a signer, onchain tx, or minting receipt.
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

BASE_SEPOLIA_CHAIN_ID = 84532
BASE_MAINNET_CHAIN_ID = 8453

DEFAULT_TARGET_CHAIN = "base_sepolia"
LIVE_MINT_GATE_ENV = "ROLE_FOUNDRY_ERC8004_ENABLE_LIVE_MINT"
LIVE_MINT_PRIVATE_KEY_ENV = "ROLE_FOUNDRY_ERC8004_PRIVATE_KEY"

CHAIN_CONFIG: dict[str, dict[str, Any]] = {
    "base_sepolia": {
        "chain_id": BASE_SEPOLIA_CHAIN_ID,
        "label": "Base Sepolia (review/demo default)",
        "rpc_url_env": "BASE_SEPOLIA_RPC_URL",
        "registry_env": "BASE_SEPOLIA_REGISTRY",
        "subgraph_env": "BASE_SEPOLIA_SUBGRAPH_URL",
        "explorer_base": "https://sepolia.basescan.org",
    },
    "base_mainnet": {
        "chain_id": BASE_MAINNET_CHAIN_ID,
        "label": "Base Mainnet (submission target)",
        "rpc_url_env": "BASE_MAINNET_RPC_URL",
        "registry_env": "BASE_MAINNET_REGISTRY",
        "subgraph_env": "BASE_MAINNET_SUBGRAPH_URL",
        "explorer_base": "https://basescan.org",
    },
}


def _resolve_chain_env(chain_key: str) -> dict[str, Any]:
    """Read chain config from env vars without overstating readiness."""
    cfg = CHAIN_CONFIG.get(chain_key, CHAIN_CONFIG[DEFAULT_TARGET_CHAIN])
    rpc_url = os.environ.get(cfg["rpc_url_env"], "")
    registry_override = os.environ.get(cfg["registry_env"], "")
    subgraph_override = os.environ.get(cfg["subgraph_env"], "")
    return {
        "chain_id": cfg["chain_id"],
        "label": cfg["label"],
        "rpc_url": rpc_url,
        "registry_override": registry_override,
        "subgraph_override": subgraph_override,
        "rpc_url_env": cfg["rpc_url_env"],
        "registry_env": cfg["registry_env"],
        "subgraph_env": cfg["subgraph_env"],
        "explorer_base": cfg["explorer_base"],
        "rpc_url_configured": bool(rpc_url),
        "registry_override_configured": bool(registry_override),
        "subgraph_override_configured": bool(subgraph_override),
        "live_mint_default_enabled": os.environ.get(LIVE_MINT_GATE_ENV) == "1",
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
    - drafts an ERC-8004 registration payload for Base via the Python agent0 SDK
    - writes a completion template without faking activation or live minting
    """

    run_dir = Path(run_dir)
    integrations_dir = run_dir / "integrations"
    integrations_dir.mkdir(parents=True, exist_ok=True)

    artifact_bundle_path = run_dir / "artifact-bundle.json"
    artifact_bundle = _load_json(artifact_bundle_path)

    chain_env = _resolve_chain_env(target_chain)
    verifiable_receipts = _build_verifiable_receipts(run_dir, result)

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

    erc8004_completion_template = _build_erc8004_completion_template(
        run_id=request.get("run_id"),
        draft_path=_relative_path(run_dir, erc8004_draft_path),
        verifiable_receipts=verifiable_receipts,
        chain_env=chain_env,
    )
    erc8004_completion_path = integrations_dir / "erc8004-completion-template.json"
    erc8004_completion_path.write_text(json.dumps(erc8004_completion_template, indent=2))

    python_mint_contract = _build_agent0_python_mint_contract(
        run_id=request.get("run_id"),
        chain_env=chain_env,
        draft_path=_relative_path(run_dir, erc8004_draft_path),
        completion_path=_relative_path(run_dir, erc8004_completion_path),
    )
    python_mint_path = integrations_dir / "agent0-python-mint.json"
    python_mint_path.write_text(json.dumps(python_mint_contract, indent=2))

    status_by_integration = {
        "verifiable_receipts": verifiable_receipts["status"],
        "erc8004_identity": "draft_ready",
        "agent0_python_mint": "staged",
    }
    completion_metrics = _build_completion_metrics(status_by_integration)
    demo_claims = _build_demo_claims(status_by_integration, chain_env)

    trust_bundle: dict[str, Any] = {
        "version": 3,
        "run_id": request.get("run_id"),
        "generated_at": _utc_now(),
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
            "rpc_url_configured": chain_env["rpc_url_configured"],
            "registry_override_configured": chain_env["registry_override_configured"],
            "subgraph_override_configured": chain_env["subgraph_override_configured"],
            "live_mint_default_enabled": chain_env["live_mint_default_enabled"],
        },
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "verifiable_receipts": verifiable_receipts,
        "erc8004_identity": {
            "status": "draft_ready",
            "recommended_path": "agent0-sdk-python",
            "agent0_sdk_recommended": True,
            "target_chain": {
                "chain_id": chain_env["chain_id"],
                "label": chain_env["label"],
                "rpc_url_configured": chain_env["rpc_url_configured"],
                "registry_override_configured": chain_env["registry_override_configured"],
                "live_mint_default_enabled": chain_env["live_mint_default_enabled"],
            },
            "python_mint_contract": python_mint_contract,
            "registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
            "completion_template_path": _relative_path(run_dir, erc8004_completion_path),
            "python_mint_path": _relative_path(run_dir, python_mint_path),
            "draft": {
                "local_draft_path": _relative_path(run_dir, erc8004_draft_path),
                "token_uri_required_for_live_mint": True,
                "registrations": [],
            },
            "blocking_requirements": [
                f"Live mint stays off unless {LIVE_MINT_GATE_ENV}=1.",
                "A public HTTP(S) token URI is required for agent.register(tokenUri); local file paths are not mintable.",
                f"A signer private key is required via {LIVE_MINT_PRIVATE_KEY_ENV} or --private-key.",
                f"A Base RPC URL must be set via {chain_env['rpc_url_env']} before calling the Python mint helper.",
                (
                    f"{chain_env['registry_env']} is optional and only needed if you want to override "
                    "the SDK's built-in Base identity registry default."
                ),
                "Only promoted/public generations may be minted, and the mint command must pass --promoted-public explicitly.",
                "No onchain claim is allowed until the completion record includes chain_id, identity_registry, agent_id, agent_uri, token_uri, and tx_hash from a confirmed transaction.",
            ],
        },
        "demo_claims": demo_claims,
        "recommended_implementation_order": [
            "verifiable_receipts",
            "erc8004_identity",
            "agent0_python_mint",
        ],
    }

    trust_bundle_path = integrations_dir / "trust-bundle.json"
    trust_bundle_path.write_text(json.dumps(trust_bundle, indent=2))

    summary_path = integrations_dir / "summary.md"
    summary_path.write_text(_build_summary_markdown(trust_bundle))

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
            "agent0_python_mint_path": _relative_path(run_dir, python_mint_path),
        }
    )
    artifact_bundle["receipts"] = artifact_receipts
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    summary = {
        "trust_bundle_path": _relative_path(run_dir, trust_bundle_path),
        "summary_path": _relative_path(run_dir, summary_path),
        "erc8004_registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
        "erc8004_completion_template_path": _relative_path(run_dir, erc8004_completion_path),
        "agent0_python_mint_path": _relative_path(run_dir, python_mint_path),
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
            "rpc_url_configured": chain_env["rpc_url_configured"],
            "registry_override_configured": chain_env["registry_override_configured"],
            "live_mint_default_enabled": chain_env["live_mint_default_enabled"],
        },
        "agent0_sdk_recommended": True,
        "erc8004_recommended_path": "agent0-sdk-python",
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
    audit_bundle_path = run_dir / "receipts" / "audit-bundle.json"

    public_artifacts: dict[str, dict[str, Any]] = {}
    for relative in (
        "request.json",
        "transcript.ndjson",
        "receipts/manifest.json",
        "receipts/evidence-index.json",
        "receipts/summary.md",
        "receipts/audit-bundle.json",
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
            "id": "audit_bundle_present",
            "label": "Machine-readable audit bundle present",
            "passed": audit_bundle_path.exists(),
            "detail": _relative_path(run_dir, audit_bundle_path) if audit_bundle_path.exists() else "missing",
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

    teacher_output = artifact_bundle.get("teacher_output") if isinstance(artifact_bundle.get("teacher_output"), dict) else {}
    student_view = artifact_bundle.get("student_view") if isinstance(artifact_bundle.get("student_view"), dict) else {}
    public_themes = artifact_bundle.get("public_curriculum_themes")
    if not isinstance(public_themes, list):
        public_themes = scorecard.get("public_curriculum_themes") if isinstance(scorecard.get("public_curriculum_themes"), list) else []

    promotion = {
        "decision": "human_review_pending",
        "eligible_for_public_issuance": False,
        "public_candidate_required": True,
        "notes": "Do not auto-promote from a completed run. A human must explicitly decide the generation is promoted/public before any live mint.",
        "blocked_if": [
            "run is still local-only or draft-only",
            "generation is not explicitly promoted/public",
            "caller cannot provide a public HTTP(S) token URI for the draft",
        ],
    }

    return {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": f"Role Foundry Frontend Apprentice — {run_id}",
        "description": (
            f"{objective} {score_line} This draft is local and not yet minted onchain. "
            "Public issuance remains pending an explicit promoted/public decision."
        ),
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
                "status": artifact_bundle.get("status") or result.get("status"),
                "teacher": teacher_output.get("actor") or scorecard.get("teacher"),
                "curriculum": {
                    "scenario_set_id": request.get("scenario_set_id"),
                    "visible_scenario_count": len(student_view.get("visible_scenarios", [])) if isinstance(student_view.get("visible_scenarios"), list) else 0,
                    "sealed_holdout_count": int(student_view.get("sealed_holdout_count", 0) or 0),
                    "public_curriculum_themes": public_themes,
                },
                "proof": {
                    "receipt_manifest_path": ((result.get("provenance") or {}).get("receipt_manifest_path")) or "receipts/manifest.json",
                    "evidence_index_path": ((result.get("provenance") or {}).get("evidence_index_path")) or "receipts/evidence-index.json",
                    "summary_path": ((result.get("provenance") or {}).get("summary_path")) or "receipts/summary.md",
                    "audit_bundle_path": ((result.get("provenance") or {}).get("audit_bundle_path")) or "receipts/audit-bundle.json",
                    "public_artifact_hashes": verifiable_receipts.get("public_artifact_hashes", {}),
                    "scorecard_hash": verifiable_receipts.get("scorecard_hash"),
                },
                "score": {
                    "aggregate": aggregate,
                    "verdict": scorecard.get("verdict") or teacher_output.get("verdict"),
                },
                "promotion": promotion,
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
        "version": 2,
        "status": "awaiting_explicit_live_mint",
        "run_id": run_id,
        "recommended_path": "agent0-sdk-python",
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
            "explorer_base": chain_env["explorer_base"],
        },
        "draft_path": draft_path,
        "required_after_mint": [
            "namespace",
            "chain_id",
            "identity_registry",
            "agent_id",
            "agent_uri",
            "token_uri",
            "tx_hash",
            "minted_at",
            "minted_by",
        ],
        "write_guardrail": (
            "Do not mark ERC-8004 as registered until a confirmed Python agent0-sdk transaction "
            "fills every required field."
        ),
        "mint_guardrails": [
            f"Live mint stays off unless {LIVE_MINT_GATE_ENV}=1.",
            "The mint command must pass --promoted-public explicitly.",
            "token_uri must be a public HTTP(S) URL that resolves to the registration draft.",
            "Only public/promoted generations may be minted.",
        ],
        "links": {
            "scorecard_hash": verifiable_receipts.get("scorecard_hash"),
            "receipt_manifest_path": "receipts/manifest.json",
            "evidence_index_path": "receipts/evidence-index.json",
            "receipt_summary_path": "receipts/summary.md",
            "audit_bundle_path": "receipts/audit-bundle.json",
        },
    }


def _build_agent0_python_mint_contract(
    *,
    run_id: str | None,
    chain_env: dict[str, Any],
    draft_path: str,
    completion_path: str,
) -> dict[str, Any]:
    """Emit the canonical Python agent0-sdk mint contract.

    This describes *how* to mint, not a claim that minting happened.
    """
    chain_id = chain_env["chain_id"]
    return {
        "version": 2,
        "owner": "Role Foundry",
        "integration_id": "role-foundry.agent0-python-mint.v1",
        "sdk_package": "agent0-sdk",
        "sdk_module": "agent0_sdk",
        "runtime": "python",
        "helper_module": "runner_bridge.erc8004_agent0",
        "helper_entrypoint": (
            "python3 -m runner_bridge.erc8004_agent0 "
            f"--run-dir runtime/runs/{run_id or '<run-id>'} "
            "--token-uri https://example.com/erc8004/run.json --promoted-public"
        ),
        "target_chain": {
            "chain_id": chain_id,
            "label": chain_env["label"],
            "rpc_url_configured": chain_env["rpc_url_configured"],
            "registry_override_configured": chain_env["registry_override_configured"],
            "subgraph_override_configured": chain_env["subgraph_override_configured"],
        },
        "mint_method": "register",
        "confirmation_method": "wait_confirmed",
        "receipt_shape": {
            "handle_fields": ["tx_hash"],
            "confirmation_fields": ["receipt", "result"],
            "result_fields": ["agentId", "agentURI"],
        },
        "registration_strategy": (
            "Write the local registration draft first, host it at an HTTP(S) token URI, then run the Python helper "
            "with an explicit signer and promoted/public gate."
        ),
        "python_flow": [
            "Install the Python SDK with `pip install agent0-sdk`.",
            f"Set {chain_env['rpc_url_env']} to a Base RPC URL.",
            f"Set {LIVE_MINT_PRIVATE_KEY_ENV} (or pass --private-key) for the signer.",
            (
                f"Optionally set {chain_env['registry_env']} and/or {chain_env['subgraph_env']} to override the SDK's "
                "Base defaults."
            ),
            "Host integrations/erc8004-registration-draft.json at a public HTTP(S) token URI.",
            f"Set {LIVE_MINT_GATE_ENV}=1 and run the helper with --promoted-public.",
            (
                "The helper calls SDK(chainId, rpcUrl, signer, registryOverrides?, subgraphOverrides?) -> "
                "createAgent(name, description, image) -> setMetadata(...) -> register(tokenUri) -> wait_confirmed(timeout)."
            ),
            "The helper writes integrations/erc8004-completion.json from the confirmed receipt/result.",
        ],
        "env_requirements": {
            "live_mint_gate": LIVE_MINT_GATE_ENV,
            "private_key": LIVE_MINT_PRIVATE_KEY_ENV,
            "rpc_url": chain_env["rpc_url_env"],
            "registry_override": chain_env["registry_env"],
            "subgraph_override": chain_env["subgraph_env"],
        },
        "draft_path": draft_path,
        "completion_template_path": completion_path,
        "blocking_requirements": [
            "agent0-sdk must be installed in the Python environment.",
            f"{LIVE_MINT_GATE_ENV}=1 must be set explicitly before any live mint.",
            f"RPC URL for chain {chain_id} must be configured via {chain_env['rpc_url_env']}.",
            "A public HTTP(S) token URI must point at the draft JSON.",
            f"A signer private key must be supplied via {LIVE_MINT_PRIVATE_KEY_ENV} or --private-key.",
            "Only promoted/public generations may be minted; sealed/private holdout artifacts must stay local.",
        ],
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

    chain_label = chain_env["label"]
    if status_by_integration.get("erc8004_identity") == "draft_ready":
        allowed.append(
            f"Role Foundry can draft an ERC-8004 registration targeting {chain_label} and hand it to a Python agent0-sdk mint helper."
        )
        blocked.append("This run already minted an ERC-8004 identity onchain.")
    elif status_by_integration.get("erc8004_identity") == "registered":
        allowed.append(f"This run has a confirmed ERC-8004 onchain identity on {chain_label}.")

    if status_by_integration.get("agent0_python_mint") == "staged":
        if chain_env["rpc_url_configured"]:
            allowed.append(
                f"The canonical Python mint path is staged for {chain_label}, and the RPC URL is configured, but live mint remains explicit/off-by-default."
            )
        else:
            allowed.append(
                f"The canonical Python mint path is staged for {chain_label}, but the RPC URL is not configured yet and live mint remains explicit/off-by-default."
            )

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
            "python_mint_path": trust_bundle["erc8004_identity"]["python_mint_path"],
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
        f"- RPC configured: `{chain.get('rpc_url_configured', False)}`",
        f"- Registry override configured: `{chain.get('registry_override_configured', False)}`",
        f"- Live mint default enabled: `{chain.get('live_mint_default_enabled', False)}`",
        f"- Live now: `{metrics.get('live_now', 0)}` / `{metrics.get('integration_count', 4)}`",
        f"- Staged now: `{metrics.get('staged_now', 0)}`",
        f"- Blocked now: `{metrics.get('blocked_now', 0)}`",
        "",
        "## Status by integration",
        "",
        f"- Verifiable receipts / scorecards: `{bundle.get('status_by_integration', {}).get('verifiable_receipts')}`",
        f"- ERC-8004 identity: `{bundle.get('status_by_integration', {}).get('erc8004_identity')}`",
        f"- agent0 Python mint helper: `{bundle.get('status_by_integration', {}).get('agent0_python_mint')}`",
        "",
        "## agent0-sdk Python wiring",
        "",
        f"- Recommended path: `{erc8004.get('recommended_path')}`",
        f"- Registration draft: `{erc8004.get('registration_draft_path')}`",
        f"- Completion template: `{erc8004.get('completion_template_path')}`",
        f"- Python mint contract: `{erc8004.get('python_mint_path')}`",
        "- Mint flow: `SDK(chainId, rpcUrl, signer, registryOverrides?)` → `createAgent(...)` → `setMetadata(...)` → `register(tokenUri)` → `wait_confirmed()`",
        "- Live mint stays off by default and requires explicit `--promoted-public` approval plus a public token URI.",
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
