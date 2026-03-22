import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
SPEC = ROOT / "specs" / "008-public-benchmark-pack-v1.md"
DOC = ROOT / "docs" / "public-benchmark-pack-v1.md"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"


class PublicBenchmarkPackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.seed = json.loads(SEED.read_text())
        cls.families = {family["id"]: family for family in cls.registry["families"]}
        cls.seed_scenarios = {scenario["id"]: scenario for scenario in cls.seed["scenarios"]}

    def test_registry_and_pack_exist(self):
        self.assertTrue(REGISTRY.exists())
        self.assertTrue(PACK.exists())
        self.assertTrue(SPEC.exists())
        self.assertTrue(DOC.exists())

    def test_pack_contains_only_benchmark_ready_student_visible_families(self):
        for family_id in self.pack["included_family_ids"]:
            family = self.families[family_id]
            self.assertEqual(family["status"], "benchmark_ready")
            self.assertEqual(family["visibility"], "student_visible")
            for scenario_id in family["source_seed_scenarios"]:
                self.assertEqual(self.seed_scenarios[scenario_id]["type"], "training")

    def test_blocked_families_are_teacher_only_and_not_included(self):
        blocked_ids = set(self.pack["blocked_family_ids"])
        included_ids = set(self.pack["included_family_ids"])
        self.assertTrue(blocked_ids)
        self.assertTrue(blocked_ids.isdisjoint(included_ids))

        for family_id in blocked_ids:
            family = self.families[family_id]
            self.assertEqual(family["status"], "blocked_pending_rewrite")
            self.assertEqual(family["visibility"], "teacher_only")
            self.assertIn("rewrite_requirements", family)
            for scenario_id in family["source_seed_scenarios"]:
                self.assertEqual(self.seed_scenarios[scenario_id]["type"], "holdout")

    def test_pack_has_concrete_episode_volume(self):
        self.assertGreaterEqual(len(self.pack["episodes"]), 10)
        family_ids = {episode["family_id"] for episode in self.pack["episodes"]}
        self.assertEqual(family_ids, set(self.pack["included_family_ids"]))

    def test_episodes_are_student_visible_and_do_not_smuggle_teacher_only_fields(self):
        forbidden_tokens = [
            "holdout_prompt",
            "judge-only prompt",
            "grading rubric",
        ]
        for episode in self.pack["episodes"]:
            self.assertIn("student_prompt", episode)
            self.assertNotEqual(episode["student_prompt"].strip(), "")
            serialized = json.dumps(episode).lower()
            for token in forbidden_tokens:
                self.assertNotIn(token, serialized)

    def test_docs_and_spec_are_honest_about_scope(self):
        doc_text = DOC.read_text().lower()
        spec_text = SPEC.read_text().lower()
        self.assertIn("public-safe benchmark pack", doc_text)
        self.assertIn("blocked / pending rewrite", doc_text)
        self.assertIn("not a sealed certification", doc_text)
        self.assertIn("blocked_pending_rewrite", spec_text)
        self.assertIn("not a sealed certification exam", spec_text)


if __name__ == "__main__":
    unittest.main()
