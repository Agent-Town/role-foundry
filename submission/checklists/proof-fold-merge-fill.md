# Proof-fold landing checklist

Use this to record the exact refs pulled from the landed roundtrip-proof lane without widening scope or inventing claims.

## Collected exact refs from the proof-fold lane

- [x] Final proof branch name: `review/submission-readiness-roundtrip-proof-20260323-1005`
- [x] Final proof commit SHA: `c353d88b866419d3da6cbb5ff7470f442310c0cc`
- [x] Exact artifact path(s):
  - tracked manifest: `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
  - local-only receipt roots: `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z` and `artifacts/clawith-gateway/rescue-proof/20260323T025254Z`
- [x] Exact script / entrypoint path:
  - `scripts/clawith_ws_roundtrip.js`
  - `scripts/clawith_vibe_once.py`
  - bootstrap helper used for bring-up / agent key recovery: `scripts/clawith_link_openclaw.py`
- [x] Exact screenshot or log excerpt path:
  - `artifacts/clawith-roundtrip/rescue-proof/20260323T025241Z/final_reply.txt`
  - `artifacts/clawith-gateway/rescue-proof/20260323T025254Z/01_fc7f2137-2d6e-4047-9061-03e7dca481c2/claude.stdout.txt`
- [x] One sentence describing what the proof demonstrates:
  - One honest external gateway-backed `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip where the reply becomes visible again through the Clawith chat/session path.
- [x] One sentence stating what it still does **not** prove:
  - It does not prove native Clawith model-pool parity, stock upstream Role Foundry API parity, or sealed / tamper-proof / third-party-certified evaluation.

## Files updated by this support lane

- [ ] `submission/drafts/judge-demo-script.md`
- [ ] `submission/drafts/pr-or-submission-summary.md`
- [x] `submission/drafts/conversation-log.roundtrip-ready.md`
- [x] `submission/drafts/evidence-proof-manifest.roundtrip-ready.json`
- [x] `submission/drafts/submission-metadata.roundtrip-ready.json`

## Placeholder sweep

Run this before committing the final fold:

```bash
rg -n "FILL_(ROUNDTRIP|FINAL)" submission/drafts submission/checklists
```

Required outcome:
- remaining `FILL_ROUNDTRIP_*` placeholders are intentional and limited to `submission/drafts/judge-demo-script.md` and `submission/drafts/pr-or-submission-summary.md` until those two narrative drafts are updated
- remaining `FILL_FINAL_*` placeholders are limited to final-review / publish-time fields
- no accidental placeholders survive elsewhere under `submission/drafts/` or `submission/checklists/`

## Claim-boundary checks after fill

- [ ] The roundtrip proof is described as **external Clawith -> OpenClaw -> Claude/vibecosystem**.
- [ ] No text was upgraded to claim **native Clawith parity**.
- [ ] No text was upgraded to claim **sealed certification**.
- [ ] If native model-pool smoke is still missing, it remains explicitly blocked.

## Final hygiene

- [ ] Re-validate JSON drafts after any further placeholder replacement.
- [ ] Re-run markdown sanity check.
- [ ] Run `git diff --check`.
- [ ] Commit with a message that clearly says the roundtrip-proof placeholders were filled from the active lane.
