# Submission Proof Checklist

_For judges inspecting the Role Foundry hackathon submission._

This checklist maps every claim to verifiable repo evidence. Items marked with a test name have an automated check in `tests/`.

---

## Repo structure and demo

| # | Claim | How to verify | Test |
|---|-------|---------------|------|
| 1 | Demo runs with `docker compose up` | Run it; browse `localhost:8080` | `test_demo_contract.py` |
| 2 | Demo pages exist (index, scenarios, run, scorecard) | Check `app/` directory | `test_required_pages_exist` |
| 3 | Demo data shows Frontend Apprentice vertical | Open `app/data.js`, look for role name | `test_frontend_apprentice_seed_role_exists` |
| 4 | Public curriculum and sealed holdouts are split | Count training vs holdout in `data.js` | `test_scenario_split_is_preserved` |
| 5 | Score deltas and iteration history are visible | Check `data.js` for run-001, run-002, iterations | `test_multiple_runs_and_iteration_history_exist` |
| 6 | Proof bundle shown on run page | Open `app/run.html` | `test_apprentice_vertical_surfaces_exist` |

## Specs and milestones

| # | Claim | How to verify | Test |
|---|-------|---------------|------|
| 7 | Every milestone has a written spec | Check `specs/001`–`007` | `test_specs_exist_for_all_milestones` |
| 8 | Milestones 1–4 are marked done | Read `docs/milestones.md` | `test_milestone_status_honesty` |
| 9 | Milestone 5–6 are not falsely claimed as done | Same file | `test_milestone_status_honesty` |

## Clawith integration (Milestone 3)

| # | Claim | How to verify | Test |
|---|-------|---------------|------|
| 10 | Clawith service is profile-gated in compose | Read `docker-compose.yml` | `test_clawith_service_is_profile_gated` |
| 11 | Clawith image comes from env var, not hardcoded | Check compose for `CLAWITH_IMAGE` | `test_clawith_image_is_configurable` |
| 12 | Seed data has correct role and scenario counts | Read `seed/role-foundry-apprentice.json` | `test_seed_has_*` |
| 13 | Bootstrap validates without a live Clawith | Run `python seed/bootstrap.py --validate` | `test_bootstrap_validate_passes` |
| 14 | Holdout titles do not leak into training payload | Automated check | `test_student_facing_payload_excludes_holdouts` |

## Runner bridge (Milestone 4)

| # | Claim | How to verify | Test |
|---|-------|---------------|------|
| 15 | Runner bridge CLI exists | `python3 -m runner_bridge.cli --help` or check `runner_bridge/` | `test_example_request_exists_and_matches_required_contract` |
| 16 | Successful run produces transcript + artifacts | Run the test; check artifact directory | `test_successful_run_transitions_to_completed_and_persists_artifacts` |
| 17 | Failed run still persists receipts | Run the test | `test_failed_run_transitions_to_failed_and_keeps_receipts` |
| 18 | Invalid requests fail before execution | Run the test | `test_invalid_request_fails_before_backend_execution` |
| 19 | Clawith PATCH contract is correct | Fake-server test verifies status sequence and auth | same as #16 |

## Documentation honesty

| # | Claim | How to verify | Test |
|---|-------|---------------|------|
| 20 | Conversation log covers M1–M4 | Read `docs/conversation-log.md` | `test_conversation_log_covers_landed_milestones` |
| 21 | README explains demo vs live mode | Read README | `test_readme_explains_demo_vs_live_mode` |
| 22 | What-is-stubbed section is honest | README lists what is NOT wired | visual check |
| 23 | No fake live integrations claimed | Grep for OAuth/Privy/fake in README | visual check |

## What is NOT claimed

- Milestone 5 (teacher evaluation loop) is queued, not landed on this branch
- Milestone 6 (partner wiring) is queued
- No Claude/Codex runner adapter — only `LocalReplayRunner`
- Web UI serves demo data, not live Clawith state
- No consumer OAuth, no Privy, no onchain artifacts yet

---

## Quick judge workflow

```bash
# 1. Run all contract tests (no Docker needed)
python3 -m pytest tests/ -v

# 2. Start the demo
docker compose up
open http://localhost:8080

# 3. Inspect the build story
cat docs/conversation-log.md
cat docs/milestones.md

# 4. Check runner bridge locally (no secrets needed)
python3 -m runner_bridge.cli \
  --request runner_bridge/examples/first-live-run.json
```
