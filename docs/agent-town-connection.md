# Agent Town connection strategy

## Decision

Role Foundry should be built as a **standalone repository and frontend** that is clearly connected to the **Agent Town** brand, world, and long-term product direction.

It should **not** be built inside Portal for the hackathon.

## Why

Portal onboarding is still flaky, especially around the more mass-adoption wallet path.
That makes it the wrong dependency for a hackathon-critical core loop.

The hackathon version should prefer:
- a clean standalone frontend
- bring-your-own-wallet flows
- simpler, more controllable testing
- reuse of hardened concepts/specs/implementation learnings from Agent Town without inheriting the whole Portal surface area

## Product bridge

The clean bridge is:
1. Human enters Agent Town
2. Human defines a company / role / problem
3. Role Foundry trains an apprentice agent
4. Apprentice is evaluated with visible receipts and scorecards
5. Best apprentice becomes publishable/deployable inside Agent Town later

## Brand reuse

We should reuse:
- Agent Town logo
- brand kit
- visual language
- world framing

We should not force all existing Portal code into the hackathon app unless it clearly speeds shipping.

## Code reuse policy

High-value reuse:
- design assets and visual system
- identity / profile patterns
- proven agent-runtime ideas
- Registry / Library concepts
- experiment-card / iteration-feed patterns
- wallet / agent ownership concepts where already hardened

Low-value reuse for the hackathon:
- unstable onboarding flows
- Privy-dependent mass adoption path
- unrelated Portal surfaces
- anything that hurts clarity or demo reliability

## Wallet stance

For the hackathon MVP:
- assume the user brings their own wallet
- assume the agent/test harness can also have its own wallet
- do not make Privy a dependency for success

Privy can return later as the mass-adoption path, not the hackathon wedge.

## Token connection

For now, the token connection should stay simple:
- link to the token in the menu
- keep the real product value tied to results, not token theatrics

Longer term, the token can connect to:
- deployment / budget rails
- tipping / rewards
- curation / boosts
- reputation / access
- marketplace participation

## Principle

Use Agent Town as the parent world and trust layer.
Use Role Foundry as the sharp, standalone mechanism that actually trains and evaluates useful agents.
