# Morning Merge Hygiene — 2026-03-28

## Stack lineage (merge order, oldest → newest)

| # | Branch | Commit | Status |
|---|--------|--------|--------|
| 1 | review/clean-spine-alpha-reconcile-20260327-0938 | 6171881 | present on stack |
| 2 | review/public-benchmark-pack-clean-spine-20260327-2328 | 54d3f79 | present on stack |
| 3 | review/receipt-provenance-clean-benchmark-20260328-0934 | 1e6cc97 | present on stack |
| 4 | review/autoresearch-alpha-exec-clean-20260328-1102 | 799686e | present on stack |
| 5 | review/live-ui-readmodel-alpha-hookup-20260328-1118 | b4700eb | present on stack |
| 6 | review/clawith-phase-f-readiness-20260328-1201 | 26edd3e | present on stack |
| 7 | review/phase-g-dataset-slice-20260328-1216 | 864606a | present on stack |

All seven slices are present on the stacked review branch lineage (tip: 864606a). They have **not** been merged to `main`.

## What is real / present on stack

- **Public benchmark pack v1** — seed-only, 20 tasks, no partner data.
- **Receipt provenance** — additive audit bundle on runner-bridge outputs.
- **Autoresearch alpha loop** — three-stage public-regression, LocalReplayRunner only.
- **Live UI read-model** — thin receipt adapter; read-only, payload-faithful.
- **Phase F readiness** — integration_state classifier + bearer-token probe (F001-F004).
- **Phase G dataset** — control surfaces for seed episode registry; blocked on live ingest.

## What is still blocked / not yet real

| Item | Blocker |
|------|---------|
| Native/live runner | No live Clawith connection; alpha uses LocalReplayRunner only |
| Sealed holdout execution | Requires live runner bridge, not replay |
| Clawith adapter round-trip | Adapter-needed; read-only probe only today |
| Dataset beyond seed | Live ingest pipeline not wired; seed-only episodes |
| Partner integrations | None present; not started |
| Browser live shell writes | UI is read-only; no mutation path |

## Targeted validation packet

```bash
python3 -m pytest -q \
  tests/test_public_benchmark_pack_v1.py \
  tests/test_receipt_provenance_hardening.py \
  tests/test_autoresearch_alpha_loop.py \
  tests/test_live_ui_alpha_receipt.py \
  tests/test_phase_f.py \
  tests/test_clawith_probe.py \
  tests/test_dataset_flywheel_phase_g.py
```

Expected: **102 passed** (observed 2026-03-28 12:53 UTC).

## Honesty constraints in force

- No fake native/live/sealed claims.
- Alpha loop is LocalReplayRunner-only — stated explicitly.
- UI receipts are thin read-only adapters — stated explicitly.
- Clawith integration is adapter-needed / probe-only — stated explicitly.
- Dataset is seed-only with blocked live ingest — stated explicitly.
- No partner integrations are present or claimed.
