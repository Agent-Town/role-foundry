# Software-Engineer Curriculum Sources

This note is intentionally narrow.

Role Foundry does **not** need a giant generic software corpus right now. The first concrete role is a **software-engineering apprentice improving Role Foundry itself**, so the next curriculum sources should be chosen for:

- small issue -> patch work
- frontend/product polish on a real UI
- code review / diff critique
- regression prevention
- documentation + artifact honesty
- eval / score reasoning

## Current repo state and the actual gap

What the repo already has is solid but narrow:

- `benchmarks/public-pack-v1/benchmark-pack.json` ships **12 public episodes across 6 public families**
- those families are all derived from the internal seed scenarios `t1`–`t6`
- they are strong on:
  - landing-story clarity
  - curriculum vs holdout separation
  - score-delta legibility
  - proof-bundle visibility
  - demo honesty
  - failure -> curriculum promotion
- they are **not yet strong** on:
  - true external issue -> patch exemplars
  - stack-adjacent frontend bugfixes
  - explicit code-review comment discipline
  - executable UI regression tasks
  - accessibility/product-polish references grounded in public standards

That matters because the current apprentice is already a real software role, not a generic “agent” role.

Also: the repo is clearly **Alpine.js + static HTML/JS on the frontend** (`app/*.html`, `app/app.js`) with a **Python runner/eval path** (`runner_bridge/*.py`). So source choice should match that reality instead of drifting into giant backend-heavy corpora.

## Ranked candidates for now

### Good hackathon-time additions

| Rank | Source | Primary URL | What signal it provides | Licensing / access status | Likely role in RF | Ingestion difficulty | Major risks |
|---|---|---|---|---|---|---|---|
| 1 | Playwright docs + examples | <https://playwright.dev/docs/best-practices> | High-signal patterns for UI regression tests, user-visible selectors, isolation, trace/debug workflows, and honest browser automation. Very directly useful for turning current RF screens into executable regression tasks. | Public. Playwright repo is Apache-2.0. | `training` | low | Easy to drift into “write Playwright tests” as an end in itself. Keep every episode tied to an actual RF product slice or regression. |
| 2 | Google Engineering Practices — code review guides | <https://google.github.io/eng-practices/review/> | Concrete review heuristics: what to look for in a diff, test/doc expectations, small-change discipline, reviewer vs author behavior, comment quality. This cleanly fills RF’s current code-review / diff-critique gap. | Public. Repo is CC BY 3.0. | `training` | low | Prose-only source; must be converted into RF-local review episodes and rubrics instead of copied wholesale. |
| 3 | Alpine.js repo + docs | <https://github.com/alpinejs/alpine> | Stack-adjacent small frontend fixes, state-management edge cases, docs changes, and UI behavior patterns that look a lot like RF’s current frontend stack. Best source for manually curated issue -> patch examples close to the repo’s actual shape. | Code/docs repo is public and MIT. **But** issue/PR/review text on GitHub should not be treated as blanket MIT relicensed content. | `manual curation only` | medium | Raw GitHub thread text has ownership/licensing ambiguity; framework-internal examples can also drift away from RF product work if not curated aggressively. |
| 4 | WAI-ARIA Authoring Practices Guide (APG) | <https://github.com/w3c/aria-practices> | Keyboard behavior, semantics, naming, disclosure/dialog/tab patterns, and other judge-visible product-polish rules for frontend work. Strong for turning vague “polish” into concrete standards-backed tasks. | Public. Repo documents are under the W3C Software and Document License. | `training` | low | Can devolve into generic accessibility trivia unless tied to specific RF screens and failures. |

### Useful support sources, but not the first thing to ingest

