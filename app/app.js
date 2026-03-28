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

const ROLE_FOUNDRY_UI_SNAPSHOT_KEYS = Object.freeze([
  'role',
  'actors',
  'scenarios',
  'runs',
  'scores',
  'student_views',
  'iterations',
  'artifacts',
  'run_replays',
]);

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

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function hasAnyOwnKey(value, keys) {
  return keys.some(key => Object.prototype.hasOwnProperty.call(value, key));
}

function normalizeNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizeRecord(value) {
  return isPlainObject(value) ? value : {};
}

function normalizeStringList(value) {
  return (Array.isArray(value) ? value : [])
    .map(item => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean);
}

function normalizeThemeSummaryList(value) {
  return (Array.isArray(value) ? value : [])
    .map(item => {
      if (typeof item === 'string') {
        return item;
      }
      if (!isPlainObject(item)) {
        return '';
      }
      return item.theme || item.title || item.description || '';
    })
    .filter(Boolean);
}

function normalizeFailureThemes(value) {
  return (Array.isArray(value) ? value : [])
    .map(theme => {
      if (typeof theme === 'string') {
        return {
          theme,
          description: '',
          source_scenarios: [],
        };
      }
      if (!isPlainObject(theme)) {
        return null;
      }
      const title = theme.theme || theme.title || theme.label;
      const description = theme.description || theme.summary || '';
      if (!title && !description) {
        return null;
      }
      return {
        theme: String(title || description || 'Theme'),
        description: String(description || ''),
        source_scenarios: normalizeStringList(theme.source_scenarios),
      };
    })
    .filter(Boolean);
}

function normalizeVisibleScenarioIds(value) {
  return (Array.isArray(value) ? value : [])
    .map(item => {
      if (typeof item === 'string') {
        return item;
      }
      if (isPlainObject(item) && item.id) {
        return String(item.id);
      }
      return null;
    })
    .filter(Boolean);
}

function normalizeChangedFiles(value) {
  return (Array.isArray(value) ? value : [])
    .map(file => {
      if (typeof file === 'string') {
        return { path: file, summary: '' };
      }
      if (isPlainObject(file) && file.path) {
        return {
          path: String(file.path),
          summary: typeof file.summary === 'string' ? file.summary : '',
        };
      }
      return null;
    })
    .filter(Boolean);
}

function normalizeTranscriptExcerpt(value) {
  return (Array.isArray(value) ? value : [])
    .map(line => {
      if (typeof line === 'string') {
        return { speaker: 'log', text: line };
      }
      if (!isPlainObject(line)) {
        return null;
      }
      if (typeof line.speaker === 'string' && typeof line.text === 'string') {
        return { speaker: line.speaker, text: line.text };
      }
      const speaker = line.event || line.speaker || line.role || line.kind;
      const text = line.message || line.text;
      if (!speaker && !text) {
        return null;
      }
      return {
        speaker: String(speaker || 'log'),
        text: String(text || ''),
      };
    })
    .filter(Boolean);
}

function normalizeReplayLines(value) {
  return (Array.isArray(value) ? value : [])
    .map((line, index) => {
      if (typeof line === 'string') {
        return { t: index * 500, msg: line };
      }
      if (!isPlainObject(line)) {
        return null;
      }

      let msg = null;
      if (typeof line.msg === 'string') {
        msg = line.msg;
      } else if (typeof line.message === 'string' && typeof line.event === 'string') {
        msg = `${line.event} — ${line.message}`;
      } else if (typeof line.message === 'string') {
        msg = line.message;
      } else if (typeof line.text === 'string' && typeof line.speaker === 'string') {
        msg = `${line.speaker}: ${line.text}`;
      } else if (typeof line.text === 'string') {
        msg = line.text;
      } else if (typeof line.event === 'string') {
        msg = line.event;
      }

      if (!msg) {
        return null;
      }

      return {
        t: normalizeNumber(line.t) ?? index * 500,
        msg,
      };
    })
    .filter(Boolean);
}

function maybeDurationFromTimes(startedAt, finishedAt) {
  if (!startedAt || !finishedAt) {
    return null;
  }
  const started = Date.parse(startedAt);
  const finished = Date.parse(finishedAt);
  if (!Number.isFinite(started) || !Number.isFinite(finished)) {
    return null;
  }
  return Math.max(0, Math.round((finished - started) / 1000));
}

