# Agent Town: Role Foundry

Role Foundry is an **Agent Town** subsystem for creating reliable role-specific agents through scenario training, hidden holdout evaluation, and budget-bounded iteration.

This repo is intentionally a **standalone frontend/repository**.
It is connected to the broader Agent Town brand and world, but it is **not** being built inside Portal.

## Current product stance

- **Option A**: standalone repo + frontend, Agent Town-branded
- Reuse **brand kit / logo / visual language** from Agent Town
- Reuse code from Portal only when it clearly accelerates shipping
- Keep the product explanation sharp: this is the apprentice-training / evaluation engine for Agent Town

## Hackathon implementation stance

- **Bring your own wallet** by default
- Do **not** depend on the Privy path for the hackathon MVP
- The token connection can stay lightweight for now: a simple token link in the app menu is enough
- The real core is the evaluation loop, scorecards, logs, receipts, and deployable apprentices

## Why this exists

Most agent demos fake capability.
Role Foundry is meant to make capability visible:
- public training scenarios
- hidden holdout tests
- teacher/student iteration
- artifact bundles
- scorecards
- honest submission metadata and receipts

## Current shorthand

Agent Town = world / shell / broader product surface  
Role Foundry = training + evaluation engine for useful citizens of Agent Town

## Docs

- `docs/agent-town-connection.md`
- `docs/synthesis-hackathon-ideation.md`
- `docs/synthesis-hackathon-stack-architecture.md`
