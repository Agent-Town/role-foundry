"""Tests proving the task-packet → runtime bridge consumes the versioned
contract surface correctly.

Every test in this file loads real frozen contract artifacts (role manifest,
evaluation contract, seed registry) and validates that the runtime bridge
produces correct, self-contained run objects from them.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from runner_bridge import curriculum
from runner_bridge.contract import ContractError, RunRequest
from runner_bridge.packet_runtime import (
    EvalContractRef,
    EvidenceContract,
    MutationBudget,
    PacketRunObject,
    build_run_object,
    load_all_run_objects,
    load_run_object,
)

ROOT = Path(__file__).resolve().parents[1]


class TestLoadRunObjectByAcceptanceTestId(unittest.TestCase):
    """load_run_object(acceptance_test_id) → PacketRunObject round-trip."""

    def test_load_a001_produces_valid_run_object(self):
        obj = load_run_object("A001", run_id="test-a001")
        self.assertIsInstance(obj, PacketRunObject)
        self.assertEqual(obj.acceptance_test_id, "A001")
        self.assertEqual(obj.role_id, curriculum.FROZEN_ROLE_ID)
        self.assertEqual(obj.role_name, curriculum.FROZEN_ROLE_NAME)
        self.assertEqual(obj.run_id, "test-a001")
        self.assertEqual(obj.packet_id, "fpe.seed.a001.freeze-the-first-apprentice-role")

    def test_load_c003_produces_phase_3_object(self):
        obj = load_run_object("C003", run_id="test-c003")
        self.assertEqual(obj.phase_index, 3)
        self.assertTrue(obj.phase_label, "phase_label must be non-empty")

    def test_invalid_acceptance_test_id_raises_contract_error(self):
        with self.assertRaises(ContractError):
            load_run_object("Z999")

    def test_malformed_acceptance_test_id_raises_contract_error(self):
        with self.assertRaises(ContractError):
            load_run_object("not-valid")

    def test_auto_generated_run_id_contains_test_id(self):
        obj = load_run_object("B002")
        self.assertIn("B002", obj.run_id)
        self.assertTrue(obj.run_id.startswith("pkt-"))


class TestPacketRunObjectContractFidelity(unittest.TestCase):
    """The run object faithfully carries the frozen contract surface."""

    @classmethod
    def setUpClass(cls):
        cls.obj = load_run_object("A001", run_id="fidelity-test")
        cls.packet = curriculum.load_registry_task("A001")

    def test_packet_content_hash_is_stable(self):
        obj2 = build_run_object(self.packet, run_id="fidelity-test-2")
        self.assertEqual(self.obj.packet_content_hash, obj2.packet_content_hash)
        self.assertEqual(len(self.obj.packet_content_hash), 64)

    def test_allowed_paths_match_packet(self):
        self.assertEqual(self.obj.allowed_paths, self.packet["allowed_paths"])

    def test_blocked_paths_match_packet(self):
        self.assertEqual(self.obj.blocked_paths, self.packet["blocked_paths"])

    def test_mutation_budget_matches_packet(self):
        raw = self.packet["mutation_budget"]
        self.assertEqual(self.obj.mutation_budget.tracked_files_max, raw["tracked_files_max"])
        self.assertEqual(self.obj.mutation_budget.net_lines_max, raw["net_lines_max"])

    def test_expected_checks_are_normalised(self):
        for check in self.obj.expected_checks:
            self.assertIn("id", check)
            self.assertIn("command", check)
            self.assertIn("why", check)
            self.assertTrue(check["command"].strip())

    def test_evidence_contract_matches_packet(self):
        raw = self.packet["evidence_contract"]
        self.assertEqual(
            len(self.obj.evidence_contract.required_artifacts),
            len(raw["required_artifacts"]),
        )
        self.assertEqual(
            self.obj.evidence_contract.provenance_required,
            raw["provenance_required"],
        )

    def test_objective_matches_packet(self):
        self.assertEqual(self.obj.objective, self.packet["objective"])

    def test_role_manifest_path_is_canonical(self):
        self.assertEqual(
            self.obj.role_manifest_path,
            "seed/frontend-product-engineer-role.v1.json",
        )


class TestEvalContractRef(unittest.TestCase):
    """The run object's eval_contract_ref correctly mirrors the frozen contract."""

    @classmethod
    def setUpClass(cls):
        cls.obj = load_run_object("A001", run_id="eval-ref-test")

    def test_eval_contract_path_is_canonical(self):
        self.assertEqual(
            self.obj.eval_contract_ref.contract_path,
            "data/curriculum/frontend-product-engineer-evaluation-contract.v1.json",
        )

    def test_eval_dimensions_match_frozen(self):
        self.assertEqual(self.obj.eval_contract_ref.dimensions, curriculum.FROZEN_DIMENSIONS)

    def test_eval_thresholds_match_frozen(self):
        self.assertAlmostEqual(
            self.obj.eval_contract_ref.task_pass_weighted_min,
            curriculum.TASK_PASS_THRESHOLD,
        )
        self.assertAlmostEqual(
            self.obj.eval_contract_ref.task_pass_dimension_floor,
            curriculum.TASK_MIN_DIMENSION,
        )


