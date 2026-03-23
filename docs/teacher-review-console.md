# Teacher Review Console — Shell v0.1.0

Status: **fixture-backed shell** (D001 acceptance test surface)

## What this shell does now

The teacher review console renders a review surface from **stored exports only**.
It consumes sample run objects, scorecards, task packets, and evaluation contracts
from `data/curriculum/` and presents them in a structured decision surface.

### Fields rendered (all from stored fixtures)

| Field | Source | Status |
|-------|--------|--------|
| Task packet identity | Public seed registry | Real fixture |
| Baseline/candidate diff summary | Sample run objects | Real fixture |
| Changed files | Sample run objects | Real fixture |
| Command results (exit codes, capture refs) | Sample run objects | Real fixture |
| Transcript excerpt | Receipt path reference only | Path placeholder |
| Weighted score breakdown (5 dimensions) | Sample scorecard | Real fixture |
| Promotion decision | Derived from scorecard gate | Computed from fixture |
| Verifier gate status | Derived from checks_run | Computed from fixture |
| Evidence/receipt links | Receipt paths from run objects | Path placeholders |
| Evaluation contract reference | Frozen contract | Real fixture |
| Honesty badge | Computed from example_only flags | Automatic |

### Honesty constraints enforced

- **`example_only: true`** in any input triggers a "sample fixture" badge
- Missing inputs produce null/empty fields, never invented data
- The shell explicitly states what is fixture-backed vs what would need live data

## Architecture

```
data/curriculum/*.json  -->  teacher-review-read-model.js  -->  teacher-review.html
  (sample run objects)       (buildTeacherReviewSnapshot)       (Alpine.js rendering)
  (sample scorecard)
  (evaluation contract)
  (public seed registry)
```

### Read-model API

```javascript
TEACHER_REVIEW_READ_MODEL.buildTeacherReviewSnapshot({
  task_packet:          /* from seed registry */,
  baseline_run:         /* from sample run objects */,
  candidate_run:        /* from sample run objects */,
  scorecard:            /* from sample scorecard */,
  evaluation_contract:  /* from evaluation contract */,
})
// Returns: { task, baseline, candidate, diff_summary, scorecard, contract,
//            promotion_decision, verifier_gate_status, evidence_links,
//            honesty_badge, data_source, shell_version }
```

## What still needs live runtime data

| Capability | Blocked on |
|-----------|-----------|
| Real transcript content | Runner bridge receipt capture |
| Live scorecard from evaluation | Evaluation loop wiring |
| Verifier gate from runner bridge | Verifier contract integration |
| Private-holdout scoring | D002 acceptance test |
| Stability checks across runs | D003 acceptance test |
| Regression gate history | D004 acceptance test |
| Multiple run comparison | Live run storage |

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
- HTML page existence and read-model references
- Nav link presence across all pages

## Files

| File | Purpose |
|------|---------|
| `app/teacher-review-read-model.js` | Read-model adapter (IIFE, no build step) |
| `app/teacher-review.html` | Teacher review shell page |
| `tests/test_teacher_review_console.py` | Contract tests |
| `docs/teacher-review-console.md` | This document |

## Conflict risk

This slice avoids `runner_bridge/`, `runtime/`, and core contract files.
Changes are confined to `app/`, `tests/`, and `docs/` with nav-link additions
to existing HTML pages (single-line additions that merge cleanly).
