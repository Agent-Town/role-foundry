# Judge Q&A note — honest short answers

Status: final-review-ready
Supporting note for `submission/judge-demo-script.md`.

## What is actually real today?

Three things:
- an executable **public alpha / public-regression** loop
- a **local private-holdout** boundary
- one real external `Clawith -> OpenClaw -> Claude/vibecosystem -> Clawith` roundtrip proof

That is the whole headline. Keep it narrow.

## Why call it a Software Engineer apprentice if the public slice is still frontend-heavy?

Because the role target is software-engineering work improving Role Foundry itself. The currently shipped public slice is still frontend/product-heavy, and we should say that plainly instead of pretending the full engineering curriculum is already complete.

## Is the private holdout flow a sealed eval system?

No. It is a **local/private discipline and separation contract**. It keeps teacher-only prompts out of tracked and student-visible artifacts, but it is not sealed certification, not tamper-proof evaluation, and not third-party-sealed holdout infrastructure.

## What exactly does the Clawith proof prove?

It proves **one real external control-plane path**:
- Clawith = control plane
- OpenClaw = harness / gateway path
- Claude/vibecosystem = executor

It does **not** prove native Clawith parity, native model-pool completion, or broad production hardening.

## Is ERC-8004/Base part of this branch?

No. At most it is an optional future hook. Do not talk about it as landed evidence here.

## What should judges remember?

This is a real but narrow alpha:
- Role Foundry has a real train/eval/promote story
- the first role is a Software Engineer apprentice improving the system itself
- the public loop is real
- the local private-holdout boundary is real
- one external roundtrip proof is real
- broader parity and sealed-eval claims are not being made
