"""Phase G dataset-flywheel contract tests (G001-G004).

These tests encode the narrowest honest slice of the Phase G forward spec.
They verify structural invariants about the episode registry, promotion
policy, holdout safety, and role-pack separation — across BOTH the legacy
Frontend Apprentice pack and the FPE pack.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# -- Shared surfaces --
SOURCE_BUCKETS = ROOT / "data" / "episode-registry" / "source-buckets.json"
PROMOTION_POLICY = ROOT / "data" / "episode-registry" / "promotion-policy.json"
SOURCE_INTAKE = ROOT / "data" / "source-research" / "software-engineer-source-intake.v1.json"

# -- Legacy apprentice surfaces --
FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "public-benchmark-pack-v1.json"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"

# -- FPE surfaces --
FPE_FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1-fpe" / "episode-family-registry.json"
FPE_PACK = ROOT / "benchmarks" / "public-pack-v1-fpe" / "benchmark-pack.json"
FPE_EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "fpe-public-benchmark-pack-v1.json"
FPE_SEED_REGISTRY = ROOT / "data" / "curriculum" / "frontend-product-engineer-public-seed-registry.v1.json"


class DatasetFlywheelPhaseGTests(unittest.TestCase):
    """G001-G004 tests for the legacy Frontend Apprentice pack."""

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
            if bucket.get("role_id") == "role-frontend-apprentice":
                bucket_scenario_ids.update(bucket.get("scenario_ids", []))
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

    def test_G001_every_bucket_has_role_id(self):
        """Every bucket must declare a role_id for cross-pack clarity."""
        for bucket in self.source_buckets["buckets"]:
            self.assertIn(
                "role_id", bucket,
                f"Bucket {bucket['id']} missing role_id",
            )
            self.assertNotEqual(bucket["role_id"].strip(), "")

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
        policy requirement and point at the shared policy surface."""
        policy = self.family_registry["policy"]
        self.assertIn("promotion_policy", policy)
        self.assertEqual(
            policy["promotion_policy_ref"],
            "data/episode-registry/promotion-policy.json",
        )

    def test_G002_promotion_policy_surface_exists(self):
        """A standalone promotion-policy.json must exist with
        machine-readable invariants and status vocabulary."""
        self.assertTrue(PROMOTION_POLICY.exists())
        policy = json.loads(PROMOTION_POLICY.read_text())
        self.assertIn("status_vocabulary", policy)
        self.assertIn("base_promotion_criteria", policy)
        self.assertIn("invariants", policy)
        # Every base criterion documented
        base_keys = {
            "source_is_public_curriculum",
            "no_teacher_only_inputs",
            "rubric_template_exists",
            "not_repo_visible_holdout",
        }
        self.assertEqual(set(policy["base_promotion_criteria"].keys()), base_keys)

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


