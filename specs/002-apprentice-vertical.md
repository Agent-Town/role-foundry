# Spec 002 — Frontend Apprentice Vertical

## Intent

Turn Role Foundry from a generic AI-demo shell into a specific dogfood product story: Robin + Neo are training the first apprentice to build Role Foundry itself.

## User story

As a judge, I should understand in under two minutes:
- who the teachers are
- what the apprentice is being trained to do
- what is public practice vs hidden exam
- how the apprentice improved
- what evidence backs the score

## Requirements

1. The landing page must explicitly frame the apprentice vertical.
2. The scenarios page must separate:
   - public curriculum
   - sealed holdout previews for judges
3. The run page must show a proof bundle including:
   - receipt summary
   - changed files
   - transcript excerpt
   - policy snapshot
4. The scorecard page must show:
   - score deltas
   - holdout integrity explanation
   - failure themes that became curriculum
5. Copy must remain honest about demo-mode limitations.

## Failure modes to prevent

- sounding like a generic agent sandbox
- implying fake live integrations
- leaking hidden holdout prompts
- showing broad repo churn instead of a narrow slice

## Acceptance checks

- Demo contract tests pass
- Manual browser walkthrough confirms the apprentice story stays coherent across all pages

## Done when

A judge can follow the apprentice loop without extra explanation from the operator.