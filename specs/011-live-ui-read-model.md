# Spec 011 — Live UI Read-Model Adapter

## Goal

Let the browser UI consume **configured read-only exports** without pretending the
full native live stack is already wired.

This spec is intentionally narrow:
- **demo mode remains the default**
- the browser may render a configured JSON export via `liveDataUrl`
- missing live fields stay empty instead of being invented
- no core `runner_bridge` contract churn is required for the UI slice

## Accepted payload shapes

The browser adapter accepts three live-oriented payload shapes:

1. **UI snapshot**
   - already shaped like the demo store (`role`, `runs`, `scores`, `artifacts`, ...)
2. **generic read-model envelope**
   - top-level `control_plane_summary` with inline run exports
3. **autoresearch alpha envelope / receipt**
   - current alpha-loop receipt shape (`baseline-eval` → `candidate-student` → `candidate-teacher-eval` → `comparison`)
   - may also include the top-level public-safe `sealing_receipt` block from spec 015
   - optionally wrapped in a consumer-side envelope that also carries `role` / `scenarios`

## Autoresearch alpha mapping

The browser maps the current alpha-loop shape into the existing UI snapshot model
without inventing new score semantics:

- `baseline-eval` → scored run
- `candidate-student` → visible run row + artifact row, but **no fake teacher scorecard**
- `candidate-teacher-eval` → scored run + comparison target
- `comparison` / `verdict` → iteration notes and comparison context
- top-level `sealing_receipt` → live read-model boundary surface only when exported
- exact comparison fields (`verdict`, `deciding_axis`, `baseline_total_score`, `candidate_total_score`, `total_score_delta`, `category_deltas`, `reasons`) stay source-faithful when present
- exact sealing boundary fields (`claim_ceiling`, `status`, `blocked_claims`, `stronger_claim_prerequisites`, `operator_checklist`, `honesty_note`) stay source-faithful when present

### Important rules

- The browser may rename fields into the existing shell contract, but it must not
  fabricate extra scoring concepts.
- The browser may surface `sealing_receipt` only as a boundary record. It must
  not relabel it as a seal, certification, tamper-proof proof, or pass/fail score.
- The comparison target for `candidate-teacher-eval` is the previous **scored**
  run, not blindly the previous run row.
- Student-safe fields (prompt pack, public curriculum themes, sealed holdout
  count) come from exported student-view data when present.
- Proof bundle panels render only from exported receipts/artifact data.

## UX behavior

- Demo mode stays explicit and first-class.
- Live mode is a **shell**: it renders configured data only.
- If live loading fails, the UI falls back to demo mode with a visible fallback
  label.
- If a live export omits a field, the matching panel stays empty or pending.

## Non-goals

- no browser fan-out across runtime directories
- no native Clawith parity claim
- no auth or OAuth additions
- no live artifact storage browser
- no `runner_bridge` API or receipt contract rewrite just for the UI

## Sample path

A committed sample export may be used to exercise the adapter locally, e.g.

- `app/live-read-model.alpha-loop.sample.json`

That sample is a **consumer-side fixture** for the browser shell. It is not a
claim that upstream Clawith already emits this exact browser-ready envelope.
