"""Tests for Spec 015 — Sealed Receipt Surface (honesty boundary).

These tests pin the claim ceiling, blocked claims, operator checklist,
and fingerprint labeling so future branches cannot overclaim without
first landing the missing controls.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "autoresearch-alpha-public-loop.json"
SPEC_FILE = ROOT / "specs" / "015-sealed-receipt-surface.md"


class SealedReceiptSurfaceSpecTests(unittest.TestCase):
    """Spec 015 exists and contains required sections."""

    def test_spec_file_exists(self):
        self.assertTrue(SPEC_FILE.exists(), "specs/015-sealed-receipt-surface.md missing")

    def test_spec_contains_required_sections(self):
        text = SPEC_FILE.read_text()
        for required in [
            "Allowed now",
            "Blocked now",
            "Required controls before stronger language",
            "claim_ceiling",
            "operator_checklist",
            "blocked_claims",
            "stronger_claim_prerequisites",
            "execution_backend",
            "private_manifest_fingerprint",
            "pre_run_manifest_commitment",
            "pre_run_manifest_attestation",
            "local operator correlation only",
        ]:
            self.assertIn(required, text, f"spec missing required content: {required}")


class SealedReceiptSurfacePublicRegressionTests(unittest.TestCase):
    """Pin the sealing_receipt honesty boundary on a public-regression run."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        artifacts_root = Path(cls._tmpdir.name) / "artifacts"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "runner_bridge.autoresearch_alpha",
                "--request",
                str(EXAMPLE_REQUEST),
                "--artifacts-root",
                str(artifacts_root),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        assert result.returncode == 0, f"alpha loop failed: {result.stderr}"
        cls.receipt = json.loads((artifacts_root / "autoresearch-alpha.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_sealing_receipt_exists(self):
        self.assertIn("sealing_receipt", self.receipt)

    def test_sealing_receipt_spec_reference(self):
        sr = self.receipt["sealing_receipt"]
        self.assertEqual(sr["spec"], "015-sealed-receipt-surface")

    def test_claim_ceiling_is_honest(self):
        sr = self.receipt["sealing_receipt"]
        # Public regression run — claim ceiling must NOT mention sealed/certified/tamper-proof
        ceiling = sr["claim_ceiling"]
        self.assertIn("public-safe receipts", ceiling)
        for forbidden in ["sealed eval", "sealed cert", "tamper-proof", "independently audited"]:
            self.assertNotIn(forbidden, ceiling.lower())

    def test_status_is_public_regression_or_local_private_holdout(self):
        sr = self.receipt["sealing_receipt"]
        self.assertIn(sr["status"], {"public_regression_alpha", "local_private_holdout_alpha"})

    def test_blocked_claims_cover_all_four_overclaims(self):
        sr = self.receipt["sealing_receipt"]
        blocked_claim_names = {bc["claim"] for bc in sr["blocked_claims"]}
        for required in [
            "sealed evaluation",
            "sealed certification",
            "tamper-proof execution",
            "independently audited",
        ]:
            self.assertIn(required, blocked_claim_names, f"missing blocked claim: {required}")

    def test_each_blocked_claim_has_reason_and_prerequisite(self):
        sr = self.receipt["sealing_receipt"]
        for bc in sr["blocked_claims"]:
            self.assertIn("reason", bc, f"blocked claim {bc['claim']} missing reason")
            self.assertIn("prerequisite", bc, f"blocked claim {bc['claim']} missing prerequisite")
            self.assertTrue(len(bc["reason"]) > 10)
            self.assertTrue(len(bc["prerequisite"]) > 10)

    def test_operator_checklist_has_required_entries(self):
        sr = self.receipt["sealing_receipt"]
        checklist = sr["operator_checklist"]
        required_entries = [
            "public_benchmark_pack_loaded",
            "integrity_gate_passed",
            "private_holdout_manifest_loaded",
            "independent_executor_sandbox",
            "third_party_holdout_auditor",
            "hardware_attestation_or_enclave",
            "external_audit",
            "pre_run_manifest_commitment",
            "pre_run_manifest_attestation",
        ]
        for entry in required_entries:
            self.assertIn(entry, checklist, f"missing checklist entry: {entry}")
            self.assertIn("present", checklist[entry])
            self.assertIn("reason", checklist[entry])
            self.assertIsInstance(checklist[entry]["present"], bool)

    def test_stronger_controls_are_all_missing(self):
        """Pin that no stronger control is accidentally marked present."""
        sr = self.receipt["sealing_receipt"]
        checklist = sr["operator_checklist"]
        must_be_false = [
            "independent_executor_sandbox",
            "third_party_holdout_auditor",
            "hardware_attestation_or_enclave",
            "external_audit",
            "pre_run_manifest_commitment",
            "pre_run_manifest_attestation",
        ]
        for entry in must_be_false:
            self.assertFalse(
                checklist[entry]["present"],
                f"{entry} must be False — landing this control requires code + spec changes, not just a flag flip",
            )

    def test_stronger_claim_prerequisites_present(self):
        sr = self.receipt["sealing_receipt"]
        prereqs = sr["stronger_claim_prerequisites"]
        self.assertIsInstance(prereqs, list)
        self.assertEqual(len(prereqs), 5)

    def test_stronger_claim_prerequisites_cover_all_five(self):
        sr = self.receipt["sealing_receipt"]
        enables_set = {p["enables"] for p in sr["stronger_claim_prerequisites"]}
        for expected in [
            "sealed evaluation",
            "sealed certification",
            "tamper-proof execution",
            "independently audited",
            "stronger tamper-evidence claims beyond local correlation",
        ]:
            self.assertIn(expected, enables_set, f"missing prerequisite enables: {expected}")

    def test_stronger_claim_prerequisites_all_unmet(self):
        sr = self.receipt["sealing_receipt"]
        for p in sr["stronger_claim_prerequisites"]:
            self.assertFalse(
                p["met"],
                f"prerequisite '{p['prerequisite']}' must be unmet — landing this requires code + spec changes",
            )
            self.assertIn("prerequisite", p)
            self.assertIn("enables", p)
            self.assertIn("met", p)

    def test_execution_backend_summary_is_present_and_honest(self):
        sr = self.receipt["sealing_receipt"]
        backend = sr["execution_backend"]
        self.assertEqual(backend["aggregate_status"], "consistent")
        self.assertEqual(backend["backend_id"], "local_replay")
        self.assertEqual(backend["mode"], "zero_secret_replay")
        self.assertEqual(
            backend["execution_backend_contract"]["claim_boundary"]["independent_executor_isolation"],
            "not_claimed",
        )
        self.assertFalse(backend["execution_honesty"]["executes_commands"])
        self.assertFalse(backend["execution_honesty"]["executes_checks"])
        self.assertEqual(
            set(backend["stage_backends"].keys()),
            {"baseline-eval", "candidate-student", "candidate-teacher-eval"},
        )

    def test_public_regression_has_no_manifest_fingerprint(self):
        """A public-regression run should not have a private manifest fingerprint."""
        sr = self.receipt["sealing_receipt"]
        # The example request does not configure private_holdout_manifest
        if sr["status"] == "public_regression_alpha":
            self.assertIsNone(sr["private_manifest_fingerprint"])

    def test_linked_receipt_paths(self):
        sr = self.receipt["sealing_receipt"]
        paths = sr["linked_receipt_paths"]
        self.assertEqual(paths["alpha_receipt"], "autoresearch-alpha.json")
        self.assertEqual(paths["alpha_request_copy"], "autoresearch-alpha.request.json")

    def test_honesty_note_disclaims_seal(self):
        sr = self.receipt["sealing_receipt"]
        note = sr["honesty_note"]
        self.assertIn("not a seal", note)
        self.assertIn("public-safe boundary record", note)

    def test_public_regression_has_no_pre_run_commitment(self):
        """A public-regression run has no private holdout, so no pre-run commitment."""
        sr = self.receipt["sealing_receipt"]
        if sr["status"] == "public_regression_alpha":
            self.assertIsNone(sr["pre_run_manifest_commitment"])
            self.assertIsNone(sr["pre_run_manifest_attestation"])
            self.assertNotIn("pre_run_manifest_commitment", sr["linked_receipt_paths"])

    def test_integrity_gate_still_blocks_sealed_eval(self):
        """The existing integrity gate must also still block overclaiming."""
        ig = self.receipt["integrity_gate"]
        self.assertFalse(ig["sealed_eval_claim_ok"])
        self.assertFalse(ig["certification_claim_ok"])


class SealedReceiptFingerprintUnitTests(unittest.TestCase):
    """Unit-test the fingerprint labeling directly."""

    def test_fingerprint_is_labeled_local_correlation_only(self):
        from runner_bridge.autoresearch_alpha import _build_sealing_receipt

        mock_manifest = {
            "meta": {"id": "test", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }
        mock_gate = {
            "status": "pass",
            "mode": "local_private_holdout",
            "summary": "test",
        }

        sr = _build_sealing_receipt(
            integrity_gate=mock_gate,
            private_holdout_pack=mock_pack,
            artifacts_root=Path("/tmp/fake"),
        )

        fp = sr["private_manifest_fingerprint"]
        self.assertIsNotNone(fp)
        self.assertEqual(fp["algorithm"], "sha256")
        self.assertEqual(fp["scope"], "local_operator_correlation_only")
        self.assertIn("does not prove anything to a third party", fp["honesty_note"])

        # Verify the hash is correct
        canonical = json.dumps(mock_manifest, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        self.assertEqual(fp["hex_digest"], expected)

    def test_no_fingerprint_without_manifest(self):
        from runner_bridge.autoresearch_alpha import _build_sealing_receipt

        sr = _build_sealing_receipt(
            integrity_gate={"status": "pass", "mode": "public_regression", "summary": "test"},
            private_holdout_pack=None,
            artifacts_root=Path("/tmp/fake"),
        )
        self.assertIsNone(sr["private_manifest_fingerprint"])


class SealingReceiptExecutionBackendUnitTests(unittest.TestCase):
    def test_named_backend_summary_stays_claim_boundary_only(self):
        from runner_bridge.autoresearch_alpha import _build_sealing_receipt
        from runner_bridge.backends import backend_contract_for_runner

        backend_contract = backend_contract_for_runner("claude_vibecosystem")
        stage_execution_backend = {
            "backend_id": "claude_vibecosystem",
            "runner_name": "claude_vibecosystem",
            "mode": "external_executor_beta",
            "selection_source": "packet_runtime.execution_backend",
            "execution_backend_contract": backend_contract,
            "execution_honesty": {
                "backend": "claude_vibecosystem",
                "mode": "external_executor_beta",
                "beta_status": "adapter_first_contract_stub",
                "executes_commands": False,
                "executes_checks": False,
                "claim_boundary": backend_contract["claim_boundary"],
                "honesty_note": "Contract/provenance seam only.",
            },
            "intended_executor_path": {
                "entrypoint": backend_contract["entrypoint"],
                "runtime": backend_contract["executor"]["runtime"],
                "agent_selection": backend_contract["executor"]["agent_selection"],
                "control_plane_path": backend_contract["control_plane"]["path"],
            },
        }

        stages = {
            "baseline-eval": {"execution_backend": stage_execution_backend},
            "candidate-student": {"execution_backend": stage_execution_backend},
            "candidate-teacher-eval": {"execution_backend": stage_execution_backend},
        }
        sr = _build_sealing_receipt(
            integrity_gate={"status": "pass", "mode": "public_regression", "summary": "test"},
            private_holdout_pack=None,
            artifacts_root=Path("/tmp/fake"),
            stages=stages,
        )

        backend = sr["execution_backend"]
        self.assertEqual(backend["aggregate_status"], "consistent")
        self.assertEqual(backend["backend_id"], "claude_vibecosystem")
        self.assertEqual(backend["mode"], "external_executor_beta")
        self.assertEqual(
            backend["execution_backend_contract"]["claim_boundary"]["sealed_evaluation"],
            "not_claimed",
        )
        self.assertFalse(backend["execution_honesty"]["executes_commands"])
        self.assertFalse(sr["operator_checklist"]["independent_executor_sandbox"]["present"])
        self.assertIn("not a seal", sr["honesty_note"])


class PreRunManifestCommitmentUnitTests(unittest.TestCase):
    """Unit-test the pre-run manifest commitment artifact."""

    def test_commitment_written_with_private_holdout(self):
        from runner_bridge.autoresearch_alpha import _write_pre_run_manifest_commitment

        mock_manifest = {
            "meta": {"id": "test-pack", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            result = _write_pre_run_manifest_commitment(
                integrity_gate_mode="local_private_holdout",
                private_holdout_pack=mock_pack,
                artifacts_root=artifacts_root,
                sequence_id="test-seq",
            )

            self.assertIsNotNone(result)
            self.assertEqual(result["type"], "pre_run_manifest_commitment")
            self.assertEqual(result["status"], "recorded_local_only")
            self.assertEqual(result["integrity_gate_mode"], "local_private_holdout")
            self.assertEqual(result["manifest_hash"]["algorithm"], "sha256")
            self.assertEqual(len(result["manifest_hash"]["hex_digest"]), 64)
            self.assertEqual(result["private_holdout_manifest_id"], "test-pack")
            self.assertEqual(result["sequence_id"], "test-seq")
            self.assertEqual(result["artifact_path"], "pre-run-manifest-commitment.json")
            self.assertEqual(result["linked_receipt_paths"]["alpha_receipt"], "autoresearch-alpha.json")
            self.assertEqual(result["linked_receipt_paths"]["alpha_request_copy"], "autoresearch-alpha.request.json")
            self.assertIsNone(result["pre_run_manifest_attestation"])
            self.assertIn("not independently published", result["honesty_note"])
            self.assertTrue(result["recorded_at"].endswith("Z"))

            # File was written.
            commitment_file = artifacts_root / "pre-run-manifest-commitment.json"
            self.assertTrue(commitment_file.exists())
            on_disk = json.loads(commitment_file.read_text())
            self.assertEqual(on_disk, result)

            # Hash matches what we'd compute directly.
            canonical = json.dumps(mock_manifest, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(canonical.encode()).hexdigest()
            self.assertEqual(result["manifest_hash"]["hex_digest"], expected)

    def test_commitment_preserves_public_safe_attestation_metadata(self):
        from runner_bridge.autoresearch_alpha import _write_pre_run_manifest_commitment

        mock_manifest = {
            "meta": {"id": "test-pack", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        canonical = json.dumps(mock_manifest, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }
        attestation = {
            "attestation_type": "third_party_witness",
            "attestor": {
                "display_name": "Example Witness Co",
                "role": "holdout witness",
                "uri": "https://example.test/witnesses/example-witness-co",
            },
            "reference": {
                "kind": "url",
                "value": "https://example.test/attestations/test-pack-001",
            },
            "attested_at": "2026-03-24T00:00:00Z",
            "attested_manifest_hash": {
                "algorithm": "sha256",
                "hex_digest": expected,
            },
            "public_note": "Recorded as a future tamper-evidence seam only.",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _write_pre_run_manifest_commitment(
                integrity_gate_mode="local_private_holdout",
                private_holdout_pack=mock_pack,
                artifacts_root=Path(tmpdir),
                sequence_id="test-seq",
                pre_run_manifest_attestation=attestation,
            )

            self.assertIsNotNone(result)
            recorded = result["pre_run_manifest_attestation"]
            self.assertEqual(recorded["status"], "metadata_reference_only")
            self.assertEqual(recorded["attestation_type"], "third_party_witness")
            self.assertEqual(recorded["attestor"]["display_name"], "Example Witness Co")
            self.assertEqual(recorded["attestor"]["role"], "holdout witness")
            self.assertEqual(recorded["reference"]["kind"], "url")
            self.assertEqual(
                recorded["reference"]["value"],
                "https://example.test/attestations/test-pack-001",
            )
            self.assertEqual(recorded["attested_manifest_hash"]["hex_digest"], expected)
            self.assertTrue(recorded["attested_manifest_hash"]["matches_local_manifest_hash"])
            self.assertEqual(recorded["verification"]["status"], "not_verified_by_role_foundry")
            self.assertIn("does not verify witness identity", recorded["verification"]["reason"])
            self.assertIn("does not by itself prove", recorded["honesty_note"])
            self.assertEqual(recorded["public_note"], "Recorded as a future tamper-evidence seam only.")

    def test_no_commitment_without_local_private_holdout_mode(self):
        from runner_bridge.autoresearch_alpha import _write_pre_run_manifest_commitment

        mock_manifest = {
            "meta": {"id": "test-pack", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            result = _write_pre_run_manifest_commitment(
                integrity_gate_mode="public_regression",
                private_holdout_pack=mock_pack,
                artifacts_root=Path(tmpdir),
                sequence_id="test",
            )
            self.assertIsNone(result)
            self.assertFalse((Path(tmpdir) / "pre-run-manifest-commitment.json").exists())

    def test_commitment_hash_matches_sealing_receipt_fingerprint(self):
        """The commitment hash must match the private_manifest_fingerprint."""
        from runner_bridge.autoresearch_alpha import (
            _build_sealing_receipt,
            _write_pre_run_manifest_commitment,
        )

        mock_manifest = {
            "meta": {"id": "test", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            commitment = _write_pre_run_manifest_commitment(
                integrity_gate_mode="local_private_holdout",
                private_holdout_pack=mock_pack,
                artifacts_root=artifacts_root,
                sequence_id="test",
            )
            sr = _build_sealing_receipt(
                integrity_gate={"status": "pass", "mode": "local_private_holdout", "summary": "test"},
                private_holdout_pack=mock_pack,
                artifacts_root=artifacts_root,
                pre_run_commitment=commitment,
            )

            self.assertEqual(
                sr["pre_run_manifest_commitment"]["manifest_hash"]["hex_digest"],
                sr["private_manifest_fingerprint"]["hex_digest"],
            )
            self.assertIsNone(sr["pre_run_manifest_attestation"])
            self.assertTrue(sr["operator_checklist"]["pre_run_manifest_commitment"]["present"])
            self.assertFalse(sr["operator_checklist"]["pre_run_manifest_attestation"]["present"])

    def test_sealing_receipt_threads_attestation_without_unlocking_claims(self):
        from runner_bridge.autoresearch_alpha import (
            _build_sealing_receipt,
            _write_pre_run_manifest_commitment,
        )

        mock_manifest = {
            "meta": {"id": "test", "visibility": "teacher_only", "public_repo_safe": False},
            "episodes": [{"id": "e1", "family_id": "f1", "title": "Test"}],
        }
        canonical = json.dumps(mock_manifest, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        mock_pack = {
            "manifest": mock_manifest,
            "meta": mock_manifest["meta"],
            "episodes_by_id": {},
            "episode_ids": [],
            "family_ids": [],
        }
        attestation = {
            "attestation_type": "third_party_signature",
            "attestor": {"display_name": "Example Signer"},
            "reference": {"kind": "opaque_id", "value": "signing-service:attestation:test-001"},
            "attested_manifest_hash": {"algorithm": "sha256", "hex_digest": expected},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            commitment = _write_pre_run_manifest_commitment(
                integrity_gate_mode="local_private_holdout",
                private_holdout_pack=mock_pack,
                artifacts_root=artifacts_root,
                sequence_id="test",
                pre_run_manifest_attestation=attestation,
            )
            sr = _build_sealing_receipt(
                integrity_gate={"status": "pass", "mode": "local_private_holdout", "summary": "test"},
                private_holdout_pack=mock_pack,
                artifacts_root=artifacts_root,
                pre_run_commitment=commitment,
            )

            self.assertEqual(
                sr["pre_run_manifest_attestation"],
                commitment["pre_run_manifest_attestation"],
            )
            self.assertTrue(sr["operator_checklist"]["pre_run_manifest_attestation"]["present"])
            self.assertIn(
                "does not verify witness identity",
                sr["operator_checklist"]["pre_run_manifest_attestation"]["reason"],
            )
            for prereq in sr["stronger_claim_prerequisites"]:
                self.assertFalse(prereq["met"])
            self.assertIn("reference-only", sr["honesty_note"])


class ReadmeHonestyBoundaryTests(unittest.TestCase):
    """README mentions the receipt surface and unmet prerequisites."""

    def test_readme_mentions_sealing_receipt(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("sealing_receipt", text)
        self.assertIn("Sealing receipt surface", text)

    def test_readme_mentions_local_pre_run_commitment(self):
        text = (ROOT / "README.md").read_text()
        self.assertIn("pre_run_manifest_commitment", text)
        self.assertIn("pre_run_manifest_attestation", text)
        self.assertIn("pre-run-manifest-commitment.json", text)
        self.assertIn("external publication", text)
        self.assertIn("third-party witnessing", text)

    def test_readme_lists_unmet_prerequisites(self):
        text = (ROOT / "README.md").read_text()
        for prereq in [
            "Independent executor sandbox",
            "Third-party holdout auditor",
            "Hardware attestation",
            "External audit",
        ]:
            self.assertIn(prereq, text, f"README missing prerequisite: {prereq}")

    def test_readme_does_not_overclaim(self):
        text = (ROOT / "README.md").read_text().lower()
        for overclaim in [
            "sealed evaluation",
            "sealed certification",
            "tamper-proof evaluation",
            "independently audited evaluation",
        ]:
            # These phrases may appear in "blocked" / "do not claim" context.
            # They must NOT appear in a positive claim context.
            # Check they only appear near "blocked" / "not" / "unmet" / "still"
            import re
            matches = list(re.finditer(re.escape(overclaim), text))
            for m in matches:
                context = text[max(0, m.start() - 200): m.end() + 200]
                has_negative = any(
                    neg in context
                    for neg in [
                        "blocked", "not ", "still ", "unmet", "do not",
                        "missing", "none of", "would enable", "prerequisite",
                        "enables", "required controls", "\" language",
                    ]
                )
                self.assertTrue(
                    has_negative,
                    f"README contains '{overclaim}' in potentially positive context: ...{context}...",
                )


if __name__ == "__main__":
    unittest.main()
