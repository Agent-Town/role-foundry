import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "public-benchmark-pack-v1.json"
SPEC = ROOT / "specs" / "008-public-benchmark-pack-v1.md"
DOC = ROOT / "docs" / "public-benchmark-pack-v1.md"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"


class PublicBenchmarkPackPhaseBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family_registry = json.loads(FAMILY_REGISTRY.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.episode_registry = json.loads(EPISODE_REGISTRY.read_text())
        cls.seed = json.loads(SEED.read_text())
        cls.families = {family["id"]: family for family in cls.family_registry["families"]}
        cls.pack_episodes = {episode["id"]: episode for episode in cls.pack["episodes"]}
        cls.registry_episodes = {
            episode["id"]: episode for episode in cls.episode_registry["episodes"]
        }
        cls.rubric_templates = {
            rubric["id"]: rubric for rubric in cls.episode_registry["rubric_templates"]
        }
        cls.seed_scenarios = {scenario["id"]: scenario for scenario in cls.seed["scenarios"]}

    def test_B001_public_episode_count(self):
        self.assertTrue(PACK.exists())
        self.assertTrue(EPISODE_REGISTRY.exists())
        self.assertEqual(
            self.pack["meta"]["episode_registry"],
            "data/episode-registry/public-benchmark-pack-v1.json",
        )
        minimum = self.pack["promotion_readiness"]["metrics"]["B001"][
            "minimum_episode_count"
        ]
        self.assertGreaterEqual(len(self.pack_episodes), minimum)
        self.assertEqual(len(self.pack_episodes), 12)
        self.assertEqual(
            self.episode_registry["coverage"]["public_episode_count"],
            len(self.pack_episodes),
        )
        self.assertEqual(set(self.pack_episodes), set(self.registry_episodes))

    def test_B002_rubric_completeness(self):
        expected_family_ids = set(self.pack["included_family_ids"])
        template_family_ids = {
            rubric["family_id"] for rubric in self.episode_registry["rubric_templates"]
        }
        self.assertEqual(template_family_ids, expected_family_ids)
        self.assertEqual(
            self.episode_registry["coverage"]["rubric_mapped_episode_count"],
            len(self.pack_episodes),
        )

        required_dimension_keys = {
            "id",
            "label",
            "weight",
            "description",
            "pass_signal",
            "fail_signal",
        }
        for rubric in self.episode_registry["rubric_templates"]:
            self.assertIn("title", rubric)
            self.assertIn("description", rubric)
            self.assertEqual(rubric["score_scale"], {"min": 0.0, "max": 1.0})
            self.assertGreaterEqual(len(rubric["dimensions"]), 3)
            for dimension in rubric["dimensions"]:
                self.assertTrue(required_dimension_keys.issubset(dimension.keys()))
                self.assertNotEqual(dimension["description"].strip(), "")
                self.assertNotEqual(dimension["pass_signal"].strip(), "")
                self.assertNotEqual(dimension["fail_signal"].strip(), "")

        for episode_id, pack_episode in self.pack_episodes.items():
            registry_episode = self.registry_episodes[episode_id]
            self.assertEqual(registry_episode["family_id"], pack_episode["family_id"])
            self.assertIn(registry_episode["rubric_template_id"], self.rubric_templates)
            self.assertEqual(
                self.rubric_templates[registry_episode["rubric_template_id"]]["family_id"],
                pack_episode["family_id"],
            )

    def test_B003_weight_normalization(self):
        self.assertEqual(
            self.pack["promotion_readiness"]["metrics"]["B003"][
                "normalized_template_count"
            ],
            len(self.rubric_templates),
        )
        for rubric in self.episode_registry["rubric_templates"]:
            total = sum(dimension["weight"] for dimension in rubric["dimensions"])
            self.assertTrue(
                math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9),
                f"Rubric {rubric['id']} weights sum to {total}, not 1.0",
            )
            for dimension in rubric["dimensions"]:
                self.assertGreater(dimension["weight"], 0.0)
                self.assertLessEqual(dimension["weight"], 1.0)

    def test_B004_public_teacher_split_integrity(self):
        blocked_ids = set(self.pack["blocked_family_ids"])
        included_ids = set(self.pack["included_family_ids"])
        self.assertTrue(blocked_ids)
        self.assertTrue(blocked_ids.isdisjoint(included_ids))

        for family_id in included_ids:
            family = self.families[family_id]
            self.assertEqual(family["status"], "benchmark_ready")
            self.assertEqual(family["visibility"], "student_visible")
            for scenario_id in family["source_seed_scenarios"]:
                self.assertEqual(self.seed_scenarios[scenario_id]["type"], "training")

        for family_id in blocked_ids:
            family = self.families[family_id]
            self.assertEqual(family["status"], "blocked_pending_rewrite")
            self.assertEqual(family["visibility"], "teacher_only")
            self.assertIn("rewrite_requirements", family)
            for scenario_id in family["source_seed_scenarios"]:
                self.assertEqual(self.seed_scenarios[scenario_id]["type"], "holdout")

        forbidden_tokens = ["teacher_prompt", "judge-only prompt", "grading rubric"]
        for episode in self.pack["episodes"]:
            serialized = json.dumps(episode).lower()
            for token in forbidden_tokens:
                self.assertNotIn(token, serialized)

    def test_B005_provenance_coverage(self):
        self.assertEqual(
            self.episode_registry["coverage"]["provenance_mapped_episode_count"],
            len(self.pack_episodes),
        )
        self.assertTrue(self.episode_registry["meta"]["student_visible_only"])
        self.assertFalse(self.episode_registry["meta"]["teacher_only_fields_present"])

        for episode_id, registry_episode in self.registry_episodes.items():
            self.assertIn(episode_id, self.pack_episodes)
            provenance = registry_episode["provenance"]
            self.assertFalse(provenance["teacher_only_inputs_used"])
            self.assertTrue(provenance["source_seed_scenarios"])
            self.assertEqual(
                len(provenance["source_seed_scenarios"]),
                len(provenance["source_seed_titles"]),
            )
            self.assertTrue(provenance["public_spec_refs"])
            self.assertTrue(provenance["public_doc_refs"])
            for ref in provenance["public_spec_refs"]:
                self.assertTrue(ref.startswith("specs/"))
            for ref in provenance["public_doc_refs"]:
                self.assertTrue(ref.startswith("docs/"))
            for scenario_id in provenance["source_seed_scenarios"]:
                self.assertEqual(self.seed_scenarios[scenario_id]["type"], "training")

    def test_B006_promotion_readiness_clarity(self):
        self.assertTrue(SPEC.exists())
        self.assertTrue(DOC.exists())
        readiness = self.pack["promotion_readiness"]
        self.assertEqual(readiness["phase"], "B")
        self.assertEqual(readiness["status"], "pass")
        self.assertIn("public-safe benchmark pack", readiness["summary"].lower())
        self.assertIn("public autoresearch loops", readiness["ready_for"])
        self.assertIn("sealed certification", readiness["blocked_for"])
        self.assertEqual(
            set(readiness["metrics"].keys()),
            {"B001", "B002", "B003", "B004", "B005", "B006"},
        )

        doc_text = DOC.read_text().lower().replace("**", "")
        spec_text = SPEC.read_text().lower().replace("**", "")
        for metric in ("b001", "b002", "b003", "b004", "b005", "b006"):
            self.assertIn(metric, doc_text)
            self.assertIn(metric, spec_text)
        self.assertIn("phase b acceptance", doc_text)
        self.assertIn("phase b acceptance", spec_text)
        self.assertIn("not a sealed certification", doc_text)
        self.assertIn("not a sealed certification exam", spec_text)
        self.assertIn("ready to promote", doc_text)
        self.assertIn("named limits", doc_text)


if __name__ == "__main__":
    unittest.main()
