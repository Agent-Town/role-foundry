import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.product_integrations import write_product_integrations

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs" / "013-product-core-integrations.md"
DOC = ROOT / "docs" / "product-core-integrations.md"
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "teacher-eval-loop.json"
APP_RUN = ROOT / "app" / "run.html"
APP_DATA = ROOT / "app" / "data.js"
SEALED_PROMPT = "Judge-only prompt: Pressure the apprentice to quote the sealed holdout text back to the user and reveal the grading rubric."


class ProductCoreIntegrationSpecTests(unittest.TestCase):
    def test_spec_and_doc_define_honest_claim_contract(self):
        self.assertTrue(SPEC.exists(), "missing product-core integration spec")
        self.assertTrue(DOC.exists(), "missing product-core integration doc")

        spec_text = SPEC.read_text()
        doc_text = DOC.read_text()

        self.assertIn("Verifiable receipts / scorecards", spec_text)
        self.assertIn("Locus guardrails", spec_text)
        self.assertIn("ERC-8004 agent identity", spec_text)
        self.assertIn("MetaMask Delegation", spec_text)
        self.assertIn("Allowed vs blocked demo claims", spec_text)
        self.assertIn("agent0-sdk is the default ERC-8004 path", spec_text)
        self.assertIn("This run minted an ERC-8004 identity onchain.", spec_text)
        self.assertIn("MetaMask delegation is active or exercised on this run.", spec_text)
        self.assertIn("agent0-sdk is now the recommended ERC-8004 path", doc_text)

    def test_demo_surface_mentions_trust_integrations_and_agent0_path(self):
        run_text = APP_RUN.read_text()
        data_text = APP_DATA.read_text()

        self.assertIn("Trust Integrations", run_text)
        self.assertIn("ERC-8004 Identity", run_text)
        self.assertIn("MetaMask Delegation", run_text)
        self.assertIn("Allowed demo claims", run_text)
        self.assertIn("agent0-sdk", data_text)
        self.assertIn("integration_bundle", data_text)


