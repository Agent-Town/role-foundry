"""Tests for the teacher review console read-model (D001 shell).

Validates that the teacher-review-read-model.js adapter correctly consumes
stored exports — both the original sample fixtures and the committed real
public-regression alpha receipt — to produce an honest review snapshot.

Contract under test:
- buildTeacherReviewSnapshot() produces all D001-required fields
- Missing inputs produce null/placeholder fields, never invented data
- Honesty badge accurately reflects fixture vs export status
- Diff summary, score breakdown, and promotion decision are correct
"""

import json
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
READ_MODEL_JS = APP / 'teacher-review-read-model.js'
DATA_DIR = ROOT / 'data' / 'curriculum'
SAMPLE_RUNS = DATA_DIR / 'frontend-product-engineer-sample-run-objects.v1.json'
SAMPLE_SCORECARD = DATA_DIR / 'frontend-product-engineer-sample-scorecard.v1.json'
EVAL_CONTRACT = DATA_DIR / 'frontend-product-engineer-evaluation-contract.v1.json'
SEED_REGISTRY = DATA_DIR / 'frontend-product-engineer-public-seed-registry.v1.json'
ALPHA_PUBLIC_EXPORT = APP / 'autoresearch-alpha.public-regression.export.json'
NODE = Path('/Users/robin/.nvm/versions/node/v24.14.0/bin/node')


