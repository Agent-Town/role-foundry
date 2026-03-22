# Synthesis Hackathon Ideation

_Last updated: 2026-03-22_

## Why this document exists

This is the working note for our Synthesis hackathon thinking: the ideas themselves, the ranking logic, and how our reasoning evolved.

The goal is **not** to collect random brainstorms.
The goal is to converge on **one sharp submission** that feels technically real, stacks multiple partner tracks honestly, and is memorable to judges.

Related architecture note: `docs/synthesis-hackathon-stack-architecture.md`

---

## Core constraints and heuristics

### Hackathon framing we are optimizing for
- One submission can stack up to **10** partner tracks, and the **Synthesis Open Track does not count toward that limit**.
- But we explicitly do **not** want a "sticker demo" with shallow integrations.
- Better target: **one coherent product with ~6–8 load-bearing integrations**.
- Official submission docs also increase the importance of proof and honesty:
  - public open-source repo
  - real `conversationLog`
  - honest `submissionMetadata` (framework, harness, model, skills, tools, resources)
  - real participant identity and onchain artifacts
- Judging emphasis from earlier public materials still appears to reward:
  - technical execution first
  - innovation second
  - impact third
  - presentation fourth

### Our current heuristics
1. **Autoresearch should be structural, not cosmetic.**
   Do not just mention Karpathy in the README. The product itself should contain an evaluate -> iterate -> keep/discard loop.
2. **Evaluation first.**
   If the eval is weak, the whole demo becomes fake. This matches older ZHC1 thinking: define the optimization function up front or the experiments become garbage.
3. **Real receipts beat vibes.**
   Real permissions, real spend controls, real identity, real payments, real logs, real score deltas.
4. **Use Agent Town assets where they create speed, not where they distort the idea.**
   Reuse is a major advantage, but the submission does not have to be boxed into Agent Town if a cleaner product wins.
5. **A verticalized example is often stronger than a generic platform claim.**
   Build the general mechanism, but demo it in one believable lane.
6. **Documentation is part of the product.**
   The official submission flow explicitly values `conversationLog`, honest stack metadata, repo history, and onchain evidence. If the build cannot explain itself clearly, it is weaker than a slightly less ambitious build with better receipts.

---

## Partner-track logic

### High-confidence core stack clusters

#### Identity / trust
- ERC-8004
- ENS
- Self

#### Permissions / guardrails
- MetaMask Delegation
- Locus

#### Wallet / funding / rails
- Base
- Celo
- Bankr
- MoonPay / OpenWallet

#### Economic activity
- Uniswap
- OpenServ
- Olas / Pearl
- Base service/commercial track

#### Privacy / proofs / storage
- Venice
- EigenCloud
- Filecoin

### Serious-build partners vs spice

#### Strong default partners for serious builds
- ERC-8004
- ENS
- Self
- MetaMask Delegation
- Locus
- Base
- Bankr
- Uniswap
- OpenServ / Olas

For finance / yield-heavy builds, add **Lido** and/or **Zyfai** to the serious-build set — they are core, not spice.

#### Spice, not baseline
- Venice
- EigenCloud
- Filecoin

These are interesting, but they should support a strong core product rather than become the whole demo unless we have a very specific reason.

### Official documentation corrections (2026-03-22)
- Track stacking is officially **max 10 tracks, excluding the Synthesis Open Track**.
- Registration creates a real **ERC-8004 identity on Base Mainnet**.
- Publishing requires **self-custody for all team members**, so any submission plan should assume wallet / transfer readiness, not just demo readiness.
- Officially confirmed track surfaces now include:
  - **Identity / trust:** ERC-8004, ENS, Self, Slice / ERC-8128
  - **Permissions / guardrails:** MetaMask Delegation, Locus, Arkhai / escrow patterns
  - **Wallets / payments / rails:** Base, Celo, Bankr, MoonPay, Status, bond.credit
  - **Economic activity / services:** Uniswap, OpenServ, Olas / Pearl
  - **Finance / treasury / yield:** Lido, Zyfai
  - **Privacy / proofs / storage:** Venice, EigenCloud, Filecoin, Lit
- **Important correction:** yield-heavy ideas should be framed around concrete official surfaces such as **Lido MCP**, **stETH Agent Treasury**, **Vault Position Monitor + Alert Agent**, and/or **Zyfai Yield-Powered AI Agents / Native Wallet / Programmable Yield** — not vague "yield" language.
- **Important correction:** MoonPay is officially narrower than generic payment rails; the real fit is **MoonPay CLI Agents** and **OpenWallet Standard**.
- **Important correction:** ENS is more central than previously treated because it has explicit tracks for **identity**, **communication**, and **open integration**.
- **Important correction:** Status gasless and Slice / ERC-8128 look like good opportunistic bonus fits, but they should not distort the core product unless they belong naturally.

---

