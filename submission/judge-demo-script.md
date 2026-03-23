# Judge Demo Script — live 2-3 minute walkthrough

Status: final-review-ready
Canonical final packet artifact for this branch.

Keep this live demo narrow. The point is not to show every file. The point is to make four honest claims quickly, then stop before the story gets inflated.

## One-sentence opener

Role Foundry trains, evaluates, and promotes role-scoped agents; the first role is a Software Engineer apprentice improving Role Foundry itself, and today’s honest proof is a public-regression alpha loop, a local private-holdout boundary, and one real external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip.

## What to make clear in under 3 minutes

- this is a **system** for role-scoped agent training/eval/promotion, not a one-off agent demo
- the first concrete role is a **Software Engineer apprentice** improving Role Foundry itself
- three things are real today:
  - an executable **public alpha / public-regression loop**
  - a **local private-holdout** separation boundary
  - one tracked **external roundtrip proof**
- three things are **not** being claimed:
  - native Clawith parity
  - sealed certification / sealed eval
  - tamper-proof or third-party-sealed evaluation

## Live route: 4 stops, 2-3 minutes total

### Stop 1 — What the product is (20-30 sec)

Show:
- `README.md`
- `app/vision.html`

Say:

> Role Foundry is the general system. It trains a role-scoped apprentice, evaluates the work, promotes the public lessons, and reruns the loop. The first concrete role is a Software Engineer apprentice improving Role Foundry itself.

Land:
- this is a **train -> evaluate -> promote -> rerun** product loop
- promotion here means **promoting public curriculum and readiness evidence**
- promotion does **not** mean sealed certification

### Stop 2 — What is executable now: the public alpha loop (35-45 sec)

Show:
- `app/run.html`
- `app/scorecard.html`

If a judge asks where the implementation/proof lives, cite:
- `specs/010-autoresearch-alpha-public-loop.md`
- `runner_bridge/examples/autoresearch-alpha-public-loop.json`
- `tests/test_autoresearch_alpha_loop.py`

Say:

> The first executable proof is the public alpha loop. We can run baseline versus candidate, have teacher evaluation score the result, and record a better, equal, or worse outcome on a public rail.

Land:
- the public loop is **real and executable**, not just screenshots
- it produces visible **better/equal/worse** receipts and score deltas
- this supports a **public-regression / public-alpha** claim
- it does **not** imply hidden or sealed evaluation

### Stop 3 — The honesty boundary: local private holdouts (30-40 sec)

Show:
- `docs/private-holdout-authoring.md`
- `specs/012-private-holdout-pack.md`
- `benchmarks/private-holdout-pack-template.json`

If a judge asks where the separation proof lives, cite:
- `tests/test_private_holdout_separation.py`

Say:

> Separately, we have a local private-holdout discipline. Teacher-only prompts can live in a gitignored local manifest, while tracked and student-visible artifacts stay redacted.

Land:
- local/private holdout discipline is **real**
- teacher-only prompts stay outside tracked and student-visible artifacts
- this supports a **local private-holdout** claim
- this is **not** sealed certification, **not** tamper-proof eval, and **not** third-party sealing

### Stop 4 — One real external roundtrip proof (35-45 sec)

Show:
- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- `submission/roundtrip-proof/final-reply.txt`
- `submission/checklists/roundtrip-receipt-audit-2026-03-23.md`

If needed, also cite:
- `submission/roundtrip-proof/roundtrip-proof.export.json`
- `scripts/clawith_ws_roundtrip.js`
- `scripts/clawith_vibe_once.py`

Say:

> We also have one real external roundtrip path. Clawith acts as the control plane, OpenClaw is the harness path, and Claude/vibecosystem is the executor. The packet includes a tracked manifest, a portable export bundle, and an audit note.

Land:
- this proves **one external control-plane path** exists
- reviewers can inspect tracked packet artifacts without needing local raw receipt trees
- raw receipt roots remain maintainer-local for deep revalidation only
- this is **not** a native Clawith parity claim
- this is **not** a native model-pool bring-up claim

### Close cleanly (10-15 sec)

Say:

> So the honest claim today is narrow: a real public alpha loop, a real local private-holdout boundary, and one real external roundtrip proof. We do not claim native Clawith parity or sealed certification.

Optional future hook, only if asked:

> A possible next differentiator is ERC-8004/Base identity plumbing, but that is not landed evidence on this branch and it is not part of today’s claim.

## 45-second compressed version

> Role Foundry is a role-training, eval, and promotion system for role-scoped agents. The first concrete role is a Software Engineer apprentice improving Role Foundry itself. Today we can honestly show three things: an executable public-regression alpha loop with better/equal/worse scoring, a local private-holdout boundary that keeps teacher-only prompts out of tracked and student-visible artifacts, and one tracked external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip proof. We do not claim native Clawith parity, sealed certification, or tamper-proof evaluation.

## Q&A handling

Keep answers short. Recenter on the narrow claim boundary. If a question starts to widen scope, answer it directly and step back to the three proven things above.

Supporting note for short answers:
- `submission/judge-qa-note.md`

## Hard non-claims

Do not upgrade this branch into claims of:
- native Clawith parity
- native model-pool bring-up completion
- sealed certification
- sealed eval
- tamper-proof evaluation
- third-party-sealed holdouts
- ERC-8004/Base as landed on this branch

## Pre-demo sanity checks

- [ ] Confirm `submission/conversation-log.md`, `submission/evidence-proof-manifest.json`, and `submission/submission-metadata.json` still agree on the final review branch + commit.
- [ ] Confirm the roundtrip manifest, export bundle, and final reply markers still match.
- [ ] Keep the non-claims verbatim unless the underlying proof materially changes.
