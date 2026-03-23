# Spec 013 — ERC-8004 Base / agent0-sdk Adapter

Status: Implementing
Owner: Role Foundry
Last updated: 2026-03-23

## Objective

Add a narrow, Role Foundry-owned adapter that makes the **generation provenance -> promotion -> portable identity** path explicit:

- a generation runs
- receipts + evaluation context + score deltas are captured
- humans decide whether that generation is promoted/public
- promoted/public generations can then be issued as ERC-8004 identities on **Base** through the agent0-sdk mint shape

This adapter does not fake wallet sessions, onchain transactions, or minting receipts.

## Scope

### In scope

- `runner_bridge/product_integrations.py` — generates local ERC-8004 registration draft, completion template, and agent0 Base adapter contract tied to run receipts.
- `app/agent0_base_adapter.mjs` — thin browser adapter following the agent0 mint shape: `discoverEip6963Providers` → `connectEip1193` → `SDK({ chainId, rpcUrl, walletProvider, registryOverrides })` → `createAgent(...)` → `registerHTTP(tokenUri)`.
- Base Sepolia (chain id 84532) as the review/demo default.
- Base Mainnet (chain id 8453) as the explicit submission target.
- Env-driven chain config (RPC URL + explicit registry address required for live minting; subgraph optional).
- Honest claim-boundary checklist update.
- Reviewer-facing wording that promoted/public generations are the intended issuance candidates.

### Out of scope

- MetaMask Delegation Toolkit integration.
- Broad runner_bridge churn or refactoring.
- Any UI beyond the adapter module itself.
- Claims of live minting, sealed eval, or partner-track completion.
- Automatic promotion of every run/generation into a public identity.
- IPFS registration (`registerIPFS`) — future follow-up.

## Architecture

```
runner_bridge/product_integrations.py
  ├── write_product_integrations(run_dir, request, result, target_chain)
  │     writes to: integrations/
  │       erc8004-registration-draft.json    ← local draft with enriched provenance
  │       erc8004-completion-template.json   ← v2, awaiting_wallet_confirmation
  │       agent0-base-adapter.json           ← adapter contract + env requirements
  │       trust-bundle.json                  ← full integration status
  │       summary.md                         ← human-readable summary

runner_bridge/mint_gateway.py
  ├── is_live_mint_enabled()                   ← checks ROLE_FOUNDRY_LIVE_MINT env
  ├── check_mint_prerequisites()               ← diagnostic of all required env
  └── mint_student_identity(draft_path, ...)   ← invokes Node mint script, returns result

app/mint_student_erc8004.mjs                   ← server-side mint via privateKey signer
  ├── Loads registration draft JSON
  ├── Initializes Agent0 SDK with privateKey
  ├── Creates agent from draft fields
  ├── Calls agent.registerHTTP(tokenUri)
  ├── Waits for tx confirmation
  └── Outputs JSON completion record to stdout

app/agent0_base_adapter.mjs                    ← browser-side mint via wallet
  ├── discoverProviders(agent0sdk)
  ├── connectWallet(provider, agent0sdk)
  ├── initSDK(agent0sdk, { chainId, rpcUrl, walletProvider, ... })
  ├── createAgentFromDraft(sdk, draft)
  ├── mintAgent(agent, tokenUri)               ← only wallet tx trigger
  ├── buildCompletionRecord(mintResult, opts)
  └── checkReadiness(opts)                     ← diagnostic, never throws
```

## Generation provenance model

For the submission story, every evaluated generation should be legible through four questions:

1. **What ran?** — request + transcript + receipt bundle
2. **How was it judged?** — evaluation context + teacher scorecard
3. **Did it improve?** — visible score deltas / better-equal-worse comparison
4. **What happened next?** — stayed local, was promoted publicly, or became eligible for ERC-8004 issuance

This spec only wires the last step as a staged adapter. It does not declare that every run is public or minted.

## Chain configuration

| Chain | ID | Default target | Env var |
|---|---|---|---|
| Base Sepolia | 84532 | review/demo | `BASE_SEPOLIA_RPC_URL` |
| Base Mainnet | 8453 | submission | `BASE_MAINNET_RPC_URL` |

Registry address is required (the local agent0-ts checkout does not reliably ship Base defaults). Subgraph URL is optional.

## Wired vs pending

The adapter makes this explicit at every layer:

| Layer | Wired now? | What makes it live |
|---|---|---|
| Bridge integration | Yes | `RunBridge.run()` calls `write_product_integrations` after provenance |
| Registration draft generation | Yes | Runs after every `write_product_integrations` call |
| Completion template generation | Yes | Same |
| Browser adapter module | Yes (code exists) | Requires agent0-sdk + wallet + RPC URL + registry override at runtime |
| Server-side mint script | Yes (code exists) | Requires ROLE_FOUNDRY_LIVE_MINT=1 + SIGNER_PRIVATE_KEY + RPC + registry |
| Python mint gateway | Yes (code exists) | Wraps Node script with safety gating |
| Provenance fields in draft | Yes | teacher_identity, curriculum_id, scorecard_hash, score_delta, promotion_status |
| Promotion/public-issuance decision | Human review only | Requires deciding the generation is worth public issuance |
| Live server-side mint on Base Sepolia | No | Requires all env vars configured + agent0-sdk available |
| Live browser mint on Base Sepolia | No | Requires agent0-sdk + wallet + RPC URL + registry override |
| Live mint on Base Mainnet | No | Same + explicit submission-target confirmation |

## Claim boundary

### Allowed now

- Role Foundry drafts ERC-8004 registration targeting Base.
- The adapter contract and browser module exist and follow the agent0 mint shape.
- The adapter makes wired-vs-pending explicit.
- Promoted/public generations can be framed as the portable-identity layer.

### Not allowed now

- "Role Foundry has minted an ERC-8004 identity on Base."
- Any sealed eval, tamper-proof, or certification claim.
- Partner-track completion claims.
- Native Clawith parity claims.

## Test coverage

- `tests/test_erc8004_base_agent0_adapter.py` — unit tests for `product_integrations.py` and `mint_gateway.py`:
  - Draft generation includes Base chain info.
  - Draft carries enriched provenance: teacher_identity, curriculum_id, score_delta, promotion_status.
  - Completion template v2 with mint_modes (server_side + browser).
  - Adapter contract includes server_side_mint configuration.
  - Trust bundle status reflects wired-vs-pending.
  - Verifiable receipt hashing excludes mutable files (`artifact-bundle.json`, `result.json`).
  - No Locus or MetaMask Delegation references in output.
  - Mint gateway is disabled by default (gated).
  - Mint gateway checks prerequisites correctly.
  - Mint gateway requires SIGNER_PRIVATE_KEY when enabled.
  - CLI integration test exercises `python3 -m runner_bridge.cli` and asserts integration files exist.

## Dependencies

- `agent0-sdk` (npm) — not vendored in this repo; the adapter is staged for when it becomes available.
- Python 3.11+ for `product_integrations.py`.

## Follow-ups

- Vendor or pin an agent0-sdk ESM bundle for local development.
- IPFS-backed token URI hosting (currently HTTP; clean hook exists in draft's `token_uri_strategy`).
- Wire IPFS registration (`registerIPFS`) as an alternative to `registerHTTP`.
- Execute first real mint on Base Sepolia with configured env.
- Add a minimal UI surface for the mint flow (blocked on SDK availability).
- Record confirmed mint receipts into the completion template.
