# Overnight handoff — 2026-03-23 Phase G

This note is a morning-review status snapshot for the clean handoff branch that layers Phase G dataset-registry work onto the public-alpha morning spine.

## What landed cleanly

- Fast-forwarded the clean public-alpha morning spine into the newest safe Phase G dataset-registry commit with no conflict resolution.
- Added a machine-readable promotion-policy surface at `data/episode-registry/promotion-policy.json`.
- Tightened both public pack registries/manifests so family status, promotion criteria, role scope, and source-intake coverage are explicit instead of prose-only.
- Expanded Phase G regression coverage in `tests/test_dataset_flywheel_phase_g.py` and kept the public-alpha receipt/UI spine intact.

## What this branch now includes

- Everything already in `review/public-alpha-morning-spine-20260323-2129`, including the live UI hookup to the real alpha receipt shape.
- The Phase G dataset/promotion-policy surface across:
  - `data/episode-registry/promotion-policy.json`
  - `data/episode-registry/source-buckets.json`
  - both public pack manifests + family registries
  - `docs/dataset-episode-registry.md`
  - `docs/dataset-flywheel.md`
- Cross-pack checks that keep Frontend Apprentice and Frontend/Product Engineer registry surfaces role-scoped and non-overlapping.

## What remains blocked / not claimable

- This branch does **not** make sealed-eval, sealed-certification, tamper-proof, or independently sealed claims.
- The repo-visible holdout families (`h1` / `h2` / `h3`) remain `blocked_pending_rewrite` and are still not promotable.
- Curated, manual-curation-only, and teacher-only intake seams are still not public benchmark families until real RF-authored episode work exists.
- Local private holdouts remain gitignored and local-only; there are still zero committed private-holdout families.
- No partner-integration, wallet/chain-runtime, or broad runner-bridge readiness claims were added here.

## Next single most important move

Author and promote one genuinely new RF-owned family from an already-curated public source seam, then run it through the same registry/promotion-policy path. That is the shortest honest path to proving this Phase G surface is operational rather than just documented.