## How the thinking evolved

### Phase 1 — initial multi-track product sweep
After reviewing partner themes, the strongest early concepts were:
1. **YieldOS / Agent CFO**
2. **Agent Desk**
3. **Quiet Deal Desk**

At that point, the thinking was:
- optimize for one coherent product
- show real permissions + identity + payments + receipts
- avoid shallow 10-track stacking

### Phase 2 — Karpathy autoresearch changes the frame
We then looked at Andrej Karpathy's `autoresearch` pattern and extracted the useful parts:
- human-authored `program.md`
- explicit metric defined up front
- bounded mutable surface
- short time-boxed experiments
- keep/discard loop
- clear results log

This pushed the ideation toward **experimentation-as-product**, not just experimentation-as-development-process.

That shift made **AutoFounder / Venture Autoresearch** much stronger, because it felt like a generalized version of a culturally hot and respected agent loop.

### Phase 3 — teacher/student idea upgrades the whole field
Robin then proposed the teacher/student concept:
- user defines the target role, goals, and success criteria
- a teacher agent derives evaluation scenarios
- user curates the scenarios
- split into public training scenarios and hidden holdout scenarios
- a student agent iteratively improves its `SOUL.md` / `IDENTITY.md` / policy stack using autoresearch
- the teacher evaluates on hidden holdouts
- failures create the next public curriculum
- the loop continues under a user-defined resource budget

This is the strongest evaluation story so far.

**Why it matters:** most agent demos fake competence. Hidden holdouts make the quality signal much more credible.

This is what moved the new **Agent Studio / Role Foundry** concept into the top spot.

**Note:** the ranked list below captures the broader idea landscape and the evolution of the thinking. The corrected, official-doc-verified shortlist appears later in **Current recommendation**.

---

## Current ranked options (top 10)

## 1) Agent Studio / Role Foundry
**Current rank:** #1  
**Why it matters:** best fusion of autoresearch, evaluation, user-defined utility, and future marketplace potential.

**Pitch:**
Create reliable role-specific agents by training them against curated public scenarios and hidden holdout tests.

**Why it is strong**
- Teacher/student loop is intuitive.
- Hidden holdout set makes evaluation feel real.
- Output is a concrete artifact: agent identity, policies, profile, scorecard, failure analysis.
- Can later connect naturally to marketplaces and deployable agent identities.

**Strong stack fit**
- ERC-8004
- ENS
- Self
- OpenServ
- Olas
- Base
- Bankr
- MetaMask Delegation
- Locus
- optional Filecoin / Venice

**Naming note**
"Character studio" is a fun internal vibe, but the more serious pitch should probably use:
- Agent Studio
- Role Foundry
- Apprentice Lab
- Mentor Loop
- Guild Forge

---

## 2) AutoFounder / Venture Autoresearch
**Current rank:** #2

**Pitch:**
Karpathy autoresearch, but for building real businesses instead of tiny training loops.

**Core loop**
- define a business problem
- define success criteria
- run time-boxed experiments
- review experiment cards
- keep/discard
- converge on a stronger business artifact

**Why it is strong**
- Huge narrative power.
- Excellent fit with ZHC1 and Agent Town history.
- Easy for judges to understand.

**Important correction**
To stay strong after the official-doc check, this cannot just be a smart experimentation UI. It needs visible trust / identity / payment / receipt wiring if we want it to stack partner tracks honestly.

---

## 3) YieldOS / Agent CFO
**Current rank:** #3

**Pitch:**
A yield-aware agent treasury built around a specific protocol path — ideally **Lido stETH yield control** and/or **Zyfai yield accounts** — where principal is protected and the agent operates from yield or earned revenue.

**Why it is strong**
- Now maps to concrete official tracks, not just a finance vibe.
- Strong receipts / monitoring story.
- Integrations can still be intrinsic rather than decorative.

**Main risk**
Financial correctness and protocol specificity may eat precious build time. This only works if we pick a concrete path — e.g. Lido treasury + vault monitor, or Zyfai yield loop — and keep scope ruthless.

---

## 4) Agent Desk / Service Foundry
**Current rank:** #4

**Pitch:**
A service agent that sells work, gets paid, improves itself over time, and can subcontract helper agents.

**Why it is strong**
- Easy to demo.
- Monetizable.
- Clear story: trust, payment, delivery, reputation.

**Main risk**
Can feel expected unless the trust/subcontracting loop is especially sharp.

---

## 5) Guardrail Gym / Red-Team Dojo
**Current rank:** #5

**Pitch:**
A teacher agent generates adversarial scenarios to train and certify a safe student agent against overspending, phishing, policy violations, prompt injection, and permission abuse.

**Why it is strong**
- Extremely legible demo.
- Turns "safe agent" from marketing into pass/fail evidence.
- Nice fit for guardrails, delegation, budget control, and identity.

---

