# Hackathon Milestones

This repo is now being driven by **spec-first milestones** so the build can keep moving without Robin being online.

Principle: each milestone must have:
- a written specification
- explicit acceptance criteria
- at least one executable check where practical
- a demoable output that the next milestone can build on

---

## Milestone 1 — Spec Backbone + Demo Contract

**Status:** in progress

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

**Status:** active

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

**Status:** queued

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

**Status:** queued

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

**Status:** queued

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