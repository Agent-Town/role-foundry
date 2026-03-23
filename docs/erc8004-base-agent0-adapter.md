# ERC-8004 Base / agent0-sdk Python mint path

## What this is

A thin, Role Foundry-owned Python path that turns a reviewed generation into a **portable identity handoff** on **Base** through the `agent0-sdk` / `agent0-py` mint flow.

The sequencing matters:

1. A generation runs.
2. Role Foundry records receipts, evaluation context, and score deltas.
3. Humans decide whether that generation is worth promoting publicly.
4. Only then should that public/promoted generation be discussed as an ERC-8004 issuance candidate.

Two layers are landed on this branch:

1. **Python integration writer** (`runner_bridge/product_integrations.py`) — runs after each evaluation run and emits local registration drafts, completion templates, and a Python mint contract tied back to the existing receipt bundle. No onchain writes.
2. **Explicit Python mint helper** (`runner_bridge/erc8004_agent0.py`) — off by default, only writes onchain when you deliberately enable the live-mint gate and run the helper.

`app/agent0_base_adapter.mjs` still exists as a historical browser-side experiment, but it is **not** the canonical repo path anymore.

## Target chains

| Chain | ID | Purpose | Env var for RPC |
|---|---|---|---|
| Base Sepolia | 84532 | Review / demo default | `BASE_SEPOLIA_RPC_URL` |
| Base Mainnet | 8453 | Submission target | `BASE_MAINNET_RPC_URL` |

Optional registry override: `BASE_SEPOLIA_REGISTRY` / `BASE_MAINNET_REGISTRY`.

Optional subgraph override: `BASE_SEPOLIA_SUBGRAPH_URL` / `BASE_MAINNET_SUBGRAPH_URL`.

## What the Python SDK flow actually supports

From the current Python package (`agent0-sdk==1.7.x`):

- signer/private key init: `SDK(chainId=..., rpcUrl=..., signer=<private_key>)`
- Base chain config: regular `chainId` + `rpcUrl`, with optional `registryOverrides` / `subgraphOverrides`
- HTTP/token-URI registration: `agent.register("https://...")`
- confirmation shape: `tx.wait_confirmed(timeout=180)` returning an object with:
  - `receipt`
  - `result`
- immediate handle shape: `tx.tx_hash`
- result shape: `result.agentId`, `result.agentURI`

That is the repo-supported mint story now. Not the old browser-wallet `registerHTTP(...)` assumption.

## Product integration writer usage

```python
from runner_bridge.product_integrations import write_product_integrations

summary = write_product_integrations(
    run_dir="runtime/runs/run-001",
    request=request_dict,
    result=result_dict,
    target_chain="base_sepolia",  # or "base_mainnet"
)
# summary["status_by_integration"]["agent0_python_mint"] == "staged"
# summary["target_chain"]["rpc_url_configured"] is an honest diagnostic only
```

The writer produces:

- `integrations/erc8004-registration-draft.json`
- `integrations/erc8004-completion-template.json`
- `integrations/agent0-python-mint.json`
- `integrations/trust-bundle.json`
- `integrations/summary.md`

## Explicit live mint usage

```bash
export BASE_SEPOLIA_RPC_URL="https://sepolia.base.org"
export ROLE_FOUNDRY_ERC8004_PRIVATE_KEY="0xyour_private_key"
export ROLE_FOUNDRY_ERC8004_ENABLE_LIVE_MINT=1

# host integrations/erc8004-registration-draft.json somewhere public first
python3 -m runner_bridge.erc8004_agent0 \
  --run-dir runtime/runs/run-001 \
  --token-uri https://example.com/erc8004/run-001.json \
  --promoted-public
```

What the helper does:

1. reads `integrations/erc8004-registration-draft.json`
2. enforces the explicit live-mint gate (`ROLE_FOUNDRY_ERC8004_ENABLE_LIVE_MINT=1`)
3. refuses to mint unless `--promoted-public` is passed
4. initializes `SDK(chainId, rpcUrl, signer, registryOverrides?, subgraphOverrides?)`
5. creates an agent from the draft
6. adds compact Role Foundry provenance metadata
7. calls `agent.register(tokenUri)`
8. waits for confirmation with `wait_confirmed(timeout=...)`
9. writes `integrations/erc8004-completion.json`

## What is real now

- Registration draft generation targeting Base, wired into `RunBridge.run()`.
- Completion templates that stay staged/off-by-default.
- Canonical Python mint contract + helper module in the actual repo.
- Honest provenance enrichment on the draft: teacher, curriculum themes, proof bundle, score, and promotion state.
- Verifiable receipt hashing of stable artifacts only (`request.json`, `transcript.ndjson`, `receipts/*`).
- A clean story that **promoted/public generations** are the issuance candidates, even though draft files can be written locally for any evaluated generation.

## What is pending

- `agent0-sdk` installed in the Python environment.
- Configured Base RPC URL.
- A hosted public HTTP(S) token URI for the registration draft JSON.
- A human promotion/public-issuance decision for the specific generation.
- A real confirmed mint on Base Sepolia or Base Mainnet.

## Claim boundary

Do **not** claim:

- "Role Foundry has minted on Base." (unless a real confirmed completion record exists)
- Any sealed eval or certification scope.
- Partner-track completion.
- That the browser adapter is the canonical repo path.

Do claim:

- "Role Foundry drafts ERC-8004 registrations targeting Base and wires a Python agent0-sdk mint path in-repo."
- "Each reviewed generation can carry receipts, evaluation context, score deltas, and an issuance-ready identity draft."
- "Promoted/public generations are the intended portable-identity layer."
- "Live mint is explicit, gated, and off by default."
