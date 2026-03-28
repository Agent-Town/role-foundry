# Runner Bridge — Hackathon Fast Path

## The problem

Role Foundry needs to dispatch runs without lying about auth or pretending Clawith magically speaks consumer subscriptions.

Two things are true at once:
1. **Clawith is the control plane** for role/run state.
2. **Actual execution can live outside Clawith** behind a narrow machine-to-machine bridge.

That is the hackathon-fast, honest path.

## The implemented Milestone 4 slice

The repo now ships one working bridge path:

```text
python3 -m runner_bridge.cli
  → validates the run request contract
  → marks the run as running
  → executes one external adapter
  → persists transcript + artifact bundle under runtime/runs/<run_id>/
  → patches final status back to the control plane
```

The first adapter is **LocalReplayRunner**.

That is deliberate:
- it is **zero-secret**
- it is **portable**
- it proves the lifecycle and storage contract without claiming Claude/Codex wiring that is not finished yet
- it gives us a local/mockable path when a real Clawith image or provider credentials are unavailable

This is not consumer OAuth. It is not pretending Clawith natively owns a Claude subscription. It is a narrow bridge.

## The implemented Milestone 5 extension

The same bridge now carries one honest teacher-evaluation slice.

If a request includes an optional `teacher_evaluation` payload, `LocalReplayRunner` will:
- keep the **student view** limited to public curriculum only
- keep sealed holdout prompt text out of judge-facing artifact files
- emit a **teacher scorecard** with per-scenario notes plus aggregate score
- collapse failed holdouts into **public curriculum themes** instead of leaking hidden prompts
- record **iteration history** with score deltas versus the prior run

The important line: the teacher can know more than the student without the repo leaking the sealed exam into the student-facing bundle.

## Task-packet → runtime bridge

The `runner_bridge.packet_runtime` module is the narrow bridge from the frozen Frontend/Product Engineer curriculum contracts to executable runtime objects.

What is real now:
- `python3 -m runner_bridge.cli --packet A001` loads a frozen task packet by acceptance-test id
- the bridge materializes `run-object.json` alongside the normal request / receipt files
- `result.json` includes a machine-readable `execution_honesty` block

What is **not** claimed:
- `LocalReplayRunner` does **not** execute packet commands
- mutation budgets and path constraints can be audited against declared `workspace_snapshot` diff evidence, but the backend does **not** independently compute diffs or prove live enforcement
- packet-driven runs are an honest contract surface for execution, not proof that live execution is complete

A packet-driven run now follows this shape:

```text
Teacher authors frozen task packet
  → python3 -m runner_bridge.cli --packet A001
  → runner_bridge.packet_runtime validates packet + role + eval contract
  → bridge writes runtime/runs/<run_id>/run-object.json
  → LocalReplayRunner writes transcript + artifacts
  → result.json records execution_honesty truthfully
```

The generated `run-object.json` freezes the packet id/version/hash, role id, allowed and blocked paths, mutation budget, expected checks, evidence contract, and receipt locations for that run.
## Current bridge shape

```text
Operator / script
  → runner_bridge.cli
  → Clawith-compatible control plane
  → LocalReplayRunner (today)
  → transcript.ndjson + artifact-bundle.json + result.json
```

Future adapters can slot into the same bridge command:
- ClaudeVibeRunner
- CodexRunner
- deterministic verifier scripts

## Request contract

Each run request must include:

```json
{
  "run_id": "run-live-001",
  "agent_role": "student",
  "scenario_set_id": "public-curriculum-v1",
  "workspace_snapshot": {},
  "time_budget": { "seconds": 60 },
  "cost_budget": { "usd": 1.5 }
}
```

Those are the required Milestone 4 fields:
- `run_id`
- `agent_role`
- `scenario_set_id`
- `workspace_snapshot`
- `time_budget`
- `cost_budget`

### Optional teacher evaluation payload

Milestone 5 adds one optional extension:

