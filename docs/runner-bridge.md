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

## Autoresearch alpha public-loop slice

There is now a first honest **executable alpha loop** on top of the bridge:

```bash
python3 -m runner_bridge.autoresearch_alpha \
  --request runner_bridge/examples/autoresearch-alpha-public-loop.json
```

What it does:
- runs a **baseline teacher eval**
- derives a **candidate student prompt pack** from the public benchmark pack plus sanitized baseline failure themes
- runs a **candidate teacher eval** with `previous_iteration` injected from the actual baseline result
- emits a **better/equal/worse** comparison receipt
- enforces an **integrity gate** so the loop can claim a public-regression result, but not a sealed-eval result

Why the integrity gate matters:
- `benchmarks/public-pack-v1` is a **public benchmark pack**, not a sealed certification exam
- the current teacher-only families are explicitly marked `blocked_pending_rewrite`
- so the alpha loop may honestly say **better on the current public/unsealed alpha rail**
- it may **not** honestly say the repo has a fresh sealed holdout path yet

That blocker is explicit instead of buried.

A first real stored public-regression export from this lane is now committed under:
- `app/autoresearch-alpha.public-regression.export.json`
- `app/autoresearch-alpha.public-regression.request.json`

Those are public-safe copies of an actual `runner_bridge.autoresearch_alpha` execution on this branch. They remain **LocalReplayRunner / zero-secret replay** artifacts and do not upgrade the claim boundary beyond public-regression alpha execution with public-safe receipts.

## Local private-holdout extension

There is now one narrow step beyond the public rail.

If the request points `private_holdout_manifest` at a local-only holdout manifest and the teacher-eval stages reference those holdout episodes by id, `runner_bridge.autoresearch_alpha` will:
- hydrate `title`, `difficulty`, `teacher_prompt`, and `scoring_rubric` from the local manifest into `request.private.json`
- keep `request.json`, transcript receipts, and the student-facing artifact bundle free of teacher-only prompt text
- write `pre-run-manifest-commitment.json` before stage execution starts, recording only public-safe metadata about the manifest hash and run linkage
- optionally preserve a public-safe `pre_run_manifest_attestation` reference block in both the commitment artifact and `sealing_receipt` when the request supplies one
- pass the integrity gate as a **local private-holdout** run when both teacher-eval stages are backed by the private manifest
- still block **sealed certification** claims

That is intentionally narrow. The pre-run commitment receipt improves local auditability only; it is not external publication, third-party proof, or tamper-proofing. Any optional `pre_run_manifest_attestation` is reference metadata only: the bridge does not verify witness identity, signature validity, publication timing, or independence, and it does not unlock stronger claims automatically.

**Allowed now:** fresh hidden holdouts in a local private manifest, a real local private-holdout rerun, and receipts that keep teacher-only content out of tracked and student-visible artifacts.

**Still blocked:** sealed-eval claims, sealed certification, partner-ready evaluation, tamper-proofing, or any claim that an independent system sealed the holdouts.

## Repo-task-shaped student prompt pack

The candidate-student stage now builds a **repo-task-shaped prompt pack** from the selected public benchmark episodes. Each visible scenario carries a `repo_task_meta` block with the fields the episode author actually provided:

- `family_id` — which episode family this belongs to
- `mutation_budget` — how wide the student may edit (`narrow`, `medium`, `broad`)
- `constraints` — policy guardrails authored by the teacher
- `suggested_files` — targeted file paths for the task
- `artifacts_required` — what the student must leave behind
- `public_checks` — verifier-friendly assertions
- `tags` — episode classification

The student view also includes a top-level `repo_task_pack` summary:

```json
{
  "repo_task_pack": {
    "role_scope": "frontend-apprentice",
    "dataset_id": "public-benchmark-pack-v1",
    "dataset_version": "1.0.0",
    "episode_count": 3,
    "family_ids": ["rf.frontend-apprentice.public.score-deltas", "..."],
    "honesty_note": "Repo-task metadata is derived from the public benchmark pack. ...",
    "recommended_verifier_commands": [
      "python3 -m unittest tests/test_public_benchmark_pack_v1.py",
      "python3 -m unittest tests/test_milestone3_contract.py tests/test_milestone5_teacher_eval_loop.py",
      "python3 -m unittest tests/test_private_holdout_separation.py"
    ]
  }
}
```

