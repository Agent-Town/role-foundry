# Spec 016 — `claude_vibecosystem` External-Executor Beta Seam

## Goal

Formalize the smallest honest `claude_vibecosystem` runner-backend surface for Role Foundry.

This spec is intentionally narrow. It makes backend naming, selection, provenance, and claim boundaries machine-readable for future alpha-loop integration. It does **not** claim sealed evaluation, tamper-proofing, independent executor isolation, certification, or native Clawith parity.

## Scope

This slice should:
- add a named `claude_vibecosystem` backend selection path to `runner_bridge.cli`
- let packet-driven runs stamp `execution_backend: "claude_vibecosystem"` into `run-object.json`
- carry a machine-readable `execution_backend_contract` block in the runtime/request surface
- provide a tiny non-destructive backend stub that records executor intent + honesty boundaries in `result.json`
- keep the current Clawith/OpenClaw/Claude proof lane framed as an **external-executor beta seam** only

## Required contract surface

### 1) CLI selection

The bridge CLI must accept:

```bash
python3 -m runner_bridge.cli --packet A001 --runner-backend claude_vibecosystem
```

That selection must route to a named backend entrypoint without requiring live network work in tests.

### 2) Run-object visibility

When the backend is explicitly selected, `run-object.json` must include:
- `execution_status: "not_started"`
- `execution_backend: "claude_vibecosystem"`
- `execution_backend_contract` with at least:
  - backend id / version
  - `mode: "external_executor_beta"`
  - executor shape (`Claude Code` + vibecosystem agent selection)
  - claim-boundary fields showing stronger claims remain blocked

### 3) Result honesty surface

The backend stub must emit `execution_honesty` that says, in machine-readable form:
- this is the `claude_vibecosystem` backend
- commands/checks were **not executed** in this stubbed test path
- the seam records external-executor intent only
- native Clawith parity is **not claimed**
- sealed evaluation is **not claimed**
- tamper-proofing is **not claimed**
- independent executor isolation is **not claimed**

### 4) Artifact inspectability

The backend stub should leave a transcript/artifact bundle/result trio so reviewers can inspect:
- which backend was selected
- which executor path would be used later
- what honesty boundary applies today

## Non-goals

- live Claude Code execution in CI/tests
- touching private holdout content
- broad `runner_bridge` redesign
- claiming executor isolation that is not actually implemented
- claiming native Clawith model-pool parity

## Done when

- Spec 016 is in the repo
- `runner_bridge.cli` supports `--runner-backend claude_vibecosystem`
- packet-driven runs can materialize `execution_backend_contract`
- a tiny backend stub exists at `runner_bridge.backends.claude_vibecosystem`
- tests pin the honesty boundary and backend-selection surface
- docs explain that this is an external-executor beta seam, not a sealed/live parity claim
