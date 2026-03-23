# Product Integrations Summary

- Run id: `run-eval-002`
- Generated at: `2026-03-23T06:23:42Z`
- Target chain: `Base Sepolia (review/demo default)` (chain id 84532)
- RPC wired: `False`
- Live now: `1` / `3`
- Staged now: `2`
- Blocked now: `0`

## Status by integration

- Verifiable receipts / scorecards: `demo_usable`
- ERC-8004 identity: `draft_ready`
- agent0 Base adapter: `staged`

## agent0-sdk / Base wiring

- Recommended path: `agent0-sdk`
- Registration draft: `integrations/erc8004-registration-draft.json`
- Completion template: `integrations/erc8004-completion-template.json`
- Mint flow: `discoverEip6963Providers` → `connectEip1193` → `SDK({ chainId, rpcUrl, walletProvider })` → `createAgent(...)` → `registerHTTP(tokenUri)`

## Allowed demo claims

- Role Foundry emits hashed local receipts and a teacher scorecard judges can inspect.
- Role Foundry can draft an ERC-8004 registration targeting Base Sepolia (review/demo default) and wire minting through a thin agent0-sdk adapter.
- The agent0-sdk Base adapter contract is staged but the RPC endpoint and registry override for Base Sepolia (review/demo default) are not yet configured.

## Blocked demo claims

- This run already minted an ERC-8004 identity onchain.
