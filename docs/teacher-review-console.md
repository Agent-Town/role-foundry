# Teacher Review Console — Shell v0.1.0

Status: **stored-export-first shell with sample fallback** (D001 acceptance test surface)

## What this shell does now

The teacher review console renders a review surface from **stored exports only**.
It now prefers the committed real public-regression alpha receipt at
`app/autoresearch-alpha.public-regression.export.json` and falls back to the
older sample run objects / scorecard / task-packet fixtures from
`data/curriculum/` when that export is unavailable.

### Fields rendered (from stored exports; some sections still fall back to fixture-only richness)

| Field | Source | Status |
|-------|--------|--------|
| Task packet identity | Public seed registry fallback only | Fixture-only on the current real alpha export |
| Baseline/candidate diff summary | Real alpha receipt or sample run objects | Real export capable |
| Changed files | Real alpha workspace snapshot or sample run objects | Real export capable |
| Command results / verifier commands | Real alpha verifier contract or sample run objects | Real export capable |
| Transcript excerpt | Receipt path reference only | Path placeholder |
| Weighted score breakdown (5 dimensions) | Sample scorecard | Fixture-only on the current real alpha export |
| Promotion decision | Derived from scorecard gate when available | Fixture-backed / pending on the current real alpha export |
| Verifier gate status | Real alpha verifier contract or `checks_run` | Real export capable |
| Evidence/receipt links | Receipt paths from real alpha export or sample run objects | Path placeholders |
| Evaluation contract reference | Frozen contract | Fixture-only on the current real alpha export |
| Honesty badge | Computed from export vs fixture shape | Automatic |

### Honesty constraints enforced

- **`example_only: true`** in any input triggers a "sample fixture" badge
- Missing inputs produce null/empty fields, never invented data
- The shell explicitly states what is fixture-backed vs what would need live data

## Architecture

```
app/autoresearch-alpha.public-regression.export.json  -->  teacher-review-read-model.js  -->  teacher-review.html
  (real stored alpha receipt)                            (buildTeacherReviewSnapshotFromAutoresearchAlpha)

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
  /* actual app/autoresearch-alpha.public-regression.export.json receipt */
)

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
| Real transcript content | Deeper receipt surfacing than path refs |
| Live scorecard from evaluation | A richer teacher-review export than the raw alpha receipt |
| Executed verifier gate (instead of `not_executed`) | A backend that really runs verifier commands |
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
| `app/autoresearch-alpha.public-regression.export.json` | Real stored public-regression alpha receipt committed for browser consumption |
| `app/autoresearch-alpha.public-regression.request.json` | Public-safe request copy for the committed real export |
| `app/teacher-review-read-model.js` | Read-model adapter (IIFE, no build step) |
| `app/teacher-review.html` | Teacher review shell page |
| `tests/test_teacher_review_console.py` | Contract tests |
| `docs/teacher-review-console.md` | This document |

## Conflict risk

This slice avoids `runner_bridge/`, `runtime/`, and core contract files.
Changes are confined to `app/`, `tests/`, and `docs/` with nav-link additions
to existing HTML pages (single-line additions that merge cleanly).
