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
              comparisonRunId: store.comparisonRunId('run-eval-002'),
              latestScoreSummary: store.latestScoreSummary(),
              overallDelta: store.scoreDelta('run-eval-002'),
              holdoutDelta: store.scoreDelta('run-eval-002', null, 'holdout'),
              candidateResults: store.resultsForRun('run-eval-002').length,
              studentHasScorecard: Boolean(store.getScorecard('run-eval-001-student')),
              candidateTeacherSummary: store.teacherSummaryForRun('run-eval-002'),
              latestFailureThemes: (store.latestIteration()?.failure_themes || []).map(theme => theme.theme),
              latestStudentPrompt: store.getStudentView(store.latestStudentViewRunId())?.prompt_summary || null,
              artifactRunIds: Object.keys(store.artifacts).sort(),
              replayRunIds: Object.keys(store.run_replays).sort(),
              sourceMode: store.sourceMode,
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
        self.assertEqual(result['comparisonRunId'], 'run-eval-001')
        self.assertEqual(result['overallDelta'], 4)
        self.assertEqual(result['holdoutDelta'], 2)
        self.assertEqual(result['candidateResults'], 9)
        self.assertFalse(result['studentHasScorecard'])
        self.assertIn('materially better', result['candidateTeacherSummary'])
        self.assertIn('Proof bundle over vibes', result['latestFailureThemes'])
        self.assertIn('public curriculum plus promoted failure themes only', result['latestStudentPrompt'])
        self.assertEqual(result['artifactRunIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['replayRunIds'], ['run-eval-001', 'run-eval-001-student', 'run-eval-002'])
        self.assertEqual(result['sourceMode'], 'live')

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
        self.assertEqual(result['comparisonRunId'], 'run-eval-001')
        self.assertEqual(result['overallDelta'], 4)
        self.assertFalse(result['studentHasScorecard'])


if __name__ == '__main__':
    unittest.main()
