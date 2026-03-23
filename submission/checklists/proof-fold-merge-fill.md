# Proof-fold landing checklist

Use this the moment the active roundtrip-proof lane lands.
The goal is to replace placeholders fast without widening scope or inventing claims.

## Inputs to collect from the proof-fold lane

- [ ] Final proof branch name
- [ ] Final proof commit SHA
- [ ] Exact artifact path(s)
- [ ] Exact script / entrypoint path
- [ ] Exact screenshot or log excerpt path
- [ ] One sentence describing what the proof demonstrates
- [ ] One sentence stating what it still does **not** prove

## Files to update immediately

- [ ] `submission/drafts/judge-demo-script.md`
- [ ] `submission/drafts/pr-or-submission-summary.md`
- [ ] `submission/drafts/conversation-log.roundtrip-ready.md`
- [ ] `submission/drafts/evidence-proof-manifest.roundtrip-ready.json`
- [ ] `submission/drafts/submission-metadata.roundtrip-ready.json`

## Placeholder sweep

Run this before committing the fold:

```bash
rg -n "FILL_(ROUNDTRIP|FINAL)" submission/drafts submission/checklists
```

Required outcome:
- demo-facing files only contain placeholders that are still intentionally pending
- final user-facing packet files contain **no accidental placeholders**

## Claim-boundary checks after fill

- [ ] The roundtrip proof is described as **external Clawith -> OpenClaw -> Claude/vibecosystem**.
- [ ] No text was upgraded to claim **native Clawith parity**.
- [ ] No text was upgraded to claim **sealed certification**.
- [ ] If native model-pool smoke is still missing, it remains explicitly blocked.

## Final hygiene

- [ ] Re-validate JSON drafts after placeholder replacement.
- [ ] Re-run markdown sanity check.
- [ ] Run `git diff --check`.
- [ ] Commit with a message that clearly says the roundtrip-proof placeholders were filled from the active lane.
