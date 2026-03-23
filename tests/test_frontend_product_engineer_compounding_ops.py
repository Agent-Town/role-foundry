import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
LINEAGE_SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-generation-lineage.schema.v1.json"
LINEAGE_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-generation-lineage-registry.v1.json"
CYCLE_SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-weekly-training-cycle.schema.v1.json"
CYCLE_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-weekly-cycle-registry.v1.json"
SAMPLE_CYCLE = ROOT / "data" / "curriculum" / "frontend-product-engineer-sample-weekly-cycle-receipt.v1.json"
DOC = ROOT / "docs" / "frontend-product-engineer-compounding-ops.md"
SEED_DOC = ROOT / "docs" / "frontend-product-engineer-seed-curriculum.md"
OPERATING_SPLIT_DOC = ROOT / "docs" / "curriculum-operating-split.md"
README = ROOT / "README.md"


class FrontendProductEngineerCompoundingOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role = json.loads(ROLE.read_text())
        cls.contract = json.loads(CONTRACT.read_text())
        cls.seed = json.loads(SEED_REGISTRY.read_text())
        cls.lineage_schema = json.loads(LINEAGE_SCHEMA.read_text())
        cls.lineage = json.loads(LINEAGE_REGISTRY.read_text())
        cls.cycle_schema = json.loads(CYCLE_SCHEMA.read_text())
        cls.cycle_registry = json.loads(CYCLE_REGISTRY.read_text())
        cls.sample_cycle = json.loads(SAMPLE_CYCLE.read_text())
        cls.task_ids = {task["task_id"] for task in cls.seed["tasks"]}

    def test_files_exist(self):
        for path in (
            ROLE,
            CONTRACT,
            SEED_REGISTRY,
            LINEAGE_SCHEMA,
            LINEAGE_REGISTRY,
            CYCLE_SCHEMA,
            CYCLE_REGISTRY,
            SAMPLE_CYCLE,
            DOC,
        ):
            self.assertTrue(path.exists(), f"missing {path}")

    def test_docs_and_readme_index_phase5_contracts(self):
        readme_text = README.read_text()
        seed_doc_text = SEED_DOC.read_text()
        split_doc_text = OPERATING_SPLIT_DOC.read_text()
        self.assertIn("docs/frontend-product-engineer-compounding-ops.md", readme_text)
        self.assertIn("frontend-product-engineer-generation-lineage-registry.v1.json", seed_doc_text)
        self.assertIn("frontend-product-engineer-sample-weekly-cycle-receipt.v1.json", seed_doc_text)
        self.assertIn("tests/test_frontend_product_engineer_compounding_ops.py", seed_doc_text)
        self.assertIn("frontend-product-engineer-weekly-cycle-registry.v1.json", split_doc_text)
        self.assertIn("runtime not yet live", split_doc_text.lower())

    def test_lineage_registry_ties_back_to_frozen_contracts(self):
        meta = self.lineage["meta"]
        schema_required = set(self.lineage_schema["required"])
        self.assertEqual(schema_required, {"meta", "generation_roots", "promoted_generations"})
        self.assertEqual(meta["role_id"], self.role["role"]["id"])
        self.assertEqual(meta["evaluation_contract_path"], CONTRACT.relative_to(ROOT).as_posix())
        self.assertEqual(meta["seed_registry_path"], SEED_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(meta["cycle_registry_path"], CYCLE_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(meta["sample_cycle_receipt_path"], SAMPLE_CYCLE.relative_to(ROOT).as_posix())
        self.assertFalse(meta["teacher_only_fields_present"])
        self.assertEqual(meta["live_promoted_generation_count"], 0)
        self.assertEqual(meta["sample_promoted_generation_count"], 3)

    def test_promoted_generation_records_are_complete_and_honest(self):
        roots = {root["generation_id"] for root in self.lineage["generation_roots"]}
        seen_generation_ids = set(roots)
        promoted = self.lineage["promoted_generations"]
        self.assertEqual(len(promoted), 3)
        for index, record in enumerate(promoted, start=1):
            self.assertTrue(record["example_only"])
            self.assertFalse(record["live_promotion_claimed"])
            self.assertEqual(record["role_id"], self.role["role"]["id"])
            self.assertEqual(record["promotion_sequence_index"], index)
            self.assertIn(record["parent_generation_id"], seen_generation_ids)
            seen_generation_ids.add(record["generation_id"])
            self.assertEqual(record["task_packet"]["packet_version"], self.seed["meta"]["version"])
            self.assertIn(record["task_packet"]["task_id"], self.task_ids)
            self.assertEqual(record["evaluation_contract"]["id"], self.contract["meta"]["id"])
            self.assertEqual(record["evaluation_contract"]["version"], self.contract["meta"]["version"])
            self.assertEqual(record["evaluation_contract"]["path"], CONTRACT.relative_to(ROOT).as_posix())
            self.assertEqual(record["regression_pack"]["source_receipt_path"], SAMPLE_CYCLE.relative_to(ROOT).as_posix())
            self.assertEqual(record["teacher_review"]["scorecard_path"], "data/curriculum/frontend-product-engineer-sample-scorecard.v1.json")
            self.assertFalse(record["promotion_decision"]["eligible_for_live_ops_claim"])
            self.assertEqual(record["promotion_decision"]["private_holdout_gate_status"], "manual_local_not_tracked")
            self.assertIn(record["curriculum_link"]["linked_task_id"], self.task_ids)
            self.assertEqual(record["artifact_refs"]["cycle_receipt_path"], SAMPLE_CYCLE.relative_to(ROOT).as_posix())
            self.assertEqual(record["artifact_refs"]["cycle_registry_path"], CYCLE_REGISTRY.relative_to(ROOT).as_posix())
            self.assertEqual(record["artifact_refs"]["ops_doc_path"], DOC.relative_to(ROOT).as_posix())

    def test_weekly_cycle_registry_stays_sample_only(self):
        meta = self.cycle_registry["meta"]
        cycle = self.cycle_registry["cycles"][0]
        self.assertEqual(meta["schema_path"], CYCLE_SCHEMA.relative_to(ROOT).as_posix())
        self.assertEqual(meta["sample_cycle_receipt_path"], SAMPLE_CYCLE.relative_to(ROOT).as_posix())
        self.assertEqual(meta["lineage_registry_path"], LINEAGE_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(meta["sample_cycle_count"], 1)
        self.assertEqual(meta["live_cycle_count"], 0)
        self.assertEqual(cycle["receipt_path"], SAMPLE_CYCLE.relative_to(ROOT).as_posix())
        self.assertTrue(cycle["example_only"])
        self.assertFalse(cycle["live_cycle_claimed"])

    def test_sample_cycle_receipt_links_end_to_end_cycle_fields(self):
        cycle = self.sample_cycle
        selected_tasks = cycle["task_selection"]["selected_tasks"]
        selected_task_ids = {task["task_id"] for task in selected_tasks}
        promoted_generation_ids = {
            record["generation_id"] for record in self.lineage["promoted_generations"]
        }

        self.assertEqual(set(self.cycle_schema["required"]), {
            "meta",
            "task_selection",
            "baseline_run",
            "candidate_run",
            "teacher_review",
            "promotion_decision",
            "regression_gate",
            "curriculum_update",
            "private_holdout_boundary",
            "honesty_notes",
        })
        self.assertTrue(cycle["meta"]["example_only"])
        self.assertFalse(cycle["meta"]["live_cycle_claimed"])
        self.assertEqual(cycle["meta"]["schema_path"], CYCLE_SCHEMA.relative_to(ROOT).as_posix())
        self.assertEqual(cycle["meta"]["seed_registry_path"], SEED_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(cycle["meta"]["evaluation_contract_path"], CONTRACT.relative_to(ROOT).as_posix())
        self.assertEqual(cycle["meta"]["lineage_registry_path"], LINEAGE_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(cycle["meta"]["future_live_receipt_root"], "runtime/training-cycles/YYYY-Www/")
        self.assertEqual(selected_task_ids, {
            "fpe.seed.e001.turn-failures-into-next-step-curriculum",
            "fpe.seed.e002.track-generation-lineage",
            "fpe.seed.e003.run-a-real-weekly-training-cycle",
        })
        self.assertTrue(selected_task_ids.issubset(self.task_ids))
        self.assertEqual(cycle["baseline_run"]["task_packet_version"], self.seed["meta"]["version"])
        self.assertEqual(cycle["baseline_run"]["evaluation_contract_version"], self.contract["meta"]["version"])
        self.assertEqual(cycle["candidate_run"]["task_packet_version"], self.seed["meta"]["version"])
        self.assertEqual(cycle["candidate_run"]["evaluation_contract_version"], self.contract["meta"]["version"])
        self.assertIn(LINEAGE_REGISTRY.relative_to(ROOT).as_posix(), cycle["candidate_run"]["changed_files"])
        self.assertIn(CYCLE_REGISTRY.relative_to(ROOT).as_posix(), cycle["candidate_run"]["changed_files"])
        self.assertEqual(cycle["teacher_review"]["scorecard_path"], "data/curriculum/frontend-product-engineer-sample-scorecard.v1.json")
        self.assertEqual(
            set(cycle["promotion_decision"]["promoted_generation_ids"]),
            promoted_generation_ids,
        )
        self.assertFalse(cycle["promotion_decision"]["eligible_for_live_ops_claim"])
        self.assertEqual(cycle["regression_gate"]["pack"]["source_seed_registry_path"], SEED_REGISTRY.relative_to(ROOT).as_posix())
        self.assertEqual(set(cycle["regression_gate"]["pack"]["task_ids"]), selected_task_ids)
        self.assertEqual(cycle["regression_gate"]["critical_regressions"], 0)
        self.assertEqual(cycle["regression_gate"]["overall_pass_rate"], 1.0)
        self.assertFalse(cycle["private_holdout_boundary"]["teacher_only_content_tracked"])
        self.assertFalse(cycle["private_holdout_boundary"]["tracked_manifest_in_git"])

    def test_failure_to_curriculum_linkage_is_machine_readable(self):
        failure_actions = {
            action["failure_id"]: action
            for action in self.sample_cycle["curriculum_update"]["failure_actions"]
        }
        self.assertEqual(
            set(failure_actions),
            {
                "failure.failure-to-curriculum-linkage-gap",
                "failure.lineage-machine-readable-gap",
                "failure.weekly-cycle-receipt-gap",
            },
        )
        self.assertEqual(
            failure_actions["failure.failure-to-curriculum-linkage-gap"]["linked_task_id"],
            "fpe.seed.e001.turn-failures-into-next-step-curriculum",
        )
        self.assertEqual(
            failure_actions["failure.lineage-machine-readable-gap"]["linked_task_id"],
            "fpe.seed.e002.track-generation-lineage",
        )
        self.assertEqual(
            failure_actions["failure.weekly-cycle-receipt-gap"]["linked_task_id"],
            "fpe.seed.e003.run-a-real-weekly-training-cycle",
        )
        self.assertTrue(self.sample_cycle["curriculum_update"]["public_safe"])

    def test_honesty_boundaries_are_explicit(self):
        serialized = "\n".join(
            path.read_text().lower()
            for path in (
                LINEAGE_REGISTRY,
                CYCLE_REGISTRY,
                SAMPLE_CYCLE,
                DOC,
                OPERATING_SPLIT_DOC,
            )
        )
        for token in ("teacher_prompt", "scoring_rubric", "sealed certification", "tamper-proof"):
            self.assertNotIn(token, serialized)
        self.assertIn("not a claim that live weekly ops already ran", DOC.read_text().lower())
        self.assertIn("live_cycle_count", CYCLE_REGISTRY.read_text().lower())
        self.assertIn("manual/local", DOC.read_text().lower())
        self.assertIn("runtime/training-cycles/yyyy-www/", DOC.read_text().lower())


if __name__ == "__main__":
    unittest.main()
