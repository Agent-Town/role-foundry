"""Tests for the ERC-8004 Base / agent0-sdk adapter integration layer.

These validate that runner_bridge/product_integrations.py:
  - generates Base-targeting registration drafts
  - emits completion templates in awaiting_wallet_confirmation state
  - writes adapter contracts with correct chain/env references
  - reports wired-vs-pending status honestly
  - hashes only stable artifacts (not result.json or artifact-bundle.json)

And that runner_bridge.cli wires product_integrations into the run lifecycle.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.product_integrations import (
    BASE_MAINNET_CHAIN_ID,
    BASE_SEPOLIA_CHAIN_ID,
    CHAIN_CONFIG,
    write_product_integrations,
)

ROOT = Path(__file__).resolve().parents[1]


def _make_run_dir(tmp: Path) -> Path:
    """Create a minimal run directory with the artifacts product_integrations expects."""
    run = tmp / "run-test-001"
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


REQUEST_DICT = {
    "run_id": "run-test-001",
    "agent_role": "student",
    "scenario_set_id": "public-curriculum-v1",
    "workspace_snapshot": {"objective": "Test objective"},
    "time_budget": {"seconds": 60},
    "cost_budget": {"usd": 1.0},
}

RESULT_DICT = {
    "status": "completed",
    "transcript_path": "transcript.ndjson",
    "artifact_bundle_path": "artifact-bundle.json",
    "machine_score": 0.85,
    "scorecard": {
        "aggregate_score": {"passed": 4, "total": 5, "pass_rate": 0.8},
    },
}


class TestWriteProductIntegrations(unittest.TestCase):
    def test_returns_summary_with_base_chain_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

            self.assertEqual(summary["target_chain"]["chain_id"], BASE_SEPOLIA_CHAIN_ID)
            self.assertTrue(summary["agent0_sdk_recommended"])
            self.assertEqual(summary["erc8004_recommended_path"], "agent0-sdk")

    def test_creates_integration_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            integrations = run_dir / "integrations"

            self.assertTrue((integrations / "erc8004-registration-draft.json").exists())
            self.assertTrue((integrations / "erc8004-completion-template.json").exists())
            self.assertTrue((integrations / "agent0-base-adapter.json").exists())
            self.assertTrue((integrations / "trust-bundle.json").exists())
            self.assertTrue((integrations / "summary.md").exists())

    def test_adapter_status_staged_without_rpc(self):
        os.environ.pop("BASE_SEPOLIA_RPC_URL", None)
        os.environ.pop("BASE_SEPOLIA_REGISTRY", None)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

            self.assertEqual(summary["status_by_integration"]["agent0_base_adapter"], "staged")
            self.assertFalse(summary["target_chain"]["wired"])

    def test_adapter_status_ready_with_rpc_and_registry(self):
        os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
        os.environ["BASE_SEPOLIA_REGISTRY"] = "0x1234567890abcdef"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = _make_run_dir(Path(tmp))
                summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

                self.assertEqual(summary["status_by_integration"]["agent0_base_adapter"], "ready")
                self.assertTrue(summary["target_chain"]["wired"])
        finally:
            os.environ.pop("BASE_SEPOLIA_RPC_URL", None)
            os.environ.pop("BASE_SEPOLIA_REGISTRY", None)

    def test_not_wired_with_rpc_only(self):
        """RPC alone is not enough — registry is also required for wired status."""
        os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
        os.environ.pop("BASE_SEPOLIA_REGISTRY", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = _make_run_dir(Path(tmp))
                summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

                self.assertFalse(summary["target_chain"]["wired"])
        finally:
            os.environ.pop("BASE_SEPOLIA_RPC_URL", None)

    def test_mainnet_target_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            summary = write_product_integrations(
                run_dir, dict(REQUEST_DICT), dict(RESULT_DICT), target_chain="base_mainnet"
            )
            self.assertEqual(summary["target_chain"]["chain_id"], BASE_MAINNET_CHAIN_ID)


class TestRegistrationDraft(unittest.TestCase):
    def test_draft_includes_base_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertEqual(draft["target_chain"]["chain_id"], BASE_SEPOLIA_CHAIN_ID)
            self.assertIn("Base Sepolia", draft["target_chain"]["label"])

    def test_draft_not_minted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertEqual(draft["registrations"], [])
            self.assertIn("not yet minted", draft["description"])

    def test_draft_includes_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertIn("4/5", draft["description"])


class TestCompletionTemplate(unittest.TestCase):
    def test_status_awaiting_wallet(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertEqual(template["status"], "awaiting_wallet_confirmation")
            self.assertEqual(template["recommended_path"], "agent0-sdk")

    def test_required_after_mint_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            required = template["required_after_mint"]
            self.assertIn("chain_id", required)
            self.assertIn("agent_id", required)
            self.assertIn("tx_hash", required)

    def test_template_targets_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertEqual(template["target_chain"]["chain_id"], BASE_SEPOLIA_CHAIN_ID)


class TestAgent0BaseAdapter(unittest.TestCase):
    def test_adapter_contract_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

            self.assertEqual(adapter["owner"], "Role Foundry")
            self.assertEqual(adapter["sdk_module"], "agent0-sdk")
            self.assertEqual(adapter["wallet_discovery"], "discoverEip6963Providers")
            self.assertEqual(adapter["wallet_connect"], "connectEip1193")
            self.assertEqual(adapter["mint_method"], "registerHTTP")
            self.assertEqual(adapter["browser_adapter_path"], "app/agent0_base_adapter.mjs")

    def test_adapter_env_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

            env = adapter["env_requirements"]
            self.assertEqual(env["rpc_url"], "BASE_SEPOLIA_RPC_URL")

    def test_adapter_blocking_requirements_include_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

            blocking = adapter["blocking_requirements"]
            self.assertTrue(any("agent0-sdk" in b for b in blocking))
            self.assertTrue(any("wallet" in b.lower() for b in blocking))
            self.assertTrue(any("RPC" in b for b in blocking))
            self.assertTrue(any("registry" in b.lower() for b in blocking))


class TestTrustBundle(unittest.TestCase):
    def test_trust_bundle_version_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            self.assertEqual(bundle["version"], 2)

    def test_trust_bundle_no_locus_or_metamask(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            self.assertNotIn("metamask_delegation", bundle)
            self.assertNotIn("metamask_delegation", bundle["status_by_integration"])
            self.assertNotIn("locus_guardrails", bundle)
            self.assertNotIn("locus_guardrails", bundle["status_by_integration"])

    def test_erc8004_identity_draft_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            self.assertEqual(bundle["status_by_integration"]["erc8004_identity"], "draft_ready")
            self.assertEqual(bundle["erc8004_identity"]["status"], "draft_ready")
            self.assertTrue(bundle["erc8004_identity"]["agent0_sdk_recommended"])

    def test_blocking_requirements_mention_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            blocking = bundle["erc8004_identity"]["blocking_requirements"]
            self.assertTrue(any("registry" in b.lower() for b in blocking))


class TestVerifiableReceiptHashing(unittest.TestCase):
    def test_does_not_hash_mutable_files(self):
        """Verify that artifact-bundle.json and result.json are NOT in the hash set,
        since they are mutated after product_integrations runs."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            hashed_files = bundle["verifiable_receipts"]["public_artifact_hashes"]
            self.assertNotIn("artifact-bundle.json", hashed_files)
            self.assertNotIn("result.json", hashed_files)

    def test_hashes_stable_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            hashed_files = bundle["verifiable_receipts"]["public_artifact_hashes"]
            self.assertIn("request.json", hashed_files)
            self.assertIn("transcript.ndjson", hashed_files)


