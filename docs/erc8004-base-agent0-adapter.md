# ERC-8004 Base / agent0-sdk Adapter

## What this is

A thin, Role Foundry-owned adapter that turns a reviewed generation into a **portable identity handoff** on **Base** through the `agent0-sdk` mint shape.

The important sequencing is deliberate:

1. A generation runs.
2. Role Foundry records receipts, evaluation context, and score deltas.
3. Humans decide whether that generation is worth promoting publicly.
4. Only then should that public/promoted generation be discussed as an ERC-8004 issuance candidate.

Three layers are landed on this branch:

1. **Python integration writer** (`runner_bridge/product_integrations.py`) — runs after each evaluation run and emits local registration drafts, completion templates, and adapter contracts tied back to the existing receipt bundle. No onchain writes.

2. **Server-side mint helper** (`app/mint_student_erc8004.mjs`) — Node.js script that mints an ERC-8004 identity using the Agent0 SDK `privateKey` signer path. Gated behind `ROLE_FOUNDRY_LIVE_MINT=1` + `SIGNER_PRIVATE_KEY`. This is the intended per-student mint path after promotion.

3. **Browser adapter** (`app/agent0_base_adapter.mjs`) — thin ESM module that follows the agent0 mint shape for browser-side registration. Only triggers a wallet tx when `mintAgent()` is called.

4. **Python mint gateway** (`runner_bridge/mint_gateway.py`) — Python wrapper that invokes the Node.js mint script with safety gating. Off by default.

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
  registryOverrides: { 84532: { IDENTITY: '0xYourRegistryAddress' } },
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

## Server-side mint (per-student, after promotion)

```bash
# Required env
export ROLE_FOUNDRY_LIVE_MINT=1
export SIGNER_PRIVATE_KEY=0x...
export BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
export BASE_SEPOLIA_REGISTRY=0xYourRegistryAddress

# Mint from a registration draft
node app/mint_student_erc8004.mjs \
  --draft runtime/runs/run-001/integrations/erc8004-registration-draft.json \
  --completion-out runtime/runs/run-001/integrations/mint-completion.json
```

Or via Python:

```python
from runner_bridge.mint_gateway import mint_student_identity, check_mint_prerequisites

# Check what's configured
prereqs = check_mint_prerequisites()
print(prereqs)  # {"ready": False, "live_mint_enabled": False, ...}

# Mint (returns structured result, never throws)
result = mint_student_identity("runtime/runs/run-001/integrations/erc8004-registration-draft.json")
if result["ok"]:
    print(result["data"])  # {agent_id, tx_hash, explorer_url, ...}
else:
    print(result["error"])  # human-readable reason
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
#   "staged" (no RPC URL / registry) or "ready" (RPC URL + registry configured)
```

## Registration draft provenance

The registration draft now carries enriched provenance for each student generation:

| Field | Source | Purpose |
|---|---|---|
| `teacher_identity` | request.teacher_identity or scorecard.teacher | Who judged the generation |
| `curriculum_id` | request.scenario_set_id | Which curriculum/scenario set was used |
| `scorecard_hash` | SHA-256 of scorecard JSON | Proof of evaluation outcome |
| `score_delta` | iteration_history[-1].delta | Score change vs previous generation |
| `promotion_status` | request.promotion_status | "unpromoted" (default) or "promoted" |
| `receipt_manifest_path` | receipts/manifest.json | Full receipt/proof bundle reference |

These fields travel with the draft into the ERC-8004 `extensions.role_foundry` block and are ready for future IPFS-backed token URI hosting.

## What is real now

- Registration draft generation targeting Base, wired into `RunBridge.run()` (runs after every CLI invocation).
- **Server-side mint script** using Agent0 SDK `privateKey` signer — the real per-student mint path.
- **Python mint gateway** with explicit env gating (off by default).
- Enriched provenance fields: teacher identity, curriculum, proof bundle hash, score delta, promotion status.
- Completion template (v2) with both server-side and browser mint mode documentation.
- Browser adapter module with the full mint flow shape.
- Readiness diagnostic that reports exactly what is wired vs pending.
- Verifiable receipt hashing of stable artifacts only (request.json, transcript, receipts/*).
- Explicit Base RPC + registry config requirement (no reliance on agent0-sdk defaults).
- A clean story that **promoted/public generations** are the ones eligible to be issued, even though draft files can be written locally for any evaluated generation.
- Token URI strategy is HTTP now; IPFS hook is clean and documented for next step.

## What is pending

- agent0-sdk availability at runtime (npm install, vendored bundle, or local checkout via `AGENT0_SDK_PATH`).
- Configured Base RPC URL + identity registry address in the environment.
- A human promotion/public-issuance decision for the specific generation.
- `ROLE_FOUNDRY_LIVE_MINT=1` + `SIGNER_PRIVATE_KEY` for the first real server-side mint.
- IPFS-backed token URI hosting (currently HTTP; clean hook in place).
- IPFS registration (`registerIPFS`) as an alternative to `registerHTTP`.

## Claim boundary

Do **not** claim:
- "Role Foundry has minted on Base."
- Any sealed eval or certification scope.
- Partner-track completion.

Do claim:
- "Role Foundry drafts ERC-8004 registrations targeting Base and wires the agent0-sdk mint path through a thin adapter."
- "A server-side mint script uses the Agent0 SDK privateKey signer for per-student minting after promotion."
- "Each reviewed generation carries teacher identity, curriculum, proof bundle, score delta, and promotion status in the registration draft."
- "Promoted/public generations are the intended portable-identity layer."
- "The adapter makes wired-vs-pending explicit. Live mint is gated behind explicit env configuration."
