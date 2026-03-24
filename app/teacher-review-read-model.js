// Role Foundry — Teacher Review Read-Model
//
// Consumes stored sample run objects, scorecards, task packets, and evaluation
// contracts to produce a teacher review snapshot. Built from stored exports only;
// missing fields stay empty instead of invented.
//
// This is the D001 read-model: "Render a review surface from stored exports only."

const TEACHER_REVIEW_READ_MODEL = (function () {
  'use strict';

  function safeString(value, fallback) {
    return typeof value === 'string' && value.length > 0 ? value : (fallback || null);
  }

  function safeNumber(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  }

  // ---------------------------------------------------------------------------
  // Task packet identity
  // ---------------------------------------------------------------------------

  function extractTaskIdentity(taskPacket) {
    const packet = safeObject(taskPacket);
    const phase = safeObject(packet.phase);
    return {
      task_id: safeString(packet.task_id),
      title: safeString(packet.title),
      role_id: safeString(packet.role_id),
      acceptance_test_id: safeString(packet.acceptance_test_id),
      phase_label: safeString(phase.label),
      phase_index: safeNumber(phase.index),
      objective: safeString(packet.objective),
      packet_version: safeString(packet.packet_version),
      status: safeString(packet.status),
    };
  }

  // ---------------------------------------------------------------------------
  // Run summary (baseline or candidate)
  // ---------------------------------------------------------------------------

  function extractRunSummary(runObject) {
    const run = safeObject(runObject);
    const workspace = safeObject(run.workspace);
    const diffStats = safeObject(run.diff_stats);
    const weightedScore = safeObject(run.weighted_score);
    const receipts = safeObject(run.receipts);

    return {
      run_id: safeString(run.run_id),
      kind: safeString(run.kind),
      example_only: Boolean(run.example_only),
      task_id: safeString(run.task_id),
      baseline_run_id: safeString(run.baseline_run_id),
      evaluation_contract_id: safeString(run.evaluation_contract_id),
      evaluation_contract_version: safeString(run.evaluation_contract_version),
      verifier_gate_status: safeString(run.verifier_gate_status),
      verifier_gate_note: safeString(run.verifier_gate_note),
      workspace: {
        kind: safeString(workspace.kind),
        isolated: Boolean(workspace.isolated),
        base_commit: safeString(workspace.base_commit),
      },
      artifact_root: safeString(run.artifact_root),
      commands: safeArray(run.commands).map(function (cmd) {
        const c = safeObject(cmd);
        return {
          command: safeString(c.command),
          exit_code: safeNumber(c.exit_code),
          stdout_capture: safeString(c.stdout_capture),
          stderr_capture: safeString(c.stderr_capture),
          execution_status: safeString(c.execution_status),
          honesty_note: safeString(c.honesty_note),
        };
      }),
      changed_files: safeArray(run.changed_files).map(function (f) {
        return typeof f === 'string' ? f : safeString(f);
      }).filter(Boolean),
      diff_stats: {
        tracked_files: safeNumber(diffStats.tracked_files),
        net_lines: safeNumber(diffStats.net_lines),
      },
      checks_run: safeArray(run.checks_run).map(function (check) {
        const ch = safeObject(check);
        return {
          id: safeString(ch.id),
          status: safeString(ch.status),
          stage: safeString(ch.stage),
          honesty_note: safeString(ch.honesty_note),
        };
      }),
      weighted_score: {
        value: safeNumber(weightedScore.value),
        contract_id: safeString(weightedScore.contract_id),
      },
      receipts: {
        task_packet_ref: safeString(receipts.task_packet_ref),
        transcript_path: safeString(receipts.transcript_path),
        changed_files_path: safeString(receipts.changed_files_path),
        checks_path: safeString(receipts.checks_path),
        scorecard_path: safeString(receipts.scorecard_path),
        provenance_manifest_path: safeString(receipts.provenance_manifest_path),
      },
    };
  }

  function deriveVerifierGateStatus(candidate) {
    if (!candidate) {
      return 'not_available';
    }
    if (candidate.verifier_gate_status) {
      return candidate.verifier_gate_status;
    }

    const checks = safeArray(candidate.checks_run);
    if (!checks.length) {
      return 'no_checks';
    }
    if (checks.every(function (c) { return c.status === 'passing'; })) {
      return 'passing';
    }
    if (checks.every(function (c) { return c.status === 'not_executed'; })) {
      return 'not_executed';
    }
    return 'failing';
  }

  function looksLikeAutoresearchAlphaReceipt(payload) {
    const input = safeObject(payload);
    const receipt = safeObject(input.autoresearch_alpha || input);
    const stages = safeObject(receipt.stages);
    return safeString(receipt.flow) === 'autoresearch-alpha' && Object.keys(stages).length > 0;
  }

  function mapAlphaStageToReviewRun(stageKey, stage, receipt) {
    const stageObject = safeObject(stage);
    const receiptObject = safeObject(receipt);
    const stageExport = safeObject(stageObject.export);
    const run = safeObject(stageExport.run);
    const result = safeObject(stageExport.result);
    const artifactBundle = safeObject(stageExport.artifact_bundle);
    const workspaceSnapshot = safeObject(artifactBundle.workspace_snapshot);
    const traceability = safeObject(stageObject.traceability);
    const benchmarkPack = safeObject(traceability.benchmark_pack);
    const comparison = safeObject(receiptObject.comparison);
    const verifierContract = safeObject(stageObject.verifier_contract);
    const commandResults = safeArray(verifierContract.command_results);
    const changedFiles = safeArray(workspaceSnapshot.changed_files).map(function (file) {
      return typeof file === 'string' ? file : safeString(file);
    }).filter(Boolean);

    return {
      run_id: safeString(stageObject.run_id) || safeString(run.id),
      kind: stageKey === 'baseline-eval' ? 'baseline' : (stageKey === 'candidate-teacher-eval' ? 'candidate' : safeString(stageKey)),
      example_only: false,
      task_id: safeString(benchmarkPack.id),
      baseline_run_id: stageKey === 'candidate-teacher-eval' ? safeString(comparison.baseline_run_id) : null,
      evaluation_contract_id: null,
      evaluation_contract_version: null,
      verifier_gate_status: safeString(verifierContract.gate_status),
      verifier_gate_note: safeString(verifierContract.honesty_note),
      workspace: {
        kind: null,
        isolated: false,
        base_commit: null,
      },
      artifact_root: null,
      commands: commandResults.map(function (entry) {
        const item = safeObject(entry);
        return {
          command: safeString(item.command),
          exit_code: safeNumber(item.exit_code),
          stdout_capture: null,
          stderr_capture: null,
          execution_status: safeString(item.execution_status),
          honesty_note: safeString(item.honesty_note),
        };
      }),
      changed_files: changedFiles,
      diff_stats: {
        tracked_files: changedFiles.length || null,
        net_lines: null,
      },
      checks_run: commandResults.map(function (entry, index) {
        const item = safeObject(entry);
        return {
          id: safeString(item.command, 'verifier-command-' + String(index + 1)),
          status: safeString(item.execution_status),
          stage: safeString(verifierContract.stage_key, stageKey),
          honesty_note: safeString(item.honesty_note),
        };
      }),
      weighted_score: {
        value: safeNumber(result.machine_score !== null && result.machine_score !== undefined ? result.machine_score : stageObject.total_score),
        contract_id: null,
      },
      receipts: {
        task_packet_ref: null,
        transcript_path: safeString(result.transcript_path),
        changed_files_path: null,
        checks_path: null,
        scorecard_path: safeString(safeObject(artifactBundle.receipts).result_path),
        provenance_manifest_path:
          safeString(safeObject(result.provenance).receipt_manifest_path)
          || safeString(safeObject(artifactBundle.receipts).receipt_manifest_path),
      },
    };
  }

  function buildTeacherReviewSnapshotFromAutoresearchAlpha(payload) {
    const input = safeObject(payload);
    const receipt = safeObject(input.autoresearch_alpha || input);
    const stages = safeObject(receipt.stages);
    const baseline = Object.keys(safeObject(stages['baseline-eval'])).length
      ? mapAlphaStageToReviewRun('baseline-eval', stages['baseline-eval'], receipt)
      : null;
    const candidate = Object.keys(safeObject(stages['candidate-teacher-eval'])).length
      ? mapAlphaStageToReviewRun('candidate-teacher-eval', stages['candidate-teacher-eval'], receipt)
      : null;

    const snapshot = buildTeacherReviewSnapshot({
      baseline_run: baseline,
      candidate_run: candidate,
    });

    snapshot.honesty_badge = 'Stored export — rendered from an actual public-regression autoresearch alpha receipt. LocalReplayRunner / zero-secret replay boundaries still apply, and missing task-packet or dimension-scorecard fields stay empty instead of invented.';
    snapshot.source_contract = 'autoresearch_alpha_receipt';
    snapshot.alpha_receipt = {
      sequence_id: safeString(receipt.sequence_id),
      dataset_manifest_id: safeString(receipt.dataset_manifest_id),
      verdict: safeString(receipt.verdict),
      integrity_mode: safeString(safeObject(receipt.integrity_gate).mode),
      claim_ceiling: safeString(safeObject(receipt.sealing_receipt).claim_ceiling),
    };
    return snapshot;
  }

  // ---------------------------------------------------------------------------
  // Scorecard breakdown
  // ---------------------------------------------------------------------------

  function extractScorecardBreakdown(scorecard) {
    const sc = safeObject(scorecard);
    const meta = safeObject(sc.meta);
    const promotionGate = safeObject(sc.promotion_gate_preview);

    return {
      meta: {
        example_only: Boolean(meta.example_only),
        task_id: safeString(meta.task_id),
        contract_id: safeString(meta.evaluation_contract_id || meta.contract_id),
        contract_version: safeString(meta.evaluation_contract_version || meta.contract_version),
        public_safe: meta.public_safe !== false,
      },
      dimensions: safeArray(sc.dimensions).map(function (dim) {
        const d = safeObject(dim);
        return {
          id: safeString(d.id),
          label: safeString(d.label),
          weight: safeNumber(d.weight),
          score: safeNumber(d.score),
          notes: safeString(d.notes),
        };
      }),
      weighted_score: safeNumber(sc.weighted_score),
      task_pass: sc.task_pass === true,
      promotion_gate: {
        public_threshold_met: promotionGate.public_threshold_met === true,
        private_holdout_threshold_required: promotionGate.private_holdout_threshold_required !== false,
        promotion_ready: promotionGate.promotion_ready === true,
        reason: safeString(promotionGate.reason),
      },
    };
  }

  // ---------------------------------------------------------------------------
  // Evaluation contract summary
  // ---------------------------------------------------------------------------

  function extractContractSummary(contract) {
    const c = safeObject(contract);
    const meta = safeObject(c.meta);
    const thresholds = safeObject(c.thresholds);
    const taskPass = safeObject(thresholds.task_pass);
    const promotionGate = safeObject(thresholds.promotion_gate);

    return {
      contract_id: safeString(meta.id),
      version: safeString(meta.version),
      role_id: safeString(meta.role_id),
      dimensions: safeArray(c.dimensions).map(function (dim) {
        const d = safeObject(dim);
        return {
          id: safeString(d.id),
          label: safeString(d.label),
          weight: safeNumber(d.weight),
          description: safeString(d.description),
        };
      }),
      thresholds: {
        task_pass_weighted_min: safeNumber(taskPass.weighted_score_min),
        task_pass_dimension_floor: safeNumber(taskPass.dimension_floor_min),
        promotion_public_min: safeNumber(promotionGate.public_weighted_score_min),
        promotion_holdout_min: safeNumber(promotionGate.private_holdout_weighted_score_min),
      },
    };
  }

  // ---------------------------------------------------------------------------
  // Teacher review snapshot — the full read-model
  // ---------------------------------------------------------------------------

  function buildTeacherReviewSnapshot(options) {
    const opts = safeObject(options);
    const taskPacket = opts.task_packet || null;
    const baselineRun = opts.baseline_run || null;
    const candidateRun = opts.candidate_run || null;
    const scorecard = opts.scorecard || null;
    const contract = opts.evaluation_contract || null;

    const task = taskPacket ? extractTaskIdentity(taskPacket) : null;
    const baseline = baselineRun ? extractRunSummary(baselineRun) : null;
    const candidate = candidateRun ? extractRunSummary(candidateRun) : null;
    const scorecardBreakdown = scorecard ? extractScorecardBreakdown(scorecard) : null;
    const contractSummary = contract ? extractContractSummary(contract) : null;

    // Compute promotion decision from available evidence
    var promotionDecision = 'pending';
    if (scorecardBreakdown) {
      if (scorecardBreakdown.promotion_gate.promotion_ready) {
        promotionDecision = 'promoted';
      } else if (scorecardBreakdown.task_pass) {
        promotionDecision = 'task_pass_no_promotion';
      } else {
        promotionDecision = 'not_passing';
      }
    }

    // Diff summary: compare baseline vs candidate
    var diffSummary = null;
    if (baseline && candidate) {
      var baselineScore = baseline.weighted_score.value;
      var candidateScore = candidate.weighted_score.value;
      diffSummary = {
        baseline_run_id: baseline.run_id,
        candidate_run_id: candidate.run_id,
        baseline_score: baselineScore,
        candidate_score: candidateScore,
        score_delta: (baselineScore !== null && candidateScore !== null)
          ? Math.round((candidateScore - baselineScore) * 10000) / 10000
          : null,
        baseline_checks_passing: baseline.checks_run.filter(function (c) { return c.status === 'passing'; }).length,
        candidate_checks_passing: candidate.checks_run.filter(function (c) { return c.status === 'passing'; }).length,
        baseline_changed_files: baseline.changed_files.length,
        candidate_changed_files: candidate.changed_files.length,
      };
    }

    // Verifier gate status
    var verifierGateStatus = deriveVerifierGateStatus(candidate);

    // Honesty badge
    var isFixtureData = Boolean(
      (baseline && baseline.example_only) ||
      (candidate && candidate.example_only) ||
      (scorecardBreakdown && scorecardBreakdown.meta.example_only)
    );

    return {
      shell_version: '0.1.0',
      data_source: isFixtureData ? 'sample_fixture' : 'stored_export',
      honesty_badge: isFixtureData
        ? 'Sample fixture — not a live run. Scores and receipts are illustrative only.'
        : 'Stored export — rendered from actual run artifacts.',

      task: task,
      baseline: baseline,
      candidate: candidate,
      diff_summary: diffSummary,
      scorecard: scorecardBreakdown,
      contract: contractSummary,
      verifier_gate_status: verifierGateStatus,
      promotion_decision: promotionDecision,

      evidence_links: {
        task_packet_ref: candidate
          ? candidate.receipts.task_packet_ref
          : (baseline ? baseline.receipts.task_packet_ref : null),
        transcript_path: candidate
          ? candidate.receipts.transcript_path
          : (baseline ? baseline.receipts.transcript_path : null),
        scorecard_path: candidate
          ? candidate.receipts.scorecard_path
          : (baseline ? baseline.receipts.scorecard_path : null),
        changed_files_path: candidate
          ? candidate.receipts.changed_files_path
          : (baseline ? baseline.receipts.changed_files_path : null),
        provenance_manifest_path: candidate
          ? candidate.receipts.provenance_manifest_path
          : (baseline ? baseline.receipts.provenance_manifest_path : null),
      },
    };
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  return Object.freeze({
    buildTeacherReviewSnapshot: buildTeacherReviewSnapshot,
    buildTeacherReviewSnapshotFromAutoresearchAlpha: buildTeacherReviewSnapshotFromAutoresearchAlpha,
    looksLikeAutoresearchAlphaReceipt: looksLikeAutoresearchAlphaReceipt,
    extractTaskIdentity: extractTaskIdentity,
    extractRunSummary: extractRunSummary,
    extractScorecardBreakdown: extractScorecardBreakdown,
    extractContractSummary: extractContractSummary,
  });
})();

if (typeof window !== 'undefined') {
  window.TEACHER_REVIEW_READ_MODEL = TEACHER_REVIEW_READ_MODEL;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TEACHER_REVIEW_READ_MODEL;
}
