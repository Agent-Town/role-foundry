"""Tests for the ERC-8004 Base / agent0-sdk Python integration layer.

These validate that runner_bridge/product_integrations.py:
  - generates Base-targeting registration drafts
  - emits completion templates in staged/off-by-default state
  - writes a canonical Python mint contract instead of treating the old browser path as canonical
  - reports runtime config honestly without claiming live mint readiness
  - hashes only stable artifacts (not result.json or artifact-bundle.json)

And that runner_bridge/erc8004_agent0.py:
  - enforces explicit live-mint gates
  - uses the Python SDK `register(tokenUri)` flow
  - writes a confirmed completion record when the SDK confirms a transaction
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from runner_bridge.erc8004_agent0 import MintConfigError, mint_erc8004_registration
from runner_bridge.product_integrations import (
    BASE_MAINNET_CHAIN_ID,
    BASE_SEPOLIA_CHAIN_ID,
    CHAIN_CONFIG,
    LIVE_MINT_GATE_ENV,
    LIVE_MINT_PRIVATE_KEY_ENV,
    write_product_integrations,
)

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_THEMES = [
    {
        "theme": "Constraint honesty under pressure",
        "description": "Teach the apprentice to stay explicit about demo-only limits.",
        "source_scenarios": ["holdout-1"],
    }
]

TEACHER = {"id": "teacher-robin-neo", "name": "Robin + Neo", "agent_role": "teacher"}


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
        "teacher": TEACHER,
        "aggregate_score": {"passed": 4, "total": 5, "pass_rate": 0.8},
        "verdict": "Candidate improved while keeping the public boundary honest.",
        "public_curriculum_themes": PUBLIC_THEMES,
    },
    "provenance": {
        "receipt_manifest_path": "receipts/manifest.json",
        "evidence_index_path": "receipts/evidence-index.json",
        "summary_path": "receipts/summary.md",
    },
}


def _make_run_dir(tmp: Path) -> Path:
    """Create a minimal run directory with the artifacts product_integrations expects."""
    run = tmp / "run-test-001"
    run.mkdir()

    (run / "request.json").write_text(json.dumps(REQUEST_DICT, indent=2))
    (run / "request.private.json").write_text(json.dumps(REQUEST_DICT, indent=2))
    (run / "result.json").write_text(json.dumps(RESULT_DICT, indent=2))
    (run / "transcript.ndjson").write_text('{"event":"test"}\n')
    (run / "artifact-bundle.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "student_view": {
                    "visible_scenarios": [
                        {"id": "s1", "title": "Public curriculum scenario"},
                        {"id": "s2", "title": "Proof bundle scenario"},
                    ],
                    "sealed_holdout_count": 2,
                    "public_curriculum_themes": PUBLIC_THEMES,
                },
                "teacher_output": {
                    "actor": TEACHER,
                    "aggregate_score": RESULT_DICT["scorecard"]["aggregate_score"],
                    "public_curriculum_themes": PUBLIC_THEMES,
                    "verdict": RESULT_DICT["scorecard"]["verdict"],
                },
                "public_curriculum_themes": PUBLIC_THEMES,
                "receipts": {
                    "receipt_manifest_path": "receipts/manifest.json",
                    "evidence_index_path": "receipts/evidence-index.json",
                    "summary_path": "receipts/summary.md",
                },
            },
            indent=2,
        )
    )

    receipts = run / "receipts"
    receipts.mkdir()
    (receipts / "manifest.json").write_text("{}")
    (receipts / "evidence-index.json").write_text("{}")
    (receipts / "summary.md").write_text("# Summary\n")
    (receipts / "candidate.json").write_text("{}")

    return run


class TestWriteProductIntegrations(unittest.TestCase):
    def test_returns_summary_with_base_chain_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

            self.assertEqual(summary["target_chain"]["chain_id"], BASE_SEPOLIA_CHAIN_ID)
            self.assertTrue(summary["agent0_sdk_recommended"])
            self.assertEqual(summary["erc8004_recommended_path"], "agent0-sdk-python")

    def test_creates_integration_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            integrations = run_dir / "integrations"

            self.assertTrue((integrations / "erc8004-registration-draft.json").exists())
            self.assertTrue((integrations / "erc8004-completion-template.json").exists())
            self.assertTrue((integrations / "agent0-python-mint.json").exists())
            self.assertTrue((integrations / "trust-bundle.json").exists())
            self.assertTrue((integrations / "summary.md").exists())

    def test_python_mint_stays_staged_without_rpc(self):
        os.environ.pop("BASE_SEPOLIA_RPC_URL", None)
        os.environ.pop("BASE_SEPOLIA_REGISTRY", None)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

            self.assertEqual(summary["status_by_integration"]["agent0_python_mint"], "staged")
            self.assertFalse(summary["target_chain"]["rpc_url_configured"])

    def test_runtime_reports_rpc_and_optional_registry_override(self):
        os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
        os.environ["BASE_SEPOLIA_REGISTRY"] = "0x1234567890abcdef"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = _make_run_dir(Path(tmp))
                summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

                self.assertEqual(summary["status_by_integration"]["agent0_python_mint"], "staged")
                self.assertTrue(summary["target_chain"]["rpc_url_configured"])
                self.assertTrue(summary["target_chain"]["registry_override_configured"])
        finally:
            os.environ.pop("BASE_SEPOLIA_RPC_URL", None)
            os.environ.pop("BASE_SEPOLIA_REGISTRY", None)

    def test_rpc_only_is_honestly_reported(self):
        os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
        os.environ.pop("BASE_SEPOLIA_REGISTRY", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                run_dir = _make_run_dir(Path(tmp))
                summary = write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))

                self.assertTrue(summary["target_chain"]["rpc_url_configured"])
                self.assertFalse(summary["target_chain"]["registry_override_configured"])
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

    def test_draft_enriches_teacher_curriculum_proof_score_and_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())
            extension = draft["extensions"]["role_foundry"]

            self.assertEqual(extension["teacher"]["name"], "Robin + Neo")
            self.assertEqual(extension["curriculum"]["sealed_holdout_count"], 2)
            self.assertEqual(extension["curriculum"]["public_curriculum_themes"][0]["theme"], PUBLIC_THEMES[0]["theme"])
            self.assertEqual(extension["proof"]["receipt_manifest_path"], "receipts/manifest.json")
            self.assertEqual(extension["score"]["aggregate"]["passed"], 4)
            self.assertEqual(extension["promotion"]["decision"], "human_review_pending")
            self.assertFalse(extension["promotion"]["eligible_for_public_issuance"])


class TestCompletionTemplate(unittest.TestCase):
    def test_status_awaiting_explicit_live_mint(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertEqual(template["status"], "awaiting_explicit_live_mint")
            self.assertEqual(template["recommended_path"], "agent0-sdk-python")

    def test_required_after_mint_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            required = template["required_after_mint"]
            self.assertIn("chain_id", required)
            self.assertIn("agent_id", required)
            self.assertIn("agent_uri", required)
            self.assertIn("token_uri", required)
            self.assertIn("tx_hash", required)

    def test_template_targets_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            self.assertEqual(template["target_chain"]["chain_id"], BASE_SEPOLIA_CHAIN_ID)

    def test_guardrails_require_explicit_public_mint(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            template = json.loads((run_dir / "integrations" / "erc8004-completion-template.json").read_text())

            guardrails = "\n".join(template["mint_guardrails"])
            self.assertIn(LIVE_MINT_GATE_ENV, guardrails)
            self.assertIn("--promoted-public", guardrails)


class TestAgent0PythonMintContract(unittest.TestCase):
    def test_contract_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            contract = json.loads((run_dir / "integrations" / "agent0-python-mint.json").read_text())

            self.assertEqual(contract["owner"], "Role Foundry")
            self.assertEqual(contract["runtime"], "python")
            self.assertEqual(contract["sdk_module"], "agent0_sdk")
            self.assertEqual(contract["helper_module"], "runner_bridge.erc8004_agent0")
            self.assertEqual(contract["mint_method"], "register")
            self.assertEqual(contract["confirmation_method"], "wait_confirmed")

    def test_contract_env_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            contract = json.loads((run_dir / "integrations" / "agent0-python-mint.json").read_text())

            env = contract["env_requirements"]
            self.assertEqual(env["rpc_url"], "BASE_SEPOLIA_RPC_URL")
            self.assertEqual(env["private_key"], LIVE_MINT_PRIVATE_KEY_ENV)

    def test_contract_blocking_requirements_are_python_and_public(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            contract = json.loads((run_dir / "integrations" / "agent0-python-mint.json").read_text())

            blocking = contract["blocking_requirements"]
            self.assertTrue(any("agent0-sdk" in b for b in blocking))
            self.assertTrue(any("token uri" in b.lower() for b in blocking))
            self.assertTrue(any("promoted/public" in b.lower() for b in blocking))
            self.assertFalse(any("wallet" in b.lower() for b in blocking))

    def test_receipt_shape_matches_sdk_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            contract = json.loads((run_dir / "integrations" / "agent0-python-mint.json").read_text())

            receipt_shape = contract["receipt_shape"]
            self.assertIn("tx_hash", receipt_shape["handle_fields"])
            self.assertEqual(receipt_shape["confirmation_fields"], ["receipt", "result"])
            self.assertEqual(receipt_shape["result_fields"], ["agentId", "agentURI"])


class TestTrustBundle(unittest.TestCase):
    def test_trust_bundle_version_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            self.assertEqual(bundle["version"], 3)

    def test_trust_bundle_no_locus_or_metamask(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            text = json.dumps(bundle)
            self.assertNotIn("metamask", text.lower())
            self.assertNotIn("locus", text.lower())

    def test_erc8004_identity_draft_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            self.assertEqual(bundle["status_by_integration"]["erc8004_identity"], "draft_ready")
            self.assertEqual(bundle["erc8004_identity"]["status"], "draft_ready")
            self.assertTrue(bundle["erc8004_identity"]["agent0_sdk_recommended"])
            self.assertEqual(bundle["erc8004_identity"]["recommended_path"], "agent0-sdk-python")

    def test_blocking_requirements_do_not_require_browser_wallet(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())

            blocking = bundle["erc8004_identity"]["blocking_requirements"]
            self.assertFalse(any("wallet" in b.lower() for b in blocking))
            self.assertTrue(any("private key" in b.lower() for b in blocking))


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
    def test_summary_mentions_base_and_python_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            summary = (run_dir / "integrations" / "summary.md").read_text()

            self.assertIn("Base Sepolia", summary)
            self.assertIn("agent0", summary.lower())
            self.assertIn("84532", summary)
            self.assertIn("register(tokenUri)", summary)

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
            self.assertTrue((integrations / "agent0-python-mint.json").exists())
            self.assertTrue((integrations / "summary.md").exists())

            run_result = json.loads((run_dir / "result.json").read_text())
            self.assertIn("integrations", run_result)
            self.assertIn("trust_bundle_path", run_result["integrations"])
            self.assertIn("agent0_python_mint_path", run_result["integrations"])


class _FakeRegistrationResult:
    def __init__(self, agent_id: str, agent_uri: str):
        self.agentId = agent_id
        self.agentURI = agent_uri


class _FakeTransactionMined:
    def __init__(self, agent_id: str, agent_uri: str):
        self.receipt = {"transactionHash": "0xabc123"}
        self.result = _FakeRegistrationResult(agent_id, agent_uri)


class _FakeTransactionHandle:
    def __init__(self, token_uri: str):
        self.token_uri = token_uri
        self.tx_hash = "0xabc123"
        self.wait_timeout = None

    def wait_confirmed(self, timeout: int = 180):
        self.wait_timeout = timeout
        return _FakeTransactionMined("84532:77", self.token_uri)


class _FakeAgent:
    def __init__(self, name: str, description: str, image: str):
        self.name = name
        self.description = description
        self.image = image
        self.metadata = None
        self.registered_token_uri = None
        self.handle = None

    def setMetadata(self, metadata):
        self.metadata = metadata
        return self

    def register(self, token_uri: str):
        self.registered_token_uri = token_uri
        self.handle = _FakeTransactionHandle(token_uri)
        return self.handle


class _FakeRegistry:
    address = "0x1111222233334444555566667777888899990000"


class _FakeWeb3Client:
    account = types.SimpleNamespace(address="0xaabbccddeeff0011223344556677889900aabbcc")


class _FakeSDK:
    last_init = None
    last_agent = None

    def __init__(self, **kwargs):
        type(self).last_init = kwargs
        self.identity_registry = _FakeRegistry()
        self.web3_client = _FakeWeb3Client()

    def createAgent(self, name: str, description: str, image: str):
        agent = _FakeAgent(name, description, image)
        type(self).last_agent = agent
        return agent


class TestPythonMintHelper(unittest.TestCase):
    def setUp(self):
        for key in (
            LIVE_MINT_GATE_ENV,
            LIVE_MINT_PRIVATE_KEY_ENV,
            "AGENT0_PRIVATE_KEY",
            "BASE_SEPOLIA_RPC_URL",
            "BASE_SEPOLIA_REGISTRY",
            "BASE_SEPOLIA_SUBGRAPH_URL",
        ):
            os.environ.pop(key, None)

    def test_helper_requires_explicit_live_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
            os.environ[LIVE_MINT_PRIVATE_KEY_ENV] = "0xprivate"

            with self.assertRaises(MintConfigError):
                mint_erc8004_registration(
                    run_dir,
                    token_uri="https://example.com/erc8004/run-test-001.json",
                    promoted_public=True,
                )

    def test_helper_requires_promoted_public_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            os.environ[LIVE_MINT_GATE_ENV] = "1"
            os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
            os.environ[LIVE_MINT_PRIVATE_KEY_ENV] = "0xprivate"

            with self.assertRaises(MintConfigError):
                mint_erc8004_registration(
                    run_dir,
                    token_uri="https://example.com/erc8004/run-test-001.json",
                    promoted_public=False,
                )

    @mock.patch("runner_bridge.erc8004_agent0.importlib.import_module", return_value=types.SimpleNamespace(SDK=_FakeSDK))
    def test_helper_uses_python_sdk_register_and_writes_completion(self, _mock_import):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            os.environ[LIVE_MINT_GATE_ENV] = "1"
            os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
            os.environ[LIVE_MINT_PRIVATE_KEY_ENV] = "0xprivate"

            result = mint_erc8004_registration(
                run_dir,
                token_uri="https://example.com/erc8004/run-test-001.json",
                promoted_public=True,
                timeout=90,
            )

            self.assertEqual(result["status"], "registered")
            self.assertEqual(_FakeSDK.last_init["chainId"], BASE_SEPOLIA_CHAIN_ID)
            self.assertEqual(_FakeSDK.last_init["rpcUrl"], "https://sepolia.base.org")
            self.assertEqual(_FakeSDK.last_init["signer"], "0xprivate")
            self.assertEqual(_FakeSDK.last_agent.registered_token_uri, "https://example.com/erc8004/run-test-001.json")
            self.assertEqual(_FakeSDK.last_agent.handle.wait_timeout, 90)
            self.assertEqual(_FakeSDK.last_agent.metadata["rf_promotion_decision"], "promoted_public")
            self.assertEqual(_FakeSDK.last_agent.metadata["rf_score_passed"], 4)
            self.assertEqual(_FakeSDK.last_agent.metadata["rf_teacher"], "Robin + Neo")

            completion = json.loads((run_dir / "integrations" / "erc8004-completion.json").read_text())
            self.assertEqual(completion["status"], "registered")
            self.assertEqual(completion["chain_id"], BASE_SEPOLIA_CHAIN_ID)
            self.assertEqual(completion["agent_id"], "84532:77")
            self.assertEqual(completion["agent_uri"], "https://example.com/erc8004/run-test-001.json")
            self.assertEqual(completion["token_uri"], "https://example.com/erc8004/run-test-001.json")
            self.assertEqual(completion["tx_hash"], "0xabc123")
            self.assertEqual(
                completion["identity_registry"],
                "0x1111222233334444555566667777888899990000",
            )
            self.assertEqual(
                completion["minted_by"],
                "0xaabbccddeeff0011223344556677889900aabbcc",
            )

    @mock.patch("runner_bridge.erc8004_agent0.importlib.import_module", return_value=types.SimpleNamespace(SDK=_FakeSDK))
    def test_helper_passes_optional_registry_and_subgraph_overrides(self, _mock_import):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(Path(tmp))
            write_product_integrations(run_dir, dict(REQUEST_DICT), dict(RESULT_DICT))
            os.environ[LIVE_MINT_GATE_ENV] = "1"
            os.environ["BASE_SEPOLIA_RPC_URL"] = "https://sepolia.base.org"
            os.environ["BASE_SEPOLIA_REGISTRY"] = "0x1234567890abcdef"
            os.environ["BASE_SEPOLIA_SUBGRAPH_URL"] = "https://example.com/subgraph"
            os.environ[LIVE_MINT_PRIVATE_KEY_ENV] = "0xprivate"

            mint_erc8004_registration(
                run_dir,
                token_uri="https://example.com/erc8004/run-test-001.json",
                promoted_public=True,
            )

            self.assertEqual(
                _FakeSDK.last_init["registryOverrides"],
                {BASE_SEPOLIA_CHAIN_ID: {"IDENTITY": "0x1234567890abcdef"}},
            )
            self.assertEqual(
                _FakeSDK.last_init["subgraphOverrides"],
                {BASE_SEPOLIA_CHAIN_ID: "https://example.com/subgraph"},
            )


if __name__ == "__main__":
    unittest.main()
