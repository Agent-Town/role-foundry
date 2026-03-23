"""Tests for the ERC-8004 Base / agent0-sdk adapter integration layer.

These validate that runner_bridge/product_integrations.py:
  - generates Base-targeting registration drafts
  - emits completion templates in awaiting_wallet_confirmation state
  - writes adapter contracts with correct chain/env references
  - reports wired-vs-pending status honestly
  - enforces locus guardrails
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from runner_bridge.product_integrations import (
    BASE_MAINNET_CHAIN_ID,
    BASE_SEPOLIA_CHAIN_ID,
    CHAIN_CONFIG,
    write_product_integrations,
)


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Create a minimal run directory with the artifacts product_integrations expects."""
    run = tmp_path / "run-test-001"
    run.mkdir()

    request = {
        "run_id": "run-test-001",
        "agent_role": "student",
        "scenario_set_id": "public-curriculum-v1",
        "workspace_snapshot": {"objective": "Test objective"},
        "time_budget": {"seconds": 60},
        "cost_budget": {"usd": 1.0},
    }
    (run / "request.json").write_text(json.dumps(request, indent=2))
    (run / "request.private.json").write_text(json.dumps(request, indent=2))

    result = {
        "status": "completed",
        "transcript_path": "transcript.ndjson",
        "artifact_bundle_path": "artifact-bundle.json",
        "machine_score": 0.85,
        "scorecard": {
            "aggregate_score": {"passed": 4, "total": 5, "pass_rate": 0.8},
        },
    }
    (run / "result.json").write_text(json.dumps(result, indent=2))
    (run / "transcript.ndjson").write_text('{"event":"test"}\n')
    (run / "artifact-bundle.json").write_text(json.dumps({"status": "completed"}, indent=2))

    receipts = run / "receipts"
    receipts.mkdir()
    (receipts / "manifest.json").write_text("{}")
    (receipts / "evidence-index.json").write_text("{}")
    (receipts / "summary.md").write_text("# Summary\n")
    (receipts / "candidate.json").write_text("{}")

    return run


@pytest.fixture()
def request_dict() -> dict:
    return {
        "run_id": "run-test-001",
        "agent_role": "student",
        "scenario_set_id": "public-curriculum-v1",
        "workspace_snapshot": {"objective": "Test objective"},
        "time_budget": {"seconds": 60},
        "cost_budget": {"usd": 1.0},
    }


@pytest.fixture()
def result_dict() -> dict:
    return {
        "status": "completed",
        "transcript_path": "transcript.ndjson",
        "artifact_bundle_path": "artifact-bundle.json",
        "machine_score": 0.85,
        "scorecard": {
            "aggregate_score": {"passed": 4, "total": 5, "pass_rate": 0.8},
        },
    }


class TestWriteProductIntegrations:
    def test_returns_summary_with_base_chain_info(self, run_dir, request_dict, result_dict):
        summary = write_product_integrations(run_dir, request_dict, result_dict)

        assert summary["target_chain"]["chain_id"] == BASE_SEPOLIA_CHAIN_ID
        assert summary["agent0_sdk_recommended"] is True
        assert summary["erc8004_recommended_path"] == "agent0-sdk"

    def test_creates_integration_files(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        integrations = run_dir / "integrations"

        assert (integrations / "erc8004-registration-draft.json").exists()
        assert (integrations / "erc8004-completion-template.json").exists()
        assert (integrations / "agent0-base-adapter.json").exists()
        assert (integrations / "trust-bundle.json").exists()
        assert (integrations / "summary.md").exists()

    def test_adapter_status_staged_without_rpc(self, run_dir, request_dict, result_dict):
        # Ensure env var is not set
        os.environ.pop("BASE_SEPOLIA_RPC_URL", None)
        summary = write_product_integrations(run_dir, request_dict, result_dict)

        assert summary["status_by_integration"]["agent0_base_adapter"] == "staged"
        assert summary["target_chain"]["wired"] is False

    def test_adapter_status_ready_with_rpc(self, run_dir, request_dict, result_dict, monkeypatch):
        monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "https://sepolia.base.org")
        summary = write_product_integrations(run_dir, request_dict, result_dict)

        assert summary["status_by_integration"]["agent0_base_adapter"] == "ready"
        assert summary["target_chain"]["wired"] is True

    def test_mainnet_target_chain(self, run_dir, request_dict, result_dict):
        summary = write_product_integrations(
            run_dir, request_dict, result_dict, target_chain="base_mainnet"
        )
        assert summary["target_chain"]["chain_id"] == BASE_MAINNET_CHAIN_ID


