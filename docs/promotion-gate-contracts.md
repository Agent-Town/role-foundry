# Promotion Gate Contracts

Status: Contract surface implemented; live enforcement is future work.
Spec: specs/014-frontend-product-engineer-20-task-curriculum.md (D002, D003, D004)
Module: runner_bridge/promotion_gates.py
Last updated: 2026-03-23

## Purpose

This document describes the three promotion gates that must all pass
before a candidate generation can be marked `promotion_ready`.  It
also makes explicit what is contract-level support (machine-readable
evaluation logic, schemas, sample artifacts) versus what requires
live gate enforcement (real execution, real holdout scoring, real
regression-pack runs).

## The three gates

### D002 — Private-holdout scoring gate

The candidate must pass both the public threshold (≥ 0.85 weighted) and
the private-holdout threshold (≥ 0.75 weighted).  Both regression_safety
and honesty_boundary_discipline must meet the critical floor (≥ 0.90).

**Contract-level (implemented now):**
- `evaluate_holdout_gate()` accepts public and holdout scorecards.
- Returns `UNAVAILABLE` when holdout data is missing — never fakes a pass.
- Thresholds are frozen in `curriculum.py` and the evaluation contract JSON.

**Live enforcement (future work):**
- Teacher authors private holdout tasks locally; none tracked by git.
- A holdout evaluation pipeline that scores and produces a holdout scorecard.
- Weekly holdout refresh cadence.

### D003 — Repeated-run stability gate

The same candidate × same task packet × same contract version runs 3 times.
At least 2 of 3 must pass the task threshold.  Weighted-score spread must
be ≤ 0.10.  No critical-dimension flip on regression_safety or
honesty_boundary_discipline.

**Contract-level (implemented now):**
- `evaluate_stability_gate()` accepts a list of 3 scorecards.
- Returns `UNAVAILABLE` when fewer than 3 scorecards are provided.
- Spread, passing count, and critical flip detection are all computed.
- Constants: `STABILITY_REQUIRED_RUNS=3`, `STABILITY_MIN_PASSING=2`,
  `STABILITY_MAX_SPREAD=0.10`.

**Live enforcement (future work):**
- Automated scheduling of 3 reruns for a candidate.
- Linking rerun receipts under `runtime/runs/`.

### D004 — Regression gate

Before promotion, the candidate runs the regression pack (last 10
promoted public tasks, or all prior promoted tasks if < 10).  Critical
regressions must be 0, overall pass rate ≥ 0.90, and pass rate must
not be lower than the current promoted baseline.

**Contract-level (implemented now):**
- `evaluate_regression_gate()` accepts a list of per-task results.
- Returns `UNAVAILABLE` when no results provided.
- Critical regression count, pass rate, and baseline comparison are
  all computed.
- Constant: `REGRESSION_MIN_PASS_RATE=0.90`.

**Live enforcement (future work):**
- Automated regression-pack execution using `benchmarks/public-pack-v1/`.
- Baseline pass-rate tracking across promoted generations.

## Machine-readable artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Gate report schema | `data/curriculum/promotion-gate-report.schema.v1.json` | JSON Schema for promotion reports |
| Sample gate report | `data/curriculum/frontend-product-engineer-sample-gate-report.v1.json` | Illustrative fixture (example_only=true) |
| Gate evaluation module | `runner_bridge/promotion_gates.py` | Python logic for all three gates |
| Evaluation contract | `data/curriculum/frontend-product-engineer-evaluation-contract.v1.json` | Frozen thresholds |

## Status vocabulary

Every gate verdict carries two key fields:

- **status**: `passed` | `failed` | `unavailable` | `not_executed`
- **availability**: `live` | `sample` | `missing`

The `honesty_notice` field on the promotion report summarizes which gates
used real data and which did not.

## Honesty boundary

The promotion gate module enforces these invariants:

1. `promotion_ready` is True ONLY when all three gates have status `passed`.
2. A gate with missing input data gets status `unavailable`, never `passed`.
3. Sample/fixture data (example_only) is flagged with `availability: sample`.
4. The `honesty_notice` makes it human-readable which gates were actually evaluated.
5. No private-holdout values are tracked in git.
6. No claim of live repeated-run automation is made.

## Integration with the promotion report

```python
from runner_bridge.promotion_gates import build_promotion_report

report = build_promotion_report(
    role_id="role-frontend-product-engineer",
    evaluation_contract_id="frontend-product-engineer-evaluation-contract-v1",
    evaluation_contract_version="1.0.0",
    candidate_id="gen-42",
    public_scorecard=public_sc,
    holdout_scorecard=None,       # unavailable until holdout pipeline exists
    stability_scorecards=None,    # unavailable until rerun scheduler exists
    regression_results=None,      # unavailable until regression runner exists
)

assert not report.promotion_ready  # blocked: gates are unavailable
print(report.honesty_notice)       # explains what is missing
```
