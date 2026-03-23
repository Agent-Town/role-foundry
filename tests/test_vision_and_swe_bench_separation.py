"""Tests for the vision/system overview page and SWE-bench holdout extension separation.

These tests verify:
- The vision page exists and follows the same conventions as other app pages.
- The vision page is linked in the nav of all app pages.
- The SWE-bench holdout extension doc exists and stays honest.
- The holdout extension manifest template is public-safe.
- No tracked file leaks SWE-bench-derived teacher-only content.
- The framing distinguishes framework vs current example.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
VISION_PAGE = APP_DIR / "vision.html"
EXTENSION_DOC = ROOT / "docs" / "swe-bench-holdout-extension.md"
EXTENSION_TEMPLATE = ROOT / "benchmarks" / "holdout-extension-manifest-template.json"

APP_PAGES = [
    APP_DIR / "index.html",
    APP_DIR / "scenarios.html",
    APP_DIR / "run.html",
    APP_DIR / "scorecard.html",
    APP_DIR / "vision.html",
]


class TestVisionPageExists(unittest.TestCase):
    def test_vision_html_exists(self):
        self.assertTrue(VISION_PAGE.exists())

    def test_vision_page_has_standard_head(self):
        text = VISION_PAGE.read_text()
        self.assertIn('link rel="stylesheet" href="style.css"', text)
        self.assertIn('script src="config.js"', text)
        self.assertIn('script src="data.js"', text)
        self.assertIn('script src="app.js"', text)

    def test_vision_page_has_nav(self):
        text = VISION_PAGE.read_text()
        self.assertIn("navComponent()", text)

    def test_vision_page_distinguishes_framework_and_example(self):
        text = VISION_PAGE.read_text().lower()
        self.assertIn("framework", text)
        self.assertIn("current concrete example", text)

    def test_vision_page_does_not_claim_swe_bench_public(self):
        text = VISION_PAGE.read_text().lower()
        # SWE-bench may be mentioned as teacher-only, but should not
        # be presented as public curriculum
        if "swe-bench" in text:
            self.assertIn("teacher-only", text)


class TestVisionLinkedInNav(unittest.TestCase):
    def test_all_pages_link_to_vision(self):
        for page in APP_PAGES:
            text = page.read_text()
            self.assertIn(
                "vision.html",
                text,
                f"{page.name} does not link to vision.html in its nav",
            )


class TestFramingPivot(unittest.TestCase):
    """Verify the copy pivot from 'Frontend Apprentice' to 'Software Engineer'."""

    def test_index_page_says_software_engineer(self):
        text = (APP_DIR / "index.html").read_text()
        self.assertIn("Software Engineer", text)

    def test_data_js_role_name_is_software_engineer(self):
        text = (APP_DIR / "data.js").read_text()
        self.assertIn("Software Engineer Apprentice", text)

    def test_data_js_uses_plain_ascii_quotes(self):
        text = (APP_DIR / "data.js").read_text()
        for ch in ("‘", "’", "“", "”"):
            self.assertNotIn(ch, text)

    def test_readme_mentions_framework_and_current_example(self):
        text = (ROOT / "README.md").read_text().lower()
        self.assertIn("the framework", text)
        self.assertIn("current concrete example", text)


class TestSWEBenchExtensionDoc(unittest.TestCase):
    def test_doc_exists(self):
        self.assertTrue(EXTENSION_DOC.exists())

    def test_doc_says_teacher_only(self):
        text = EXTENSION_DOC.read_text().lower()
        self.assertIn("teacher-only", text)

    def test_doc_says_small(self):
        text = EXTENSION_DOC.read_text().lower()
        self.assertIn("small", text)

    def test_doc_does_not_claim_integration(self):
        text = EXTENSION_DOC.read_text().lower()
        # Should not claim RF "uses" or "is integrated with" SWE-bench
        self.assertNotIn("swe-bench integrated", text)
        self.assertNotIn("swe-bench compatible", text)

    def test_doc_mentions_rewrite_requirement(self):
        text = EXTENSION_DOC.read_text().lower()
        self.assertIn("rewrite", text)

    def test_doc_mentions_max_episodes(self):
        text = EXTENSION_DOC.read_text()
        self.assertIn("10", text)


class TestExtensionManifestTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads(EXTENSION_TEMPLATE.read_text())

    def test_template_exists(self):
        self.assertTrue(EXTENSION_TEMPLATE.exists())

    def test_template_is_not_public_repo_safe(self):
        self.assertFalse(self.template["meta"]["public_repo_safe"])

    def test_template_visibility_is_teacher_only(self):
        self.assertEqual(self.template["meta"]["visibility"], "teacher_only")

    def test_template_rounds_are_placeholders(self):
        for item in self.template["extension_rounds"]:
            self.assertTrue(item.get("_placeholder", False))
            self.assertIn("REPLACE-ME", item.get("extension_id", ""))

    def test_template_source_policy_requires_rewrite(self):
        self.assertTrue(self.template["source_policy"]["requires_rewrite"])
        self.assertFalse(self.template["source_policy"]["verbatim_copy_allowed"])
        self.assertFalse(self.template["source_policy"]["student_visible"])
        self.assertTrue(self.template["source_policy"]["author_in_private_manifest"])

    def test_template_has_max_episodes_limit(self):
        self.assertEqual(self.template["source_policy"]["max_episodes_per_round"], 10)

    def test_template_contains_no_teacher_only_prompt_or_rubric_fields(self):
        text = EXTENSION_TEMPLATE.read_text()
        self.assertNotIn('"teacher_prompt"', text)
        self.assertNotIn('"scoring_rubric"', text)


if __name__ == "__main__":
    unittest.main()
