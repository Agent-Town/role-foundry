"""
Submission proof contract tests — Spec 007.

These tests lock the claims made in the submission checklist and docs.
They ensure the conversation log, milestone status, and submission
checklist stay honest and current as the repo evolves.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CONV_LOG = DOCS / "conversation-log.md"
MILESTONES = DOCS / "milestones.md"
CHECKLIST = DOCS / "submission-proof-checklist.md"
README = ROOT / "README.md"


class ConversationLogTests(unittest.TestCase):
    """The conversation log must reflect the real build story."""

    @classmethod
    def setUpClass(cls):
        cls.text = CONV_LOG.read_text()

    def test_conversation_log_exists(self):
        self.assertTrue(CONV_LOG.exists())

    def test_conversation_log_covers_landed_milestones(self):
        """Every landed milestone must have a corresponding log entry."""
        self.assertIn("Direction lock", self.text)
        self.assertIn("Architecture lock", self.text)
        self.assertIn("Milestones 1 and 2 landed", self.text)
        self.assertIn("Milestone 3 landed", self.text)
        self.assertIn("Milestone 4 landed", self.text)
        self.assertIn("Milestone 5 landed", self.text)

    def test_conversation_log_does_not_claim_unshipped_milestones(self):
        """M6 should not appear as a landed entry."""
        self.assertNotIn("Milestone 6 landed", self.text)

    def test_conversation_log_mentions_honest_stubs(self):
        """The log should acknowledge what is NOT wired."""
        self.assertIn("NOT claimed", self.text)


class MilestoneStatusTests(unittest.TestCase):
    """Milestone status must match what is actually committed."""

    @classmethod
    def setUpClass(cls):
        cls.text = MILESTONES.read_text()

    def test_milestone_status_honesty(self):
        """M1-M4 done, M5-M6 queued."""
        # Extract status lines after each milestone heading
        blocks = re.split(r"## Milestone \d", self.text)
        statuses = {}
        for block in blocks[1:]:
            match = re.search(r"\*\*Status:\*\*\s*(\w+)", block)
            if match:
                # Get milestone number from the block
                num_match = re.search(r"Milestone (\d)", "## Milestone " + block[:5])
                # Fallback: count position
                statuses[len(statuses) + 1] = match.group(1)

        # Re-parse more carefully
        statuses = {}
        for m in re.finditer(
            r"## Milestone (\d).*?\n\n\*\*Status:\*\*\s*(\w+)", self.text, re.DOTALL
        ):
            statuses[int(m.group(1))] = m.group(2)

        for m in (1, 2, 3, 4, 5):
            self.assertEqual(
                statuses.get(m),
                "done",
                f"Milestone {m} should be marked done",
            )
        for m in (6,):
            self.assertEqual(
                statuses.get(m),
                "queued",
                f"Milestone {m} should be marked queued",
            )


class SubmissionChecklistTests(unittest.TestCase):
    """The submission checklist must exist and cover key areas."""

    @classmethod
    def setUpClass(cls):
        cls.text = CHECKLIST.read_text()

    def test_checklist_exists(self):
        self.assertTrue(CHECKLIST.exists())

    def test_checklist_covers_demo(self):
        self.assertIn("docker compose up", self.text)

    def test_checklist_covers_runner_bridge(self):
        self.assertIn("Runner bridge", self.text)

    def test_checklist_covers_honesty_section(self):
        self.assertIn("NOT claimed", self.text)

    def test_checklist_has_judge_workflow(self):
        self.assertIn("Quick judge workflow", self.text)


class ReadmeSubmissionTests(unittest.TestCase):
    """README must support honest judge inspection."""

    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text()

    def test_readme_lists_what_is_stubbed(self):
        self.assertIn("still stubbed", self.text.lower())

    def test_readme_does_not_claim_live_ui_reads_clawith(self):
        """The web UI does not consume live state yet — README must not claim it does."""
        self.assertIn("web app still serves demo data", self.text.lower())

    def test_readme_links_conversation_log(self):
        self.assertIn("conversation-log.md", self.text)

    def test_readme_links_submission_checklist(self):
        self.assertIn("submission-proof-checklist.md", self.text)
        self.assertIn("Judge inspection path", self.text)


if __name__ == "__main__":
    unittest.main()
