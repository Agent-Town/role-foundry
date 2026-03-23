"""Tests for spec-014 curriculum contract implementation.

Covers: role manifest alignment, evaluation contract normalization,
task-packet schema validation, mutation-budget defaults, seed packet
coverage, and teacher/student separation rules.

TDD-first: these tests were written before the implementation artifacts.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── Artifact paths ──────────────────────────────────────────────────
ROLE_MANIFEST = ROOT / "seed" / "frontend-product-engineer.json"
EVAL_CONTRACT = ROOT / "data" / "curriculum" / "evaluation-contract.json"
TASK_SCHEMA = ROOT / "data" / "curriculum" / "task-packet-schema.json"
CURRICULUM_INDEX = ROOT / "data" / "curriculum" / "curriculum-index.json"
TASKS_DIR = ROOT / "data" / "curriculum" / "tasks"

# ── Spec constants ──────────────────────────────────────────────────
FROZEN_ROLE_ID = "frontend-product-engineer"
FROZEN_ROLE_NAME = "Frontend/Product Engineer"

FROZEN_DIMENSIONS = {
    "task_outcome": 0.30,
    "regression_safety": 0.25,
    "mutation_discipline": 0.15,
    "evidence_quality": 0.15,
    "honesty_boundary_discipline": 0.15,
}

TASK_PASS_THRESHOLD = 0.80
TASK_MIN_DIMENSION = 0.60
PROMOTION_PUBLIC_THRESHOLD = 0.85
PROMOTION_HOLDOUT_THRESHOLD = 0.75
PROMOTION_CRITICAL_FLOOR = 0.90

DEFAULT_MAX_FILES = 6
DEFAULT_MAX_LINES = 400

REQUIRED_TASK_FIELDS = [
    "task_id",
    "role_id",
    "phase",
    "objective",
    "context",
    "allowed_paths",
    "blocked_paths",
    "expected_checks",
    "rubric_ref",
    "time_budget_minutes",
    "evidence_contract",
]

PHASE_1_IDS = ["A001", "A002", "A003", "A004"]

ALL_TASK_IDS = [
    "A001", "A002", "A003", "A004",
    "B001", "B002", "B003", "B004",
    "C001", "C002", "C003", "C004",
    "D001", "D002", "D003", "D004",
    "E001", "E002", "E003", "E004",
]


# ════════════════════════════════════════════════════════════════════
# A001 — Role manifest tests
# ════════════════════════════════════════════════════════════════════

class TestRoleManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(ROLE_MANIFEST.read_text())

    def test_manifest_exists(self):
        self.assertTrue(ROLE_MANIFEST.exists())

    def test_role_id_matches_frozen_spec(self):
        self.assertEqual(self.manifest["role"]["id"], FROZEN_ROLE_ID)

    def test_role_name_matches_frozen_spec(self):
        self.assertEqual(self.manifest["role"]["name"], FROZEN_ROLE_NAME)

    def test_allowed_paths_present(self):
        allowed = self.manifest["role"]["allowed_paths"]
        self.assertIsInstance(allowed, list)
        self.assertGreater(len(allowed), 0)
        for p in ["app/**", "docs/**", "specs/**", "tests/**", "data/**", "seed/**"]:
            self.assertIn(p, allowed)

    def test_blocked_paths_present(self):
        blocked = self.manifest["role"]["blocked_paths"]
        self.assertIsInstance(blocked, list)
        self.assertGreater(len(blocked), 0)

    def test_blocked_paths_exclude_partner_wallet_infra(self):
        blocked = self.manifest["role"]["blocked_paths"]
        blocked_text = " ".join(blocked).lower()
        # The blocked list or blocked_categories must mention these
        categories = self.manifest["role"].get("blocked_categories", [])
        all_blocked = blocked_text + " " + " ".join(categories).lower()
        for term in ["partner", "wallet", "chain", "infra"]:
            self.assertIn(term, all_blocked,
                          f"Blocked surface must mention '{term}'")

    def test_manifest_references_spec_014(self):
        ref = self.manifest.get("meta", {}).get("spec", "")
        self.assertIn("014", ref)


# ════════════════════════════════════════════════════════════════════
# A002 — Evaluation contract tests
# ════════════════════════════════════════════════════════════════════

class TestEvaluationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(EVAL_CONTRACT.read_text())

    def test_contract_exists(self):
        self.assertTrue(EVAL_CONTRACT.exists())

    def test_dimensions_match_frozen_spec(self):
        dims = self.contract["dimensions"]
        for key, weight in FROZEN_DIMENSIONS.items():
            self.assertIn(key, dims)
            self.assertAlmostEqual(dims[key]["weight"], weight, places=2)

    def test_weights_sum_to_one(self):
        total = sum(d["weight"] for d in self.contract["dimensions"].values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_thresholds_present(self):
        t = self.contract["thresholds"]
        self.assertAlmostEqual(t["task_pass"], TASK_PASS_THRESHOLD)
        self.assertAlmostEqual(t["task_min_dimension"], TASK_MIN_DIMENSION)
        self.assertAlmostEqual(t["promotion_public"], PROMOTION_PUBLIC_THRESHOLD)
        self.assertAlmostEqual(t["promotion_holdout"], PROMOTION_HOLDOUT_THRESHOLD)
        self.assertAlmostEqual(t["promotion_critical_floor"], PROMOTION_CRITICAL_FLOOR)

    def test_critical_dimensions_identified(self):
        crit = self.contract["thresholds"]["critical_dimensions"]
        self.assertIn("regression_safety", crit)
        self.assertIn("honesty_boundary_discipline", crit)

    def test_contract_rejects_missing_dimension(self):
        """Validator should reject a scorecard missing a dimension."""
        from runner_bridge.curriculum import validate_scorecard
        bad = {k: 0.85 for k in FROZEN_DIMENSIONS}
        del bad["evidence_quality"]
        with self.assertRaises(ValueError):
            validate_scorecard(bad)

    def test_contract_rejects_renormalized_weights(self):
        """Validator should reject tampered weights."""
        from runner_bridge.curriculum import validate_evaluation_contract
        tampered = json.loads(EVAL_CONTRACT.read_text())
        tampered["dimensions"]["task_outcome"]["weight"] = 0.50
        with self.assertRaises(ValueError):
            validate_evaluation_contract(tampered)


# ════════════════════════════════════════════════════════════════════
# A003 — Mutation surface tests
# ════════════════════════════════════════════════════════════════════

class TestMutationSurface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packets = {}
        for p in TASKS_DIR.glob("*.json"):
            cls.packets[p.stem] = json.loads(p.read_text())

    def test_every_packet_declares_allowed_paths(self):
        for tid, pkt in self.packets.items():
            self.assertIn("allowed_paths", pkt, f"{tid} missing allowed_paths")
            self.assertIsInstance(pkt["allowed_paths"], list)
            self.assertGreater(len(pkt["allowed_paths"]), 0,
                               f"{tid} allowed_paths is empty")

    def test_every_packet_declares_blocked_paths(self):
        for tid, pkt in self.packets.items():
            self.assertIn("blocked_paths", pkt, f"{tid} missing blocked_paths")
            self.assertIsInstance(pkt["blocked_paths"], list)

    def test_mutation_budget_defaults(self):
        for tid, pkt in self.packets.items():
            budget = pkt.get("mutation_budget", {})
            max_files = budget.get("max_files", DEFAULT_MAX_FILES)
            max_lines = budget.get("max_lines", DEFAULT_MAX_LINES)
            self.assertLessEqual(max_files, DEFAULT_MAX_FILES * 2,
                                 f"{tid} max_files unreasonably high")
            self.assertLessEqual(max_lines, DEFAULT_MAX_LINES * 2,
                                 f"{tid} max_lines unreasonably high")

    def test_default_budget_constants_match_spec(self):
        self.assertEqual(DEFAULT_MAX_FILES, 6)
        self.assertEqual(DEFAULT_MAX_LINES, 400)


# ════════════════════════════════════════════════════════════════════
# A004 — Task packet schema tests
# ════════════════════════════════════════════════════════════════════

class TestTaskPacketSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(TASK_SCHEMA.read_text())
        cls.packets = {}
        for p in TASKS_DIR.glob("*.json"):
            cls.packets[p.stem] = json.loads(p.read_text())

    def test_schema_exists(self):
        self.assertTrue(TASK_SCHEMA.exists())

    def test_schema_requires_all_spec_fields(self):
        required = self.schema.get("required", [])
        for f in REQUIRED_TASK_FIELDS:
            self.assertIn(f, required, f"Schema missing required field: {f}")

    def test_all_seed_packets_validate_against_schema(self):
        from runner_bridge.curriculum import validate_task_packet
        for tid, pkt in self.packets.items():
            try:
                validate_task_packet(pkt)
            except Exception as e:
                self.fail(f"Task packet {tid} failed validation: {e}")

    def test_all_seed_packets_have_required_fields(self):
        for tid, pkt in self.packets.items():
            for f in REQUIRED_TASK_FIELDS:
                self.assertIn(f, pkt, f"{tid} missing field: {f}")

    def test_all_seed_packets_reference_frozen_role(self):
        for tid, pkt in self.packets.items():
            self.assertEqual(pkt["role_id"], FROZEN_ROLE_ID,
                             f"{tid} has wrong role_id")

    def test_at_least_two_example_packets_exist(self):
        self.assertGreaterEqual(len(self.packets), 2)

    def test_validator_rejects_packet_missing_required_field(self):
        from runner_bridge.curriculum import validate_task_packet
        bad = {"task_id": "X999", "role_id": FROZEN_ROLE_ID}
        with self.assertRaises(ValueError):
            validate_task_packet(bad)


# ════════════════════════════════════════════════════════════════════
# Curriculum index / registry tests
# ════════════════════════════════════════════════════════════════════

class TestCurriculumIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads(CURRICULUM_INDEX.read_text())

    def test_index_exists(self):
        self.assertTrue(CURRICULUM_INDEX.exists())

    def test_index_has_20_entries(self):
        self.assertEqual(len(self.index["tasks"]), 20)

    def test_every_entry_has_task_id_and_phase(self):
        for entry in self.index["tasks"]:
            self.assertIn("task_id", entry)
            self.assertIn("phase", entry)

    def test_index_task_ids_match_spec(self):
        ids = [e["task_id"] for e in self.index["tasks"]]
        self.assertEqual(ids, ALL_TASK_IDS)

    def test_phase_balance_is_4_per_phase(self):
        from collections import Counter
        phases = Counter(e["phase"] for e in self.index["tasks"])
        for phase_num in range(1, 6):
            self.assertEqual(phases[phase_num], 4,
                             f"Phase {phase_num} should have 4 tasks")

    def test_implemented_status_is_honest(self):
        """Only Phase 1 packets are actually implemented now."""
        for entry in self.index["tasks"]:
            if entry["task_id"] in PHASE_1_IDS:
                self.assertEqual(entry["status"], "implemented",
                                 f"{entry['task_id']} should be implemented")
            else:
                self.assertIn(entry["status"], ("planned", "future"),
                              f"{entry['task_id']} should be planned/future")

    def test_implemented_packets_exist_on_disk(self):
        for entry in self.index["tasks"]:
            if entry["status"] == "implemented":
                packet_file = TASKS_DIR / f"{entry['task_id']}.json"
                self.assertTrue(packet_file.exists(),
                                f"Implemented {entry['task_id']} has no packet file")

    def test_planned_packets_do_not_exist(self):
        """Planned tasks should NOT have fake packet files."""
        for entry in self.index["tasks"]:
            if entry["status"] in ("planned", "future"):
                packet_file = TASKS_DIR / f"{entry['task_id']}.json"
                self.assertFalse(packet_file.exists(),
                                 f"Planned {entry['task_id']} should not have a packet file yet")


# ════════════════════════════════════════════════════════════════════
# Provenance / separation rules
# ════════════════════════════════════════════════════════════════════

class TestProvenanceAndSeparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(ROLE_MANIFEST.read_text())
        cls.packets = {}
        for p in TASKS_DIR.glob("*.json"):
            cls.packets[p.stem] = json.loads(p.read_text())

    def test_all_packets_reference_rubric(self):
        for tid, pkt in self.packets.items():
            ref = pkt.get("rubric_ref", "")
            self.assertTrue(ref, f"{tid} missing rubric_ref")
            self.assertIn("evaluation-contract", ref)

    def test_all_packets_have_evidence_contract(self):
        for tid, pkt in self.packets.items():
            ec = pkt.get("evidence_contract", {})
            self.assertIsInstance(ec, dict, f"{tid} evidence_contract not dict")
            self.assertGreater(len(ec), 0, f"{tid} evidence_contract empty")

    def test_no_packet_references_private_holdout_content(self):
        """Public task packets must not leak holdout content.

        Note: blocked_paths may reference 'private-holdout-pack' as a
        blocking rule — that is correct, not a leak. We check that
        objectives, context, and evidence do not reference holdout content.
        """
        leak_fields = ("objective", "context", "pass_threshold",
                       "failure_interpretation")
        for tid, pkt in self.packets.items():
            for field in leak_fields:
                val = str(pkt.get(field, "")).lower()
                self.assertNotIn("private-holdout-pack", val,
                                 f"{tid}.{field} references private holdout content")


# ════════════════════════════════════════════════════════════════════
# Validator module tests
# ════════════════════════════════════════════════════════════════════

class TestValidatorModule(unittest.TestCase):
    def test_module_importable(self):
        import runner_bridge.curriculum  # noqa: F401

    def test_validate_task_packet_function_exists(self):
        from runner_bridge.curriculum import validate_task_packet
        self.assertTrue(callable(validate_task_packet))

    def test_validate_scorecard_function_exists(self):
        from runner_bridge.curriculum import validate_scorecard
        self.assertTrue(callable(validate_scorecard))

    def test_validate_evaluation_contract_function_exists(self):
        from runner_bridge.curriculum import validate_evaluation_contract
        self.assertTrue(callable(validate_evaluation_contract))

    def test_scorecard_pass_check(self):
        from runner_bridge.curriculum import check_task_pass
        passing = {k: 0.90 for k in FROZEN_DIMENSIONS}
        self.assertTrue(check_task_pass(passing))

    def test_scorecard_fail_below_threshold(self):
        from runner_bridge.curriculum import check_task_pass
        failing = {k: 0.70 for k in FROZEN_DIMENSIONS}
        self.assertFalse(check_task_pass(failing))

    def test_scorecard_fail_one_dimension_below_floor(self):
        from runner_bridge.curriculum import check_task_pass
        scores = {k: 0.90 for k in FROZEN_DIMENSIONS}
        scores["evidence_quality"] = 0.50  # below 0.60 floor
        self.assertFalse(check_task_pass(scores))


if __name__ == "__main__":
    unittest.main()
