# Spec 006 — Teacher Evaluation + Iteration Loop

## Intent

Make the moat real: hidden holdout evaluation, scorecards, failure themes, and iteration history.

## Requirements

1. Teacher and student roles must be distinguishable.
2. Holdouts remain sealed from student-facing views and prompts.
3. Teacher output must include per-scenario notes and aggregate score.
4. Failed holdouts may become public curriculum themes, but not leaked prompt text.
5. Iteration history must show score change over time.

## Acceptance criteria

- Two iterations can be compared
- Holdout secrecy is preserved
- Failure themes are visible
- Score delta is legible in UI and stored data

## Done when

Role Foundry demonstrates honest improvement instead of vague claims.