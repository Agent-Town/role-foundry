from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runner_bridge.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]
TEACHER_EVAL_REQUEST = ROOT / "runner_bridge" / "examples" / "teacher-eval-loop.json"
ORIGINAL_HOLDOUT_TITLE = "Sealed Holdout — Fake Live Wiring Temptation"


class PacketRuntimeAuditBundleTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.artifacts_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_packet(self, packet_id: str, run_id: str) -> Path:
        exit_code = cli_main([
            "--packet",
            packet_id,
            "--run-id",
            run_id,
            "--artifacts-root",
            str(self.artifacts_root),
        ])
        self.assertEqual(exit_code, 0)
        return self.artifacts_root / run_id

    def test_d001_audit_bundle_is_emitted_and_threaded_through_public_surfaces(self):
        run_dir = self._run_packet("A001", "audit-packet-a001")

        audit_bundle = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())
        manifest = json.loads((run_dir / "receipts" / "manifest.json").read_text())
        result = json.loads((run_dir / "result.json").read_text())
        artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())

        self.assertEqual(audit_bundle["run_id"], "audit-packet-a001")
        self.assertEqual(manifest["receipts"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(result["provenance"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(artifact_bundle["receipts"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(artifact_bundle["provenance"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertTrue(
            any(artifact["path"] == "receipts/audit-bundle.json" for artifact in manifest["artifacts"])
        )
        self.assertEqual(audit_bundle["artifact_index"]["status"], "finalized")
        indexed_paths = {entry["path"] for entry in audit_bundle["artifact_index"]["generated_artifacts"]}
        self.assertIn("receipts/manifest.json", indexed_paths)
        self.assertIn("receipts/summary.md", indexed_paths)
        self.assertIn("receipts/audit-bundle.json", indexed_paths)

    def test_d002_packet_runtime_human_audit_is_honest_about_missing_teacher_sections(self):
        run_dir = self._run_packet("A001", "audit-packet-sections")
        audit_bundle = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())
        sections = audit_bundle["human_audit"]["sections"]

        self.assertEqual(sections["run_metadata"]["status"], "available")
        self.assertEqual(sections["benchmark_input_summary"]["status"], "available")
        self.assertEqual(sections["mutation_summary"]["status"], "partial")
        self.assertEqual(sections["teacher_scorecard"]["status"], "unavailable")
        self.assertEqual(sections["verdict_and_reasons"]["status"], "unavailable")
        self.assertIn("honesty_note", sections["teacher_scorecard"])
        self.assertIn("honesty_note", sections["verdict_and_reasons"])
        self.assertEqual(audit_bundle["human_audit"]["status"], "partial")

    def test_d003_required_artifact_validation_is_machine_readable_and_honest(self):
        run_dir = self._run_packet("A001", "audit-packet-required")
        validation = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())["required_artifact_validation"]

        self.assertEqual(validation["status"], "pass")
        self.assertGreater(validation["declared_count"], 0)
        self.assertEqual(validation["missing_count"], 0)
        self.assertIn("does not prove command execution", validation["honesty_note"])
        for item in validation["results"]:
            self.assertIn(item["status"], {"pass", "missing"})
            self.assertIn(item["present_in"], {"repo", "run", "repo+run", "missing"})

    def test_d004_redaction_audit_and_summary_headings_stay_honest_on_packet_runtime(self):
        run_dir = self._run_packet("A001", "audit-packet-redaction")
        audit_bundle = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())
        redaction = audit_bundle["redaction_audit"]
        summary = (run_dir / "receipts" / "summary.md").read_text()

        self.assertEqual(redaction["status"], "pass")
        surfaces = {entry["surface"]: entry for entry in redaction["checks"]}
        for surface in (
            "request.json",
            "artifact-bundle.json",
            "result.json",
            "run-object.json",
            "receipts/manifest.json",
            "receipts/summary.md",
            "receipts/audit-bundle.json",
        ):
            self.assertEqual(surfaces[surface]["status"], "clean")
        self.assertEqual(surfaces["read-model-export"]["status"], "not_emitted")
        self.assertTrue(all(entry["status"] != "leak_detected" for entry in redaction["checks"]))

        for heading in (
            "## Run metadata",
            "## Benchmark input summary",
            "## Mutation summary",
            "## Teacher scorecard",
            "## Verdict and reasons",
        ):
            self.assertIn(heading, summary)


class TeacherEvalRedactionAuditTests(unittest.TestCase):
    def test_d005_teacher_eval_run_keeps_private_prompts_out_of_public_request_and_audit_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            exit_code = cli_main([
                "--request",
                str(TEACHER_EVAL_REQUEST),
                "--artifacts-root",
                str(artifacts_root),
            ])
            self.assertEqual(exit_code, 0)

            run_dir = artifacts_root / "run-eval-002"
            request_json = (run_dir / "request.json").read_text()
            audit_bundle = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())
            sections = audit_bundle["human_audit"]["sections"]
            redaction = audit_bundle["redaction_audit"]
            surfaces = {entry["surface"]: entry for entry in redaction["checks"]}
            summary = (run_dir / "receipts" / "summary.md").read_text()

            self.assertNotIn('"teacher_prompt"', request_json)
            self.assertNotIn('"holdout_prompt"', request_json)
            self.assertNotIn('"scoring_rubric"', request_json)
            self.assertNotIn(ORIGINAL_HOLDOUT_TITLE, request_json)
            self.assertIn('"prompt_visibility": "sealed"', request_json)

            self.assertEqual(sections["teacher_scorecard"]["status"], "available")
            self.assertEqual(sections["verdict_and_reasons"]["status"], "available")
            self.assertEqual(redaction["status"], "pass")
            self.assertGreater(redaction["sensitive_value_count"], 0)
            self.assertEqual(surfaces["request.json"]["status"], "clean")
            self.assertEqual(surfaces["receipts/manifest.json"]["status"], "clean")
            self.assertEqual(surfaces["receipts/summary.md"]["status"], "clean")
            self.assertEqual(surfaces["receipts/audit-bundle.json"]["status"], "clean")
            self.assertEqual(surfaces["read-model-export"]["status"], "not_emitted")
            self.assertIn("## Teacher scorecard", summary)
            self.assertIn("## Verdict and reasons", summary)


if __name__ == "__main__":
    unittest.main()