## 6) Vertical Apprentice Factory
**Current rank:** #6

**Pitch:**
Take the teacher/student mechanism and focus it on one specific role such as a frontend engineer, dentist-office assistant, or legal intake agent.

**Why it is strong**
- More believable than a generic platform claim.
- Better GTM story.
- Still proves the general mechanism.
- The official submission docs make it easier to be honest and legible about tools, scenarios, and receipts in one concrete lane.

**Strategic note**
This may be the best "Path B disguised as Path A" move: build a general engine, demo one sharp vertical.

---

## 7) Celo Field Agent Academy
**Current rank:** #7

**Pitch:**
Train mobile-first, trust-verified agents for real-world small businesses using stablecoins, identity proofs, and Celo distribution.

**Why it is interesting**
- Celo makes the identity + payment + mobile story unusually coherent.

---

## 8) Quiet Deal Desk
**Current rank:** #8

**Pitch:**
A private strategy/procurement/decision agent that compares options privately and only acts within bounded permissions.

**Why it is interesting**
- Strong privacy + trust story.
- Feels futuristic.

**Main risk**
Privacy + verifiable compute adds a lot of complexity quickly.

---

## 9) Agent Passport / Trust Pack
**Current rank:** #9

**Pitch:**
Portable identity, wallet, permissions, and attestations for deployable agents.

**Why it is interesting**
- Strong infra play.
- Many partner-track fits.

**Main risk**
Infra demos are respected but easy to forget.

---

## 10) Octant Judge Lab
**Current rank:** #10

**Pitch:**
An agent that evaluates grants or public goods using explicit rubrics, evidence gathering, and auditable scoring traces.

**Why it is interesting**
- Nicely aligned with the hackathon's own AI-judge framing.

**Main risk**
Less commercial and a bit narrower than the top concepts.

---

## Deep note on the current favorite: Agent Studio / Role Foundry

## Best version of the concept
The best form of the teacher/student idea is:

> A system for creating reliable role-specific agents through curated scenario training, hidden holdout evaluation, and budget-bounded autoresearch.

### Recommended demo flow
1. User defines a role.
2. User defines success criteria.
3. Teacher generates a scenario set.
4. User curates the scenario set.
5. Scenarios are split into:
   - public training set
   - hidden holdout set
6. Student iterates on:
   - `SOUL.md`
   - `IDENTITY.md`
   - policies
   - tool strategy
   - memory / behavioral scaffolding
7. Student self-tests on the public set.
8. Student submits to teacher.
9. Teacher evaluates on holdout.
10. Failures become the next public curriculum.
11. Repeat until budget or quality target is reached.

### Why this one currently feels best
- It makes evaluation non-trivial.
- It produces a visible improvement loop.
- It fits the current autoresearch zeitgeist.
- It can reuse agent identity / trust / wallet / marketplace primitives naturally.
- It naturally produces strong `conversationLog`, scorecards, and artifact history for submission.
- It has a clean marketplace future: train -> certify -> deploy -> hire.

### Main risks to watch
1. **Teacher leakage**
   The teacher cannot accidentally leak the holdout distribution.
2. **Prompt-only theater**
   Scenarios should ideally involve real tasks, tools, or policies, not just vibes-based chat judging.
3. **Overbuilding**
   Do not build a whole research platform. Build the minimum loop that proves the mechanism.

---

## Current recommendation

This section **supersedes** the older ranking above where it conflicts with the official-doc corrections.

If we had to choose today, the corrected shortlist is:
1. **Agent Studio / Role Foundry**
2. **Vertical Apprentice Factory**
3. **AutoFounder / Venture Autoresearch**

### My current preference
- **Best overall:** Agent Studio / Role Foundry
- **Best execution form:** Vertical Apprentice Factory (Role Foundry through one concrete lane)
- **Best fallback:** AutoFounder
- **Best finance-heavy alternative:** YieldOS, but only with a concrete **Lido** or **Zyfai** path

### Tactical recommendation
If deadline pressure is real, the strongest move is:
- build the **general Role Foundry mechanism**
- demo it with **one killer vertical**
- wire only the partner tracks that are genuinely load-bearing

That gives us both:
- a strong product story
- a believable execution scope
- cleaner `conversationLog`, metadata, and receipts for submission

---

## Source notes
- Internal ideation summaries from 2026-03-22 (LCM summaries including `sum_422fe4e09cb8279c` and `sum_2ef046d72326d160`)
- ZHC1 direction note: `memory/2026-03-18.md`
- Durable facts log: `life/areas/projects/synthesis-hackathon/items.json`
- Official Synthesis registration / participant skill: `https://synthesis.md/SKILL.md`
- Official Synthesis submission skill: `https://synthesis.md/submission/skill.md`
- Official prize catalog: `https://synthesis.devfolio.co/catalog/prizes.md` (+ pages 2 and 3)
