# Dataset Flywheel — Phase G Control Surfaces

Phase G on this spine is deliberately narrow.

It does **not** invent new runtime behavior, sealed teacher packs, or a second public benchmark pack.
It does one smaller but real thing: make dataset expansion auditable before the repo grows more families.

## What is now explicit

Two machine-readable surfaces now define the current dataset boundary:

- `data/episode-registry/source-buckets.json`
- `data/episode-registry/promotion-policy.json`

They sit on top of the existing Frontend Apprentice public benchmark pack and answer four questions directly.

## G001 — Registry completeness

Every currently known role-scoped source bucket is registered explicitly instead of being inferred from prose.

Current buckets on this spine:

1. `frontend-apprentice-public-benchmark`
   - `benchmark_pack_committed`
   - backed by `benchmarks/public-pack-v1/`
2. `frontend-apprentice-blocked-teacher-only`
   - `blocked_pending_rewrite`
   - covers repo-visible `h1` / `h2` / `h3`
3. `frontend-apprentice-local-private-holdout`
   - `local_only_uncommitted`
   - placeholder for future fresh teacher-only rewrites outside the public pack
4. `frontend-product-engineer-public-seed-curriculum`
   - `seed_curriculum_only`
   - backed by the committed 20-task seed curriculum under `data/curriculum/`
5. `frontend-product-engineer-local-private-holdout`
   - `local_only_uncommitted`
   - named honestly as uncommitted, not faked as a pack

## G002 — Promotion policy completeness

Every committed Frontend Apprentice candidate family now has explicit promotion criteria in `data/episode-registry/promotion-policy.json`.

Required base criteria are:

- `source_is_public_curriculum`
- `no_teacher_only_inputs`
- `rubric_template_exists`
- `not_repo_visible_holdout`

Current state:

- the 6 public Frontend Apprentice families are `benchmark_ready`
- the 3 repo-visible teacher-only families are `rewrite_before_holdout_promotion`
- the Frontend/Product Engineer lane remains seed-only and therefore has **zero** invented candidate families

## G003 — Holdout promotion safety

The blocked `h1` / `h2` / `h3` families stay blocked.

That means:

- they remain out of `public-benchmark-pack-v1`
- they are marked repo-visible / leaky in promotion policy
- they carry explicit rewrite requirements before any teacher-only promotion can be considered
- no sealed-certification claim is made from current repo-visible holdout framing

## G004 — Role-pack separation

`public-benchmark-pack-v1` is explicitly scoped to `frontend-apprentice`.

The Phase G slice keeps that boundary machine-readable:

- `benchmarks/public-pack-v1/benchmark-pack.json` declares `role_scope`
- the pack now also points to its `source_bucket_id` and shared promotion policy
- the companion episode registry and family registry point back to the same control surfaces
- Frontend/Product Engineer material is recorded only as seed curriculum, not silently mixed into the Frontend Apprentice pack

## What is benchmark-ready now

Benchmark-ready now:

- Frontend Apprentice public pack
- 12 committed public episodes
- 6 committed `benchmark_ready` families

Blocked or not yet promoted:

- 3 Frontend Apprentice repo-visible teacher-only families
- all fresh teacher-only rewrites, because none are committed on this spine
- all Frontend/Product Engineer benchmark-pack work, because only seed curriculum is committed

## What this slice does not claim

It does not claim:

- a sealed teacher-only benchmark pack
- native Clawith parity
- a committed Frontend/Product Engineer benchmark pack
- automatic promotion from seed curriculum into benchmark packs

## Audit commands

```bash
python3 -m unittest tests/test_dataset_flywheel_phase_g.py -v
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
```
