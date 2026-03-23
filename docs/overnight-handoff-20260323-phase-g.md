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

## What remains blocked / not claimable

- This branch still does **not** justify sealed-eval, sealed-certification, tamper-proof, or independently sealed claims.
- The repo-visible holdout families (`h1` / `h2` / `h3`) remain `blocked_pending_rewrite` and are still not promotable.
- Local private holdouts remain gitignored and local-only; there are still zero committed teacher-only families.
- Manual-curation-only seams (for example Alpine.js) are still not public benchmark families.
- No new native-live, partner-integration, wallet/chain-runtime, or broad runner-bridge readiness claims were added here.

## Next single most important move

Author the first fresh teacher-only holdout rewrite in the local gitignored private path and score it honestly. The public source-backed promotion path is now proven; the remaining honest blocker is turning the private holdout seam into a real teacher-only workflow without leaking it into the tracked repo.
