# Teacher Review Console — Shell v0.1.0

Status: **stored-export-first shell with real-export enrichment** (D001 acceptance test surface)

## What this shell does now

The teacher review console renders a review surface from **stored exports only**.
It prefers the committed real public-regression alpha receipt at
`app/autoresearch-alpha.public-regression.export.json` and its public-safe
request copy at `app/autoresearch-alpha.public-regression.request.json`, then
falls back to the older sample run objects / scorecard / task-packet fixtures
from `data/curriculum/` when that export is unavailable.

It now also reads the committed Phase 5 fixture artifacts
`data/curriculum/frontend-product-engineer-sample-weekly-cycle.v1.json` and
`data/curriculum/frontend-product-engineer-generation-lineage.v1.json` to show
**stored comparison history, promotion history, and regression-gate history**
without pretending those fixture records are live runtime enforcement.

### Fields rendered

| Field | Source | Status |
|-------|--------|--------|
| Frozen task packet identity | Public seed registry fallback only | **Fixture-only** on the current real alpha export |
| Public task-pack context (repo task pack, visible episodes/families, prompt summary) | Real alpha receipt `candidate-student.artifact_bundle.student_view.repo_task_pack` | **Real export capable now** |
| Baseline/candidate diff summary | Real alpha receipt or sample run objects | **Real export capable** |
| Changed files | Real alpha workspace snapshot or sample run objects | **Real export capable** |
| Command results / verifier commands | Real alpha verifier contract or sample run objects | **Real export capable** |
| Transcript excerpts | Real alpha `transcript_excerpt` arrays | **Real export capable now** |
| Teacher verdict / scenario results / public curriculum themes | Real alpha `candidate-teacher-eval.export.result.scorecard` | **Real export capable now** |
| Alpha evaluation context (claim ceiling, deciding axis, epsilon, verifier command list, request refs) | Real alpha receipt + request copy | **Real export capable now** |
| Evidence / receipt links and per-stage receipt coverage | Real alpha `artifact_coverage`, provenance, and outputs | **Real export capable now** |
| Stored comparison history (baseline/candidate/verdict/verifier/promotion columns) | Real alpha `comparison` + `verifier_gate`, plus sample weekly-cycle receipt | **Mixed real + fixture history now** |
| Stored promotion history | Sample generation-lineage registry | **Fixture-only now** |
| Stored regression-gate history | Sample weekly-cycle receipt + generation-lineage registry | **Fixture-only now** |
| Weighted score breakdown (5 dimensions) | Sample scorecard | **Fixture-only** on the current real alpha export |
| Frozen evaluation contract (5 dimensions / thresholds) | Sample evaluation contract | **Fixture-only** on the current real alpha export |
| Promotion decision | Derived from scorecard gate when available | **Fixture-backed / pending** on the current real alpha export |
| Honesty badge | Computed from export vs fixture shape | Automatic |

### Honesty constraints enforced

- Missing inputs produce null/empty fields, never invented data
- The real public-regression export now shows more real context, but it **still**
  leaves frozen task-packet identity and dimensioned scorecards blank because the
  stored export does not carry them
- Stored comparison / promotion / regression history is explicitly labeled by
  source:
  - **real receipt** rows can show exported verdicts and verifier-gate outcomes
  - **fixture lineage / weekly-cycle** rows can show stored promotion or
    regression records, but keep verifier execution / live enforcement blank when
    the artifacts do not carry them
- The shell explicitly separates:
  - **real export context** (public task pack, teacher verdict, transcript excerpts, receipt paths)
  - **fixture-only richness** (frozen task packet, 5-dimension scorecard, frozen contract thresholds, lineage/promotion/regression history)

## Architecture

```text
app/autoresearch-alpha.public-regression.export.json   -->
app/autoresearch-alpha.public-regression.request.json  -->  teacher-review-read-model.js  -->  teacher-review.html
                                                          (buildTeacherReviewSnapshotFromAutoresearchAlpha)

data/curriculum/frontend-product-engineer-sample-weekly-cycle.v1.json   -->
data/curriculum/frontend-product-engineer-generation-lineage.v1.json    -->  teacher-review-read-model.js  -->  teacher-review.html
                                                                          (buildStoredHistorySnapshot)

fallback:

data/curriculum/*.json  -->  teacher-review-read-model.js  -->  teacher-review.html
  (sample run objects)       (buildTeacherReviewSnapshot)       (Alpine.js rendering)
  (sample scorecard)
  (evaluation contract)
  (public seed registry)
```

