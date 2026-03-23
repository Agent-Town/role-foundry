# Spec 013 — ERC-8004 Base / agent0-sdk Python mint path

Status: Implementing
Owner: Role Foundry
Last updated: 2026-03-23

## Objective

Add a narrow, Role Foundry-owned path that makes the **generation provenance -> promotion -> portable identity** handoff explicit:

- a generation runs
- receipts + evaluation context + score deltas are captured
- humans decide whether that generation is promoted/public
- promoted/public generations can then be issued as ERC-8004 identities on **Base** through the Python `agent0-sdk` mint flow

This path does not fake signers, onchain transactions, or mint receipts.

## Scope

### In scope

- `runner_bridge/product_integrations.py` — generates local ERC-8004 registration draft, completion template, and Python mint contract tied to run receipts.
- `runner_bridge/erc8004_agent0.py` — explicit Python helper following the real SDK flow:
  `SDK({ chainId, rpcUrl, signer, registryOverrides?, subgraphOverrides? })` → `createAgent(...)` → `setMetadata(...)` → `register(tokenUri)` → `wait_confirmed()`.
- Base Sepolia (chain id 84532) as the review/demo default.
- Base Mainnet (chain id 8453) as the explicit submission target.
- Env-driven chain config (RPC URL required for the helper; registry/subgraph overrides optional).
- Honest claim-boundary checklist update.
- Reviewer-facing wording that promoted/public generations are the intended issuance candidates.

### Out of scope

- Browser wallet / wallet-popup UI work.
- Broad `runner_bridge` churn or refactoring.
- Claims of live minting, sealed eval, or partner-track completion.
- Automatic promotion of every run/generation into a public identity.
- IPFS registration (`registerIPFS`) — future follow-up.

## Architecture

```text
runner_bridge/product_integrations.py
  ├── write_product_integrations(run_dir, request, result, target_chain)
  │     writes to: integrations/
  │       erc8004-registration-draft.json    ← local draft, not minted
  │       erc8004-completion-template.json   ← awaiting explicit live mint
  │       agent0-python-mint.json            ← Python mint contract + env requirements
  │       trust-bundle.json                  ← full integration status
  │       summary.md                         ← human-readable summary

runner_bridge/erc8004_agent0.py
  ├── mint_erc8004_registration(...)
  ├── build_completion_record(...)
  └── main()                                 ← explicit CLI entrypoint
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

Optional registry override: `BASE_SEPOLIA_REGISTRY` / `BASE_MAINNET_REGISTRY`.

Optional subgraph override: `BASE_SEPOLIA_SUBGRAPH_URL` / `BASE_MAINNET_SUBGRAPH_URL`.

## Exact SDK flow this repo supports

The repo-support contract is based on the current Python SDK surface, not guesswork:

- signer/private key init: `SDK(chainId=..., rpcUrl=..., signer=<private_key>)`
- Base chain config: `chainId` + `rpcUrl`, optional `registryOverrides` / `subgraphOverrides`
- HTTP/token-URI registration: `agent.register(tokenUri)`
- transaction handle: `tx.tx_hash`
- confirmation call: `tx.wait_confirmed(timeout=...)`
- confirmation payload: `{ receipt, result }`
- result fields: `result.agentId`, `result.agentURI`

## Wired vs pending

The path makes this explicit at every layer:

| Layer | Wired now? | What makes it live |
|---|---|---|
| Bridge integration | Yes | `RunBridge.run()` calls `write_product_integrations` after provenance |
| Registration draft generation | Yes | Runs after every `write_product_integrations` call |
| Completion template generation | Yes | Same |
| Python mint helper module | Yes (code exists) | Requires `agent0-sdk`, RPC URL, signer private key, public token URI, explicit live gate, and `--promoted-public` |
| Promotion/public-issuance decision | Human review only | Requires deciding the generation is worth public issuance |
| Live mint on Base Sepolia | No | Requires configured RPC URL + signer + public token URI + explicit gate |
| Live mint on Base Mainnet | No | Same + explicit submission-target confirmation |

## Claim boundary

### Allowed now

- Role Foundry drafts ERC-8004 registration targeting Base.
- The canonical in-repo path is Python-native and matches the real SDK surface.
- The path makes staged-vs-live explicit.
- Promoted/public generations can be framed as the portable-identity layer.

### Not allowed now

- "Role Foundry has minted an ERC-8004 identity on Base."
- Any sealed eval, tamper-proof, or certification claim.
- Partner-track completion claims.
- Treating the historical browser adapter as the canonical integration story.

## Test coverage

- `tests/test_erc8004_base_agent0_adapter.py` — unit tests for `product_integrations.py` and `erc8004_agent0.py`:
  - draft generation includes Base chain info
  - completion template stays in explicit staged state
  - Python mint contract references correct chain/env vars
  - trust bundle status reflects staged-vs-live honestly
  - verifiable receipt hashing excludes mutable files (`artifact-bundle.json`, `result.json`)
  - Python helper enforces live gate + promoted/public gate
  - Python helper writes a confirmed completion record from a mocked SDK transaction

## Dependencies

- `agent0-sdk` (Python package)
- Python 3.11+ for the repo helper modules

## Follow-ups

- Add a real hosted token-URI publishing path for the draft JSON.
- Decide whether to pin `agent0-sdk` in repo bootstrap docs.
- Wire IPFS registration (`registerIPFS`) as an alternative to `register(tokenUri)`.
- Record one real Sepolia mint receipt once the public token-URI hosting step exists.
