# Overnight handoff — 2026-03-23 late refresh

This note supersedes the earlier Phase G snapshot on the pre-promotion head. It reflects the repo state after the Google Eng Practices promotion plus a small docs-only reconcile pass.

## What landed cleanly tonight

- Kept the clean public-alpha + Phase G dataset-registry spine intact, then carried a real source-backed family promotion on top without widening scope into new runtime/UI/integration work.
- Promoted `intake-google-eng-practices` from curated intake to shipped public family `rf.frontend-apprentice.public.code-review-discipline`.
- Added 2 RF-authored public episodes (`pbpv1-e15`, `pbpv1-e16`) plus a fresh 4-dimension rubric for diff critique, test/doc expectations, and scope control.
- Grew the Frontend Apprentice public benchmark pack from 14 to 16 episodes and from 7 to 8 public families.
- Kept the shared Phase G registry surfaces coherent: source intake, source buckets, family registry, benchmark pack, episode registry, and teacher-source tests all agree on the promoted family.

## Why Phase G is now operational, not just documented

A tracked public source seam completed the full repo-visible path tonight:

- `discover` → `curate` → `promote` on `intake-google-eng-practices`
- promoted source bucket linkage in `data/episode-registry/source-buckets.json`
- promoted family entry in `benchmarks/public-pack-v1/episode-family-registry.json`
- shipped episodes + rubric in `benchmarks/public-pack-v1/benchmark-pack.json` and `data/episode-registry/public-benchmark-pack-v1.json`
- regression coverage in `tests/test_teacher_source_curriculum.py` and the existing Phase G dataset-flywheel suite

That is the first clean proof that the Phase G promotion surface can move a real tracked source into RF-authored public curriculum, not just describe the policy in prose.

## Local private-holdout status now

- The gitignored private lane is no longer just a first-rewrite scaffold: fresh local-only replacement coverage now exists for all three previously blocked teacher-only families (`h1` / `h2` / `h3`).
- The latest local private-holdout alpha rerun loaded **6/6** holdouts from the manifest and recorded a `better` comparison verdict.
- None of that teacher-only material is committed here. The tracked repo still contains zero teacher-only prompts, rubrics, or episode bodies.

## Sealing receipt boundary + pre-run commitment now landed

- `specs/015-sealed-receipt-surface.md` and the alpha-loop receipt now add a top-level `sealing_receipt` block as a **public-safe honesty boundary, not a seal**.
- That block records the current claim ceiling (`local private-holdout alpha execution with public-safe receipts` when the local manifest lane is used), the current status tier, blocked stronger claims, and the unmet prerequisites for any stronger sealing / tamper-evidence language.
- When a local private-holdout manifest is actually loaded, the run now writes a local-only `pre-run-manifest-commitment.json` artifact **before** any stage execution begins, and the receipt surfaces it as `pre_run_manifest_commitment` with the manifest hash, timestamp, sequence linkage, and honesty note.
- The same boundary can still include a SHA-256 fingerprint labeled **local operator correlation only**; together these surfaces improve local auditability and operator correlation only, not publication, third-party witnessing, signing, tamper-proofing, certification, or independent audit.
- The read-only live UI/read-model shell now renders the same boundary when a `sealing_receipt` is exported. The committed browser sample stays at **public-regression alpha**, so it still blocks stronger sealed/certified/tamper-proof claims instead of inventing them.

## `claude_vibecosystem` external-executor beta seam now landed

- `specs/016-claude-vibecosystem-backend.md` formalizes a named `claude_vibecosystem` runner backend as a narrow **external-executor beta seam**.
- `python3 -m runner_bridge.cli --packet A001 --runner-backend claude_vibecosystem` now stamps `execution_backend: "claude_vibecosystem"` into `run-object.json` and can carry a machine-readable `execution_backend_contract` block through the packet/runtime surface.
- The tiny backend stub writes `execution_honesty` plus provenance/inspectability surfaces so reviewers can see the backend id, intended executor path, and current claim boundary in machine-readable form.
- This is the honest extension of the existing `docs/clawith-vibecosystem-real-path.md` proof lane: the contract/provenance seam is now explicit in the public runner surfaces, without pretending the stub is live execution.

**Important honesty line:** this is a contract/provenance-real external-executor beta seam only. It remains a non-destructive stub. It does **not** create live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, or native Clawith parity.

## What remains blocked / not claimable

- This branch still does **not** justify sealed-eval, sealed-certification, tamper-proof, or independently sealed claims.
- The repo-visible holdout family entries (`h1` / `h2` / `h3`) remain `blocked_pending_rewrite` in the tracked public registry and are still not promotable as public or sealed families.
- Local private holdouts remain gitignored and local-only; the new pre-run commitment improves local operator auditability/correlation before stage execution, but the honest claim ceiling is still **local private-holdout alpha execution with public-safe receipts**, not sealed certification.
- Manual-curation-only seams (for example Alpine.js) are still not public benchmark families.
- No new native-live, partner-integration, wallet/chain-runtime, or broad runner-bridge readiness claims were added here beyond the narrow `claude_vibecosystem` contract/provenance seam described above.

## Next single most important move

Treat `sealing_receipt` plus the local-only `pre_run_manifest_commitment` as the hard claim boundary and only raise the language above local private-holdout alpha execution when real controls land behind it — independent executor isolation, third-party manifest signing/audit, and stronger tamper-evidence than local operator correlation.