```json
{
  "teacher_evaluation": {
    "teacher": { "name": "Robin + Neo", "agent_role": "teacher" },
    "student": { "name": "Frontend Apprentice", "agent_role": "student" },
    "previous_iteration": {
      "run_id": "run-eval-001",
      "aggregate_score": { "passed": 2, "total": 5, "pass_rate": 0.4 }
    },
    "scenarios": [
      {
        "id": "t4",
        "type": "training",
        "student_prompt": "Leave a proof bundle",
        "passed": true,
        "score": 1.0,
        "teacher_notes": "Receipts are clear now."
      },
      {
        "id": "h2",
        "type": "holdout",
        "holdout_prompt": "Judge-only hidden prompt text",
        "passed": false,
        "score": 0.6,
        "teacher_notes": "Still too close to leaking the exam.",
        "public_failure_theme": "Explain evaluation integrity without leaking the exam",
        "public_failure_summary": "Teach the public lesson, not the hidden prompt."
      }
    ]
  }
}
```

The backend may receive the raw teacher payload, but the artifact directory keeps a redacted student-safe request view.

## Result contract

Each adapter must leave a `result.json` that the bridge can normalize into:

```json
{
  "status": "completed",
  "transcript_path": "transcript.ndjson",
  "artifact_bundle_path": "artifact-bundle.json",
  "machine_score": 0.8,
  "scorecard": {}
}
```

Allowed statuses are:
- `completed`
- `failed`
- `timeout`

Failure is first-class. A failed run still needs receipts.

### Teacher scorecard shape

When `teacher_evaluation` is present, the scorecard now carries:
- teacher identity and `agent_role: "teacher"`
- student identity and `agent_role: "student"`
- aggregate score (`passed`, `total`, `pass_rate`, `average_score`)
- per-scenario notes
- public curriculum themes derived from failed holdouts
- iteration history with score deltas

That is the Milestone 5 storage contract.

### Additive receipt provenance exports

The bridge now writes one extra receipt-provenance layer on top of the existing run outputs.

Important: this does **not** change the teacher judgment semantics.
It just makes the existing baseline / candidate / evaluation receipts easier to inspect and carry around.

The extra files are:
- `receipts/manifest.json` — artifact inventory with visibility labels, file hashes, and canonical receipt paths
- `receipts/candidate.json` — current-run receipt anchored to the workspace snapshot and student-visible prompt pack
- `receipts/baseline.json` — prior-run aggregate receipt when `previous_iteration` exists
- `receipts/evaluation.json` — teacher score/export receipt when `teacher_evaluation` ran
- `receipts/evidence-index.json` — evidence map linking receipts back to transcript lines, artifact JSON pointers, and private source records where needed
- `receipts/audit-bundle.json` — machine-readable audit bundle with artifact validation, redaction audit, traceability, and human-audit sections
- `receipts/summary.md` — human-readable export for quick judge/operator inspection; includes audit-bundle headings for the five human-audit sections

Private source artifacts may still be referenced in the evidence index, but only by path + pointer.
The public provenance files do not quote sealed holdout prompt text.

## Control-plane patch contract

For this milestone we keep the control-plane contract narrow and mockable.

The bridge sends:

### Run starts

`PATCH /api/runs/{run_id}`

```json
{
  "status": "running",
  "started_at": "2026-03-22T08:00:00Z",
  "agent_role": "student",
  "scenario_set_id": "public-curriculum-v1"
}
```

### Run finishes

`PATCH /api/runs/{run_id}`

```json
{
  "status": "completed",
  "finished_at": "2026-03-22T08:00:12Z",
  "transcript_path": "/abs/path/runtime/runs/run-live-001/transcript.ndjson",
  "artifact_bundle_path": "/abs/path/runtime/runs/run-live-001/artifact-bundle.json",
  "machine_score": 0.8,
  "scorecard": {}
}
```

If the adapter fails, the same endpoint is patched with `status: "failed"` (or `timeout`) plus an `error` field.

Important: this is the **bridge-side contract** Role Foundry can target today. It is intentionally small so it can be implemented against a fake server in tests or shimmed onto a real Clawith instance without inventing fake upstream capabilities.

## Artifact layout

By default the bridge writes to:

```text
runtime/runs/<run_id>/
  request.json
  request.private.json
  stdout.log
  stderr.log
  transcript.ndjson
  artifact-bundle.json
  result.json
  receipts/
    manifest.json
    candidate.json
    baseline.json      # when previous_iteration exists
    evaluation.json    # when teacher_evaluation runs
    evidence-index.json
    audit-bundle.json
    summary.md
```

