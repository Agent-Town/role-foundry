// Role Foundry — Shared app logic (Alpine.js)

const ROLE_FOUNDRY_STORAGE_KEYS = Object.freeze({
  mode: 'roleFoundry.mode',
  liveDataUrl: 'roleFoundry.liveDataUrl',
});

const ROLE_FOUNDRY_DEFAULT_CONFIG = Object.freeze({
  defaultMode: 'demo',
  liveDataUrl: null,
  liveLabel: 'Clawith live shell',
});

function cloneRoleFoundryData(value) {
  if (typeof structuredClone === 'function') {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function roleFoundryConfig() {
  return {
    ...ROLE_FOUNDRY_DEFAULT_CONFIG,
    ...(window.ROLE_FOUNDRY_CONFIG || {}),
  };
}

function safeStorageRead(key) {
  try {
    return window.localStorage?.getItem(key) || null;
  } catch (_error) {
    return null;
  }
}

function safeStorageWrite(key, value) {
  try {
    if (value === null || value === undefined || value === '') {
      window.localStorage?.removeItem(key);
      return;
    }
    window.localStorage?.setItem(key, String(value));
  } catch (_error) {
    // Ignore storage failures in private/incognito contexts.
  }
}

function roleFoundryUrlState() {
  const url = new URL(window.location.href);
  return {
    mode: url.searchParams.get('mode'),
    liveDataUrl: url.searchParams.get('liveDataUrl'),
  };
}

function normalizeRequestedMode(mode) {
  return mode === 'live' ? 'live' : 'demo';
}

function resolveRequestedMode(config) {
  const urlState = roleFoundryUrlState();
  const storedMode = safeStorageRead(ROLE_FOUNDRY_STORAGE_KEYS.mode);
  return normalizeRequestedMode(urlState.mode || storedMode || config.defaultMode || 'demo');
}

function resolveLiveDataUrl(config) {
  const urlState = roleFoundryUrlState();
  const storedUrl = safeStorageRead(ROLE_FOUNDRY_STORAGE_KEYS.liveDataUrl);
  return urlState.liveDataUrl || config.liveDataUrl || storedUrl || null;
}

function ensureObject(value, label) {
  if (value === undefined || value === null) {
    return;
  }
  if (typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
}

function ensureArray(value, label) {
  if (value === undefined || value === null) {
    return;
  }
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`);
  }
}

function validateSnapshotShape(payload) {
  ensureObject(payload, 'snapshot');
  ensureObject(payload.role, 'role');
  ensureArray(payload.scenarios, 'scenarios');
  ensureArray(payload.runs, 'runs');
  ensureObject(payload.scores, 'scores');
  ensureArray(payload.iterations, 'iterations');
  ensureObject(payload.artifacts, 'artifacts');
  ensureObject(payload.run_replays, 'run_replays');
}

function defaultRoleForMode(mode) {
  if (mode === 'live') {
    return {
      name: 'Frontend Apprentice',
      subtitle: 'Live UI shell',
      description:
        'The live shell is ready to render Clawith-backed snapshots when a real endpoint is configured. Until then, the demo remains the honest default.',
      teachers: ['Robin', 'Neo'],
      demo_contract: 'Live shell only. No fake Clawith capability is implied.',
      goals: [],
      success_criteria: [],
    };
  }

  return cloneRoleFoundryData(DEMO_DATA.role);
}

function createDataSkeleton(mode) {
  return {
    mode,
    role: defaultRoleForMode(mode),
    scenarios: [],
    runs: [],
    scores: {},
    iterations: [],
    artifacts: {},
    run_replays: {},
  };
}

function normalizeRole(role, mode) {
  const base = defaultRoleForMode(mode);
  if (!role || typeof role !== 'object' || Array.isArray(role)) {
    return base;
  }

  return {
    ...base,
    ...role,
    teachers: Array.isArray(role.teachers) ? role.teachers : base.teachers,
    goals: Array.isArray(role.goals) ? role.goals : base.goals,
    success_criteria: Array.isArray(role.success_criteria)
      ? role.success_criteria
      : base.success_criteria,
  };
}

function normalizeRuns(runs) {
  return (Array.isArray(runs) ? runs : []).filter(run => run && typeof run === 'object' && run.id);
}

function normalizeScenarios(scenarios) {
  return (Array.isArray(scenarios) ? scenarios : []).filter(
    scenario => scenario && typeof scenario === 'object' && scenario.id
  );
}

function normalizeIterations(iterations) {
  return (Array.isArray(iterations) ? iterations : []).filter(
    iteration => iteration && typeof iteration === 'object' && iteration.to_run
  );
}

function normalizeRecord(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function normalizeAppData(payload, mode) {
  validateSnapshotShape(payload);

  const base = mode === 'demo' ? cloneRoleFoundryData(DEMO_DATA) : createDataSkeleton(mode);

  return {
    ...base,
    ...payload,
    mode,
    role: normalizeRole(payload.role ?? base.role, mode),
    scenarios: normalizeScenarios(payload.scenarios ?? base.scenarios),
    runs: normalizeRuns(payload.runs ?? base.runs),
    scores: normalizeRecord(payload.scores ?? base.scores),
    iterations: normalizeIterations(payload.iterations ?? base.iterations),
    artifacts: normalizeRecord(payload.artifacts ?? base.artifacts),
    run_replays: normalizeRecord(payload.run_replays ?? base.run_replays),
  };
}

function liveShellState(config, requestedMode, liveDataUrl) {
  const configured = Boolean(liveDataUrl);
  return {
    label: config.liveLabel,
    configured,
    endpoint: liveDataUrl,
    status: requestedMode === 'live' ? (configured ? 'loading' : 'missing-endpoint') : 'idle',
    lastError: null,
  };
}

function createAppStore(config) {
  const requestedMode = resolveRequestedMode(config);
  const liveDataUrl = resolveLiveDataUrl(config);
  const initialData = normalizeAppData(DEMO_DATA, 'demo');

  return {
    ...initialData,
    sourceMode: 'demo',
    requestedMode,
    loading: false,
    ready: Promise.resolve(),
    liveShell: liveShellState(config, requestedMode, liveDataUrl),

    applySnapshot(snapshot, meta = {}) {
      Object.assign(this, snapshot);
      this.sourceMode = meta.sourceMode ?? this.sourceMode;
      this.requestedMode = meta.requestedMode ?? this.requestedMode;
      this.loading = meta.loading ?? this.loading;
      this.liveShell = {
        ...this.liveShell,
        status: meta.status ?? this.liveShell.status,
        lastError:
          meta.lastError === undefined ? this.liveShell.lastError : meta.lastError,
        configured: meta.configured ?? this.liveShell.configured,
        endpoint: meta.endpoint ?? this.liveShell.endpoint,
      };
    },

    async initialize() {
      if (this.requestedMode !== 'live') {
        return;
      }

      if (!this.liveShell.configured || !this.liveShell.endpoint) {
        this.liveShell.status = 'missing-endpoint';
        return;
      }

      await this.loadLiveSnapshot();
    },

    async loadLiveSnapshot() {
      this.loading = true;
      this.liveShell.status = 'loading';
      this.liveShell.lastError = null;

      try {
        const response = await fetch(this.liveShell.endpoint, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`Live snapshot request failed with ${response.status}`);
        }

        const payload = await response.json();
        const snapshot = normalizeAppData(payload, 'live');
        this.applySnapshot(snapshot, {
          sourceMode: 'live',
          requestedMode: 'live',
          loading: false,
          status: 'connected',
          configured: true,
          endpoint: this.liveShell.endpoint,
          lastError: null,
        });
      } catch (error) {
        const fallback = normalizeAppData(DEMO_DATA, 'demo');
        this.applySnapshot(fallback, {
          sourceMode: 'demo',
          requestedMode: 'live',
          loading: false,
          status: 'error',
          configured: Boolean(this.liveShell.endpoint),
          endpoint: this.liveShell.endpoint,
          lastError: error?.message || 'Failed to load live snapshot',
        });
      }
    },

    switchMode(mode) {
      const nextMode = normalizeRequestedMode(mode);
      const url = new URL(window.location.href);
      url.searchParams.set('mode', nextMode);
      if (this.liveShell.endpoint) {
        url.searchParams.set('liveDataUrl', this.liveShell.endpoint);
      } else {
        url.searchParams.delete('liveDataUrl');
      }
      safeStorageWrite(ROLE_FOUNDRY_STORAGE_KEYS.mode, nextMode);
      safeStorageWrite(ROLE_FOUNDRY_STORAGE_KEYS.liveDataUrl, this.liveShell.endpoint);
      window.location.assign(url.toString());
    },

    // Helpers
    getScenario(id) {
      return this.scenarios.find(scenario => scenario.id === id) || null;
    },

    getRun(id) {
      return this.runs.find(run => run.id === id) || null;
    },

    orderedRuns() {
      return [...this.runs].sort((a, b) => {
        if (Number.isFinite(a.iteration) && Number.isFinite(b.iteration) && a.iteration !== b.iteration) {
          return a.iteration - b.iteration;
        }

        const aStarted = a.started_at ? Date.parse(a.started_at) : NaN;
        const bStarted = b.started_at ? Date.parse(b.started_at) : NaN;
        if (Number.isFinite(aStarted) && Number.isFinite(bStarted) && aStarted !== bStarted) {
          return aStarted - bStarted;
        }

        return String(a.id).localeCompare(String(b.id));
      });
    },

    baselineRun() {
      return this.orderedRuns()[0] || null;
    },

    latestRun() {
      const runs = this.orderedRuns();
      return runs[runs.length - 1] || null;
    },

    latestRunId() {
      return this.latestRun()?.id || null;
    },

    previousRun(runId) {
      const runs = this.orderedRuns();
      const currentIndex = runs.findIndex(run => run.id === runId);
      if (currentIndex <= 0) {
        return null;
      }
      return runs[currentIndex - 1] || null;
    },

    comparisonRunId(runId) {
      return this.previousRun(runId)?.id || null;
    },

    hasComparisonRun(runId) {
      return Boolean(this.comparisonRunId(runId));
    },

    getActor(role) {
      return this.actors?.[role] || null;
    },

    getScorecard(runId) {
      return this.scores?.[runId] || null;
    },

    getStudentView(runId) {
      return this.student_views?.[runId] || null;
    },

    getIteration(runId) {
      return this.iterations.find(iteration => iteration.to_run === runId) || null;
    },

    latestIteration() {
      return this.latestRunId() ? this.getIteration(this.latestRunId()) : null;
    },

    getArtifact(runId) {
      return this.artifacts?.[runId] || null;
    },

    getRunReplay(runId) {
      return this.run_replays?.[runId] || [];
    },

    hasRunReplay(runId) {
      return this.getRunReplay(runId).length > 0;
    },

    getTeacherForRun(runId) {
      const scorecard = this.getScorecard(runId);
      if (!scorecard?.judged_by) return null;
      return Object.values(this.actors || {}).find(actor => actor.id === scorecard.judged_by) || null;
    },

    iterationTimeline() {
      return this.runs.map((run, index) => {
        const scorecard = this.getScorecard(run.id);
        const previousRun = index > 0 ? this.runs[index - 1] : null;
        const previousScorecard = previousRun ? this.getScorecard(previousRun.id) : null;
        return {
          run_id: run.id,
          iteration: run.iteration,
          aggregate_score: scorecard?.aggregate_score || null,
          delta: previousScorecard
            ? {
                overall: (scorecard?.aggregate_score?.passed || 0) - (previousScorecard?.aggregate_score?.passed || 0),
                holdout:
                  (scorecard?.aggregate_score?.holdout?.passed || 0)
                  - (previousScorecard?.aggregate_score?.holdout?.passed || 0),
                pass_rate_points: Math.round(((scorecard?.aggregate_score?.pass_rate || 0) - (previousScorecard?.aggregate_score?.pass_rate || 0)) * 100),
              }
            : null,
        };
      });
    },

    trainingScenarios() {
      return this.scenarios.filter(scenario => scenario.type === 'training');
    },

    holdoutScenarios() {
      return this.scenarios.filter(scenario => scenario.type === 'holdout');
    },

    resultsForRun(runId) {
      return this.getScorecard(runId)?.results || [];
    },

    resultsByType(runId, type) {
      return this.resultsForRun(runId).filter(
        result => this.getScenario(result.scenario_id)?.type === type
      );
    },

    passCount(runId, type = null) {
      const results = type ? this.resultsByType(runId, type) : this.resultsForRun(runId);
      return results.filter(result => result.passed).length;
    },

    passRate(runId, type = null) {
      const results = type ? this.resultsByType(runId, type) : this.resultsForRun(runId);
      if (!results.length) return null;
      return this.passCount(runId, type) / results.length;
    },

    scoreDelta(currentRunId, previousRunId = null, type = null) {
      const baselineId = previousRunId || this.comparisonRunId(currentRunId);
      if (!currentRunId || !baselineId) return null;
      return this.passCount(currentRunId, type) - this.passCount(baselineId, type);
    },

    passRateDelta(currentRunId, previousRunId = null, type = null) {
      const baselineId = previousRunId || this.comparisonRunId(currentRunId);
      const currentRate = this.passRate(currentRunId, type);
      const baselineRate = this.passRate(baselineId, type);
      if (currentRate === null || baselineRate === null) return null;
      return currentRate - baselineRate;
    },

    scoreForScenario(runId, scenarioId) {
      return this.getScorecard(runId)?.results.find(result => result.scenario_id === scenarioId)?.score ?? null;
    },

    getRunLabel(runId) {
      return this.getRun(runId)?.label || runId || '—';
    },

    getRunShortLabel(runId) {
      const label = this.getRunLabel(runId);
      return label.includes('—') ? label.split('—')[0].trim() : label;
    },

    latestScoreSummary() {
      const runId = this.latestRunId();
      const scorecard = runId ? this.getScorecard(runId) : null;
      if (!scorecard) {
        return this.sourceMode === 'live' ? 'No scored live runs yet' : 'No scored runs yet';
      }
      return `${scorecard.overall}/${scorecard.total} (${this.formatPercent(scorecard.pass_rate)})`;
    },

    sourceSummaryLabel() {
      if (this.sourceMode === 'live') {
        return this.liveShell.label;
      }
      return 'Demo seed data';
    },

    sourceSummaryDetail() {
      if (this.sourceMode === 'live') {
        return this.liveShell.endpoint || 'Configured live snapshot';
      }
      return 'Static apprentice dataset. Honest fallback when no live endpoint is wired.';
    },

    modeBadgeLabel() {
      if (this.sourceMode === 'live') {
        return 'LIVE SHELL';
      }
      if (this.requestedMode === 'live') {
        return 'LIVE SHELL (FALLBACK)';
      }
      return 'DEMO MODE';
    },

    modeBannerTone() {
      if (this.sourceMode === 'live') return 'tone-live';
      if (this.requestedMode === 'live' && this.liveShell.status === 'error') return 'tone-error';
      if (this.requestedMode === 'live') return 'tone-warning';
      return 'tone-demo';
    },

    modeBannerText() {
      if (this.sourceMode === 'live') {
        return 'Rendering a configured live snapshot. If fields are missing, the UI stays empty rather than inventing them.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'loading') {
        return 'Loading a live snapshot. Demo data remains visible until a real response arrives.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'missing-endpoint') {
        return 'Live shell requested, but no liveDataUrl is configured. Demo data remains the honest fallback.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'error') {
        return 'Live shell requested, but the snapshot failed to load. Demo data remains visible and is clearly labeled as demo.';
      }

      return 'Static, judge-friendly apprentice data. No auth theater. No fake live wiring.';
    },

    replayStatusText(runId) {
      if (!runId) {
        return 'Select a run to inspect its receipts.';
      }
      if (this.hasRunReplay(runId)) {
        return 'Scripted replay available for this run.';
      }
      if (this.sourceMode === 'live') {
        return 'No replay exported yet. The live shell will render replays when the control plane emits them.';
      }
      return 'No replay lines recorded for this run.';
    },

    formatDuration(sec) {
      if (!Number.isFinite(sec)) return '—';
      const m = Math.floor(sec / 60);
      const s = sec % 60;
      return `${m}m ${s}s`;
    },

    formatCost(usd) {
      if (!Number.isFinite(usd)) return '—';
      return `$${usd.toFixed(2)}`;
    },

    formatDate(iso) {
      if (!iso) return '—';
      return new Date(iso).toLocaleString();
    },

    formatPercent(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
      return `${Math.round(Number(value) * 100)}%`;
    },

    formatSigned(value, decimals = 0, suffix = '') {
      if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return '—';
      }
      const num = Number(value || 0);
      const sign = num > 0 ? '+' : num < 0 ? '−' : '';
      const abs = Math.abs(num);
      const rounded = decimals > 0 ? abs.toFixed(decimals) : Math.round(abs).toString();
      return `${sign}${rounded}${suffix}`;
    },
  };
}

document.addEventListener('alpine:init', () => {
  const store = createAppStore(roleFoundryConfig());
  Alpine.store('app', store);
  store.ready = store.initialize();
});

// Nav component — highlights current page and preserves mode query params
function navComponent() {
  const currentUrl = new URL(window.location.href);

  return {
    currentPage: currentUrl.pathname.split('/').pop() || 'index.html',
    isActive(page) {
      return this.currentPage === page;
    },
    pageHref(page) {
      const url = new URL(page, currentUrl);
      const mode = currentUrl.searchParams.get('mode');
      const liveDataUrl = currentUrl.searchParams.get('liveDataUrl');
      if (mode) url.searchParams.set('mode', mode);
      if (liveDataUrl) url.searchParams.set('liveDataUrl', liveDataUrl);
      return `${url.pathname.split('/').pop()}${url.search}`;
    },
  };
}
