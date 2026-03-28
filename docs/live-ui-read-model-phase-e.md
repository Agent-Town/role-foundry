# Live UI read-model Phase E status

## Scope

This note documents the smallest honest Phase E slice landed on top of the executable autoresearch alpha spine.

Goals of this slice:
- keep demo mode explicit and intact
- let the browser adapt the **real** `runner_bridge.autoresearch_alpha` receipt shape
- render only payload-backed fields
- degrade missing fields to empty / pending instead of inventing semantics

## Accepted sample paths

Two local fixtures exercise the adapter:

- `app/live-read-model.alpha-loop.sample.json`
  - rich consumer-side envelope with inline `export` sub-objects
  - useful for full-shell development
  - **not** a claim that upstream emits this browser-ready shape

- `app/live-read-model.alpha-receipt.sample.json`
  - thin executable receipt captured from `runner_bridge.autoresearch_alpha`
  - this is the shape the current public-regression loop really emits:
    - `receipt_type`
    - `comparison_verdict`
    - `score_deltas`
    - thin `stages`
    - `integrity_gate`
    - `blocked_criteria`

Both shapes are recognized by the adapter.

## What is genuinely live now

- Run list for the 3 alpha stages
- Aggregate score summary from `aggregate_score`
- Baseline/candidate comparison linkage
- Verdict label from `comparison_verdict`
- Score delta surfaces computed from real aggregate scores
- Explicit demo/live badge and live-shell tone

## What is still pending

These surfaces stay empty/pending when the thin executable receipt is the only input:

- per-scenario results breakdown
- inline replay lines
- proof bundle / artifact viewer
- student-view prompt summary
- richer failure-theme / curriculum promotion detail

That is intentional. No fake data is injected for pending surfaces.

## Test coverage

Phase E acceptance coverage lives in:
- `tests/test_live_ui_alpha_receipt.py`

That suite covers:
- **E001** read-model schema validity against the real receipt shape
- **E002** baseline/candidate visibility
- **E003** verdict fidelity
- **E004** explicit demo/live marker behavior
- **E005** graceful missing-data degradation
