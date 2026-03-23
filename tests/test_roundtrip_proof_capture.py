"""Smoke tests for the roundtrip proof-capture helper.

Exercises manifest generation, secret redaction, and local artifact copying
without requiring a live Clawith server or Claude Code CLI.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# Import the helper module directly
import capture_clawith_roundtrip_proof as cap


class TestRedaction(unittest.TestCase):
    """Secret redaction must neutralize gateway keys, JWTs, and bearer tokens."""

    def test_gateway_key_redacted(self):
        text = "api_key: oc-abc123def456ghi789"
        result = cap.redact_secrets(text)
        self.assertNotIn("abc123def456ghi789", result)
        self.assertIn("oc-REDACTED", result)

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.signature"
        result = cap.redact_secrets(text)
        self.assertNotIn("payload", result)

    def test_jwt_redacted(self):
        text = "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig"
        result = cap.redact_secrets(text)
        self.assertNotIn("payload", result)

    def test_plain_text_unchanged(self):
        text = "Hello world, no secrets here."
        self.assertEqual(cap.redact_secrets(text), text)

    def test_redact_dict_deep(self):
        obj = {
            "api_key": "oc-secret1234567890abcdef",
            "nested": {"token": "eyJhbGciOiJIUzI1NiJ9.big.secret"},
            "list": ["oc-another1234567890abc"],
            "safe": 42,
        }
        result = cap.redact_dict(obj)
        self.assertIn("REDACTED", json.dumps(result))
        self.assertNotIn("secret1234567890", json.dumps(result))
        self.assertEqual(result["safe"], 42)


class TestManifestGeneration(unittest.TestCase):
    """Manifest must accurately reflect what is present vs missing."""

    def _make_manifest(self, **overrides):
        defaults = {
            "tag": "20260323T000000Z",
            "agent_identity": {"present": False, "note": "not found"},
            "gateway_artifacts": {"present": False, "note": "not found"},
            "clawith_api": {"present": False, "note": "skipped"},
            "worker_snapshot": {"present": False, "note": "not found"},
            "screenshots": {"present": False, "note": "not supplied"},
        }
        defaults.update(overrides)
        return cap.build_manifest(**defaults)

    def test_all_missing(self):
        m = self._make_manifest()
        self.assertEqual(m["summary"]["present"], 0)
        self.assertEqual(m["summary"]["total"], 5)
        self.assertFalse(m["summary"]["complete"])
        self.assertEqual(len(m["summary"]["missing_pieces"]), 5)

    def test_all_present(self):
        m = self._make_manifest(
            agent_identity={"present": True, "path": "agent-identity.json"},
            gateway_artifacts={
                "present": True,
                "paths": [
                    "01_msg/message.json",
                    "01_msg/prompt.txt",
                    "01_msg/claude.stdout.txt",
                    "01_msg/report.json",
                ],
            },
            clawith_api={
                "present": True,
                "paths": [
                    "clawith-api/gateway-messages.json",
                    "clawith-api/session-messages.json",
                ],
            },
            worker_snapshot={"present": True, "path": "worker-script-snapshot.py"},
            screenshots={"present": True, "paths": ["step1.png"]},
        )
        self.assertEqual(m["summary"]["present"], 5)
        self.assertTrue(m["summary"]["complete"])
        self.assertEqual(m["summary"]["missing_pieces"], [])

    def test_partial(self):
        m = self._make_manifest(
            agent_identity={"present": True, "path": "agent-identity.json"},
            worker_snapshot={"present": True, "path": "worker-script-snapshot.py"},
        )
        self.assertEqual(m["summary"]["present"], 1)
        self.assertFalse(m["summary"]["complete"])
        self.assertIn("inbound_task", m["summary"]["missing_pieces"])

    def test_worker_snapshot_alone_is_not_execution_evidence(self):
        m = self._make_manifest(
            worker_snapshot={"present": True, "path": "worker-script-snapshot.py"},
        )
        self.assertFalse(m["evidence"]["worker_execution"]["present"])

    def test_honesty_notice_present(self):
        m = self._make_manifest()
        self.assertIn("honesty_notice", m)
        self.assertIn("fabricated", m["honesty_notice"].lower())

    def test_manifest_version_2(self):
        m = self._make_manifest()
        self.assertEqual(m["proof_bundle_version"], 2)

    def test_five_evidence_keys(self):
        m = self._make_manifest()
        expected = {"inbound_task", "agent_identity_linked", "worker_execution",
                    "result_in_clawith", "screenshot_bundle"}
        self.assertEqual(set(m["evidence"].keys()), expected)


class TestLocalArtifactCopying(unittest.TestCase):
    """Artifact copying must work with real temp files."""

    def test_gather_agent_identity_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_agent_identity(Path(tmp) / "nonexistent.json", proof_dir)
            self.assertFalse(result["present"])

    def test_gather_agent_identity_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            key_file = Path(tmp) / "key.json"
            key_file.write_text(json.dumps({
                "api_key": "oc-testsecretvalue1234567890",
                "agent_id": "abc-123",
                "agent_name": "test-bot",
            }))
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_agent_identity(key_file, proof_dir)
            self.assertTrue(result["present"])

            # Verify redaction in the copied file
            copied = json.loads((proof_dir / "agent-identity.json").read_text())
            self.assertNotIn("testsecretvalue", json.dumps(copied))
            self.assertEqual(copied["agent_id"], "abc-123")

    def test_gather_gateway_artifacts_with_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            art_dir = Path(tmp) / "artifacts" / "run1"
            art_dir.mkdir(parents=True)
            (art_dir / "poll.json").write_text(json.dumps({"messages": [], "key": "oc-secretkey12345678"}))
            (art_dir / "prompt.txt").write_text("test prompt")

            proof_dir = Path(tmp) / "proof"
            result = cap.gather_gateway_artifacts(art_dir, proof_dir)
            self.assertTrue(result["present"])
            self.assertEqual(len(result["paths"]), 2)

            # Verify JSON was redacted
            copied_poll = json.loads((proof_dir / "gateway-artifacts" / "poll.json").read_text())
            self.assertNotIn("secretkey", json.dumps(copied_poll))

    def test_gather_worker_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_worker_script_snapshot(proof_dir)
            # This depends on the actual repo file existing
            worker = ROOT / "scripts" / "clawith_vibe_once.py"
            if worker.exists():
                self.assertTrue(result["present"])
            else:
                self.assertFalse(result["present"])


class TestScreenshotGathering(unittest.TestCase):
    """Screenshot packaging must copy images and report missing explicitly."""

    def test_no_dir_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_screenshots(None, proof_dir)
            self.assertFalse(result["present"])
            self.assertIn("absent", result["note"].lower())

    def test_nonexistent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_screenshots(Path(tmp) / "nope", proof_dir)
            self.assertFalse(result["present"])
            self.assertIn("not found", result["note"].lower())

    def test_dir_with_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            ss_dir = Path(tmp) / "screenshots"
            ss_dir.mkdir()
            (ss_dir / "step1.png").write_bytes(b"\x89PNG")
            (ss_dir / "step2.jpg").write_bytes(b"\xff\xd8")
            (ss_dir / "notes.txt").write_text("ignore me")

            proof_dir = Path(tmp) / "proof"
            result = cap.gather_screenshots(ss_dir, proof_dir)
            self.assertTrue(result["present"])
            self.assertEqual(len(result["paths"]), 2)
            # txt file should not be copied
            self.assertFalse((proof_dir / "screenshots" / "notes.txt").exists())

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ss_dir = Path(tmp) / "screenshots"
            ss_dir.mkdir()
            proof_dir = Path(tmp) / "proof"
            result = cap.gather_screenshots(ss_dir, proof_dir)
            self.assertFalse(result["present"])
            self.assertIn("no image files", result["note"].lower())


class TestInferHelpers(unittest.TestCase):
    """Agent ID and session ID inference from local files."""

    def test_infer_agent_id_from_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = Path(tmp) / "key.json"
            key.write_text(json.dumps({"agent_id": "abc-123", "api_key": "oc-x"}))
            self.assertEqual(cap._infer_agent_id(key), "abc-123")

    def test_infer_agent_id_missing(self):
        self.assertIsNone(cap._infer_agent_id(Path("/nonexistent")))

    def test_infer_session_id_from_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            msg_dir = Path(tmp) / "01_msg"
            msg_dir.mkdir()
            (msg_dir / "message.json").write_text(json.dumps({"conversation_id": "sess-42"}))
            self.assertEqual(cap._infer_session_id(Path(tmp)), "sess-42")

    def test_infer_session_id_none(self):
        self.assertIsNone(cap._infer_session_id(None))


class TestEndToEnd(unittest.TestCase):
    """Run the full capture with synthetic local data."""

    def test_full_capture_with_partial_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            # Set up a fake key file
            key_file = tmp_path / "key.json"
            key_file.write_text(json.dumps({
                "api_key": "oc-fakekey1234567890abcdef",
                "agent_id": "test-id",
                "agent_name": "test-agent",
            }))

            # Set up fake artifacts
            art_dir = tmp_path / "artifacts"
            art_dir.mkdir()
            (art_dir / "poll.json").write_text(json.dumps({"messages": []}))

            proof_dir = tmp_path / "proof"

            agent_identity = cap.gather_agent_identity(key_file, proof_dir)
            gateway_artifacts = cap.gather_gateway_artifacts(art_dir, proof_dir)
            clawith_api = cap.gather_clawith_api(None, None, proof_dir)
            worker_snapshot = cap.gather_worker_script_snapshot(proof_dir)
            screenshots = cap.gather_screenshots(None, proof_dir)

            manifest = cap.build_manifest(
                tag="20260323T120000Z",
                agent_identity=agent_identity,
                gateway_artifacts=gateway_artifacts,
                clawith_api=clawith_api,
                worker_snapshot=worker_snapshot,
                screenshots=screenshots,
            )

            self.assertTrue(agent_identity["present"])
            self.assertTrue(gateway_artifacts["present"])
            self.assertFalse(clawith_api["present"])
            self.assertFalse(screenshots["present"])
            # worker_snapshot depends on repo file

            # Manifest must be JSON-serializable
            json.dumps(manifest)

            # Missing pieces must include result_in_clawith and screenshot_bundle
            self.assertIn("result_in_clawith", manifest["summary"]["missing_pieces"])
            self.assertIn("screenshot_bundle", manifest["summary"]["missing_pieces"])


if __name__ == "__main__":
    unittest.main()