class TestSummaryMarkdown(unittest.TestCase):
    def test_summary_mentions_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            summary = (run_dir / "integrations" / "summary.md").read_text()

            self.assertIn("Base Sepolia", summary)
            self.assertIn("agent0", summary.lower())
            self.assertIn("84532", summary)

    def test_summary_no_locus_mention(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            summary = (run_dir / "integrations" / "summary.md").read_text()

            self.assertNotIn("Locus", summary)


class TestChainConfig(unittest.TestCase):
    def test_base_sepolia_in_config(self):
        self.assertIn("base_sepolia", CHAIN_CONFIG)
        self.assertEqual(CHAIN_CONFIG["base_sepolia"]["chain_id"], 84532)

    def test_base_mainnet_in_config(self):
        self.assertIn("base_mainnet", CHAIN_CONFIG)
        self.assertEqual(CHAIN_CONFIG["base_mainnet"]["chain_id"], 8453)


class TestCLIIntegration(unittest.TestCase):
    """Integration test: run the CLI and verify integration files are emitted."""

    def test_cli_run_produces_integration_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            request_path = Path(tmpdir) / "request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "run_id": "run-integration-test",
                        "agent_role": "student",
                        "scenario_set_id": "public-curriculum-v1",
                        "workspace_snapshot": {"objective": "Test bridge integration"},
                        "time_budget": {"seconds": 30},
                        "cost_budget": {"usd": 1.0},
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.cli",
                    "--request",
                    str(request_path),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = artifacts_root / "run-integration-test"
            integrations = run_dir / "integrations"
            self.assertTrue(integrations.exists(), "integrations/ directory not created by CLI")
            self.assertTrue((integrations / "trust-bundle.json").exists())
            self.assertTrue((integrations / "erc8004-registration-draft.json").exists())
            self.assertTrue((integrations / "erc8004-completion-template.json").exists())
            self.assertTrue((integrations / "agent0-base-adapter.json").exists())
            self.assertTrue((integrations / "summary.md").exists())

            # Verify result.json has integrations key
            run_result = json.loads((run_dir / "result.json").read_text())
            self.assertIn("integrations", run_result)
            self.assertIn("trust_bundle_path", run_result["integrations"])


class TestRegistrationDraftProvenance(unittest.TestCase):
    """Tests for enriched provenance fields in the registration draft."""

    def test_draft_has_provenance_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            ext = draft["extensions"]["role_foundry"]
            self.assertEqual(ext["run_id"], "run-test-001")
            self.assertEqual(ext["agent_role"], "student")
            self.assertEqual(ext["curriculum_id"], "public-curriculum-v1")
            self.assertEqual(ext["promotion_status"], "unpromoted")
            self.assertIn("scorecard_hash", ext)

    def test_draft_carries_teacher_identity(self):
        """Teacher identity flows through when present in request."""
        request = dict(REQUEST_DICT)
        request["teacher_identity"] = "teacher-model-v1"
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, request, dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertEqual(draft["extensions"]["role_foundry"]["teacher_identity"], "teacher-model-v1")

    def test_draft_has_token_uri_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertEqual(draft["token_uri_strategy"], "http")
            self.assertIn("IPFS", draft["token_uri_note"])

    def test_promoted_status_propagates(self):
        request = dict(REQUEST_DICT)
        request["promotion_status"] = "promoted"
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, request, dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

            self.assertEqual(draft["extensions"]["role_foundry"]["promotion_status"], "promoted")


class TestCompletionTemplateV2(unittest.TestCase):
    """Tests for v2 completion template with mint modes."""

    def test_completion_template_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertEqual(template["version"], 2)

    def test_completion_template_has_mint_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertIn("mint_modes", template)
            modes = template["mint_modes"]
            self.assertIn("server_side", modes)
            self.assertIn("browser", modes)
            self.assertEqual(modes["server_side"]["signer"], "privateKey")
            self.assertEqual(modes["server_side"]["gate_env"], "ROLE_FOUNDRY_LIVE_MINT")

    def test_adapter_has_server_side_mint(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            adapter = json.loads((run_dir / "integrations" / "agent0-base-adapter.json").read_text())

            self.assertIn("server_side_mint", adapter)
            self.assertEqual(adapter["server_side_mint"]["signer_mode"], "privateKey")
            self.assertEqual(adapter["server_side_mint"]["script"], "app/mint_student_erc8004.mjs")


class TestMintGateway(unittest.TestCase):
    """Tests for the Python mint gateway."""

    def test_mint_disabled_by_default(self):
        from runner_bridge.mint_gateway import is_live_mint_enabled, mint_student_identity

        os.environ.pop("ROLE_FOUNDRY_LIVE_MINT", None)
        self.assertFalse(is_live_mint_enabled())

        result = mint_student_identity("/nonexistent/draft.json")
        self.assertFalse(result["ok"])
        self.assertTrue(result.get("gated"))

    def test_prerequisites_report(self):
        from runner_bridge.mint_gateway import check_mint_prerequisites

        os.environ.pop("ROLE_FOUNDRY_LIVE_MINT", None)
        os.environ.pop("SIGNER_PRIVATE_KEY", None)
        checks = check_mint_prerequisites()
        self.assertFalse(checks["live_mint_enabled"])
        self.assertFalse(checks["signer_private_key_set"])
        self.assertFalse(checks["ready"])
        self.assertTrue(checks["mint_script_exists"])

    def test_mint_requires_signer_key(self):
        from runner_bridge.mint_gateway import mint_student_identity

        os.environ["ROLE_FOUNDRY_LIVE_MINT"] = "1"
        os.environ.pop("SIGNER_PRIVATE_KEY", None)
        try:
            result = mint_student_identity("/nonexistent/draft.json")
            self.assertFalse(result["ok"])
            self.assertIn("SIGNER_PRIVATE_KEY", result["error"])
        finally:
            os.environ.pop("ROLE_FOUNDRY_LIVE_MINT", None)

    def test_mint_requires_draft_exists(self):
        from runner_bridge.mint_gateway import mint_student_identity

        os.environ["ROLE_FOUNDRY_LIVE_MINT"] = "1"
        os.environ["SIGNER_PRIVATE_KEY"] = "0xdeadbeef"
        try:
            result = mint_student_identity("/nonexistent/draft.json")
            self.assertFalse(result["ok"])
            self.assertIn("not found", result["error"])
        finally:
            os.environ.pop("ROLE_FOUNDRY_LIVE_MINT", None)
            os.environ.pop("SIGNER_PRIVATE_KEY", None)


if __name__ == "__main__":
    unittest.main()
