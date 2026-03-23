/**
 * agent0_base_adapter.mjs — Role Foundry-owned thin adapter for ERC-8004
 * registration on Base via agent0-sdk.
 *
 * Shape follows the Portal/house.js precedent:
 *   discoverEip6963Providers -> connectEip1193 -> SDK({ chainId, rpcUrl, walletProvider })
 *   -> createAgent(...) -> registerHTTP(tokenUri)
 *
 * This file does NOT fake wallet sessions, onchain txs, or minting receipts.
 * It is a staging adapter: it wires the real mint path and makes wired-vs-pending
 * explicit at every step.
 *
 * Environment:
 *   - Requires agent0-sdk to be available (vendored bundle or CDN).
 *   - Requires an EIP-6963 / EIP-1193 compatible wallet in the browser.
 *   - Chain config (chainId, rpcUrl) must be provided explicitly.
 *   - Base Sepolia (84532) is the review/demo default.
 *   - Base Mainnet (8453) is the explicit submission target.
 */

// ---------------------------------------------------------------------------
// Chain defaults — explicit, env-driven, no faked registry/subgraph values.
// ---------------------------------------------------------------------------

export const BASE_SEPOLIA_CHAIN_ID = 84532;
export const BASE_MAINNET_CHAIN_ID = 8453;

export const CHAIN_PRESETS = {
  [BASE_SEPOLIA_CHAIN_ID]: {
    label: 'Base Sepolia (review/demo default)',
    explorerBase: 'https://sepolia.basescan.org',
  },
  [BASE_MAINNET_CHAIN_ID]: {
    label: 'Base Mainnet (submission target)',
    explorerBase: 'https://basescan.org',
  },
};

// ---------------------------------------------------------------------------
// Status sentinel — every public function returns { ok, error?, data? }
// so callers never have to guess whether something actually happened.
// ---------------------------------------------------------------------------

function ok(data) {
  return { ok: true, data };
}

function fail(error) {
  return { ok: false, error: String(error) };
}

// ---------------------------------------------------------------------------
// 1. Wallet discovery (EIP-6963)
// ---------------------------------------------------------------------------

/**
 * Discover injected EIP-6963 wallet providers.
 * Returns { ok, data: provider[] } or { ok: false, error }.
 *
 * If agent0-sdk is available and exports discoverEip6963Providers, delegates
 * to that.  Otherwise falls back to window.ethereum if present.
 */
export async function discoverProviders(agent0sdk) {
  try {
    if (agent0sdk && typeof agent0sdk.discoverEip6963Providers === 'function') {
      const providers = await agent0sdk.discoverEip6963Providers();
      if (!providers || providers.length === 0) {
        return fail('No EIP-6963 wallet providers found.');
      }
      return ok(providers);
    }
    // Fallback: window.ethereum (MetaMask or compatible)
    if (typeof window !== 'undefined' && window.ethereum) {
      return ok([{ provider: window.ethereum, info: { name: 'window.ethereum' } }]);
    }
    return fail('No wallet provider found. Install a browser wallet (e.g. MetaMask).');
  } catch (err) {
    return fail(`Wallet discovery failed: ${err.message || err}`);
  }
}

// ---------------------------------------------------------------------------
// 2. Wallet connection (EIP-1193)
// ---------------------------------------------------------------------------

/**
 * Connect to an EIP-1193 provider (prompts the user).
 * Returns { ok, data: { provider, accounts } } or { ok: false, error }.
 */
export async function connectWallet(provider, agent0sdk) {
  try {
    if (agent0sdk && typeof agent0sdk.connectEip1193 === 'function') {
      await agent0sdk.connectEip1193(provider);
    } else {
      // Direct EIP-1193 request
      await provider.request({ method: 'eth_requestAccounts' });
    }
    const accounts = await provider.request({ method: 'eth_accounts' });
    if (!accounts || accounts.length === 0) {
      return fail('Wallet connected but no accounts returned.');
    }
    return ok({ provider, accounts });
  } catch (err) {
    return fail(`Wallet connection failed: ${err.message || err}`);
  }
}

// ---------------------------------------------------------------------------
// 3. SDK initialization
// ---------------------------------------------------------------------------

/**
 * Initialize agent0-sdk targeting a Base chain.
 *
 * @param {object} agent0sdk  - The imported agent0-sdk module (must export SDK).
 * @param {object} opts
 * @param {number} opts.chainId        - 84532 (Base Sepolia) or 8453 (Base Mainnet).
 * @param {string} opts.rpcUrl         - Base RPC endpoint (required).
 * @param {object} opts.walletProvider - Connected EIP-1193 provider.
 * @param {object} [opts.registryOverrides]  - Optional registry address override.
 * @param {object} [opts.subgraphOverrides]  - Optional subgraph URL override.
 *
 * Returns { ok, data: sdkInstance } or { ok: false, error }.
 */
