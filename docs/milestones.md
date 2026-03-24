# Hackathon Milestones

This repo is now being driven by **spec-first milestones** so the build can keep moving without Robin being online.

Principle: each milestone must have:
- a written specification
- explicit acceptance criteria
- at least one executable check where practical
- a demoable output that the next milestone can build on

---

## Milestone 1 — Spec Backbone + Demo Contract

**Status:** done

**Goal:** lock the product/story contract so later implementation does not drift.

**Spec docs:**
- `specs/001-demo-contract.md`
- `specs/002-apprentice-vertical.md`

**GitHub tracking:**
- Issue #1 — demo contract and spec-first foundation

**Acceptance criteria:**
- demo-mode role, scenarios, runs, and score deltas are treated as a contract
- required judge-facing pages exist
- README/docs stay aligned with demo-vs-live split
- executable demo-contract checks pass

**Builds on:** existing demo shell

---

## Milestone 2 — Frontend Apprentice Vertical

**Status:** done

**Goal:** make the dogfood vertical legible: Role Foundry is training its own first builder apprentice.

**Spec docs:**
- `specs/002-apprentice-vertical.md`

**GitHub tracking:**
- Issue #2 — apprentice vertical

**Acceptance criteria:**
- landing page clearly frames Robin + Neo teaching the apprentice
- scenarios page makes public curriculum vs hidden holdouts obvious
- run page shows receipts, changed files, transcript excerpt, and policy snapshot
- scorecard page shows score deltas and failure-to-curriculum loop

**Builds on:** Milestone 1

---

## Milestone 3 — Clawith Control Plane in Compose

**Status:** done

**Goal:** replace the current stub with a real control plane service that the repo can talk to honestly.

**Spec docs:**
- `specs/003-clawith-compose.md`
- `specs/004-role-scenario-seed.md`

**GitHub tracking:**
- Issue #3 — Clawith in compose
- Issue #4 — role/scenario seed model

**Acceptance criteria:**
- `docker compose up` can start a real Clawith service when an image is provided
- health check passes
- bootstrap path can seed one role and one scenario set
- live mode remains optional and honest when config is absent

**Builds on:** Milestones 1–2

---

## Milestone 4 — Runner Bridge + First Live Run

**Status:** done

**Goal:** make one real teacher/student run happen without faking consumer OAuth inside Clawith.

**Spec docs:**
- `specs/005-runner-bridge-first-run.md`

**GitHub tracking:**
- Issue #5 — runner bridge and first live run

**Acceptance criteria:**
- runner contract is implemented for at least one backend
- one run record can move from queued → running → completed/failed
- transcript and artifact bundle are stored and viewable
- demo mode still works with zero secrets

**Builds on:** Milestone 3

---

## Milestone 5 — Teacher Evaluation + Iteration Loop

**Status:** done

**Goal:** prove the actual moat: hidden holdout evaluation, failure themes, and score improvement.

**Spec docs:**
- `specs/006-teacher-eval-loop.md`

**GitHub tracking:**
- Issue #6 — teacher evaluation and iteration loop

**Acceptance criteria:**
- holdouts remain sealed from student-facing surfaces
- teacher produces a scorecard with scenario-level results
- failed holdouts become public curriculum themes, not leaked prompts
- at least two iterations can be shown honestly

**Builds on:** Milestone 4

**Landed support slices on this spine:**
- `specs/008-public-benchmark-pack-v1.md` + `docs/public-benchmark-pack-v1.md` freeze the first public-safe benchmark pack v1.
- the Frontend Apprentice public pack now stands at **9 families / 18 episodes** after promoting `intake-alpinejs-curation` into `rf.frontend-apprentice.public.alpine-state-patterns` with 2 RF-authored episodes.
- the Alpine promotion keeps a strict provenance boundary: it is grounded in Alpine public docs/examples only, while raw Alpine GitHub issue/PR/review text remains excluded from the public pack.
- additive receipt provenance now rides on top of the existing runner-bridge outputs; it does not change the teacher score semantics.
- `specs/009-clawith-readiness-probe.md` + `docs/clawith-integration.md` keep the upstream Clawith path adapter-first and read-only.
- `specs/011-live-ui-read-model.md` keeps the browser live shell read-only and payload-faithful for configured exports / fixtures.

**Executable follow-through now landed on this branch:**
- `specs/010-autoresearch-alpha-public-loop.md` + `tests/test_autoresearch_alpha_loop.py` deliver the first honest baseline → candidate-student → candidate-teacher-eval → better/equal/worse loop.
- the integrity gate explicitly allows **public-regression** claims while blocking **sealed-eval** claims until fresh teacher-only families exist outside the public repo.

**Local private holdout scaffold + verified local status:**
- `specs/012-private-holdout-pack.md` + `benchmarks/private-holdout-pack-template.json` + `tests/test_private_holdout_separation.py` define the tracked public contract without shipping any real teacher-only content.
- `scripts/holdout_author.py` + `docs/private-holdout-authoring.md` make that path locally authorable and auditable without changing the public alpha-loop claims.
- Local-only status now: fresh replacement coverage exists for all three previously blocked teacher-only families (`h1` / `h2` / `h3`), and the latest private alpha rerun loaded **6/6** manifest holdouts with a `better` comparison verdict.
- On actual local private-holdout runs, the lane can now emit `pre-run-manifest-commitment.json` before stage execution and surface it as `pre_run_manifest_commitment` for local-only operator auditability/correlation; when a public-safe `pre_run_manifest_attestation` is supplied, that same metadata/reference is preserved into the commitment, `sealing_receipt`, and `operator_checklist.pre_run_manifest_attestation`.