When the benchmark pack's `execution_policy` includes `recommended_verifier_commands`, those commands are carried through into `repo_task_pack` so the student (or an automated runner) can run the same verification suite the benchmark author intended.

The candidate receipt at `receipts/candidate.json` also surfaces the `repo_task_pack` summary — including `recommended_verifier_commands` when present — so a reviewer can inspect what concrete repo task family the student was asked to do and which verifier commands apply.

**What is still not real:** this is still local replay / public-regression alpha. The `repo_task_meta` fields come from the public benchmark pack, not from a live task assignment system. The repo-task shape makes the prompt pack inspectable and less canned, but does not change the evaluation contract.

### Verifier contract (Step C eval-contract)

Every stage receipt now includes a `verifier_contract` block and the top-level alpha receipt includes a `verifier_gate` summary. These make the eval contract state-machine-readable:

- **`verifier_contract.required_commands`** — the verifier commands the benchmark pack specifies.
- **`verifier_contract.command_results`** — per-command execution status and exit code.
- **`verifier_contract.gate_status`** — one of `pass`, `fail`, `not_executed`, `no_commands`, or `incomplete`.
- **`verifier_gate.aggregate_status`** — rolled up across all stages.

In the local-replay alpha path, `gate_status` is always `not_executed` and every command result has `execution_status: "not_executed"` with `exit_code: null`. This is honest: the local-replay runner does not execute verifier commands. The gate becomes meaningful when a live-execution backend (for example a real `codex` adapter or a live-upgraded `claude_vibecosystem` runner) is wired.

The candidate receipt at `receipts/candidate.json` also includes a `verifier_gate` block with the same honesty contract.

### Backend provenance in artifact bundles and alpha receipts

When a run exposes backend provenance, the bridge now preserves that seam in public-safe audit surfaces:

- `artifact-bundle.json.execution_backend` — selected/observed backend id
- `artifact-bundle.json.execution_backend_contract` — backend mode / intended executor path / claim boundary when available
- `artifact-bundle.json.execution_honesty` — summarized non-execution or boundary status
- receipt-level `execution_backend` blocks (for example `receipts/candidate.json`)
- alpha-loop `sealing_receipt.execution_backend` — per-stage backend summary plus the current claim-boundary note

These are provenance / honesty surfaces only. They do **not** by themselves prove live execution, independent executor isolation, sealed evaluation, certification, tamper-proofing, or native Clawith parity.

## Task-packet → runtime bridge

The `runner_bridge.packet_runtime` module is the bridge from versioned curriculum task packets to executable runtime objects. It closes the gap between "the curriculum defines 20 tasks" and "a runner backend can pick one up and execute it."

### How it works

```text
Teacher authors frozen task packet (in public seed registry)
  → CLI: python3 -m runner_bridge.cli --packet A001
  → load_run_object("A001") validates against frozen contract
  → cross-references evaluation contract + role manifest
  → produces a PacketRunObject
  → .to_run_request() → RunRequest the bridge can execute
  → RunBridge.run() → materializes run-object.json + request.private.json
  → LocalReplayRunner (today) produces transcript + receipts
  → result.json includes machine-readable execution_honesty block
```

### Packet-driven CLI path

The CLI now supports loading a task packet directly by acceptance_test_id:

```bash
# Run a specific task packet end-to-end through the bridge
python3 -m runner_bridge.cli --packet A001

# With explicit run-id and artifacts directory
python3 -m runner_bridge.cli \
  --packet C001 \
  --run-id my-run-001 \
  --artifacts-root runtime/runs

# Select the contract-first claude_vibecosystem beta seam
python3 -m runner_bridge.cli \
  --packet A001 \
  --runner-backend claude_vibecosystem \
  --artifacts-root runtime/runs

# With control plane
python3 -m runner_bridge.cli \
  --packet A001 \
  --clawith-url http://localhost:3000 \
  --clawith-secret "$CLAWITH_SECRET"
```

The `--packet` flag and `--request` flag are alternatives. `--packet` loads from the frozen public seed registry by acceptance_test_id, builds a `PacketRunObject`, converts it to a `RunRequest`, and feeds it to the bridge. `--request` loads a pre-built request JSON as before.

