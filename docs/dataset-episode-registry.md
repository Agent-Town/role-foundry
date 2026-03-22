# Dataset Episode Registry

`data/episode-registry/public-benchmark-pack-v1.json` is the **companion registry** for the public benchmark pack.

It exists for one reason: the benchmark pack manifest is good at telling the student what to do, but Phase B also needs an audit surface for **how each public episode is judged and where it came from**.

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

## What this registry does **not** contain

It does **not** contain:

- teacher-only prompt text
- teacher-side scoring rubrics
- fresh hidden-holdout prompts
- sealed-certification claims

That material belongs only in the local gitignored private-holdout path.

## Why it matters

This registry makes four previously implicit claims explicit:

1. **rubric completeness** — every shipped public episode maps to a complete public rubric
2. **weight normalization** — every public rubric sums to `1.0`
3. **provenance coverage** — every shipped public episode traces back to public curriculum
4. **promotion clarity** — the public pack is ready to promote for public regression/training use, not for sealed certification

## Audit commands

```bash
python3 -m unittest tests/test_public_benchmark_pack_v1.py
python3 -m unittest tests/test_private_holdout_separation.py
```

If those pass, the public pack still has:

- only student-visible included families
- blocked teacher-only families excluded from the public pack
- complete public rubric coverage
- normalized public weights
- full public provenance coverage
