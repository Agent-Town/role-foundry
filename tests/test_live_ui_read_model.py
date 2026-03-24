import json
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
DATA_JS = APP / 'data.js'
APP_JS = APP / 'app.js'
ALPHA_SAMPLE = APP / 'live-read-model.alpha-loop.sample.json'
ALPHA_REAL_EXPORT = APP / 'autoresearch-alpha.public-regression.export.json'
NODE = Path('/Users/robin/.nvm/versions/node/v24.14.0/bin/node')


class LiveUiReadModelTests(unittest.TestCase):
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
              endpoint: 'live-read-model.alpha-loop.sample.json',
            }});

            console.log(JSON.stringify({{
              runIds: store.orderedRuns().map(run => run.id),
              scoredRunIds: store.scoredRuns().map(run => run.id),
              latestRunId: store.latestRunId(),
              latestScoredRunId: store.latestScoredRunId(),
              latestStudentViewRunId: store.latestStudentViewRunId(),
              candidateComparisonRunId: store.comparisonRunId('run-eval-002'),
              latestScoreSummary: store.latestScoreSummary(),
              overallDelta: store.scoreDelta('run-eval-002'),
              holdoutDelta: store.scoreDelta('run-eval-002', null, 'holdout'),
              candidateResults: store.resultsForRun('run-eval-002').length,
              studentHasScorecard: Boolean(store.getScorecard('run-eval-001-student')),
              candidateTeacherSummary: store.teacherSummaryForRun('run-eval-002'),
              latestFailureThemes: (store.latestIteration()?.failure_themes || []).map(theme => theme.theme),
              latestStudentPrompt: store.getStudentView(store.latestStudentViewRunId())?.prompt_summary || null,
              latestStudentVisibleLabels: (store.getStudentView(store.latestStudentViewRunId())?.visible_scenarios || []).map(ref => store.visibleScenarioLabel(ref)),
              artifactRunIds: Object.keys(store.artifacts).sort(),
              replayRunIds: Object.keys(store.run_replays).sort(),
              sourceMode: store.sourceMode,
              trainingScenarioCount: store.trainingScenarios().length,
              holdoutScenarioCount: store.holdoutScenarios().length,
              readModelSource: store.alphaLoopReadModel()?.source || null,
              alphaComparisonVerdict: store.alphaLoopComparison()?.verdict || null,
              alphaComparisonAxis: store.alphaLoopComparison()?.deciding_axis || null,
              alphaTotalScoreDelta: store.alphaLoopComparison()?.total_score_delta ?? null,
              alphaPassCountDelta: store.alphaLoopComparison()?.category_deltas?.pass_count ?? null,
              alphaHoldoutPassCountDelta: store.alphaLoopComparison()?.category_deltas?.holdout_pass_count ?? null,
              alphaIntegrityStatus: store.alphaLoopReadModel()?.integrity_gate?.status || null,
              alphaStageKeys: (store.alphaLoopReadModel()?.stages || []).map(stage => stage.stage_key),
              alphaSealingStatus: store.alphaLoopSealingReceipt()?.status || null,
              alphaSealingClaimCeiling: store.alphaLoopSealingReceipt()?.claim_ceiling || null,
              alphaSealingNote: store.alphaLoopSealingReceipt()?.honesty_note || null,
              alphaSealingBlockedClaims: store.alphaLoopBlockedClaims().map(entry => entry.claim),
              alphaSealingPresentChecklist: store.alphaLoopSealingChecklistEntries(true).map(entry => entry.key),
              alphaSealingPendingChecklist: store.alphaLoopSealingChecklistEntries(false).map(entry => entry.key),
              alphaSealingUnmetPrerequisites: store.alphaLoopUnmetSealingPrerequisites().map(entry => entry.enables),
              alphaSealingFingerprintScope: store.alphaLoopSealingFingerprint()?.scope || null,
            }}));
            """
        )
        completed = subprocess.run(
            [str(NODE), '-e', script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def test_alpha_envelope_maps_into_live_shell_snapshot(self):
        payload_expression = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_SAMPLE))}, 'utf8'))"
        result = self._run_node(payload_expression)

        self.assertEqual(result['runIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['scoredRunIds'], ['run-eval-001', 'run-eval-002'])
        self.assertEqual(result['latestRunId'], 'run-eval-002')
        self.assertEqual(result['latestScoredRunId'], 'run-eval-002')
        self.assertEqual(result['latestStudentViewRunId'], 'run-eval-002')
        self.assertEqual(result['candidateComparisonRunId'], 'run-eval-001')
        self.assertEqual(result['latestScoreSummary'], '4/5 (80%)')
        self.assertEqual(result['overallDelta'], 2)
        self.assertEqual(result['holdoutDelta'], 1)
        self.assertEqual(result['candidateResults'], 5)
        self.assertFalse(result['studentHasScorecard'])
        self.assertIn('Candidate materially improved', result['candidateTeacherSummary'])
        self.assertEqual(result['latestFailureThemes'], ['Rewrite teacher-only holdout families outside the public repo'])
        self.assertIn('public benchmark pack', result['latestStudentPrompt'])
        self.assertEqual(
            result['latestStudentVisibleLabels'],
            [
                'Expose visible score deltas',
                'Attach a proof bundle to each strong run',
                'Convert failures into the next curriculum',
            ],
        )
        self.assertEqual(result['artifactRunIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['replayRunIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['sourceMode'], 'live')
        self.assertEqual(result['trainingScenarioCount'], 3)
        self.assertEqual(result['holdoutScenarioCount'], 2)
        self.assertEqual(result['readModelSource'], 'autoresearch-alpha')
        self.assertEqual(result['alphaComparisonVerdict'], 'better')
        self.assertEqual(result['alphaComparisonAxis'], 'machine_score')
        self.assertEqual(result['alphaTotalScoreDelta'], 0.4)
        self.assertEqual(result['alphaPassCountDelta'], 2)
        self.assertEqual(result['alphaHoldoutPassCountDelta'], 1)
        self.assertEqual(result['alphaIntegrityStatus'], 'pass')
        self.assertEqual(
            result['alphaStageKeys'],
            ['baseline-eval', 'candidate-student', 'candidate-teacher-eval'],
        )
        self.assertEqual(result['alphaSealingStatus'], 'public_regression_alpha')
        self.assertEqual(
            result['alphaSealingClaimCeiling'],
            'public-regression alpha execution with public-safe receipts',
        )
        self.assertIn('not a seal', result['alphaSealingNote'])
        self.assertEqual(
            result['alphaSealingBlockedClaims'],
            [
                'sealed evaluation',
                'sealed certification',
                'tamper-proof execution',
                'independently audited',
            ],
        )
        self.assertEqual(
            result['alphaSealingPresentChecklist'],
            ['public_benchmark_pack_loaded', 'integrity_gate_passed'],
        )
        self.assertEqual(
            result['alphaSealingPendingChecklist'],
            [
                'private_holdout_manifest_loaded',
                'independent_executor_sandbox',
                'third_party_holdout_auditor',
                'hardware_attestation_or_enclave',
                'external_audit',
                'pre_run_manifest_commitment',
            ],
        )
        self.assertEqual(
            result['alphaSealingUnmetPrerequisites'],
            [
                'sealed evaluation',
                'sealed certification',
                'tamper-proof execution',
                'independently audited',
                'stronger tamper-evidence claims beyond local correlation',
            ],
        )
        self.assertIsNone(result['alphaSealingFingerprintScope'])

    def test_real_public_regression_export_adapts_into_live_shell_snapshot(self):
        payload_expression = f"JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_REAL_EXPORT))}, 'utf8'))"
        result = self._run_node(payload_expression)

        self.assertEqual(result['runIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['candidateComparisonRunId'], 'run-eval-001')
        self.assertEqual(result['readModelSource'], 'autoresearch-alpha')
        self.assertEqual(result['alphaComparisonVerdict'], 'better')
        self.assertEqual(result['alphaSealingStatus'], 'public_regression_alpha')
        self.assertEqual(
            result['alphaSealingClaimCeiling'],
            'public-regression alpha execution with public-safe receipts',
        )
        self.assertEqual(result['overallDelta'], 2)
        self.assertEqual(result['holdoutDelta'], 1)
        self.assertFalse(result['studentHasScorecard'])

    def test_raw_autoresearch_receipt_without_outer_envelope_still_adapts(self):
        payload_expression = textwrap.dedent(
            f"""
            (() => {{
              const envelope = JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_SAMPLE))}, 'utf8'));
              return envelope.autoresearch_alpha;
            }})()
            """
        ).strip()
        result = self._run_node(payload_expression)

        self.assertEqual(result['runIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['scoredRunIds'], ['run-eval-001', 'run-eval-002'])
        self.assertEqual(result['candidateComparisonRunId'], 'run-eval-001')
        self.assertEqual(result['trainingScenarioCount'], 6)
        self.assertEqual(result['holdoutScenarioCount'], 2)
        self.assertEqual(result['alphaComparisonVerdict'], 'better')
        self.assertEqual(
            result['latestStudentVisibleLabels'],
            [
                'Expose visible score deltas',
                'Attach a proof bundle to each strong run',
                'Convert failures into the next curriculum',
            ],
        )
        self.assertFalse(result['studentHasScorecard'])
        self.assertEqual(result['alphaSealingStatus'], 'public_regression_alpha')
        self.assertIn('sealed evaluation', result['alphaSealingBlockedClaims'])

    def test_student_only_live_receipt_keeps_missing_comparison_honest(self):
        payload_expression = textwrap.dedent(
            f"""
            (() => {{
              const envelope = JSON.parse(fs.readFileSync({json.dumps(str(ALPHA_SAMPLE))}, 'utf8'));
              const receipt = envelope.autoresearch_alpha;
              return {{
                flow: receipt.flow,
                sequence_id: receipt.sequence_id,
                dataset_manifest_id: receipt.dataset_manifest_id,
                dataset_version: receipt.dataset_version,
                control_plane_mode: receipt.control_plane_mode,
                stages: {{
                  'candidate-student': receipt.stages['candidate-student']
                }}
              }};
            }})()
            """
        ).strip()
        result = self._run_node(payload_expression)

        self.assertEqual(result['runIds'], ['run-eval-001-student'])
        self.assertEqual(result['scoredRunIds'], [])
        self.assertEqual(result['latestRunId'], 'run-eval-001-student')
        self.assertIsNone(result['latestScoredRunId'])
        self.assertEqual(result['latestStudentViewRunId'], 'run-eval-001-student')
        self.assertEqual(result['latestScoreSummary'], 'No scored live runs yet')
        self.assertEqual(result['candidateResults'], 0)
        self.assertFalse(result['studentHasScorecard'])
        self.assertEqual(result['alphaComparisonVerdict'], None)
        self.assertEqual(result['alphaTotalScoreDelta'], None)
        self.assertEqual(result['trainingScenarioCount'], 3)
        self.assertEqual(result['holdoutScenarioCount'], 0)
        self.assertEqual(
            result['latestStudentVisibleLabels'],
            [
                'Show why Run 2 is better with concrete deltas',
                'Make the proof bundle legible at a glance',
                'Promote one failed theme into public curriculum safely',
            ],
        )
        self.assertEqual(result['artifactRunIds'], ['run-eval-001-student'])
        self.assertEqual(result['replayRunIds'], ['run-eval-001-student'])
        self.assertEqual(result['alphaStageKeys'], ['candidate-student'])
        self.assertIsNone(result['alphaSealingStatus'])
        self.assertEqual(result['alphaSealingBlockedClaims'], [])
        self.assertEqual(result['alphaSealingUnmetPrerequisites'], [])


if __name__ == '__main__':
    unittest.main()