These slices are real. This branch now has an executable **public alpha loop**, evidence that the local private-holdout lane can run honestly with full replacement coverage, a local-only pre-run manifest commitment artifact before stage execution, an optional reference-only `pre_run_manifest_attestation` seam that can be threaded through the public-safe receipt surfaces, and a named `claude_vibecosystem` external-executor beta seam whose backend provenance now threads through `artifact-bundle.json`, candidate/evaluation receipts, per-stage alpha receipts, and `sealing_receipt.execution_backend`. The claim ceiling still stops at backend provenance / claim-boundary evidence on top of local private-holdout alpha execution plus a non-destructive external-executor beta stub; the attestation seam remains `not_verified_by_role_foundry`, and sealed/certified/tamper-proof claims remain blocked.

**Public-safe sealing boundary:**
- `specs/015-sealed-receipt-surface.md` + `tests/test_sealed_receipt_surface.py` add a top-level `sealing_receipt` block that records the current claim ceiling, blocked stronger claims, unmet prerequisites, and (when the local manifest lane is used) a local-only `pre_run_manifest_commitment` recorded before stage execution; if supplied, a public-safe `pre_run_manifest_attestation` is preserved there too and reflected in `operator_checklist.pre_run_manifest_attestation`.
- That sealing boundary now also summarizes backend provenance across the alpha sequence: `artifact-bundle.json` carries `execution_backend` / `execution_backend_contract` / `execution_honesty`, candidate/evaluation receipts expose receipt-level `execution_backend` blocks, per-stage alpha receipts carry stage-local `execution_backend`, and `sealing_receipt.execution_backend` rolls that up into one public-safe claim-boundary summary.
- The optional `pre_run_manifest_attestation` seam is metadata/reference-only: it can preserve a caller-supplied witness/signing reference plus whether the attested manifest hash matches the local manifest hash, but it remains `verification.status: not_verified_by_role_foundry` and does **not** by itself satisfy the stronger tamper-evidence prerequisite.
- `specs/011-live-ui-read-model.md` + `app/live-read-model.alpha-loop.sample.json` + `tests/test_live_ui_read_model.py` now let the read-only live shell render that same boundary record verbatim when it is exported, without relabeling it as a seal, certification, or tamper-proof proof.
- The pre-run manifest commitment, optional reference-only attestation seam, and backend provenance surfaces improve local auditability/operator correlation plus backend claim-boundary evidence only. They do **not** create publication, verified witnessing, signature validation, tamper-proofing, certification, or independent audit.
- This keeps the branch honest: local private-holdout alpha execution is real, the committed browser sample remains a public-regression fixture, and stronger sealing / certification / tamper-proof / audited language remains blocked until new controls actually land.

**Named external-executor beta seam:**
- `specs/016-claude-vibecosystem-backend.md`, `runner_bridge.backends.claude_vibecosystem`, and `tests/test_claude_vibecosystem_beta_seam.py` add a named `claude_vibecosystem` runner-backend selection path.
- Packet-driven runs can now stamp `execution_backend: "claude_vibecosystem"` into `run-object.json` and carry a machine-readable `execution_backend_contract` block through the runtime/request surface.
- The stubbed backend emits `execution_honesty` plus inspectable transcript/artifact/result outputs so the backend id, intended executor path, and current claim boundary stay machine-readable.
- That backend provenance is now preserved all the way into `artifact-bundle.json`, candidate/evaluation receipts, per-stage alpha receipts, and `sealing_receipt.execution_backend` when the alpha/audit surfaces are exported.
- This remains backend provenance / claim-boundary evidence only on top of a contract/provenance-real external-executor beta seam. It is intentionally non-destructive and does **not** create live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, audit, or native Clawith parity.

**Phase F adapter-readiness hardening (F001-F004):**
- `scripts/check_clawith_adapter_prereqs.py` — GET-only prereq checker covering all 6 required F001 categories with explicit ready/blocked/unknown output
- `docs/clawith-adapter-bringup.md` — seam-to-upstream mapping matrix using the 5 allowed F003 statuses
- `tests/test_clawith_adapter_readiness.py` — 19 tests covering F001 probe coverage, F002 zero false-ready, F003 mapping completeness, and F004 non-destructive guarantee
- The prereq checker never reports `ready` when admin or model-pool presence is missing or unknown (F002 hardening)

**Autoresearch Alpha review-spine freeze:**
- In scope on this branch: the public benchmark pack v1, the executable public alpha loop, the read-only live UI/read-model shell, the local private-holdout authoring/separation contract, and the public-safe sealing receipt boundary.
- Out of scope on this branch: sealed-certification claims, partner-integration expansion, native live artifact browsing/storage fan-out, and broad `runner_bridge` core-contract churn.
- If a follow-up change is not required to keep those four contracts coherent, it belongs on another branch.

---

## Milestone 6 — Submission Proof + Partner Wiring

**Status:** queued

**Goal:** package the project for Synthesis with honest receipts, docs, and load-bearing integrations.

**Spec docs:**
- `specs/007-submission-proof.md`

**GitHub tracking:**
- Issue #7 — submission proof, partner wiring, and polish

**Acceptance criteria:**
- `docs/conversation-log.md` reflects the real build story
- submission metadata can be filled honestly from repo evidence
- partner integrations are real, narrow, and non-decorative
- repo/demo are simple for judges to inspect and run

**Builds on:** Milestone 5

---

## Execution rule

We do **not** start a later milestone until the previous milestone has at least:
1. a written spec
2. explicit acceptance criteria
3. a passing check or a documented reason why the check is manual

That is the TDD/spec rail for the rest of the hackathon.
