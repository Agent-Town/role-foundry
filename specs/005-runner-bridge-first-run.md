# Spec 005 — Runner Bridge + First Live Run

## Intent

Prove the fast hackathon path: Clawith manages state while an external runner executes the actual model-backed work.

## Requirements

1. The runner adapter must accept:
   - `run_id`
   - `agent_role`
   - `scenario_set_id`
   - `workspace_snapshot`
   - `time_budget`
   - `cost_budget`
2. The adapter must return:
   - status
   - transcript path
   - artifact bundle path
   - optional scorecard
   - machine score
3. One run must travel through lifecycle states honestly.
4. Demo mode must not require any secrets.

## Acceptance criteria

- One adapter works end-to-end
- Transcript evidence is persisted
- Artifact bundle can be inspected
- Failure is represented honestly, not hidden

## Done when

Role Foundry can show one real run without pretending Clawith natively owns consumer subscription auth.