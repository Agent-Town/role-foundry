import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs" / "014-frontend-product-engineer-20-task-curriculum.md"
README = ROOT / "README.md"

EXPECTED_PHASES = [
    "## Phase 1 — Freeze the game being played",
    "## Phase 2 — Build the teacher operating system",
    "## Phase 3 — Make the coding loop real",
    "## Phase 4 — Make evaluation trustworthy",
    "## Phase 5 — Make the system compound",
]

EXPECTED_TESTS = [
    ("A001", "Freeze the first apprentice role"),
    ("A002", "Freeze the evaluation contract"),
    ("A003", "Freeze the mutation surface"),
    ("A004", "Freeze the canonical task packet"),
    ("B001", "Build task authoring from a template"),
    ("B002", "Build source-intake -> curriculum promotion workflow"),
    ("B003", "Author the first 20-task seed set"),
    ("B004", "Add weekly holdout refresh"),
    ("C001", "Standardize isolated execution"),
    ("C002", "Wire baseline run as a first-class object"),
    ("C003", "Wire candidate run with real code/test execution"),
    ("C004", "Capture full receipts automatically"),
    ("D001", "Build the teacher review console"),
    ("D002", "Require private-holdout scoring for promotion"),
    ("D003", "Add repeated-run stability checks"),
    ("D004", "Add regression gates"),
    ("E001", "Turn failures into next-step curriculum"),
    ("E002", "Track generation lineage"),
    ("E003", "Run a real weekly training cycle"),
    ("E004", "Only then expand to a second role"),
]

REQUIRED_FIELDS = [
    "Goal",
    "Metric",
    "Pass threshold",
    "Evidence",
    "Failure interpretation",
]


class FrontendProductEngineerCurriculumSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec_text = SPEC.read_text()
        cls.readme_text = README.read_text()

    def test_spec_exists(self):
        self.assertTrue(SPEC.exists())

    def test_spec_has_all_phase_headings(self):
        for heading in EXPECTED_PHASES:
            self.assertIn(heading, self.spec_text)

    def test_spec_has_exactly_20_acceptance_tests_with_expected_titles(self):
        found = re.findall(r"^### ([A-E]\d{3}) — (.+)$", self.spec_text, flags=re.MULTILINE)
        self.assertEqual(found, EXPECTED_TESTS)
        self.assertEqual(len(found), 20)

    def test_each_acceptance_test_has_required_fields(self):
        matches = list(re.finditer(r"^### ([A-E]\d{3}) — .+$", self.spec_text, flags=re.MULTILINE))
        self.assertEqual(len(matches), 20)

        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(self.spec_text)
            section = self.spec_text[start:end]
            for field in REQUIRED_FIELDS:
                self.assertRegex(
                    section,
                    rf"(?m)^- {re.escape(field)}:",
                    msg=f"{match.group(1)} missing field: {field}",
                )

    def test_spec_is_tdd_first_and_metric_first(self):
        self.assertIn("Start with a failing automated check", self.spec_text)
        self.assertIn("No task is done on prose alone", self.spec_text)
        self.assertIn("Task pass threshold", self.spec_text)
        self.assertIn("Promotion gate threshold", self.spec_text)

    def test_spec_freezes_scoring_contract_and_mutation_budget(self):
        for token in (
            "Task outcome",
            "Regression safety",
            "Mutation discipline",
            "Evidence quality",
            "Honesty / boundary discipline",
            "<= 6 tracked files",
            "<= 400 net changed lines",
        ):
            self.assertIn(token, self.spec_text)

    def test_spec_stays_scoped(self):
        lower = self.spec_text.lower()
        self.assertIn("out of scope", lower)
        self.assertIn("partner integrations", lower)
        self.assertIn("wallet or chain work", lower)
        self.assertIn("unrelated infra", lower)

    def test_readme_lists_the_new_spec(self):
        self.assertIn(
            "specs/014-frontend-product-engineer-20-task-curriculum.md",
            self.readme_text,
        )


if __name__ == "__main__":
    unittest.main()