function normalizePublicActor(actor, defaultRole = null) {
  if (!isPlainObject(actor)) {
    return null;
  }

  const name = actor.name || actor.label || (defaultRole ? defaultRole.replace(/(^|[-_\s])(\w)/g, (_m, p1, p2) => `${p1}${p2.toUpperCase()}`) : null);
  if (!actor.id && !name) {
    return null;
  }

  return {
    ...actor,
    id: actor.id || null,
    name: name || 'Unknown',
    agent_role: actor.agent_role || defaultRole || null,
  };
}

function normalizeUiScorecardShape(value) {
  if (!isPlainObject(value)) {
    return null;
  }

  let rawResults = [];
  if (Array.isArray(value.results)) {
    rawResults = value.results;
  } else if (Array.isArray(value.scenario_results)) {
    rawResults = value.scenario_results;
  }

  const results = rawResults
    .map(result => {
      if (!isPlainObject(result) || !result.scenario_id) {
        return null;
      }
      return {
        scenario_id: String(result.scenario_id),
        passed: Boolean(result.passed),
        score: normalizeNumber(result.score),
        notes:
          typeof result.notes === 'string'
            ? result.notes
            : (typeof result.teacher_notes === 'string' ? result.teacher_notes : ''),
      };
    })
    .filter(Boolean);

  const aggregate = normalizeRecord(value.aggregate_score);
  const overall =
    normalizeNumber(value.overall) ??
    normalizeNumber(aggregate.passed) ??
    (results.length ? results.filter(result => result.passed).length : null);
  const total =
    normalizeNumber(value.total) ??
    normalizeNumber(aggregate.total) ??
    (results.length ? results.length : null);
  const passRate =
    normalizeNumber(value.pass_rate) ??
    normalizeNumber(aggregate.pass_rate) ??
    (overall !== null && total ? overall / total : null);

  if (overall === null && total === null && passRate === null && !results.length) {
    return null;
  }

  return {
    judged_by: value.judged_by || value.teacher?.id || value.actor?.id || null,
    teacher_summary:
      typeof value.teacher_summary === 'string'
        ? value.teacher_summary
        : (typeof value.verdict === 'string' ? value.verdict : ''),
    overall,
    total,
    pass_rate: passRate,
    aggregate_score: Object.keys(aggregate).length ? aggregate : {
      passed: overall,
      total,
      pass_rate: passRate,
    },
    results,
  };
}

function looksLikeUiSnapshotPayload(payload) {
  return isPlainObject(payload) && hasAnyOwnKey(payload, ROLE_FOUNDRY_UI_SNAPSHOT_KEYS);
}

function looksLikeLiveReadModelPayload(payload) {
  return isPlainObject(payload) && isPlainObject(payload.control_plane_summary);
}

function looksLikeSingleRunExport(payload) {
  if (!isPlainObject(payload)) {
    return false;
  }

  return (
    isPlainObject(payload.run) ||
    isPlainObject(payload.result) ||
    isPlainObject(payload.artifact_bundle) ||
    Boolean(payload.run_id && isPlainObject(payload.workspace_snapshot))
  );
}

function looksLikeAutoresearchAlphaPayload(payload) {
  if (!isPlainObject(payload)) {
    return false;
  }

  // Rich envelope shape (sample/export format)
  if (payload.flow === 'autoresearch-alpha' && isPlainObject(payload.stages)) {
    return true;
  }

  // Real executable receipt shape from runner_bridge.autoresearch_alpha
  if (payload.receipt_type === 'autoresearch-alpha' && isPlainObject(payload.stages)) {
    return true;
  }

  // Nested envelope (outer wrapper with .autoresearch_alpha sub-object)
  if (isPlainObject(payload.autoresearch_alpha)) {
    const inner = payload.autoresearch_alpha;
    if (
      (inner.flow === 'autoresearch-alpha' || inner.receipt_type === 'autoresearch-alpha') &&
      isPlainObject(inner.stages)
    ) {
      return true;
    }
  }

  return false;
}

