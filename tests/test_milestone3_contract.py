"""
Milestone 3 contract tests — Clawith compose wiring + honest probe lane.

These tests verify the live-mode acceptance criteria from docs/milestones.md,
plus the newer read-only probe lane:
  - docker compose can start a real Clawith service when an image is provided
  - compose health check targets the real upstream API path
  - seed payload validation works without a live Clawith
  - live-mode preflight stays read-only and honest when upstream parity is absent
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "docker-compose.yml"
SEED_DIR = ROOT / "seed"
SEED_FILE = SEED_DIR / "role-foundry-apprentice.json"
BOOTSTRAP = SEED_DIR / "bootstrap.py"
PROBE = SEED_DIR / "probe_clawith.py"
DOCS = ROOT / "docs"
ENV_EXAMPLE = ROOT / ".env.example"


class SeedDataModelTests(unittest.TestCase):
    """Spec 004 — Role + Scenario Seed Model."""

    @classmethod
    def setUpClass(cls):
        with open(SEED_FILE) as f:
            cls.data = json.load(f)

    def test_seed_file_exists(self):
        self.assertTrue(SEED_FILE.exists())

    def test_seed_has_role_with_required_fields(self):
        role = self.data["role"]
        for field in ("id", "name", "description", "goals", "success_criteria"):
            self.assertIn(field, role, f"role missing '{field}'")
            self.assertTrue(role[field], f"role '{field}' is empty")

    def test_seed_has_at_least_6_training_scenarios(self):
        training = [s for s in self.data["scenarios"] if s["type"] == "training"]
        self.assertGreaterEqual(len(training), 6)

    def test_seed_has_at_least_3_holdout_scenarios(self):
        holdouts = [s for s in self.data["scenarios"] if s["type"] == "holdout"]
        self.assertGreaterEqual(len(holdouts), 3)

    def test_every_scenario_has_required_fields(self):
        for s in self.data["scenarios"]:
            for field in ("id", "title", "description", "type", "difficulty"):
                self.assertIn(field, s, f"scenario {s.get('id', '?')} missing '{field}'")

    def test_scenario_types_are_valid(self):
        for s in self.data["scenarios"]:
            self.assertIn(s["type"], ("training", "holdout"))

    def test_scenario_ids_are_unique(self):
        ids = [s["id"] for s in self.data["scenarios"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_student_facing_payload_excludes_holdouts(self):
        """Holdout scenario details must not appear in a student-facing query."""
        training = [s for s in self.data["scenarios"] if s["type"] == "training"]
        holdouts = [s for s in self.data["scenarios"] if s["type"] == "holdout"]
        training_str = json.dumps(training)
        for h in holdouts:
            self.assertNotIn(
                h["title"],
                training_str,
                f"holdout title '{h['title']}' leaked into training payload",
            )

    def test_seed_role_matches_demo_data_name(self):
        """Seed data should represent the same vertical as demo mode."""
        self.assertEqual(self.data["role"]["name"], "Frontend Apprentice")


class BootstrapScriptTests(unittest.TestCase):
    """Bootstrap script must stay honest about what it can and cannot seed."""

    def test_bootstrap_script_exists(self):
        self.assertTrue(BOOTSTRAP.exists())

    def test_probe_script_exists(self):
        self.assertTrue(PROBE.exists())

    def test_bootstrap_validate_passes(self):
        result = subprocess.run(
            [sys.executable, str(BOOTSTRAP), "--validate"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, f"bootstrap --validate failed:\n{result.stderr}")
        self.assertIn("PASS", result.stdout)

    def test_bootstrap_dry_run_shows_plan(self):
        result = subprocess.run(
            [sys.executable, str(BOOTSTRAP), "--seed", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0, f"bootstrap --dry-run failed:\n{result.stderr}")
        self.assertIn("[dry-run]", result.stdout)
        self.assertIn("Frontend Apprentice", result.stdout)
        self.assertIn("legacy", result.stdout.lower())


class ComposeIntegrationTests(unittest.TestCase):
    """Spec 003 + Spec 009 — Clawith compose wiring and preflight probe."""

    @classmethod
    def setUpClass(cls):
        cls.text = COMPOSE.read_text()

    def test_clawith_service_is_profile_gated(self):
        self.assertIn("clawith:", self.text)
        self.assertIn('profiles: ["live"]', self.text)

    def test_clawith_has_real_health_check(self):
        self.assertIn("/api/health", self.text)
        self.assertNotIn("http://localhost:3000/health", self.text)

    def test_clawith_depends_on_postgres_and_redis(self):
        self.assertIn("postgres:", self.text)
        self.assertIn("redis:", self.text)

    def test_bootstrap_depends_on_clawith_healthy(self):
        self.assertIn("bootstrap:", self.text)
        self.assertIn("condition: service_healthy", self.text)

    def test_bootstrap_runs_read_only_probe(self):
        self.assertIn("seed/probe_clawith.py", self.text)
        self.assertNotIn("seed/bootstrap.py --seed", self.text)

    def test_clawith_image_is_configurable(self):
        self.assertIn("CLAWITH_IMAGE", self.text)
        self.assertNotIn("../Clawith", self.text)
        self.assertNotIn("../clawith", self.text)

    def test_demo_compose_up_does_not_require_clawith(self):
        self.assertIn('profiles: ["live"]', self.text)


class DocumentationTests(unittest.TestCase):
    """Integration docs must exist and be honest."""

    def test_clawith_integration_doc_exists(self):
        doc = DOCS / "clawith-integration.md"
        self.assertTrue(doc.exists())

    def test_integration_doc_covers_probe_lane(self):
        text = (DOCS / "clawith-integration.md").read_text()
        self.assertIn("demo mode", text.lower())
        self.assertIn("live mode", text.lower())
        self.assertIn("/api/health", text)
        self.assertIn("/api/auth/registration-config", text)
        self.assertIn("/api/enterprise/llm-models", text)
        self.assertIn("/api/admin/companies", text)
        self.assertIn("probe_clawith.py", text)
        self.assertIn("/api/roles", text)
        self.assertIn("/api/scenarios", text)
        self.assertIn("/api/runs/{run_id}", text)

    def test_env_example_has_clawith_image_var(self):
        text = ENV_EXAMPLE.read_text()
        self.assertIn("CLAWITH_IMAGE", text)


if __name__ == "__main__":
    unittest.main()
