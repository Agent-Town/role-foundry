"""Phase G dataset-flywheel contract tests (G001-G004).

These tests encode the narrowest honest slice of the Phase G forward spec.
They verify structural invariants about the episode registry, promotion
policy, holdout safety, and role-pack separation.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BUCKETS = ROOT / "data" / "episode-registry" / "source-buckets.json"
FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "public-benchmark-pack-v1.json"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"


class DatasetFlywheelPhaseGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_buckets = json.loads(SOURCE_BUCKETS.read_text())
        cls.family_registry = json.loads(FAMILY_REGISTRY.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.episode_registry = json.loads(EPISODE_REGISTRY.read_text())
        cls.seed = json.loads(SEED.read_text())
        cls.families = {f["id"]: f for f in cls.family_registry["families"]}
        cls.seed_scenarios = {s["id"]: s for s in cls.seed["scenarios"]}

    # ------------------------------------------------------------------
    # G001: Registry completeness — all current internal buckets
    #        represented in the episode registry scaffold.
    # ------------------------------------------------------------------

    def test_G001_source_buckets_file_exists(self):
        """Source-bucket index must exist."""
        self.assertTrue(SOURCE_BUCKETS.exists())

    def test_G001_all_seed_scenarios_covered(self):
        """Every scenario in the seed must map to exactly one bucket."""
        all_scenario_ids = set(self.seed_scenarios.keys())
        bucket_scenario_ids = set()
        for bucket in self.source_buckets["buckets"]:
            bucket_scenario_ids.update(bucket["scenario_ids"])
        self.assertEqual(bucket_scenario_ids, all_scenario_ids)

    def test_G001_bucket_types_present(self):
        """At least public-training, blocked-teacher-only, and
        local-private-holdout buckets must exist."""
        bucket_ids = {b["id"] for b in self.source_buckets["buckets"]}
        required = {"public-training", "blocked-teacher-only", "local-private-holdout"}
        self.assertTrue(required.issubset(bucket_ids))

    def test_G001_public_training_bucket_matches_pack(self):
        """Public-training bucket family count must match the pack's
        included families."""
        public_bucket = next(
            b for b in self.source_buckets["buckets"] if b["id"] == "public-training"
        )
        self.assertEqual(
            public_bucket["family_count"], len(self.pack["included_family_ids"])
        )

    def test_G001_blocked_bucket_matches_registry(self):
        """Blocked-teacher-only bucket family count must match the pack's
        blocked families."""
        blocked_bucket = next(
            b for b in self.source_buckets["buckets"]
            if b["id"] == "blocked-teacher-only"
        )
        self.assertEqual(
            blocked_bucket["family_count"], len(self.pack["blocked_family_ids"])
        )

    def test_G001_local_holdout_bucket_has_zero_committed_families(self):
        """Local-private-holdout bucket must report zero committed families
        because actual holdouts are gitignored."""
        holdout_bucket = next(
            b for b in self.source_buckets["buckets"]
            if b["id"] == "local-private-holdout"
        )
        self.assertEqual(holdout_bucket["family_count"], 0)
        self.assertEqual(holdout_bucket["status"], "local_only")

    def test_G001_completeness_metadata(self):
        """Completeness block must accurately report totals."""
        completeness = self.source_buckets["completeness"]
        self.assertEqual(
            completeness["total_buckets"], len(self.source_buckets["buckets"])
        )
        self.assertTrue(completeness["all_seed_scenarios_covered"])

    # ------------------------------------------------------------------
    # G002: Promotion policy completeness — candidate families lacking
    #        promotion criteria = 0.
    # ------------------------------------------------------------------

    def test_G002_every_family_has_promotion_criteria(self):
        """Every family (benchmark_ready or blocked) must have explicit
        promotion_criteria. Zero families may lack this field."""
        families_without_criteria = []
        for family in self.family_registry["families"]:
            if "promotion_criteria" not in family:
                families_without_criteria.append(family["id"])
        self.assertEqual(
            len(families_without_criteria),
            0,
            f"Families lacking promotion_criteria: {families_without_criteria}",
        )

    def test_G002_benchmark_ready_families_have_all_criteria_true(self):
        """Benchmark-ready families must have all base promotion criteria
        satisfied (true)."""
        base_keys = {
            "source_is_public_curriculum",
            "no_teacher_only_inputs",
            "rubric_template_exists",
            "not_repo_visible_holdout",
        }
        for family in self.family_registry["families"]:
            if family["status"] == "benchmark_ready":
                criteria = family["promotion_criteria"]
                for key in base_keys:
                    self.assertTrue(
                        criteria.get(key),
                        f"{family['id']} missing or false for {key}",
                    )

    def test_G002_blocked_families_have_unmet_criteria(self):
        """Blocked families must have at least one promotion criterion
        that is false, making the block reason machine-readable."""
        for family in self.family_registry["families"]:
            if family["status"] == "blocked_pending_rewrite":
                criteria = family["promotion_criteria"]
                has_false = any(v is False for v in criteria.values())
                self.assertTrue(
                    has_false,
                    f"{family['id']} is blocked but all criteria are true",
                )

    def test_G002_promotion_policy_documented(self):
        """The family registry policy block must document the promotion
        policy requirement."""
        policy = self.family_registry["policy"]
        self.assertIn("promotion_policy", policy)

    # ------------------------------------------------------------------
    # G003: Holdout promotion safety — families promoted to teacher-only
    #        benchmark status while marked repo-visible/leaky = 0.
    # ------------------------------------------------------------------

    def test_G003_no_repo_visible_family_promoted_to_benchmark(self):
        """Any family whose blocked_reason mentions repo-visible disclosure
        must NOT have status benchmark_ready. This is the core safety
        invariant: you cannot honestly promote a leaked holdout."""
        violations = []
        for family in self.family_registry["families"]:
            if family.get("blocked_reason"):
                if family["status"] != "blocked_pending_rewrite":
                    violations.append(family["id"])
        self.assertEqual(
            len(violations),
            0,
            f"Repo-visible families incorrectly promoted: {violations}",
        )

    def test_G003_blocked_families_have_rewrite_requirements(self):
        """Every blocked family must document what rewrite is needed
        before it can ever be promoted."""
        for family in self.family_registry["families"]:
            if family["status"] == "blocked_pending_rewrite":
                self.assertIn(
                    "rewrite_requirements",
                    family,
                    f"{family['id']} blocked but missing rewrite_requirements",
                )
                self.assertGreater(len(family["rewrite_requirements"]), 0)

    def test_G003_blocked_families_not_in_pack_included(self):
        """Blocked families must not appear in the pack's included list."""
        included = set(self.pack["included_family_ids"])
        for family in self.family_registry["families"]:
            if family["status"] == "blocked_pending_rewrite":
                self.assertNotIn(
                    family["id"],
                    included,
                    f"Blocked family {family['id']} found in included_family_ids",
                )

    def test_G003_holdout_scenarios_not_in_public_episodes(self):
        """No episode in the public pack should source from holdout
        scenarios (h1, h2, h3)."""
        holdout_ids = {
            s["id"] for s in self.seed["scenarios"] if s["type"] == "holdout"
        }
        for episode in self.pack["episodes"]:
            family = self.families.get(episode["family_id"])
            if family and "source_seed_scenarios" in family:
                overlap = holdout_ids.intersection(family["source_seed_scenarios"])
                self.assertEqual(
                    len(overlap),
                    0,
                    f"Episode {episode['id']} sources from holdout: {overlap}",
                )

    # ------------------------------------------------------------------
    # G004: Role-pack separation — benchmark packs containing mixed-role
    #        episodes without explicit scoping = 0.
    # ------------------------------------------------------------------

    def test_G004_pack_has_explicit_role_scope(self):
        """The benchmark pack must declare an explicit role_scope."""
        self.assertIn("role_scope", self.pack["meta"])
        self.assertNotEqual(self.pack["meta"]["role_scope"].strip(), "")

    def test_G004_all_families_have_role_scope(self):
        """Every family must declare a role_scope field."""
        missing = []
        for family in self.family_registry["families"]:
            if "role_scope" not in family:
                missing.append(family["id"])
        self.assertEqual(
            len(missing), 0, f"Families missing role_scope: {missing}"
        )

    def test_G004_no_mixed_roles_in_pack(self):
        """All included families must share the pack's declared role_scope.
        Mixed-role packs without explicit scoping are forbidden."""
        pack_scope = self.pack["meta"]["role_scope"]
        mismatched = []
        for family_id in self.pack["included_family_ids"]:
            family = self.families[family_id]
            if family.get("role_scope") != pack_scope:
                mismatched.append(family_id)
        self.assertEqual(
            len(mismatched),
            0,
            f"Families with role_scope != pack scope '{pack_scope}': {mismatched}",
        )

    def test_G004_episodes_match_family_role(self):
        """Every episode in the pack must belong to a family whose role
        matches the pack's declared role."""
        pack_role = self.pack["meta"]["role"]
        for episode in self.pack["episodes"]:
            family = self.families.get(episode["family_id"])
            self.assertIsNotNone(
                family, f"Episode {episode['id']} references unknown family"
            )
            self.assertEqual(
                family["role"],
                pack_role,
                f"Episode {episode['id']} role mismatch: "
                f"{family['role']} != {pack_role}",
            )


if __name__ == "__main__":
    unittest.main()