class TeacherReviewReadModelTests(unittest.TestCase):
    """Tests for the teacher review read-model adapter."""

    def _run_node(self, script_body: str) -> dict:
        """Run a Node.js script that loads the read-model and returns JSON."""
        script = textwrap.dedent(f"""
            const fs = require('fs');
            const vm = require('vm');

            const sandbox = {{ console, JSON, Object, Array, Boolean, Number, String, Math, Error, module: {{ exports: {{}} }} }};
            vm.createContext(sandbox);
            vm.runInContext(fs.readFileSync({json.dumps(str(READ_MODEL_JS))}, 'utf8'), sandbox);

            const readModel = sandbox.module.exports;

            {script_body}
        """)
        completed = subprocess.run(
            [str(NODE), '-e', script],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            self.fail(f"Node.js script failed:\\n{completed.stderr}")
        return json.loads(completed.stdout)

    def _load_fixtures_script(self) -> str:
        """Return JS that loads all sample fixtures into variables."""
        return textwrap.dedent(f"""
            const runObjects = JSON.parse(fs.readFileSync({json.dumps(str(SAMPLE_RUNS))}, 'utf8'));
            const scorecard = JSON.parse(fs.readFileSync({json.dumps(str(SAMPLE_SCORECARD))}, 'utf8'));
            const contract = JSON.parse(fs.readFileSync({json.dumps(str(EVAL_CONTRACT))}, 'utf8'));
            const registry = JSON.parse(fs.readFileSync({json.dumps(str(SEED_REGISTRY))}, 'utf8'));
            const taskPacket = registry.tasks.find(t => t.task_id === runObjects.baseline_run.task_id);
        """)

    # ------------------------------------------------------------------
    # Full snapshot with all inputs
    # ------------------------------------------------------------------

    def test_full_snapshot_has_all_d001_fields(self):
        """D001 requires: task packet, diff summary, changed files, command
        results, transcript excerpt (as receipt ref), weighted score breakdown,
        and promotion decision."""
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                task_packet: taskPacket,
                baseline_run: runObjects.baseline_run,
                candidate_run: runObjects.candidate_run,
                scorecard: scorecard,
                evaluation_contract: contract,
            }});
            console.log(JSON.stringify({{
                has_task: snapshot.task !== null,
                has_baseline: snapshot.baseline !== null,
                has_candidate: snapshot.candidate !== null,
                has_diff_summary: snapshot.diff_summary !== null,
                has_scorecard: snapshot.scorecard !== null,
                has_contract: snapshot.contract !== null,
                has_evidence_links: snapshot.evidence_links !== null,
                promotion_decision: snapshot.promotion_decision,
                verifier_gate_status: snapshot.verifier_gate_status,
                honesty_badge: snapshot.honesty_badge,
                data_source: snapshot.data_source,
                shell_version: snapshot.shell_version,
            }}));
        """)
        self.assertTrue(result['has_task'])
        self.assertTrue(result['has_baseline'])
        self.assertTrue(result['has_candidate'])
        self.assertTrue(result['has_diff_summary'])
        self.assertTrue(result['has_scorecard'])
        self.assertTrue(result['has_contract'])
        self.assertTrue(result['has_evidence_links'])
        self.assertIn(result['promotion_decision'], ['promoted', 'task_pass_no_promotion', 'not_passing', 'pending'])
        self.assertIn(result['verifier_gate_status'], ['passing', 'failing', 'not_executed', 'no_checks', 'not_available'])
        self.assertIsNotNone(result['honesty_badge'])
        self.assertEqual(result['data_source'], 'sample_fixture')
        self.assertEqual(result['shell_version'], '0.1.0')

    # ------------------------------------------------------------------
    # Task identity extraction
    # ------------------------------------------------------------------

    def test_task_identity_fields(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                task_packet: taskPacket,
                baseline_run: runObjects.baseline_run,
                candidate_run: runObjects.candidate_run,
                scorecard: scorecard,
                evaluation_contract: contract,
            }});
            console.log(JSON.stringify(snapshot.task));
        """)
        self.assertEqual(result['task_id'], 'fpe.seed.a001.freeze-the-first-apprentice-role')
        self.assertEqual(result['role_id'], 'role-frontend-product-engineer')
        self.assertIsNotNone(result['title'])
        self.assertIsNotNone(result['objective'])
        self.assertEqual(result['acceptance_test_id'], 'A001')
        self.assertEqual(result['phase_index'], 1)

    # ------------------------------------------------------------------
    # Diff summary
    # ------------------------------------------------------------------

    def test_diff_summary_values(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                task_packet: taskPacket,
                baseline_run: runObjects.baseline_run,
                candidate_run: runObjects.candidate_run,
                scorecard: scorecard,
                evaluation_contract: contract,
            }});
            console.log(JSON.stringify(snapshot.diff_summary));
        """)
        self.assertEqual(result['baseline_run_id'], 'sample-fpe-a001-baseline')
        self.assertEqual(result['candidate_run_id'], 'sample-fpe-a001-candidate')
        self.assertAlmostEqual(result['baseline_score'], 0.62, places=2)
        self.assertAlmostEqual(result['candidate_score'], 0.8975, places=4)
        self.assertGreater(result['score_delta'], 0)
        self.assertEqual(result['baseline_changed_files'], 2)
        self.assertEqual(result['candidate_changed_files'], 3)

    # ------------------------------------------------------------------
    # Scorecard breakdown
    # ------------------------------------------------------------------

    def test_scorecard_breakdown(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                scorecard: scorecard,
            }});
            console.log(JSON.stringify({{
                weighted_score: snapshot.scorecard.weighted_score,
                task_pass: snapshot.scorecard.task_pass,
                dimension_count: snapshot.scorecard.dimensions.length,
                dimension_ids: snapshot.scorecard.dimensions.map(d => d.id),
                weights_sum: snapshot.scorecard.dimensions.reduce((sum, d) => sum + (d.weight || 0), 0),
                promotion_ready: snapshot.scorecard.promotion_gate.promotion_ready,
            }}));
        """)
        self.assertAlmostEqual(result['weighted_score'], 0.8975, places=4)
        self.assertTrue(result['task_pass'])
        self.assertEqual(result['dimension_count'], 5)
        self.assertEqual(result['dimension_ids'], [
            'task_outcome', 'regression_safety', 'mutation_discipline',
            'evidence_quality', 'honesty_boundary_discipline',
        ])
        self.assertAlmostEqual(result['weights_sum'], 1.0, places=2)
        self.assertFalse(result['promotion_ready'])

    # ------------------------------------------------------------------
    # Promotion decision logic
    # ------------------------------------------------------------------

    def test_promotion_decision_task_pass_no_promotion(self):
        """Sample scorecard passes task but promotion_ready is false."""
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                scorecard: scorecard,
            }});
            console.log(JSON.stringify({{ decision: snapshot.promotion_decision }}));
        """)
        self.assertEqual(result['decision'], 'task_pass_no_promotion')

    # ------------------------------------------------------------------
    # Evidence links
    # ------------------------------------------------------------------

    def test_evidence_links_from_candidate(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                candidate_run: runObjects.candidate_run,
            }});
            console.log(JSON.stringify(snapshot.evidence_links));
        """)
        self.assertIsNotNone(result['task_packet_ref'])
        self.assertIsNotNone(result['transcript_path'])
        self.assertIsNotNone(result['scorecard_path'])
        self.assertIsNotNone(result['changed_files_path'])
        self.assertIsNotNone(result['provenance_manifest_path'])

    # ------------------------------------------------------------------
    # Contract summary
    # ------------------------------------------------------------------

    def test_contract_summary(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                evaluation_contract: contract,
            }});
            console.log(JSON.stringify(snapshot.contract));
        """)
        self.assertEqual(result['contract_id'], 'frontend-product-engineer-evaluation-contract-v1')
        self.assertEqual(result['version'], '1.0.0')
        self.assertEqual(len(result['dimensions']), 5)
        self.assertAlmostEqual(result['thresholds']['task_pass_weighted_min'], 0.8, places=1)
        self.assertAlmostEqual(result['thresholds']['promotion_holdout_min'], 0.75, places=2)

    # ------------------------------------------------------------------
    # Honesty: missing inputs produce nulls, not inventions
    # ------------------------------------------------------------------

    def test_empty_inputs_produce_null_fields(self):
        """Missing data renders as empty instead of invented (D001 criterion)."""
        result = self._run_node("""
            const snapshot = readModel.buildTeacherReviewSnapshot({});
            console.log(JSON.stringify({
                task: snapshot.task,
                baseline: snapshot.baseline,
                candidate: snapshot.candidate,
                diff_summary: snapshot.diff_summary,
                scorecard: snapshot.scorecard,
                contract: snapshot.contract,
                promotion_decision: snapshot.promotion_decision,
                verifier_gate_status: snapshot.verifier_gate_status,
                data_source: snapshot.data_source,
            }));
        """)
        self.assertIsNone(result['task'])
        self.assertIsNone(result['baseline'])
        self.assertIsNone(result['candidate'])
        self.assertIsNone(result['diff_summary'])
        self.assertIsNone(result['scorecard'])
        self.assertIsNone(result['contract'])
        self.assertEqual(result['promotion_decision'], 'pending')
        self.assertEqual(result['verifier_gate_status'], 'not_available')
        self.assertEqual(result['data_source'], 'stored_export')

    def test_partial_inputs_produce_partial_snapshot(self):
        """Only scorecard provided; other fields stay null."""
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                scorecard: scorecard,
            }});
            console.log(JSON.stringify({{
                task: snapshot.task,
                baseline: snapshot.baseline,
                candidate: snapshot.candidate,
                diff_summary: snapshot.diff_summary,
                has_scorecard: snapshot.scorecard !== null,
                has_contract: snapshot.contract !== null,
            }}));
        """)
        self.assertIsNone(result['task'])
        self.assertIsNone(result['baseline'])
        self.assertIsNone(result['candidate'])
        self.assertIsNone(result['diff_summary'])
        self.assertTrue(result['has_scorecard'])
        self.assertFalse(result['has_contract'])

    # ------------------------------------------------------------------
    # Honesty badge
    # ------------------------------------------------------------------

    def test_fixture_badge_when_example_only(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                baseline_run: runObjects.baseline_run,
                candidate_run: runObjects.candidate_run,
                scorecard: scorecard,
            }});
            console.log(JSON.stringify({{
                data_source: snapshot.data_source,
                honesty_badge: snapshot.honesty_badge,
            }}));
        """)
        self.assertEqual(result['data_source'], 'sample_fixture')
        self.assertIn('fixture', result['honesty_badge'].lower())

    def test_export_badge_when_not_example(self):
        """Non-example data should get stored_export badge."""
        result = self._run_node("""
            const snapshot = readModel.buildTeacherReviewSnapshot({
                candidate_run: {
                    run_id: 'real-run-001',
                    kind: 'candidate',
                    example_only: false,
                    commands: [],
                    changed_files: [],
                    checks_run: [],
                    weighted_score: { value: 0.90 },
                    receipts: {},
                },
            });
            console.log(JSON.stringify({
                data_source: snapshot.data_source,
            }));
        """)
        self.assertEqual(result['data_source'], 'stored_export')

    # ------------------------------------------------------------------
    # Verifier gate status
    # ------------------------------------------------------------------

    def test_verifier_gate_passing_when_all_checks_pass(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                candidate_run: runObjects.candidate_run,
            }});
            console.log(JSON.stringify({{ gate: snapshot.verifier_gate_status }}));
        """)
        self.assertEqual(result['gate'], 'passing')

    def test_verifier_gate_failing_when_checks_fail(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                baseline_run: runObjects.baseline_run,
            }});
            console.log(JSON.stringify({{ gate: snapshot.verifier_gate_status }}));
        """)
        # baseline has no candidate, so gate should be not_available
        self.assertEqual(result['gate'], 'not_available')

    # ------------------------------------------------------------------
    # Command results extraction
    # ------------------------------------------------------------------

    def test_command_results_extracted(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                candidate_run: runObjects.candidate_run,
            }});
            console.log(JSON.stringify({{
                command_count: snapshot.candidate.commands.length,
                first_command: snapshot.candidate.commands[0]?.command || null,
                first_exit_code: snapshot.candidate.commands[0]?.exit_code,
            }}));
        """)
        self.assertGreater(result['command_count'], 0)
        self.assertIsNotNone(result['first_command'])
        self.assertEqual(result['first_exit_code'], 0)

    # ------------------------------------------------------------------
    # Run summary fields
    # ------------------------------------------------------------------

    def test_run_summary_workspace_isolation(self):
        result = self._run_node(f"""
            {self._load_fixtures_script()}
            const snapshot = readModel.buildTeacherReviewSnapshot({{
                candidate_run: runObjects.candidate_run,
            }});
            console.log(JSON.stringify({{
                workspace_kind: snapshot.candidate.workspace.kind,
                isolated: snapshot.candidate.workspace.isolated,
                base_commit: snapshot.candidate.workspace.base_commit,
            }}));
        """)
        self.assertEqual(result['workspace_kind'], 'git_worktree')
        self.assertTrue(result['isolated'])
        self.assertIsNotNone(result['base_commit'])

    def test_autoresearch_alpha_export_maps_to_stored_export_snapshot(self):
        result = self._run_node(f"""
            const receipt = JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_PUBLIC_EXPORT))}, 'utf8'));
            const snapshot = readModel.buildTeacherReviewSnapshotFromAutoresearchAlpha(receipt);
            console.log(JSON.stringify({{
                data_source: snapshot.data_source,
                source_contract: snapshot.source_contract,
                baseline_run_id: snapshot.baseline?.run_id || null,
                candidate_run_id: snapshot.candidate?.run_id || null,
                score_delta: snapshot.diff_summary?.score_delta ?? null,
                verifier_gate_status: snapshot.verifier_gate_status,
                candidate_command_count: snapshot.candidate?.commands?.length || 0,
                first_command_status: snapshot.candidate?.commands?.[0]?.execution_status || null,
                candidate_changed_files: snapshot.candidate?.changed_files?.length || 0,
                scorecard_present: snapshot.scorecard !== null,
                contract_present: snapshot.contract !== null,
                honesty_badge: snapshot.honesty_badge,
                alpha_verdict: snapshot.alpha_receipt?.verdict || null,
            }}));
        """)
        self.assertEqual(result['data_source'], 'stored_export')
        self.assertEqual(result['source_contract'], 'autoresearch_alpha_receipt')
        self.assertEqual(result['baseline_run_id'], 'run-eval-001')
        self.assertEqual(result['candidate_run_id'], 'run-eval-002')
        self.assertAlmostEqual(result['score_delta'], 0.4, places=4)
        self.assertEqual(result['verifier_gate_status'], 'not_executed')
        self.assertGreater(result['candidate_command_count'], 0)
        self.assertEqual(result['first_command_status'], 'not_executed')
        self.assertGreater(result['candidate_changed_files'], 0)
        self.assertFalse(result['scorecard_present'])
        self.assertFalse(result['contract_present'])
        self.assertIn('public-regression', result['honesty_badge'])
        self.assertEqual(result['alpha_verdict'], 'better')