### Read-model API

```javascript
TEACHER_REVIEW_READ_MODEL.buildTeacherReviewSnapshotFromAutoresearchAlpha(
  /* app/autoresearch-alpha.public-regression.export.json */,
  /* optional app/autoresearch-alpha.public-regression.request.json */
)

TEACHER_REVIEW_READ_MODEL.buildTeacherReviewSnapshot({
  task_packet:          /* from seed registry */,
  baseline_run:         /* from sample run objects */,
  candidate_run:        /* from sample run objects */,
  scorecard:            /* from sample scorecard */,
  evaluation_contract:  /* from evaluation contract */,
})
// Returns: { task, task_context, baseline, candidate, diff_summary, scorecard,
//            teacher_evaluation, contract, evaluation_summary,
//            promotion_decision, verifier_gate_status, evidence_links,
//            receipt_coverage, honesty_badge, data_source, shell_version }

TEACHER_REVIEW_READ_MODEL.buildStoredHistorySnapshot({
  alpha_receipt:       /* optional committed public alpha receipt */,
  weekly_cycle:        /* optional sample weekly-cycle receipt */,
  generation_lineage:  /* optional sample lineage registry */,
})
// Returns: { comparison_history, promotion_history, regression_history, summary }
```

## What still needs a richer runtime bundle

| Capability | Why it is still missing |
|-----------|--------------------------|
| Frozen task packet identity on the real export path | The alpha export carries a repo task pack / public benchmark slice, not a first-class frozen task packet |
| Real 5-dimension weighted scorecard | The alpha export carries teacher scenario results, not the frozen dimension/weight contract used by fixture scorecards |
| Real promotion decision | The current real export carries comparison/verdict context, not a promotion gate object |
| Executed verifier gate (instead of `not_executed`) | The stored alpha path still uses `LocalReplayRunner` / zero-secret replay |
| Real promotion decision on the alpha path | Promotion history is available today from fixture lineage/cycle records, but the committed alpha receipt still does not carry a runtime promotion-gate object |
| Private-holdout scoring | D002 acceptance test |
| Live stability checks across runs | D003 acceptance test |
| Live enforced regression-gate outcomes | D004 acceptance test; the console only shows stored fixture history today |

## Test coverage

`tests/test_teacher_review_console.py` validates:

- Full snapshot with all D001 fields present
- Task identity extraction from seed registry
- Diff summary computation (baseline vs candidate)
- Scorecard breakdown (5 dimensions, weights sum to 1.0)
- Promotion decision logic
- Evidence link extraction
- Contract summary
- Honesty: missing inputs produce nulls, not inventions
- Honesty badge accuracy (fixture vs export)
- Verifier gate status
- Command results extraction
- Workspace isolation fields
- **Real export task-pack context, transcript excerpts, teacher verdicts, evaluation summary, and receipt coverage**
- **Stored history snapshot combines real alpha comparison data with fixture lineage / weekly-cycle records without inventing missing execution or promotion fields**
- **Honesty lock: the real export still leaves frozen task packet / dimensioned contract fields blank**
- HTML page existence and read-model references
- Nav link presence across all pages

## Files

| File | Purpose |
|------|---------|
| `app/autoresearch-alpha.public-regression.export.json` | Real stored public-regression alpha receipt committed for browser consumption |
| `app/autoresearch-alpha.public-regression.request.json` | Public-safe request copy used to enrich real-export evaluation context |
| `app/teacher-review-read-model.js` | Read-model adapter (IIFE, no build step) |
| `app/teacher-review.html` | Teacher review shell page |
| `data/curriculum/frontend-product-engineer-sample-weekly-cycle.v1.json` | Fixture cycle receipt used for stored comparison/regression history |
| `data/curriculum/frontend-product-engineer-generation-lineage.v1.json` | Fixture lineage registry used for stored promotion/regression history |
| `tests/test_teacher_review_console.py` | Contract tests |
| `docs/teacher-review-console.md` | This document |

## Conflict risk

This slice stays in `app/`, `tests/`, `docs/`, and `README.md` only.
It does not touch `runner_bridge/`, private holdout content, or core runtime
contracts.