class TestRunObjectToRunRequest(unittest.TestCase):
    """PacketRunObject.to_run_request() produces a valid RunRequest."""

    @classmethod
    def setUpClass(cls):
        cls.obj = load_run_object("A001", run_id="req-test-a001")
        cls.request = cls.obj.to_run_request(
            workspace_snapshot={"changed_files": ["README.md"]},
            cost_budget_usd=2.0,
        )

    def test_request_is_a_run_request(self):
        self.assertIsInstance(self.request, RunRequest)

    def test_request_run_id_matches(self):
        self.assertEqual(self.request.run_id, "req-test-a001")

    def test_request_agent_role_is_student(self):
        self.assertEqual(self.request.agent_role, "student")

    def test_request_scenario_set_references_packet(self):
        self.assertEqual(self.request.scenario_set_id, "packet:A001")

    def test_request_time_budget_matches_packet(self):
        self.assertEqual(self.request.time_budget, {"minutes": 60})

    def test_request_cost_budget_matches_input(self):
        self.assertEqual(self.request.cost_budget, {"usd": 2.0})

    def test_request_workspace_snapshot_carries_objective(self):
        self.assertEqual(
            self.request.workspace_snapshot["objective"],
            self.obj.objective,
        )

    def test_request_workspace_snapshot_carries_changed_files(self):
        self.assertEqual(
            self.request.workspace_snapshot["changed_files"],
            ["README.md"],
        )

    def test_request_extras_carry_packet_runtime_block(self):
        prt = self.request.extras.get("packet_runtime")
        self.assertIsNotNone(prt)
        self.assertEqual(prt["packet_id"], self.obj.packet_id)
        self.assertEqual(prt["acceptance_test_id"], "A001")
        self.assertEqual(prt["role_id"], curriculum.FROZEN_ROLE_ID)
        self.assertEqual(prt["execution_status"], "not_started")
        self.assertEqual(prt["execution_backend"], "pending")

    def test_request_extras_carry_mutation_budget(self):
        prt = self.request.extras["packet_runtime"]
        mb = prt["mutation_budget"]
        self.assertEqual(mb["tracked_files_max"], self.obj.mutation_budget.tracked_files_max)
        self.assertEqual(mb["net_lines_max"], self.obj.mutation_budget.net_lines_max)

    def test_request_extras_carry_expected_checks(self):
        prt = self.request.extras["packet_runtime"]
        self.assertEqual(prt["expected_checks"], self.obj.expected_checks)

    def test_request_round_trips_through_dict(self):
        d = self.request.to_dict()
        restored = RunRequest.from_dict(d)
        self.assertEqual(restored.run_id, self.request.run_id)
        self.assertIn("packet_runtime", restored.extras)


class TestRunObjectToDict(unittest.TestCase):
    """PacketRunObject.to_dict() produces a JSON-serialisable dict."""

    def test_to_dict_is_json_serialisable(self):
        obj = load_run_object("A001", run_id="dict-test")
        d = obj.to_dict()
        serialised = json.dumps(d, sort_keys=True)
        restored = json.loads(serialised)
        self.assertEqual(restored["packet_id"], obj.packet_id)
        self.assertEqual(restored["role_id"], curriculum.FROZEN_ROLE_ID)
        self.assertEqual(restored["execution_status"], "not_started")


