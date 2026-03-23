# Spec 009 — Clawith Readiness Probe Lane

## Goal

Replace fuzzy bring-up assumptions with a read-only probe lane that tells us whether a local upstream Clawith instance is actually usable for adapter-first Role Foundry work.

## Requirements

1. Role Foundry must provide a **read-only probe** command for a Clawith base URL.
2. The probe must verify the public upstream surface:
   - `GET /api/health`
   - `GET /api/version`
   - `GET /api/auth/registration-config`
3. The probe must verify the auth-gated surface shape:
   - `/api/auth/me`
   - `/api/enterprise/llm-models`
   - `/api/admin/companies`
4. The probe must support an optional deeper local check for:
   - admin presence
   - model-pool presence
   using **read-only** local inspection (for example Docker/container SQL reads).
5. The docs must explicitly call out endpoint mismatch / adapter risk when upstream Clawith does **not** expose:
   - `/api/roles`
   - `/api/scenarios`
   - `PATCH /api/runs/{run_id}`
6. The compose health check must target the real upstream health path, not a weaker frontend path.
7. No destructive writes are allowed in the default live-mode preflight path.

## Acceptance

A contributor can run one command and answer, honestly:
- is upstream Clawith alive?
- is the auth surface real?
- is there an admin yet?
- is there a model pool yet?
- do we still need an adapter/shim for Role Foundry-native writes?

## Non-goals

- inventing native upstream parity
- changing runner bridge core contracts
- forcing seed writes into stock upstream Clawith
