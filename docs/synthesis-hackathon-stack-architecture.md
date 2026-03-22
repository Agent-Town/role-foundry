# Synthesis Hackathon Stack Architecture

_Last updated: 2026-03-22_

## Why this document exists

This note captures the architecture decision behind the current hackathon direction.

The key idea is **fractal reuse**:
- we use one layered agent stack to build the hackathon project
- then the hackathon project itself uses the same stack to run teacher/student/evaluator loops
- each teacher or student test run is itself an agent run with artifacts, logs, scores, and budgets

This is the machine layer that should remain reusable after the hackathon.

---

## Decision summary

### Chosen default
Use **one Clawith instance per environment** as the control plane.

Do **not** start with multiple nested or layered Clawith instances.

### Why
Nested Clawith instances sound elegant and become operational sludge:
- duplicated schedulers
- duplicated memory systems
- blurred source of truth
- harder debugging
- harder isolation
- worse observability
- more risk of evaluation contamination and holdout leakage

If we later go multi-instance, it should be for one of only three reasons:
1. environment separation (`dev`, `staging`, `prod`)
2. hard isolation for untrusted workloads
3. scale boundaries for worker capacity

Not because recursion feels philosophically neat.

---

## Layered stack

## Layer 0 — Human orchestration
**Robin + Neo** are the top-level orchestrators.

Role split:
- Robin sets direction, constraints, goals, and taste
- Neo helps design the architecture, manage runs, review outputs, and keep the system coherent

This is not just advisory. Neo is part of the operating loop.

---

## Layer 1 — Control plane
### Clawith
Use Clawith as the **machine/control layer**.

Clawith is the right home for:
- persistent agent identity
- long-term memory
- multi-agent coordination
- workspaces
- scheduling / triggers
- approvals
- logs / reflections
- run registry
- artifact attachments

For this hackathon, Clawith should own the canonical truth for:
- which agents exist
- which runs are active
- which artifacts belong to which run
- which scores were assigned
- which approvals or failures occurred

### Important note on official submission honesty
Synthesis submission docs require honest harness / tool metadata.

Clawith is based on OpenClaw, but we should only claim `openclaw` as the harness where that is genuinely accurate and defensible. If parts of the system are better described as Clawith-derived or custom orchestration on top of OpenClaw, the final metadata should say so honestly.

---

## Layer 2 — Execution backends
The control plane should dispatch to explicit runner adapters.

### 1) Claude + vibecosystem runner
Use vibecosystem as an **implementation backend**, not the core system architecture.

What it is good for:
- task decomposition
- multi-role coding work
- implementation swarms
- spec-to-task expansion
- rapid code generation under Claude subscriptions

What it should **not** own:
- global system truth
- evaluation truth
- holdout integrity
- final audit record

### 2) Codex runner
Use Codex as an independent backend for:
- second-opinion implementation
- critique
- review
- evaluator / critic roles
- patch-focused execution

### Why both matter
Do not let the same model family always build and always judge.

Recommended bias:
- **student / builder** = Claude + vibecosystem
- **teacher / critic / auditor** = Codex
- deterministic tests first, model judgment second

That reduces correlated failure and self-congratulatory grading.

---

## Layer 3 — Visualization and human presence
### Claw3D
Use Claw3D as the **human-facing visualization layer**.

Strong use cases:
- wall of live experiments
- agent presence / visibility
- jump into a run
- monitoring parallel work
- playback of important runs
- making the system feel legible instead of hidden behind logs

### Boundary rule
Claw3D should be a viewer/operator surface, not the source of truth.

It should not own:
- scoring truth
- evaluation truth
- secrets
- submission truth
- artifact authority

### Integration caution
Claw3D is built around an OpenClaw Gateway model.
Clawith is a different platform/runtime.

So the assumption "Claw3D will directly visualize Clawith agents" is **not** safe by default.

The correct approach is to introduce a normalized event and state boundary.

---

## Core architectural pattern

```text
Robin + Neo
  ↓
Clawith Control Plane
  - agent registry
  - run planner
  - scenario store
  - holdout vault
  - evaluation store
  - artifact index
  - approvals / audit
  ↓
Runner Adapters
  - ClaudeVibeRunner
  - CodexRunner
  - optional direct OpenClaw runner later
  ↓
Run Artifacts
  - transcripts
  - logs
  - screenshots
  - scorecards
  - code refs
  - output bundles
  ↓
Visualization Layer
  - Claw3D wall
  - playback
  - operator monitoring
```

The system should layer **responsibilities**, not layer runtime daemons on top of each other.

---

