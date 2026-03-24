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
    if (value === null || value === undefined || value === '') {
      return null;
    }
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function safeObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  }

  function mapTextList(value) {
    return safeArray(value).map(function (entry) {
      return safeString(entry);
    }).filter(Boolean);
  }

  function extractTranscriptExcerpt(entries) {
    return safeArray(entries).map(function (entry) {
      const item = safeObject(entry);
      return {
        ts: safeString(item.ts),
        event: safeString(item.event),
        message: safeString(item.message),
      };
    }).filter(function (entry) {
      return entry.ts || entry.event || entry.message;
    });
  }

  function stageSortKey(stageKey) {
    if (stageKey === 'baseline-eval') {
      return 1;
    }
    if (stageKey === 'candidate-student') {
      return 2;
    }
    if (stageKey === 'candidate-teacher-eval') {
      return 3;
    }
    return 99;
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
      task_packet_version: safeString(run.task_packet_version),
      baseline_run_id: safeString(run.baseline_run_id),
      evaluation_contract_id: safeString(run.evaluation_contract_id),
      evaluation_contract_version: safeString(run.evaluation_contract_version),
      verifier_gate_status: safeString(run.verifier_gate_status),
      verifier_gate_note: safeString(run.verifier_gate_note),
      objective: safeString(run.objective),
      policy_snapshot: mapTextList(run.policy_snapshot),
      transcript_excerpt: extractTranscriptExcerpt(run.transcript_excerpt),
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
        evidence_index_path: safeString(receipts.evidence_index_path),
        summary_path: safeString(receipts.summary_path),
        audit_bundle_path: safeString(receipts.audit_bundle_path),
        request_path: safeString(receipts.request_path),
        artifact_bundle_path: safeString(receipts.artifact_bundle_path),
        result_path: safeString(receipts.result_path),
        baseline_receipt_path: safeString(receipts.baseline_receipt_path),
        candidate_receipt_path: safeString(receipts.candidate_receipt_path),
        evaluation_receipt_path: safeString(receipts.evaluation_receipt_path),
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
    const artifactCoverage = safeObject(safeObject(receiptObject.artifact_coverage)[stageKey]);
    const coveragePaths = safeObject(artifactCoverage.paths);
    const resultProvenance = safeObject(result.provenance);
    const bundleReceipts = safeObject(artifactBundle.receipts);
    const episodeReceiptPaths = safeObject(resultProvenance.episode_receipt_paths);
    const changedFiles = safeArray(workspaceSnapshot.changed_files).map(function (file) {
      return typeof file === 'string' ? file : safeString(file);
    }).filter(Boolean);

    return {
      run_id: safeString(stageObject.run_id) || safeString(run.id),
      kind: stageKey === 'baseline-eval' ? 'baseline' : (stageKey === 'candidate-teacher-eval' ? 'candidate' : safeString(stageKey)),
      example_only: false,
      task_id: safeString(benchmarkPack.id),
      task_packet_version: null,
      baseline_run_id: stageKey === 'candidate-teacher-eval' ? safeString(comparison.baseline_run_id) : null,
      evaluation_contract_id: null,
      evaluation_contract_version: null,
      verifier_gate_status: safeString(verifierContract.gate_status),
      verifier_gate_note: safeString(verifierContract.honesty_note),
      objective: safeString(workspaceSnapshot.objective),
      policy_snapshot: mapTextList(workspaceSnapshot.policy_snapshot),
      transcript_excerpt: extractTranscriptExcerpt(stageExport.transcript_excerpt),
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
        transcript_path: safeString(coveragePaths['transcript.ndjson']) || safeString(result.transcript_path),
        changed_files_path: null,
        checks_path: null,
        scorecard_path: safeString(coveragePaths['result.json']) || safeString(bundleReceipts.result_path),
        provenance_manifest_path:
          safeString(coveragePaths['receipts/manifest.json'])
          || safeString(resultProvenance.receipt_manifest_path)
          || safeString(bundleReceipts.receipt_manifest_path),
        evidence_index_path:
          safeString(coveragePaths['receipts/evidence-index.json'])
          || safeString(resultProvenance.evidence_index_path)
          || safeString(bundleReceipts.evidence_index_path),
        summary_path:
          safeString(coveragePaths['receipts/summary.md'])
          || safeString(resultProvenance.summary_path)
          || safeString(bundleReceipts.summary_path),
        audit_bundle_path:
          safeString(coveragePaths['receipts/audit-bundle.json'])
          || safeString(resultProvenance.audit_bundle_path)
          || safeString(bundleReceipts.audit_bundle_path),
        request_path: safeString(coveragePaths['request.json']),
        artifact_bundle_path:
          safeString(coveragePaths['artifact-bundle.json'])
          || safeString(result.artifact_bundle_path),
        result_path:
          safeString(coveragePaths['result.json'])
          || safeString(bundleReceipts.result_path),
        baseline_receipt_path:
          safeString(coveragePaths['receipts/baseline.json'])
          || safeString(episodeReceiptPaths.baseline),
        candidate_receipt_path:
          safeString(coveragePaths['receipts/candidate.json'])
          || safeString(episodeReceiptPaths.candidate),
        evaluation_receipt_path:
          safeString(coveragePaths['receipts/evaluation.json'])
          || safeString(episodeReceiptPaths.evaluation),
      },
    };
  }

  function extractAlphaTaskContext(receiptPayload, requestPayload) {
    const receipt = safeObject(receiptPayload.autoresearch_alpha || receiptPayload);
    const request = safeObject(requestPayload);
    const candidateStage = safeObject(safeObject(receipt.stages)['candidate-student']);
    const stageExport = safeObject(candidateStage.export);
    const artifactBundle = safeObject(stageExport.artifact_bundle);
    const studentView = safeObject(artifactBundle.student_view);
    const repoTaskPack = safeObject(studentView.repo_task_pack);
    const benchmarkPack = safeObject(safeObject(candidateStage.traceability).benchmark_pack);
    const episodeIds = safeArray(repoTaskPack.episode_ids).map(function (id) {
      return safeString(id);
    }).filter(Boolean);
    const familyIds = safeArray(repoTaskPack.family_ids).map(function (id) {
      return safeString(id);
    }).filter(Boolean);
    const visibleScenarios = safeArray(studentView.visible_scenarios).map(function (scenario) {
      const item = safeObject(scenario);
      const meta = safeObject(item.repo_task_meta);
      return {
        id: safeString(item.id),
        title: safeString(item.title),
        type: safeString(item.type),
        difficulty: safeString(item.difficulty),
        student_prompt: safeString(item.student_prompt),
        family_id: safeString(meta.family_id),
        mutation_budget: safeString(meta.mutation_budget),
        artifacts_required: mapTextList(meta.artifacts_required),
        public_checks: mapTextList(meta.public_checks),
        tags: mapTextList(meta.tags),
      };
    }).filter(function (scenario) {
      return scenario.id || scenario.title;
    });

    if (
      !Object.keys(repoTaskPack).length
      && !visibleScenarios.length
      && !safeString(studentView.prompt_summary)
      && !safeString(receipt.dataset_manifest_id)
    ) {
      return null;
    }

    return {
      source: 'repo_task_pack',
      role_scope: safeString(repoTaskPack.role_scope) || safeString(benchmarkPack.role_scope),
      dataset_id: safeString(repoTaskPack.dataset_id) || safeString(receipt.dataset_manifest_id),
      dataset_version: safeString(repoTaskPack.dataset_version) || safeString(receipt.dataset_version),
      episode_count: safeNumber(repoTaskPack.episode_count) || (episodeIds.length ? episodeIds.length : null),
      episode_ids: episodeIds,
      family_ids: familyIds,
      prompt_summary: safeString(studentView.prompt_summary),
      honesty_note: safeString(repoTaskPack.honesty_note),
      public_benchmark_pack_ref: safeString(request.public_benchmark_pack),
      family_registry_ref: safeString(request.family_registry),
      recommended_verifier_commands: mapTextList(repoTaskPack.recommended_verifier_commands),
      visible_scenarios: visibleScenarios,
    };
  }

  function mapAlphaScenarioResult(result) {
    const item = safeObject(result);
    return {
      id: safeString(item.scenario_id) || safeString(item.id),
      title: safeString(item.title),
      type: safeString(item.type),
      difficulty: safeString(item.difficulty),
      visibility: safeString(item.visibility),
      passed: item.passed === true,
      score: safeNumber(item.score),
      notes: safeString(item.notes) || safeString(item.teacher_notes),
    };
  }

  function mapAlphaIterationHistory(entries) {
    return safeArray(entries).map(function (entry) {
      const item = safeObject(entry);
      const aggregate = safeObject(item.aggregate_score);
      const holdout = safeObject(aggregate.holdout);
      const delta = safeObject(item.delta);
      return {
        run_id: safeString(item.run_id),
        label: safeString(item.label),
        aggregate_score: {
          passed: safeNumber(aggregate.passed),
          total: safeNumber(aggregate.total),
          pass_rate: safeNumber(aggregate.pass_rate),
          average_score: safeNumber(aggregate.average_score),
          holdout: {
            passed: safeNumber(holdout.passed),
            total: safeNumber(holdout.total),
            pass_rate: safeNumber(holdout.pass_rate),
          },
        },
        delta: {
          pass_count: safeNumber(delta.pass_count),
          pass_rate: safeNumber(delta.pass_rate),
          average_score: safeNumber(delta.average_score),
          holdout_pass_count: safeNumber(delta.holdout_pass_count),
          holdout_pass_rate: safeNumber(delta.holdout_pass_rate),
        },
      };
    }).filter(function (entry) {
      return entry.run_id || entry.label;
    });
  }

  function extractAlphaTeacherEvaluation(receiptPayload, requestPayload) {
    const receipt = safeObject(receiptPayload.autoresearch_alpha || receiptPayload);
    const request = safeObject(requestPayload);
    const stage = safeObject(safeObject(receipt.stages)['candidate-teacher-eval']);
    const stageExport = safeObject(stage.export);
    const result = safeObject(stageExport.result);
    const scorecard = safeObject(result.scorecard);
    const requestStage = safeObject(safeObject(request.stages)['candidate-teacher-eval']);
    const requestEval = safeObject(safeObject(safeObject(requestStage.request).teacher_evaluation));
    const aggregate = safeObject(scorecard.aggregate_score);
    const holdout = safeObject(aggregate.holdout);
    const comparison = safeObject(receipt.comparison);

    if (!Object.keys(scorecard).length && !Object.keys(requestEval).length) {
      return null;
    }

    const teacher = safeObject(scorecard.teacher || requestEval.teacher);
    const student = safeObject(scorecard.student || requestEval.student);

    return {
      teacher: {
        id: safeString(teacher.id),
        name: safeString(teacher.name),
        agent_role: safeString(teacher.agent_role),
      },
      student: {
        id: safeString(student.id),
        name: safeString(student.name),
        agent_role: safeString(student.agent_role),
      },
      student_prompt_summary:
        safeString(requestEval.student_prompt_summary)
        || safeString(safeObject(safeObject(stageExport.artifact_bundle).student_view).prompt_summary),
      verdict: safeString(scorecard.verdict) || safeString(requestEval.teacher_verdict),
      comparison_verdict: safeString(comparison.verdict),
      deciding_axis:
        safeString(comparison.deciding_axis)
        || safeString(safeObject(request.comparison_policy).deciding_axis),
      aggregate_score: {
        passed: safeNumber(aggregate.passed),
        total: safeNumber(aggregate.total),
        pass_rate: safeNumber(aggregate.pass_rate),
        average_score: safeNumber(aggregate.average_score),
        holdout: {
          passed: safeNumber(holdout.passed),
          total: safeNumber(holdout.total),
          pass_rate: safeNumber(holdout.pass_rate),
        },
      },
      scenario_results: safeArray(scorecard.scenario_results || requestEval.scenarios).map(mapAlphaScenarioResult).filter(function (entry) {
        return entry.id || entry.title;
      }),
      public_curriculum_themes: safeArray(scorecard.public_curriculum_themes).map(function (theme) {
        const item = safeObject(theme);
        return {
          theme: safeString(item.theme),
          description: safeString(item.description),
          source_scenarios: mapTextList(item.source_scenarios),
        };
      }).filter(function (entry) {
        return entry.theme || entry.description;
      }),
      iteration_history: mapAlphaIterationHistory(scorecard.iteration_history),
      comparison_reasons: mapTextList(comparison.reasons),
    };
  }

  function extractAlphaRequiredVerifierCommands(receiptPayload) {
    const receipt = safeObject(receiptPayload.autoresearch_alpha || receiptPayload);
    const stages = safeObject(receipt.stages);
    const preferredOrder = ['candidate-teacher-eval', 'candidate-student', 'baseline-eval'];
    for (var i = 0; i < preferredOrder.length; i += 1) {
      const stageKey = preferredOrder[i];
      const commands = mapTextList(safeObject(safeObject(stages[stageKey]).verifier_contract).required_commands);
      if (commands.length) {
        return commands;
      }
    }
    return [];
  }

  function extractAlphaEvaluationSummary(receiptPayload, requestPayload) {
    const receipt = safeObject(receiptPayload.autoresearch_alpha || receiptPayload);
    const request = safeObject(requestPayload);
    const requestStages = safeObject(request.stages);
    const receiptStages = safeObject(receipt.stages);
    const comparisonPolicy = safeObject(request.comparison_policy);
    const integrityGate = safeObject(receipt.integrity_gate);
    const verifierGate = safeObject(receipt.verifier_gate);
    const sealingReceipt = safeObject(receipt.sealing_receipt);
    const stageLabels = Object.keys(Object.keys(requestStages).length ? requestStages : receiptStages)
      .sort(function (a, b) { return stageSortKey(a) - stageSortKey(b); })
      .map(function (stageKey) {
        const requestStage = safeObject(requestStages[stageKey]);
        const receiptStage = safeObject(receiptStages[stageKey]);
        return {
          stage_key: stageKey,
          label: safeString(requestStage.label),
          run_id: safeString(receiptStage.run_id),
          status: safeString(receiptStage.status),
        };
      })
      .filter(function (entry) {
        return entry.stage_key || entry.label || entry.run_id;
      });

    if (
      !safeString(receipt.control_plane_mode)
      && !safeString(sealingReceipt.claim_ceiling)
      && !safeString(comparisonPolicy.deciding_axis)
      && !stageLabels.length
    ) {
      return null;
    }

    return {
      control_plane_mode: safeString(receipt.control_plane_mode),
      integrity_mode: safeString(integrityGate.mode),
      integrity_summary: safeString(integrityGate.summary),
      claim_ceiling: safeString(sealingReceipt.claim_ceiling),
      public_benchmark_pack_ref: safeString(request.public_benchmark_pack),
      family_registry_ref: safeString(request.family_registry),
      deciding_axis: safeString(comparisonPolicy.deciding_axis) || safeString(safeObject(receipt.comparison).deciding_axis),
      epsilon: safeNumber(comparisonPolicy.epsilon),
      verifier_gate_status: safeString(verifierGate.aggregate_status),
      total_commands: safeNumber(verifierGate.total_commands),
      executed_commands: safeNumber(verifierGate.executed_commands),
      required_verifier_commands: extractAlphaRequiredVerifierCommands(receipt),
      stage_labels: stageLabels,
      blocked_claims: safeArray(sealingReceipt.blocked_claims).map(function (entry) {
        const item = safeObject(entry);
        return {
          claim: safeString(item.claim),
          reason: safeString(item.reason),
          prerequisite: safeString(item.prerequisite),
        };
      }).filter(function (entry) {
        return entry.claim || entry.reason;
      }),
    };
  }

  function mapAlphaArtifactCoverage(receiptPayload) {
    const receipt = safeObject(receiptPayload.autoresearch_alpha || receiptPayload);
    const coverage = safeObject(receipt.artifact_coverage);
    return Object.keys(coverage)
      .sort(function (a, b) { return stageSortKey(a) - stageSortKey(b); })
      .map(function (stageKey) {
        const item = safeObject(coverage[stageKey]);
        const paths = safeObject(item.paths);
        return {
          stage_key: stageKey,
          run_id: safeString(item.run_id),
          complete: item.complete === true,
          request_path: safeString(paths['request.json']),
          transcript_path: safeString(paths['transcript.ndjson']),
          artifact_bundle_path: safeString(paths['artifact-bundle.json']),
          result_path: safeString(paths['result.json']),
          manifest_path: safeString(paths['receipts/manifest.json']),
          evidence_index_path: safeString(paths['receipts/evidence-index.json']),
          summary_path: safeString(paths['receipts/summary.md']),
          audit_bundle_path: safeString(paths['receipts/audit-bundle.json']),
          baseline_receipt_path: safeString(paths['receipts/baseline.json']),
          candidate_receipt_path: safeString(paths['receipts/candidate.json']),
          evaluation_receipt_path: safeString(paths['receipts/evaluation.json']),
        };
      });
  }

  function safeBooleanOrNull(value) {
    return value === true ? true : (value === false ? false : null);
  }

  function deriveRegressionGateStatus(regressionGate) {
    const gate = safeObject(regressionGate);
    const enforced = safeBooleanOrNull(gate.enforced);
    const gatePassed = safeBooleanOrNull(gate.gate_passed);
    if (enforced === false) {
      return 'not_enforced';
    }
    if (gatePassed === true) {
      return 'passed';
    }
    if (gatePassed === false) {
      return 'failed';
    }
    if (enforced === true) {
      return 'pending';
    }
    return null;
  }

  function mapAlphaComparisonHistoryEntry(receiptPayload) {
    const payload = safeObject(receiptPayload);
    const receipt = safeObject(payload.autoresearch_alpha || payload);
    const comparison = safeObject(receipt.comparison);
    const categoryDeltas = safeObject(comparison.category_deltas);
    const verifierGate = safeObject(receipt.verifier_gate);

    if (!Object.keys(comparison).length) {
      return null;
    }

    return {
      entry_id: safeString(receipt.sequence_id) || safeString(comparison.candidate_run_id) || safeString(comparison.baseline_run_id),
      source_kind: 'autoresearch_alpha_receipt',
      source_label: 'Public-regression alpha receipt',
      recorded_at: null,
      example_only: false,
      baseline_run_id: safeString(comparison.baseline_run_id),
      candidate_run_id: safeString(comparison.candidate_run_id),
      baseline_total_score: safeNumber(comparison.baseline_total_score),
      candidate_total_score: safeNumber(comparison.candidate_total_score),
      total_score_delta: safeNumber(comparison.total_score_delta),
      verdict: safeString(comparison.verdict) || safeString(receipt.verdict),
      deciding_axis: safeString(comparison.deciding_axis),
      pass_count_delta: safeNumber(categoryDeltas.pass_count),
      pass_rate_delta: safeNumber(categoryDeltas.pass_rate),
      holdout_pass_count_delta: safeNumber(categoryDeltas.holdout_pass_count),
      holdout_pass_rate_delta: safeNumber(categoryDeltas.holdout_pass_rate),
      verifier_gate_status: safeString(verifierGate.aggregate_status),
      executed_commands: safeNumber(verifierGate.executed_commands),
      total_commands: safeNumber(verifierGate.total_commands),
      promotion_decision: null,
      regression_gate_enforced: null,
      regression_gate_status: null,
      comparison_reasons: mapTextList(comparison.reasons),
      teacher_review_notes: null,
      honesty_note:
        safeString(verifierGate.honesty_note)
        || 'Stored alpha comparison receipt only. Promotion and regression history stay blank when the export does not carry them.',
    };
  }

  function mapWeeklyCycleComparisonHistoryEntry(weeklyCyclePayload) {
    const payload = safeObject(weeklyCyclePayload);
    const meta = safeObject(payload.meta);
    const cycle = safeObject(payload.cycle);
    const baseline = safeObject(cycle.baseline);
    const candidate = safeObject(cycle.candidate);
    const teacherReview = safeObject(cycle.teacher_review);
    const promotionDecision = safeObject(cycle.promotion_decision);
    const regressionGate = safeObject(cycle.regression_gate);
    const baselineScore = safeNumber(baseline.weighted_score);
    const candidateScore = safeNumber(candidate.weighted_score);

    if (!safeString(cycle.cycle_id) && !safeString(candidate.run_id) && !safeString(baseline.run_id)) {
      return null;
    }

    return {
      entry_id: safeString(cycle.cycle_id) || safeString(candidate.run_id) || safeString(baseline.run_id),
      source_kind: 'weekly_cycle_receipt',
      source_label: 'Weekly training cycle receipt',
      recorded_at: safeString(cycle.cycle_week),
      example_only: cycle.example_only === true || meta.example_only === true,
      baseline_run_id: safeString(baseline.run_id),
      candidate_run_id: safeString(candidate.run_id),
      baseline_total_score: baselineScore,
      candidate_total_score: candidateScore,
      total_score_delta:
        baselineScore !== null && candidateScore !== null
          ? candidateScore - baselineScore
          : null,
      verdict: null,
      deciding_axis: null,
      pass_count_delta: null,
      pass_rate_delta: null,
      holdout_pass_count_delta: null,
      holdout_pass_rate_delta: null,
      verifier_gate_status: null,
      executed_commands: null,
      total_commands: null,
      promotion_decision: safeString(promotionDecision.decision),
      regression_gate_enforced: safeBooleanOrNull(regressionGate.enforced),
      regression_gate_status: deriveRegressionGateStatus(regressionGate),
      comparison_reasons: [],
      teacher_review_notes: safeString(teacherReview.notes),
      honesty_note:
        'Fixture weekly-cycle receipt. Stored baseline/candidate scores and promotion metadata render here; verdict and executed verifier status stay blank because this receipt does not carry them.',
    };
  }

  function mapGenerationPromotionHistoryEntry(generation) {
    const entry = safeObject(generation);
    const promotionDecision = safeObject(entry.promotion_decision);
    const runObjectRef = safeObject(entry.run_object_ref);
    const regressionGate = safeObject(entry.regression_gate);

    if (!safeString(entry.generation_id) && safeNumber(entry.generation_index) === null) {
      return null;
    }

    return {
      entry_id: safeString(entry.generation_id) || String(safeNumber(entry.generation_index) || ''),
      source_kind: 'generation_lineage',
      source_label: 'Generation lineage registry',
      recorded_at: safeString(entry.created_at),
      example_only: entry.example_only === true,
      generation_id: safeString(entry.generation_id),
      generation_index: safeNumber(entry.generation_index),
      parent_generation_id: safeString(entry.parent_generation_id),
      decision: safeString(promotionDecision.decision),
      reason: safeString(promotionDecision.reason),
      teacher_reviewed: promotionDecision.teacher_reviewed === true,
      public_score: safeNumber(promotionDecision.public_score),
      holdout_score_available: promotionDecision.holdout_score_available === true,
      stability_check_passed: safeBooleanOrNull(promotionDecision.stability_check_passed),
      regression_gate_passed: safeBooleanOrNull(promotionDecision.regression_gate_passed),
      regression_gate_enforced: safeBooleanOrNull(regressionGate.enforced),
      run_id: safeString(runObjectRef.run_id),
      run_artifact_available: runObjectRef.available === true,
      honesty_note:
        runObjectRef.available === true
          ? 'Promotion record came from the committed lineage registry.'
          : 'Promotion record came from the committed lineage registry; linked run artifacts are not tracked in git yet.',
    };
  }

  function mapGenerationRegressionHistoryEntry(generation) {
    const entry = safeObject(generation);
    const regressionGate = safeObject(entry.regression_gate);

    if (!safeString(entry.generation_id) && !Object.keys(regressionGate).length) {
      return null;
    }

    return {
      entry_id: safeString(entry.generation_id) || String(safeNumber(entry.generation_index) || ''),
      source_kind: 'generation_lineage',
      source_label: 'Generation lineage registry',
      recorded_at: safeString(entry.created_at),
      example_only: entry.example_only === true,
      generation_id: safeString(entry.generation_id),
      generation_index: safeNumber(entry.generation_index),
      cycle_id: null,
      run_id: null,
      enforced: safeBooleanOrNull(regressionGate.enforced),
      tasks_checked: safeNumber(regressionGate.tasks_checked),
      regressions_found: safeNumber(regressionGate.regressions_found),
      gate_passed: safeBooleanOrNull(regressionGate.gate_passed),
      gate_status: deriveRegressionGateStatus(regressionGate),
      honesty_note:
        regressionGate.enforced === false
          ? 'Regression gate is present as a contract record, but enforcement is explicitly not live on this lineage entry.'
          : 'Regression gate record loaded from the committed lineage registry.',
    };
  }

  function mapWeeklyCycleRegressionHistoryEntry(weeklyCyclePayload) {
    const payload = safeObject(weeklyCyclePayload);
    const meta = safeObject(payload.meta);
    const cycle = safeObject(payload.cycle);
    const regressionGate = safeObject(cycle.regression_gate);
    const generationRef = safeObject(cycle.generation_ref);
    const candidate = safeObject(cycle.candidate);

    if (!safeString(cycle.cycle_id) && !Object.keys(regressionGate).length) {
      return null;
    }

    return {
      entry_id: safeString(cycle.cycle_id) || safeString(generationRef.generation_id),
      source_kind: 'weekly_cycle_receipt',
      source_label: 'Weekly training cycle receipt',
      recorded_at: safeString(cycle.cycle_week),
      example_only: cycle.example_only === true || meta.example_only === true,
      generation_id: safeString(generationRef.generation_id),
      generation_index: safeNumber(generationRef.generation_index),
      cycle_id: safeString(cycle.cycle_id),
      run_id: safeString(candidate.run_id),
      enforced: safeBooleanOrNull(regressionGate.enforced),
      tasks_checked: safeNumber(regressionGate.tasks_checked),
      regressions_found: safeNumber(regressionGate.regressions_found),
      gate_passed: safeBooleanOrNull(regressionGate.gate_passed),
      gate_status: deriveRegressionGateStatus(regressionGate),
      honesty_note:
        regressionGate.enforced === false
          ? 'Weekly cycle recorded a regression-gate slot, but enforcement stayed off. Tasks checked and regressions found remain blank instead of invented.'
          : 'Regression gate record loaded from the committed weekly-cycle receipt.',
    };
  }

  function buildStoredHistorySnapshot(inputs) {
    const options = safeObject(inputs);
    const comparisonHistory = [];
    const promotionHistory = [];
    const regressionHistory = [];

    const alphaEntry = mapAlphaComparisonHistoryEntry(options.alpha_receipt);
    if (alphaEntry) {
      comparisonHistory.push(alphaEntry);
    }

    const weeklyComparisonEntry = mapWeeklyCycleComparisonHistoryEntry(options.weekly_cycle);
    if (weeklyComparisonEntry) {
      comparisonHistory.push(weeklyComparisonEntry);
    }

    safeArray(safeObject(options.generation_lineage).generations).forEach(function (generation) {
      const promotionEntry = mapGenerationPromotionHistoryEntry(generation);
      const regressionEntry = mapGenerationRegressionHistoryEntry(generation);
      if (promotionEntry) {
        promotionHistory.push(promotionEntry);
      }
      if (regressionEntry) {
        regressionHistory.push(regressionEntry);
      }
    });

    const weeklyRegressionEntry = mapWeeklyCycleRegressionHistoryEntry(options.weekly_cycle);
    if (weeklyRegressionEntry) {
      regressionHistory.push(weeklyRegressionEntry);
    }

    comparisonHistory.sort(function (a, b) {
      const aRecorded = a.recorded_at ? Date.parse(a.recorded_at) : NaN;
      const bRecorded = b.recorded_at ? Date.parse(b.recorded_at) : NaN;
      if (Number.isFinite(aRecorded) && Number.isFinite(bRecorded) && aRecorded !== bRecorded) {
        return aRecorded - bRecorded;
      }
      return String(a.entry_id || '').localeCompare(String(b.entry_id || ''));
    });

    promotionHistory.sort(function (a, b) {
      const aIndex = safeNumber(a.generation_index);
      const bIndex = safeNumber(b.generation_index);
      if (aIndex !== null && bIndex !== null && aIndex !== bIndex) {
        return aIndex - bIndex;
      }
      return String(a.entry_id || '').localeCompare(String(b.entry_id || ''));
    });

    regressionHistory.sort(function (a, b) {
      const aIndex = safeNumber(a.generation_index);
      const bIndex = safeNumber(b.generation_index);
      if (aIndex !== null && bIndex !== null && aIndex !== bIndex) {
        return aIndex - bIndex;
      }
      const aRecorded = a.recorded_at ? Date.parse(a.recorded_at) : NaN;
      const bRecorded = b.recorded_at ? Date.parse(b.recorded_at) : NaN;
      if (Number.isFinite(aRecorded) && Number.isFinite(bRecorded) && aRecorded !== bRecorded) {
        return aRecorded - bRecorded;
      }
      return String(a.entry_id || '').localeCompare(String(b.entry_id || ''));
    });

    return {
      comparison_history: comparisonHistory,
      promotion_history: promotionHistory,
      regression_history: regressionHistory,
      summary: {
        comparison_count: comparisonHistory.length,
        promotion_count: promotionHistory.length,
        regression_count: regressionHistory.length,
        explicit_verdict_count: comparisonHistory.filter(function (entry) { return Boolean(entry.verdict); }).length,
        explicit_promotion_count: promotionHistory.filter(function (entry) { return Boolean(entry.decision); }).length,
        honesty_note:
          'Stored history view combines the committed public alpha receipt with fixture lineage/cycle records. Missing executed verifier data, promotion gates, and regression enforcement stay blank or pending instead of being invented.',
      },
    };
  }

  function buildTeacherReviewSnapshotFromAutoresearchAlpha(payload, requestPayload) {
    const input = safeObject(payload);
    const receipt = safeObject(input.autoresearch_alpha || input);
    const request = safeObject(requestPayload);
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

    snapshot.task_context = extractAlphaTaskContext(receipt, request);
    snapshot.teacher_evaluation = extractAlphaTeacherEvaluation(receipt, request);
    snapshot.evaluation_summary = extractAlphaEvaluationSummary(receipt, request);
    snapshot.receipt_coverage = mapAlphaArtifactCoverage(receipt);
    snapshot.honesty_badge = 'Stored export — rendered from an actual public-regression autoresearch alpha receipt. Public task-pack context, teacher verdicts, transcript excerpts, and receipt paths are shown when present; frozen task-packet identity and dimensioned scorecards stay empty when the export does not carry them.';
    snapshot.source_contract = 'autoresearch_alpha_receipt';
    snapshot.alpha_receipt = {
      sequence_id: safeString(receipt.sequence_id),
      dataset_manifest_id: safeString(receipt.dataset_manifest_id),
      dataset_version: safeString(receipt.dataset_version),
      control_plane_mode: safeString(receipt.control_plane_mode),
      verdict: safeString(receipt.verdict),
      integrity_mode: safeString(safeObject(receipt.integrity_gate).mode),
      claim_ceiling: safeString(safeObject(receipt.sealing_receipt).claim_ceiling),
    };
    snapshot.evidence_links.alpha_receipt_path =
      safeString(safeObject(receipt.outputs).receipt_path)
      || safeString(safeObject(safeObject(receipt.sealing_receipt).linked_receipt_paths).alpha_receipt);
    snapshot.evidence_links.alpha_request_copy_path =
      safeString(safeObject(receipt.outputs).request_copy_path)
      || safeString(safeObject(safeObject(receipt.sealing_receipt).linked_receipt_paths).alpha_request_copy);
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
      task_context: null,
      baseline: baseline,
      candidate: candidate,
      diff_summary: diffSummary,
      scorecard: scorecardBreakdown,
      teacher_evaluation: null,
      contract: contractSummary,
      evaluation_summary: null,
      verifier_gate_status: verifierGateStatus,
      promotion_decision: promotionDecision,
      receipt_coverage: [],

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
        evidence_index_path: candidate
          ? candidate.receipts.evidence_index_path
          : (baseline ? baseline.receipts.evidence_index_path : null),
        summary_path: candidate
          ? candidate.receipts.summary_path
          : (baseline ? baseline.receipts.summary_path : null),
        audit_bundle_path: candidate
          ? candidate.receipts.audit_bundle_path
          : (baseline ? baseline.receipts.audit_bundle_path : null),
        request_path: candidate
          ? candidate.receipts.request_path
          : (baseline ? baseline.receipts.request_path : null),
        artifact_bundle_path: candidate
          ? candidate.receipts.artifact_bundle_path
          : (baseline ? baseline.receipts.artifact_bundle_path : null),
        result_path: candidate
          ? candidate.receipts.result_path
          : (baseline ? baseline.receipts.result_path : null),
        baseline_receipt_path: candidate
          ? candidate.receipts.baseline_receipt_path
          : (baseline ? baseline.receipts.baseline_receipt_path : null),
        candidate_receipt_path: candidate
          ? candidate.receipts.candidate_receipt_path
          : (baseline ? baseline.receipts.candidate_receipt_path : null),
        evaluation_receipt_path: candidate
          ? candidate.receipts.evaluation_receipt_path
          : (baseline ? baseline.receipts.evaluation_receipt_path : null),
        alpha_receipt_path: null,
        alpha_request_copy_path: null,
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
    extractAlphaTaskContext: extractAlphaTaskContext,
    extractAlphaTeacherEvaluation: extractAlphaTeacherEvaluation,
    extractAlphaEvaluationSummary: extractAlphaEvaluationSummary,
    buildStoredHistorySnapshot: buildStoredHistorySnapshot,
  });
})();

if (typeof window !== 'undefined') {
  window.TEACHER_REVIEW_READ_MODEL = TEACHER_REVIEW_READ_MODEL;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TEACHER_REVIEW_READ_MODEL;
}