`--runner-backend claude_vibecosystem` is the new contract-first beta seam. It selects a named backend, stamps that choice into `run-object.json`, carries a machine-readable `execution_backend_contract`, and routes execution to a tiny non-destructive adapter stub. In tests and local contract checks that stub records intent + claim boundary only: it does **not** invoke Claude Code, vibecosystem hooks, or the live Clawith/OpenClaw gateway. It does not claim sealed evaluation, tamper-proofing, independent executor isolation, or native Clawith parity.

### run-object.json — runtime artifact export

When a run is driven by a task packet (i.e. the request carries a `packet_runtime` block), the bridge materializes a `run-object.json` in the run directory. This is the concrete runtime artifact that proves the bridge consumed the versioned contract surface:

```text
runtime/runs/<run_id>/run-object.json
```

Contents:

| Field | Source | Purpose |
|-------|--------|---------|
| `run_id` | bridge-assigned | This run's identity |
| `packet_id` | task packet `task_id` | Stable task identity |
| `packet_version` | task packet `packet_version` | Version of the packet definition |
| `packet_content_hash` | SHA-256 of canonical JSON | Detect packet drift without version bump |
| `acceptance_test_id` | task packet `acceptance_test_id` | Human-readable test ref (A001–E004) |
| `role_id` | role manifest | Frozen role identity |
| `phase_index` | task packet | Which curriculum phase |
| `eval_contract_ref` | evaluation contract | Dimensions, weights, thresholds |
| `mutation_budget` | task packet | Max tracked files and net lines |
| `allowed_paths`, `blocked_paths` | task packet | Path constraints for the student workspace |
| `expected_checks` | task packet | Commands the student must run |
| `evidence_contract` | task packet | Required artifacts and provenance rules |
| `execution_status` | always `"not_started"` at creation | Honest: no claim of execution at construction time |
| `execution_backend` | `"pending"` by default; explicit backend id when selected | Honest backend naming without claiming execution |
| `execution_backend_contract` | present when a named backend is selected | Machine-readable backend mode, executor path, and claim boundary |
| `receipt_output_dir` | bridge | Where receipts will be written |
| `artifact_locations` | bridge | Paths to request.json, request.private.json, run-object.json, receipts/ |

### execution_honesty — machine-readable backend status

When `LocalReplayRunner` processes a packet-driven request, `result.json` includes an `execution_honesty` block that makes the non-execution status machine-readable:

```json
{
  "execution_honesty": {
    "backend": "LocalReplayRunner",
    "executes_commands": false,
    "executes_checks": false,
    "check_results": [
      {
        "id": "check-1",
        "command": "python3 -m pytest tests/...",
        "execution_status": "not_executed",
        "exit_code": null,
        "reason": "LocalReplayRunner does not execute packet commands"
      }
    ],
    "mutation_enforcement": "not_enforced",
    "path_constraint_enforcement": "not_enforced",
    "mutation_surface_audit": {
      "status": "unavailable",
      "source": { "kind": "unavailable" },
      "honesty_note": "No diffable git worktree metadata was provided in workspace_snapshot. This run cannot honestly claim mutation-surface compliance."
    },
    "mutation_surface_audit_path": "receipts/mutation-surface-audit.json",
    "honesty_note": "LocalReplayRunner is a zero-secret replay backend..."
  }
}
```

This makes it explicit that LocalReplayRunner does not execute task commands, enforce mutation budgets, or enforce path constraints. When a real worktree diff is available, the bridge can still audit the actual changed-file surface against the packet contract. When no diff exists, the receipt says so plainly instead of implying the surface passed.

When `--runner-backend claude_vibecosystem` is selected, `execution_honesty` still stays conservative: the backend reports `executes_commands: false`, `executes_checks: false`, `mode: "external_executor_beta"`, and a claim-boundary block that says native Clawith parity, sealed evaluation, tamper-proofing, and independent executor isolation are all **not claimed**. That beta seam is intentionally inspectable but non-destructive.

### PacketRunObject contents

Each run object is a frozen, self-contained snapshot:

