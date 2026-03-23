# PR / submission summary

Status: submission-packet-ready_pending_human_publish
Canonical final packet artifact for this branch.

## Plain-English summary

This branch turns the honest review line into a **submission-ready packet** without widening the evidence boundary. Role Foundry is a **generation provenance** system for role-scoped apprentices: each evaluated generation leaves inspectable receipts, evaluation context, score deltas, and a promotion decision. Promoted public generations can then be staged for **ERC-8004 issuance on Base** through a thin Role Foundry-owned adapter.

The first concrete role remains a **Software Engineer apprentice** improving Role Foundry itself. The shipped public slice is still frontend/product-heavy, and this branch keeps saying that plainly instead of pretending broader completed coverage.

## What a judge can verify quickly

- an executable **public alpha / public-regression loop** with baseline -> candidate -> teacher-eval -> better/equal/worse comparison proof
- a **local private-holdout** separation boundary where teacher-only prompts stay outside tracked and student-visible artifacts
- a staged **ERC-8004 / Base** issuance path where receipt-backed generations get local registration drafts, completion templates, and a thin agent0/Base adapter contract without faking a wallet tx
- one tracked external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip proof, backed by a reviewer-safe manifest/export bundle under `submission/`
- a canonical submission packet under `submission/` with final paths instead of broken local proof references

## What this branch deliberately does not claim

- **live Base minting** on Sepolia or mainnet
- **partner-track completion**
- **native Clawith parity**
- **native model-pool bring-up completion**
- **sealed certification** or **sealed eval**
- **tamper-proof** or **third-party-sealed** evaluation

## Reviewer note

This packet is ready to publish once the short human/admin steps in `submission/checklists/final-publish-todo.md` are done. The story stays narrow and honest: generation receipts -> evaluation -> deltas -> promotion -> staged portable identity, with no fake jump to live minting or sealed evaluation.