class TestRegistrationDraft:
    def test_draft_includes_base_chain(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

        assert draft["target_chain"]["chain_id"] == BASE_SEPOLIA_CHAIN_ID
        assert "Base Sepolia" in draft["target_chain"]["label"]

    def test_draft_not_minted(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

        assert draft["registrations"] == []
        assert "not yet minted" in draft["description"]

    def test_draft_includes_score(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

        assert "4/5" in draft["description"]


class TestCompletionTemplate:
    def test_status_awaiting_wallet(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

        assert template["status"] == "awaiting_wallet_confirmation"
        assert template["recommended_path"] == "agent0-sdk"

    def test_required_after_mint_fields(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

        required = template["required_after_mint"]
        assert "chain_id" in required
        assert "agent_id" in required
        assert "tx_hash" in required

    def test_template_targets_base(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

        assert template["target_chain"]["chain_id"] == BASE_SEPOLIA_CHAIN_ID


class TestAgent0BaseAdapter:
    def test_adapter_contract_shape(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

        assert adapter["owner"] == "Role Foundry"
        assert adapter["sdk_module"] == "agent0-sdk"
        assert adapter["wallet_discovery"] == "discoverEip6963Providers"
        assert adapter["wallet_connect"] == "connectEip1193"
        assert adapter["mint_method"] == "registerHTTP"
        assert adapter["browser_adapter_path"] == "app/agent0_base_adapter.mjs"

    def test_adapter_env_requirements(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

        env = adapter["env_requirements"]
        assert env["rpc_url"] == "BASE_SEPOLIA_RPC_URL"

    def test_adapter_blocking_requirements(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

        blocking = adapter["blocking_requirements"]
        assert any("agent0-sdk" in b for b in blocking)
        assert any("wallet" in b.lower() for b in blocking)
        assert any("RPC" in b for b in blocking)


class TestTrustBundle:
    def test_trust_bundle_version_2(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

        assert bundle["version"] == 2

    def test_trust_bundle_no_metamask_delegation(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

        assert "metamask_delegation" not in bundle
        assert "metamask_delegation" not in bundle["status_by_integration"]

    def test_erc8004_identity_draft_ready(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

        assert bundle["status_by_integration"]["erc8004_identity"] == "draft_ready"
        assert bundle["erc8004_identity"]["status"] == "draft_ready"
        assert bundle["erc8004_identity"]["agent0_sdk_recommended"] is True


class TestLocusGuardrails:
    def test_guardrails_pass_with_complete_receipts(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

        # With scorecard + receipts, guardrails should be demo_usable
        guardrails = bundle.get("locus_guardrails", {})
        erc_check = next(
            (c for c in guardrails.get("checks", []) if c["id"] == "erc8004_claim_is_staged"),
            None,
        )
        assert erc_check is not None
        assert erc_check["passed"] is True

    def test_sealed_text_not_leaked(self, run_dir, request_dict, result_dict):
        """Ensure sealed holdout text in private request doesn't leak to public artifacts."""
        private = json.loads((run_dir / "request.private.json").read_text())
        private["teacher_evaluation"] = {
            "scenarios": [{"holdout_prompt": "SECRET_HOLDOUT_TEXT"}]
        }
        (run_dir / "request.private.json").write_text(json.dumps(private))

        write_product_integrations(run_dir, request_dict, result_dict)
        bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())
        guardrails = bundle["locus_guardrails"]

        redaction_check = next(
            (c for c in guardrails["checks"] if c["id"] == "sealed_holdout_redaction"),
            None,
        )
        assert redaction_check is not None
        assert redaction_check["passed"] is True


class TestSummaryMarkdown:
    def test_summary_mentions_base(self, run_dir, request_dict, result_dict):
        write_product_integrations(run_dir, request_dict, result_dict)
        summary = (run_dir / "integrations" / "summary.md").read_text()

        assert "Base Sepolia" in summary
        assert "agent0" in summary.lower()
        assert "84532" in summary


class TestChainConfig:
    def test_base_sepolia_in_config(self):
        assert "base_sepolia" in CHAIN_CONFIG
        assert CHAIN_CONFIG["base_sepolia"]["chain_id"] == 84532

    def test_base_mainnet_in_config(self):
        assert "base_mainnet" in CHAIN_CONFIG
        assert CHAIN_CONFIG["base_mainnet"]["chain_id"] == 8453
