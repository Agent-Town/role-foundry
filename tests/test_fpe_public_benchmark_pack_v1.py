"""Contract tests for the Frontend/Product Engineer public benchmark pack v1.

These tests mirror the Phase B acceptance checkpoints (B001–B006) from
Spec 008 but applied to the new FPE curriculum pack, plus an alpha-loop
consumability proof.
"""

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FPE_FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1-fpe" / "episode-family-registry.json"
FPE_PACK = ROOT / "benchmarks" / "public-pack-v1-fpe" / "benchmark-pack.json"
FPE_EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "fpe-public-benchmark-pack-v1.json"
FPE_SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
FPE_EVAL_CONTRACT = ROOT / "data" / "curriculum" / "frontend-product-engineer-evaluation-contract.v1.json"
FPE_ROLE_MANIFEST = ROOT / "seed" / "frontend-product-engineer-role.v1.json"
FPE_EXAMPLE_REQUEST = ROOT / "runner_bridge" / "examples" / "fpe-autoresearch-alpha-public-loop.json"

# Legacy apprentice pack — must not be broken
LEGACY_PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
LEGACY_FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"


class FPEBenchmarkPackPhaseBTests(unittest.TestCase):
    """Phase B acceptance checkpoints for the FPE public benchmark pack."""

    @classmethod
    def setUpClass(cls):
        cls.family_registry = json.loads(FPE_FAMILY_REGISTRY.read_text())
        cls.pack = json.loads(FPE_PACK.read_text())
        cls.episode_registry = json.loads(FPE_EPISODE_REGISTRY.read_text())
        cls.seed_registry = json.loads(FPE_SEED_REGISTRY.read_text())
        cls.eval_contract = json.loads(FPE_EVAL_CONTRACT.read_text())
        cls.role_manifest = json.loads(FPE_ROLE_MANIFEST.read_text())

        cls.families = {f["id"]: f for f in cls.family_registry["families"]}
        cls.pack_episodes = {ep["id"]: ep for ep in cls.pack["episodes"]}
        cls.registry_episodes = {ep["id"]: ep for ep in cls.episode_registry["episodes"]}
        cls.rubric_templates = {r["id"]: r for r in cls.episode_registry["rubric_templates"]}
        cls.seed_tasks = {t["task_id"]: t for t in cls.seed_registry["tasks"]}

    # ------------------------------------------------------------------ B001
    def test_B001_public_episode_count_at_least_8(self):
        """>= 8 public episodes across >= 3 families."""
        self.assertTrue(FPE_PACK.exists())
        self.assertTrue(FPE_EPISODE_REGISTRY.exists())
        self.assertGreaterEqual(len(self.pack_episodes), 8)
        self.assertEqual(len(self.pack_episodes), 20)
        self.assertGreaterEqual(len(self.pack["included_family_ids"]), 3)
        self.assertEqual(len(self.pack["included_family_ids"]), 5)
        self.assertEqual(
            self.episode_registry["coverage"]["public_episode_count"],
            len(self.pack_episodes),
        )
        self.assertEqual(set(self.pack_episodes), set(self.registry_episodes))

    # ------------------------------------------------------------------ B002
    def test_B002_rubric_completeness(self):
        """Every episode maps to a rubric template with complete dimensions."""
        expected_family_ids = set(self.pack["included_family_ids"])
        template_family_ids = {r["family_id"] for r in self.episode_registry["rubric_templates"]}
        self.assertEqual(template_family_ids, expected_family_ids)
        self.assertEqual(
            self.episode_registry["coverage"]["rubric_mapped_episode_count"],
            len(self.pack_episodes),
        )

        required_keys = {"id", "label", "weight", "description", "pass_signal", "fail_signal"}
        for rubric in self.episode_registry["rubric_templates"]:
            self.assertIn("title", rubric)
            self.assertIn("description", rubric)
            self.assertEqual(rubric["score_scale"], {"min": 0.0, "max": 1.0})
            self.assertGreaterEqual(len(rubric["dimensions"]), 3)
            for dim in rubric["dimensions"]:
                self.assertTrue(required_keys.issubset(dim.keys()))
                self.assertNotEqual(dim["description"].strip(), "")
                self.assertNotEqual(dim["pass_signal"].strip(), "")
                self.assertNotEqual(dim["fail_signal"].strip(), "")

        for ep_id, pack_ep in self.pack_episodes.items():
            reg_ep = self.registry_episodes[ep_id]
            self.assertEqual(reg_ep["family_id"], pack_ep["family_id"])
            self.assertIn(reg_ep["rubric_template_id"], self.rubric_templates)
            self.assertEqual(
                self.rubric_templates[reg_ep["rubric_template_id"]]["family_id"],
                pack_ep["family_id"],
            )

    # ------------------------------------------------------------------ B003
    def test_B003_weight_normalization(self):
        """Each rubric template sums to 1.0."""
        for rubric in self.episode_registry["rubric_templates"]:
            total = sum(d["weight"] for d in rubric["dimensions"])
            self.assertTrue(
                math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9),
                f"Rubric {rubric['id']} weights sum to {total}, not 1.0",
            )
            for dim in rubric["dimensions"]:
                self.assertGreater(dim["weight"], 0.0)
                self.assertLessEqual(dim["weight"], 1.0)

    def test_B003_dimensions_match_evaluation_contract(self):
        """Rubric dimensions match the frozen evaluation contract exactly."""
        contract_dim_ids = [d["id"] for d in self.eval_contract["dimensions"]]
        contract_weights = {d["id"]: d["weight"] for d in self.eval_contract["dimensions"]}
        for rubric in self.episode_registry["rubric_templates"]:
            rubric_dim_ids = [d["id"] for d in rubric["dimensions"]]
            self.assertEqual(rubric_dim_ids, contract_dim_ids)
            for dim in rubric["dimensions"]:
                self.assertAlmostEqual(dim["weight"], contract_weights[dim["id"]])

    # ------------------------------------------------------------------ B004
    def test_B004_public_teacher_split_integrity(self):
        """All included families are benchmark_ready + student_visible. No blocked families."""
        included_ids = set(self.pack["included_family_ids"])
        blocked_ids = set(self.pack["blocked_family_ids"])
        self.assertTrue(included_ids)
        self.assertEqual(blocked_ids, set())
        self.assertTrue(blocked_ids.isdisjoint(included_ids))

        for fam_id in included_ids:
            fam = self.families[fam_id]
            self.assertEqual(fam["status"], "benchmark_ready")
            self.assertEqual(fam["visibility"], "student_visible")

        # No teacher-only tokens in episodes
        forbidden_tokens = ["teacher_prompt", "judge-only prompt", "grading rubric"]
        for ep in self.pack["episodes"]:
            serialized = json.dumps(ep).lower()
            for token in forbidden_tokens:
                self.assertNotIn(token, serialized)

    # ------------------------------------------------------------------ B005
    def test_B005_provenance_coverage(self):
        """Every episode has provenance back to Spec 014."""
        self.assertEqual(
            self.episode_registry["coverage"]["provenance_mapped_episode_count"],
            len(self.pack_episodes),
        )
        self.assertTrue(self.episode_registry["meta"]["student_visible_only"])
        self.assertFalse(self.episode_registry["meta"]["teacher_only_fields_present"])

        for ep_id, reg_ep in self.registry_episodes.items():
            self.assertIn(ep_id, self.pack_episodes)
            prov = reg_ep["provenance"]
            self.assertFalse(prov["teacher_only_inputs_used"])
            self.assertTrue(prov["source_seed_scenarios"])
            self.assertEqual(
                len(prov["source_seed_scenarios"]),
                len(prov["source_seed_titles"]),
            )
            self.assertTrue(prov["public_spec_refs"])
            self.assertTrue(prov["public_doc_refs"])
            for ref in prov["public_spec_refs"]:
                self.assertTrue(ref.startswith("specs/"))
            for ref in prov["public_doc_refs"]:
                self.assertTrue(ref.startswith("docs/"))

    # ------------------------------------------------------------------ B006
    def test_B006_promotion_readiness_clarity(self):
        readiness = self.pack["promotion_readiness"]
        self.assertEqual(readiness["phase"], "B")
        self.assertEqual(readiness["status"], "pass")
        self.assertIn("public-safe", readiness["summary"].lower())
        self.assertIn("public autoresearch loops", readiness["ready_for"])
        self.assertIn("sealed certification", readiness["blocked_for"])
        self.assertEqual(
            set(readiness["metrics"].keys()),
            {"B001", "B002", "B003", "B004", "B005", "B006"},
        )

    # ------------------------------------------------------------------ Honesty
    def test_pack_honesty_fields(self):
        """The pack is explicit about what it is and is not."""
        self.assertTrue(self.pack["execution_policy"]["student_visible_only"])
        self.assertFalse(self.pack["execution_policy"]["teacher_only_fields_present"])
        self.assertIn("not a sealed certification", self.pack["meta"]["honesty_note"].lower())

    def test_all_episodes_trace_to_seed_registry(self):
        """Every pack episode corresponds to a task in the seed registry."""
        for ep_id in self.pack_episodes:
            self.assertIn(ep_id, self.seed_tasks, f"{ep_id} not in seed registry")

    # --------------------------------------------------------- Readiness honesty
    def test_every_family_has_readiness_fields(self):
        """Every family must declare machine-readable readiness dimensions."""
        required_keys = {"benchmark_pack", "runtime_status", "alpha_consumable", "blocked_claims", "evidence"}
        valid_runtime = {"complete", "partial", "not_started"}
        for fam_id, fam in self.families.items():
            self.assertIn("readiness", fam, f"{fam_id} missing readiness block")
            r = fam["readiness"]
            self.assertTrue(required_keys.issubset(r.keys()), f"{fam_id} readiness missing keys: {required_keys - set(r.keys())}")
            self.assertIsInstance(r["benchmark_pack"], bool)
            self.assertTrue(r["benchmark_pack"], f"{fam_id} is in the pack but benchmark_pack is False")
            self.assertIn(r["runtime_status"], valid_runtime, f"{fam_id} has invalid runtime_status: {r['runtime_status']}")
            self.assertIsInstance(r["alpha_consumable"], bool)
            self.assertIsInstance(r["blocked_claims"], list)
            self.assertIsInstance(r["evidence"], str)
            self.assertGreater(len(r["evidence"]), 0, f"{fam_id} readiness evidence is empty")

    def test_readiness_aligns_to_curriculum_operating_split(self):
        """Readiness values must match the honest status from curriculum-operating-split.md."""
        expected = {
            "rf.fpe.public.phase-1": "complete",
            "rf.fpe.public.phase-2": "not_started",
            "rf.fpe.public.phase-3": "partial",
            "rf.fpe.public.phase-4": "not_started",
            "rf.fpe.public.phase-5": "not_started",
        }
        for fam_id, expected_status in expected.items():
            actual = self.families[fam_id]["readiness"]["runtime_status"]
            self.assertEqual(
                actual, expected_status,
                f"{fam_id}: runtime_status is '{actual}', expected '{expected_status}' per curriculum-operating-split.md"
            )

    def test_pack_meta_has_readiness_by_phase(self):
        """benchmark-pack.json must carry a readiness_by_phase summary."""
        self.assertIn("readiness_by_phase", self.pack["meta"])
        rbp = self.pack["meta"]["readiness_by_phase"]
        self.assertEqual(len(rbp), 5)
        for phase_key, phase_r in rbp.items():
            self.assertTrue(phase_r["benchmark_pack"])
            self.assertIn(phase_r["runtime_status"], {"complete", "partial", "not_started"})

    def test_no_runtime_complete_overclaim(self):
        """Phases 2, 4, 5 must NOT claim runtime_status 'complete'."""
        no_complete_phases = {"rf.fpe.public.phase-2", "rf.fpe.public.phase-4", "rf.fpe.public.phase-5"}
        for fam_id in no_complete_phases:
            self.assertNotEqual(
                self.families[fam_id]["readiness"]["runtime_status"], "complete",
                f"{fam_id} overclaims runtime complete — contradicts curriculum-operating-split.md"
            )

    def test_blocked_claims_non_empty_for_incomplete_phases(self):
        """Families with runtime not complete must declare at least one blocked claim."""
        for fam_id, fam in self.families.items():
            r = fam["readiness"]
            if r["runtime_status"] != "complete":
                self.assertGreater(
                    len(r["blocked_claims"]), 0,
                    f"{fam_id} has runtime_status={r['runtime_status']} but no blocked_claims — must be explicit about what is missing"
                )

    def test_promotion_readiness_blocked_for_includes_runtime(self):
        """promotion_readiness.blocked_for must mention runtime-incomplete phases."""
        blocked = self.pack["promotion_readiness"]["blocked_for"]
        blocked_joined = " ".join(blocked).lower()
        self.assertTrue(
            "runtime" in blocked_joined or "phases" in blocked_joined,
            f"promotion_readiness.blocked_for should mention runtime-incomplete phases: {blocked}"
        )

    def test_honesty_note_mentions_runtime_distinction(self):
        """The pack honesty_note must mention that benchmark_ready != runtime live."""
        note = self.pack["meta"]["honesty_note"].lower()
        self.assertTrue(
            "runtime" in note,
            "honesty_note must mention runtime readiness distinction"
        )

    def test_role_consistency(self):
        """Pack, family registry, and role manifest agree on role identity."""
        self.assertEqual(self.pack["meta"]["role"], "Frontend/Product Engineer")
        self.assertEqual(self.pack["meta"]["role_scope"], "frontend-product-engineer")
        self.assertEqual(self.role_manifest["role"]["id"], "role-frontend-product-engineer")
        for fam in self.families.values():
            self.assertEqual(fam["role"], "Frontend/Product Engineer")
            self.assertEqual(fam["role_scope"], "frontend-product-engineer")