function validateSnapshotShape(payload) {
  ensureObject(payload, 'snapshot');
  ensureObject(payload.role, 'role');
  ensureObject(payload.actors, 'actors');
  ensureArray(payload.scenarios, 'scenarios');
  ensureArray(payload.runs, 'runs');
  ensureObject(payload.scores, 'scores');
  ensureObject(payload.student_views, 'student_views');
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
        'The live shell renders configured read-only snapshots or runtime receipt exports when they exist. Missing fields stay empty instead of being invented.',
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
    actors: {},
    scenarios: [],
    runs: [],
    scores: {},
    student_views: {},
    iterations: [],
    artifacts: {},
    run_replays: {},
  };
}

function normalizeRole(role, mode) {
  const base = defaultRoleForMode(mode);
  if (!isPlainObject(role)) {
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

function normalizeActors(actors) {
  const record = normalizeRecord(actors);
  return Object.fromEntries(
    Object.entries(record)
      .map(([key, actor]) => [key, normalizePublicActor(actor, key)])
      .filter(([, actor]) => Boolean(actor))
  );
}

function normalizeRuns(runs) {
  return (Array.isArray(runs) ? runs : [])
    .filter(run => isPlainObject(run) && run.id)
    .map(run => ({
      ...run,
      id: String(run.id),
      comparison_run_id: typeof run.comparison_run_id === 'string' ? run.comparison_run_id : null,
      sort_order: normalizeNumber(run.sort_order),
      iteration: normalizeNumber(run.iteration),
      duration_sec: normalizeNumber(run.duration_sec),
      cost_usd: normalizeNumber(run.cost_usd),
    }));
}

function normalizeScenarios(scenarios) {
  return (Array.isArray(scenarios) ? scenarios : []).filter(
    scenario => isPlainObject(scenario) && scenario.id
  );
}

function normalizeIterations(iterations) {
  return (Array.isArray(iterations) ? iterations : []).filter(
    iteration => isPlainObject(iteration) && iteration.to_run
  );
}

function normalizeStudentViews(studentViews) {
  const record = normalizeRecord(studentViews);
  return Object.fromEntries(
    Object.entries(record)
      .map(([runId, studentView]) => {
        const normalized = mapLiveStudentView(studentView);
        return normalized ? [runId, normalized] : null;
      })
      .filter(Boolean)
  );
}

function basenameish(value) {
  if (!value) {
    return null;
  }
  const text = String(value);
  return text.split('/').pop() || text;
}

function buildRuntimeJudgeReceipt(runId, runSummary, result, artifactBundle) {
  const lines = [];
  if (runSummary?.stage_label) {
    lines.push(`Stage: ${runSummary.stage_label}`);
  }
  if (runSummary?.label) {
    lines.push(`Run: ${runSummary.label}`);
  } else if (runId) {
    lines.push(`Run id: ${runId}`);
  }

  const status = runSummary?.status || result?.status || artifactBundle?.status;
  if (status) {
    lines.push(`Status: ${status}`);
  }

  const scenarioSetId = artifactBundle?.scenario_set_id || runSummary?.scenario_set_id;
  if (scenarioSetId) {
    lines.push(`Scenario set: ${scenarioSetId}`);
  }

  const transcriptReceipt = result?.transcript_path || artifactBundle?.receipts?.transcript_path;
  if (transcriptReceipt) {
    lines.push(`Transcript receipt: ${basenameish(transcriptReceipt)}`);
  }

  const artifactReceipt = result?.artifact_bundle_path || artifactBundle?.receipts?.artifact_bundle_path;
  if (artifactReceipt) {
    lines.push(`Artifact bundle receipt: ${basenameish(artifactReceipt)}`);
  }

  const resultReceipt = artifactBundle?.receipts?.result_path;
  if (resultReceipt) {
    lines.push(`Result receipt: ${basenameish(resultReceipt)}`);
  }

  const machineScore = normalizeNumber(result?.machine_score);
  if (machineScore !== null) {
    lines.push(`Machine score receipt: ${machineScore}`);
  }

  const error = result?.error || artifactBundle?.error;
  if (error) {
    lines.push(`Error: ${error}`);
  }

  return lines;
}

function mapLiveStudentView(studentView) {
  if (!isPlainObject(studentView)) {
    return null;
  }

  return {
    ...studentView,
    agent_role: studentView.agent_role || 'student',
    prompt_summary:
      typeof studentView.prompt_summary === 'string'
        ? studentView.prompt_summary
        : 'Train on the visible curriculum only. Hidden holdouts stay sealed.',
    visible_scenarios: normalizeVisibleScenarioIds(studentView.visible_scenarios),
    public_curriculum_themes: normalizeThemeSummaryList(studentView.public_curriculum_themes),
    sealed_holdout_count: normalizeNumber(studentView.sealed_holdout_count) ?? 0,
  };
}

function mapLiveArtifact(runId, entry, result, artifactBundle) {
  const workspaceSnapshot = normalizeRecord(entry.workspace_snapshot ?? artifactBundle?.workspace_snapshot);
  const objective =
    typeof entry.objective === 'string'
      ? entry.objective
      : (typeof workspaceSnapshot.objective === 'string' ? workspaceSnapshot.objective : '');
  const changedFiles = normalizeChangedFiles(entry.changed_files ?? workspaceSnapshot.changed_files);
  const policySnapshot = normalizeStringList(entry.policy_snapshot ?? workspaceSnapshot.policy_snapshot);
  const transcriptExcerpt = normalizeTranscriptExcerpt(
    entry.transcript_excerpt ?? artifactBundle?.transcript_excerpt ?? result?.transcript_excerpt
  );
  const judgeReceipt = normalizeStringList(entry.judge_receipt);
  const receiptSummary = judgeReceipt.length
    ? judgeReceipt
    : buildRuntimeJudgeReceipt(runId, entry.run || entry, result, artifactBundle);

  if (
    !objective &&
    !receiptSummary.length &&
    !changedFiles.length &&
    !policySnapshot.length &&
    !transcriptExcerpt.length
  ) {
    return null;
  }

  return {
    objective,
    judge_receipt: receiptSummary,
    policy_snapshot: policySnapshot,
    changed_files: changedFiles,
    transcript_excerpt: transcriptExcerpt,
  };
}

function mapLiveRunEntry(entry) {
  if (!isPlainObject(entry)) {
    return null;
  }

  const runSummary = normalizeRecord(entry.run);
  const result = normalizeRecord(entry.result);
  const artifactBundle = normalizeRecord(entry.artifact_bundle);
  const runId =
    runSummary.id ||
    runSummary.run_id ||
    entry.id ||
    entry.run_id ||
    artifactBundle.run_id ||
    result.run_id;

  if (!runId) {
    return null;
  }

  const startedAt = runSummary.started_at || result.started_at || null;
  const finishedAt = runSummary.finished_at || result.finished_at || null;
  const rawScorecard =
    entry.scorecard ||
    result.scorecard ||
    entry.teacher_scorecard ||
    entry.teacher_output ||
    artifactBundle.teacher_output ||
    (isPlainObject(entry.aggregate_score) ? {
      aggregate_score: entry.aggregate_score,
      total_score: entry.total_score,
      verdict: entry.verdict,
    } : null);
  const studentView = mapLiveStudentView(entry.student_view || artifactBundle.student_view);
  const scorecard = normalizeUiScorecardShape(rawScorecard);
  const teacherActor = normalizePublicActor(rawScorecard?.teacher || rawScorecard?.actor, 'teacher');
  const studentActor = normalizePublicActor(studentView?.actor || rawScorecard?.student, 'student');

  const run = {
    id: String(runId),
    label: runSummary.label || runSummary.title || entry.label || `Run ${runId}`,
    status: runSummary.status || result.status || artifactBundle.status || 'unknown',
    started_at: startedAt,
    finished_at: finishedAt,
    duration_sec: normalizeNumber(runSummary.duration_sec) ?? maybeDurationFromTimes(startedAt, finishedAt),
    cost_usd: normalizeNumber(runSummary.cost_usd) ?? normalizeNumber(result.cost_usd),
    runner: runSummary.runner || result.runner || entry.runner || rawScorecard?.runner || null,
    iteration: normalizeNumber(runSummary.iteration ?? entry.iteration),
    comparison_run_id:
      typeof runSummary.comparison_run_id === 'string'
        ? runSummary.comparison_run_id
        : (typeof entry.comparison_run_id === 'string' ? entry.comparison_run_id : null),
    stage_label:
      typeof runSummary.stage_label === 'string'
        ? runSummary.stage_label
        : (typeof entry.stage_label === 'string' ? entry.stage_label : null),
    sort_order: normalizeNumber(runSummary.sort_order ?? entry.sort_order),
  };

  return {
    run,
    scorecard,
    studentView,
    artifact: mapLiveArtifact(run.id, entry, result, artifactBundle),
    replay: normalizeReplayLines(
      entry.run_replay ??
      entry.replay_lines ??
      entry.transcript_events ??
      entry.transcript_excerpt ??
      artifactBundle.transcript_excerpt ??
      result.transcript_excerpt
    ),
    actors: {
      teacher: teacherActor,
      student: studentActor,
    },
  };
}

function mapLiveReadModelPayloadToSnapshot(payload) {
  const summary = normalizeRecord(payload.control_plane_summary ?? payload);
  const snapshot = createDataSkeleton('live');
  snapshot.mode = 'live';

  if (summary.role !== undefined) {
    snapshot.role = summary.role;
  }
  if (summary.actors !== undefined) {
    snapshot.actors = summary.actors;
  }
  if (summary.scenarios !== undefined) {
    snapshot.scenarios = summary.scenarios;
  }
  if (summary.student_views !== undefined) {
    snapshot.student_views = summary.student_views;
  }
  if (summary.iterations !== undefined) {
    snapshot.iterations = summary.iterations;
  }
  if (summary.scores !== undefined) {
    snapshot.scores = summary.scores;
  }
  if (summary.artifacts !== undefined) {
    snapshot.artifacts = summary.artifacts;
  }
  if (summary.run_replays !== undefined) {
    snapshot.run_replays = summary.run_replays;
  }

  (Array.isArray(summary.runs) ? summary.runs : [])
    .map(mapLiveRunEntry)
    .filter(Boolean)
    .forEach(mapped => {
      snapshot.runs.push(mapped.run);
      if (mapped.scorecard) {
        snapshot.scores[mapped.run.id] = mapped.scorecard;
      }
      if (mapped.studentView) {
        snapshot.student_views[mapped.run.id] = mapped.studentView;
      }
      if (mapped.artifact) {
        snapshot.artifacts[mapped.run.id] = mapped.artifact;
      }
      if (mapped.replay.length) {
        snapshot.run_replays[mapped.run.id] = mapped.replay;
      }
      if (mapped.actors.student && !snapshot.actors.student) {
        snapshot.actors.student = mapped.actors.student;
      }
      if (mapped.actors.teacher && !snapshot.actors.teacher) {
        snapshot.actors.teacher = mapped.actors.teacher;
      }
    });

  return snapshot;
}

function mapSingleRunExportToSnapshot(payload) {
  return mapLiveReadModelPayloadToSnapshot({
    control_plane_summary: {
      role: payload.role,
      scenarios: payload.scenarios,
      runs: [payload],
    },
  });
}

function mapAutoresearchAlphaPayloadToSnapshot(payload) {
  const envelope = normalizeRecord(payload.autoresearch_alpha ? payload : {});
  const receipt = normalizeRecord(payload.autoresearch_alpha || payload);
  const stageExports = {
    ...normalizeRecord(receipt.stage_exports),
    ...normalizeRecord(envelope.stage_exports),
  };
  const stages = normalizeRecord(receipt.stages);
  // Real receipt uses comparison_verdict; rich envelope uses comparison
  const comparison = normalizeRecord(receipt.comparison || receipt.comparison_verdict);
  const snapshot = createDataSkeleton('live');
  snapshot.mode = 'live';

  if (envelope.role !== undefined) {
    snapshot.role = envelope.role;
  }
  if (envelope.actors !== undefined) {
    snapshot.actors = envelope.actors;
  }
  if (envelope.scenarios !== undefined) {
    snapshot.scenarios = envelope.scenarios;
  }

  const orderedStages = [
    {
      key: 'baseline-eval',
      label: 'Baseline eval',
      fallbackIteration: 1,
    },
    {
      key: 'candidate-student',
      label: 'Candidate student',
      fallbackIteration: 2,
    },
    {
      key: 'candidate-teacher-eval',
      label: 'Candidate teacher eval',
      fallbackIteration: 3,
    },
  ];

  orderedStages.forEach((stageSpec, index) => {
    const stage = normalizeRecord(stages[stageSpec.key]);
    if (!Object.keys(stage).length) {
      return;
    }

    const stageExport = normalizeRecord(stage.export || stageExports[stageSpec.key]);
    const stageRun = normalizeRecord(stageExport.run);
    const runId = stage.run_id || stageRun.id || stageRun.run_id || stageExport.run_id;
    if (!runId) {
      return;
    }

    const fallbackScorecard = isPlainObject(stage.aggregate_score)
      ? {
          aggregate_score: stage.aggregate_score,
          total_score: stage.total_score,
          verdict: stage.verdict_text || (stageSpec.key === 'candidate-teacher-eval' ? (comparison.verdict || comparison.label) : undefined),
          scenario_results: [],
          public_curriculum_themes: stage.public_curriculum_themes,
        }
      : null;

    const comparisonRunId =
      stageSpec.key === 'candidate-teacher-eval'
        ? String(
            comparison.baseline_run_id || normalizeRecord(stages['baseline-eval']).run_id || ''
          ) || null
        : null;

    const mapped = mapLiveRunEntry({
      ...stageExport,
      stage_label: stageRun.stage_label || stageSpec.label,
      sort_order: stageRun.sort_order ?? index + 1,
      comparison_run_id: stageRun.comparison_run_id || comparisonRunId,
      run: {
        id: runId,
        label: stageRun.label || `${stageSpec.label} — ${runId}`,
        status: stageRun.status || stage.status || normalizeRecord(stageExport.result).status || 'unknown',
        started_at: stageRun.started_at || null,
        finished_at: stageRun.finished_at || null,
        duration_sec: stageRun.duration_sec,
        cost_usd: stageRun.cost_usd,
        runner:
          stageRun.runner ||
          normalizeRecord(stageExport.result).runner ||
          normalizeRecord(normalizeRecord(stageExport.result).scorecard).runner ||
          null,
        iteration:
          stageRun.iteration ||
          normalizeNumber(normalizeRecord(stage.lineage).iteration_index) ||
          stageSpec.fallbackIteration,
        stage_label: stageRun.stage_label || stageSpec.label,
        comparison_run_id: stageRun.comparison_run_id || comparisonRunId,
        sort_order: stageRun.sort_order ?? index + 1,
      },
      result: stageExport.result || {
        status: stage.status,
        machine_score: stage.total_score,
        scorecard: fallbackScorecard,
      },
      artifact_bundle: stageExport.artifact_bundle,
      student_view: stageExport.student_view,
      teacher_scorecard:
        stageExport.teacher_scorecard || stageExport.teacher_output || fallbackScorecard,
      transcript_excerpt: stageExport.transcript_excerpt,
      run_replay: stageExport.run_replay,
    });

    if (!mapped) {
      return;
    }

    snapshot.runs.push(mapped.run);
    if (mapped.scorecard) {
      snapshot.scores[mapped.run.id] = mapped.scorecard;
    }
    if (mapped.studentView) {
      snapshot.student_views[mapped.run.id] = mapped.studentView;
    }
    if (mapped.artifact) {
      snapshot.artifacts[mapped.run.id] = mapped.artifact;
    }
    if (mapped.replay.length) {
      snapshot.run_replays[mapped.run.id] = mapped.replay;
    }
    if (mapped.actors.student && !snapshot.actors.student) {
      snapshot.actors.student = mapped.actors.student;
    }
    if (mapped.actors.teacher && !snapshot.actors.teacher) {
      snapshot.actors.teacher = mapped.actors.teacher;
    }
  });

  const baselineRunId = comparison.baseline_run_id || normalizeRecord(stages['baseline-eval']).run_id || null;
  const candidateRunId = comparison.candidate_run_id || normalizeRecord(stages['candidate-teacher-eval']).run_id || null;
  const baselineScorecard = baselineRunId ? snapshot.scores[baselineRunId] : null;
  const candidateScorecard = candidateRunId ? snapshot.scores[candidateRunId] : null;
  const candidateStageExport = normalizeRecord(
    normalizeRecord(stages['candidate-teacher-eval']).export || stageExports['candidate-teacher-eval']
  );
  const candidateBundle = normalizeRecord(candidateStageExport.artifact_bundle);
  const candidateResultScorecard =
    normalizeRecord(normalizeRecord(candidateStageExport.result).scorecard) ||
    normalizeRecord(candidateStageExport.teacher_scorecard) ||
    normalizeRecord(candidateStageExport.teacher_output) ||
    normalizeRecord(candidateBundle.teacher_output);
  const failureThemes = normalizeFailureThemes(
    candidateResultScorecard.public_curriculum_themes || candidateBundle.public_curriculum_themes
  );
  const policyChanges = normalizeStringList(candidateBundle.workspace_snapshot?.policy_snapshot);
  const reasons = normalizeStringList(comparison.reasons);

  if (candidateRunId) {
    snapshot.iterations.push({
      from_run: baselineRunId,
      to_run: candidateRunId,
      label: 'Autoresearch alpha — candidate teacher eval',
      identity_snapshot:
        candidateScorecard?.teacher_summary ||
        ((comparison.verdict || comparison.label) ? `Teacher verdict: ${comparison.verdict || comparison.label}` : 'Teacher evaluation recorded.'),
      policy_changes: policyChanges,
      curriculum_notes:
        reasons.join(' ') ||
        'Read-only alpha-loop comparison receipt; missing fields stay empty instead of being invented.',
      failure_themes: failureThemes,
      score_delta:
        baselineScorecard && candidateScorecard
          ? {
              overall:
                (candidateScorecard.aggregate_score?.passed ?? candidateScorecard.overall ?? 0)
                - (baselineScorecard.aggregate_score?.passed ?? baselineScorecard.overall ?? 0),
              holdout:
                (candidateScorecard.aggregate_score?.holdout?.passed ?? 0)
                - (baselineScorecard.aggregate_score?.holdout?.passed ?? 0),
              pass_rate_points: Math.round(
                ((candidateScorecard.aggregate_score?.pass_rate ?? candidateScorecard.pass_rate ?? 0)
                - (baselineScorecard.aggregate_score?.pass_rate ?? baselineScorecard.pass_rate ?? 0)) * 100
              ),
              holdout_pass_rate_points: Math.round(
                ((candidateScorecard.aggregate_score?.holdout?.pass_rate ?? 0)
                - (baselineScorecard.aggregate_score?.holdout?.pass_rate ?? 0)) * 100
              ),
            }
          : null,
      comparison: comparison,
    });
  }

  return snapshot;
}

function adaptLivePayload(payload) {
  if (looksLikeAutoresearchAlphaPayload(payload)) {
    return mapAutoresearchAlphaPayloadToSnapshot(payload);
  }
  if (looksLikeLiveReadModelPayload(payload)) {
    return mapLiveReadModelPayloadToSnapshot(payload);
  }
  if (looksLikeSingleRunExport(payload)) {
    return mapSingleRunExportToSnapshot(payload);
  }
  if (looksLikeUiSnapshotPayload(payload)) {
    return payload;
  }
  return payload;
}

window.ROLE_FOUNDRY_READ_MODEL = Object.freeze({
  adaptLivePayload,
  mapAutoresearchAlphaPayloadToSnapshot,
  mapLiveReadModelPayloadToSnapshot,
  mapSingleRunExportToSnapshot,
});

function normalizeAppData(payload, mode) {
  validateSnapshotShape(payload);

  const base = mode === 'demo' ? cloneRoleFoundryData(DEMO_DATA) : createDataSkeleton(mode);

  return {
    ...base,
    ...payload,
    mode,
    role: normalizeRole(payload.role ?? base.role, mode),
    actors: normalizeActors(payload.actors ?? base.actors),
    scenarios: normalizeScenarios(payload.scenarios ?? base.scenarios),
    runs: normalizeRuns(payload.runs ?? base.runs),
    scores: normalizeRecord(payload.scores ?? base.scores),
    student_views: normalizeStudentViews(payload.student_views ?? base.student_views),
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
        const snapshot = normalizeAppData(adaptLivePayload(payload), 'live');
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

    getActor(role) {
      return this.actors?.[role] || null;
    },

    getScorecard(runId) {
      return this.scores?.[runId] || null;
    },

    getStudentView(runId) {
      return this.student_views?.[runId] || null;
    },

    getTeacherForRun(runId) {
      const scorecard = this.getScorecard(runId);
      if (!scorecard?.judged_by) return null;
      return Object.values(this.actors || {}).find(actor => actor.id === scorecard.judged_by) || null;
    },

    getIteration(runId) {
      return this.iterations.find(iteration => iteration.to_run === runId) || null;
    },

    latestIteration() {
      return this.latestScoredRunId() ? this.getIteration(this.latestScoredRunId()) : null;
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

    orderedRuns() {
      return [...this.runs].sort((a, b) => {
        if (Number.isFinite(a.sort_order) && Number.isFinite(b.sort_order) && a.sort_order !== b.sort_order) {
          return a.sort_order - b.sort_order;
        }

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

    scoredRuns() {
      return this.orderedRuns().filter(run => Boolean(this.getScorecard(run.id)));
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

    latestScoredRun() {
      const runs = this.scoredRuns();
      return runs[runs.length - 1] || null;
    },

    latestScoredRunId() {
      return this.latestScoredRun()?.id || null;
    },

    latestStudentViewRunId() {
      const runs = this.orderedRuns().filter(run => Boolean(this.getStudentView(run.id)));
      return runs[runs.length - 1]?.id || null;
    },

    previousRun(runId) {
      const runs = this.orderedRuns();
      const currentIndex = runs.findIndex(run => run.id === runId);
      if (currentIndex <= 0) {
        return null;
      }
      return runs[currentIndex - 1] || null;
    },

    previousScoredRun(runId) {
      const runs = this.scoredRuns();
      const currentIndex = runs.findIndex(run => run.id === runId);
      if (currentIndex <= 0) {
        return null;
      }
      return runs[currentIndex - 1] || null;
    },

    comparisonRunId(runId) {
      const run = this.getRun(runId);
      if (run?.comparison_run_id) {
        return run.comparison_run_id;
      }
      return this.previousScoredRun(runId)?.id || null;
    },

    hasComparisonRun(runId) {
      return Boolean(this.comparisonRunId(runId));
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
      const currentScorecard = this.getScorecard(currentRunId);
      const baselineScorecard = this.getScorecard(baselineId);
      if (!currentScorecard || !baselineScorecard) return null;
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

    teacherSummaryForRun(runId) {
      return this.getScorecard(runId)?.teacher_summary || this.getIteration(runId)?.identity_snapshot || null;
    },

    iterationTimeline() {
      return this.scoredRuns().map(run => {
        const scorecard = this.getScorecard(run.id);
        const baselineId = this.comparisonRunId(run.id);
        const baselineScorecard = baselineId ? this.getScorecard(baselineId) : null;
        return {
          run_id: run.id,
          iteration: run.iteration,
          aggregate_score: scorecard?.aggregate_score || null,
          delta: baselineScorecard
            ? {
                overall:
                  (scorecard?.aggregate_score?.passed ?? scorecard?.overall ?? 0)
                  - (baselineScorecard?.aggregate_score?.passed ?? baselineScorecard?.overall ?? 0),
                holdout:
                  (scorecard?.aggregate_score?.holdout?.passed ?? 0)
                  - (baselineScorecard?.aggregate_score?.holdout?.passed ?? 0),
                pass_rate_points: Math.round(
                  ((scorecard?.aggregate_score?.pass_rate ?? scorecard?.pass_rate ?? 0)
                  - (baselineScorecard?.aggregate_score?.pass_rate ?? baselineScorecard?.pass_rate ?? 0)) * 100
                ),
              }
            : null,
        };
      });
    },

    getRunLabel(runId) {
      return this.getRun(runId)?.label || runId || '—';
    },

    getRunShortLabel(runId) {
      const label = this.getRunLabel(runId);
      return label.includes('—') ? label.split('—')[0].trim() : label;
    },

    latestScoreSummary() {
      const runId = this.latestScoredRunId();
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
        return this.liveShell.endpoint || 'Configured live snapshot, read-model export, or alpha-loop receipt';
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
        return 'Rendering configured live data. Missing fields stay empty instead of being invented.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'loading') {
        return 'Loading live data. Demo data remains visible until a real snapshot or read-model export arrives.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'missing-endpoint') {
        return 'Live shell requested, but no liveDataUrl is configured. Demo data remains the honest fallback.';
      }

      if (this.requestedMode === 'live' && this.liveShell.status === 'error') {
        return 'Live shell requested, but the snapshot or read-model export failed to load. Demo data remains visible and is clearly labeled as demo.';
      }

      return 'Static, judge-friendly apprentice data. No auth theater. No fake live wiring.';
    },

    replayStatusText(runId) {
      if (!runId) {
        return 'Select a run to inspect its receipts.';
      }
      if (this.hasRunReplay(runId)) {
        return 'Replay lines are available for this run.';
      }
      if (this.sourceMode === 'live') {
        return 'No inline replay lines were exported for this run yet.';
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
  const store = Alpine.reactive(createAppStore(roleFoundryConfig()));
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