| Field | Source | Purpose |
|-------|--------|---------|
| `packet_id` | task packet `task_id` | Stable task identity |
| `packet_version` | task packet `packet_version` | Version of the packet definition |
| `packet_content_hash` | SHA-256 of canonical JSON | Detect packet drift without version bump |
| `acceptance_test_id` | task packet `acceptance_test_id` | Human-readable test ref (A001–E004) |
| `role_id`, `role_name` | role manifest | Frozen role identity |
| `allowed_paths`, `blocked_paths` | task packet | Path constraints for the student workspace |
| `mutation_budget` | task packet | Max tracked files and net lines |
| `expected_checks` | task packet | Commands the student must run |
| `eval_contract_ref` | evaluation contract | Dimensions, weights, thresholds |
| `evidence_contract` | task packet | Required artifacts and provenance rules |
| `execution_status` | always `"not_started"` | Honest: no claim of execution at construction time |
| `execution_backend` | `"pending"` by default; explicit backend id when selected | Honest backend naming without implying work happened |
| `execution_backend_contract` | backend registry | Optional backend mode / claim-boundary snapshot for named seams |

### Usage

```python
from runner_bridge.backends import backend_contract_for_runner
from runner_bridge.packet_runtime import load_run_object

# Load by acceptance test id
obj = load_run_object(
    "C001",
    run_id="my-run-001",
    execution_backend="claude_vibecosystem",
    execution_backend_contract=backend_contract_for_runner("claude_vibecosystem"),
)

# Inspect contract constraints
print(obj.mutation_budget.tracked_files_max)          # 6
print(obj.eval_contract_ref.dimensions)               # frozen 5 dimensions
print(obj.execution_backend)                          # claude_vibecosystem
print(obj.execution_backend_contract["mode"])        # external_executor_beta

# Convert to a RunRequest for the bridge
request = obj.to_run_request(
    workspace_snapshot={"changed_files": ["app/run.html"]},
    cost_budget_usd=1.50,
)

# The request carries the full packet_runtime block in extras
print(request.extras["packet_runtime"]["acceptance_test_id"])  # "C001"
```

### Batch loading

```python
from runner_bridge.packet_runtime import load_all_run_objects

# Load all 20 public seed tasks as run objects
objects = load_all_run_objects()
for obj in objects:
    req = obj.to_run_request()
    # each req is ready for RunBridge.run()
```

### Honesty note

The run object describes the *input shape* — what the run should do, which constraints apply, and what evidence is required. It does **not** claim that execution has happened. `execution_status` starts as `"not_started"`. `execution_backend` stays `"pending"` unless an explicit named seam is selected, and `execution_backend_contract` only records the chosen backend's mode + claim boundary. The `execution_honesty` block in `result.json` makes the backend's actual capabilities machine-readable.

## Current bridge shape

```text
Operator / script
  → runner_bridge.cli
  → Clawith-compatible control plane
  → LocalReplayRunner (default today)
    or claude_vibecosystem (contract-first beta seam)
  → transcript.ndjson + artifact-bundle.json + result.json
```

Future adapters can slot into the same bridge command:
- live-upgraded `claude_vibecosystem`
- `codex`
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
- `receipts/audit-bundle.json` — machine-readable artifact index plus required-artifact validation, redaction checks, and lineage / benchmark-pack / episode traceability with honest availability flags
- `receipts/summary.md` — human-readable export for quick judge/operator inspection with explicit run metadata, benchmark input, mutation, teacher scorecard, and verdict sections

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

`artifact-bundle.json` and `result.json` now also include a small `provenance` block pointing at the receipt manifest, evidence index, audit bundle, summary export, and any baseline / candidate / evaluation receipt files for the run.

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

## What is still not done

- no native consumer OAuth in Clawith
- no claim that Clawith already ships these exact run-patch endpoints upstream
- no live `claude_vibecosystem` execution path yet beyond the contract-first beta seam / stub
- no full browser fan-out across live run storage yet; the UI only consumes configured read-only exports / receipts

That is fine. The slice is still useful because it proves one honest run lifecycle end to end, proves a narrow teacher evaluation + iteration loop without leaking holdout prompt text into student-facing artifacts, and now gives the browser a receipt-oriented live shell without pretending the whole native stack is done.
