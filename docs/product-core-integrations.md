# Product-core integrations

This repo now treats four trust/integration lanes as one coherent product slice:

1. **Verifiable receipts / scorecards**
2. **Locus guardrails**
3. **ERC-8004 agent identity**
4. **MetaMask Delegation**

The important point is what this does **not** do:
- no fake onchain writes
- no fake partner-hosted enforcement
- no fake wallet delegation activation
- no fake sealed-eval claim

## Current honest state

| Integration | State now | Why |
|---|---|---|
| Verifiable receipts / scorecards | `demo_usable` | Existing receipt provenance + new content-hash bundle make runs inspectable now |
| Locus guardrails | `demo_usable` | Local contract evaluates redaction/integrity checks now |
| ERC-8004 agent identity | `draft_ready` | Role Foundry can generate a registration draft and a wallet mint plan, but does not claim minting |
| MetaMask Delegation | `contract_ready` | Scope/constraints are defined, but no live permission grant exists |

## Recommended ERC-8004 path
Yes: **agent0-sdk is now the recommended ERC-8004 path for Role Foundry.**

Why:
- local workspace precedent already exists in Agent Town / Portal
- the SDK already supports browser wallet flows
- it keeps the write path human-approved
- it lets Role Foundry own the product contract while reusing the implementation layer

## Exact wiring
1. Role Foundry emits `integrations/erc8004-registration-draft.json`
2. Role Foundry emits `integrations/erc8004-completion-template.json`
3. A thin Role Foundry adapter loads a pinned/vendored `agent0-sdk` browser bundle
4. The adapter discovers/connects a wallet (`discoverEip6963Providers`, `connectEip1193`)
5. The adapter creates the agent with Role Foundry-owned metadata
6. The adapter mints via `registerHTTP(tokenUri)`
7. Only after confirmation does Role Foundry fill the completion record and upgrade the claim from `draft_ready` to `registered`

## MetaMask Delegation stance
MetaMask should be used to constrain future identity-completion work, not as a vague “wallet integration” badge.

So the repo currently emits a **delegation intent** that:
- applies to one run
- applies to one identity-completion action
- blocks arbitrary contract calls
- blocks arbitrary token transfer
- stays non-active until a real permission receipt exists

## Demo claims
Allowed:
- local hashed receipts and teacher scorecards
- local Locus-style guardrail checks
- ERC-8004 draft readiness via `agent0-sdk`
- constrained MetaMask delegation intent

Blocked:
- minted-onchain claim
- active delegation claim
- hosted Locus enforcement claim
- scorecards/proofs written onchain claim