`request.json` is the redacted artifact copy.

`request.private.json` is the raw backend input. That split is what keeps holdout prompt text out of the student-facing bundle while still letting the teacher side evaluate the run.

`artifact-bundle.json` and `result.json` now also include a small `provenance` block pointing at the receipt manifest, evidence index, summary export, and any baseline / candidate / evaluation receipt files for the run.

## First live run

Against a Clawith-compatible endpoint:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Teacher evaluation demo:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/teacher-eval-loop.json \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

Without a control plane, to exercise the local receipts path only:

```bash
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json
```

The second command is not a claim that Clawith is running. It is just the fastest zero-secret way to verify the transcript/artifact contract locally.

## Autoresearch alpha — public-regression loop

The `runner_bridge.autoresearch_alpha` module implements a real three-stage public-regression loop that executes each stage as a separate run through RunBridge.

### Three stages

| # | Stage | What it does | RunBridge call? |
|---|-------|-------------|-----------------|
| 1 | `baseline-eval` | Teacher evaluation of the baseline state | Yes — full run with `teacher_evaluation` |
| 2 | `candidate-student` | Student consumes the public benchmark prompt pack only (no teacher evaluation) | Yes — run with `student_prompt_pack` extra only |
| 3 | `candidate-teacher-eval` | Teacher evaluation of the candidate, with `previous_iteration` injected from the **real** baseline aggregate score | Yes — full run with `teacher_evaluation` |

Each stage gets its own run directory, its own `request.json` / `result.json` / `transcript.ndjson` / `artifact-bundle.json`, and its own provenance receipts.

### CLI entrypoint

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request runner_bridge/examples/autoresearch-alpha-public-loop.json \
  --artifacts-root runtime/runs
```

### Request shape

The request JSON follows a stage-config shape:

```json
{
  "run_id_prefix": "autoresearch-alpha-example",
  "public_benchmark_pack": "benchmarks/public-pack-v1/benchmark-pack.json",
  "family_registry": "benchmarks/public-pack-v1/episode-family-registry.json",
  "integrity_policy": { "public_regression": "required", "sealed_eval": "blocked" },
  "comparison_policy": { "metric": "pass_rate", "direction": "higher_is_better" },
  "stages": {
    "baseline-eval": { "request": { "teacher_evaluation": { ... } } },
    "candidate-student": { "request": { "prompt_pack_episode_ids": [...] } },
    "candidate-teacher-eval": { "request": { "teacher_evaluation": { ... } } }
  }
}
```

### Artifact outputs

```text
artifacts_root/
  autoresearch-alpha.json               # top-level receipt
  autoresearch-alpha.request.json       # copy of the request
  <prefix>.run-record-history.json      # per-stage lifecycle (queued → running → completed)
  <prefix>-baseline-eval/               # stage 1 run dir
  <prefix>-candidate-student/           # stage 2 run dir
  <prefix>-candidate-teacher-eval/      # stage 3 run dir
```

### Honest blocked claims

The receipt surfaces explicit `blocked_criteria` and `phase_c_acceptance`:

- **C003** (live execution backend) — blocked; LocalReplayRunner is a deterministic shim
- **C007** (sealed eval / certification) — blocked; public-regression lane only

The `integrity_gate` reports `public_regression: pass|fail` but honestly marks `sealed_eval: blocked` and `certification: blocked`.

This loop does not claim sealed-holdout coverage or live execution. Mutation-surface auditing is available when declared diff evidence is present; otherwise it stays honestly blocked. Verdict stability still remains blocked.

## What is still not done

- no native consumer OAuth in Clawith
- no claim that Clawith already ships these exact run-patch endpoints upstream
- no ClaudeVibeRunner wired yet
- no full browser fan-out across live run storage yet; the UI only consumes configured read-only exports / receipts

That is fine. The slice is still useful because it proves one honest run lifecycle end to end, proves a narrow teacher evaluation + iteration loop without leaking holdout prompt text into student-facing artifacts, and now gives the browser a receipt-oriented live shell without pretending the whole native stack is done.
