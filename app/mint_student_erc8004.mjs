#!/usr/bin/env node
/**
 * mint_student_erc8004.mjs — Server-side ERC-8004 mint for a promoted student generation.
 *
 * Uses the Agent0 SDK privateKey signer path (NOT browser wallet/EIP-6963).
 * This is the real mint helper that Role Foundry invokes after a promotion decision.
 *
 * Usage:
 *   node app/mint_student_erc8004.mjs --draft <path-to-registration-draft.json>
 *
 * Required env:
 *   SIGNER_PRIVATE_KEY     - Hex private key for the minting wallet
 *   BASE_SEPOLIA_RPC_URL   - (or BASE_MAINNET_RPC_URL for mainnet)
 *   BASE_SEPOLIA_REGISTRY  - (or BASE_MAINNET_REGISTRY) Identity registry address
 *
 * Optional env:
 *   TARGET_CHAIN           - "base_sepolia" (default) or "base_mainnet"
 *   TOKEN_URI              - HTTP URI for the registration metadata (defaults to draft path)
 *   AGENT0_SDK_PATH        - Path to agent0-sdk package (defaults to local checkout)
 *
 * Output: JSON to stdout with mint result or error.
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Chain config — mirrors product_integrations.py
// ---------------------------------------------------------------------------

const CHAIN_CONFIG = {
  base_sepolia: {
    chain_id: 84532,
    label: 'Base Sepolia (review/demo default)',
    rpc_env: 'BASE_SEPOLIA_RPC_URL',
    registry_env: 'BASE_SEPOLIA_REGISTRY',
    explorer: 'https://sepolia.basescan.org',
  },
  base_mainnet: {
    chain_id: 8453,
    label: 'Base Mainnet (submission target)',
    rpc_env: 'BASE_MAINNET_RPC_URL',
    registry_env: 'BASE_MAINNET_REGISTRY',
    explorer: 'https://basescan.org',
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fail(error, code = 1) {
  const result = { ok: false, error: String(error) };
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exit(code);
}

function loadDraft(draftPath) {
  try {
    const raw = readFileSync(draftPath, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    fail(`Failed to load registration draft: ${err.message}`);
  }
}

async function loadSDK() {
  const sdkPath = process.env.AGENT0_SDK_PATH
    || resolve(__dirname, '..', '..', 'agent0lab', 'agent0-ts');

  try {
    // Try the built dist first, fall back to src
    const mod = await import(resolve(sdkPath, 'dist', 'index.js'));
    return mod;
  } catch {
    try {
      const mod = await import(resolve(sdkPath, 'src', 'index.ts'));
      return mod;
    } catch (err) {
      fail(
        `Cannot load agent0-sdk from ${sdkPath}. ` +
        `Set AGENT0_SDK_PATH or ensure the SDK is built. Error: ${err.message}`
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Main mint flow
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    options: {
      draft: { type: 'string' },
      'completion-out': { type: 'string' },
    },
  });

  if (!values.draft) {
    fail('--draft <path> is required');
  }

  const privateKey = process.env.SIGNER_PRIVATE_KEY;
  if (!privateKey) {
    fail('SIGNER_PRIVATE_KEY env var is required for server-side minting');
  }

  const targetChain = process.env.TARGET_CHAIN || 'base_sepolia';
  const chainCfg = CHAIN_CONFIG[targetChain];
  if (!chainCfg) {
    fail(`Unknown TARGET_CHAIN: ${targetChain}. Use base_sepolia or base_mainnet.`);
  }

  const rpcUrl = process.env[chainCfg.rpc_env];
  if (!rpcUrl) {
    fail(`${chainCfg.rpc_env} env var is required for chain ${chainCfg.chain_id}`);
  }

  const registry = process.env[chainCfg.registry_env];
  if (!registry) {
    fail(`${chainCfg.registry_env} env var is required (agent0-sdk does not default for Base)`);
  }

  // Load the registration draft
  const draft = loadDraft(values.draft);

  // Validate draft has provenance fields
  if (!draft.name) {
    fail('Registration draft missing "name" field');
  }

  // Load agent0-sdk
  const agent0 = await loadSDK();

  // Initialize SDK with privateKey signer
  const sdk = new agent0.SDK({
    chainId: chainCfg.chain_id,
    rpcUrl,
    privateKey,
    registryOverrides: {
      [chainCfg.chain_id]: { IDENTITY: registry },
    },
  });

  // Create agent from draft
  const agent = sdk.createAgent(
    draft.name,
    draft.description || '',
    draft.image || 'about:blank',
  );

  // Add services from draft if present
  if (Array.isArray(draft.services)) {
    for (const svc of draft.services) {
      if (svc.name && svc.endpoint) {
        agent.addEndpoint(svc.name, svc.type || 'web', svc.endpoint);
      }
    }
  }

  // Determine token URI
  const tokenUri = process.env.TOKEN_URI || '';

  // Mint via registerHTTP
  const regTx = await agent.registerHTTP(tokenUri);

  // Wait for confirmation
  const { receipt, result: registrationFile } = await regTx.waitConfirmed({
    timeoutMs: 120_000,
  });

  const agentId = registrationFile.agentId || agent.agentId || null;
  const txHash = receipt?.transactionHash || null;

  // Build completion record
  const completionRecord = {
    namespace: 'erc8004',
    chain_id: chainCfg.chain_id,
    chain_label: chainCfg.label,
    identity_registry: registry,
    agent_id: agentId,
    agent_uri: registrationFile.agentURI || tokenUri || null,
    tx_hash: txHash,
    explorer_url: txHash ? `${chainCfg.explorer}/tx/${txHash}` : null,
    minted_at: new Date().toISOString(),
    minted_by: 'server-side-signer',
    mint_mode: 'privateKey',
    draft_path: values.draft,
    provenance: draft.extensions?.role_foundry || null,
  };

  // Write completion record if --completion-out specified
  if (values['completion-out']) {
    writeFileSync(values['completion-out'], JSON.stringify(completionRecord, null, 2));
  }

  const output = { ok: true, data: completionRecord };
  process.stdout.write(JSON.stringify(output, null, 2) + '\n');
}

main().catch((err) => fail(`Unhandled error: ${err.message}`));
