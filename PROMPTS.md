# PROMPTS.md — AI Usage Log

## 2026-10-04 - Product-image build, marketing import, and reflection evidence

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store, including architecture, template, URL, and testing conventions.
2. "Read HANDOFF.md and implement the agreed product-image feature. After reading it, delete HANDOFF.md and do not commit it.

   Follow AGENTS.md. Do not edit .gitignore or commit product-images/. Keep the supplied source images until importing and verification are complete.

   Run the test suite and fix failures caused by the feature. Give me basic browser verification steps covering uploads, replacements, removals, rejected files, missing-file fallback, the marketing import command, and catalog/detail appearance."
3. "FocusHalo has been added through the employee back-office form. Do not run seed.

   Read the standard session-log prompt in the PROMPTS.md header and follow it to log this build session.

   Gather the actual code evidence for my reflection:
   1. Product image field definitions, with filenames and line numbers; explain upload_to.
   2. The opening back-office upload form tag, with filename and line number; explain enctype.
   3. FocusHalo's image file paths on disk, image values stored in the database, and browser image URLs. Include both catalog and detail versions.
   4. The fields/settings and files that determine these paths and URLs.
   5. The development URL configuration that serves media, with filename and line numbers.
   6. The exact media folder and database file needed for the grading snapshot.

   Inspect the actual code and database; do not guess. Do not commit yet."

4. "The assignment explicitly requires an ImageField on Product, but you implemented image_catalog and image_detail as FileFields.

   Change these processed image fields to ImageFields while preserving the existing optimized WebP files, database values, validation, and upload behavior. Generate and apply the migration, run the relevant checks, and confirm FocusHalo still displays correctly.

   Update the build-session log to include this correction. Then give me the updated image-field definitions and line numbers, plus any other reflection references whose line numbers changed. Do not run seed or commit yet."

### Summary

- **Outcome:** Implemented two optional optimized image fields, shared still-image validation and WebP processing for employee and Django admin forms, current previews, replacement/removal/deletion cleanup after commit, independent missing-file placeholders, square uncropped catalog/detail frames, configurable local media, development media serving, explicit marketing import mappings, orphan-file reconciliation, documentation, and isolated image tests. Read and deleted HANDOFF.md. Verified migrations on a disposable database before applying the image migration to the existing database. Imported all 12 mapped marketing images successfully; rerunning skipped all 12. Verified the 24 imported WebPs and catalog/detail HTTP rendering. Supplied source artwork remains intact. Kept .gitignore unchanged and excluded media/ and product-images/ through this checkout's .git/info/exclude. No seed, commit, or push was run. Preserved previous PROMPTS.md entries.
- **Verification:** The focused image suite passed 21 tests; the final full suite passed 254 tests. A subsequent focused validation check passed 4 tests after improving very-large-image error wording. Ruff lint, formatting checks for products/config, Django system checks, migration consistency checks, disposable migration application, and forced production Tailwind build passed. Imported optimized files totaled 1,899,798 bytes versus 24,343,724 bytes of mapped source artwork. Browser steps were supplied; visual browser verification was not performed or claimed. For the reflection follow-up, inspected actual code with line numbers, runtime settings, and FocusHalo's database row (pk 35, slug focushalo). Both stored WebPs exist, decode correctly at 600x600 and 1200x1200, appear in the rendered catalog/detail HTML, and return HTTP 200 through development media routes.
- **Deviations:** No recommended design choices were overridden. Chose 10 MiB (10,485,760 bytes), WebP quality 85, UUID filenames, import_product_images as the command name, and two non-editable FileFields controlled by shared form upload/removal fields. The user's instruction not to edit .gitignore was honored using local Git exclusions. The user subsequently reported creating FocusHalo through the employee form and requested a session log plus evidence for their own reflection; no reflection file was written.
- **Sideways:** uv initially failed to access its cache inside the sandbox; approved escalation allowed dependency installation and checks. The first disposable migration check applied successfully but temporary-directory cleanup failed because SQLite remained open; closing connections made the rerun pass. Lint/format checks found ordering and formatting issues, which were corrected; incidental formatting outside the feature was restored. An inline verification command failed due to PowerShell quoting; a multiline Python script verified the actual imports instead. Failed storage writes are cleaned without publishing a partial replacement. Database rollback preserves previous files but can leave a complete unreferenced new pair because storage is not transactional; the documented prune_product_images command reviews files older than 24 hours before optional deletion. No feature test failures occurred.


### ImageField correction follow-up

