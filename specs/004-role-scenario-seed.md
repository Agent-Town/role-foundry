# Spec 004 — Role + Scenario Seed Model

## Intent

Create the first live-mode data model for roles, scenarios, public curriculum, and hidden holdouts.

## Requirements

1. A role record must contain name, description, goals, and success criteria.
2. A scenario record must include:
   - id
   - title
   - description
   - type (`training` or `holdout`)
   - difficulty
3. Holdouts must be excluded from student-facing payloads.
4. Bootstrap must be able to seed one complete apprentice vertical.
5. Seed data must remain narrow and judge-legible.

## Acceptance criteria

- One seed role exists
- At least 6 training scenarios exist
- At least 3 holdouts exist
- Student-facing queries do not expose holdout prompts verbatim

## Done when

The live system can represent the same core structure that the static demo already shows.