from __future__ import annotations

import unittest
from pathlib import Path

from runner_bridge.backends import backend_command_for_runner, backend_contract_for_runner, known_runner_backends

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs" / "016-claude-vibecosystem-backend.md"
REAL_PATH_DOC = ROOT / "docs" / "clawith-vibecosystem-real-path.md"


class ClaudeVibecosystemBackendRegistryTests(unittest.TestCase):
    def test_named_backend_registry_exposes_claude_vibecosystem(self):
        self.assertIn("claude_vibecosystem", known_runner_backends())
        command = backend_command_for_runner("claude_vibecosystem")
        self.assertEqual(command[-1], "runner_bridge.backends.claude_vibecosystem")

    def test_backend_contract_pins_honesty_boundary(self):
        contract = backend_contract_for_runner("claude_vibecosystem")
        self.assertEqual(contract["mode"], "external_executor_beta")
        self.assertEqual(contract["beta_status"], "live_public_smoke_available")
        self.assertEqual(contract["executor"]["runtime"], "Claude Code")
        self.assertEqual(contract["executor"]["agent_selection"], "vibecosystem")
        self.assertEqual(contract["claim_boundary"]["sealed_evaluation"], "not_claimed")
        self.assertEqual(contract["claim_boundary"]["independent_executor_isolation"], "not_claimed")


class ClaudeVibecosystemDocumentationTests(unittest.TestCase):
    def test_spec_exists_and_names_claim_boundary(self):
        self.assertTrue(SPEC.exists())
        text = SPEC.read_text()
        self.assertIn("external-executor beta seam", text)
        self.assertIn("execution_backend_contract", text)
        self.assertIn("sealed evaluation", text)
        self.assertIn("independent executor isolation", text)
        self.assertIn("not claimed", text)

    def test_real_path_doc_mentions_current_beta_seam(self):
        text = REAL_PATH_DOC.read_text()
        self.assertIn("--runner-backend claude_vibecosystem", text)
        self.assertIn("execution_backend_contract", text)
        self.assertIn("does not create independent executor isolation", text)


if __name__ == "__main__":
    unittest.main()
