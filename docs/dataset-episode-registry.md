# Dataset Episode Registry

The episode registry layer provides audit surfaces for **how each public episode is judged, where it came from, and what promotion policy governs it**.

## Registry surfaces

| Surface | Path | Purpose |
|---------|------|---------|
| Apprentice episode registry | `data/episode-registry/public-benchmark-pack-v1.json` | Rubrics + provenance for the 16-episode Frontend Apprentice pack |
| FPE episode registry | `data/episode-registry/fpe-public-benchmark-pack-v1.json` | Rubrics + provenance for the 20-episode FPE pack |
| Source buckets | `data/episode-registry/source-buckets.json` | Every internal source bucket across both roles |
| Promotion policy | `data/episode-registry/promotion-policy.json` | Machine-readable status vocabulary, criteria, and invariants |

## What each episode registry records

For each public episode, the registry records:

- the public benchmark-pack episode id
- the public family id
- the public rubric template id
- provenance back to the public training seed scenario or acceptance test
- the public spec/doc refs that govern the pack contract

It also defines one **public rubric template** per public family.

Each rubric template includes:

- explicit dimension ids and labels
- a normalized weight for each dimension
- a short description of what the dimension is judging
- pass/fail signals that stay public-safe

## What these registries do **not** contain

They do **not** contain:

- teacher-only prompt text
- teacher-side scoring rubrics
- fresh hidden-holdout prompts
- sealed-certification claims

That material belongs only in the local gitignored private-holdout path.

## Promotion policy

`data/episode-registry/promotion-policy.json` defines:

- **family-status vocabulary** — `benchmark_ready`, `blocked_pending_rewrite`, `local_only`
- **source-intake status vocabulary** — `promoted`, `curated`, `discovered`, `blocked_teacher_only_holdout`
- **promotion modes** — `public_benchmark_family`, `public_candidate`, `manual_curation_only`, `teacher_only_manual_curation`
- **base promotion criteria** — the four boolean fields every family must carry
- **invariants** — machine-readable rules with test references (G001-G004)
- **pack refs** — which packs exist and their role scopes

Every family in every family registry must have explicit `promotion_criteria`. Blocked families must have at least one false criterion and document `rewrite_requirements`. Every tracked source-intake seam must also land in an explicit intake bucket with a documented status and promotion mode.

## Source buckets

`data/episode-registry/source-buckets.json` now exposes two layers:

- **family buckets**
  - **Frontend Apprentice**: `public-training` (8 families), `blocked-teacher-only` (3 families), `local-private-holdout` (0 committed)
  - **Frontend/Product Engineer**: `fpe-public-training` (5 families), `fpe-local-private-holdout` (0 committed)
- **source-intake buckets**
  - `frontend-apprentice-source-intake-promoted` — already promoted into a public family (`rf.frontend-apprentice.public.playwright-regression`)
  - `frontend-apprentice-source-intake-curated` — curated public candidate bucket (currently empty; Google Eng Practices promoted out)
  - `frontend-apprentice-source-intake-manual-curation-only` — discovered source that requires teacher rewrite before any RF family exists
  - `frontend-apprentice-source-intake-blocked-teacher-only` — explicit teacher-only holdout direction, blocked from all public packs

Each bucket carries a `role_id`, ensuring no bucket serves multiple roles or silently mixes roles.

## Why it matters

These registries make previously implicit claims explicit:

1. **rubric completeness** — every shipped public episode maps to a complete public rubric
2. **weight normalization** — every public rubric sums to `1.0`
3. **provenance coverage** — every shipped public episode traces back to public curriculum
4. **promotion clarity** — the public packs are ready for public regression/training use, not for sealed certification
5. **role isolation** — each pack targets exactly one role; no mixed-role packs exist
6. **intake completeness** — every seed scenario/task and every tracked source-intake seam maps to exactly one bucket

## Audit commands

```bash
# G001-G004 dataset-flywheel tests (both packs)
python3 -m unittest tests/test_dataset_flywheel_phase_g.py

# Pack-specific tests
python3 -m unittest tests/test_public_benchmark_pack_v1.py
python3 -m unittest tests/test_fpe_public_benchmark_pack_v1.py

# Teacher-source intake seams
python3 -m unittest tests/test_teacher_source_curriculum.py

# Private holdout separation
python3 -m unittest tests/test_private_holdout_separation.py
```

If those pass, both public packs have:

- only student-visible included families
- blocked teacher-only families excluded from public packs
- complete public rubric coverage
- normalized public weights
- full public provenance coverage
- explicit promotion criteria on every family
- explicit status + promotion mode on every tracked intake seam
- role-scoped packs with no cross-role leakage
