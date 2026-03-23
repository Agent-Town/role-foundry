# Dataset Flywheel — Phase G Contract

Phase G encodes four structural invariants about how the episode registry,
promotion policy, holdout safety, and role-pack separation work together.

## G001 — Registry completeness

**Requirement:** All current internal source buckets must be represented in
`data/episode-registry/source-buckets.json`.

**Current state (passing):** The registry now tracks both family buckets and
source-intake buckets.

### Family buckets

| Role | Bucket | Status | Families |
|------|--------|--------|----------|
| Frontend Apprentice | `public-training` | active | 9 |
| Frontend Apprentice | `blocked-teacher-only` | blocked_pending_rewrite | 3 |
| Frontend Apprentice | `local-private-holdout` | local_only | 0 committed |
| Frontend/Product Engineer | `fpe-public-training` | active | 5 |
| Frontend/Product Engineer | `fpe-local-private-holdout` | local_only | 0 committed |

### Source-intake buckets

| Bucket | Status | Promotion mode | Notes |
|--------|--------|----------------|-------|
| `frontend-apprentice-source-intake-promoted` | promoted | `public_benchmark_family` | Playwright-backed, Google Eng Practices-backed, and Alpine docs/examples-backed families are promoted |
| `frontend-apprentice-source-intake-curated` | curated | `public_candidate` | Currently empty; no curated-but-unpromoted public intake seams remain |
| `frontend-apprentice-source-intake-manual-curation-only` | discovered | `manual_curation_only` | Currently empty; Alpine docs/examples were manually rewritten and promoted, while raw GitHub threads remain excluded |
| `frontend-apprentice-source-intake-blocked-teacher-only` | blocked_teacher_only_holdout | `teacher_only_manual_curation` | SWE-bench remains a teacher-only holdout direction |

Every Frontend Apprentice seed scenario maps to exactly one family bucket.
Every FPE acceptance test maps to exactly one family bucket. Every tracked
source-intake record maps to exactly one intake bucket.

## G002 — Promotion policy completeness

**Requirement:** Every candidate family must have explicit `promotion_criteria`.
Candidate intake seams must also have explicit status + promotion mode.

**Current state (passing):**

- Every family in both family registries carries explicit `promotion_criteria`
- `data/episode-registry/promotion-policy.json` defines:
  - family-status vocabulary
  - source-intake status vocabulary
  - promotion modes
  - base criteria
  - invariants with test refs
- Both family registries point back to the shared promotion policy surface

Benchmark-ready families satisfy all base criteria. Blocked families have at
least one false criterion and explicit rewrite requirements. Manual-curation
and teacher-only source-intake seams are explicit instead of prose-only, and
there is no longer a curated-but-unpromoted public intake seam.

## G003 — Holdout promotion safety

**Requirement:** Repo-visible or leaky families must not be promoted into
benchmark-ready teacher-only status without explicit blocking.

**Current state (passing):**

- h1 / h2 / h3 remain `blocked_pending_rewrite`
- Their `blocked_reason` explains that the repo already discloses their framing
- They do not appear in any public benchmark pack
- SWE-bench remains an explicit `blocked_teacher_only_holdout` intake seam
- Unpromoted manual-curation-only and teacher-only intake buckets carry no promoted public
  families, no promoted public episodes, and no public-pack refs

No sealed teacher pack is claimed. No private holdout content is tracked.

## G004 — Role-pack separation

**Requirement:** Benchmark packs containing mixed-role episodes without
explicit scoping = 0.

**Current state (passing):**

- `public-benchmark-pack-v1` declares `role_scope: frontend-apprentice`
- `fpe-public-benchmark-pack-v1` declares `role_scope: frontend-product-engineer`
- Families in each pack match the pack role + role_scope
- Episode ids and family ids are disjoint across the two packs
- Both pack manifests and both episode registries point back to the shared
  source-bucket and promotion-policy surfaces

## Blockers

None for G001–G004. The current contract passes honestly.

**Remaining Phase G work not covered here:**
- G005+ contracts (if any) from the full forward spec are not addressed
- No sealed teacher pack is claimed or invented
- Local private holdouts remain gitignored and local-only
- h1/h2/h3 remain blocked pending genuine rewrite
- No unpromoted manual-curation-only public-source seams remain after the Alpine docs/examples promotion; raw GitHub discussion text is still excluded from direct public-pack promotion
- Teacher-only holdout seams remain blocked from any public promotion path

## Audit commands

```bash
python3 -m unittest tests/test_dataset_flywheel_phase_g.py -v
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
python3 -m unittest tests/test_fpe_public_benchmark_pack_v1.py -v
python3 -m unittest tests/test_teacher_source_curriculum.py -v
python3 -m unittest tests/test_private_holdout_separation.py -v
```