export function initSDK(agent0sdk, opts) {
  if (!agent0sdk || typeof agent0sdk.SDK !== 'function') {
    return fail('agent0-sdk not loaded or does not export SDK.');
  }
  if (!opts || !opts.rpcUrl) {
    return fail('rpcUrl is required to initialize the SDK.');
  }
  if (!opts.walletProvider) {
    return fail('walletProvider is required for write operations.');
  }

  const chainId = opts.chainId || BASE_SEPOLIA_CHAIN_ID;
  const sdkOpts = {
    chainId,
    rpcUrl: opts.rpcUrl,
    walletProvider: opts.walletProvider,
  };
  if (opts.registryOverrides) {
    sdkOpts.registryOverrides = opts.registryOverrides;
  }
  if (opts.subgraphOverrides) {
    sdkOpts.subgraphOverrides = opts.subgraphOverrides;
  }

  try {
    const sdk = new agent0sdk.SDK(sdkOpts);
    return ok(sdk);
  } catch (err) {
    return fail(`SDK initialization failed: ${err.message || err}`);
  }
}

// ---------------------------------------------------------------------------
// 4. Agent creation from registration draft
// ---------------------------------------------------------------------------

/**
 * Create an agent profile from a Role Foundry registration draft.
 *
 * @param {object} sdk   - Initialized agent0-sdk instance.
 * @param {object} draft - The registration draft from product_integrations.py.
 *
 * Returns { ok, data: agent } or { ok: false, error }.
 */
export function createAgentFromDraft(sdk, draft) {
  if (!sdk || typeof sdk.createAgent !== 'function') {
    return fail('SDK instance is missing or does not support createAgent.');
  }
  if (!draft || !draft.name) {
    return fail('Registration draft is missing or has no name.');
  }

  try {
    const agent = sdk.createAgent(
      draft.name,
      draft.description || '',
      draft.image || 'about:blank'
    );
    return ok(agent);
  } catch (err) {
    return fail(`Agent creation failed: ${err.message || err}`);
  }
}

// ---------------------------------------------------------------------------
// 5. Minting (registerHTTP)
// ---------------------------------------------------------------------------

/**
 * Mint the agent onchain via registerHTTP.
 * This is the ONLY function that triggers a wallet transaction.
 *
 * @param {object} agent    - agent0-sdk agent instance.
 * @param {string} tokenUri - URI for the registration JSON (can be '' for now).
 *
 * Returns { ok, data: { agentId, txHash, chainId } } or { ok: false, error }.
 */
export async function mintAgent(agent, tokenUri) {
  if (!agent || typeof agent.registerHTTP !== 'function') {
    return fail('Agent instance does not support registerHTTP.');
  }

  try {
    const regTx = await agent.registerHTTP(tokenUri || '');
    // agent0-sdk returns a pending tx; wait for confirmation
    if (regTx && typeof regTx.waitConfirmed === 'function') {
      const { receipt } = await regTx.waitConfirmed();
      return ok({
        agentId: agent.agentId || null,
        agentURI: agent.agentURI || null,
        txHash: receipt?.transactionHash || null,
      });
    }
    // Older SDK versions may return the result directly
    return ok({
      agentId: regTx?.agentId || agent.agentId || null,
      agentURI: regTx?.agentURI || agent.agentURI || null,
      txHash: null,
    });
  } catch (err) {
    return fail(`Minting failed: ${err.message || err}`);
  }
}

// ---------------------------------------------------------------------------
// 6. Completion record writer
// ---------------------------------------------------------------------------

/**
 * Build a completion record from a successful mint.
 * This is the data that fills the completion template's required_after_mint fields.
 *
 * Does NOT write to any file — the caller decides persistence.
 */
export function buildCompletionRecord(mintResult, opts) {
  if (!mintResult || !mintResult.ok) {
    return fail('Cannot build completion record from a failed mint.');
  }
  const { agentId, agentURI, txHash } = mintResult.data;
  const chainId = opts?.chainId || BASE_SEPOLIA_CHAIN_ID;
  const preset = CHAIN_PRESETS[chainId] || {};

  return ok({
    namespace: 'erc8004',
    chain_id: chainId,
    chain_label: preset.label || `chain ${chainId}`,
    identity_registry: opts?.registry || 'agent0-sdk-default',
    agent_id: agentId,
    agent_uri: agentURI,
    tx_hash: txHash,
    explorer_url: txHash && preset.explorerBase
      ? `${preset.explorerBase}/tx/${txHash}`
      : null,
    minted_at: new Date().toISOString(),
    minted_by: opts?.walletAddress || null,
  });
}

// ---------------------------------------------------------------------------
// 7. Status check — is a live mint possible right now?
// ---------------------------------------------------------------------------

/**
 * Check whether the adapter is fully wired for a live mint attempt.
 * Returns a diagnostic object, never throws.
 */
export function checkReadiness(opts) {
  const checks = {
    agent0_sdk_available: !!(opts?.agent0sdk && typeof opts.agent0sdk.SDK === 'function'),
    wallet_provider_present: !!opts?.walletProvider,
    rpc_url_configured: !!opts?.rpcUrl,
    chain_id_valid: [BASE_SEPOLIA_CHAIN_ID, BASE_MAINNET_CHAIN_ID].includes(opts?.chainId),
  };
  const ready = Object.values(checks).every(Boolean);
  return { ready, checks };
}
