# Dataset Flywheel — Phase G Contract

Phase G encodes four structural invariants about how the episode registry,
promotion policy, holdout safety, and role-pack separation work together.

## G001 — Registry completeness

**Requirement:** All current internal source buckets must be represented in
`data/episode-registry/source-buckets.json`.

**Current state (passing):** Three buckets are registered:

| Bucket | Status | Families |
|--------|--------|----------|
| `public-training` | active | 7 (t1–t7) |
| `blocked-teacher-only` | blocked_pending_rewrite / readiness=`rewrite_before_holdout_promotion` | 3 (h1–h3) |
| `local-private-holdout` | local_only / readiness=`blocked` | 0 committed |

Every scenario in `seed/role-foundry-apprentice.json` maps to exactly one bucket.

## G002 — Promotion policy completeness

**Requirement:** Every candidate family must have explicit `promotion_criteria`.
Families lacking criteria = 0.

**Current state (passing):** All 10 families (7 benchmark-ready + 3 blocked)
now carry `promotion_criteria` in
`benchmarks/public-pack-v1/episode-family-registry.json`.

- Benchmark-ready families: all base criteria satisfied (true)
- Blocked families: at least one criterion is false, making the block machine-readable
- Every family now also carries an explicit `readiness_state`

## G003 — Holdout promotion safety

**Requirement:** Families promoted to teacher-only benchmark status while
marked repo-visible/leaky = 0.

**Current state (passing):** h1, h2, h3 remain legacy-status
`blocked_pending_rewrite` and readiness-state
`rewrite_before_holdout_promotion`.
Their `blocked_reason` documents that the repo already discloses their framing.
None are included in any benchmark pack.

## G004 — Role-pack separation

**Requirement:** Benchmark packs containing mixed-role episodes without
explicit scoping = 0.

**Current state (passing):** The pack declares `role_scope: "frontend-apprentice"`.
Every family declares a matching `role_scope`. All episodes belong to families
with role = "Frontend Apprentice", matching the pack.

## Blockers

None for G001–G004. All four contracts pass honestly.

**Remaining Phase G work not covered here:**
- G005+ contracts (if any) from the full forward spec are not addressed
- No sealed teacher pack is claimed or invented
- Local private holdouts remain gitignored and local-only
- h1/h2/h3 remain blocked pending genuine rewrite

## Audit commands

```bash
python3 -m unittest tests/test_dataset_flywheel_phase_g.py -v
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
```
