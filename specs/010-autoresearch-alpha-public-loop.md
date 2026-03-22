# Spec 010 — Autoresearch Alpha Public Loop

## Goal

Land the first honest executable **baseline → candidate → teacher-eval → better/equal/worse** loop without pretending the repo already has a truly sealed holdout path.

## Scope

This slice is deliberately narrow:
- orchestrate the current `runner_bridge` lifecycle into a three-stage alpha loop
- use the **public benchmark pack** for the candidate lifecycle
- carry forward only **sanitized public failure themes** into the student prompt pack
- produce a comparison receipt that says **better**, **equal**, or **worse**
- enforce an **integrity gate** that blocks sealed-eval claims when the holdout path is still public / disclosed

## Required stages

1. **Baseline lifecycle**
   - run a baseline teacher evaluation
   - persist transcript, artifact bundle, result, and receipt provenance
2. **Candidate lifecycle**
   - run a student stage from a public-safe prompt pack only
   - include visible scenarios, sanitized public failure themes, and sealed-holdout count
   - do not emit a fake teacher verdict for the student-only stage
3. **Teacher eval completeness**
   - run a candidate teacher evaluation against the current teacher-side scenarios
   - inject `previous_iteration` from the actual baseline result
   - emit per-scenario notes, aggregate score, iteration delta, and public curriculum themes
4. **Comparison verdict completeness**
   - compare the baseline scored run with the candidate scored run
   - emit a concrete `better` / `equal` / `worse` verdict plus the deciding axis and score deltas
5. **Integrity gate enforcement**
   - if the caller requires a sealed holdout path, block execution explicitly
   - otherwise allow a public-regression loop, but record that sealed-eval claims remain blocked
6. **Artifact coverage**
   - each stage must leave request, transcript, artifact bundle, result, and receipt-manifest outputs
   - teacher-eval stages must also leave evaluation receipts
   - the candidate teacher-eval stage must leave a baseline receipt

## Non-goals

- inventing a sealed certification path
- claiming fresh hidden-eval integrity while holdout families remain repo-visible
- partner-track work
- browser fan-out over runtime artifact storage
- broad runner-contract churn

## Done when

Role Foundry can honestly say:
- the alpha loop is executable end to end
- the candidate lifecycle is public-safe
- the teacher-eval lifecycle is artifact-complete
- the comparison verdict is explicit
- the missing sealed holdout path is a named blocker, not a hidden assumption
