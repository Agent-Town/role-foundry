# ERC-8004 Base / agent0-sdk Adapter

## What this is

A thin, Role Foundry-owned adapter that wires ERC-8004 agent registration on **Base** through the `agent0-sdk` mint shape. Two layers:

1. **Python integration writer** (`runner_bridge/product_integrations.py`) — runs after each evaluation run and emits local registration drafts, completion templates, and adapter contracts. No onchain writes.

2. **Browser adapter** (`app/agent0_base_adapter.mjs`) — thin ESM module that follows the agent0 mint shape for browser-side registration. Only triggers a wallet tx when `mintAgent()` is called.

## Target chains

| Chain | ID | Purpose | Env var for RPC |
|---|---|---|---|
| Base Sepolia | 84532 | Review / demo default | `BASE_SEPOLIA_RPC_URL` |
| Base Mainnet | 8453 | Submission target | `BASE_MAINNET_RPC_URL` |

Registry address: `BASE_SEPOLIA_REGISTRY` (and `BASE_MAINNET_REGISTRY`) — **required** for live minting. The local agent0-ts checkout does not reliably ship Base defaults.

Subgraph URL: `BASE_SEPOLIA_SUBGRAPH_URL` (and mainnet) — optional.

## Browser adapter usage

```javascript
import * as adapter from './agent0_base_adapter.mjs';

// Check readiness
const status = adapter.checkReadiness({
  agent0sdk,
  walletProvider,
  rpcUrl: 'https://sepolia.base.org',
  chainId: 84532,
});
if (!status.ready) console.log('Missing:', status.checks);

// Discover + connect wallet
const providers = await adapter.discoverProviders(agent0sdk);
if (!providers.ok) throw new Error(providers.error);

const wallet = await adapter.connectWallet(providers.data[0].provider, agent0sdk);
if (!wallet.ok) throw new Error(wallet.error);

// Init SDK (registry is required — agent0-sdk does not default for Base)
const sdk = adapter.initSDK(agent0sdk, {
  chainId: 84532,
  rpcUrl: 'https://sepolia.base.org',
  walletProvider: wallet.data.provider,
  registryOverrides: { '84532': '0xYourRegistryAddress' },
});
if (!sdk.ok) throw new Error(sdk.error);

// Create agent from registration draft
const agent = adapter.createAgentFromDraft(sdk.data, registrationDraft);
if (!agent.ok) throw new Error(agent.error);

// Mint (triggers wallet popup)
const mint = await adapter.mintAgent(agent.data, tokenUri);
if (!mint.ok) throw new Error(mint.error);

// Build completion record
const completion = adapter.buildCompletionRecord(mint, {
  chainId: 84532,
  walletAddress: wallet.data.accounts[0],
});
```

## Python integration writer usage

```python
from runner_bridge.product_integrations import write_product_integrations

summary = write_product_integrations(
    run_dir="runtime/runs/run-001",
    request=request_dict,
    result=result_dict,
    target_chain="base_sepolia",  # or "base_mainnet"
)
# summary["status_by_integration"]["agent0_base_adapter"]
#   "staged" (no RPC URL) or "ready" (RPC URL configured)
```

## What is real now

- Registration draft generation targeting Base, wired into `RunBridge.run()` (runs after every CLI invocation).
- Completion template with `awaiting_wallet_confirmation` status.
- Browser adapter module with the full mint flow shape.
- Readiness diagnostic that reports exactly what is wired vs pending.
- Verifiable receipt hashing of stable artifacts only (request.json, transcript, receipts/*).
- Explicit Base RPC + registry config requirement (no reliance on agent0-sdk defaults).

## What is pending

- agent0-sdk availability (npm install or vendored bundle).
- Configured Base RPC URL + identity registry address in the environment.
- An actual wallet-approved mint on Base Sepolia or Mainnet.
- IPFS registration (registerIPFS) as an alternative to registerHTTP.

## Claim boundary

Do **not** claim:
- "Role Foundry has minted on Base."
- Any sealed eval or certification scope.
- Partner-track completion.

Do claim:
- "Role Foundry drafts ERC-8004 registrations targeting Base and wires the agent0-sdk mint path."
- "The adapter makes wired-vs-pending explicit."
