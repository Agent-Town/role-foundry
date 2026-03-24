# Dataset Episode Registry

`data/episode-registry/public-benchmark-pack-v1.json` is the **companion registry** for the public benchmark pack.

It exists for one reason: the benchmark pack manifest is good at telling the student what to do, but Phase B also needs an audit surface for **how each public episode is judged, where it came from, whether it stayed public-safe, and whether the family is actually ready to promote**.

## What this registry records

For each public episode, the registry records:

- the public benchmark-pack episode id
- the public family id
- the public rubric template id
- provenance back to the public training seed scenario
- the public spec/doc refs that govern the pack contract

It also defines one **public rubric template** per public family.

Each rubric template includes:

- explicit dimension ids and labels
- a normalized weight for each dimension
- a short description of what the dimension is judging
- pass/fail signals that stay public-safe

At the registry level it also records:

- **14 public episodes** mapped into the registry
- **7 benchmark-ready public families**
- **14/14 provenance mappings**
- **100% public provenance coverage**
- **100% family readiness coverage**
- the **integrity audit** outcome for tracked public pack artifacts

## Readiness states

The family registry now exposes an explicit readiness-state layer so Phase B does not have to infer promotion clarity from prose alone.

Allowed readiness states are:

- `draft`
- `benchmark_ready`
- `rewrite_before_holdout_promotion`
- `blocked`

Current state for the public benchmark-pack path:

- `7` families are `benchmark_ready`
- `3` families are `rewrite_before_holdout_promotion`
- `0` committed families use `draft` or `blocked`

The legacy family `status` field still exists for compatibility, but the readiness state is the clearer promotion-planning signal.

## What this registry does **not** contain

It does **not** contain:

- teacher-only prompt text
- teacher-side scoring rubrics
- fresh hidden-holdout prompts
- sealed-certification claims

That material belongs only in the local gitignored private-holdout path.

## Why it matters

This registry makes five Phase B claims explicit instead of implied:

1. **rubric completeness** — every shipped public episode maps to a complete public rubric
2. **weight normalization** — every public rubric sums to `1.0`
3. **provenance coverage** — every shipped public episode traces back to public curriculum
4. **leak-audit clarity** — tracked public pack artifacts record zero teacher-only field/token hits
5. **promotion clarity** — every candidate family has an explicit readiness state

## Audit commands

```bash
python3 -m unittest tests/test_public_benchmark_pack_v1.py -v
python3 -m unittest tests/test_dataset_flywheel_phase_g.py -v
python3 -m unittest tests/test_private_holdout_separation.py -v
```

If those pass, the public pack still has:

- only student-visible included families
- blocked teacher-only families excluded from the public pack
- complete public rubric coverage
- normalized public weights
- full public provenance coverage
- explicit readiness states across all candidate families
- zero teacher-only leakage in tracked public pack artifacts
