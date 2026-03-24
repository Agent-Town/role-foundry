# Conversation Log

_Curated build log for Synthesis hackathon submission._

This log captures the key decisions, not every message. It exists because the Synthesis submission values honest `conversationLog` and build history.

---

## 2026-03-22 — Direction lock

**Decision:** Build Role Foundry as the hackathon submission.

**Context:** Evaluated 10 concepts across partner-track fit, technical depth, and demo clarity. Role Foundry (teacher/student agent training with hidden holdout evaluation) ranked #1 because:
- The evaluation loop is non-trivial and produces real evidence
- Hidden holdouts make quality claims credible instead of vibes-based
- It naturally produces scorecards, artifact bundles, and conversation logs that match what the submission format rewards
- It stacks 6-8 partner tracks without shallow integration

**Rejected alternatives:** AutoFounder (#2), YieldOS (#3), Agent Desk (#4). See `docs/synthesis-hackathon-ideation.md` for full ranking.

---

## 2026-03-22 — Architecture lock

**Decision:** One Clawith instance as control plane. No nested Clawith stacks.

**Key choices:**
- Clawith = control plane (agent registry, run registry, evaluation store)
- Claude + vibecosystem = student/builder execution backend
- Codex = teacher/critic/evaluator backend (different model family to avoid self-congratulatory grading)
- Claw3D = visualization layer (viewer, not source of truth)
- Per-run isolation is non-negotiable for holdout integrity

See `docs/synthesis-hackathon-stack-architecture.md` for details.

---

## 2026-03-22 — Wallet and auth stance

**Decision:** Bring-your-own-wallet for hackathon. No Privy dependency.

**Why:** Portal onboarding (especially the mass-adoption wallet path) is still flaky. Wrong dependency for a hackathon-critical core loop.

**Decision:** No consumer OAuth through Clawith for the hackathon.

**Why:** Clawith doesn't natively support consumer OAuth subscriptions. Rather than fake it, we use a runner-bridge pattern. See `docs/runner-bridge.md`.

---

## 2026-03-22 — Scaffold created

**What shipped:**
- Demo UI (static HTML/JS) with pre-baked example data for roles, scenarios, runs, and scorecards
- Docker Compose stack (web + postgres + redis, Clawith stubbed)
- Documentation suite (ideation, architecture, connection strategy)
- README rewritten for hackathon clarity

**What's stubbed:**
- Clawith service (needs image)
- Bootstrap/seed service
- Live mode (needs Clawith + LLM keys)

---

## 2026-03-22 — Spec-first milestone rail added

**Decision:** Move the repo to milestone-driven, spec-first execution so work can continue cleanly without Robin being online.

**What changed:**
- Added `docs/milestones.md` as the ordered hackathon roadmap
- Added `specs/001`–`specs/007` to define milestone contracts and acceptance criteria
- Added `tests/test_demo_contract.py` so the current demo shell has an executable baseline contract

**Why:** The hackathon is moving too fast for vague TODOs. Each slice now needs a written spec, explicit acceptance criteria, and a runnable check before later slices build on top of it.

**GitHub tracking:** Repo milestones `M1`–`M6` were created along with issues #1–#7 so the hackathon roadmap is public and inspectable.

---

## 2026-03-22 — Milestones 1 and 2 landed

**Outcome:**
- Milestone 1 (spec backbone + demo contract) is now in the repo with executable tests.
- Milestone 2 (Frontend Apprentice vertical) is now committed as the first coherent judge-facing product slice.

**Evidence:**
- `tests/test_demo_contract.py` passes
- app pages now show the apprentice story, sealed holdouts, proof bundle, score deltas, and failure-to-curriculum loop
- GitHub history now includes milestone/spec commits rather than only ideation docs

---

## 2026-03-22 — Milestone 3 landed honestly

**Outcome:** The repo now has a real live-mode compose lane without pretending upstream/native parity is solved.

**What changed:**
- `docker-compose.yml` gained a profile-gated Clawith service path
- the bootstrap lane became a **read-only probe** instead of a destructive seed shortcut
- `docs/clawith-integration.md` now explains the real upstream surface, the adapter-first gaps, and the honest next step when parity is absent

**Evidence:**
- `tests/test_milestone3_contract.py` passes
- `seed/probe_clawith.py` exists and stays read-only
- the probe/docs explicitly call out `/api/runs/{run_id}` as an adapter-side contract, not an observed native upstream write path

---

## 2026-03-22 — Milestone 4 landed as the first bridge-backed run slice

**Outcome:** Role Foundry can now execute one narrow run lifecycle end to end without fake consumer OAuth.

**What changed:**
- `python3 -m runner_bridge.cli` validates a request, marks the run running, executes `LocalReplayRunner`, stores transcript/artifact outputs, and patches final state back to a Clawith-compatible surface
- the bridge supports a zero-secret local/mockable path when a real control plane or provider credentials are unavailable
- failure remains first-class and still emits inspectable receipts

**Evidence:**
- `tests/test_milestone4_runner_bridge.py` passes
- `runner_bridge/examples/first-live-run.json` exercises the contract
- `docs/runner-bridge.md` documents the request/result/patch shape honestly

---

## 2026-03-22 — Milestone 5 + alpha support slices landed

**Outcome:** The repo now carries a coherent teacher-eval/iteration spine plus the minimum support work for the next alpha step.

**What changed:**
- teacher evaluation now produces a scorecard with scenario notes, aggregate score, public curriculum themes, and iteration deltas
- the bridge writes redacted/public and raw/private request artifacts separately so holdouts stay sealed from the student bundle
- additive receipt provenance files make the baseline/candidate/evaluation lineage easier to audit without changing scoring semantics
- a public-safe benchmark pack v1 was frozen from student-visible families only; holdout-derived families remain blocked pending rewrite
- the browser can consume configured read-only live/read-model exports, including an alpha-loop-shaped fixture

**Important honesty line:** the committed alpha-loop export is a **consumer-side sample/fixture**. It is not a claim that the first fully real baseline → candidate → teacher-eval loop has already run end to end on this branch.

**Evidence:**
- `tests/test_milestone5_teacher_eval_loop.py` passes
- `tests/test_public_benchmark_pack_v1.py` passes
- `tests/test_live_ui_read_model.py` passes
- `docs/public-benchmark-pack-v1.md` and `specs/008-public-benchmark-pack-v1.md` define the public-safe benchmark scope
- `specs/011-live-ui-read-model.md` defines the read-only browser adapter contract

---

## 2026-03-23 — First executable public alpha loop landed

**Outcome:** The repo can now execute the first honest public alpha loop end to end instead of only showing supporting fixtures.

**What changed:**
- `python3 -m runner_bridge.autoresearch_alpha` now orchestrates `baseline-eval` → `candidate-student` → `candidate-teacher-eval`
- the loop emits a concrete **better / equal / worse** comparison receipt with artifact coverage for every stage
- the candidate-student stage uses only public-safe benchmark material plus promoted public failure themes
- the integrity gate records that public regression is okay today while fresh sealed-eval claims remain blocked

**Evidence:**
- `tests/test_autoresearch_alpha_loop.py` passes
- `runner_bridge/examples/autoresearch-alpha-public-loop.json` exercises the contract
- README and bridge docs say plainly that this is a **public** alpha loop, not a sealed certification path

---

## 2026-03-23 — Clean spine promotion + private holdout scaffold

**Outcome:** The review branch was tightened so the docs tell one coherent story and the next sealed-holdout step has an honest public contract.

**What changed:**
- `docs/milestones.md` now marks Milestones 3–5 done, records the executable public alpha loop, and keeps Milestone 6 queued
- README now links the benchmark/probe/alpha/live-read-model/private-holdout support docs and says plainly that the alpha-loop browser export is still a sample fixture
- demo data now includes explicit teacher/student actors and student-view metadata so the UI contract matches the teacher-eval story already present elsewhere
- duplicate spec numbering was resolved by keeping `specs/010-autoresearch-alpha-public-loop.md` for the executable loop, moving the live UI read-model contract to `specs/011-live-ui-read-model.md`, and placing the private holdout contract at `specs/012-private-holdout-pack.md`
- the repo now carries a public-safe private-holdout scaffold: template, gitignore rule, and separation tests, but **no real teacher-only content**

**Evidence:**
- targeted and full test passes on the promotion branch
- no broad `runner_bridge` contract rewrite was needed for this cleanup

---

## 2026-03-23 — External gateway roundtrip proof folded into submission packaging

**Outcome:** The submission/readiness branch now carries one honest proof that Clawith can remain the control plane while Claude + vibecosystem acts as the external executor through the upstream gateway contract.

**What changed:**
- `docs/clawith-vibecosystem-real-path.md` now documents the exact adapter-first lane and links the packaged proof index
- `scripts/clawith_link_openclaw.py` creates or reuses the linked OpenClaw agent and saves the gateway key under `runtime/`
- `scripts/clawith_vibe_once.py` captures one gateway-worker cycle with Claude Code + vibecosystem and writes receipts under `artifacts/clawith-gateway/...`
- `scripts/clawith_ws_roundtrip.js` sends a real user chat message over the stock Clawith websocket/session path and captures the visible assistant reply under `artifacts/clawith-roundtrip/...`
- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json` indexes the local receipt roots without committing the raw artifacts themselves

**Evidence:**
- referenced local receipt roots: `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z/` and `artifacts/clawith-gateway/rescue-proof/20260323T025254Z/`
- required final reply markers: `REAL_GATEWAY_ROUNDTRIP_OK_20260323_0958Z` and `CLAWITH_CONTROL_PLANE_VIBECOSYSTEM_EXECUTOR`
- the tracked proof index records the agent/session/message ids used for the capture

**Important honesty line:** this proves the external gateway + Claude/vibecosystem executor lane only. It does **not** prove native Clawith model-pool parity, stock upstream Role Foundry API parity, sealed evaluation, or tamper-proof certification.


---

## 2026-03-24 — Public-safe sealing receipt boundary + pre-run manifest commitment + optional attestation seam + live-shell surfacing folded into the overnight handoff

**Outcome:** The freshest overnight handoff branch now carries a machine-readable receipt boundary, a local-only pre-run manifest commitment artifact for private-holdout runs, an optional reference-only pre-run manifest attestation seam, and a read-only live-shell rendering path that says exactly what the current alpha/read-model export can and cannot claim.

**What changed:**
- `specs/015-sealed-receipt-surface.md` defines a top-level `sealing_receipt` block on the alpha receipt as a public-safe boundary record, not a seal
- `runner_bridge.autoresearch_alpha` now emits the claim ceiling, status tier, blocked stronger claims, unmet prerequisites, and a private-manifest fingerprint labeled `local_operator_correlation_only`; when the local manifest lane is used it also writes `pre-run-manifest-commitment.json` before stage execution, surfaces a public-safe `pre_run_manifest_commitment` summary in the receipt, and can preserve a caller-supplied public-safe `pre_run_manifest_attestation` into both that commitment and the top-level `sealing_receipt`
- the same sealing boundary now reflects that seam in `operator_checklist.pre_run_manifest_attestation`, while keeping the attestation explicitly metadata/reference-only with `verification.status: not_verified_by_role_foundry`
- `specs/011-live-ui-read-model.md`, `app/live-read-model.alpha-loop.sample.json`, and the scorecard live shell now surface the same boundary when a `sealing_receipt` is exported, while keeping the committed browser sample at public-regression alpha rather than inventing a stronger seal/certification story
- README + handoff/status docs now say plainly that the local private-holdout alpha lane is real, that the pre-run commitment plus optional attestation seam improve local auditability/operator correlation/reference threading only, and that stronger sealing / certification / tamper-proof language is still blocked

**Evidence:**
- `tests/test_sealed_receipt_surface.py` passes and now pins conservative `pre_run_manifest_attestation` behavior
- `tests/test_autoresearch_alpha_loop.py` now pins the local private-holdout `sealing_receipt` + `pre_run_manifest_commitment` threading, including `pre_run_manifest_attestation` propagation and the operator checklist flag
- `tests/test_live_ui_read_model.py` now pins the read-model/browser surfacing of the sealing boundary
- no private holdout content was added to git

**Important honesty line:** the new `sealing_receipt`, local-only `pre_run_manifest_commitment`, and optional `pre_run_manifest_attestation` explain the next claim boundary and improve local operator auditability/correlation plus public-safe reference threading. The attestation seam is metadata/reference-only, remains `not_verified_by_role_foundry`, and does **not** itself create publication, verified witnessing, signature validation, tamper-proofing, certification, or independent audit.

---

## 2026-03-24 — Alpine docs/examples promotion surfaced in public-safe status docs

**Outcome:** The overnight handoff and milestone/status surfaces now reflect the newly landed Alpine promotion instead of stopping at the earlier Google-only pack counts.

**What changed:**
- `intake-alpinejs-curation` is now surfaced as promoted into `rf.frontend-apprentice.public.alpine-state-patterns`
- the family ships 2 RF-authored public episodes (`pbpv1-e17`, `pbpv1-e18`), bringing the Frontend Apprentice public benchmark pack to **9 families / 18 episodes**
- status docs now say plainly that this promotion is grounded in Alpine public docs/examples only; raw Alpine GitHub issue/PR/review text remains excluded from the public pack

**Evidence:**
- `docs/public-benchmark-pack-v1.md`, `data/episode-registry/public-benchmark-pack-v1.json`, and `benchmarks/public-pack-v1/episode-family-registry.json` all show the promoted family and pack counts
- `tests/test_public_benchmark_pack_v1.py`, `tests/test_teacher_source_curriculum.py`, and `tests/test_dataset_flywheel_phase_g.py` remain the contract checks for the public-pack, source-intake, and Phase G surfaces

**Important honesty line:** Alpine is public-safe here only because the promoted family was manually rewritten from Alpine public docs/examples into original RF-authored episodes. Raw Alpine GitHub issue/PR/review text is still excluded.

---

## 2026-03-24 — `claude_vibecosystem` external-executor beta seam surfaced in the overnight status spine

**Outcome:** The repo now tells one coherent public-safe story about the newly landed `claude_vibecosystem` backend seam instead of stopping at the pre-run manifest commitment layer.

**What changed:**
- `specs/016-claude-vibecosystem-backend.md` formalizes a named `claude_vibecosystem` runner-backend as a narrow external-executor beta seam
- `runner_bridge.cli`, `runner_bridge.packet_runtime`, and `runner_bridge.backends.claude_vibecosystem` let packet-driven runs stamp `execution_backend: "claude_vibecosystem"` plus a machine-readable `execution_backend_contract` block into the run/runtime surfaces
- the backend stub emits `execution_honesty` in `result.json`, keeping backend naming, intended executor path, and claim boundaries machine-readable
- `docs/overnight-handoff-20260323-phase-g.md` and `docs/milestones.md` now say plainly that this seam is real as a contract/provenance surface, but still a non-destructive stub

**Evidence:**
- `tests/test_claude_vibecosystem_beta_seam.py` pins the backend registry, contract, and docs surfacing
- `tests/test_packet_runtime_bridge_e2e.py` pins `execution_backend: "claude_vibecosystem"`, `execution_backend_contract`, and the conservative `execution_honesty` block
- `docs/clawith-vibecosystem-real-path.md` remains the reference for the separate real gateway/executor proof lane

**Important honesty line:** this is a contract/provenance-real external-executor beta seam only. It does **not** create live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, or native Clawith parity.

---

## 2026-03-24 — Backend provenance receipt hardening surfaced across alpha/audit status docs

**Outcome:** The overnight handoff, milestone status, and curated build log now explicitly reflect that backend provenance no longer stops at packet/runtime setup; it now threads through the public-safe alpha/audit receipt surfaces too.

**What changed:**
- `docs/overnight-handoff-20260323-phase-g.md` and `docs/milestones.md` now call out that `artifact-bundle.json` carries `execution_backend`, `execution_backend_contract`, and `execution_honesty`
- those same docs now say plainly that candidate/evaluation receipts carry receipt-level `execution_backend` blocks when present
- the status spine now points out that each alpha stage export carries its own `execution_backend`, and the top-level `sealing_receipt.execution_backend` summarizes backend provenance across the full alpha sequence
- the public-safe wording now keeps the honesty boundary explicit: this is backend provenance / claim-boundary evidence only, not live execution, independent isolation, sealed eval, certification, tamper-proofing, audit, or native Clawith parity

**Evidence:**
- `tests/test_packet_runtime_bridge_e2e.py` pins backend provenance in `artifact-bundle.json` plus receipt-level `execution_backend` on candidate receipts
- `tests/test_autoresearch_alpha_loop.py` pins `execution_backend` on all three alpha stages plus the rolled-up `sealing_receipt.execution_backend` summary
- `tests/test_sealed_receipt_surface.py` pins the `sealing_receipt.execution_backend` summary, stage coverage, and conservative honesty notes

**Important honesty line:** this docs/status reconcile only surfaces newly landed backend provenance and claim-boundary evidence. It does **not** itself create live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, audit, or native Clawith parity.
