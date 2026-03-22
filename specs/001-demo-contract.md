# Spec 001 — Demo Contract

## Intent

Lock the current demo shell as a reliable baseline that later live-mode work can build on without breaking the judge-facing story.

## Requirements

1. The repo must expose four judge-facing pages:
   - `app/index.html`
   - `app/scenarios.html`
   - `app/run.html`
   - `app/scorecard.html`
2. Demo mode must remain explicit and honest.
3. The single data seam is `app/data.js`.
4. The seed role must remain a **Frontend Apprentice** / dogfood-builder framing, not a generic customer-support placeholder.
5. The demo must preserve a visible split between public curriculum and hidden holdouts.
6. The demo must preserve visible score deltas between at least two runs.
7. The repo must keep docs that explain:
   - demo mode vs live mode
   - runner bridge rationale
   - ordered milestone plan

## Non-goals

- Real Clawith integration
- Consumer OAuth
- Full artifact viewer backed by live data

## Acceptance checks

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- Manual browser smoke test of the four pages

## Done when

The test suite passes and the repo still tells the same honest story in both code and docs.