- **Outcome:** The user identified an assignment requirement the initial implementation missed: Product must use ImageField. Changed both processed image fields from FileField to ImageField, retaining upload_to="products/", blank=True and editable=False. Generated 0005_alter_product_image_catalog_and_more with two AlterField operations; verified migrations on a disposable database, then applied it to the existing database. Compared every product's image database values and SHA-256 hashes of all 26 media files before and after migration: all were unchanged. FocusHalo retained its catalog/detail paths and URLs, with valid 600x600 and 1200x1200 WebPs. Both rendered pages reference the correct files, and both media requests returned HTTP 200 through Django's test client. No visual browser verification was claimed. The upload, validation, optimization and cleanup code was unchanged. No seed or commit was run.
- **Verification:** The full suite passed 254 tests after the ImageField correction, including 21 image tests covering uploads, replacements, removals, validation, storage failures, fallback rendering and imports. Ruff check, model formatting, Django system checks, migration consistency checks and disposable migration application passed. showmigrations confirms migration 0005 is applied. No CSS/templates changed, so Tailwind did not need rebuilding.
- **Deviations and sideways:** The initial FileField choice did not meet the assignment's explicit ImageField requirement; this correction fixes that mistake. Recorded the user's correction as prompt 4 while retaining the original session history. Formatting initially needed normalization and passed afterward; no test failures occurred. Rechecked all prior reflection references: field definitions remain products/models.py lines 67 and 68; prepare_image remains line 121, URL fallback line 139, catalog URL property line 148 and detail URL property line 153. The form tag remains line 16, settings lines 135/136, media route line 19, and catalog/detail image tags lines 64/17. New migration ImageField declarations are at lines 16 and 21. No previous reflection code-reference line numbers changed.

### FocusHalo image-generation provenance

- FocusHalo's image was generated using ChatGPT's image-generation tool with this exact prompt:

  "Create a square polished ecommerce product photograph for a fictional futuristic product called FocusHalo. A sleek premium black neural headband with a subtle luminous violet ring and refined electronics, clearly recognizable as wearable headband, floating at a three-quarter angle against a clean dark charcoal studio background. Entire device visible, centered with generous margin, crisp realistic materials, soft studio highlights and violet accent light. No text, no lettering, no logos, no people. High quality product catalog artwork."

## 2026-10-04 - Product-image design interview and implementation handoff

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store.
2. "$grill-me I want to add product images to ThoughtTronix. Marketing's provided images are in product-images/ at the repository root. This is a temporary source folder, not Django's media directory. Every product must display its uploaded image when available or the existing placeholder. Missing files must not produce broken image icons. Employees must upload images through the back office. Reject unusable files before saving them and explain the problem in plain language. Images should look consistent across the catalog and product detail pages, including alongside placeholders. Pages should stay fast. Interview me one question at a time to settle the design. Explore the codebase for anything you can answer yourself."
3. Supplied the grill-me skill instructions: interview one question at a time, assume beginner knowledge, state which design decision each question settles, explain options and tradeoffs, recommend one option with reasons, and explore the codebase instead of asking questions it can answer.
4. "A" — use a dedicated initial import command, then back-office uploads for future changes.
5. "A" — assign SoulSear artwork to SoulSear Mark I only.
6. "A" — use the SyncRest image without text.
7. "A" — show the whole image inside a fixed frame without cropping.
8. "A" — use square frames for catalog and detail images and placeholders.
9. "A" — one image per product, with upload, replacement, and removal controls rather than a gallery.
10. "A" — generate smaller catalog and larger detail images during upload/import rather than serving originals unchanged.
11. "A" — accept still JPEG, PNG, and WebP files, validating actual decoded contents.
12. "A" — cap uploads at 10 MB and 20 million pixels.
13. "A" — require at least 400 pixels on each side.
14. "A" — store optimized versions only, without retaining originals.
15. "A" — use a separate configurable local media directory rather than cloud storage.
16. "A" — preserve existing product images when rerunning the marketing import and report skipped products.
17. "A" — automatically delete old files after successful replacement, removal, or product deletion.
18. "A" — generate WebP versions capped at 600 pixels on the longest side for catalog cards and 1,200 pixels for detail, preserving proportions/transparency without enlargement.
19. "A" — continue importing valid files when individual sources are missing or invalid and report each problem.
20. "A" — support image uploads through Django admin with the same validation and processing as the back office.
21. "Write HANDOFF.md for a fresh session to implement our agreed product-image design. Include every settled requirement, the artwork mappings, relevant codebase findings, and test/browser verification requirements. Do not commit HANDOFF.md. Read the standard session-log prompt in the PROMPTS.md header and follow it to log this interview session."

### Summary

- **Outcome:** Completed the design interview and wrote HANDOFF.md with the complete agreed requirements, 12 explicit artwork mappings, repository findings, and automated/browser verification requirements. Inspected product models, forms, views, admin, URLs, templates, settings, dependency configuration, seed catalog, shared fixtures, documentation, and Git status. Checked supplied PNG dimensions and visually inspected both SyncRest variants. Product-image implementation, migrations, imports, and tests were not performed. No files were committed or pushed.
- **Deviations:** The user selected every recommended option, with no overridden recommendations or follow-up corrections. The final follow-up requested a fresh-session implementation handoff and this log. Routine implementation details not individually decided are identified in the handoff rather than presented as settled choices.
- **Sideways:** An initial quoted search for product names returned no matches; a targeted search resolved the relevant names. A file-listing command included a nonexistent tests directory; the actual product tests were found in products/tests.py and products/test_backoffice.py. Neither issue affected the design. The existing untracked product-images/ folder was left intact. No browser verification or application checks were claimed for this documentation-only session.

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
