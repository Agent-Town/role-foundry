import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_INTAKE = ROOT / "data" / "source-research" / "software-engineer-source-intake.v1.json"
WORKFLOW_DOC = ROOT / "docs" / "teacher-source-curriculum-workflow.md"
FAMILY_REGISTRY = ROOT / "benchmarks" / "public-pack-v1" / "episode-family-registry.json"
PACK = ROOT / "benchmarks" / "public-pack-v1" / "benchmark-pack.json"
EPISODE_REGISTRY = ROOT / "data" / "episode-registry" / "public-benchmark-pack-v1.json"
SEED = ROOT / "seed" / "role-foundry-apprentice.json"
DATA_JS = ROOT / "app" / "data.js"


class TeacherSourceCurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intake = json.loads(SOURCE_INTAKE.read_text())
        cls.registry = json.loads(FAMILY_REGISTRY.read_text())
        cls.pack = json.loads(PACK.read_text())
        cls.episode_registry = json.loads(EPISODE_REGISTRY.read_text())
        cls.seed = json.loads(SEED.read_text())
        cls.intake_records = {r["id"]: r for r in cls.intake["intake_records"]}

    def test_source_intake_has_required_fields(self):
        required_keys = {
            "id", "source_id", "source_name", "source_url", "license",
            "manual_curation_only", "status", "discovered_by", "provenance",
        }
        for record in self.intake["intake_records"]:
            self.assertTrue(
                required_keys.issubset(record.keys()),
                f"Record {record.get('id')} missing keys: {required_keys - set(record.keys())}",
            )

    def test_source_intake_has_at_least_four_records(self):
        self.assertGreaterEqual(len(self.intake["intake_records"]), 4)

    def test_promoted_source_has_family_and_episodes(self):
        promoted = [r for r in self.intake["intake_records"] if r["status"] == "promoted"]
        self.assertGreaterEqual(len(promoted), 1, "At least one source must be promoted")
        for record in promoted:
            self.assertIsNotNone(record["promoted_family_id"])
            self.assertTrue(len(record["promoted_episode_ids"]) > 0)
            self.assertIn(
                record["promoted_family_id"],
                self.pack["included_family_ids"],
            )

    def test_playwright_family_in_pack_and_registry(self):
        playwright_family = "rf.frontend-apprentice.public.playwright-regression"
        self.assertIn(playwright_family, self.pack["included_family_ids"])

        families = {f["id"]: f for f in self.registry["families"]}
        self.assertIn(playwright_family, families)
        family = families[playwright_family]
        self.assertEqual(family["status"], "benchmark_ready")
        self.assertEqual(family["visibility"], "student_visible")
        self.assertIn("source_backed_by", family)
        self.assertEqual(family["source_backed_by"]["source_license"], "Apache-2.0")

    def test_playwright_episodes_have_provenance(self):
        episodes = {e["id"]: e for e in self.episode_registry["episodes"]}
        for eid in ("pbpv1-e13", "pbpv1-e14"):
            self.assertIn(eid, episodes)
            ep = episodes[eid]
            self.assertEqual(
                ep["family_id"],
                "rf.frontend-apprentice.public.playwright-regression",
            )
            self.assertIn("source_backed_by", ep["provenance"])
            self.assertEqual(
                ep["provenance"]["source_backed_by"]["source_license"],
                "Apache-2.0",
            )
            self.assertFalse(ep["provenance"]["teacher_only_inputs_used"])

    def test_playwright_rubric_exists(self):
        rubrics = {r["id"]: r for r in self.episode_registry["rubric_templates"]}
        self.assertIn("pbpv1-rubric-playwright-regression-v1", rubrics)
        rubric = rubrics["pbpv1-rubric-playwright-regression-v1"]
        self.assertEqual(
            rubric["family_id"],
            "rf.frontend-apprentice.public.playwright-regression",
        )
        total_weight = sum(d["weight"] for d in rubric["dimensions"])
        self.assertAlmostEqual(total_weight, 1.0, places=9)

    def test_google_eng_practices_promoted(self):
        """Google Eng Practices intake must be promoted with family and episodes."""
        google = self.intake_records.get("intake-google-eng-practices")
        self.assertIsNotNone(google, "Google Eng Practices intake record must exist")
        self.assertEqual(google["status"], "promoted")
        self.assertFalse(google["manual_curation_only"])
        self.assertFalse(google["provenance"]["teacher_only_inputs_used"])
        self.assertEqual(
            google["promoted_family_id"],
            "rf.frontend-apprentice.public.code-review-discipline",
        )
        self.assertEqual(len(google["promoted_episode_ids"]), 2)
        self.assertIn(
            google["promoted_family_id"],
            self.pack["included_family_ids"],
        )

    def test_google_family_in_pack_and_registry(self):
        """Google-backed family must be in pack and registry with source_backed_by."""
        google_family = "rf.frontend-apprentice.public.code-review-discipline"
        self.assertIn(google_family, self.pack["included_family_ids"])

        families = {f["id"]: f for f in self.registry["families"]}
        self.assertIn(google_family, families)
        family = families[google_family]
        self.assertEqual(family["status"], "benchmark_ready")
        self.assertEqual(family["visibility"], "student_visible")
        self.assertIn("source_backed_by", family)
        self.assertEqual(family["source_backed_by"]["source_license"], "CC BY 3.0")
        self.assertTrue(family["source_backed_by"]["rf_authored"])

    def test_google_episodes_have_provenance(self):
        """Google-backed episodes must have proper provenance."""
        episodes = {e["id"]: e for e in self.episode_registry["episodes"]}
        for eid in ("pbpv1-e15", "pbpv1-e16"):
            self.assertIn(eid, episodes)
            ep = episodes[eid]
            self.assertEqual(
                ep["family_id"],
                "rf.frontend-apprentice.public.code-review-discipline",
            )
            self.assertIn("source_backed_by", ep["provenance"])
            self.assertEqual(
                ep["provenance"]["source_backed_by"]["source_license"],
                "CC BY 3.0",
            )
            self.assertFalse(ep["provenance"]["teacher_only_inputs_used"])

    def test_google_rubric_exists(self):
        """Google-backed family must have a complete rubric template."""
        rubrics = {r["id"]: r for r in self.episode_registry["rubric_templates"]}
        self.assertIn("pbpv1-rubric-code-review-discipline-v1", rubrics)
        rubric = rubrics["pbpv1-rubric-code-review-discipline-v1"]
        self.assertEqual(
            rubric["family_id"],
            "rf.frontend-apprentice.public.code-review-discipline",
        )
        total_weight = sum(d["weight"] for d in rubric["dimensions"])
        self.assertAlmostEqual(total_weight, 1.0, places=9)

    def test_alpine_promoted_from_manual_curation_only_docs_lane(self):
        """Alpine intake should be promoted, but stay explicitly manual-curation-only."""
        alpine = self.intake_records.get("intake-alpinejs-curation")
        self.assertIsNotNone(alpine, "Alpine intake record must exist")
        self.assertEqual(alpine["status"], "promoted")
        self.assertTrue(alpine["manual_curation_only"])
        self.assertFalse(alpine["provenance"]["teacher_only_inputs_used"])
        self.assertEqual(
            alpine["promoted_family_id"],
            "rf.frontend-apprentice.public.alpine-state-patterns",
        )
        self.assertEqual(alpine["promoted_episode_ids"], ["pbpv1-e17", "pbpv1-e18"])
        self.assertIn("allowed_source_material", alpine)
        self.assertIn("excluded_source_material", alpine)

    def test_alpine_family_in_pack_and_registry(self):
        alpine_family = "rf.frontend-apprentice.public.alpine-state-patterns"
        self.assertIn(alpine_family, self.pack["included_family_ids"])

        families = {f["id"]: f for f in self.registry["families"]}
        self.assertIn(alpine_family, families)
        family = families[alpine_family]
        self.assertEqual(family["status"], "benchmark_ready")
        self.assertEqual(family["visibility"], "student_visible")
        self.assertEqual(family["source_seed_scenarios"], ["t9"])
        self.assertIn("source_backed_by", family)
        self.assertEqual(family["source_backed_by"]["source_license"], "MIT")
        self.assertTrue(family["source_backed_by"]["rf_authored"])

    def test_alpine_episodes_have_provenance(self):
        episodes = {e["id"]: e for e in self.episode_registry["episodes"]}
        for eid in ("pbpv1-e17", "pbpv1-e18"):
            self.assertIn(eid, episodes)
            ep = episodes[eid]
            self.assertEqual(
                ep["family_id"],
                "rf.frontend-apprentice.public.alpine-state-patterns",
            )
            self.assertIn("source_backed_by", ep["provenance"])
            self.assertEqual(
                ep["provenance"]["source_backed_by"]["source_license"],
                "MIT",
            )
            self.assertFalse(ep["provenance"]["teacher_only_inputs_used"])

    def test_alpine_rubric_exists(self):
        rubrics = {r["id"]: r for r in self.episode_registry["rubric_templates"]}
        self.assertIn("pbpv1-rubric-alpine-state-patterns-v1", rubrics)
        rubric = rubrics["pbpv1-rubric-alpine-state-patterns-v1"]
        self.assertEqual(
            rubric["family_id"],
            "rf.frontend-apprentice.public.alpine-state-patterns",
        )
        total_weight = sum(d["weight"] for d in rubric["dimensions"])
        self.assertAlmostEqual(total_weight, 1.0, places=9)

    def test_swebench_record_is_blocked_teacher_only(self):
        swebench = self.intake_records.get("intake-swebench-teacher-holdout")
        self.assertIsNotNone(swebench, "SWE-bench intake record must exist")
        self.assertEqual(swebench["status"], "blocked_teacher_only_holdout")
        self.assertTrue(swebench["manual_curation_only"])
        self.assertTrue(swebench["provenance"]["teacher_only_inputs_used"])
        self.assertIsNone(swebench["promoted_family_id"])
        self.assertEqual(len(swebench["promoted_episode_ids"]), 0)
        self.assertIn("teacher_only_holdout_direction", swebench)
        self.assertIn("never public curriculum", swebench["teacher_only_holdout_direction"]["scope"])

    def test_swebench_not_in_public_pack(self):
        for family_id in self.pack["included_family_ids"]:
            self.assertNotIn("swebench", family_id.lower())
            self.assertNotIn("swe-bench", family_id.lower())
        for episode in self.pack["episodes"]:
            serialized = json.dumps(episode).lower()
            self.assertNotIn("swebench", serialized)
            self.assertNotIn("swe-bench", serialized)

    def test_swebench_not_in_demo_data(self):
        data_js_text = DATA_JS.read_text()
        # The teacher_source_intake section mentions SWE-bench for teacher display,
        # but it must be marked teacher_only and must not appear in scenarios array.
        # Check that no scenario has swebench content
        self.assertNotIn("swebench", data_js_text.lower().split("teacher_source_intake")[0])

    def test_workflow_doc_exists_and_has_key_content(self):
        self.assertTrue(WORKFLOW_DOC.exists())
        text = WORKFLOW_DOC.read_text().lower()
        self.assertIn("discover", text)
        self.assertIn("curate", text)
        self.assertIn("promote", text)
        self.assertIn("swe-bench", text)
        self.assertIn("teacher-only", text)
        self.assertIn("manual curation", text)
        self.assertIn("any teacher", text)

    def test_seed_has_t7_scenario(self):
        scenario_ids = {s["id"] for s in self.seed["scenarios"]}
        self.assertIn("t7", scenario_ids)
        t7 = next(s for s in self.seed["scenarios"] if s["id"] == "t7")
        self.assertEqual(t7["type"], "training")

    def test_seed_has_t8_scenario(self):
        scenario_ids = {s["id"] for s in self.seed["scenarios"]}
        self.assertIn("t8", scenario_ids)
        t8 = next(s for s in self.seed["scenarios"] if s["id"] == "t8")
        self.assertEqual(t8["type"], "training")

    def test_seed_has_t9_scenario(self):
        scenario_ids = {s["id"] for s in self.seed["scenarios"]}
        self.assertIn("t9", scenario_ids)
        t9 = next(s for s in self.seed["scenarios"] if s["id"] == "t9")
        self.assertEqual(t9["type"], "training")

    def test_episode_registry_coverage_consistent(self):
        coverage = self.episode_registry["coverage"]
        episodes = self.episode_registry["episodes"]
        rubrics = self.episode_registry["rubric_templates"]
        self.assertEqual(coverage["public_episode_count"], len(episodes))
        self.assertEqual(coverage["rubric_template_count"], len(rubrics))
        self.assertEqual(coverage["rubric_mapped_episode_count"], len(episodes))
        self.assertEqual(coverage["provenance_mapped_episode_count"], len(episodes))


if __name__ == "__main__":
    unittest.main()
