# Submission packet

Canonical final packet for review branch `review/submission-erc-provenance-20260323-1240`.

The recorded `final_review_commit` in the packet files is the **content-freeze commit** for the finalized packet. The branch head may be one tiny stamp commit later so the packet can record a stable non-self-referential SHA.

## Canonical final artifacts

- `submission/judge-demo-script.md`
- `submission/judge-qa-note.md`
- `submission/pr-or-submission-summary.md`
- `submission/conversation-log.md`
- `submission/evidence-proof-manifest.json`
- `submission/submission-metadata.json`

## Supporting proof artifacts

- `submission/clawith-vibecosystem-roundtrip-proof.manifest.json`
- `submission/roundtrip-proof/README.md`
- `submission/roundtrip-proof/roundtrip-proof.export.json`
- `submission/roundtrip-proof/final-reply.txt`
- `submission/checklists/roundtrip-receipt-audit-2026-03-23.md`
- `submission/base-sepolia-mint-proof/run-eval-002/README.md`
- `submission/base-sepolia-mint-proof/run-eval-002/registration.json`
- `submission/base-sepolia-mint-proof/run-eval-002/completion-template.json`
- `submission/base-sepolia-mint-proof/run-eval-002/integrations/summary.md`
- `submission/base-sepolia-mint-proof/run-eval-002/integrations/agent0-base-adapter.json`
- `submission/base-sepolia-mint-proof/run-eval-002/result.json`
- `submission/base-sepolia-mint-proof/run-eval-002/artifact-bundle.json`
- `submission/base-sepolia-mint-proof/run-eval-002/receipts/evidence-index.json`

## Archived prep artifacts

The former `submission/drafts/*` files are kept only as archived handoff markers pointing at the canonical final packet above.

## Current honest claim boundary

This packet supports four current headline claims:
- an executable public alpha / public-regression loop
- a local private-holdout honesty boundary
- a staged ERC-8004 / Base issuance path for promoted public generations, with a load-bearing Base Sepolia draft proof bundle (`run-eval-002`) as partner-wiring evidence
- one external `Clawith -> OpenClaw -> Claude/vibecosystem` roundtrip proof

What ties those together is the generation provenance story: each generation leaves receipts, evaluation context, score deltas, and a promotion/public-issuance decision judges can inspect.

It does **not** support claims of live Base minting, partner-track completion, native Clawith parity, sealed certification, tamper-proof evaluation, or third-party-sealed holdouts.
