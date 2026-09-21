# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

## 2026-09-20 — Featured product field and badges

### Prompts

1. Add an is_featured field to the Product model. It should be a BooleanField that defaults to False so existing products remain unfeatured. Only add the field for now. Do not add a badge or change any templates yet.
2. Add a "Featured" badge for products where is_featured is True. The badge must appear on both the catalog listing and the product detail page. Follow the project's existing styling and testing patterns.
3. Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including any corrections. End the entry with a short summary: the outcome, any places where I deviated from a recommended answer or asked follow-up questions, and anything that went sideways.

### Summary

- **Outcome:** Added `Product.is_featured` as a `BooleanField(default=False)` and generated migration `0003_product_is_featured` so existing products remain unfeatured when it is applied. The first change left templates untouched. After the follow-up request, added conditional DaisyUI "Featured" badges to the catalog (including category listings) and product detail pages. Added parametrized tests covering featured/unfeatured and available/unavailable products on all three pages. All 50 product tests and Ruff checks passed; Django system and migration consistency checks passed after the model change. The migration was not applied to the local database during this session.
- **Deviations:** No corrections or recommendations were overridden. The user followed up on the initial field-only request by explicitly requesting badges, then requested this log.
- **Sideways:** The initial 38-test run passed with a pytest cache write warning. The later 50-test run disabled the cache provider and passed without that warning. Git reported LF-to-CRLF conversion warnings for edited files; no test or lint failures occurred.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught
