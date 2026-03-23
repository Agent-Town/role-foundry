"""Teacher-ops lifecycle contract tests.

Validates the machine-readable teacher workflow contract, source→promotion
linkage, task authoring template, holdout refresh receipt schema, and the
holdout_author.py tooling — all against the existing Frontend/Product Engineer
curriculum surface as single source of truth.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ── Canonical paths ──────────────────────────────────────────────
LIFECYCLE_CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-teacher-task-lifecycle.v1.json"
REFRESH_SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json"
SOURCE_RECORDS = ROOT / "data" / "curriculum" / "frontend-product-engineer-source-records.v1.json"
PROMOTION_RECORDS = ROOT / "data" / "curriculum" / "frontend-product-engineer-promotion-records.v1.json"
SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
EVAL_CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
TASK_SCHEMA = ROOT / "data" / "curriculum" / "frontend-product-engineer-task-packet.schema.v1.json"
TASK_TEMPLATE = ROOT / "seed" / "frontend-product-engineer-task-template.v1.json"
ROLE_MANIFEST = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
HOLDOUT_TEMPLATE = ROOT / "benchmarks" / "private-holdout-pack-template.json"
HOLDOUT_AUTHOR = ROOT / "scripts" / "holdout_author.py"
WORKFLOW_DOC = ROOT / "docs" / "teacher-source-curriculum-workflow.md"

EXPECTED_LIFECYCLE_STATES = [
    "draft",
    "intake_recorded",
    "promoted",
    "seed_defined",
    "executed",
    "scored",
]


class TestLifecycleContractExists(unittest.TestCase):
    def test_lifecycle_contract_file_exists(self):
        self.assertTrue(
            LIFECYCLE_CONTRACT.exists(),
            "frontend-product-engineer-teacher-task-lifecycle.v1.json missing",
        )

    def test_refresh_receipt_schema_exists(self):
        self.assertTrue(
            REFRESH_SCHEMA.exists(),
            "frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json missing",
        )


class TestLifecycleContractStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(LIFECYCLE_CONTRACT.read_text())

    def test_meta_references_frozen_role(self):
        meta = self.contract["meta"]
        self.assertEqual(meta["role_id"], "role-frontend-product-engineer")
        self.assertTrue(meta["public_repo_safe"])
        self.assertFalse(meta["teacher_only_fields_present"])

    def test_all_expected_states_present(self):
        state_ids = [s["id"] for s in self.contract["task_lifecycle_states"]]
        self.assertEqual(state_ids, EXPECTED_LIFECYCLE_STATES)

    def test_every_state_has_required_fields(self):
        for state in self.contract["task_lifecycle_states"]:
            self.assertIn("id", state)
            self.assertIn("label", state)
            self.assertIn("description", state)
            self.assertIn("entry_conditions", state)
            self.assertIn("exit_conditions", state)
            self.assertIn("artifacts", state)
            self.assertTrue(len(state["entry_conditions"]) >= 1,
                            f"state {state['id']} has no entry conditions")

    def test_transitions_reference_valid_states(self):
        valid_ids = set(EXPECTED_LIFECYCLE_STATES)
        for t in self.contract["valid_transitions"]:
            self.assertIn(t["from"], valid_ids, f"transition from unknown state: {t['from']}")
            self.assertIn(t["to"], valid_ids, f"transition to unknown state: {t['to']}")
            self.assertIn("trigger", t)

    def test_scored_can_loop_back_to_seed_defined(self):
        """Failure→curriculum loop: scored tasks go back to seed_defined."""
        transitions = self.contract["valid_transitions"]
        loop_back = [t for t in transitions if t["from"] == "scored" and t["to"] == "seed_defined"]
        self.assertEqual(len(loop_back), 1, "missing scored→seed_defined loop-back transition")

    def test_provenance_rules_block_teacher_content(self):
        blocked = self.contract["provenance_rules"]["public_tasks_must_not_contain"]
        for token in ("teacher_prompt", "scoring_rubric"):
            self.assertIn(token, blocked)

    def test_holdout_refresh_rules_reference_tracked_artifacts(self):
        rules = self.contract["holdout_refresh_rules"]
        tracked = rules["tracked_artifacts"]
        self.assertIn("data/curriculum/frontend-product-engineer-private-holdout-refresh-receipt.schema.v1.json", tracked)
        self.assertIn("scripts/holdout_author.py", tracked)

    def test_holdout_refresh_local_only_artifacts_are_not_tracked(self):
        rules = self.contract["holdout_refresh_rules"]
        for path in rules["local_only_artifacts"]:
            self.assertIn("private-holdout-pack", path)

    def test_implementation_status_is_honest(self):
        status = self.contract["implementation_status"]
        self.assertTrue(len(status["implemented"]) >= 1)
        self.assertTrue(len(status["future"]) >= 1)
        # executed and scored are marked future
        future_text = " ".join(status["future"]).lower()
        self.assertIn("executed", future_text)
        self.assertIn("scored", future_text)


class TestRefreshReceiptSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(REFRESH_SCHEMA.read_text())

    def test_schema_has_json_schema_id(self):
        self.assertIn("$schema", self.schema)
        self.assertIn("$id", self.schema)

    def test_required_fields_present(self):
        required = self.schema["required"]
        for field in ("receipt_id", "refresh_date", "role_id", "pack_version_before",
                       "pack_version_after", "actions", "audit_result", "honesty_note"):
            self.assertIn(field, required)

    def test_actions_require_counts(self):
        actions = self.schema["properties"]["actions"]
        action_required = actions["required"]
        for field in ("episodes_reviewed", "episodes_retired", "episodes_added",
                       "episodes_rewritten", "total_episodes_after"):
            self.assertIn(field, action_required)

    def test_audit_result_requires_ran_and_passed(self):
        audit = self.schema["properties"]["audit_result"]
        self.assertIn("ran_audit", audit["required"])
        self.assertIn("passed", audit["required"])

    def test_schema_does_not_contain_teacher_content_fields(self):
        serialized = json.dumps(self.schema).lower()
        for forbidden in ("teacher_prompt", "scoring_rubric", "holdout_text"):
            self.assertNotIn(forbidden, serialized)

    def test_retirement_reasons_are_enumerated(self):
        reasons_schema = (
            self.schema["properties"]["actions"]["properties"]
            ["retirement_reasons"]["items"]["properties"]["reason"]
        )
        self.assertIn("enum", reasons_schema)
        allowed = set(reasons_schema["enum"])
        self.assertIn("leaked", allowed)
        self.assertIn("stale", allowed)
        self.assertIn("replaced", allowed)


class TestSourcePromotionLinkage(unittest.TestCase):
    """Every promoted task must trace back to a source record and forward
    to the seed registry — the full provenance chain."""

    @classmethod
    def setUpClass(cls):
        cls.sources = json.loads(SOURCE_RECORDS.read_text())
        cls.promotions = json.loads(PROMOTION_RECORDS.read_text())
        cls.registry = json.loads(SEED_REGISTRY.read_text())
        cls.source_map = {s["id"]: s for s in cls.sources["source_records"]}
        cls.promo_map = {p["id"]: p for p in cls.promotions["promotion_records"]}
        cls.task_map = {t["task_id"]: t for t in cls.registry["tasks"]}

    def test_20_source_records_exist(self):
        self.assertEqual(len(self.sources["source_records"]), 20)

    def test_20_promotion_records_exist(self):
        self.assertEqual(len(self.promotions["promotion_records"]), 20)

    def test_every_promotion_points_to_real_source(self):
        for promo in self.promotions["promotion_records"]:
            src_id = promo["source_record_id"]
            self.assertIn(src_id, self.source_map,
                          f"promotion {promo['id']} references missing source {src_id}")

    def test_every_promotion_points_to_real_task(self):
        for promo in self.promotions["promotion_records"]:
            task_id = promo["task_id"]
            self.assertIn(task_id, self.task_map,
                          f"promotion {promo['id']} references missing task {task_id}")

    def test_every_seed_task_has_matching_source_and_promotion(self):
        for task in self.registry["tasks"]:
            prov = task["provenance"]
            src_id = prov["source_record_id"]
            promo_id = prov["promotion_record_id"]
            self.assertIn(src_id, self.source_map,
                          f"task {task['task_id']} references missing source {src_id}")
            self.assertIn(promo_id, self.promo_map,
                          f"task {task['task_id']} references missing promotion {promo_id}")

    def test_acceptance_test_ids_are_consistent_across_chain(self):
        for promo in self.promotions["promotion_records"]:
            src = self.source_map[promo["source_record_id"]]
            self.assertEqual(promo["acceptance_test_id"], src["acceptance_test_id"],
                             f"promotion {promo['id']} acceptance_test_id mismatch with source")

    def test_no_teacher_only_inputs_in_public_chain(self):
        for src in self.sources["source_records"]:
            self.assertFalse(src["teacher_only_inputs_used"],
                             f"source {src['id']} claims teacher-only inputs")
        for promo in self.promotions["promotion_records"]:
            self.assertFalse(promo["teacher_only_inputs_used"],
                             f"promotion {promo['id']} claims teacher-only inputs")
        for task in self.registry["tasks"]:
            self.assertFalse(task["provenance"]["teacher_only_inputs_used"],
                             f"task {task['task_id']} claims teacher-only inputs")


class TestTaskAuthoringTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads(TASK_TEMPLATE.read_text())
        cls.schema = json.loads(TASK_SCHEMA.read_text())

    def test_template_exists(self):
        self.assertTrue(TASK_TEMPLATE.exists())

    def test_template_has_all_required_schema_fields(self):
        required = self.schema.get("required", [])
        for field in required:
            self.assertIn(field, self.template,
                          f"template missing required field: {field}")

    def test_template_role_id_matches_frozen(self):
        self.assertEqual(self.template["role_id"], "role-frontend-product-engineer")

    def test_template_blocked_paths_include_defaults(self):
        blocked = self.template.get("blocked_paths", [])
        self.assertTrue(any("submission" in p for p in blocked))
        self.assertTrue(any("private-holdout-pack" in p for p in blocked))

    def test_template_rubric_ref_points_at_canonical_contract(self):
        rubric = self.template.get("rubric_ref", {})
        self.assertIn("evaluation-contract", rubric.get("contract_path", ""))


class TestHoldoutAuthorTooling(unittest.TestCase):
    def test_holdout_author_script_exists(self):
        self.assertTrue(HOLDOUT_AUTHOR.exists())

    def test_holdout_author_has_init_command(self):
        text = HOLDOUT_AUTHOR.read_text()
        self.assertIn("def cmd_init", text)

    def test_holdout_author_has_audit_command(self):
        text = HOLDOUT_AUTHOR.read_text()
        self.assertIn("def cmd_audit", text)

    def test_holdout_author_has_status_command(self):
        text = HOLDOUT_AUTHOR.read_text()
        self.assertIn("def cmd_status", text)

    def test_holdout_author_has_refresh_command(self):
        text = HOLDOUT_AUTHOR.read_text()
        self.assertIn("def cmd_refresh", text)

    def test_holdout_author_refresh_registered_in_dispatcher(self):
        text = HOLDOUT_AUTHOR.read_text()
        self.assertIn('"refresh":', text)

    def test_holdout_template_has_refresh_metadata(self):
        template = json.loads(HOLDOUT_TEMPLATE.read_text())
        self.assertIn("refresh_metadata", template)
        meta = template["refresh_metadata"]
        self.assertIn("refresh_cadence", meta)
        self.assertEqual(meta["refresh_cadence"], "weekly")
        self.assertIn("archive_policy", meta)

    def test_holdout_template_archive_policy_requires_audit(self):
        template = json.loads(HOLDOUT_TEMPLATE.read_text())
        policy = template["refresh_metadata"]["archive_policy"]
        self.assertTrue(policy["require_audit_on_refresh"])
        self.assertTrue(policy["retire_after_leak"])

    def test_holdout_author_help_runs_without_error(self):
        result = subprocess.run(
            ["python3", str(HOLDOUT_AUTHOR), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("refresh", result.stdout)


class TestWorkflowDocumentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = WORKFLOW_DOC.read_text()

    def test_doc_references_lifecycle_contract(self):
        self.assertIn("frontend-product-engineer-teacher-task-lifecycle", self.doc)

    def test_doc_references_refresh_receipt_schema(self):
        self.assertIn("frontend-product-engineer-private-holdout-refresh-receipt", self.doc)

    def test_doc_describes_lifecycle_states(self):
        for state in ("draft", "intake_recorded", "promoted", "seed_defined"):
            self.assertIn(state, self.doc,
                          f"workflow doc missing lifecycle state: {state}")

    def test_doc_describes_refresh_workflow(self):
        self.assertIn("refresh", self.doc.lower())
        self.assertIn("weekly", self.doc.lower())


if __name__ == "__main__":
    unittest.main()
