# PROMPTS.md — AI Usage Log

## 2026-09-27 - Discount coupons and coupon picker review

### Prompts

1. Help design discount coupons for the ThoughtTronix project. Inspect the existing checkout and order code first. Interview me one decision at a time about the rules the assignment leaves open. Do not edit files yet.
2. Here is the coupon assignment brief, including the fixed requirements and the open design decisions.
3. Choose percentage discounts only; product-specific coupons must discount only eligible products and order-wide coupons the whole order.
4. Show a mixed-cart example with two Seraphines and one ineligible product using a 50% Seraphine coupon, then confirm the checkout and saved-order amounts.
5. Implement the plan.
6. Browser review found the New coupon Products options jumbled and hard to read, so inspect the rendered form and CSS, fix the selector, and verify it without committing.
7. Skip temporary browser scripts; I will verify the checkbox selector manually. Stop automation and report changed files, tests, and commit status.
8. Run the full test suite and Ruff check after the selector fix. If they pass, commit and push the coupon feature and selector fix as checkpoint 1. Keep the session log and reflection for later.
9. Make one small review improvement: visually highlight checked products in the coupon picker while keeping checkbox behavior. Run focused selector tests and Ruff, then show the change before committing.
10. Read the standard session-log prompt in the PROMPTS.md header and write this session's log. Do not write REFLECTION.md or commit yet.

### Summary

- **Outcome:** Settled coupon rules and implemented models, migrations, checkout quoting and placement, staff management, order and dashboard discount reporting, documentation, and tests. The mixed-cart example is $598.00 subtotal, $249.00 discount, and $349.00 total. Browser review led to a readable checkbox product picker, followed by a selected-row highlight that retains native checkbox behavior.
- **Verification:** Full suite passed with 233 tests; Ruff passed. The focused selector suite passed with 4 tests after the highlight change. Django checks, migration checks, and Tailwind build also passed.
- **Deviations:** Follow-up questions resolved the assignment's open rules. No reflection was written.
- **Sideways:** Temporary Chrome automation was stopped at the user's request. Checkpoint `e292190` was created; its push was interrupted. The final highlight remains uncommitted. The intentional `CLAUDE.md` to `AGENTS.md` rename was preserved.

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
