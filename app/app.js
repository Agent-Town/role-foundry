// Role Foundry — Shared app logic (Alpine.js)

document.addEventListener('alpine:init', () => {
  Alpine.store('app', {
    ...DEMO_DATA,

    // Helpers
    getScenario(id) {
      return this.scenarios.find(s => s.id === id);
    },

    getRun(id) {
      return this.runs.find(run => run.id === id);
    },

    getScorecard(runId) {
      return this.scores[runId] || null;
    },

    getIteration(runId) {
      return this.iterations.find(iter => iter.to_run === runId) || null;
    },

    getArtifact(runId) {
      return this.artifacts?.[runId] || null;
    },

    getRunReplay(runId) {
      return this.run_replays?.[runId] || [];
    },

    trainingScenarios() {
      return this.scenarios.filter(s => s.type === 'training');
    },

    holdoutScenarios() {
      return this.scenarios.filter(s => s.type === 'holdout');
    },

    resultsForRun(runId) {
      return this.getScorecard(runId)?.results || [];
    },

    resultsByType(runId, type) {
      return this.resultsForRun(runId).filter(result => this.getScenario(result.scenario_id)?.type === type);
    },

    passCount(runId, type = null) {
      const results = type ? this.resultsByType(runId, type) : this.resultsForRun(runId);
      return results.filter(result => result.passed).length;
    },

    passRate(runId, type = null) {
      const results = type ? this.resultsByType(runId, type) : this.resultsForRun(runId);
      if (!results.length) return 0;
      return this.passCount(runId, type) / results.length;
    },

    scoreDelta(currentRunId, previousRunId = 'run-001', type = null) {
      return this.passCount(currentRunId, type) - this.passCount(previousRunId, type);
    },

    passRateDelta(currentRunId, previousRunId = 'run-001', type = null) {
      return this.passRate(currentRunId, type) - this.passRate(previousRunId, type);
    },

    formatDuration(sec) {
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      return `${m}m ${s}s`;
    },

    formatCost(usd) {
      return `$${usd.toFixed(2)}`;
    },

    formatDate(iso) {
      return new Date(iso).toLocaleString();
    },

    formatPercent(value) {
      return `${Math.round(value * 100)}%`;
    },

    formatSigned(value, decimals = 0, suffix = '') {
      const num = Number(value || 0);
      const sign = num > 0 ? '+' : num < 0 ? '−' : '';
      const abs = Math.abs(num);
      const rounded = decimals > 0 ? abs.toFixed(decimals) : Math.round(abs).toString();
      return `${sign}${rounded}${suffix}`;
    },
  });
});

// Nav component — highlights current page
function navComponent() {
  return {
    currentPage: window.location.pathname.split('/').pop() || 'index.html',
    isActive(page) {
      return this.currentPage === page;
    },
  };
}
