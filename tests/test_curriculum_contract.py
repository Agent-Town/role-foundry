"""Curriculum contract tests for the frozen Frontend/Product Engineer role.

These tests keep the role-specific, versioned curriculum surface honest while
also exercising the reusable validator/runtime helpers in runner_bridge.
"""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from runner_bridge import curriculum

ROOT = Path(__file__).resolve().parents[1]
ROLE_MANIFEST = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
EVAL_CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
TASK_SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-task-packet.schema.v1.json"
SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
SAMPLE_SCORECARD = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-scorecard.v1.json"
OPERATING_SPLIT_DOC = ROOT / "docs" / "curriculum-operating-split.md"
README = ROOT / "README.md"

GENERIC_ALIAS_PATHS = [
    ROOT / "seed" / "frontend-product-engineer.json",
    ROOT / "data" / "curriculum" / "evaluation-contract.json",
    ROOT / "data" / "curriculum" / "task-packet-schema.json",
    ROOT / "data" / "curriculum" / "curriculum-index.json",
    ROOT / "data" / "curriculum" / "tasks",
]

EXPECTED_ACCEPTANCE_TESTS = [
    ("A001", "Freeze the first apprentice role"),
    ("A002", "Freeze the evaluation contract"),
    ("A003", "Freeze the mutation surface"),
    ("A004", "Freeze the canonical task packet"),
    ("B001", "Build task authoring from a template"),
    ("B002", "Build source-intake -> curriculum promotion workflow"),
    ("B003", "Author the first 20-task seed set"),
    ("B004", "Add weekly holdout refresh"),
    ("C001", "Standardize isolated execution"),
    ("C002", "Wire baseline run as a first-class object"),
    ("C003", "Wire candidate run with real code/test execution"),
    ("C004", "Capture full receipts automatically"),
    ("D001", "Build the teacher review console"),
    ("D002", "Require private-holdout scoring for promotion"),
    ("D003", "Add repeated-run stability checks"),
    ("D004", "Add regression gates"),
    ("E001", "Turn failures into next-step curriculum"),
    ("E002", "Track generation lineage"),
    ("E003", "Run a real weekly training cycle"),
    ("E004", "Only then expand to a second role"),
]


class TestCanonicalArtifactSurface(unittest.TestCase):
    def test_versioned_role_specific_files_exist(self):
        for path in (
            ROLE_MANIFEST,
            EVAL_CONTRACT,
            TASK_SCHEMA,
            SEED_REGISTRY,
            SAMPLE_SCORECARD,
            OPERATING_SPLIT_DOC,
        ):
            self.assertTrue(path.exists(), f"missing {path}")

    def test_generic_alias_files_are_absent(self):
        for path in GENERIC_ALIAS_PATHS:
            self.assertFalse(path.exists(), f"unexpected duplicate curriculum surface: {path}")

    def test_readme_indexes_both_curriculum_docs(self):
        readme_text = README.read_text()
        self.assertIn("docs/frontend-product-engineer-seed-curriculum.md", readme_text)
        self.assertIn("docs/curriculum-operating-split.md", readme_text)


class TestRoleManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(ROLE_MANIFEST.read_text())

    def test_role_identity_is_frozen(self):
        role = self.manifest["role"]
        self.assertEqual(role["id"], curriculum.FROZEN_ROLE_ID)
        self.assertEqual(role["name"], curriculum.FROZEN_ROLE_NAME)

    def test_allowed_and_blocked_surfaces_are_explicit(self):
        role = self.manifest["role"]
        self.assertIn("app/**", role["allowed_root_paths_default"])
        self.assertIn("docs/**", role["allowed_root_paths_default"])
        self.assertIn("data/**", role["allowed_root_paths_default"])
        self.assertIn("submission/**", role["blocked_paths_default"])
        blocked_notes = " ".join(role["blocked_scope_notes"]).lower()
        for token in ("partner integrations", "wallet / chain work", "unrelated infra"):
            self.assertIn(token, blocked_notes)

    def test_manifest_points_at_canonical_contract_files(self):
        role = self.manifest["role"]
        self.assertEqual(
            role["scoring_contract_path"],
            EVAL_CONTRACT.relative_to(ROOT).as_posix(),
        )
        self.assertEqual(
            role["task_packet_schema_path"],
            TASK_SCHEMA.relative_to(ROOT).as_posix(),
        )
        self.assertEqual(
            role["seed_registry_path"],
            SEED_REGISTRY.relative_to(ROOT).as_posix(),
        )
        self.assertIn("014", self.manifest["meta"]["source_spec"])


class TestEvaluationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(EVAL_CONTRACT.read_text())

    def test_contract_validates_against_frozen_constants(self):
        curriculum.validate_evaluation_contract(self.contract)

    def test_contract_dimensions_match_spec_014(self):
        dimensions = {entry["id"]: entry for entry in self.contract["dimensions"]}
        self.assertEqual(set(dimensions), set(curriculum.FROZEN_DIMENSIONS))
        for dimension, weight in curriculum.FROZEN_DIMENSIONS.items():
            self.assertAlmostEqual(dimensions[dimension]["weight"], weight, places=2)

    def test_contract_thresholds_match_frozen_values(self):
        thresholds = self.contract["thresholds"]
        self.assertEqual(thresholds["task_pass"]["weighted_score_min"], curriculum.TASK_PASS_THRESHOLD)
        self.assertEqual(thresholds["task_pass"]["dimension_floor_min"], curriculum.TASK_MIN_DIMENSION)
        gate = thresholds["promotion_gate"]
        self.assertEqual(gate["public_weighted_score_min"], curriculum.PROMOTION_PUBLIC_THRESHOLD)
        self.assertEqual(gate["private_holdout_weighted_score_min"], curriculum.PROMOTION_HOLDOUT_THRESHOLD)
        self.assertEqual(gate["critical_dimension_floors"]["regression_safety"], curriculum.PROMOTION_CRITICAL_FLOOR)
        self.assertEqual(gate["critical_dimension_floors"]["honesty_boundary_discipline"], curriculum.PROMOTION_CRITICAL_FLOOR)

    def test_contract_declares_minimum_task_packet_fields(self):
        declared = set(self.contract["required_task_packet_fields"])
        self.assertTrue(set(curriculum.REQUIRED_TASK_FIELDS).issubset(declared))


class TestPublicSeedRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(SEED_REGISTRY.read_text())
        cls.tasks = cls.registry["tasks"]

    def test_registry_has_20_tasks_in_spec_order(self):
        found = [(task["acceptance_test_id"], task["title"]) for task in self.tasks]
        self.assertEqual(found, EXPECTED_ACCEPTANCE_TESTS)
        self.assertEqual(self.registry["counts"]["task_count"], 20)

    def test_registry_has_4_tasks_per_phase(self):
        phase_counts = Counter(task["phase"]["index"] for task in self.tasks)
        self.assertEqual(phase_counts, Counter({1: 4, 2: 4, 3: 4, 4: 4, 5: 4}))

    def test_every_packet_validates_against_runtime_helper(self):
        for task in self.tasks:
            curriculum.validate_task_packet(task)
            self.assertEqual(task["role_id"], curriculum.FROZEN_ROLE_ID)
            self.assertEqual(task["rubric_ref"]["contract_id"], self.registry["meta"]["evaluation_contract_path"].split("/")[-1].replace(".json", "").replace(".v1", "-v1"))
            self.assertEqual(task["rubric_ref"]["contract_path"], EVAL_CONTRACT.relative_to(ROOT).as_posix())

    def test_public_seed_packets_stay_student_visible_and_public_safe(self):
        serialized = SEED_REGISTRY.read_text().lower()
        for task in self.tasks:
            self.assertTrue(task["student_visible"])
            self.assertFalse(task["teacher_only_fields_present"])
            self.assertEqual(task["status"], "public_seed_defined")
        for token in ("teacher_prompt", "judge-only prompt", "private scoring rubric"):
            self.assertNotIn(token, serialized)


class TestOperatingSplitHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc_text = OPERATING_SPLIT_DOC.read_text()

    def test_doc_names_the_canonical_contract_surface(self):
        for token in (
            "seed/frontend-product-engineer-role.v1.json",
            "data/curriculum/frontend-product-engineer-evaluation-contract.v1.json",
            "data/curriculum/frontend-product-engineer-task-packet.schema.v1.json",
            "data/curriculum/frontend-product-engineer-public-seed-registry.v1.json",
            "runner_bridge/curriculum.py",
        ):
            self.assertIn(token, self.doc_text)

    def test_doc_explains_defined_vs_live_status(self):
        self.assertIn("20 public seed task packets are checked in", self.doc_text)
        self.assertIn("Packet-defined, runtime not yet live", self.doc_text)
        self.assertIn("There is intentionally no separate generic", self.doc_text)

    def test_doc_keeps_step_c_verifier_gate_honest(self):
        self.assertIn("verifier_contract", self.doc_text)
        self.assertIn("verifier_gate", self.doc_text)
        self.assertIn('not_executed', self.doc_text)


class TestValidatorModule(unittest.TestCase):
    def test_module_path_constants_point_at_versioned_files(self):
        self.assertEqual(curriculum.ROLE_MANIFEST_PATH, ROLE_MANIFEST)
        self.assertEqual(curriculum.EVAL_CONTRACT_PATH, EVAL_CONTRACT)
        self.assertEqual(curriculum.TASK_SCHEMA_PATH, TASK_SCHEMA)
        self.assertEqual(curriculum.SEED_REGISTRY_PATH, SEED_REGISTRY)

    def test_load_registry_task_returns_a_valid_packet(self):
        packet = curriculum.load_registry_task("A001")
        self.assertEqual(packet["acceptance_test_id"], "A001")
        self.assertEqual(packet["role_id"], curriculum.FROZEN_ROLE_ID)

    def test_sample_scorecard_round_trip_passes(self):
        scorecard = json.loads(SAMPLE_SCORECARD.read_text())
        scores = curriculum.score_map_from_scorecard(scorecard)
        curriculum.validate_scorecard(scores)
        self.assertTrue(curriculum.check_task_pass(scores))

    def test_scorecard_missing_dimension_is_rejected(self):
        bad = {key: 0.9 for key in curriculum.FROZEN_DIMENSIONS}
        del bad["evidence_quality"]
        with self.assertRaises(ValueError):
            curriculum.validate_scorecard(bad)

    def test_tampered_contract_is_rejected(self):
        tampered = json.loads(EVAL_CONTRACT.read_text())
        for dimension in tampered["dimensions"]:
            if dimension["id"] == "task_outcome":
                dimension["weight"] = 0.5
                break
        with self.assertRaises(ValueError):
            curriculum.validate_evaluation_contract(tampered)


if __name__ == "__main__":
    unittest.main()
