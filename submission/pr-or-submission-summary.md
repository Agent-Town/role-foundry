# PR / submission summary

Status: final-review-ready
Canonical final packet artifact for this branch.

## Plain-English summary

This branch takes the frozen submission packet and makes the core story cleaner: Role Foundry is a **generation provenance** system for role-scoped apprentices. Each evaluated generation leaves inspectable receipts, evaluation context, score deltas, and a promotion decision. Promoted public generations can then be staged for **ERC-8004 issuance on Base** through a thin Role Foundry-owned Python mint path.

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

This branch is better than the frozen packet because it no longer says "ERC later" while the code is already present. It shows the full narrow chain — generation receipts -> evaluation -> deltas -> promotion -> staged portable identity — without widening the evidence boundary.