class FPEDatasetFlywheelPhaseGTests(unittest.TestCase):
    """G001-G004 tests for the FPE (Frontend/Product Engineer) pack."""

    @classmethod
    def setUpClass(cls):
        cls.source_buckets = json.loads(SOURCE_BUCKETS.read_text())
        cls.family_registry = json.loads(FPE_FAMILY_REGISTRY.read_text())
        cls.pack = json.loads(FPE_PACK.read_text())
        cls.episode_registry = json.loads(FPE_EPISODE_REGISTRY.read_text())
        cls.seed_registry = json.loads(FPE_SEED_REGISTRY.read_text())
        cls.families = {f["id"]: f for f in cls.family_registry["families"]}

    # ------------------------------------------------------------------
    # G001: Registry completeness for FPE
    # ------------------------------------------------------------------

    def test_G001_fpe_buckets_present(self):
        """FPE-specific buckets must exist in source-buckets.json."""
        bucket_ids = {b["id"] for b in self.source_buckets["buckets"]}
        required = {"fpe-public-training", "fpe-local-private-holdout"}
        self.assertTrue(
            required.issubset(bucket_ids),
            f"Missing FPE buckets: {required - bucket_ids}",
        )

    def test_G001_fpe_public_bucket_matches_pack(self):
        """FPE public-training bucket family count must match the pack's
        included families."""
        fpe_bucket = next(
            b for b in self.source_buckets["buckets"]
            if b["id"] == "fpe-public-training"
        )
        self.assertEqual(
            fpe_bucket["family_count"], len(self.pack["included_family_ids"])
        )
        self.assertEqual(fpe_bucket["role_id"], "role-frontend-product-engineer")

    def test_G001_fpe_all_seed_tasks_covered(self):
        """Every acceptance test in the FPE seed registry must map to the
        fpe-public-training bucket."""
        fpe_bucket = next(
            b for b in self.source_buckets["buckets"]
            if b["id"] == "fpe-public-training"
        )
        bucket_task_ids = set(fpe_bucket.get("seed_task_ids", []))
        registry_task_ids = set()
        for phase in self.seed_registry["phase_summary"]:
            registry_task_ids.update(phase["acceptance_tests"])
        self.assertEqual(bucket_task_ids, registry_task_ids)

    def test_G001_fpe_holdout_bucket_has_zero_committed(self):
        """FPE holdout bucket must have zero committed families."""
        holdout = next(
            b for b in self.source_buckets["buckets"]
            if b["id"] == "fpe-local-private-holdout"
        )
        self.assertEqual(holdout["family_count"], 0)
        self.assertEqual(holdout["status"], "local_only")

    def test_G001_fpe_completeness_by_role(self):
        """Completeness section must include FPE role data."""
        by_role = self.source_buckets["completeness"]["by_role"]
        self.assertIn("role-frontend-product-engineer", by_role)
        fpe_completeness = by_role["role-frontend-product-engineer"]
        self.assertTrue(fpe_completeness["all_seed_tasks_covered"])

    # ------------------------------------------------------------------
    # G002: Promotion policy completeness for FPE
    # ------------------------------------------------------------------

    def test_G002_every_fpe_family_has_promotion_criteria(self):
        """Every FPE family must have explicit promotion_criteria."""
        families_without = []
        for family in self.family_registry["families"]:
            if "promotion_criteria" not in family:
                families_without.append(family["id"])
        self.assertEqual(
            len(families_without), 0,
            f"FPE families lacking promotion_criteria: {families_without}",
        )

    def test_G002_fpe_benchmark_ready_all_criteria_true(self):
        """All FPE benchmark_ready families must have all base criteria true."""
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
                        f"FPE {family['id']} missing or false for {key}",
                    )

    def test_G002_fpe_promotion_policy_documented(self):
        """FPE family registry must document its promotion policy and
        point at the shared policy surface."""
        policy = self.family_registry["policy"]
        self.assertIn("promotion_policy", policy)
        self.assertEqual(
            policy["promotion_policy_ref"],
            "data/episode-registry/promotion-policy.json",
        )

    # ------------------------------------------------------------------
    # G003: Holdout promotion safety for FPE
    # ------------------------------------------------------------------

    def test_G003_fpe_no_blocked_families_in_pack(self):
        """FPE pack must have no blocked families in included list."""
        included = set(self.pack["included_family_ids"])
        for family in self.family_registry["families"]:
            if family["status"] == "blocked_pending_rewrite":
                self.assertNotIn(family["id"], included)

    def test_G003_fpe_no_repo_visible_promoted(self):
        """Any FPE family with blocked_reason must not be benchmark_ready."""
        violations = []
        for family in self.family_registry["families"]:
            if family.get("blocked_reason"):
                if family["status"] != "blocked_pending_rewrite":
                    violations.append(family["id"])
        self.assertEqual(
            len(violations), 0,
            f"FPE repo-visible families incorrectly promoted: {violations}",
        )

    # ------------------------------------------------------------------
    # G004: Role-pack separation for FPE
    # ------------------------------------------------------------------

    def test_G004_fpe_pack_has_explicit_role_scope(self):
        """FPE pack must declare an explicit role_scope."""
        self.assertIn("role_scope", self.pack["meta"])
        self.assertEqual(
            self.pack["meta"]["role_scope"], "frontend-product-engineer"
        )

    def test_G004_fpe_all_families_have_role_scope(self):
        """Every FPE family must declare a role_scope."""
        missing = []
        for family in self.family_registry["families"]:
            if "role_scope" not in family:
                missing.append(family["id"])
        self.assertEqual(len(missing), 0, f"FPE families missing role_scope: {missing}")

    def test_G004_fpe_no_mixed_roles_in_pack(self):
        """All FPE included families must share the FPE pack's role_scope."""
        pack_scope = self.pack["meta"]["role_scope"]
        mismatched = []
        for family_id in self.pack["included_family_ids"]:
            family = self.families[family_id]
            if family.get("role_scope") != pack_scope:
                mismatched.append(family_id)
        self.assertEqual(
            len(mismatched), 0,
            f"FPE families with wrong role_scope: {mismatched}",
        )

    def test_G004_fpe_episodes_match_family_role(self):
        """Every FPE episode must belong to a family matching the pack role."""
        pack_role = self.pack["meta"]["role"]
        for episode in self.pack["episodes"]:
            family = self.families.get(episode["family_id"])
            self.assertIsNotNone(
                family,
                f"FPE episode {episode['id']} references unknown family",
            )
            self.assertEqual(
                family["role"], pack_role,
                f"FPE episode {episode['id']} role mismatch",
            )


