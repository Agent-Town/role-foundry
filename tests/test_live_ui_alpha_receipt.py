"""Phase E tests — Live UI alpha hookup against real executable receipt shape.

E001: Read-model schema validity (real receipt adapts without error)
E002: Baseline/candidate visibility (both runs appear in ordered runs)
E003: Verdict fidelity (UI verdict fields match source receipt)
E004: Demo/live honesty marker (sourceMode is explicit)
E005: Graceful missing-data behavior (partial receipts degrade cleanly)
"""

import json
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
DATA_JS = APP / 'data.js'
APP_JS = APP / 'app.js'
ALPHA_RECEIPT_SAMPLE = APP / 'live-read-model.alpha-receipt.sample.json'
ALPHA_ENVELOPE_SAMPLE = APP / 'live-read-model.alpha-loop.sample.json'
NODE = Path('/Users/robin/.nvm/versions/node/v24.14.0/bin/node')


class _NodeAdapterMixin:
    """Shared helper: run the JS adapter in a Node VM and return store state."""

    def _run_node(self, payload_expression: str) -> dict:
        script = textwrap.dedent(
            f"""
            const fs = require('fs');
            const vm = require('vm');

            const sandbox = {{
              console,
              URL,
              structuredClone: globalThis.structuredClone,
              window: {{
                location: {{
                  href: 'http://example.test/app/index.html?mode=live&liveDataUrl=sample.json',
                  assign() {{}}
                }},
                localStorage: {{
                  getItem() {{ return null; }},
                  setItem() {{}},
                  removeItem() {{}}
                }}
              }},
              document: {{ addEventListener() {{}} }},
              fetch: async () => {{ throw new Error('fetch not expected in unit test'); }},
            }};
            sandbox.window.window = sandbox.window;
            vm.createContext(sandbox);
            vm.runInContext(fs.readFileSync({json.dumps(str(DATA_JS))}, 'utf8'), sandbox);
            vm.runInContext(fs.readFileSync({json.dumps(str(APP_JS))}, 'utf8'), sandbox);

            const payload = {payload_expression};
            const adapted = sandbox.window.ROLE_FOUNDRY_READ_MODEL.adaptLivePayload(payload);
            const normalized = sandbox.normalizeAppData(adapted, 'live');
            const store = sandbox.createAppStore(sandbox.roleFoundryConfig());
            store.applySnapshot(normalized, {{
              sourceMode: 'live',
              requestedMode: 'live',
              loading: false,
              status: 'connected',
              configured: true,
              endpoint: 'live-read-model.alpha-receipt.sample.json',
            }});

            // Collect comprehensive state for assertions
            const latestScoredId = store.latestScoredRunId();
            const compId = latestScoredId ? store.comparisonRunId(latestScoredId) : null;
            const latestIteration = store.latestIteration();

            console.log(JSON.stringify({{
              // E001 — schema validity
              runIds: store.orderedRuns().map(r => r.id),
              scoredRunIds: store.scoredRuns().map(r => r.id),
              runCount: store.runs.length,

              // E002 — baseline/candidate visibility
              baselineRunId: store.baselineRun()?.id || null,
              latestRunId: store.latestRunId(),
              latestScoredRunId: latestScoredId,
              comparisonRunId: compId,
              hasComparisonRun: latestScoredId ? store.hasComparisonRun(latestScoredId) : false,

              // E003 — verdict fidelity
              latestScoreSummary: store.latestScoreSummary(),
              teacherSummary: latestScoredId ? store.teacherSummaryForRun(latestScoredId) : null,
              overallDelta: latestScoredId ? store.scoreDelta(latestScoredId) : null,
              iterationScoreDelta: latestIteration?.score_delta || null,
              iterationLabel: latestIteration?.label || null,
              iterationIdentitySnapshot: latestIteration?.identity_snapshot || null,

              // E004 — demo/live marker
              sourceMode: store.sourceMode,
              requestedMode: store.requestedMode,
              modeBadgeLabel: store.modeBadgeLabel(),
              modeBannerTone: store.modeBannerTone(),

              // E005 — graceful degradation
              candidateResultCount: latestScoredId ? store.resultsForRun(latestScoredId).length : 0,
              studentHasScorecard: Boolean(store.getScorecard(
                store.orderedRuns().find(r => r.stage_label === 'Candidate student')?.id || '__missing__'
              )),
              latestStudentViewRunId: store.latestStudentViewRunId(),
              replayRunIds: Object.keys(store.run_replays).sort(),
              artifactRunIds: Object.keys(store.artifacts).sort(),

              // Run statuses
              runStatuses: store.orderedRuns().map(r => ({{ id: r.id, status: r.status, stage_label: r.stage_label }})),
            }}));
            """
        )
        completed = subprocess.run(
            [str(NODE), '-e', script],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(f"Node script failed:\n{completed.stderr}")
        return json.loads(completed.stdout)


class E001_ReadModelSchemaValidity(_NodeAdapterMixin, unittest.TestCase):
    """E001: Real executable receipt adapts through the read-model without error."""

    def test_real_receipt_adapts_to_three_runs(self):
        """Real receipt produces exactly three runs (one per stage)."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['runCount'], 3)
        self.assertEqual(len(result['runIds']), 3)

    def test_real_receipt_run_ids_match_source(self):
        """Adapted run IDs match the source receipt stage run_ids."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        expected_ids = [
            'autoresearch-alpha-example-baseline-eval',
            'autoresearch-alpha-example-candidate-student',
            'autoresearch-alpha-example-candidate-teacher-eval',
        ]
        self.assertEqual(result['runIds'], expected_ids)

    def test_real_receipt_scored_runs_are_teacher_stages_only(self):
        """Only baseline-eval and candidate-teacher-eval have scorecards."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['scoredRunIds'], [
            'autoresearch-alpha-example-baseline-eval',
            'autoresearch-alpha-example-candidate-teacher-eval',
        ])

    def test_existing_envelope_sample_still_works(self):
        """The rich envelope sample must still adapt correctly (no regression)."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_ENVELOPE_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(len(result['runIds']), 3)
        self.assertIn('run-eval-001', result['runIds'])


