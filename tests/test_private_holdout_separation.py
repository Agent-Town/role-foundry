"""Tests proving public artifacts do not leak teacher-only holdout content.

These tests verify the separation contract defined in spec 012:
- No tracked git file contains teacher_prompt or scoring_rubric keys.
- The public benchmark pack contains only student_visible families.
- The private holdout path is gitignored.
- The public template contains no actual episode content.
- If a local holdout manifest exists, it conforms to the expected schema.
"""

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
PUBLIC_PACK = BENCHMARKS / "public-pack-v1" / "benchmark-pack.json"
REGISTRY = BENCHMARKS / "public-pack-v1" / "episode-family-registry.json"
TEMPLATE = BENCHMARKS / "private-holdout-pack-template.json"
PRIVATE_DIR = BENCHMARKS / "private-holdout-pack"
PRIVATE_MANIFEST = PRIVATE_DIR / "holdout-manifest.json"
GITIGNORE = ROOT / ".gitignore"
SPEC = ROOT / "specs" / "012-private-holdout-pack.md"
DOC = ROOT / "docs" / "public-benchmark-pack-v1.md"


class TestGitignoreExcludesPrivateHoldouts(unittest.TestCase):
    def test_gitignore_contains_private_holdout_entry(self):
        text = GITIGNORE.read_text()
        self.assertIn("benchmarks/private-holdout-pack/", text)

    def test_private_holdout_dir_not_tracked_by_git(self):
        """Verify git does not track any file inside the private holdout dir."""
        result = subprocess.run(
            ["git", "ls-files", "--cached", "benchmarks/private-holdout-pack/"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        tracked_files = result.stdout.strip()
        self.assertEqual(
            tracked_files,
            "",
            f"Private holdout files are tracked by git: {tracked_files}",
        )


class TestPublicArtifactsContainNoTeacherContent(unittest.TestCase):
    """Scan all tracked JSON files under benchmarks/ for teacher-only keys."""

    FORBIDDEN_KEYS = {"teacher_prompt", "scoring_rubric"}

    def _tracked_json_files(self):
        result = subprocess.run(
            ["git", "ls-files", "--cached", "benchmarks/"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        paths = result.stdout.strip().splitlines()
        return [ROOT / p for p in paths if p.endswith(".json")]

    def test_no_tracked_benchmark_json_contains_teacher_keys(self):
        for path in self._tracked_json_files():
            if path == TEMPLATE:
                continue
            text = path.read_text()
            for key in self.FORBIDDEN_KEYS:
                self.assertNotIn(
                    f'"{key}"',
                    text,
                    f"Tracked file {path.relative_to(ROOT)} contains forbidden key '{key}'",
                )

    def test_no_tracked_file_anywhere_contains_teacher_prompt_value(self):
        """Broader check: no tracked file contains what looks like actual holdout content."""
        result = subprocess.run(
            ["git", "ls-files", "--cached"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        all_tracked = result.stdout.strip().splitlines()
        json_files = [ROOT / p for p in all_tracked if p.endswith(".json")]
        for path in json_files:
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            self._assert_no_teacher_keys_recursive(data, path)

    def _assert_no_teacher_keys_recursive(self, obj, path, breadcrumb=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current = f"{breadcrumb}.{key}" if breadcrumb else key
                if key in self.FORBIDDEN_KEYS:
                    if path == TEMPLATE:
                        if key == "teacher_prompt":
                            self.assertIn(
                                "REPLACE-ME",
                                str(value),
                                f"{path.relative_to(ROOT)}:{current} has real content in template",
                            )
                        elif key == "scoring_rubric":
                            self.assertEqual(
                                value,
                                {},
                                f"{path.relative_to(ROOT)}:{current} should be an empty placeholder rubric",
                            )
                    else:
                        self.fail(
                            f"Tracked file {path.relative_to(ROOT)} has teacher key at {current}"
                        )
                self._assert_no_teacher_keys_recursive(value, path, current)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._assert_no_teacher_keys_recursive(item, path, f"{breadcrumb}[{i}]")


class TestPublicBenchmarkPackStaysPublicOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = json.loads(PUBLIC_PACK.read_text())
        cls.registry = json.loads(REGISTRY.read_text())
        cls.families = {f["id"]: f for f in cls.registry["families"]}

    def test_included_families_are_student_visible(self):
        for fid in self.pack["included_family_ids"]:
            family = self.families[fid]
            self.assertEqual(family["visibility"], "student_visible")
            self.assertEqual(family["status"], "benchmark_ready")

    def test_blocked_families_excluded_from_pack(self):
        included = set(self.pack["included_family_ids"])
        blocked = set(self.pack["blocked_family_ids"])
        self.assertTrue(included.isdisjoint(blocked))

    def test_pack_execution_policy_is_student_only(self):
        self.assertTrue(self.pack["execution_policy"]["student_visible_only"])
        self.assertFalse(self.pack["execution_policy"]["teacher_only_fields_present"])


class TestTemplateContainsNoRealContent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads(TEMPLATE.read_text())

    def test_template_exists(self):
        self.assertTrue(TEMPLATE.exists())

    def test_template_episodes_are_placeholders(self):
        for episode in self.template["episodes"]:
            self.assertTrue(
                episode.get("_placeholder", False),
                "Template episode missing _placeholder flag",
            )
            self.assertIn("REPLACE-ME", episode.get("id", ""))

    def test_template_meta_marks_not_public(self):
        self.assertFalse(self.template["meta"]["public_repo_safe"])
        self.assertEqual(self.template["meta"]["visibility"], "teacher_only")


class TestPrivateManifestSchemaIfPresent(unittest.TestCase):
    """If a local holdout manifest exists, verify it has the right shape."""

    def setUp(self):
        if not PRIVATE_MANIFEST.exists():
            self.skipTest("No local holdout manifest present (expected in CI)")
        self.manifest = json.loads(PRIVATE_MANIFEST.read_text())

    def test_meta_visibility_is_teacher_only(self):
        self.assertEqual(self.manifest["meta"]["visibility"], "teacher_only")
        self.assertFalse(self.manifest["meta"]["public_repo_safe"])

    def test_episodes_have_required_fields(self):
        required = {"id", "family_id", "title", "teacher_prompt", "scoring_rubric", "difficulty"}
        for ep in self.manifest["episodes"]:
            missing = required - set(ep.keys())
            self.assertFalse(missing, f"Episode {ep.get('id', '?')} missing: {missing}")

    def test_episodes_are_not_placeholders(self):
        for ep in self.manifest["episodes"]:
            self.assertNotIn("REPLACE-ME", ep["id"])
            self.assertNotIn("REPLACE-ME", ep["teacher_prompt"])


class TestSpecHonestyStatements(unittest.TestCase):
    def test_spec_exists(self):
        self.assertTrue(SPEC.exists())

    def test_spec_does_not_claim_sealed_certification(self):
        text = SPEC.read_text().lower().replace("**", "")
        self.assertIn("not a sealed certification exam", text)

    def test_spec_mentions_gitignore(self):
        text = SPEC.read_text().lower()
        self.assertIn("gitignore", text)

    def test_spec_mentions_teacher_only(self):
        text = SPEC.read_text()
        self.assertIn("teacher_only", text)

    def test_public_doc_mentions_local_private_holdout_path(self):
        text = DOC.read_text().lower()
        self.assertIn("benchmarks/private-holdout-pack-template.json", text)
        self.assertIn("benchmarks/private-holdout-pack/holdout-manifest.json", text)
        self.assertIn("no sealed certification claim", text)


if __name__ == "__main__":
    unittest.main()