class CrossPackIsolationTests(unittest.TestCase):
    """G004 cross-pack tests: both packs must be role-isolated."""

    @classmethod
    def setUpClass(cls):
        cls.apprentice_pack = json.loads(PACK.read_text())
        cls.fpe_pack = json.loads(FPE_PACK.read_text())
        cls.apprentice_registry = json.loads(EPISODE_REGISTRY.read_text())
        cls.fpe_registry = json.loads(FPE_EPISODE_REGISTRY.read_text())
        cls.source_buckets = json.loads(SOURCE_BUCKETS.read_text())

    def test_G004_cross_pack_episode_ids_disjoint(self):
        """Episode IDs must not overlap between packs targeting different roles."""
        apprentice_eps = {ep["id"] for ep in self.apprentice_pack["episodes"]}
        fpe_eps = {ep["id"] for ep in self.fpe_pack["episodes"]}
        overlap = apprentice_eps & fpe_eps
        self.assertEqual(
            len(overlap), 0,
            f"Episode IDs overlap across packs: {overlap}",
        )

    def test_G004_cross_pack_family_ids_disjoint(self):
        """Family IDs must not overlap between packs."""
        apprentice_fams = set(self.apprentice_pack["included_family_ids"])
        fpe_fams = set(self.fpe_pack["included_family_ids"])
        overlap = apprentice_fams & fpe_fams
        self.assertEqual(
            len(overlap), 0,
            f"Family IDs overlap across packs: {overlap}",
        )

    def test_G004_cross_pack_role_scopes_differ(self):
        """The two packs must target different role_scopes."""
        self.assertNotEqual(
            self.apprentice_pack["meta"]["role_scope"],
            self.fpe_pack["meta"]["role_scope"],
        )

    def test_G004_pack_meta_links_back_to_registry_surfaces(self):
        """Both pack manifests must point at the shared source-bucket and
        promotion-policy surfaces."""
        for pack in (self.apprentice_pack, self.fpe_pack):
            self.assertEqual(
                pack["meta"]["source_bucket_registry"],
                "data/episode-registry/source-buckets.json",
            )
            self.assertEqual(
                pack["meta"]["promotion_policy_path"],
                "data/episode-registry/promotion-policy.json",
            )

    def test_G004_episode_registry_meta_links_back_to_policy(self):
        """Episode registries must link back to the shared bucket + policy surfaces."""
        for registry in (self.apprentice_registry, self.fpe_registry):
            self.assertEqual(
                registry["meta"]["source_bucket_registry"],
                "data/episode-registry/source-buckets.json",
            )
            self.assertEqual(
                registry["meta"]["promotion_policy_path"],
                "data/episode-registry/promotion-policy.json",
            )

    def test_G001_source_buckets_cover_both_roles(self):
        """Source buckets completeness must account for both roles."""
        by_role = self.source_buckets["completeness"]["by_role"]
        self.assertIn("role-frontend-apprentice", by_role)
        self.assertIn("role-frontend-product-engineer", by_role)

    def test_G001_no_bucket_serves_multiple_roles(self):
        """Each bucket must have exactly one role_id."""
        for bucket in self.source_buckets["buckets"]:
            self.assertIn("role_id", bucket)
            # role_id must be a single string, not a list
            self.assertIsInstance(bucket["role_id"], str)