| Rank | Source | Primary URL | What signal it provides | Licensing / access status | Likely role in RF | Ingestion difficulty | Major risks |
|---|---|---|---|---|---|---|---|
| 5 | MDN Web Docs | <https://developer.mozilla.org/en-US/> | Standards-grounded web-platform explanations and code examples. Good support material for frontend correctness, DOM behavior, accessibility, and docs honesty. | Public. MDN prose is CC BY-SA; code samples are CC0 for newer samples and older samples are mixed/historical. | `manual curation only` | low | Mixed licensing on prose/code makes raw ingestion annoying; also reference prose is less valuable than task-shaped examples. |
| 6 | web-platform-tests (WPT) | <https://github.com/web-platform-tests/wpt> | Executable browser-behavior cases, rendering/reftest patterns, and regression-thinking discipline. Very strong oracle source once RF has a stable browser-test lane. | Public. BSD-3-Clause. | `public benchmark` | medium | Easy to get dragged into browser-spec minutiae instead of practical RF product work. Better after a Playwright-based RF regression lane exists. |
| 7 | SWE-bench / SWE-bench Verified | <https://github.com/SWE-bench/SWE-bench> | Real issue -> patch benchmark structure, evaluation harness ideas, and comparison/score reasoning. Useful as a reference point for benchmark design. | Public MIT harness/dataset packaging, but task instances inherit mixed upstream repo realities and evaluation is infra-heavy. | `public benchmark` | high | Wrong size and shape for RF right now: broad, expensive, often backend-heavy, contamination-prone, and not especially aligned with the repo’s current frontend/product loop. |

## What not to use directly

### 1. Raw GitHub issue / PR / review-comment dumps

Do **not** bulk-train directly on scraped GitHub discussion text.

Why:

- GitHub’s Terms of Service say users **own the content they post**.
- GitHub API access is governed by separate API terms.
- Public visibility is **not** the same thing as clean downstream training rights.
- The quality is noisy, adversarial, repetitive, and hard to attribute correctly.

Use GitHub threads only as **manual curation input**, then rewrite Role Foundry episodes in RF’s own words.

Reference: <https://docs.github.com/en/site-policy/github-terms/github-terms-of-service>

### 2. Generic tutorial/blog scraping

Do **not** ingest random blogs, SEO tutorials, or broad “JavaScript tips” dumps.

Why:

- quality is wildly uneven
- provenance is messy
- duplication is rampant
- the signal is decorative compared with issue -> patch, review, and regression material

If a blog post teaches something genuinely useful, turn the lesson into an original RF-authored episode instead of importing the prose.

## Best candidates for NOW, in plain English

If the question is “what should we add next week, not next year?”, the best additions are:

1. **Playwright-based regression curriculum**
   - best immediate fit for the current repo
   - turns visible RF UI slices into executable checks
   - directly improves bugfixing, regression prevention, and artifact honesty

2. **Code-review curriculum from Google Eng Practices**
   - cleanest way to add diff critique without licensing mud
   - strengthens reviewer comments, scope control, test/doc expectations, and uncertainty honesty

3. **Manual-curation lane from Alpine.js issues/PRs**
   - best stack-adjacent issue -> patch material
   - should be rewritten into original RF episodes, not imported raw

APG should be used as a **supporting reference** inside the first two additions, not treated as a giant standalone curriculum dump.

## Narrow next-step plan for the top 3 additions

### 1. Playwright regression mini-pack

Add one small public family for RF itself, something like:

- `rf.software-engineer.public.playwright-regression`

Start with **4-6 episodes** only, tied to current UI surfaces:

- landing page story clarity stays visible after a copy edit
- run detail page preserves proof-bundle evidence panels
- curriculum vs teacher-only labels stay explicit
- live/read-model fallback stays honest when data is missing

Rules:

- use role/text/test-id style selectors, not brittle CSS/XPath
- every episode should have a visible product reason, not just “more tests”
- require receipts: failing check, fix, and passing rerun

### 2. Code-review / diff-critique mini-pack

Add one family for review behavior, something like:

- `rf.software-engineer.public.code-review-discipline`

Start with **6-8 review-only episodes** built from tiny RF-local diffs.

Score for:

- whether the review found the real user-facing risk
- whether it asked for tests/docs when needed
- whether it kept blocking vs non-blocking comments distinct
- whether it avoided fake certainty when evidence was weak
- whether it kept scope narrow instead of demanding repo-wide churn

This is one of the cheapest high-signal additions available.

### 3. Manually curated issue -> patch exemplars from Alpine.js

Create a tiny allowlist process:

- pick **10** merged Alpine.js issues/PRs max
- prefer small UI behavior, docs, accessibility, or state-transition fixes
- keep code/diff context only where license is clear
- rewrite task statements, hints, and rubrics into original RF wording
- ship only the first **3** as pilot episodes

This gets RF real issue -> patch texture without pretending raw GitHub discussion text is clean training data.

## One best immediate next move

Add the **Playwright regression mini-pack first**.

It is the narrowest honest upgrade that immediately improves the current apprentice on exactly the work RF already does: visible frontend changes, regression prevention, receipts, and small-scope bugfixing.
