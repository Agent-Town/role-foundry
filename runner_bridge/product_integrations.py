from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
AGENT0_WORKSPACE_PATH = "/Users/robin/.openclaw/workspace/agent0lab/agent0-ts"
AGENT0_PRECEDENT_PATHS = [
    "/Users/robin/.openclaw/workspace/Portal/public/erc8004-phase3.md",
    "/Users/robin/.openclaw/workspace/Portal-docs/scripts/build_agent0_sdk_bundle.mjs",
    "/Users/robin/.openclaw/workspace/Portal-docs/e2e/05_erc8004_mint.spec.js",
]
METAMASK_DOC_URL = "https://docs.metamask.io/smart-accounts-kit/"


def write_product_integrations(
    run_dir: str | Path,
    request: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Write the honest product-integration bundle for one run.

    This layer stays product-owned and local-first:
    - it hashes receipt/scorecard artifacts that already exist
    - it evaluates local guardrail checks against public/private artifacts
    - it drafts an ERC-8004 registration payload and agent0-sdk wiring plan
    - it writes a MetaMask delegation intent contract without faking activation
    """

    run_dir = Path(run_dir)
    integrations_dir = run_dir / "integrations"
    integrations_dir.mkdir(parents=True, exist_ok=True)

    request_public = _load_json(run_dir / "request.json")
    request_private = _load_json(run_dir / "request.private.json")
    artifact_bundle_path = run_dir / "artifact-bundle.json"
    artifact_bundle = _load_json(artifact_bundle_path)

    verifiable_receipts = _build_verifiable_receipts(run_dir, result)

    erc8004_draft = _build_erc8004_registration_draft(
        run_id=request.get("run_id"),
        request=request,
        result=result,
        artifact_bundle=artifact_bundle,
        verifiable_receipts=verifiable_receipts,
    )
    erc8004_draft_path = integrations_dir / "erc8004-registration-draft.json"
    erc8004_draft_path.write_text(json.dumps(erc8004_draft, indent=2))

    erc8004_completion_template = _build_erc8004_completion_template(
        run_id=request.get("run_id"),
        draft_path=_relative_path(run_dir, erc8004_draft_path),
        verifiable_receipts=verifiable_receipts,
    )
    erc8004_completion_template_path = integrations_dir / "erc8004-completion-template.json"
    erc8004_completion_template_path.write_text(json.dumps(erc8004_completion_template, indent=2))

    metamask_delegation = _build_metamask_delegation_intent(
        run_id=request.get("run_id"),
        verifiable_receipts=verifiable_receipts,
        completion_template_path=_relative_path(run_dir, erc8004_completion_template_path),
    )
    delegation_path = integrations_dir / "metamask-delegation-intent.json"
    delegation_path.write_text(json.dumps(metamask_delegation, indent=2))

    locus_guardrails = _build_locus_guardrails(
        run_dir=run_dir,
        request_public=request_public,
        request_private=request_private,
        result=result,
        verifiable_receipts=verifiable_receipts,
        erc8004_status="draft_ready",
        metamask_status="contract_ready",
    )

    status_by_integration = {
        "verifiable_receipts": verifiable_receipts["status"],
        "locus_guardrails": locus_guardrails["status"],
        "erc8004_identity": "draft_ready",
        "metamask_delegation": "contract_ready",
    }
    completion_metrics = _build_completion_metrics(status_by_integration)
    demo_claims = _build_demo_claims(status_by_integration)

    trust_bundle = {
        "version": 1,
        "run_id": request.get("run_id"),
        "generated_at": _utc_now(),
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "verifiable_receipts": verifiable_receipts,
        "locus_guardrails": locus_guardrails,
        "erc8004_identity": {
            "status": "draft_ready",
            "recommended_path": "agent0-sdk",
            "agent0_sdk_recommended": True,
            "local_precedent": {
                "workspace_sdk_path": AGENT0_WORKSPACE_PATH,
                "source_files": AGENT0_PRECEDENT_PATHS,
            },
            "agent0_adapter": {
                "owner": "Role Foundry",
                "adapter_id": "role-foundry.agent0-adapter.v1",
                "sdk_module": "agent0-sdk",
                "wallet_discovery": "discoverEip6963Providers",
                "wallet_connect": "connectEip1193",
                "mint_method": "registerHTTP",
                "registration_strategy": "Write local registration draft first, then let a human-approved wallet mint with registerHTTP(tokenUri).",
                "preferred_bundle_strategy": "Thin internal adapter over a vendored or pinned browser bundle built from the existing agent0-ts workspace path.",
                "browser_flow": [
                    "Load a pinned agent0-sdk browser bundle through a Role Foundry-owned adapter.",
                    "Discover EIP-6963 wallets and connect an EIP-1193 provider.",
                    "Create SDK({ chainId, rpcUrl, walletProvider }).",
                    "Build the agent profile from the Role Foundry run and receipt bundle.",
                    "Call createAgent(name, description, image).",
                    "Mint with agent.registerHTTP(tokenUri) only after the human wallet approves.",
                    "Persist the confirmed chain id, registry, agent id, and tx hash into the completion record.",
                ],
            },
            "registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
            "completion_template_path": _relative_path(run_dir, erc8004_completion_template_path),
            "draft": {
                "token_uri": _relative_path(run_dir, erc8004_draft_path),
                "registrations": [],
            },
            "blocking_requirements": [
                "A human-approved EIP-1193 wallet session is required for any write.",
                "A supported chain + rpcUrl must be configured explicitly.",
                "No onchain claim is allowed until the completion record includes chain id, registry, agent id, and tx hash.",
            ],
        },
        "metamask_delegation": {
            "status": "contract_ready",
            "recommended_path": "MetaMask Smart Accounts Kit",
            "documentation_url": METAMASK_DOC_URL,
            "intent_path": _relative_path(run_dir, delegation_path),
            "scope": "Future smart-account delegation is limited to completing one approved ERC-8004 identity registration for this run.",
            "blocking_requirements": [
                "A delegated smart account or equivalent MetaMask permission flow is not configured in this repo yet.",
                "A human wallet approval step is still required before any delegated execution can become active.",
                "No arbitrary contract-call delegation is permitted by this contract.",
            ],
        },
        "demo_claims": demo_claims,
        "recommended_implementation_order": [
            "verifiable_receipts",
            "locus_guardrails",
            "erc8004_identity",
            "metamask_delegation",
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
            "metamask_delegation_intent_path": _relative_path(run_dir, delegation_path),
        }
    )
    artifact_bundle["receipts"] = artifact_receipts
    artifact_bundle_path.write_text(json.dumps(artifact_bundle, indent=2))

    summary = {
        "trust_bundle_path": _relative_path(run_dir, trust_bundle_path),
        "summary_path": _relative_path(run_dir, summary_path),
        "erc8004_registration_draft_path": _relative_path(run_dir, erc8004_draft_path),
        "erc8004_completion_template_path": _relative_path(run_dir, erc8004_completion_template_path),
        "metamask_delegation_intent_path": _relative_path(run_dir, delegation_path),
        "status_by_integration": status_by_integration,
        "completion_metrics": completion_metrics,
        "agent0_sdk_recommended": True,
        "erc8004_recommended_path": "agent0-sdk",
    }
    result["integrations"] = summary
    return summary


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
    scorecard_present = bool(scorecard_hash)

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
            "passed": scorecard_present,
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
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "awaiting_wallet_confirmation",
        "run_id": run_id,
        "recommended_path": "agent0-sdk",
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


def _build_metamask_delegation_intent(
    *,
    run_id: str | None,
    verifiable_receipts: dict[str, Any],
    completion_template_path: str,
) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "contract_ready",
        "run_id": run_id,
        "recommended_path": "MetaMask Smart Accounts Kit",
        "scope": "Only allow one approved identity-completion flow for the matching Role Foundry run.",
        "delegated_action": {
            "id": "erc8004.complete_registration",
            "description": "Complete one previously drafted ERC-8004 registration after explicit human approval.",
            "max_uses": 1,
            "requires_run_id": run_id,
            "requires_scorecard_hash": verifiable_receipts.get("scorecard_hash", {}).get("sha256"),
            "completion_template_path": completion_template_path,
        },
        "blocked_actions": [
            "arbitrary_contract_call",
            "arbitrary_token_transfer",
            "scorecard_publication_without_receipt_hash",
            "guardrail_policy_mutation",
        ],
        "activation_requirements": [
            "Provision a MetaMask smart account or equivalent advanced-permissions surface.",
            "Have the human wallet approve the permission grant.",
            "Record a delegation activation receipt before claiming the permission is live.",
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
    metamask_status: str,
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
        {
            "id": "delegation_claim_is_staged",
            "label": "MetaMask delegation claim stays non-active until a permission receipt exists",
            "passed": metamask_status == "contract_ready",
            "detail": metamask_status,
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
        "public_artifact_count": len([path for path in PUBLIC_SCAN_PATHS if (run_dir / path).exists()]),
    }


def _build_completion_metrics(status_by_integration: dict[str, str]) -> dict[str, Any]:
    demo_usable = {"demo_usable", "registered", "active"}
    contract_only = {"draft_ready", "contract_ready"}

    return {
        "integration_count": len(status_by_integration),
        "demo_usable_now": sum(1 for status in status_by_integration.values() if status in demo_usable),
        "contract_only_now": sum(1 for status in status_by_integration.values() if status in contract_only),
        "blocked_now": sum(1 for status in status_by_integration.values() if status not in demo_usable | contract_only),
        "status_by_integration": status_by_integration,
    }


def _build_demo_claims(status_by_integration: dict[str, str]) -> dict[str, list[str]]:
    allowed = []
    blocked = []

    if status_by_integration.get("verifiable_receipts") == "demo_usable":
        allowed.append("Role Foundry emits hashed local receipts and a teacher scorecard judges can inspect.")
    else:
        blocked.append("Role Foundry has a fully verifiable receipt + scorecard bundle for every run.")

    if status_by_integration.get("locus_guardrails") == "demo_usable":
        allowed.append("Role Foundry runs a local Locus-style guardrail contract for redaction, receipt completeness, and staged external claims.")
    else:
        blocked.append("Locus guardrails are fully enforced and passing on this run.")

    if status_by_integration.get("erc8004_identity") == "draft_ready":
        allowed.append("Role Foundry can draft an ERC-8004 registration and wire minting through a thin internal agent0-sdk adapter.")
        blocked.append("This run already minted an ERC-8004 identity onchain.")
    elif status_by_integration.get("erc8004_identity") == "registered":
        allowed.append("This run has a confirmed ERC-8004 onchain identity receipt.")
    else:
        blocked.append("Role Foundry has an ERC-8004 identity path ready for this run.")

    if status_by_integration.get("metamask_delegation") == "contract_ready":
        allowed.append("Role Foundry defines a constrained MetaMask delegation intent for future identity completion, but it is not active yet.")
        blocked.append("MetaMask delegation is active or exercised on this run.")
    elif status_by_integration.get("metamask_delegation") == "active":
        allowed.append("A constrained MetaMask delegation receipt is active for this run.")
    else:
        blocked.append("MetaMask delegation is ready to use in this repo right now.")

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
        "verifiable_receipts": trust_bundle["verifiable_receipts"],
        "locus_guardrails": trust_bundle["locus_guardrails"],
        "erc8004_identity": trust_bundle["erc8004_identity"],
        "metamask_delegation": trust_bundle["metamask_delegation"],
        "demo_claims": trust_bundle["demo_claims"],
        "paths": {
            "trust_bundle_path": trust_bundle_path,
            "summary_path": summary_path,
            "registration_draft_path": trust_bundle["erc8004_identity"]["registration_draft_path"],
            "delegation_intent_path": trust_bundle["metamask_delegation"]["intent_path"],
        },
    }


def _build_summary_markdown(bundle: dict[str, Any]) -> str:
    metrics = bundle.get("completion_metrics") if isinstance(bundle.get("completion_metrics"), dict) else {}
    claims = bundle.get("demo_claims") if isinstance(bundle.get("demo_claims"), dict) else {}
    erc8004 = bundle.get("erc8004_identity") if isinstance(bundle.get("erc8004_identity"), dict) else {}
    delegation = bundle.get("metamask_delegation") if isinstance(bundle.get("metamask_delegation"), dict) else {}

    lines = [
        "# Product Integrations Summary",
        "",
        f"- Run id: `{bundle.get('run_id')}`",
        f"- Generated at: `{bundle.get('generated_at')}`",
        f"- Demo-usable now: `{metrics.get('demo_usable_now', 0)}` / `{metrics.get('integration_count', 4)}`",
        f"- Contract-only now: `{metrics.get('contract_only_now', 0)}`",
        f"- Blocked now: `{metrics.get('blocked_now', 0)}`",
        "",
        "## Status by integration",
        "",
        f"- Verifiable receipts / scorecards: `{bundle.get('status_by_integration', {}).get('verifiable_receipts')}`",
        f"- Locus guardrails: `{bundle.get('status_by_integration', {}).get('locus_guardrails')}`",
        f"- ERC-8004 identity: `{bundle.get('status_by_integration', {}).get('erc8004_identity')}`",
        f"- MetaMask Delegation: `{bundle.get('status_by_integration', {}).get('metamask_delegation')}`",
        "",
        "## agent0-sdk wiring",
        "",
        f"- Recommended path: `{erc8004.get('recommended_path')}`",
        f"- Registration draft: `{erc8004.get('registration_draft_path')}`",
        f"- Completion template: `{erc8004.get('completion_template_path')}`",
        "- Mint flow: `discoverEip6963Providers` → `connectEip1193` → `createAgent(...)` → `registerHTTP(tokenUri)`",
        "",
        "## MetaMask delegation scope",
        "",
        f"- Recommended path: `{delegation.get('recommended_path')}`",
        f"- Intent path: `{delegation.get('intent_path')}`",
        f"- Scope: {delegation.get('scope')}",
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
        hit_count = 0
        for sealed in sealed_texts:
            if sealed and sealed in text:
                hit_count += 1
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
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _hash_json(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }


def _relative_path(root: Path, path: Path) -> str:
    return str(path.relative_to(root))


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
