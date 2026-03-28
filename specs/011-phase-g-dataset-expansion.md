# Spec 011 — Phase G Dataset Expansion (Controlled)

## Intent

Land the smallest honest Phase G slice on top of the Phase F spine.

This slice does **not** broaden runtime semantics.
It adds explicit dataset-control surfaces so future benchmark growth has to pass through named buckets, named promotion rules, and named role boundaries.

## Scope

This spec covers only:

- `G001` registry completeness
- `G002` promotion policy completeness
- `G003` holdout promotion safety
- `G004` role-pack separation

It does **not** cover:

- new execution/runtime behavior
- partner integrations
- holdout authoring
- UI redesign
- native Clawith parity claims
- a second benchmark pack for Frontend/Product Engineer

## Data surfaces

- `data/episode-registry/source-buckets.json`
- `data/episode-registry/promotion-policy.json`
- additive metadata refs from the existing Frontend Apprentice public pack + companion registries

## Acceptance checks

### G001 — Registry completeness

- **Metric:** source buckets represented in the registry scaffold
- **Pass threshold:** all current role-scoped buckets on this spine are registered explicitly
- **Evidence:** `data/episode-registry/source-buckets.json` + `tests/test_dataset_flywheel_phase_g.py`
- **Failure interpretation:** dataset intake is implicit, so future expansion will drift or silently mix states

Current required buckets on this spine:

- Frontend Apprentice public benchmark bucket
- Frontend Apprentice blocked repo-visible teacher-only bucket
- Frontend Apprentice local/private holdout placeholder bucket
- Frontend/Product Engineer public seed-curriculum bucket
- Frontend/Product Engineer local/private holdout placeholder bucket

### G002 — Promotion policy completeness

- **Metric:** committed candidate families lacking explicit promotion criteria
- **Pass threshold:** `0`
- **Evidence:** `data/episode-registry/promotion-policy.json` + `tests/test_dataset_flywheel_phase_g.py`
- **Failure interpretation:** dataset growth becomes ad hoc and promotion decisions stop being auditable

Required base criteria for every committed candidate family:

- `source_is_public_curriculum`
- `no_teacher_only_inputs`
- `rubric_template_exists`
- `not_repo_visible_holdout`

### G003 — Holdout promotion safety

- **Metric:** repo-visible or leaky families promoted while still marked rewrite-needed
- **Pass threshold:** `0`
- **Evidence:** promotion-policy validation + public-pack exclusion checks
- **Failure interpretation:** teacher benchmark integrity is compromised

Current honesty rule:

- `h1` / `h2` / `h3` remain `rewrite_before_holdout_promotion`
- they stay outside the public pack
- future teacher-only rewrites may exist only as local/private material until a fresh non-disclosed version exists

### G004 — Role-pack separation

- **Metric:** committed benchmark packs containing mixed-role material without explicit scoping
- **Pass threshold:** `0`
- **Evidence:** pack metadata + family-registry scope validation
- **Failure interpretation:** evaluation signal is muddled across roles and packs stop being comparable

Current honesty rule:

- `public-benchmark-pack-v1` is scoped only to `frontend-apprentice`
- Frontend/Product Engineer remains seed-curriculum-only on this spine
- no FPE benchmark pack is claimed or implied

## Done when

Role Foundry can honestly say:

- dataset intake is no longer implicit
- candidate-family promotion rules are machine-readable
- repo-visible holdout families cannot be silently promoted
- role-scoped benchmark packs are explicit
- Frontend/Product Engineer seed data is visible without being misrepresented as a committed benchmark pack

## Verification

```bash
python3 -m unittest tests/test_dataset_flywheel_phase_g.py -v
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
```