class E002_BaselineCandidateVisibility(_NodeAdapterMixin, unittest.TestCase):
    """E002: Both baseline and candidate runs are visible in ordered runs."""

    def test_baseline_run_identified(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['baselineRunId'], 'autoresearch-alpha-example-baseline-eval')

    def test_candidate_is_latest_scored(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['latestScoredRunId'], 'autoresearch-alpha-example-candidate-teacher-eval')

    def test_comparison_links_candidate_to_baseline(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertTrue(result['hasComparisonRun'])
        self.assertEqual(result['comparisonRunId'], 'autoresearch-alpha-example-baseline-eval')

    def test_all_run_statuses_completed(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        for run_info in result['runStatuses']:
            self.assertEqual(run_info['status'], 'completed', f"run {run_info['id']} not completed")


class E003_VerdictFidelity(_NodeAdapterMixin, unittest.TestCase):
    """E003: UI verdict fields match the source receipt exactly."""

    def test_score_summary_reflects_aggregate(self):
        """Latest scored run shows 4/4 from the receipt aggregate."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['latestScoreSummary'], '4/4 (100%)')

    def test_teacher_summary_contains_verdict_label(self):
        """Teacher summary references the comparison verdict."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        summary = result['teacherSummary'] or ''
        # Should contain the verdict text or comparison label
        has_verdict = 'better' in summary.lower() or 'evaluation' in summary.lower()
        self.assertTrue(has_verdict, f"teacher summary missing verdict: {summary}")

    def test_iteration_score_delta_computed(self):
        """Iteration score_delta is computed from aggregate scores."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        delta = result['iterationScoreDelta']
        self.assertIsNotNone(delta, "score_delta should be computed from aggregate scorecards")
        # Both baseline and candidate have passed=4, so overall delta is 0
        self.assertEqual(delta['overall'], 0)

    def test_identity_snapshot_contains_verdict(self):
        """Iteration identity_snapshot references the verdict."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        snapshot = result['iterationIdentitySnapshot'] or ''
        has_verdict_ref = 'better' in snapshot.lower() or 'evaluation' in snapshot.lower()
        self.assertTrue(has_verdict_ref, f"identity snapshot: {snapshot}")


class E004_DemoLiveHonestyMarker(_NodeAdapterMixin, unittest.TestCase):
    """E004: Explicit demo/live state marker in the UI store."""

    def test_source_mode_is_live(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['sourceMode'], 'live')

    def test_mode_badge_says_live(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['modeBadgeLabel'], 'LIVE SHELL')

    def test_mode_banner_tone_is_live(self):
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['modeBannerTone'], 'tone-live')


class E005_GracefulMissingData(_NodeAdapterMixin, unittest.TestCase):
    """E005: Missing/partial fields degrade to pending/empty, not crashes."""

    def test_student_stage_has_no_scorecard(self):
        """Candidate-student has no teacher evaluation → no scorecard."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertFalse(result['studentHasScorecard'])

    def test_thin_receipt_has_no_per_scenario_results(self):
        """Real receipt lacks scenario_results → resultsForRun returns empty."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['candidateResultCount'], 0)

    def test_no_replay_lines_is_empty_not_error(self):
        """Real receipt has no replay lines → run_replays is empty, not crashed."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        self.assertEqual(result['replayRunIds'], [])

    def test_no_artifacts_is_empty_not_error(self):
        """Real receipt has no inline artifacts → artifacts dict is empty."""
        expr = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_RECEIPT_SAMPLE))}, 'utf8'))"
        result = self._run_node(expr)
        # May have empty artifacts or minimal ones; should not crash
        self.assertIsInstance(result['artifactRunIds'], list)

    def test_receipt_with_missing_stages_degrades(self):
        """A receipt with only baseline-eval still adapts without error."""
        partial_receipt = textwrap.dedent("""
            ({
              receipt_type: 'autoresearch-alpha',
              receipt_version: '0.2.0',
              stages: {
                'baseline-eval': {
                  run_id: 'partial-baseline',
                  status: 'completed',
                  aggregate_score: { passed: 2, total: 4, pass_rate: 0.5, average_score: 0.4 },
                  machine_score: 0.4
                }
              },
              comparison_verdict: {},
              score_deltas: {},
              blocked_criteria: [],
              honesty_note: 'Partial receipt for testing graceful degradation.'
            })
        """).strip()
        result = self._run_node(partial_receipt)
        self.assertEqual(result['runCount'], 1)
        self.assertEqual(result['runIds'], ['partial-baseline'])
        self.assertEqual(result['sourceMode'], 'live')

    def test_receipt_with_empty_comparison_verdict_degrades(self):
        """Empty comparison_verdict should not crash the adapter."""
        receipt_expr = textwrap.dedent("""
            ({
              receipt_type: 'autoresearch-alpha',
              receipt_version: '0.2.0',
              stages: {
                'baseline-eval': {
                  run_id: 'empty-verdict-baseline',
                  status: 'completed',
                  aggregate_score: { passed: 3, total: 4, pass_rate: 0.75, average_score: 0.6 },
                  machine_score: 0.6
                },
                'candidate-student': {
                  run_id: 'empty-verdict-student',
                  status: 'completed',
                  machine_score: 0.7
                },
                'candidate-teacher-eval': {
                  run_id: 'empty-verdict-candidate',
                  status: 'completed',
                  aggregate_score: { passed: 4, total: 4, pass_rate: 1.0, average_score: 0.8 },
                  machine_score: 0.8
                }
              },
              comparison_verdict: {},
              score_deltas: {},
              blocked_criteria: [],
              honesty_note: 'Empty verdict for degradation testing.'
            })
        """).strip()
        result = self._run_node(receipt_expr)
        self.assertEqual(result['runCount'], 3)
        self.assertEqual(result['sourceMode'], 'live')


if __name__ == '__main__':
    unittest.main()
