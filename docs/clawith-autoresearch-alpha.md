# Clawith Autoresearch Alpha — Honest Scope

This is the first **control-plane-backed alpha path** in the repo.

It is intentionally narrow. The goal is to prove the **dataset → queued run → bridge execution → inspectable run state → receipts** spine without pretending the full Clawith-native stack is already finished.

## Canonical dataset pack

The **single source of truth** for the Frontend Apprentice alpha path is:

- `datasets/frontend-apprentice/alpha-pack.json`

That canonical dataset pack includes:
- the Frontend Apprentice role/scenario seed payload
- the first live request export
- the teacher-eval request export used by the alpha demo
- the manifest id `frontend-apprentice-alpha-v1`

Compatibility exports are still committed for convenience, but they are derived from the canonical pack:
- `seed/role-foundry-apprentice.json`
- `runner_bridge/examples/first-live-run.json`
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
4. registers a **queued** run via `POST /api/runs`
5. runs `runner_bridge.cli` logic through the selected backend
6. lets the bridge patch **running** and final status back through `PATCH /api/runs/{run_id}`
7. reads the final run record back via `GET /api/runs/{run_id}`
8. writes evidence receipts into the run directory

Default backend:
- `local-replay` — zero-secret, judge-safe, deterministic

Optional backend:
- `claude-vibe` — real Claude CLI student run, still behind the same control-plane seam, but not the judge-default path

## Inspectable evidence

After the alpha demo runs, inspect:

- `runtime/control-plane-shim/control-plane-state.json`
- `runtime/alpha-runs/run-eval-002/control-plane-summary.json`
- `runtime/alpha-runs/run-eval-002/dataset-manifest.json`
- `runtime/alpha-runs/run-eval-002/request.json`
- `runtime/alpha-runs/run-eval-002/request.private.json`
- `runtime/alpha-runs/run-eval-002/artifact-bundle.json`
- `runtime/alpha-runs/run-eval-002/result.json`

The important line: the run state history is now **inspectable**.

Expected status progression on the bundled path:
- `queued`
- `running`
- `completed`

## Holdout handling

The teacher-eval alpha request still contains sealed holdout prompts in the raw request.

What stays true:
- `request.private.json` keeps the raw teacher payload
- `request.json` is redacted for student-facing artifacts
- the student-facing artifact bundle contains public curriculum, public failure themes, and sealed holdout counts
- sealed holdout prompt text stays out of student-facing receipts

## What is real vs what is not

### Real today
- one canonical dataset pack for the Frontend Apprentice
- one honest run lifecycle through a Clawith-compatible control-plane seam
- inspectable run state transitions (`queued → running → completed`)
- judge-visible receipts for dataset manifest, run state, transcript, and artifact bundle
- optional Claude student execution through the same bridge seam

### Still local/mockable
- the bundled control-plane server is a **Clawith-compatible shim**, not a claim about native upstream Clawith endpoints
- the default backend is still deterministic local replay
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
- the control plane sees a queued run before execution starts
- the bridge mutates that run over HTTP
- the final run record can be read back and inspected alongside the artifacts

That is enough to prove the spine honestly.