class TestLoadAllRunObjects(unittest.TestCase):
    """load_all_run_objects() covers all 20 public seed tasks."""

    @classmethod
    def setUpClass(cls):
        cls.objects = load_all_run_objects()

    def test_produces_20_run_objects(self):
        self.assertEqual(len(self.objects), 20)

    def test_all_objects_have_unique_packet_ids(self):
        ids = [obj.packet_id for obj in self.objects]
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_phases_represented(self):
        phases = {obj.phase_index for obj in self.objects}
        self.assertEqual(phases, {1, 2, 3, 4, 5})

    def test_every_object_has_frozen_role_id(self):
        for obj in self.objects:
            self.assertEqual(obj.role_id, curriculum.FROZEN_ROLE_ID)

    def test_every_object_has_eval_contract_ref(self):
        for obj in self.objects:
            self.assertEqual(
                obj.eval_contract_ref.dimensions,
                curriculum.FROZEN_DIMENSIONS,
            )

    def test_every_object_converts_to_run_request(self):
        for obj in self.objects:
            req = obj.to_run_request()
            self.assertIsInstance(req, RunRequest)
            self.assertEqual(req.run_id, obj.run_id)

    def test_every_object_has_expected_checks(self):
        for obj in self.objects:
            self.assertTrue(len(obj.expected_checks) > 0, f"{obj.acceptance_test_id} has no checks")

    def test_every_object_has_evidence_contract(self):
        for obj in self.objects:
            self.assertTrue(
                len(obj.evidence_contract.required_artifacts) > 0,
                f"{obj.acceptance_test_id} has no required artifacts",
            )


class TestBuildRunObjectFromRawPacket(unittest.TestCase):
    """build_run_object() works with arbitrary validated packet dicts."""

    def _minimal_packet(self) -> dict:
        return {
            "task_id": "test.minimal.001",
            "role_id": curriculum.FROZEN_ROLE_ID,
            "acceptance_test_id": "A001",
            "title": "Minimal test packet",
            "phase": {"id": "phase-1", "label": "Test phase", "index": 1},
            "objective": "Test objective",
            "context": {"summary": "Test context summary"},
            "success_criteria": ["It works"],
            "allowed_paths": ["app/**"],
            "blocked_paths": ["submission/**"],
            "expected_checks": [
                {"id": "check-1", "command": "echo ok", "why": "sanity"}
            ],
            "rubric_ref": {
                "contract_id": "frontend-product-engineer-evaluation-contract-v1",
                "contract_path": "data/curriculum/frontend-product-engineer-evaluation-contract.v1.json",
                "version": "1.0.0",
            },
            "time_budget_minutes": 30,
            "mutation_budget": {
                "tracked_files_max": 3,
                "net_lines_max": 100,
            },
            "evidence_contract": {
                "required_artifacts": [
                    {"path": "app/test.html", "visibility": "public", "description": "test"}
                ],
                "provenance_required": True,
                "student_visible_only": True,
            },
            "packet_version": "1.0.0",
        }

    def test_build_from_raw_packet(self):
        packet = self._minimal_packet()
        obj = build_run_object(packet, run_id="raw-test")
        self.assertEqual(obj.packet_id, "test.minimal.001")
        self.assertEqual(obj.mutation_budget.tracked_files_max, 3)
        self.assertEqual(obj.mutation_budget.net_lines_max, 100)
        self.assertEqual(obj.time_budget_minutes, 30)

    def test_invalid_packet_raises_contract_error(self):
        bad = {"task_id": "broken"}
        with self.assertRaises(ContractError):
            build_run_object(bad, run_id="bad-test")


class TestHonestyBoundaries(unittest.TestCase):
    """Run objects must not overclaim execution status."""

    def test_execution_status_is_not_started(self):
        obj = load_run_object("A001", run_id="honesty-test")
        self.assertEqual(obj.execution_status, "not_started")

    def test_execution_backend_is_pending(self):
        obj = load_run_object("A001", run_id="honesty-test")
        self.assertEqual(obj.execution_backend, "pending")

    def test_request_extras_carry_honesty_fields(self):
        obj = load_run_object("A001", run_id="honesty-test")
        req = obj.to_run_request()
        prt = req.extras["packet_runtime"]
        self.assertEqual(prt["execution_status"], "not_started")
        self.assertEqual(prt["execution_backend"], "pending")


if __name__ == "__main__":
    unittest.main()