class FPEAlphaLoopConsumabilityTests(unittest.TestCase):
    """Prove that runner_bridge.autoresearch_alpha can consume the FPE pack immediately."""

    def test_example_request_exists_and_is_valid(self):
        self.assertTrue(FPE_EXAMPLE_REQUEST.exists())
        payload = json.loads(FPE_EXAMPLE_REQUEST.read_text())
        self.assertIn("public_benchmark_pack", payload)
        self.assertIn("family_registry", payload)
        self.assertIn("stages", payload)
        for stage_key in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
            self.assertIn(stage_key, payload["stages"])
            self.assertIn("request", payload["stages"][stage_key])

    def test_fpe_alpha_loop_executes_end_to_end(self):
        """The alpha loop runs to completion with the FPE pack and produces a valid receipt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "runner_bridge.autoresearch_alpha",
                    "--request",
                    str(FPE_EXAMPLE_REQUEST),
                    "--artifacts-root",
                    str(artifacts_root),
                ],
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            receipt_path = artifacts_root / "autoresearch-alpha.json"
            self.assertTrue(receipt_path.exists())

            receipt = json.loads(receipt_path.read_text())
            self.assertTrue(receipt["ok"])
            self.assertEqual(receipt["flow"], "autoresearch-alpha")
            self.assertEqual(receipt["dataset_manifest_id"], "fpe-public-benchmark-pack-v1")
            self.assertEqual(receipt["verdict"], "better")

            # Integrity gate
            ig = receipt["integrity_gate"]
            self.assertEqual(ig["status"], "pass")
            self.assertEqual(ig["mode"], "public_regression")
            self.assertTrue(ig["public_regression_ok"])
            self.assertFalse(ig["sealed_eval_claim_ok"])
            self.assertFalse(ig["certification_claim_ok"])

            # All stages completed
            for stage_key in ("baseline-eval", "candidate-student", "candidate-teacher-eval"):
                self.assertEqual(
                    receipt["stages"][stage_key]["status"],
                    "completed",
                    f"{stage_key} did not complete",
                )

            # Candidate student has repo_task_pack from the FPE pack
            student_bundle = receipt["stages"]["candidate-student"]["export"]["artifact_bundle"]
            self.assertIn("student_view", student_bundle)
            rtp = student_bundle["student_view"]["repo_task_pack"]
            self.assertEqual(rtp["role_scope"], "frontend-product-engineer")
            self.assertEqual(rtp["dataset_id"], "fpe-public-benchmark-pack-v1")
            self.assertGreater(rtp["episode_count"], 0)

            # Comparison receipt
            comparison = receipt["comparison"]
            self.assertTrue(comparison["complete"])
            self.assertEqual(comparison["verdict"], "better")
            self.assertGreater(comparison["total_score_delta"], 0)


class LegacyPackNotBrokenTests(unittest.TestCase):
    """Ensure the legacy apprentice benchmark pack is not broken by the new FPE pack."""

    def test_legacy_pack_still_loads(self):
        self.assertTrue(LEGACY_PACK.exists())
        pack = json.loads(LEGACY_PACK.read_text())
        self.assertEqual(pack["meta"]["id"], "public-benchmark-pack-v1")
        self.assertEqual(len(pack["episodes"]), 14)

    def test_legacy_family_registry_still_loads(self):
        self.assertTrue(LEGACY_FAMILY_REGISTRY.exists())
        reg = json.loads(LEGACY_FAMILY_REGISTRY.read_text())
        self.assertEqual(len([f for f in reg["families"] if f["status"] == "benchmark_ready"]), 7)

    def test_legacy_and_fpe_packs_are_independent(self):
        legacy = json.loads(LEGACY_PACK.read_text())
        fpe = json.loads(FPE_PACK.read_text())
        self.assertNotEqual(legacy["meta"]["id"], fpe["meta"]["id"])
        legacy_eps = {ep["id"] for ep in legacy["episodes"]}
        fpe_eps = {ep["id"] for ep in fpe["episodes"]}
        self.assertTrue(legacy_eps.isdisjoint(fpe_eps))


if __name__ == "__main__":
    unittest.main()
