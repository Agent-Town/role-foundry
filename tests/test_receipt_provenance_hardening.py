from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runner_bridge.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]
TEACHER_EVAL_REQUEST = ROOT / "runner_bridge" / "examples" / "teacher-eval-loop.json"
ALPHA_REQUEST = ROOT / "runner_bridge" / "examples" / "autoresearch-alpha-public-loop.json"
ORIGINAL_HOLDOUT_TITLE = "Sealed Holdout — Fake Live Wiring Temptation"


class AuditBundlePacketRuntimeTests(unittest.TestCase):
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

    def test_audit_bundle_is_emitted_and_threaded_through_public_surfaces(self):
        run_dir = self._run_packet("A001", "audit-packet-a001")

        audit_bundle = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())
        manifest = json.loads((run_dir / "receipts" / "manifest.json").read_text())
        result = json.loads((run_dir / "result.json").read_text())
        artifact_bundle = json.loads((run_dir / "artifact-bundle.json").read_text())
        draft = json.loads((run_dir / "integrations" / "erc8004-registration-draft.json").read_text())

        self.assertEqual(audit_bundle["run_id"], "audit-packet-a001")
        self.assertEqual(manifest["receipts"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(result["provenance"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(artifact_bundle["receipts"]["audit_bundle_path"], "receipts/audit-bundle.json")
        self.assertEqual(
            draft["extensions"]["role_foundry"]["proof"]["audit_bundle_path"],
            "receipts/audit-bundle.json",
        )

    def test_packet_runtime_human_audit_is_honest_about_missing_teacher_sections(self):
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

    def test_required_artifact_validation_is_machine_readable_and_honest(self):
        run_dir = self._run_packet("A001", "audit-packet-required")
        validation = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())["required_artifact_validation"]

        self.assertEqual(validation["status"], "pass")
        self.assertGreater(validation["declared_count"], 0)
        self.assertEqual(validation["missing_count"], 0)
        self.assertIn("does not prove command execution", validation["honesty_note"])
        for item in validation["results"]:
            self.assertIn(item["status"], {"pass", "missing"})
            self.assertIn(item["present_in"], {"repo", "run", "repo+run", "missing"})

    def test_redaction_audit_reports_read_model_as_not_emitted_without_claiming_failure(self):
        run_dir = self._run_packet("A001", "audit-packet-redaction")
        redaction = json.loads((run_dir / "receipts" / "audit-bundle.json").read_text())["redaction_audit"]

        self.assertEqual(redaction["status"], "pass")
        surfaces = {entry["surface"]: entry for entry in redaction["checks"]}
        for surface in (
            "receipts/manifest.json",
            "receipts/summary.md",
            "receipts/audit-bundle.json",
            "integrations/trust-bundle.json",
            "integrations/erc8004-registration-draft.json",
            "integrations/summary.md",
        ):
            self.assertEqual(surfaces[surface]["status"], "clean")
        self.assertEqual(surfaces["read-model-export"]["status"], "not_emitted")
        self.assertTrue(all(entry["status"] != "leak_detected" for entry in redaction["checks"]))

    def test_summary_markdown_lists_the_five_human_audit_sections(self):
        run_dir = self._run_packet("A001", "audit-packet-summary")
        summary = (run_dir / "receipts" / "summary.md").read_text()

        for heading in (
            "## Run metadata",
            "## Benchmark input summary",
            "## Mutation summary",
            "## Teacher scorecard",
            "## Verdict and reasons",
        ):
            self.assertIn(heading, summary)


class TeacherEvalRedactionAuditTests(unittest.TestCase):
    def test_teacher_eval_run_keeps_private_prompts_out_of_student_facing_request_and_audit_passes(self):
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

            self.assertNotIn('"teacher_prompt"', request_json)
            self.assertNotIn('"scoring_rubric"', request_json)
            self.assertNotIn(ORIGINAL_HOLDOUT_TITLE, request_json)
            self.assertIn('"prompt_visibility": "sealed"', request_json)

            self.assertEqual(sections["teacher_scorecard"]["status"], "available")
            self.assertEqual(sections["verdict_and_reasons"]["status"], "available")
            self.assertEqual(redaction["status"], "pass")
            self.assertGreater(redaction["sensitive_value_count"], 0)

            surfaces = {entry["surface"]: entry for entry in redaction["checks"]}
            self.assertEqual(surfaces["request.json"]["status"], "clean")
            for surface in (
                "receipts/manifest.json",
                "receipts/summary.md",
                "receipts/audit-bundle.json",
                "integrations/trust-bundle.json",
                "integrations/erc8004-registration-draft.json",
                "integrations/summary.md",
            ):
                self.assertEqual(surfaces[surface]["status"], "clean")
            self.assertEqual(surfaces["read-model-export"]["status"], "not_emitted")

            summary = (run_dir / "receipts" / "summary.md").read_text()
            self.assertIn("## Teacher scorecard", summary)
            self.assertIn("## Verdict and reasons", summary)


class AutoresearchAlphaTraceabilityTests(unittest.TestCase):
    def _run_alpha_public(self, artifacts_root: Path) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "runner_bridge.autoresearch_alpha",
                "--request",
                str(ALPHA_REQUEST),
                "--artifacts-root",
                str(artifacts_root),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((artifacts_root / "autoresearch-alpha.json").read_text())

    def test_stage_lineage_uses_loop_sequence_id_and_stage_traceability_carries_pack_and_episode_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            receipt = self._run_alpha_public(artifacts_root)
            sequence_id = receipt["sequence_id"]

            baseline_run_id = receipt["stages"]["baseline-eval"]["run_id"]
            candidate_student_run_id = receipt["stages"]["candidate-student"]["run_id"]

            for stage_key, expected_iteration, expected_label, expected_root, expected_parent in (
                ("baseline-eval", 1, "baseline", baseline_run_id, None),
                ("candidate-student", 2, "candidate-student", baseline_run_id, baseline_run_id),
                ("candidate-teacher-eval", 3, "candidate", baseline_run_id, candidate_student_run_id),
            ):
                stage = receipt["stages"][stage_key]
                self.assertEqual(stage["lineage"]["sequence_id"], sequence_id)
                self.assertIn("scenario_set_id", stage["lineage"])
                self.assertEqual(stage["traceability"]["root_run_id"], expected_root)
                self.assertEqual(stage["traceability"]["parent_run_id"], expected_parent)
                self.assertEqual(stage["traceability"]["iteration_index"], expected_iteration)
                self.assertEqual(stage["traceability"]["iteration_label"], expected_label)
                self.assertEqual(stage["traceability"]["benchmark_pack"]["id"], "public-benchmark-pack-v1")
                self.assertTrue(stage["traceability"]["benchmark_pack"]["version"])

            candidate_traceability = receipt["stages"]["candidate-student"]["traceability"]
            self.assertGreater(len(candidate_traceability["episodes"]["visible_episode_ids"]), 0)
            self.assertGreater(len(candidate_traceability["episodes"]["family_ids"]), 0)

            baseline_traceability = receipt["stages"]["baseline-eval"]["traceability"]
            self.assertEqual(baseline_traceability["episodes"]["holdout_episode_ids"]["status"], "withheld")
            self.assertGreater(baseline_traceability["episodes"]["holdout_count"], 0)

    def test_stage_audit_bundles_mark_teacher_sections_available_only_where_truthful(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            receipt = self._run_alpha_public(artifacts_root)

            baseline_run_id = receipt["stages"]["baseline-eval"]["run_id"]
            candidate_student_run_id = receipt["stages"]["candidate-student"]["run_id"]

            for stage_key, expected_status, expected_iteration, expected_label, expected_root, expected_parent in (
                ("baseline-eval", "available", 1, "baseline", baseline_run_id, None),
                ("candidate-student", "unavailable", 2, "candidate-student", baseline_run_id, baseline_run_id),
                ("candidate-teacher-eval", "available", 3, "candidate", baseline_run_id, candidate_student_run_id),
            ):
                run_id = receipt["stages"][stage_key]["run_id"]
                audit_bundle = json.loads((artifacts_root / run_id / "receipts" / "audit-bundle.json").read_text())
                sections = audit_bundle["human_audit"]["sections"]
                lineage = audit_bundle["traceability"]["lineage"]
                redaction_surfaces = {entry["surface"]: entry for entry in audit_bundle["redaction_audit"]["checks"]}

                self.assertEqual(sections["teacher_scorecard"]["status"], expected_status)
                self.assertEqual(lineage["sequence_id"], receipt["sequence_id"])
                self.assertEqual(lineage["stage_key"], stage_key)
                self.assertEqual(lineage["root_run_id"], expected_root)
                self.assertEqual(lineage["parent_run_id"], expected_parent)
                self.assertEqual(lineage["iteration_index"], expected_iteration)
                self.assertEqual(lineage["iteration_label"], expected_label)
                for surface in (
                    "receipts/manifest.json",
                    "receipts/summary.md",
                    "receipts/audit-bundle.json",
                    "integrations/trust-bundle.json",
                    "integrations/erc8004-registration-draft.json",
                    "integrations/summary.md",
                ):
                    self.assertEqual(redaction_surfaces[surface]["status"], "clean")
                if expected_status == "unavailable":
                    self.assertIn("honesty_note", sections["teacher_scorecard"])
                    self.assertIn("honesty_note", sections["verdict_and_reasons"])

    def test_artifact_coverage_requires_the_audit_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            receipt = self._run_alpha_public(artifacts_root)

            for stage_key in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
                checks = receipt["artifact_coverage"][stage_key]["checks"]
                self.assertTrue(checks["receipts/audit-bundle.json"])
                self.assertTrue(checks["bundle_provenance_has_audit_bundle"])
                self.assertTrue(checks["result_provenance_has_audit_bundle"])


if __name__ == "__main__":
    unittest.main()