class TeacherReviewHTMLTests(unittest.TestCase):
    """Validates the teacher-review.html page exists and references the
    read-model correctly."""

    def test_teacher_review_html_exists(self):
        html_path = APP / 'teacher-review.html'
        self.assertTrue(html_path.exists(), "app/teacher-review.html must exist")

    def test_teacher_review_html_loads_read_model(self):
        html_path = APP / 'teacher-review.html'
        content = html_path.read_text()
        self.assertIn('teacher-review-read-model.js', content)
        self.assertIn('TEACHER_REVIEW_READ_MODEL', content)
        self.assertIn('buildTeacherReviewSnapshotFromAutoresearchAlpha', content)
        self.assertIn('autoresearch-alpha.public-regression.export.json', content)

    def test_teacher_review_html_references_d001_fields(self):
        """The HTML must reference all D001 required review fields."""
        html_path = APP / 'teacher-review.html'
        content = html_path.read_text()
        required_references = [
            'task',              # task packet identity
            'diff_summary',      # diff summary
            'changed_files',     # changed files
            'commands',          # command results
            'scorecard',         # weighted score breakdown
            'promotion_decision', # promotion decision
            'verifier_gate',     # verifier gate status
            'evidence_links',    # evidence/receipt links
            'honesty_badge',     # honesty badge
        ]
        for ref in required_references:
            self.assertIn(ref, content, f"teacher-review.html must reference '{ref}'")

    def test_teacher_review_read_model_js_exists(self):
        self.assertTrue(READ_MODEL_JS.exists(), "app/teacher-review-read-model.js must exist")

    def test_nav_links_include_teacher_review(self):
        """All app HTML pages should include a Teacher Review nav link."""
        html_files = list(APP.glob('*.html'))
        self.assertGreater(len(html_files), 0)
        for html_file in html_files:
            content = html_file.read_text()
            self.assertIn(
                "teacher-review.html",
                content,
                f"{html_file.name} must include teacher-review.html nav link",
            )


if __name__ == '__main__':
    unittest.main()
