# Overnight handoff — 2026-03-23 late refresh

This note supersedes the earlier Phase G snapshot on the pre-promotion head. It reflects the repo state after the Google Eng Practices promotion, the Alpine docs/examples promotion, and a small backend-provenance docs/status reconcile pass.

## What landed cleanly tonight

- Kept the clean public-alpha + Phase G dataset-registry spine intact, then carried real source-backed family promotions on top without widening scope into new runtime/UI/integration work.
- Promoted `intake-google-eng-practices` from curated intake to shipped public family `rf.frontend-apprentice.public.code-review-discipline`.
- Promoted `intake-alpinejs-curation` from a manual-curation-only docs/examples seam to shipped public family `rf.frontend-apprentice.public.alpine-state-patterns`.
- Added 4 RF-authored public episodes across those two promotions (`pbpv1-e15`–`pbpv1-e18`) plus fresh public rubrics for review-discipline and Alpine state-pattern work.
- Grew the Frontend Apprentice public benchmark pack from 14 to 18 episodes and from 7 to 9 public families.
- Kept the shared Phase G registry surfaces coherent: source intake, source buckets, family registry, benchmark pack, episode registry, and teacher-source tests all agree on the promoted families.

## Why Phase G is now operational, not just documented

Tracked public source seams have now completed the full repo-visible path:

- `discover` → `curate` → `promote` on `intake-google-eng-practices`
- `discover` → `manual rewrite from docs/examples only` → `promote` on `intake-alpinejs-curation`
- promoted source bucket linkage in `data/episode-registry/source-buckets.json`
- promoted family entries in `benchmarks/public-pack-v1/episode-family-registry.json`
- shipped episodes + rubrics in `benchmarks/public-pack-v1/benchmark-pack.json` and `data/episode-registry/public-benchmark-pack-v1.json`
- regression coverage in `tests/test_teacher_source_curriculum.py` and the existing Phase G dataset-flywheel suite

That is now repeated proof that the Phase G promotion surface can move real tracked sources into RF-authored public curriculum, including a docs/examples-only manual-curation seam, not just describe the policy in prose.

## Alpine promotion boundary now

- `rf.frontend-apprentice.public.alpine-state-patterns` is public-safe only because it was authored as original RF work grounded in Alpine public docs/examples.
- The family ships 2 RF-authored episodes (`pbpv1-e17`, `pbpv1-e18`), bringing the Frontend Apprentice pack to **9 families / 18 episodes**.
- Raw Alpine GitHub issue / PR / review text remains excluded from the public pack and is **not** part of the promotion claim here.

## Local private-holdout status now

- The gitignored private lane is no longer just a first-rewrite scaffold: fresh local-only replacement coverage now exists for all three previously blocked teacher-only families (`h1` / `h2` / `h3`).
- The latest local private-holdout alpha rerun loaded **6/6** holdouts from the manifest and recorded a `better` comparison verdict.
- None of that teacher-only material is committed here. The tracked repo still contains zero teacher-only prompts, rubrics, or episode bodies.

## Sealing receipt boundary + pre-run commitment now landed

- `specs/015-sealed-receipt-surface.md` and the alpha-loop receipt now add a top-level `sealing_receipt` block as a **public-safe honesty boundary, not a seal**.
- That block records the current claim ceiling (`local private-holdout alpha execution with public-safe receipts` when the local manifest lane is used), the current status tier, blocked stronger claims, and the unmet prerequisites for any stronger sealing / tamper-evidence language.
- Backend provenance now threads through the public-safe audit surfaces too: `artifact-bundle.json` carries `execution_backend`, `execution_backend_contract`, and `execution_honesty`; receipt-level `execution_backend` blocks now show up in candidate/evaluation receipts; each alpha stage export now carries its own `execution_backend`; and the top-level `sealing_receipt.execution_backend` summarizes backend provenance across the full alpha sequence.
- When a local private-holdout manifest is actually loaded, the run now writes a local-only `pre-run-manifest-commitment.json` artifact **before** any stage execution begins, and the receipt surfaces it as `pre_run_manifest_commitment` with the manifest hash, timestamp, sequence linkage, and honesty note.
- The same boundary can still include a SHA-256 fingerprint labeled **local operator correlation only**; together these surfaces improve local auditability, operator correlation, and backend claim-boundary evidence only — not publication, third-party witnessing, signing, tamper-proofing, certification, or independent audit.
- The read-only live UI/read-model shell now renders the same boundary when a `sealing_receipt` is exported. The committed browser sample stays at **public-regression alpha**, so it still blocks stronger sealed/certified/tamper-proof claims instead of inventing them.

## `claude_vibecosystem` external-executor beta seam now landed

- `specs/016-claude-vibecosystem-backend.md` formalizes a named `claude_vibecosystem` runner backend as a narrow **external-executor beta seam**.
- `python3 -m runner_bridge.cli --packet A001 --runner-backend claude_vibecosystem` now stamps `execution_backend: "claude_vibecosystem"` into `run-object.json` and can carry a machine-readable `execution_backend_contract` block through the packet/runtime surface.
- The tiny backend stub writes `execution_honesty` plus provenance/inspectability surfaces so reviewers can see the backend id, intended executor path, and current claim boundary in machine-readable form.
- That backend provenance now survives past packet/runtime setup into `artifact-bundle.json`, receipt-level `execution_backend` blocks (including candidate/evaluation receipts when present), per-stage alpha receipts, and `sealing_receipt.execution_backend`.
- This is the honest extension of the existing `docs/clawith-vibecosystem-real-path.md` proof lane: the contract/provenance seam is now explicit in the public runner surfaces, without pretending the stub is live execution.

**Important honesty line:** this is backend provenance / claim-boundary evidence only on top of a contract/provenance-real external-executor beta seam. It remains a non-destructive stub. It does **not** create live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, audit, or native Clawith parity.

## What remains blocked / not claimable

- This branch still does **not** justify sealed-eval, sealed-certification, tamper-proof, or independently sealed claims.
- The repo-visible holdout family entries (`h1` / `h2` / `h3`) remain `blocked_pending_rewrite` in the tracked public registry and are still not promotable as public or sealed families.
- Local private holdouts remain gitignored and local-only; the new pre-run commitment improves local operator auditability/correlation before stage execution, but the honest claim ceiling is still **local private-holdout alpha execution with public-safe receipts**, not sealed certification.
- The unpromoted manual-curation-only bucket is currently empty. Alpine.js moved out only after a docs/examples-only manual rewrite into `rf.frontend-apprentice.public.alpine-state-patterns`; raw Alpine GitHub issue/PR/review text remains excluded from the public pack and would still have to re-enter through manual teacher curation, not direct promotion.
- No new native-live, partner-integration, wallet/chain-runtime, or broad runner-bridge readiness claims were added here beyond the narrow `claude_vibecosystem` contract/provenance seam described above.

## Next single most important move

Treat `sealing_receipt` plus the local-only `pre_run_manifest_commitment` as the hard claim boundary and only raise the language above local private-holdout alpha execution when real controls land behind it — independent executor isolation, third-party manifest signing/audit, and stronger tamper-evidence than local operator correlation.
