from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .product_integrations import (
    CHAIN_CONFIG,
    DEFAULT_TARGET_CHAIN,
    LIVE_MINT_GATE_ENV,
    LIVE_MINT_PRIVATE_KEY_ENV,
    _load_json,
    _resolve_chain_env,
)


class MintConfigError(RuntimeError):
    """Raised when the explicit live-mint gate or inputs are not satisfied."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explicitly mint a Role Foundry ERC-8004 identity via the Python agent0 SDK"
    )
    parser.add_argument("--run-dir", required=True, help="Path to the run directory that already has integrations/")
    parser.add_argument("--token-uri", required=True, help="Public HTTP(S) token URI for the hosted registration draft JSON")
    parser.add_argument(
        "--target-chain",
        default=DEFAULT_TARGET_CHAIN,
        choices=sorted(CHAIN_CONFIG.keys()),
        help="Base chain target to mint on",
    )
    parser.add_argument(
        "--private-key",
        help=f"Signer private key. Defaults to ${LIVE_MINT_PRIVATE_KEY_ENV} or $AGENT0_PRIVATE_KEY",
    )
    parser.add_argument("--registry-override", help="Optional identity-registry override address")
    parser.add_argument("--subgraph-override", help="Optional subgraph override URL")
    parser.add_argument("--timeout", type=int, default=180, help="wait_confirmed timeout in seconds")
    parser.add_argument(
        "--promoted-public",
        action="store_true",
        help="Required explicit human gate: only promoted/public generations may be minted",
    )
    return parser


def mint_erc8004_registration(
    run_dir: str | Path,
    *,
    token_uri: str,
    target_chain: str = DEFAULT_TARGET_CHAIN,
    private_key: str | None = None,
    registry_override: str | None = None,
    subgraph_override: str | None = None,
    timeout: int = 180,
    promoted_public: bool = False,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    integrations_dir = run_dir / "integrations"
    draft_path = integrations_dir / "erc8004-registration-draft.json"
    template_path = integrations_dir / "erc8004-completion-template.json"

    if not integrations_dir.exists():
        raise MintConfigError(f"missing integrations directory: {integrations_dir}")
    if os.environ.get(LIVE_MINT_GATE_ENV) != "1":
        raise MintConfigError(
            f"live mint is disabled; set {LIVE_MINT_GATE_ENV}=1 to allow an explicit Python mint"
        )
    if not promoted_public:
        raise MintConfigError("refusing to mint without --promoted-public")
    if not token_uri.startswith(("http://", "https://")):
        raise MintConfigError("token_uri must be an HTTP(S) URL")
    if not draft_path.exists():
        raise MintConfigError(f"missing registration draft: {draft_path}")
    if not template_path.exists():
        raise MintConfigError(f"missing completion template: {template_path}")

    chain_env = _resolve_chain_env(target_chain)
    if not chain_env["rpc_url"]:
        raise MintConfigError(
            f"missing {chain_env['rpc_url_env']}; the Python helper requires an explicit Base RPC URL"
        )

    private_key = private_key or os.environ.get(LIVE_MINT_PRIVATE_KEY_ENV) or os.environ.get("AGENT0_PRIVATE_KEY")
    if not private_key:
        raise MintConfigError(
            f"missing signer private key; pass --private-key or set {LIVE_MINT_PRIVATE_KEY_ENV}"
        )

    draft = _load_json(draft_path)
    template = _load_json(template_path)

    agent0_sdk = _import_agent0_sdk()
    sdk_kwargs: dict[str, Any] = {
        "chainId": chain_env["chain_id"],
        "rpcUrl": chain_env["rpc_url"],
        "signer": private_key,
    }

    effective_registry = registry_override or chain_env["registry_override"]
    if effective_registry:
        sdk_kwargs["registryOverrides"] = {chain_env["chain_id"]: {"IDENTITY": effective_registry}}
    effective_subgraph = subgraph_override or chain_env["subgraph_override"]
    if effective_subgraph:
        sdk_kwargs["subgraphOverrides"] = {chain_env["chain_id"]: effective_subgraph}

    sdk = agent0_sdk.SDK(**sdk_kwargs)
    agent = sdk.createAgent(
        name=str(draft.get("name") or f"Role Foundry Run {draft.get('extensions', {}).get('role_foundry', {}).get('run_id') or ''}").strip(),
        description=str(draft.get("description") or "Role Foundry ERC-8004 registration").strip(),
        image=str(draft.get("image") or "about:blank"),
    )

    metadata = _build_agent0_metadata(draft, token_uri=token_uri, promoted_public=promoted_public)
    if metadata and hasattr(agent, "setMetadata"):
        agent.setMetadata(metadata)

    tx_handle = agent.register(token_uri)
    confirmed = tx_handle.wait_confirmed(timeout=timeout)

    tx_hash = _normalize_hex(getattr(tx_handle, "tx_hash", None))
    receipt = _as_dict(getattr(confirmed, "receipt", None))
    tx_hash = tx_hash or _normalize_hex(receipt.get("transactionHash"))
    result_obj = getattr(confirmed, "result", None)
    result_payload = _as_dict(result_obj)
    agent_id = result_payload.get("agentId")
    agent_uri = result_payload.get("agentURI") or token_uri

    completion = build_completion_record(
        template=template,
        chain_env=chain_env,
        token_uri=token_uri,
        identity_registry=_extract_contract_address(getattr(sdk, "identity_registry", None)),
        agent_id=agent_id,
        agent_uri=agent_uri,
        tx_hash=tx_hash,
        minted_by=_extract_minted_by(sdk),
        receipt=receipt,
        result_payload=result_payload,
    )

    completion_path = integrations_dir / "erc8004-completion.json"
    completion_path.write_text(json.dumps(completion, indent=2))

    return {
        "status": "registered",
        "run_dir": str(run_dir),
        "target_chain": {
            "chain_id": chain_env["chain_id"],
            "label": chain_env["label"],
        },
        "completion_path": str(completion_path),
        "token_uri": token_uri,
        "agent_id": agent_id,
        "agent_uri": agent_uri,
        "tx_hash": tx_hash,
    }


def build_completion_record(
    *,
    template: dict[str, Any],
    chain_env: dict[str, Any],
    token_uri: str,
    identity_registry: str | None,
    agent_id: str | None,
    agent_uri: str | None,
    tx_hash: str | None,
    minted_by: str | None,
    receipt: dict[str, Any],
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    explorer_url = None
    if tx_hash and chain_env.get("explorer_base"):
        explorer_url = f"{chain_env['explorer_base']}/tx/{tx_hash}"

    completion = dict(template)
    completion.update(
        {
            "status": "registered",
            "namespace": "erc8004",
            "chain_id": chain_env["chain_id"],
            "chain_label": chain_env["label"],
            "identity_registry": identity_registry,
            "agent_id": agent_id,
            "agent_uri": agent_uri,
            "token_uri": token_uri,
            "tx_hash": tx_hash,
            "explorer_url": explorer_url,
            "minted_at": _utc_now(),
            "minted_by": minted_by,
            "confirmation": {
                "receipt": receipt,
                "result": result_payload,
            },
            "promotion": {
                "decision": "promoted_public",
                "eligible_for_public_issuance": True,
            },
        }
    )
    return completion


def _import_agent0_sdk() -> Any:
    try:
        module = importlib.import_module("agent0_sdk")
    except ImportError as exc:
        raise MintConfigError("agent0-sdk is not installed; run `pip install agent0-sdk`") from exc
    sdk_cls = getattr(module, "SDK", None)
    if sdk_cls is None:
        raise MintConfigError("agent0_sdk.SDK is unavailable in the installed package")
    return module


def _build_agent0_metadata(
    draft: dict[str, Any],
    *,
    token_uri: str,
    promoted_public: bool,
) -> dict[str, Any]:
    extension = ((draft.get("extensions") or {}).get("role_foundry")) or {}
    score = extension.get("score") if isinstance(extension.get("score"), dict) else {}
    aggregate = score.get("aggregate") if isinstance(score.get("aggregate"), dict) else {}
    curriculum = extension.get("curriculum") if isinstance(extension.get("curriculum"), dict) else {}
    proof = extension.get("proof") if isinstance(extension.get("proof"), dict) else {}
    teacher = extension.get("teacher") if isinstance(extension.get("teacher"), dict) else {}

    return {
        "rf_run_id": extension.get("run_id"),
        "rf_agent_role": extension.get("agent_role"),
        "rf_scenario_set_id": extension.get("scenario_set_id"),
        "rf_teacher": teacher.get("name"),
        "rf_score_passed": aggregate.get("passed"),
        "rf_score_total": aggregate.get("total"),
        "rf_score_pass_rate": aggregate.get("pass_rate"),
        "rf_curriculum_theme_count": len(curriculum.get("public_curriculum_themes", []))
        if isinstance(curriculum.get("public_curriculum_themes"), list)
        else 0,
        "rf_proof_manifest": proof.get("receipt_manifest_path"),
        "rf_promotion_decision": "promoted_public" if promoted_public else "human_review_pending",
        "rf_token_uri": token_uri,
    }


def _extract_contract_address(contract: Any) -> str | None:
    if contract is None:
        return None
    address = getattr(contract, "address", None)
    return _normalize_hex(address) or (str(address) if address else None)


def _extract_minted_by(sdk: Any) -> str | None:
    account = getattr(getattr(sdk, "web3_client", None), "account", None)
    address = getattr(account, "address", None)
    return _normalize_hex(address) or (str(address) if address else None)


def _normalize_hex(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if hasattr(value, "hex") and callable(value.hex):
        raw = value.hex()
        if isinstance(raw, str):
            return raw if raw.startswith("0x") else f"0x{raw}"
    text = str(value)
    if not text:
        return None
    return text if text.startswith("0x") else text


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    payload: dict[str, Any] = {}
    for key in ("agentId", "agentURI", "transactionHash", "blockNumber"):
        if hasattr(value, key):
            payload[key] = getattr(value, key)
    if payload:
        return payload
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {"value": value}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = mint_erc8004_registration(
            args.run_dir,
            token_uri=args.token_uri,
            target_chain=args.target_chain,
            private_key=args.private_key,
            registry_override=args.registry_override,
            subgraph_override=args.subgraph_override,
            timeout=args.timeout,
            promoted_public=args.promoted_public,
        )
    except MintConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