## First-class run object
Every teacher, student, evaluator, or builder run should be represented as a first-class run record.

Minimum fields:
- `run_id`
- `agent_role` (`teacher`, `student`, `critic`, `builder`, `verifier`)
- `agent_template_version`
- `runner_backend` (`claude_vibecosystem`, `codex`, etc.)
- `workspace_snapshot`
- `scenario_set_id`
- `holdout_access` (`none`, `teacher-only`)
- `time_budget`
- `cost_budget`
- `status`
- `transcript_path`
- `artifact_bundle_path`
- `scorecard`
- `machine_score`
- `created_at`, `started_at`, `finished_at`

This is the base unit for:
- evaluation
- observability
- replay
- auditability
- submission proof

---

## Isolation rules
This part is non-negotiable if the teacher/student idea is real.

### Per-run isolation
Each run should get:
- isolated workspace / worktree
- isolated HOME or equivalent config dir
- isolated memory / rules store where applicable
- isolated logs
- isolated artifact bundle

### Why this matters
Without isolation, we risk:
- hidden holdout leakage
- cross-project contamination
- false performance gains
- non-reproducible scoring
- confusing artifacts

### Special warning for vibecosystem
vibecosystem's self-learning is powerful and dangerous.

If it shares rules or memory across unrelated runs, the benchmark becomes fake.

Therefore, when vibecosystem is used inside evaluation loops, we should control:
- what learning persists
- what remains local to one run
- when any learned rule is promoted beyond a single run

Default posture: **isolated by default, promote explicitly.**

---

## Evaluation architecture
Evaluation should stay separate from execution.

### Score family 1 — outcome score
Measures whether the agent solved the task.
Examples:
- scenario pass/fail
- rubric score
- hidden holdout performance
- artifact quality
- policy correctness

### Score family 2 — machine score
Measures whether the run itself behaved well as a machine process.
Examples:
- stayed within time budget
- stayed within cost budget
- produced usable logs
- attached required artifacts
- no sandbox violations
- clean completion state
- reproducible output bundle

This is important because the runtime stack itself is part of what we are building and should be evaluatable.

---

## Event schema for Claw3D and ops surfaces
Before building the 3D wall, define a small normalized event stream.

Suggested event types:
- `run.created`
- `run.started`
- `run.blocked`
- `run.tool_active`
- `run.artifact_added`
- `run.score_updated`
- `run.review_requested`
- `run.failed`
- `run.completed`

Suggested state slices:
- agent identity
- run identity
- current phase
- last event time
- active tool / active task
- score summary
- artifact count
- warning / blocked state

Claw3D can then visualize the system without becoming tightly coupled to internal orchestration details.

---

## Recommended backend role split

### Claude + vibecosystem
Best for:
- broad implementation work
- complex decomposition
- multi-step feature execution
- swarming on build tasks

### Codex
Best for:
- critical review
- rubric-based critique
- independent patching
- evaluator or adversarial checker roles

### Operating pattern
A good first operating split is:
- Teacher planner: Claude or Neo-assisted orchestration
- Student builder: Claude + vibecosystem
- Independent critic: Codex
- Deterministic verifier: tests / scripts / scenario checks

---

## Recommended build sequence

## Phase 1 — Prove the kernel
Build the minimum viable system:
- one Clawith control plane
- one Claude/vibecosystem runner adapter
- one Codex runner adapter
- one teacher run
- one student run
- one scorecard
- one artifact bundle

Do **not** start with full 3D ambition.

## Phase 2 — Hard isolation
Add:
- per-run workspace snapshots
- holdout vault mechanics
- stricter memory segregation
- clean runner contracts

## Phase 3 — Visualization
Add:
- experiment wall
- live run cards
- run playback
- click-to-jump operator view

## Phase 4 — Productization
Use the same architecture to build the actual hackathon product:
- Role Foundry / Agent Studio
- Vertical Apprentice Factory
- AutoFounder variants if still relevant

This is the fractal move done properly.

---

## Hackathon-specific implications

### Why this stack is attractive for the hackathon
- It produces real logs and artifacts.
- It naturally supports `conversationLog`.
- It can create strong receipts and score traces.
- It keeps the teacher/student loop grounded in real runs.
- It makes the demo legible for judges.

### What to avoid
- nested runtime cleverness instead of shipping
- shared hidden state between evaluation runs
- vague harness claims in submission metadata
- building the entire 3D world before the kernel works

### Current default strategy fit
This architecture most naturally supports:
1. **Role Foundry / Agent Studio**
2. **Vertical Apprentice Factory**
3. **AutoFounder** as a fallback or sibling mode

---

