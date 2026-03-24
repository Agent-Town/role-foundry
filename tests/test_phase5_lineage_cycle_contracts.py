"""Phase 5 contract tests: generation lineage, weekly training cycles, and
cross-artifact linkage.

These tests enforce:
- Generation lineage registry schema and content honesty
- Weekly training-cycle receipt schema and end-to-end flow
- Linkage between curriculum contracts, run objects, promotion decisions,
  failure follow-up, and curriculum updates
- Honesty boundaries: no teacher-only holdout content in public artifacts,
  run objects marked available=false when not tracked in git, all sample
  artifacts clearly marked example_only
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from runner_bridge import curriculum
from runner_bridge.lineage import (
    LINEAGE_REGISTRY_PATH,
    LINEAGE_SCHEMA_PATH,
    WEEKLY_CYCLE_PATH,
    WEEKLY_CYCLE_SCHEMA_PATH,
    check_promoted_score_threshold,
    load_lineage_registry,
    load_weekly_cycle,
    validate_lineage_registry,
    validate_weekly_cycle,
    verify_lineage_cycle_linkage,
)

ROOT = Path(__file__).resolve().parents[1]

SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
EVAL_CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
SAMPLE_RUN_OBJECTS = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-run-objects.v1.json"
OPERATING_SPLIT_DOC = ROOT / "docs" / "curriculum-operating-split.md"
PHASE5_DOC = ROOT / "docs" / "phase5-lineage-cycle-ops.md"
README = ROOT / "README.md"


class TestPhase5ArtifactSurface(unittest.TestCase):
    """All Phase 5 schema and data files exist."""

    def test_lineage_schema_exists(self):
        self.assertTrue(LINEAGE_SCHEMA_PATH.exists())

    def test_lineage_registry_exists(self):
        self.assertTrue(LINEAGE_REGISTRY_PATH.exists())

    def test_weekly_cycle_schema_exists(self):
        self.assertTrue(WEEKLY_CYCLE_SCHEMA_PATH.exists())

    def test_weekly_cycle_receipt_exists(self):
        self.assertTrue(WEEKLY_CYCLE_PATH.exists())


class TestSchemaContracts(unittest.TestCase):
    """Schema files stay machine-readable and aligned with the helper contracts."""

    @classmethod
    def setUpClass(cls):
        cls.lineage_schema = json.loads(LINEAGE_SCHEMA_PATH.read_text())
        cls.weekly_schema = json.loads(WEEKLY_CYCLE_SCHEMA_PATH.read_text())

    def test_lineage_schema_has_expected_identity_and_required_fields(self):
        self.assertEqual(self.lineage_schema["$id"], "generation-lineage-registry.schema.v1")
        self.assertEqual(self.lineage_schema["type"], "object")
        self.assertEqual(set(self.lineage_schema["required"]), {"meta", "generations"})
        generation_required = set(
            self.lineage_schema["properties"]["generations"]["items"]["required"]
        )
        for field in (
            "generation_id",
            "generation_index",
            "parent_generation_id",
            "promotion_decision",
            "curriculum_contract_ref",
            "run_object_ref",
            "regression_gate",
        ):
            self.assertIn(field, generation_required)

    def test_weekly_cycle_schema_has_expected_identity_and_required_fields(self):
        self.assertEqual(self.weekly_schema["$id"], "weekly-training-cycle-receipt.schema.v1")
        self.assertEqual(self.weekly_schema["type"], "object")
        self.assertEqual(set(self.weekly_schema["required"]), {"meta", "cycle"})
        cycle_required = set(self.weekly_schema["properties"]["cycle"]["required"])
        for field in (
            "task_selection",
            "baseline",
            "candidate",
            "teacher_review",
            "promotion_decision",
            "regression_gate",
            "curriculum_update",
            "generation_ref",
        ):
            self.assertIn(field, cycle_required)


class TestGenerationLineageRegistry(unittest.TestCase):
    """Validates the generation lineage registry contract."""

    @classmethod
    def setUpClass(cls):
        cls.registry = load_lineage_registry()
        cls.generations = cls.registry["generations"]

    def test_meta_role_id_matches_frozen_role(self):
        self.assertEqual(
            self.registry["meta"]["role_id"],
            curriculum.FROZEN_ROLE_ID,
        )

    def test_meta_marks_example_only(self):
        self.assertTrue(self.registry["meta"]["example_only"])

    def test_has_at_least_3_promoted_generations(self):
        promoted = [g for g in self.generations if g["promoted"]]
        self.assertGreaterEqual(len(promoted), 3)

    def test_all_generations_marked_example_only(self):
        for gen in self.generations:
            self.assertTrue(
                gen["example_only"],
                f"{gen['generation_id']} must be marked example_only",
            )

    def test_generation_indices_are_sequential(self):
        for i, gen in enumerate(self.generations):
            self.assertEqual(gen["generation_index"], i + 1)

    def test_first_generation_has_null_parent(self):
        self.assertIsNone(self.generations[0]["parent_generation_id"])

    def test_subsequent_generations_reference_prior(self):
        seen = {self.generations[0]["generation_id"]}
        for gen in self.generations[1:]:
            self.assertIn(
                gen["parent_generation_id"], seen,
                f"{gen['generation_id']} parent not in prior generations",
            )
            seen.add(gen["generation_id"])

    def test_every_generation_references_canonical_contract_paths(self):
        expected_registry = SEED_REGISTRY.relative_to(ROOT).as_posix()
        expected_contract = EVAL_CONTRACT.relative_to(ROOT).as_posix()
        for gen in self.generations:
            ref = gen["curriculum_contract_ref"]
            self.assertEqual(ref["seed_registry_path"], expected_registry)
            self.assertEqual(ref["evaluation_contract_path"], expected_contract)

    def test_promoted_generations_have_public_score_above_threshold(self):
        for gen in self.generations:
            if gen["promoted"]:
                score = gen["promotion_decision"]["public_score"]
                self.assertIsNotNone(score)
                self.assertGreaterEqual(
                    score, curriculum.PROMOTION_PUBLIC_THRESHOLD,
                    f"{gen['generation_id']} public_score below promotion threshold",
                )

    def test_run_object_refs_honest_about_availability(self):
        for gen in self.generations:
            ref = gen["run_object_ref"]
            self.assertIn("available", ref)
            if not ref["available"]:
                self.assertIsNotNone(
                    ref.get("sample_run_objects_path"),
                    f"{gen['generation_id']} unavailable run_object_ref "
                    "should point to sample_run_objects_path",
                )

    def test_regression_gate_declares_enforced_status(self):
        for gen in self.generations:
            gate = gen["regression_gate"]
            self.assertIn("enforced", gate)

    def test_no_teacher_only_content_in_lineage(self):
        serialized = json.dumps(self.registry).lower()
        for token in (
            "teacher_prompt", "scoring_rubric", "judge-only prompt",
            "holdout_score_value", "private_holdout_score",
        ):
            self.assertNotIn(
                token, serialized,
                f"lineage must not contain teacher-only token: {token}",
            )

    def test_failure_follow_up_linkage(self):
        """At least one generation has failure follow-up with curriculum updates."""
        has_follow_up = False
        for gen in self.generations:
            ff = gen.get("failure_follow_up")
            if ff is not None:
                has_follow_up = True
                self.assertIn("failures_identified", ff)
                self.assertIn("curriculum_updates", ff)
                for update in ff["curriculum_updates"]:
                    self.assertIn(update["action"], (
                        "new_task", "modified_existing_task", "ignore_defer",
                    ))
                    self.assertTrue(update["description"])
        self.assertTrue(has_follow_up, "at least one generation should have failure_follow_up")


class TestWeeklyCycleReceipt(unittest.TestCase):
    """Validates the weekly training cycle receipt contract."""

    @classmethod
    def setUpClass(cls):
        cls.receipt = load_weekly_cycle()
        cls.cycle = cls.receipt["cycle"]

    def test_meta_role_id_matches_frozen_role(self):
        self.assertEqual(
            self.receipt["meta"]["role_id"],
            curriculum.FROZEN_ROLE_ID,
        )

    def test_meta_marks_example_only(self):
        self.assertTrue(self.receipt["meta"]["example_only"])

    def test_cycle_marks_example_only(self):
        self.assertTrue(self.cycle["example_only"])

    def test_task_selection_has_tasks(self):
        sel = self.cycle["task_selection"]
        self.assertIsInstance(sel["task_ids"], list)
        self.assertTrue(len(sel["task_ids"]) > 0)

    def test_task_selection_ids_are_valid(self):
        """Selected task IDs must exist in the seed registry."""
        registry = json.loads(SEED_REGISTRY.read_text())
        valid_ids = {t["acceptance_test_id"] for t in registry["tasks"]}
        for tid in self.cycle["task_selection"]["task_ids"]:
            self.assertIn(tid, valid_ids, f"task {tid} not in seed registry")

    def test_baseline_and_candidate_present(self):
        for key in ("baseline", "candidate"):
            run = self.cycle[key]
            self.assertIn("available", run)
            self.assertIn("run_id", run)

    def test_teacher_review_present(self):
        review = self.cycle["teacher_review"]
        self.assertIn("reviewed", review)
        self.assertIn("review_method", review)

    def test_promotion_decision_present_and_valid(self):
        pd = self.cycle["promotion_decision"]
        self.assertIn(pd["decision"], ("promoted", "not_promoted", "deferred"))
        self.assertIn("public_score", pd)
        self.assertIn("holdout_score_available", pd)

    def test_regression_gate_present(self):
        rg = self.cycle["regression_gate"]
        self.assertIn("enforced", rg)

    def test_curriculum_update_present(self):
        cu = self.cycle["curriculum_update"]
        self.assertIn("updates_made", cu)

    def test_generation_ref_present(self):
        gr = self.cycle["generation_ref"]
        self.assertIn("generation_id", gr)

    def test_end_to_end_cycle_connects_all_stages(self):
        """The sample cycle must connect task selection through to generation ref."""
        self.assertTrue(self.cycle["task_selection"]["task_ids"])
        self.assertIsNotNone(self.cycle["baseline"]["run_id"])
        self.assertIsNotNone(self.cycle["candidate"]["run_id"])
        self.assertTrue(self.cycle["teacher_review"]["reviewed"])
        self.assertIn(
            self.cycle["promotion_decision"]["decision"],
            ("promoted", "not_promoted", "deferred"),
        )
        self.assertIsNotNone(self.cycle["generation_ref"]["generation_id"])

    def test_no_teacher_only_content_in_cycle(self):
        serialized = json.dumps(self.receipt).lower()
        for token in (
            "teacher_prompt", "scoring_rubric", "judge-only prompt",
            "holdout_score_value", "private_holdout_score",
        ):
            self.assertNotIn(token, serialized)


class TestCrossArtifactLinkage(unittest.TestCase):
    """Validates linkage between lineage, weekly cycles, curriculum, and run objects."""

    @classmethod
    def setUpClass(cls):
        cls.lineage = load_lineage_registry()
        cls.cycle = load_weekly_cycle()
        cls.run_objects = json.loads(SAMPLE_RUN_OBJECTS.read_text())

    def test_weekly_cycle_links_to_lineage_generation(self):
        issues = verify_lineage_cycle_linkage(self.lineage, self.cycle)
        self.assertEqual(issues, [], f"linkage issues: {issues}")

    def test_lineage_references_same_seed_registry_as_curriculum(self):
        expected = SEED_REGISTRY.relative_to(ROOT).as_posix()
        for gen in self.lineage["generations"]:
            self.assertEqual(
                gen["curriculum_contract_ref"]["seed_registry_path"],
                expected,
            )

    def test_lineage_references_same_eval_contract_as_curriculum(self):
        expected = EVAL_CONTRACT.relative_to(ROOT).as_posix()
        for gen in self.lineage["generations"]:
            self.assertEqual(
                gen["curriculum_contract_ref"]["evaluation_contract_path"],
                expected,
            )

    def test_sample_run_objects_linkable_from_lineage(self):
        """At least one generation references the sample run objects file."""
        sample_path = SAMPLE_RUN_OBJECTS.relative_to(ROOT).as_posix()
        found = False
        for gen in self.lineage["generations"]:
            ref = gen["run_object_ref"]
            if ref.get("sample_run_objects_path") == sample_path:
                found = True
                break
        self.assertTrue(found, "at least one generation should reference sample run objects")

    def test_weekly_cycle_baseline_run_id_matches_sample(self):
        """The weekly cycle baseline run_id should match the sample run objects."""
        cycle_baseline_id = self.cycle["cycle"]["baseline"]["run_id"]
        sample_baseline_id = self.run_objects["baseline_run"]["run_id"]
        self.assertEqual(cycle_baseline_id, sample_baseline_id)

    def test_weekly_cycle_candidate_run_id_matches_sample(self):
        cycle_candidate_id = self.cycle["cycle"]["candidate"]["run_id"]
        sample_candidate_id = self.run_objects["candidate_run"]["run_id"]
        self.assertEqual(cycle_candidate_id, sample_candidate_id)


class TestPhase5Docs(unittest.TestCase):
    """Docs and indexes must expose the Phase 5 contract surface honestly."""

    @classmethod
    def setUpClass(cls):
        cls.readme_text = README.read_text()
        cls.operating_split_text = OPERATING_SPLIT_DOC.read_text()
        cls.phase5_doc_text = PHASE5_DOC.read_text()

    def test_readme_indexes_phase5_doc(self):
        self.assertIn("docs/phase5-lineage-cycle-ops.md", self.readme_text)

    def test_operating_split_mentions_phase5_contract_surface(self):
        for token in (
            "runner_bridge/lineage.py",
            "tests/test_phase5_lineage_cycle_contracts.py",
            "docs/phase5-lineage-cycle-ops.md",
        ):
            self.assertIn(token, self.operating_split_text)

    def test_phase5_doc_calls_out_fixture_only_scope(self):
        for token in (
            "contract-level fixture/sample artifacts",
            "NOT live automation",
            "holdout_score_available",
            "available: false",
        ):
            self.assertIn(token, self.phase5_doc_text)


class TestHonestyBoundaries(unittest.TestCase):
    """Enforces honesty constraints across Phase 5 artifacts."""

    @classmethod
    def setUpClass(cls):
        cls.lineage = load_lineage_registry()
        cls.cycle = load_weekly_cycle()

    def test_no_artifact_claims_live_weekly_automation(self):
        """No artifact should claim to be a real weekly cycle unless example_only is false."""
        self.assertTrue(self.lineage["meta"]["example_only"])
        self.assertTrue(self.cycle["meta"]["example_only"])
        self.assertTrue(self.cycle["cycle"]["example_only"])
        for gen in self.lineage["generations"]:
            self.assertTrue(gen["example_only"])

    def test_private_holdouts_not_tracked_in_git(self):
        """No Phase 5 artifact should contain actual holdout score values."""
        for gen in self.lineage["generations"]:
            pd = gen["promotion_decision"]
            # holdout_score_available is a boolean, not a score value
            self.assertNotIn("holdout_score_value", pd)
            self.assertNotIn("private_holdout_score", pd)

    def test_run_objects_not_falsely_claimed_available(self):
        """Run objects marked available must have an artifact_root."""
        for gen in self.lineage["generations"]:
            ref = gen["run_object_ref"]
            if ref["available"]:
                self.assertIsNotNone(
                    ref.get("artifact_root"),
                    f"{gen['generation_id']} claims available but has no artifact_root",
                )

    def test_regression_gates_honest_about_enforcement(self):
        """If regression gate not enforced, tasks_checked should be null."""
        for gen in self.lineage["generations"]:
            gate = gen["regression_gate"]
            if not gate["enforced"]:
                self.assertIsNone(gate.get("tasks_checked"))
                self.assertIsNone(gate.get("regressions_found"))


class TestValidatorEdgeCases(unittest.TestCase):
    """Tests for the lineage module validation helpers."""

    def test_check_promoted_score_threshold_passes(self):
        self.assertTrue(check_promoted_score_threshold(0.90))
        self.assertTrue(check_promoted_score_threshold(0.85))

    def test_check_promoted_score_threshold_fails(self):
        self.assertFalse(check_promoted_score_threshold(0.84))
        self.assertFalse(check_promoted_score_threshold(None))

    def test_validate_lineage_rejects_missing_meta(self):
        with self.assertRaises(ValueError):
            validate_lineage_registry({"generations": []})

    def test_validate_lineage_rejects_empty_generations(self):
        with self.assertRaises(ValueError):
            validate_lineage_registry({
                "meta": {
                    "role_id": curriculum.FROZEN_ROLE_ID,
                    "schema_version": "1.0.0",
                },
                "generations": [],
            })

    def test_validate_lineage_rejects_wrong_role_id(self):
        with self.assertRaises(ValueError):
            validate_lineage_registry({
                "meta": {
                    "role_id": "wrong-role",
                    "schema_version": "1.0.0",
                },
                "generations": [{}],
            })

    def test_validate_weekly_cycle_rejects_missing_cycle(self):
        with self.assertRaises(ValueError):
            validate_weekly_cycle({
                "meta": {
                    "role_id": curriculum.FROZEN_ROLE_ID,
                    "schema_version": "1.0.0",
                },
            })

    def test_linkage_verifier_catches_missing_generation(self):
        fake_lineage = {"generations": []}
        fake_cycle = {
            "cycle": {
                "generation_ref": {"generation_id": "nonexistent"},
            },
        }
        issues = verify_lineage_cycle_linkage(fake_lineage, fake_cycle)
        self.assertTrue(any("not in the lineage" in i for i in issues))

    def test_linkage_verifier_catches_null_generation_ref(self):
        fake_cycle = {
            "cycle": {
                "generation_ref": {"generation_id": None},
            },
        }
        issues = verify_lineage_cycle_linkage({"generations": []}, fake_cycle)
        self.assertTrue(any("null" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
