"""Private-holdout separation boundary tests.

These tests assert that:
1. The tracked template exists and is valid JSON with no teacher-only content.
2. The spec and authoring doc exist and are aligned with the template.
3. No tracked file in the relevant directories contains teacher-only prompt or rubric text.
4. The local/ directory is .gitignore'd.
5. The template schema is internally consistent.
6. Public and private family ID namespaces do not overlap.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "benchmarks" / "private-holdout-pack-template.json"
SPEC = ROOT / "specs" / "012-private-holdout-pack.md"
DOC = ROOT / "docs" / "private-holdout-authoring.md"
GITIGNORE = ROOT / ".gitignore"
PUBLIC_PACK_DIR = ROOT / "benchmarks" / "public-pack-v1"
BENCHMARKS_DIR = ROOT / "benchmarks"
SEED_CURRICULUM_DOC = ROOT / "docs" / "frontend-product-engineer-seed-curriculum.md"
README = ROOT / "README.md"
RUNNER_BRIDGE_DOC = ROOT / "docs" / "runner-bridge.md"

FORBIDDEN_TOKENS = [
    "teacher_prompt",
    "holdout_prompt",
    "scoring_rubric",
    "judge-only prompt",
    "grading rubric",
    "private rubric text",
    "sealed prompt text",
]


class TestTemplateExists(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = json.loads(TEMPLATE.read_text())

    def test_template_file_exists(self):
        self.assertTrue(TEMPLATE.exists())

    def test_template_is_valid_json(self):
        self.assertIn("meta", self.template)
        self.assertIn("schema", self.template)
        self.assertIn("constraints", self.template)
        self.assertIn("separation_contract", self.template)

    def test_template_meta_references_spec_and_doc(self):
        meta = self.template["meta"]
        self.assertEqual(meta["spec"], "specs/012-private-holdout-pack.md")
        self.assertEqual(meta["doc"], "docs/private-holdout-authoring.md")

    def test_template_declares_local_only(self):
        constraints = self.template["constraints"]
        self.assertTrue(constraints["local_only"])
        self.assertFalse(constraints["tracked_by_git"])
        self.assertEqual(constraints["visibility_must_be"], "teacher_only")
        self.assertTrue(constraints["teacher_only_must_be"])
        self.assertFalse(constraints["student_visible_must_be"])

    def test_template_schema_declares_required_fields(self):
        schema = self.template["schema"]
        self.assertTrue(schema["required_top_level_fields"])
        self.assertTrue(schema["meta_required_fields"])
        self.assertTrue(schema["holdout_family_required_fields"])
        self.assertTrue(schema["holdout_episode_required_fields"])
        self.assertIn("visibility", schema["holdout_family_required_fields"])
        self.assertIn("teacher_only", schema["holdout_episode_required_fields"])

    def test_template_separation_contract_is_consistent(self):
        contract = self.template["separation_contract"]
        self.assertEqual(contract["overlap_policy"], "zero_overlap")
        self.assertEqual(contract["public_pack_path"], "benchmarks/public-pack-v1/")
        self.assertEqual(contract["private_pack_local_path"], "local/private-holdout-packs/")
        self.assertTrue(contract["evaluation_contract_shared"])
        self.assertIn("public", contract["family_id_namespace"])
        self.assertIn("private", contract["family_id_namespace"])


class TestNoTeacherContentInTrackedFiles(unittest.TestCase):
    """Assert that no tracked file in sensitive directories contains teacher-only content."""

    def _scan_files(self, directory, extensions=(".json", ".md")):
        """Yield (path, lower-case content) for all matching files under directory."""
        if not directory.exists():
            return
        for ext in extensions:
            for path in directory.rglob(f"*{ext}"):
                yield path, path.read_text().lower()

    def _is_constraint_reference(self, line):
        """Return True if the line references a token as a constraint/rule, not actual content."""
        constraint_signals = (
            "forbidden", "must never", "must not", "never appear",
            "constraint", "following tokens", "keep the", "outside",
            "rewrite", "blocked", "not_for", "not for",
        )
        # A line that is just a backtick-quoted list item (e.g. "- `teacher_prompt`")
        # is listing a forbidden token, not containing actual teacher content.
        stripped = line.strip()
        if stripped.startswith("- `") and stripped.endswith("`"):
            return True
        return any(signal in line for signal in constraint_signals)

    def test_benchmarks_dir_has_no_teacher_only_content(self):
        for path, content in self._scan_files(BENCHMARKS_DIR):
            for token in FORBIDDEN_TOKENS:
                if token in content:
                    # Allow the token in the template's forbidden_in_tracked_files list
                    if path == TEMPLATE and f'"{token}"' in TEMPLATE.read_text().lower():
                        continue
                    # Allow the token when it appears in a constraint/rule context
                    lines_with_token = [
                        line for line in content.split("\n")
                        if token in line and not self._is_constraint_reference(line)
                    ]
                    for line in lines_with_token:
                        self.fail(
                            f"Forbidden token '{token}' found in tracked file {path}: "
                            f"{line.strip()}"
                        )

    def test_spec_012_has_no_teacher_only_content(self):
        content = SPEC.read_text().lower()
        for token in FORBIDDEN_TOKENS:
            lines_with_token = [
                line for line in content.split("\n")
                if token in line and not self._is_constraint_reference(line)
            ]
            for line in lines_with_token:
                self.fail(
                    f"Forbidden token '{token}' in spec 012 outside of "
                    f"a constraint/forbidden-list context: {line.strip()}"
                )

    def test_authoring_doc_has_no_teacher_only_content(self):
        content = DOC.read_text().lower()
        for token in FORBIDDEN_TOKENS:
            lines_with_token = [
                line for line in content.split("\n")
                if token in line and not self._is_constraint_reference(line)
            ]
            for line in lines_with_token:
                self.fail(
                    f"Forbidden token '{token}' in authoring doc outside of "
                    f"a constraint/forbidden-list context: {line.strip()}"
                )


class TestGitignoreExcludesLocal(unittest.TestCase):
    def test_gitignore_excludes_local_directory(self):
        gitignore_text = GITIGNORE.read_text()
        self.assertTrue(
            any(line.strip() in ("local/", "local") for line in gitignore_text.split("\n")),
            ".gitignore must exclude local/ directory",
        )


class TestPublicPrivateNamespaceDisjoint(unittest.TestCase):
    def test_public_pack_families_use_correct_namespace(self):
        if not (PUBLIC_PACK_DIR / "episode-family-registry.json").exists():
            self.skipTest("public pack not present")
        registry = json.loads((PUBLIC_PACK_DIR / "episode-family-registry.json").read_text())
        for family in registry["families"]:
            # Student-visible families must use .public. namespace
            if family["visibility"] == "student_visible":
                self.assertIn(
                    ".public.",
                    family["id"],
                    f"Student-visible family {family['id']} does not use .public. namespace",
                )
            # No family in the public registry should use .holdout. namespace
            self.assertNotIn(
                ".holdout.",
                family["id"],
                f"Family {family['id']} uses .holdout. namespace in public registry",
            )

    def test_template_example_family_uses_holdout_namespace(self):
        template = json.loads(TEMPLATE.read_text())
        example = template["example_holdout_family_shape"]
        self.assertIn(".holdout.", example["id"])
        self.assertNotIn(".public.", example["id"])
        self.assertEqual(example["visibility"], "teacher_only")


class TestSpecAndDocAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec_text = SPEC.read_text()
        cls.doc_text = DOC.read_text()
        cls.template = json.loads(TEMPLATE.read_text())

    def test_spec_exists(self):
        self.assertTrue(SPEC.exists())

    def test_doc_exists(self):
        self.assertTrue(DOC.exists())

    def test_spec_references_template(self):
        self.assertIn("benchmarks/private-holdout-pack-template.json", self.spec_text)

    def test_spec_references_doc(self):
        self.assertIn("docs/private-holdout-authoring.md", self.spec_text)

    def test_spec_references_test(self):
        self.assertIn("tests/test_private_holdout_separation.py", self.spec_text)

    def test_doc_references_template(self):
        self.assertIn("benchmarks/private-holdout-pack-template.json", self.doc_text)

    def test_doc_references_spec(self):
        self.assertIn("specs/012-private-holdout-pack.md", self.doc_text)

    def test_doc_references_test(self):
        self.assertIn("tests/test_private_holdout_separation.py", self.doc_text)

    def test_doc_references_local_directory(self):
        self.assertIn("local/private-holdout-packs/", self.doc_text)

    def test_spec_is_honest_about_scaffold_status(self):
        lower = self.spec_text.lower()
        self.assertIn("scaffold", lower)
        self.assertIn("not a sealed certification", lower)

    def test_doc_is_honest_about_scaffold_status(self):
        lower = self.doc_text.lower()
        self.assertIn("scaffold", lower)

    def test_seed_curriculum_doc_references_separation_test(self):
        seed_doc = SEED_CURRICULUM_DOC.read_text()
        self.assertIn("tests/test_private_holdout_separation.py", seed_doc)

    def test_readme_references_holdout_doc(self):
        readme = README.read_text()
        self.assertIn("docs/private-holdout-authoring.md", readme)

    def test_readme_references_holdout_spec(self):
        readme = README.read_text()
        self.assertIn("specs/012-private-holdout-pack.md", readme)


if __name__ == "__main__":
    unittest.main()
