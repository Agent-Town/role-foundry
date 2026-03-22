# Clawith Autoresearch Alpha — Honest Scope

This is the first **control-plane-backed alpha path** in the repo.

It is intentionally narrow. The goal is to prove the **dataset → queued run → bridge execution → inspectable run state → receipts** spine without pretending the full Clawith-native stack is already finished.

## Canonical dataset pack

The **single source of truth** for the Frontend Apprentice alpha path is:

- `datasets/frontend-apprentice/alpha-pack.json`

That canonical dataset pack includes:
- the Frontend Apprentice role/scenario seed payload
- the first live request export
- the baseline teacher-eval export (`run-eval-001`)
- the follow-up candidate teacher-eval export (`run-eval-002`)
- the manifest id `frontend-apprentice-alpha-v1`

Compatibility exports are still committed for convenience, but they are derived from the canonical pack:
- `seed/role-foundry-apprentice.json`
- `runner_bridge/examples/first-live-run.json`
- `runner_bridge/examples/teacher-eval-baseline.json`
- `runner_bridge/examples/teacher-eval-loop.json`

Check that they stay in sync:

```bash
python3 -m runner_bridge.dataset_pack check
```

## What the alpha demo actually does

Run:

```bash
python3 -m runner_bridge.alpha_demo
```

By default that command:
1. loads the canonical Frontend Apprentice pack
2. starts the repo-local **Clawith-compatible shim**
3. seeds the role + scenarios through HTTP (`POST /api/roles`, `POST /api/scenarios`)
4. registers the **baseline** run as `queued` via `POST /api/runs`
5. runs the baseline request through the selected backend and records `queued → running → completed`
6. derives the candidate request's `previous_iteration` block from the actual baseline scorecard receipts
7. registers the **candidate** run with explicit lineage (`root_run_id`, `parent_run_id`, `iteration_index`)
8. runs the candidate request through the same seam and records `queued → running → completed`
9. reads both final run records back via `GET /api/runs/{run_id}`
10. writes per-run receipts plus `baseline-candidate-summary.json`

Default backend:
- `local-replay` — zero-secret, judge-safe, deterministic

Optional backend:
- `claude-vibe` — real Claude CLI student run, still behind the same control-plane seam, but not the judge-default path

## Inspectable evidence

After the alpha demo runs, inspect:

- `runtime/control-plane-shim/control-plane-state.json`
- `runtime/alpha-runs/baseline-candidate-summary.json`
- `runtime/alpha-runs/run-eval-001/control-plane-summary.json`
- `runtime/alpha-runs/run-eval-001/student-view.json`
- `runtime/alpha-runs/run-eval-001/teacher-scorecard.json`
- `runtime/alpha-runs/run-eval-002/control-plane-summary.json`
- `runtime/alpha-runs/run-eval-002/request.json`
- `runtime/alpha-runs/run-eval-002/request.private.json`
- `runtime/alpha-runs/run-eval-002/student-view.json`
- `runtime/alpha-runs/run-eval-002/teacher-scorecard.json`
- `runtime/alpha-runs/run-eval-002/artifact-bundle.json`
- `runtime/alpha-runs/run-eval-002/result.json`

The important lines are now both inspectable:
- each run keeps a real state history
- the candidate run carries explicit lineage back to the baseline
- the top-level summary shows the actual baseline → candidate iteration pair

Expected status progression for each bundled run:
- `queued`
- `running`
- `completed`

## Holdout handling

The teacher-eval alpha requests still contain sealed holdout prompts in the raw teacher payload.

What stays true:
- `request.private.json` keeps the raw teacher payload
- `request.json` is redacted for student-safe inspection
- `student-view.json` contains only the student-facing prompt pack: visible scenarios, promoted public themes, and sealed-holdout counts
- `teacher-scorecard.json` contains the teacher-facing score output without copying the sealed holdout prompt text back into student artifacts
- sealed holdout prompt text stays out of `request.json`, `student-view.json`, `teacher-scorecard.json`, `artifact-bundle.json`, and `baseline-candidate-summary.json`

## What is real vs what is not

### Real today
- one canonical dataset pack for the Frontend Apprentice
- one honest two-run baseline → candidate slice through a Clawith-compatible control-plane seam
- inspectable run state transitions (`queued → running → completed`) for both runs
- explicit lineage in run records (`root_run_id`, `parent_run_id`, `iteration_index`)
- judge-visible receipts for dataset manifest, run state, transcript, student view, teacher scorecard, and artifact bundle
- optional Claude student execution through the same bridge seam
- a deterministic `role-foundry-eval/v1` scorecard on `LocalReplayRunner`, including hard integrity gates, weighted category totals, and explicit `better / equal / worse` comparison reasons

### Still local/mockable
- the bundled control-plane server is a **Clawith-compatible shim**, not a claim about native upstream Clawith endpoints
- the default backend is still deterministic local replay
- later live wiring still needs a real teacher/evaluator backend to generate the eval-contract inputs automatically
- the web UI still serves static demo data

### Not claimed
- no native Clawith OAuth or consumer subscription auth
- no claim that upstream Clawith already ships this exact run API
- no claim that Clawith-native model-pool execution is configured for this repo
- no fake live UI backed by control-plane reads yet
- no fake partner wiring or fake autonomous autoresearch loop beyond this narrow alpha slice

## Why this slice matters

This is the first repo path where the control-plane seam is doing real work instead of only being implied in docs:
- the canonical dataset pack is referenced by manifest id
- the control plane sees a queued baseline before execution starts
- the candidate run is derived from the actual baseline receipts instead of a fake retrospective claim
- the bridge mutates both runs over HTTP
- the final run records can be read back and inspected alongside the per-run and sequence artifacts

That is enough to prove the spine honestly, even though the control plane is still a repo-local shim by default.
