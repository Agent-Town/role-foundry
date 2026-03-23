import json
import math
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
TEMPLATE = ROOT / "seed" / "frontend-product-engineer-task-template.v1.json"
CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-task-packet.schema.v1.json"
SOURCES = ROOT / "data" / "curriculum" / "frontend-product-engineer-source-records.v1.json"
PROMOTIONS = ROOT / "data" / "curriculum" / "frontend-product-engineer-promotion-records.v1.json"
REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
SCORECARD = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-scorecard.v1.json"
RUN_OBJECTS = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-run-objects.v1.json"
DOC = ROOT / "docs" / "frontend-product-engineer-seed-curriculum.md"
README = ROOT / "README.md"
SPEC = ROOT / "specs" / "014-frontend-product-engineer-20-task-curriculum.md"

EXPECTED_TESTS = [
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

REQUIRED_PACKET_FIELDS = {
    "task_id",
    "role_id",
    "acceptance_test_id",
    "title",
    "phase",
    "objective",
    "context",
    "success_criteria",
    "allowed_paths",
    "blocked_paths",
    "expected_checks",
    "rubric_ref",
    "time_budget_minutes",
    "mutation_budget",
    "evidence_contract",
    "provenance",
    "packet_version",
    "student_visible",
    "teacher_only_fields_present",
}


class FrontendProductEngineerSeedRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role = json.loads(ROLE.read_text())
        cls.template = json.loads(TEMPLATE.read_text())
        cls.contract = json.loads(CONTRACT.read_text())
        cls.schema = json.loads(SCHEMA.read_text())
        cls.sources = json.loads(SOURCES.read_text())
        cls.promotions = json.loads(PROMOTIONS.read_text())
        cls.registry = json.loads(REGISTRY.read_text())
        cls.scorecard = json.loads(SCORECARD.read_text())
        cls.run_objects = json.loads(RUN_OBJECTS.read_text())
        cls.tasks = cls.registry["tasks"]
        cls.task_by_code = {task["acceptance_test_id"]: task for task in cls.tasks}
        cls.source_by_id = {record["id"]: record for record in cls.sources["source_records"]}
        cls.promotion_by_id = {record["id"]: record for record in cls.promotions["promotion_records"]}

    def test_files_exist(self):
        for path in (ROLE, TEMPLATE, CONTRACT, SCHEMA, SOURCES, PROMOTIONS, REGISTRY, SCORECARD, RUN_OBJECTS, DOC):
            self.assertTrue(path.exists(), f"missing {path}")

    def test_A001_role_manifest_is_frozen(self):
        role = self.role["role"]
        self.assertEqual(role["name"], "Frontend/Product Engineer")
        self.assertEqual(role["id"], self.registry["meta"]["role_id"])
        self.assertEqual({task["role_id"] for task in self.tasks}, {role["id"]})
        blocked = json.dumps(role["blocked_scope_notes"]).lower()
        for token in ("partner integrations", "wallet / chain work", "unrelated infra"):
            self.assertIn(token, blocked)

    def test_A002_evaluation_contract_is_frozen(self):
        labels = [dimension["label"] for dimension in self.contract["dimensions"]]
        self.assertEqual(
            labels,
            [
                "Task outcome",
                "Regression safety",
                "Mutation discipline",
                "Evidence quality",
                "Honesty / boundary discipline",
            ],
        )
        total = sum(dimension["weight"] for dimension in self.contract["dimensions"])
        self.assertTrue(math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9))
        self.assertEqual(self.contract["thresholds"]["task_pass"]["weighted_score_min"], 0.80)
        self.assertEqual(self.contract["thresholds"]["task_pass"]["dimension_floor_min"], 0.60)
        gate = self.contract["thresholds"]["promotion_gate"]
        self.assertEqual(gate["public_weighted_score_min"], 0.85)
        self.assertEqual(gate["private_holdout_weighted_score_min"], 0.75)
        self.assertEqual(gate["critical_dimension_floors"]["regression_safety"], 0.90)
        self.assertEqual(gate["critical_dimension_floors"]["honesty_boundary_discipline"], 0.90)
        self.assertEqual(self.scorecard["meta"]["evaluation_contract_id"], self.contract["meta"]["id"])
        self.assertEqual(self.scorecard["meta"]["evaluation_contract_version"], self.contract["meta"]["version"])

    def test_A003_every_task_declares_mutation_surface_and_budget(self):
        defaults = self.contract["mutation_budget_defaults"]
        self.assertEqual(defaults["tracked_files_max"], 6)
        self.assertEqual(defaults["net_lines_max"], 400)
        for task in self.tasks:
            self.assertTrue(task["allowed_paths"])
            self.assertTrue(task["blocked_paths"])
            budget = task["mutation_budget"]
            self.assertIn("tracked_files_max", budget)
            self.assertIn("net_lines_max", budget)
            if not budget["overrides_default"]:
                self.assertLessEqual(budget["tracked_files_max"], defaults["tracked_files_max"])
                self.assertLessEqual(budget["net_lines_max"], defaults["net_lines_max"])
            else:
                self.assertTrue(budget["override_reason"])
        for run_key in ("baseline_run", "candidate_run"):
            run = self.run_objects[run_key]
            self.assertTrue(run["changed_files"])
            self.assertIn("tracked_files", run["diff_stats"])
            self.assertIn("net_lines", run["diff_stats"])

    def test_A004_schema_and_packet_contract_are_machine_readable(self):
        required = set(self.schema["required"])
        self.assertTrue(REQUIRED_PACKET_FIELDS.issubset(required))
        for task in self.tasks:
            self.assertTrue(REQUIRED_PACKET_FIELDS.issubset(task.keys()))
            self.assertFalse(task["teacher_only_fields_present"])
            self.assertTrue(task["student_visible"])
        self.assertEqual(
            self.run_objects["baseline_run"]["task_packet_version"],
            self.run_objects["candidate_run"]["task_packet_version"],
        )

    def test_B001_authoring_template_is_complete(self):
        for field in REQUIRED_PACKET_FIELDS:
            self.assertIn(field, self.template)
        self.assertTrue(self.template["objective"].strip())
        self.assertTrue(self.template["context"]["summary"].strip())
        self.assertTrue(self.template["expected_checks"])
        self.assertTrue(self.template["evidence_contract"]["required_artifacts"])
        self.assertNotEqual(self.template["time_budget_minutes"], 0)

    def test_B002_provenance_maps_one_source_and_one_promotion_record_per_task(self):
        self.assertEqual(len(self.sources["source_records"]), 20)
        self.assertEqual(len(self.promotions["promotion_records"]), 20)
        for task in self.tasks:
            provenance = task["provenance"]
            source = self.source_by_id[provenance["source_record_id"]]
            promotion = self.promotion_by_id[provenance["promotion_record_id"]]
            self.assertEqual(source["acceptance_test_id"], task["acceptance_test_id"])
            self.assertEqual(promotion["task_id"], task["task_id"])
            self.assertEqual(promotion["source_record_id"], source["id"])
            self.assertFalse(source["teacher_only_inputs_used"])
            self.assertFalse(promotion["teacher_only_inputs_used"])
            self.assertFalse(provenance["teacher_only_inputs_used"])

    def test_B003_full_seed_set_exists_with_phase_balance(self):
        self.assertEqual(self.registry["counts"]["task_count"], 20)
        self.assertEqual(len(self.tasks), 20)
        found = [(task["acceptance_test_id"], task["title"]) for task in self.tasks]
        self.assertEqual(found, EXPECTED_TESTS)
        phase_counts = Counter(task["phase"]["id"] for task in self.tasks)
        self.assertEqual(set(phase_counts.values()), {4})
        self.assertEqual(len(phase_counts), 5)

    def test_B004_public_registry_stays_public_safe(self):
        serialized = REGISTRY.read_text().lower()
        for token in ("teacher_prompt", "scoring_rubric", "judge-only prompt"):
            self.assertNotIn(token, serialized)
        self.assertTrue(self.registry["meta"]["student_visible_only"])
        self.assertFalse(self.registry["meta"]["teacher_only_fields_present"])

    def test_C001_run_objects_record_isolated_execution(self):
        for run_key in ("baseline_run", "candidate_run"):
            run = self.run_objects[run_key]
            self.assertTrue(run["example_only"])
            self.assertEqual(run["workspace"]["kind"], "git_worktree")
            self.assertTrue(run["workspace"]["isolated"])
            self.assertTrue(run["workspace"]["base_commit"])
            self.assertFalse(run["workspace"]["root_checkout_allowed_for_scoring"])
            self.assertTrue(run["artifact_root"].startswith("runtime/runs/"))

    def test_C002_baseline_and_candidate_share_packet_and_contract_versions(self):
        baseline = self.run_objects["baseline_run"]
        candidate = self.run_objects["candidate_run"]
        self.assertEqual(baseline["task_packet_version"], candidate["task_packet_version"])
        self.assertEqual(baseline["evaluation_contract_version"], candidate["evaluation_contract_version"])
        self.assertEqual(candidate["baseline_run_id"], baseline["run_id"])
        self.assertIn("weighted_score", baseline)

    def test_C003_candidate_run_fixture_captures_execution_fields(self):
        candidate = self.run_objects["candidate_run"]
        self.assertTrue(candidate["commands"])
        for command in candidate["commands"]:
            self.assertIn("command", command)
            self.assertIn("exit_code", command)
            self.assertIn("stdout_capture", command)
            self.assertIn("stderr_capture", command)
        self.assertTrue(candidate["changed_files"])
        self.assertTrue(candidate["checks_run"])
        self.assertEqual(candidate["checks_run"][0]["stage"], "post_change")

    def test_C004_receipt_surface_is_complete(self):
        for run_key in ("baseline_run", "candidate_run"):
            receipts = self.run_objects[run_key]["receipts"]
            for field in (
                "task_packet_ref",
                "transcript_path",
                "changed_files_path",
                "checks_path",
                "scorecard_path",
                "provenance_manifest_path",
            ):
                self.assertIn(field, receipts)

    def test_D001_teacher_review_packet_is_seeded(self):
        task = self.task_by_code["D001"]
        self.assertIn("app/**", task["allowed_paths"])
        serialized = json.dumps(task).lower()
        for token in (
            "diff summary",
            "changed files",
            "command results",
            "transcript excerpt",
            "weighted score breakdown",
            "promotion decision",
        ):
            self.assertIn(token, serialized)

    def test_D002_private_holdout_promotion_gate_is_machine_readable(self):
        gate = self.contract["thresholds"]["promotion_gate"]
        self.assertEqual(gate["public_weighted_score_min"], 0.85)
        self.assertEqual(gate["private_holdout_weighted_score_min"], 0.75)
        task = self.task_by_code["D002"]
        serialized = json.dumps(task).lower()
        self.assertIn("private-holdout", serialized)
        self.assertIn("0.90", serialized)

    def test_D003_stability_thresholds_are_declared(self):
        serialized = json.dumps(self.task_by_code["D003"]).lower()
        for token in ("3 runs", "2 of 3", "0.10"):
            self.assertIn(token, serialized)

    def test_D004_regression_gate_thresholds_are_declared(self):
        serialized = json.dumps(self.task_by_code["D004"]).lower()
        for token in ("last 10 promoted public tasks", "critical regressions", "0.90"):
            self.assertIn(token, serialized)

    def test_E001_failure_to_curriculum_linkage_is_declared(self):
        serialized = json.dumps(self.task_by_code["E001"]).lower()
        for token in ("new task", "modified existing task", "ignore/defer"):
            self.assertIn(token, serialized)

    def test_E002_lineage_fields_are_declared(self):
        serialized = json.dumps(self.task_by_code["E002"]).lower()
        for token in (
            "parent generation",
            "task-packet version",
            "evaluation-contract version",
            "regression-pack version",
            "promotion reason",
        ):
            self.assertIn(token, serialized)

    def test_E003_weekly_cycle_scope_is_declared(self):
        task = self.task_by_code["E003"]
        self.assertIn("runtime/**", task["allowed_paths"])
        serialized = json.dumps(task).lower()
        for token in ("task selection", "baseline", "candidate", "teacher review", "regression gate", "curriculum update"):
            self.assertIn(token, serialized)

    def test_E004_second_role_activation_gate_stays_closed(self):
        serialized = json.dumps(self.task_by_code["E004"]).lower()
        for token in (
            "20-task seed set",
            "private-holdout promotion gating",
            "stability and regression gates",
            "3 promoted generations",
        ):
            self.assertIn(token, serialized)

    def test_doc_and_readme_index_the_seed_curriculum(self):
        doc_text = DOC.read_text()
        readme_text = README.read_text()
        self.assertIn("public seed-task registry", doc_text.lower())
        self.assertIn("tests/test_frontend_product_engineer_seed_registry.py", doc_text)
        self.assertIn("docs/frontend-product-engineer-seed-curriculum.md", readme_text)


if __name__ == "__main__":
    unittest.main()
