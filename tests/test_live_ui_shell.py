import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
APP_JS = APP / 'app.js'
PAGES = ['index.html', 'scenarios.html', 'run.html', 'scorecard.html']


class LiveUiShellMarkupTests(unittest.TestCase):
    def test_pages_load_runtime_config_and_mode_controls(self):
        for page in PAGES:
            text = (APP / page).read_text()
            self.assertIn('config.js', text, f'{page} should load app/config.js')
            self.assertIn("switchMode('live')", text, f'{page} should expose the live-shell toggle')
            self.assertIn('pageHref(', text, f'{page} should preserve mode params in nav links')
            self.assertIn('modeBannerText()', text, f'{page} should render the shared mode banner')

    def test_config_file_exists_and_defaults_to_demo(self):
        text = (APP / 'config.js').read_text()
        self.assertIn("defaultMode: 'demo'", text)
        self.assertIn('liveDataUrl: null', text)
        self.assertIn('Clawith live shell', text)

    def test_live_ui_pages_no_longer_hardcode_demo_run_ids(self):
        run_text = (APP / 'run.html').read_text()
        scorecard_text = (APP / 'scorecard.html').read_text()
        index_text = (APP / 'index.html').read_text()

        self.assertNotIn("detailRun === 'run-002'", run_text)
        self.assertNotIn("selectedRun === 'run-002'", scorecard_text)
        self.assertNotIn('Compare to Run 1', scorecard_text)
        self.assertNotIn("scores['run-002']", index_text)


class LiveUiShellContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = APP_JS.read_text()

    def test_shared_app_store_has_live_shell_seam(self):
        required = [
            'resolveRequestedMode',
            'resolveLiveDataUrl',
            'normalizeAppData',
            'loadLiveSnapshot',
            'switchMode',
            'modeBannerText',
            'comparisonRunId',
            'latestRunId',
            'pageHref',
        ]
        for needle in required:
            self.assertIn(needle, self.text)

    def test_live_snapshot_fetch_is_explicit_and_cache_busted(self):
        self.assertIn('fetch(this.liveShell.endpoint, { cache: \'no-store\' })', self.text)
        self.assertIn("status: 'connected'", self.text)

    def test_failed_live_snapshot_falls_back_to_demo_honestly(self):
        self.assertIn('const fallback = normalizeAppData(DEMO_DATA, \'demo\')', self.text)
        self.assertIn("sourceMode: 'demo'", self.text)
        self.assertIn("requestedMode: 'live'", self.text)
        self.assertIn("status: 'error'", self.text)
        self.assertIn('Demo data remains visible and is clearly labeled as demo.', self.text)

    def test_shared_logic_uses_relative_run_comparison_not_fixed_ids(self):
        self.assertNotIn('run-001', self.text)
        self.assertNotIn('run-002', self.text)
        self.assertIn('previousRun(runId)', self.text)
        self.assertIn('comparisonRunId(runId)', self.text)


if __name__ == '__main__':
    unittest.main()
