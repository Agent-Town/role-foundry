# Judge Demo Script — honest current story

Status: draft-final-review-pending
Use this as the live walkthrough script for judges.
Roundtrip proof references are filled from `origin/review/clawith-vibe-roundtrip-demo-20260323-1000` and `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`.

## One-sentence opener

Role Foundry is a role-training, evaluation, and promotion system for AI apprentices; the first concrete role is a Software Engineer apprentice, and the current proof is an honest public alpha loop plus a local private-holdout boundary, plus one tracked external Clawith -> OpenClaw -> Claude/vibecosystem roundtrip proof.

## 5-7 minute walkthrough

### 1. Frame the product in 20 seconds

Say:

> Role Foundry is the general system. It trains an apprentice against visible curriculum, judges the work, promotes the public lessons, and keeps teacher-only holdouts out of student-visible artifacts.

Show:
- `README.md`
- `app/vision.html`

Land these points:
- this is a **role-training / eval / promotion** system, not a single hard-coded demo
- the loop is the product: define role -> train -> evaluate -> promote lessons -> rerun
- promotion here means **promoting public curriculum and readiness evidence**, not sealed certification

### 2. Show the first concrete role: Software Engineer apprentice

Say:

> The first shipped role is a Software Engineer apprentice improving Role Foundry itself. The repo is both the training ground and the thing being improved.

Show:
- `README.md` section "The current concrete example"
- the main demo UI and score/run surfaces (`app/index.html`, `app/run.html`, `app/scorecard.html`)

Land these points:
- first concrete role = **Software Engineer apprentice**
- current public curriculum is still frontend/product-heavy
- that naming is an honest scope note, not a claim that the full engineering curriculum is already shipped

### 3. Show the proof that exists now: the public alpha loop

Say:

> The first executable proof is the public alpha loop. It proves baseline -> candidate -> teacher-eval -> better/equal/worse comparison on a public, inspectable rail.

Show:
- `specs/010-autoresearch-alpha-public-loop.md`
- `runner_bridge/examples/autoresearch-alpha-public-loop.json`
- `tests/test_autoresearch_alpha_loop.py`
- README section "Autoresearch alpha loop"

Land these points:
- the repo has an **executable public alpha loop**, not just mock screenshots
- it records better/equal/worse comparison receipts and visible score deltas
- the integrity gate explicitly allows **public-regression** claims and blocks fake **sealed-eval** claims

### 4. Show the honesty boundary: local private holdouts

Say:

> The next honest step is local private holdouts. The repo ships the separation contract and authoring path, but not the teacher-only prompts themselves.

Show:
- `docs/private-holdout-authoring.md`
- `specs/012-private-holdout-pack.md`
- `benchmarks/private-holdout-pack-template.json`
- `tests/test_private_holdout_separation.py`

Land these points:
- fresh hidden holdouts can live in a **gitignored local manifest**
- student-visible artifacts stay redacted
- this is enough for a **local private-holdout** alpha run
- this is **not** sealed certification and **not** third-party-sealed evaluation

### 5. Show the external roundtrip proof

Say:

> Separate from the public alpha loop, we also have one tracked proof that an external control-plane path really works: Clawith -> OpenClaw -> Claude/vibecosystem. That proof is intentionally kept separate from native-parity claims.

Cite:
- proof branch: `origin/review/clawith-vibe-roundtrip-demo-20260323-1000`
- proof commit: `4dab2a9866b86df4525d9698a7c844ab538ac61c`
- tracked proof index: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- local receipt roots: `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z` and `artifacts/clawith-gateway/rescue-proof/20260323T025254Z`
- proof entrypoints: `scripts/clawith_ws_roundtrip.js` and `scripts/clawith_vibe_once.py`
- screenshot/log excerpt path: `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z/final_reply.txt`
- required reply markers: `REAL_GATEWAY_ROUNDTRIP_OK_20260323_0958Z` and `CLAWITH_CONTROL_PLANE_VIBECOSYSTEM_EXECUTOR`

Land these points:
- this proves an **external roundtrip path** exists
- Clawith is acting as control plane; OpenClaw is the harness path; Claude/vibecosystem is the execution backend
- raw receipt dirs stay local; the tracked manifest indexes them without committing them
- this is **not** a claim that stock/native Clawith already has full Role Foundry parity
- this is **not** a claim that Clawith-native model-pool bring-up is complete

### 6. End with the non-claims

Say:

> The honest claim is narrower than the ambition. We can prove a public alpha loop, a local private-holdout boundary, and an external roundtrip path. We do not claim native Clawith parity, sealed certification, tamper-proof evaluation, or third-party-sealed holdouts.

## 60-second fallback version

> Role Foundry is a role-training, eval, and promotion system for AI apprentices. The first shipped role is a Software Engineer apprentice improving Role Foundry itself. Today we can honestly prove an executable public alpha loop with better/equal/worse receipts, plus a local private-holdout boundary that keeps teacher-only prompts out of tracked and student-visible artifacts, plus one tracked external Clawith -> OpenClaw -> Claude/vibecosystem roundtrip proof indexed by a repo-visible manifest. What we do not claim is native Clawith parity, sealed certification, tamper-proof eval, or third-party-sealed holdouts.

## Required checks before a final live demo

- [ ] Confirm the local receipt roots cited in the manifest still exist and still match the tracked ids.
- [ ] Confirm the final reply markers still match the proof manifest.
- [ ] Keep the non-claims verbatim unless the underlying proof materially changes.
- [ ] Replace any remaining `FILL_FINAL_REVIEW_*` placeholders in final publish artifacts.
