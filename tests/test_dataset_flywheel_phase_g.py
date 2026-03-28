import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUCKETS = ROOT / "data" / "episode-registry" / "source-buckets.json"
PROMOTION_POLICY = ROOT / "data" / "episode-registry" / "promotion-policy.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "public-benchmark-pack-v1.json"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"
FPE_SEED_REGISTRY = (
    ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"
)
DOC = ROOT / "docs" / "dataset-flywheel.md"
DATASET_DOC = ROOT / "docs" / "dataset-episode-registry.md"
SPEC = ROOT / "specs" / "011-phase-g-dataset-expansion.md"


class DatasetFlywheelPhaseGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_buckets = json.loads(SOURCE_BUCKETS.read_text())
        cls.policy = json.loads(PROMOTION_POLICY.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.family_registry = json.loads(FAMILY_REGISTRY.read_text())
        cls.episode_registry = json.loads(EPISODE_REGISTRY.read_text())
        cls.seed = json.loads(SEED.read_text())
        cls.fpe_seed_registry = json.loads(FPE_SEED_REGISTRY.read_text())
        cls.buckets = {bucket["id"]: bucket for bucket in cls.source_buckets["buckets"]}
        cls.policy_buckets = {
            bucket["bucket_id"]: bucket for bucket in cls.policy["buckets"]
        }
        cls.family_by_id = {
            family["id"]: family for family in cls.family_registry["families"]
        }
        cls.policy_families = {}
        for bucket in cls.policy["buckets"]:
            for family in bucket.get("families", []):
                cls.policy_families[family["family_id"]] = family

    # G001 -----------------------------------------------------------------

    def test_G001_registry_scaffold_exists(self):
        self.assertTrue(SOURCE_BUCKETS.exists())
        self.assertEqual(self.source_buckets["meta"]["phase"], "G")
        self.assertEqual(
            set(self.source_buckets["meta"]["allowed_bucket_readiness_states"]),
            {
                "benchmark_pack_committed",
                "blocked_pending_rewrite",
                "seed_curriculum_only",
                "local_only_uncommitted",
            },
        )

    def test_G001_all_required_bucket_ids_are_present(self):
        self.assertEqual(
            set(self.buckets),
            {
                "frontend-apprentice-public-benchmark",
                "frontend-apprentice-blocked-teacher-only",
                "frontend-apprentice-local-private-holdout",
                "frontend-product-engineer-public-seed-curriculum",
                "frontend-product-engineer-local-private-holdout",
            },
        )

    def test_G001_frontend_apprentice_seed_scenarios_are_covered(self):
        seed_scenarios = {scenario["id"] for scenario in self.seed["scenarios"]}
        bucket_scenarios = set(
            self.buckets["frontend-apprentice-public-benchmark"]["seed_scenario_ids"]
        ) | set(self.buckets["frontend-apprentice-blocked-teacher-only"]["seed_scenario_ids"])
        self.assertEqual(bucket_scenarios, seed_scenarios)

    def test_G001_frontend_apprentice_bucket_counts_match_public_and_blocked_sets(self):
        public_bucket = self.buckets["frontend-apprentice-public-benchmark"]
        blocked_bucket = self.buckets["frontend-apprentice-blocked-teacher-only"]
        self.assertEqual(
            public_bucket["committed_family_count"], len(self.pack["included_family_ids"])
        )
        self.assertEqual(
            public_bucket["committed_episode_count"], self.pack["meta"]["public_episode_count"]
        )
        self.assertEqual(
            blocked_bucket["committed_family_count"], len(self.pack["blocked_family_ids"])
        )
        self.assertEqual(blocked_bucket["committed_episode_count"], 0)

    def test_G001_frontend_product_engineer_seed_bucket_is_seed_only(self):
        bucket = self.buckets["frontend-product-engineer-public-seed-curriculum"]
        self.assertEqual(bucket["readiness_state"], "seed_curriculum_only")
        self.assertIsNone(bucket["benchmark_pack_path"])
        self.assertEqual(bucket["seed_task_count"], self.fpe_seed_registry["counts"]["task_count"])
        self.assertEqual(bucket["seed_task_count"], 20)
        self.assertEqual(bucket["committed_family_count"], 0)
        self.assertEqual(bucket["committed_episode_count"], 0)

    def test_G001_local_only_buckets_are_explicitly_uncommitted(self):
        for bucket_id in (
            "frontend-apprentice-local-private-holdout",
            "frontend-product-engineer-local-private-holdout",
        ):
            bucket = self.buckets[bucket_id]
            self.assertEqual(bucket["readiness_state"], "local_only_uncommitted")
            self.assertIsNone(bucket["benchmark_pack_path"])
            self.assertEqual(bucket["committed_family_count"], 0)
            self.assertEqual(bucket["committed_episode_count"], 0)

    def test_G001_public_pack_path_maps_back_to_public_bucket(self):
        pack_paths = {
            bucket["benchmark_pack_path"]
            for bucket in self.source_buckets["buckets"]
            if bucket.get("benchmark_pack_path")
        }
        self.assertEqual(pack_paths, {"benchmarks/public-pack-v1/benchmark-pack.json"})
        self.assertEqual(
            self.buckets["frontend-apprentice-public-benchmark"]["benchmark_pack_path"],
            self.pack["meta"]["family_registry"].replace(
                "episode-family-registry.json", "benchmark-pack.json"
            ),
        )

    # G002 -----------------------------------------------------------------

    def test_G002_promotion_policy_exists_and_declares_required_keys(self):
        self.assertTrue(PROMOTION_POLICY.exists())
        self.assertEqual(self.policy["meta"]["phase"], "G")
        self.assertEqual(
            set(self.policy["required_promotion_criteria_keys"]),
            {
                "source_is_public_curriculum",
                "no_teacher_only_inputs",
                "rubric_template_exists",
                "not_repo_visible_holdout",
            },
        )

    def test_G002_every_family_registry_family_appears_once_in_policy(self):
        registry_ids = set(self.family_by_id)
        policy_ids = set(self.policy_families)
        self.assertEqual(policy_ids, registry_ids)

    def test_G002_every_candidate_family_has_complete_criteria(self):
        required = set(self.policy["required_promotion_criteria_keys"])
        for family_id, family in self.policy_families.items():
            criteria = family["promotion_criteria"]
            self.assertTrue(criteria)
            self.assertTrue(required.issubset(criteria.keys()), family_id)

    def test_G002_policy_entries_match_family_registry_readiness_and_criteria(self):
        for family_id, policy_family in self.policy_families.items():
            registry_family = self.family_by_id[family_id]
            self.assertEqual(policy_family["readiness_state"], registry_family["readiness_state"])
            self.assertEqual(policy_family["promotion_criteria"], registry_family["promotion_criteria"])

    def test_G002_benchmark_ready_families_have_all_required_criteria_true(self):
        required = self.policy["required_promotion_criteria_keys"]
        for family in self.policy_buckets["frontend-apprentice-public-benchmark"]["families"]:
            self.assertEqual(family["readiness_state"], "benchmark_ready")
            for key in required:
                self.assertTrue(family["promotion_criteria"][key], f"{family['family_id']}:{key}")

    def test_G002_blocked_families_have_false_criteria_and_rewrite_requirements(self):
        for family in self.policy_buckets["frontend-apprentice-blocked-teacher-only"]["families"]:
            self.assertEqual(family["promotion_status"], "blocked")
            self.assertEqual(family["readiness_state"], "rewrite_before_holdout_promotion")
            self.assertTrue(any(value is False for value in family["promotion_criteria"].values()))
            self.assertTrue(family.get("block_reason"))
            self.assertTrue(family.get("rewrite_requirements"))

    def test_G002_seed_only_and_local_only_buckets_do_not_invent_candidate_families(self):
        for bucket_id in (
            "frontend-apprentice-local-private-holdout",
            "frontend-product-engineer-public-seed-curriculum",
            "frontend-product-engineer-local-private-holdout",
        ):
            bucket = self.policy_buckets[bucket_id]
            self.assertEqual(bucket["candidate_family_count"], 0)
            self.assertEqual(bucket["families"], [])

    # G003 -----------------------------------------------------------------

    def test_G003_repo_visible_or_leaky_families_are_not_promoted(self):
        for family in self.policy_families.values():
            if family["repo_visible_or_leaky"]:
                self.assertNotEqual(family["promotion_status"], "promoted")
                self.assertEqual(
                    family["readiness_state"], "rewrite_before_holdout_promotion"
                )

    def test_G003_rewrite_before_holdout_promotion_families_stay_out_of_public_pack(self):
        included = set(self.pack["included_family_ids"])
        for family in self.policy_buckets["frontend-apprentice-blocked-teacher-only"]["families"]:
            self.assertNotIn(family["family_id"], included)

    def test_G003_blocked_policy_families_match_pack_blocked_family_ids(self):
        blocked_policy_ids = {
            family["family_id"]
            for family in self.policy_buckets["frontend-apprentice-blocked-teacher-only"]["families"]
        }
        self.assertEqual(blocked_policy_ids, set(self.pack["blocked_family_ids"]))

    def test_G003_local_only_holdout_buckets_remain_empty(self):
        for bucket_id in (
            "frontend-apprentice-local-private-holdout",
            "frontend-product-engineer-local-private-holdout",
        ):
            self.assertEqual(self.policy_buckets[bucket_id]["families"], [])

    # G004 -----------------------------------------------------------------

    def test_G004_pack_and_companion_registry_point_to_shared_phase_g_surfaces(self):
        self.assertEqual(
            self.pack["meta"]["source_bucket_id"],
            "frontend-apprentice-public-benchmark",
        )
        self.assertEqual(
            self.pack["meta"]["source_bucket_registry"],
            "data/episode-registry/source-buckets.json",
        )
        self.assertEqual(
            self.pack["meta"]["promotion_policy_path"],
            "data/episode-registry/promotion-policy.json",
        )
        self.assertEqual(self.pack["meta"]["role_scope"], "frontend-apprentice")
        self.assertEqual(
            self.episode_registry["meta"]["source_bucket_id"],
            self.pack["meta"]["source_bucket_id"],
        )
        self.assertEqual(
            self.episode_registry["meta"]["source_bucket_registry_path"],
            self.pack["meta"]["source_bucket_registry"],
        )
        self.assertEqual(
            self.episode_registry["meta"]["promotion_policy_path"],
            self.pack["meta"]["promotion_policy_path"],
        )
        self.assertEqual(self.episode_registry["meta"]["role_scope"], "frontend-apprentice")

    def test_G004_family_registry_policy_points_to_shared_phase_g_surfaces(self):
        policy = self.family_registry["policy"]
        self.assertEqual(
            policy["source_bucket_registry_ref"],
            "data/episode-registry/source-buckets.json",
        )
        self.assertEqual(
            policy["promotion_policy_ref"],
            "data/episode-registry/promotion-policy.json",
        )
        self.assertEqual(
            policy["candidate_bucket_ids"],
            [
                "frontend-apprentice-public-benchmark",
                "frontend-apprentice-blocked-teacher-only",
                "frontend-apprentice-local-private-holdout",
            ],
        )

    def test_G004_all_pack_families_match_pack_role_scope(self):
        pack_scope = self.pack["meta"]["role_scope"]
        for family_id in self.pack["included_family_ids"] + self.pack["blocked_family_ids"]:
            self.assertEqual(self.family_by_id[family_id]["role_scope"], pack_scope)

    def test_G004_no_frontend_product_engineer_material_is_mixed_into_public_pack(self):
        for episode in self.pack["episodes"]:
            self.assertNotIn("product-engineer", episode["family_id"])
        for family_id in self.pack["included_family_ids"] + self.pack["blocked_family_ids"]:
            self.assertNotIn("product-engineer", family_id)

    def test_G004_docs_and_spec_name_the_bounded_phase_g_state(self):
        self.assertTrue(DOC.exists())
        self.assertTrue(DATASET_DOC.exists())
        self.assertTrue(SPEC.exists())
        doc_text = DOC.read_text().lower()
        dataset_doc_text = DATASET_DOC.read_text().lower()
        spec_text = SPEC.read_text().lower()
        for token in (
            "g001",
            "g002",
            "g003",
            "g004",
            "frontend/product engineer",
            "seed_curriculum_only",
            "rewrite_before_holdout_promotion",
            "does not claim",
        ):
            self.assertIn(token, doc_text)
        for token in (
            "source-buckets.json",
            "promotion-policy.json",
            "dataset-flywheel.md",
        ):
            self.assertIn(token, dataset_doc_text)
        for token in (
            "g001",
            "g002",
            "g003",
            "g004",
            "frontend/product engineer",
            "no fpe benchmark pack is claimed",
        ):
            self.assertIn(token, spec_text)


if __name__ == "__main__":
    unittest.main()
