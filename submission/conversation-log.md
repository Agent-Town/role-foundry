# conversationLog

Status: final-review-ready
Canonical final packet artifact for review branch `review/submission-erc-provenance-20260323-1240`.

## 1. Submission framing

- Project: Role Foundry
- Final review branch: `review/submission-erc-provenance-20260323-1240`
- Final review commit: `324f29f81f3a9e81b52b6b89f5daa6fc29a6ac12`
- One-sentence claim:
  - Role Foundry is a role-training, evaluation, and promotion system for AI apprentices; this branch makes the generation provenance chain explicit by showing that each evaluated generation carries receipts, evaluation context, score deltas, and a promotion/public-issuance decision, while the current evidence proves a Software Engineer apprentice public alpha loop, a local private-holdout honesty boundary, a staged ERC-8004/Base issuance path, and an external Clawith -> OpenClaw -> Claude/vibecosystem roundtrip path without claiming live minting, native parity, or sealed certification.

## 2. Repo-visible proof already present

- The repo frames Role Foundry as a general training/eval/promotion system rather than a one-off app.
- The first concrete role is the **Software Engineer apprentice** improving Role Foundry itself.
- The repo contains an executable **public alpha loop** (`specs/010-autoresearch-alpha-public-loop.md`, `runner_bridge/examples/autoresearch-alpha-public-loop.json`, `tests/test_autoresearch_alpha_loop.py`).
- The repo contains a **local private-holdout** contract and leak-separation path (`docs/private-holdout-authoring.md`, `specs/012-private-holdout-pack.md`, `tests/test_private_holdout_separation.py`).
- The repo now contains a staged **ERC-8004 / Base** issuance path (`docs/erc8004-base-agent0-adapter.md`, `runner_bridge/product_integrations.py`, `app/agent0_base_adapter.mjs`, `tests/test_erc8004_base_agent0_adapter.py`).
- The submission packet is canonicalized under `submission/` and accompanied by a tracked portable roundtrip-proof bundle under `submission/roundtrip-proof/`.

## 3. ERC / Base adapter entry

- Spec: `specs/013-erc8004-base-agent0-adapter.md`
- Usage doc: `docs/erc8004-base-agent0-adapter.md`
- Bridge integration: `runner_bridge/product_integrations.py`
- Browser adapter: `app/agent0_base_adapter.mjs`
- Test coverage: `tests/test_erc8004_base_agent0_adapter.py`
- Adapter note:
  - The repo can draft ERC-8004 registration payloads targeting Base and can stage the agent0 mint flow through a thin Role Foundry-owned adapter.
  - The staged story is for **promoted/public generations**; draft generation does not itself mean a public issuance happened.
  - No wallet transaction, no onchain receipt, and no live mint has been claimed on this branch.

## 4. Roundtrip proof entry

- Proof branch: `origin/review/clawith-vibe-roundtrip-demo-20260323-1000`
- Proof commit: `4dab2a9866b86df4525d9698a7c844ab538ac61c`
- Tracked proof index: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- Portable proof bundle: `submission/roundtrip-proof/roundtrip-proof.export.json`
- Portable final reply excerpt: `submission/roundtrip-proof/final-reply.txt`
- Audit note: `submission/checklists/roundtrip-receipt-audit-2026-03-23.md`
- Proof entrypoints: `scripts/clawith_ws_roundtrip.js` and `scripts/clawith_vibe_once.py`
- Proof note:
  - The tracked manifest and portable bundle let reviewers inspect the proof without needing raw receipt directories committed into git.
  - Maintainer-local receipt roots remain indexed in the manifest only for deep revalidation.
  - This proof shows one external **Clawith -> OpenClaw -> Claude/vibecosystem** roundtrip path.
  - It does **not** upgrade the claim to native Clawith parity.

## 5. Explicit non-claims

- No claim of live Base minting on Sepolia or mainnet.
- No claim of partner-track completion.
- No claim of native Clawith parity.
- No claim of native model-pool bring-up completion unless separately evidenced.
- No claim of sealed certification.
- No claim of tamper-proof or third-party-sealed evaluation.

## 6. Checks to cite in the final packet

- `/opt/homebrew/bin/pytest -q tests/test_vision_and_swe_bench_separation.py tests/test_teacher_source_curriculum.py tests/test_public_benchmark_pack_v1.py tests/test_autoresearch_alpha_loop.py tests/test_private_holdout_separation.py tests/test_demo_contract.py tests/test_milestone3_contract.py tests/test_erc8004_base_agent0_adapter.py`
- `python3 -m py_compile runner_bridge/bridge.py runner_bridge/product_integrations.py scripts/clawith_link_openclaw.py scripts/clawith_vibe_once.py`
- `/Users/robin/.nvm/versions/node/v24.14.0/bin/node --check scripts/clawith_ws_roundtrip.js`
- `/Users/robin/.nvm/versions/node/v24.14.0/bin/node --check app/agent0_base_adapter.mjs`
- `git diff --check`

## 7. Reviewer note

This branch is the cleaner reviewer-facing packet because it no longer leaves ERC-8004/Base in the "optional later" bucket while the adapter code already exists. It keeps the claim boundary narrow: staged issuance is in, live minting is still out.