## Canonical architecture decision

For the current hackathon build, the default architecture is:

- **Clawith** = control plane / machine layer
- **vibecosystem** = Claude execution backend for implementation-heavy agent runs
- **Codex** = independent builder / critic / evaluator backend
- **Claw3D** = human-facing visualization and monitoring layer
- **Neo + Robin** = orchestration and policy layer

And the topology decision is:

> **One Clawith instance per environment. Many isolated run sandboxes. No nested Clawith stack as the default.**

---

## LLM and runtime configuration by component

This section captures the practical configuration reality of each tool in the proposed stack.

### Clawith
Clawith is the only layer of the three that behaves like a true control-plane LLM manager.

What the repo does:
- stores LLM definitions in a database model pool (`llm_models`)
- lets native agents reference `primary_model_id` and optional `fallback_model_id`
- uses those model assignments across chat, tasks, heartbeats, schedules, and reminders
- supports multiple providers through a unified client abstraction

Implications:
- Clawith expects API-level provider credentials, not just consumer app subscriptions
- provider config is not mainly driven by `.env`; it is primarily created as model records in the app
- OpenClaw-linked agents are different: their model / personality / skills are configured on the OpenClaw side, not inside Clawith

Practical setup shape:
- add model entries for the providers we actually want available to Clawith-native agents
- assign them per agent as primary / fallback
- use Clawith-native LLMs mainly for orchestration, teacher, planner, critic, and management roles

### vibecosystem
vibecosystem is **not** its own LLM runtime.
It is a Claude Code plugin/ecosystem.

What the repo does:
- installs agents, skills, hooks, and rules into `~/.claude/`
- declares agent model preferences in markdown frontmatter like `model: sonnet` or `model: opus`
- relies on Claude Code itself as the runtime
- describes itself explicitly as having no custom model layer and no custom API

Implications:
- vibecosystem inherits Claude Code authentication and model access
- there is no separate vibecosystem model pool to configure like Clawith has
- if Claude Code is authenticated and usable, vibecosystem works on top of it
- if Claude Code is not installed / authenticated, vibecosystem has nothing to stand on
- Codex is not a native vibecosystem backend; Codex should remain a separate runner adapter in our architecture

Optional env/config surfaces found in the repo are about memory and observability, not core model access:
- `CONTINUOUS_CLAUDE_DB_URL` for PostgreSQL memory
- `VOYAGE_API_KEY` for optional embeddings
- `BRAINTRUST_API_KEY` for optional tracing

Practical setup shape:
- install Claude Code and authenticate it first
- install vibecosystem into an isolated `~/.claude` home for each run sandbox when evaluation integrity matters
- treat its self-learning and cross-project memory as opt-in / promotable state, not default shared truth

### Claw3D
Claw3D is **not** a general-purpose LLM runtime either.
It is a Studio / proxy / visualization layer for OpenClaw.

What the repo does:
- connects to an existing OpenClaw Gateway using a gateway URL and token
- loads gateway config and model catalog from the upstream gateway
- filters or presents model choices based on what the gateway exposes
- optionally uses OpenClaw media/audio capability for transcription
- optionally uses ElevenLabs for voice reply features

Implications:
- Claw3D does not own the main LLM configuration for agents
- the actual model setup lives in the connected OpenClaw gateway
- the key thing to configure in Claw3D is connectivity, not model credentials

Main configuration surfaces:
- `NEXT_PUBLIC_GATEWAY_URL`
- Studio gateway token / settings
- optional `STUDIO_ACCESS_TOKEN` for protecting a public Studio host
- optional `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID` for voice replies

Practical setup shape:
- point Claw3D at a working OpenClaw gateway
- let it consume models from the gateway rather than inventing another model layer
- if we adapt Claw3D to visualize Clawith-controlled runs, do that through an event/state adapter, not by pretending Claw3D is the control plane

### Clean mental model
- **Clawith** = manages model pool for native agents
- **vibecosystem** = piggybacks on Claude Code's model access
- **Claw3D** = piggybacks on OpenClaw gateway model/runtime state
- **Codex** = separate runner in our architecture, not native to vibecosystem or Claw3D

### What this means for our stack
The clean split remains:
- Clawith for orchestration and canonical run state
- vibecosystem for Claude-based implementation runs
- Codex for independent critique / build / evaluation runs
- Claw3D for monitoring and live visibility

That split matches the actual repos better than trying to force one universal model-config story across all three.

---

## Related docs
- `docs/synthesis-hackathon-ideation.md`
- `memory/2026-03-18.md`
- `life/areas/projects/synthesis-hackathon/items.json`