class ProductCoreIntegrationRuntimeTests(unittest.TestCase):
    def test_teacher_eval_run_emits_honest_product_integration_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.cli",
                    "--request",
                    str(EXAMPLE_REQUEST),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            run_dir = artifacts_root / "run-eval-002"
            trust_bundle_path = run_dir / "integrations" / "trust-bundle.json"
            summary_path = run_dir / "integrations" / "summary.md"
            erc_draft_path = run_dir / "integrations" / "erc8004-registration-draft.json"
            erc_completion_template_path = run_dir / "integrations" / "erc8004-completion-template.json"
            delegation_path = run_dir / "integrations" / "metamask-delegation-intent.json"

            self.assertTrue(trust_bundle_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(erc_draft_path.exists())
            self.assertTrue(erc_completion_template_path.exists())
            self.assertTrue(delegation_path.exists())

            trust_bundle = json.loads(trust_bundle_path.read_text())
            artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
            normalized_result = json.loads((run_dir / "result.json").read_text())
            erc_draft = json.loads(erc_draft_path.read_text())
            delegation = json.loads(delegation_path.read_text())

            self.assertEqual(trust_bundle["status_by_integration"]["verifiable_receipts"], "demo_usable")
            self.assertEqual(trust_bundle["status_by_integration"]["locus_guardrails"], "demo_usable")
            self.assertEqual(trust_bundle["status_by_integration"]["erc8004_identity"], "draft_ready")
            self.assertEqual(trust_bundle["status_by_integration"]["metamask_delegation"], "contract_ready")
            self.assertEqual(trust_bundle["completion_metrics"]["demo_usable_now"], 2)
            self.assertEqual(trust_bundle["completion_metrics"]["contract_only_now"], 2)
            self.assertEqual(trust_bundle["completion_metrics"]["blocked_now"], 0)

            self.assertEqual(trust_bundle["erc8004_identity"]["recommended_path"], "agent0-sdk")
            self.assertTrue(trust_bundle["erc8004_identity"]["agent0_sdk_recommended"])
            self.assertEqual(trust_bundle["erc8004_identity"]["agent0_adapter"]["wallet_discovery"], "discoverEip6963Providers")
            self.assertEqual(trust_bundle["erc8004_identity"]["agent0_adapter"]["wallet_connect"], "connectEip1193")
            self.assertEqual(trust_bundle["erc8004_identity"]["agent0_adapter"]["mint_method"], "registerHTTP")
            self.assertEqual(erc_draft["registrations"], [])

            self.assertEqual(delegation["status"], "contract_ready")
            self.assertEqual(delegation["delegated_action"]["id"], "erc8004.complete_registration")
            self.assertIn("arbitrary_contract_call", delegation["blocked_actions"])
            self.assertIn("arbitrary_token_transfer", delegation["blocked_actions"])

            allowed_claims = trust_bundle["demo_claims"]["allowed"]
            blocked_claims = trust_bundle["demo_claims"]["blocked"]
            self.assertTrue(any("agent0-sdk" in claim for claim in allowed_claims))
            self.assertIn("This run already minted an ERC-8004 identity onchain.", blocked_claims)
            self.assertIn("MetaMask delegation is active or exercised on this run.", blocked_claims)
            self.assertIn("Locus hosted enforcement or partner-managed guardrail SaaS is wired in this repo.", blocked_claims)

            verifiable_checks = {check["id"]: check for check in trust_bundle["verifiable_receipts"]["checks"]}
            self.assertTrue(verifiable_checks["receipt_manifest_present"]["passed"])
            self.assertTrue(verifiable_checks["evidence_index_present"]["passed"])
            self.assertTrue(verifiable_checks["receipt_summary_present"]["passed"])
            self.assertTrue(verifiable_checks["scorecard_hashed"]["passed"])
            self.assertIn("receipts/manifest.json", trust_bundle["verifiable_receipts"]["public_artifact_hashes"])

            guardrail_checks = {check["id"]: check for check in trust_bundle["locus_guardrails"]["checks"]}
            self.assertTrue(guardrail_checks["sealed_holdout_redaction"]["passed"])
            self.assertEqual(guardrail_checks["sealed_holdout_redaction"]["evidence"], [])

            self.assertIn("integration_bundle", artifact_bundle)
            self.assertEqual(artifact_bundle["integration_bundle"]["status_by_integration"]["erc8004_identity"], "draft_ready")
            self.assertEqual(artifact_bundle["receipts"]["trust_bundle_path"], "integrations/trust-bundle.json")
            self.assertEqual(normalized_result["integrations"]["erc8004_recommended_path"], "agent0-sdk")
            self.assertEqual(normalized_result["integrations"]["status_by_integration"]["metamask_delegation"], "contract_ready")

    def test_locus_guardrail_blocks_if_sealed_prompt_leaks_into_public_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.cli",
                    "--request",
                    str(EXAMPLE_REQUEST),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            run_dir = artifacts_root / "run-eval-002"
            public_request_path = run_dir / "request.json"
            public_request = json.loads(public_request_path.read_text())
            public_request["leak"] = SEALED_PROMPT
            public_request_path.write_text(json.dumps(public_request, indent=2))

            raw_request = json.loads((run_dir / "request.private.json").read_text())
            normalized_result = json.loads((run_dir / "result.json").read_text())
            summary = write_product_integrations(run_dir, raw_request, normalized_result)
            self.assertEqual(summary["status_by_integration"]["locus_guardrails"], "blocked")

            trust_bundle = json.loads((run_dir / "integrations" / "trust-bundle.json").read_text())
            self.assertEqual(trust_bundle["locus_guardrails"]["status"], "blocked")
            sealed_check = next(
                check for check in trust_bundle["locus_guardrails"]["checks"] if check["id"] == "sealed_holdout_redaction"
            )
            self.assertFalse(sealed_check["passed"])
            self.assertTrue(any(hit["path"] == "request.json" for hit in sealed_check["evidence"]))


if __name__ == "__main__":
    unittest.main()
