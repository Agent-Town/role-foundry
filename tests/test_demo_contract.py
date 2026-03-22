import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
DOCS = ROOT / 'docs'
DATA_JS = APP / 'data.js'
README = ROOT / 'README.md'
COMPOSE = ROOT / 'docker-compose.yml'


class DemoContractTests(unittest.TestCase):
    def test_required_pages_exist(self):
        required = ['index.html', 'scenarios.html', 'run.html', 'scorecard.html']
        for name in required:
            self.assertTrue((APP / name).exists(), f'missing page: {name}')

    def test_demo_data_file_exists(self):
        self.assertTrue(DATA_JS.exists(), 'app/data.js must exist as the demo data seam')

    def test_demo_mode_is_explicit(self):
        text = DATA_JS.read_text()
        self.assertIn("mode: 'demo'", text)

    def test_frontend_apprentice_seed_role_exists(self):
        text = DATA_JS.read_text()
        self.assertIn("name: 'Frontend Apprentice'", text)
        self.assertIn('Robin + Neo', text)

    def test_scenario_split_is_preserved(self):
        text = DATA_JS.read_text()
        training_count = len(re.findall(r"type:\s*'training'", text))
        holdout_count = len(re.findall(r"type:\s*'holdout'", text))
        self.assertGreaterEqual(training_count, 6)
        self.assertGreaterEqual(holdout_count, 3)

    def test_multiple_runs_and_iteration_history_exist(self):
        text = DATA_JS.read_text()
        self.assertIn("'run-001'", text)
        self.assertIn("'run-002'", text)
        self.assertIn('iterations:', text)
        self.assertIn('failure_themes', text)
        self.assertIn('student_views:', text)
        self.assertIn("agent_role: 'student'", text)
        self.assertIn("agent_role: 'teacher'", text)

    def test_apprentice_vertical_surfaces_exist(self):
        index_text = (APP / 'index.html').read_text()
        scenarios_text = (APP / 'scenarios.html').read_text()
        run_text = (APP / 'run.html').read_text()
        scorecard_text = (APP / 'scorecard.html').read_text()

        self.assertIn('Frontend Apprentice', index_text)
        self.assertIn('Public Curriculum &amp; Sealed Holdouts', scenarios_text)
        self.assertIn('Proof Bundle', run_text)
        self.assertIn('Policy Snapshot', run_text)
        self.assertIn('Transcript Excerpt', run_text)
        self.assertIn('Failure Analysis → Next Curriculum', scorecard_text)
        self.assertIn('Compare to ', scorecard_text)
        self.assertIn('config.js', index_text)

    def test_readme_explains_demo_vs_live_mode(self):
        text = README.read_text()
        self.assertIn('Demo mode vs live mode', text)
        self.assertIn('runner-bridge', text)
        self.assertIn('Clawith', text)

    def test_compose_includes_demo_stack_and_live_profile(self):
        text = COMPOSE.read_text()
        self.assertIn('role-foundry-web:', text)
        self.assertIn('postgres:', text)
        self.assertIn('redis:', text)
        # M3: clawith and bootstrap are real services gated by the "live" profile
        self.assertIn('clawith:', text)
        self.assertIn('bootstrap:', text)
        self.assertIn('profiles: ["live"]', text)

    def test_required_docs_exist(self):
        required = [
            'conversation-log.md',
            'runner-bridge.md',
            'v1-mvp-plan.md',
            'milestones.md',
        ]
        for name in required:
            self.assertTrue((DOCS / name).exists(), f'missing doc: {name}')

    def test_specs_exist_for_all_milestones(self):
        specs_dir = ROOT / 'specs'
        required = [
            '001-demo-contract.md',
            '002-apprentice-vertical.md',
            '003-clawith-compose.md',
            '004-role-scenario-seed.md',
            '005-runner-bridge-first-run.md',
            '006-teacher-eval-loop.md',
            '007-submission-proof.md',
        ]
        for name in required:
            self.assertTrue((specs_dir / name).exists(), f'missing spec: {name}')


if __name__ == '__main__':
    unittest.main()