class SourceIntakePhaseGTests(unittest.TestCase):
    """Phase G tests for tracked source-intake seams."""

    @classmethod
    def setUpClass(cls):
        cls.source_buckets = json.loads(SOURCE_BUCKETS.read_text())
        cls.policy = json.loads(PROMOTION_POLICY.read_text())
        cls.intake = json.loads(SOURCE_INTAKE.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.fpe_pack = json.loads(FPE_PACK.read_text())
        cls.family_registry = json.loads(FAMILY_REGISTRY.read_text())
        cls.intake_buckets = cls.source_buckets["intake_buckets"]
        cls.intake_records = {r["id"]: r for r in cls.intake["intake_records"]}

    def test_G001_intake_buckets_present(self):
        """All current intake seams must be explicitly bucketed."""
        bucket_ids = {b["id"] for b in self.intake_buckets}
        required = {
            "frontend-apprentice-source-intake-promoted",
            "frontend-apprentice-source-intake-curated",
            "frontend-apprentice-source-intake-manual-curation-only",
            "frontend-apprentice-source-intake-blocked-teacher-only",
        }
        self.assertTrue(required.issubset(bucket_ids))

    def test_G001_all_intake_records_covered_exactly_once(self):
        """Every tracked source-intake record must appear in exactly one intake bucket."""
        bucket_record_ids = []
        for bucket in self.intake_buckets:
            bucket_record_ids.extend(bucket["intake_record_ids"])
        self.assertEqual(set(bucket_record_ids), set(self.intake_records))
        self.assertEqual(len(bucket_record_ids), len(set(bucket_record_ids)))

    def test_G001_intake_completeness_metadata(self):
        """Completeness metadata must report the intake seams explicitly."""
        completeness = self.source_buckets["completeness"]
        self.assertEqual(
            completeness["total_intake_buckets"],
            len(self.intake_buckets),
        )
        apprentice = completeness["by_role"]["role-frontend-apprentice"]
        self.assertTrue(apprentice["all_intake_records_covered"])
        self.assertEqual(
            set(apprentice["intake_record_ids"]),
            set(self.intake_records),
        )

    def test_G002_intake_buckets_have_explicit_status_and_promotion_mode(self):
        """Every intake bucket must use documented status + promotion_mode values."""
        allowed_statuses = set(self.policy["source_intake_status_vocabulary"].keys())
        allowed_modes = set(self.policy["promotion_modes"].keys())
        for bucket in self.intake_buckets:
            self.assertIn(bucket["status"], allowed_statuses)
            self.assertIn(bucket["promotion_mode"], allowed_modes)
            self.assertIn("manual_curation_only", bucket)

    def test_G002_promoted_intake_maps_to_public_family(self):
        """Promoted intake seams must point at real public families and episodes."""
        promoted = next(
            b for b in self.intake_buckets
            if b["id"] == "frontend-apprentice-source-intake-promoted"
        )
        included = set(self.pack["included_family_ids"])
        family_ids = {f["id"] for f in self.family_registry["families"]}
        for family_id in promoted["promoted_family_ids"]:
            self.assertIn(family_id, included)
            self.assertIn(family_id, family_ids)
        self.assertTrue(promoted["promoted_episode_ids"])

    def test_G003_manual_curation_and_blocked_teacher_only_intake_not_publicly_promoted(self):
        """Manual-curation-only and blocked teacher-only seams must not carry public-pack refs or promoted families."""
        disallowed_modes = {"manual_curation_only", "teacher_only_manual_curation"}
        for bucket in self.intake_buckets:
            if bucket["promotion_mode"] in disallowed_modes:
                self.assertEqual(bucket["promoted_family_ids"], [])
                self.assertEqual(bucket["promoted_episode_ids"], [])
                self.assertEqual(bucket["pack_refs"], [])

    def test_G003_blocked_teacher_only_intake_blocked_for_all_public_packs(self):
        """The blocked teacher-only holdout seam must be explicitly barred from both public packs."""
        blocked = next(
            b for b in self.intake_buckets
            if b["id"] == "frontend-apprentice-source-intake-blocked-teacher-only"
        )
        self.assertEqual(blocked["status"], "blocked_teacher_only_holdout")
        self.assertTrue(blocked["manual_curation_only"])
        self.assertIn(
            "benchmarks/public-pack-v1/benchmark-pack.json",
            blocked["blocked_for"],
        )
        self.assertIn(
            "benchmarks/public-pack-v1-fpe/benchmark-pack.json",
            blocked["blocked_for"],
        )

    def test_G003_blocked_teacher_only_intake_not_in_public_pack_payloads(self):
        """Blocked teacher-only intake seams must not leak into either public pack payload."""
        for payload in (self.pack, self.fpe_pack):
            serialized = json.dumps(payload).lower()
            self.assertNotIn("swebench", serialized)
            self.assertNotIn("swe-bench", serialized)


class PromotionPolicySurfaceTests(unittest.TestCase):
    """Tests for the standalone promotion-policy.json surface."""

    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(PROMOTION_POLICY.read_text())

    def test_policy_file_exists(self):
        self.assertTrue(PROMOTION_POLICY.exists())

    def test_status_vocabulary_covers_all_statuses(self):
        """Status vocabulary must define all statuses used in family registries."""
        expected = {"benchmark_ready", "blocked_pending_rewrite", "local_only"}
        self.assertEqual(set(self.policy["status_vocabulary"].keys()), expected)

    def test_source_intake_status_vocabulary_covers_current_seams(self):
        """Source-intake status vocabulary must cover the tracked intake seams."""
        expected = {"promoted", "curated", "discovered", "blocked_teacher_only_holdout"}
        self.assertEqual(
            set(self.policy["source_intake_status_vocabulary"].keys()),
            expected,
        )

    def test_promotion_modes_cover_current_seams(self):
        """Promotion modes must cover public, candidate, manual-curation, and teacher-only seams."""
        expected = {
            "public_benchmark_family",
            "public_candidate",
            "manual_curation_only",
            "teacher_only_manual_curation",
        }
        self.assertEqual(set(self.policy["promotion_modes"].keys()), expected)

    def test_invariants_reference_test_files(self):
        """Each invariant must reference a test function."""
        for inv in self.policy["invariants"]:
            self.assertIn("test_ref", inv)
            self.assertTrue(
                inv["test_ref"].startswith("tests/"),
                f"Invariant {inv['id']} test_ref does not point to tests/",
            )

    def test_pack_refs_cover_both_packs(self):
        """Pack refs must list both the apprentice and FPE packs."""
        pack_ids = {p["pack_id"] for p in self.policy["pack_refs"]}
        self.assertIn("public-benchmark-pack-v1", pack_ids)
        self.assertIn("fpe-public-benchmark-pack-v1", pack_ids)

    def test_invariants_have_unique_ids(self):
        """All invariant IDs must be unique."""
        ids = [inv["id"] for inv in self.policy["invariants"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
