# Judge Demo Script — live 2-3 minute walkthrough

Status: submission-published
Canonical live walkthrough for the submission packet on this branch.

Keep this live demo narrow. The point is not to show every file. The point is to make the provenance chain legible fast, then stop before the story gets inflated.

## One-sentence opener

Role Foundry trains, evaluates, and promotes role-scoped apprentices; each evaluated generation leaves receipts, evaluation context, score deltas, and a promotion decision, and promoted public generations can be staged as ERC-8004 identities on Base. Today’s honest proof is a public-regression alpha loop, a local private-holdout boundary, a staged ERC-8004/Base issuance path, and one real external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip.

## What to make clear in under 3 minutes

- this is a **system** for role-scoped generation provenance / training / eval / promotion, not a one-off agent demo
- the first concrete role is a **Software Engineer apprentice** improving Role Foundry itself
- four things are real today:
  - an executable **public alpha / public-regression loop**
  - a **local private-holdout** separation boundary
  - a staged **ERC-8004 / Base issuance path**
  - one tracked **external roundtrip proof**
- four things are **not** being claimed:
  - live Base minting
  - partner-track completion
  - native Clawith parity
  - sealed / tamper-proof / third-party-sealed evaluation

## Live route: 5 stops, 2-3 minutes total

### Stop 1 — What the product is (20-30 sec)

Show:
- `README.md`
- `app/vision.html`

Say:

> Role Foundry is the general system. It trains a role-scoped apprentice, evaluates each generation, records the receipts and score deltas, decides what gets promoted publicly, and only then stages portable identity for the promoted public generations. The first concrete role is a Software Engineer apprentice improving Role Foundry itself.

Land:
- this is a **train -> evaluate -> promote -> issue** product loop
- the provenance chain is the point: receipts, evaluation context, deltas, promotion decision
- promotion here means **promoting public curriculum and readiness evidence**
- promotion does **not** mean sealed certification

### Stop 2 — What is executable now: the public alpha loop (30-40 sec)

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

### Stop 3 — The honesty boundary: local private holdouts (25-35 sec)

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

### Stop 4 — The portable identity layer: ERC-8004 / Base (25-35 sec)

Show:
- `docs/erc8004-base-agent0-adapter.md`
- `runner_bridge/product_integrations.py`
- `runner_bridge/erc8004_agent0.py`
- `tests/test_erc8004_base_agent0_adapter.py`

Say:

> After each evaluated generation, the bridge can write a local ERC-8004 registration draft, a completion template, and a canonical Python mint contract tied back to the existing receipts. For promoted/public generations, that becomes the portable identity handoff. No onchain transaction is faked here.

Land:
- the staged issuance path is **real in repo code**
- Base Sepolia is the review/demo default; Base Mainnet is the explicit submission target
- this is a **staged issuance** claim, not a live mint claim
- the Python path makes staged-vs-live explicit: RPC, signer, token URI, live gate, promotion decision

### Stop 5 — One real external roundtrip proof (25-35 sec)

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

> So the honest claim today is narrow: a real public alpha loop, a real local private-holdout boundary, a real staged ERC-8004/Base issuance path, and one real external roundtrip proof. We do not claim live Base minting, partner-track completion, native Clawith parity, or sealed certification.

## 45-second compressed version

> Role Foundry is a role-training, eval, and promotion system for role-scoped apprentices. Each evaluated generation leaves receipts, evaluation context, score deltas, and a promotion decision. Promoted public generations can be staged for ERC-8004 identity issuance on Base. Today we can honestly show four things: an executable public-regression alpha loop with better/equal/worse scoring, a local private-holdout boundary that keeps teacher-only prompts out of tracked and student-visible artifacts, a staged ERC-8004/Base issuance path backed by repo code, and one tracked external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip proof. We do not claim live Base minting, partner-track completion, native Clawith parity, or sealed/tamper-proof evaluation.

## Q&A handling

Keep answers short. Recenter on the narrow claim boundary. If a question starts to widen scope, answer it directly and step back to the four proven things above.

Supporting note for short answers:
- `submission/judge-qa-note.md`

## Hard non-claims

Do not upgrade this branch into claims of:
- live Base minting
- partner-track completion
- native Clawith parity
- native model-pool bring-up completion
- sealed certification
- sealed eval
- tamper-proof evaluation
- third-party-sealed holdouts

## Pre-demo sanity checks

- [ ] Confirm `submission/conversation-log.md`, `submission/evidence-proof-manifest.json`, and `submission/submission-metadata.json` still agree on the final review branch + commit.
- [ ] Confirm the roundtrip manifest, export bundle, and final reply markers still match.
- [ ] If there is still no wallet-approved onchain receipt on this branch, keep every ERC/Base phrase as **staged / not minted**.
- [ ] Keep the non-claims verbatim unless the underlying proof materially changes.
