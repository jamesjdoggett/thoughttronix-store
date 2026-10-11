# PROMPTS.md — AI Usage Log

## 2026-10-11 - Account Security Center Phase 3

### Prompts

1. "Read prd/account-security.md and plans/account-security.md. Implement Phase 3 only. Run automated checks and explain how to verify it manually in the browser. Do not begin Phase 4 or commit yet."
2. "Update PROMPTS.md with this Phase 3 session: all my prompts in order, corrections, outcome, deviations, and anything that went sideways. Commit Phase 3 and its session log with the message "Complete Account Security Center Phase 3", push, and confirm the working tree is clean. Do not begin Phase 4."

### Summary

- **Outcome:** Read the account-security PRD and plan and implemented Phase 3 only. Signed-in verification and correction flows now identify account/destination cooldowns, account/destination hourly limits, and network suppression, with seconds until retry. Overlapping account/destination limits report the longer wait. Reservation feedback comes from the same database operation that enforces the limits; invalid, suppressed, and failed requests retain network accounting. Added distinct expired, malformed, superseded/unavailable, successful, and already-verified link feedback, with retry guidance and signed-payload structure validation. Retained the documented policy that resending for an unchanged address leaves earlier unexpired links usable and repeated verification is harmless; address correction permanently invalidates previous links through the existing revision counter. Verification takes a database write lock before reading state, including on SQLite, and retries transient lock contention. Send reservations refresh current account state to avoid reserving delivery for stale corrected or verified addresses. Email exceptions and zero accepted messages both produce failure feedback while preserving saved state and attempted-send limits. Added accounts/PHASE3.md with behavior, policies, and browser verification instructions. No migration was needed. No Phase 4 checkout enforcement or continuation changes were begun. The user subsequently authorized this log, the exact requested commit message, and a push.
- **Verification:** The final full suite passed **335 tests**. The 34 new Phase 3 tests cover exact cooldown/hourly/24-hour expiry boundaries, shared account/destination limits, longest-wait feedback, network accounting for requests that send nothing, malformed signed payloads, superseded and repeated links, ownership isolation, stale account state, exception/zero-delivery failures, successful retry, concurrent hourly/network reservations, and simultaneous verification visits. After the concurrency-test correction, all 34 focused Phase 3 tests passed before the full-suite run. Ruff lint, changed-file formatting, Django system checks, migration consistency, production CSS rebuild, and git diff checks passed. Repository-wide Ruff formatting still flags the pre-existing unchanged orders/test_coupon_selector.py; that unrelated file was left untouched.
- **Browser confirmation:** Supplied browser steps for cooldown and resend feedback, repeated links, anonymous/different-account visits, invalidated and malformed links, hourly/network suppression, and delivery-failure recovery. Exact expiry and concurrency scenarios were verified automatically. The user has not explicitly reported Phase 3 browser results; no manual browser pass is claimed.
- **Deviations and follow-up questions:** No user correction, design clarification, or follow-up question occurred during Phase 3. Kept the earlier same-address resend policy and the planned Phase 3 scope. The user authorized committing and pushing after the implementation report, while reiterating that Phase 4 must not begin. This entry is added above existing entries without rewriting their history.
- **Sideways and corrections:** The initial accounts-only run passed 89 tests and failed the simultaneous-link test because it read Django test-client template contexts collected globally across threads; both requests appeared to share the same context. Corrected the test to inspect each response's own rendered HTML. The focused 34-test run then passed, including one verification and one already-verified result from concurrent visits, followed by the 335-test full-suite pass. Also corrected retry-message grammar for a one-second wait and reran verification. Commands used approved escalation for uv cache access. The existing repository-wide formatting issue remained outside this phase and was reported rather than changed.

## 2026-10-11 - Account Security Center Phase 2

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store, including commands, architecture, template, URL, testing, and AI-usage-log conventions.
2. "Read prd/account-security.md and plans/account-security.md. Implement Phase 2 only. Run automated checks and explain how to verify it manually in the browser. Do not begin Phase 3 or commit yet."
3. "Phase 2 passed automated and manual verification. Append the standard session log to PROMPTS.md, then commit the phase and log as "Complete Account Security Center Phase 2". Push and confirm the working tree is clean."

### Summary

- **Outcome:** Implemented Phase 2 only: shared Account security navigation and overview for customers, employees, and administrators; current-email or missing-email state, verification status, and password guidance; an adoption prompt after unverified users sign in; and adding or correcting an unverified email after current-password confirmation. Reused Phase 1 verification, delivery, and request limits. Email validation normalizes casing and surrounding whitespace, with database uniqueness enforcement and conflict feedback. Added migration 0003 with an email revision counter so correction invalidates prior verification links permanently, including when returning to a former address. Conditional updates reject stale account state. Preserved legacy-address evidence, account identity, password hashes, carts, purchases, and historical order email snapshots. Suppressed or failed delivery preserves the corrected address and permits resend under existing limits. Added accounts/PHASE2.md with implementation notes and browser verification instructions. The migration was not applied to the local database by the agent. Phase 3 and later flows were not begun. Added this log above existing entries without rewriting history; the user authorized committing the phase and log with the exact requested message and pushing to origin.
- **Verification:** The full automated suite passed **301 tests**, including new coverage for all roles, anonymous access, password validation, ownership isolation, legacy-address states, unavailable addresses, uniqueness-conflict feedback, stale links, delivery failure and retry, limits, verified-address protection, and preserved carts and orders. Ruff lint, changed-file formatting, Django system checks, migration consistency, production CSS rebuild, and git diff checks passed. Repository-wide Ruff formatting reported the pre-existing unchanged orders/test_coupon_selector.py; that unrelated file was left untouched.
- **Browser confirmation:** The user explicitly confirmed that Phase 2 passed automated and manual verification. The user did not enumerate individual browser scenarios, so no additional scenario-specific browser results are claimed.
- **Deviations and follow-up questions:** No design clarification or follow-up question was asked. The email revision counter implements the required invalidation after correction while retaining Phase 1's same-address resend policy. Password controls remain guidance until their planned phases. After successful verification, the user authorized the session log, commit, and push.
- **Sideways:** uv initially failed because the sandbox could not access its external cache; approved escalation allowed migration generation and checks to run. Repository-wide format verification identified an unrelated existing formatting issue; changed-file formatting passed, and no unrelated formatting change was made. No automated test failures or user-requested implementation corrections occurred in this phase.

## 2026-10-11 - Account security Phase 1 implementation and console-link correction

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store, including commands, architecture, template, URL, testing, and AI-usage-log conventions.
2. "Read prd/account-security.md and plans/account-security.md. Implement Phase 1 only, following its acceptance criteria. Use Django's built-in authentication and password framework for security-sensitive work.

   Run automated verification, including Ruff formatting, Ruff linting, and the full test suite. Then explain how I can manually verify Phase 1 in the browser.

   Do not implement later phases or commit yet."
3. "Phase 1 is not complete. Clicking the verification link from the console email shows:

   'This link is invalid or expired. Sign in to the account that requested it to send another email.'

   Investigate why the freshly generated link is rejected. Check the generated URL, token creation and validation, and account verification state. Fix the cause and add a regression test that follows the actual link generated in the outgoing email.

   Run verification again and give me browser retest steps. Do not continue to Phase 2 or commit."
4. "The browser retest passed: the new verification link works. Phase 1 is approved.

   Append a session log to PROMPTS.md under today's date, newest entry at the top. Record every prompt in order, including corrections. Summarize the outcome, follow-up questions, and the console email URL wrapping problem and fix. Record 281 passing tests. Only claim browser checks I actually confirmed.

   Do not commit yet; let me review the log first."

### Summary

- **Outcome:** Implemented Phase 1 signup and initial email verification only. Signup requires a valid unique email normalized by trimming surrounding whitespace and lowercasing, with database uniqueness enforcement; dots and plus suffixes remain significant. Retained Django UserCreationForm, password validators, and username authentication. Added signed 24-hour verification links using Django timestamp signing, signed-in resend, expired/invalid-link guidance, and delivery-failure retry without deleting accounts. Verification does not authenticate recipients. Added durable, transactional account/destination and network request limits, including suppressed requests and failed sends. Chose and documented 10 signup attempts per network address per rolling hour; resends leave earlier links to the same unchanged address valid until expiry. Added configurable email delivery with working local console defaults and Phase 1 documentation/browser instructions in accounts/PHASE1.md. Applied accounts migration 0002 locally. Existing addresses start unverified; valid unique addresses are normalized, while invalid addresses and every member of a duplicate group have their original values preserved in legacy_email and assigned email cleared. Migration tests verify preserved account identifiers, roles, carts, orders, and historical order email snapshots. No later-phase checkout enforcement, Security Center, email correction/replacement, password changes, or recovery flows were implemented. No seed, commit, or push was run.
- **Verification:** The final full suite passed **281 tests**, including regressions that follow URLs extracted from actual outgoing signup and resend messages and captured console output. Console-link tests cover anonymous and signed-in recipients. Ruff formatting and linting, Django system checks, migration consistency checks, and git diff checks passed. The production Tailwind stylesheet was rebuilt during the initial implementation. The initial corrected Phase 1 suite passed 276 tests before the browser-reported console-link defect; that result did not establish that console links were usable. After the fix, checked the active local backend against the existing unverified account: the printed URL matched the complete generated URL and its token validated for the current account and email, without changing that account's verification state during the diagnostic.
- **Browser confirmation:** The user first reported that clicking the console verification link displayed the invalid-or-expired message. After the fix and retest instructions, the user explicitly confirmed that the new verification link works and approved Phase 1. No other browser checks, including private-window authentication behavior, resend cooldowns, cart access, duplicate-email validation, or delivery-failure recovery, were confirmed by the user or claimed as completed browser verification.
- **Deviations and follow-up questions:** No design clarification or follow-up question was asked of the user. The user corrected the premature Phase 1 completion claim by reporting the broken console link, requested investigation and an outgoing-email regression, then confirmed the successful browser retest and approved the phase. The numeric signup threshold, legacy-duplicate migration policy, and same-address resend policy were implementation choices documented within the approved Phase 1 scope. This log is added above the previous entries without rewriting their history and remains uncommitted for review.
- **Sideways:** uv initially could not access its external cache; approved escalation allowed verification commands to run. Ruff found formatting/import/model-order issues that were corrected; unrelated formatter changes were restored. Focused testing caught transient SQLite locking under simultaneous requests and an incorrect cart-response assertion; database reservations now retry lock contention, and the test follows the existing cart response. Full-suite testing exposed an existing coupon migration test creating a historical account model against the new account schema; its fixture now uses the current user model and passes the user ID to the historical order model. A throttled-signup response attempted to add an error to an unbound form; it was corrected to show a message without validating further submitted identities. Most significantly, Django 6's standard console backend serialized the long verification URL using quoted-printable soft line breaks with '=' markers. Clicking the visible fragment submitted a truncated token even though the original generated URL, signed payload, and database email were correct. Earlier tests inspected decoded in-memory email bodies and missed the console serialization defect. Added a regression that reproduced the failure from captured console output, then introduced accounts.mail_backends.ConsoleEmailBackend, a Django console-backend subclass using the RFC 998-character line limit so the full URL remains intact. It is the default development backend; SMTP serialization and token validation are unchanged. The regressions passed after the fix, followed by the 281-test full-suite pass and the user's confirmed browser retest. A process-inspection diagnostic was denied by the sandbox and was unnecessary once console serialization reproduced the cause.

## 2026-10-11 - Account Security Center tracer-bullet plan

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store, including commands, architecture, template, URL, and testing conventions.
2. "$prd-to-plan

   Read prd/account-security-center.md and create a tracer-bullet implementation plan. Propose the phases and ask me to review their granularity before writing the plan. After I approve, save it to plans/account-security.md. Do not implement anything."
3. Supplied the prd-to-plan skill instructions: inspect the PRD and codebase, identify durable architectural decisions, propose independently usable vertical slices with user-story mappings, obtain granularity approval, and then write the Markdown plan with acceptance criteria.
4. "The seven-phase granularity feels right. Keep the phases separate, but include basic resend, expired-link guidance, and retry after delivery failure in Phase 1 so initial verification is a complete usable flow. Phase 3 can finish detailed rate-limit feedback and remaining failure cases. Enforce the required request limits from the first exposed email flow.

   With that adjustment, I approve the breakdown. Write plans/account-security.md. Do not implement anything."
5. "Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including corrections. End with the outcome, deviations or follow-up questions, and anything that went sideways.

   Include that I reviewed the seven proposed phases and requested basic resend, expired-link guidance, delivery-failure retry, and required request limits in Phase 1 before approving.

   Record the comparison: the naive plan delayed customer behavior behind a foundations phase and combined password changes and recovery; the final plan delivers signup and verification first and separates those password flows.

   Do not implement anything."

### Summary

- **Outcome:** Read the PRD, planning skill, repository instructions, and existing account, checkout, settings, template, and test patterns. Proposed seven phases with user-story mappings, waited for approval, and created plans/account-security.md with durable architectural decisions and acceptance criteria. The final phases are signup and initial verification; security overview and existing-account adoption; verification feedback and remaining failure cases; verified checkout and continuation; replacement email lifecycle; signed-in password changes; and forgotten-password recovery. Added this log above existing entries without rewriting them. No application implementation, migrations, seed, tests, commit, or push was performed.
- **Deviations and follow-up questions:** Asked whether the seven phases were too coarse or too fine and whether any should be merged or split. The user reviewed and retained all seven, but required basic resend, expired-link guidance, delivery-failure retry, and required request limits in Phase 1 before approving. Phase 3 retains detailed rate-limit feedback and remaining failure cases. The saved plan reflects that adjustment. As requested in the logging prompt, the comparison is: the naive plan delayed customer behavior behind a foundations phase and combined password changes and recovery; the final plan delivers signup and verification first and separates those password flows. The naive plan itself was not presented or created in this session.
- **Sideways:** No tool failures occurred. One broad repository read was truncated; no application or browser verification was claimed. Existing modifications to PROMPTS.md and untracked skill/PRD files were observed and preserved. Planning details left open by the PRD, including the numeric signup-attempt limit, same-address verification-resend invalidation policy, and operational legacy-duplicate resolution, remain implementation decisions rather than invented approved requirements.

## 2026-10-11 - Account Security Center design interview and PRD

### Prompts

1. Provided the repository's AGENTS.md instructions and Windows workspace context for the ThoughtTronix Store, including commands, architecture, template, URL, and testing conventions.
2. "$grill-me

   I want to design an Account Security Center for ThoughtTronix. Customers need to provide an email address when signing up, change their password, and reset a forgotten password through email.

   Help me work out how these features should behave. Recommend one or two additional account security features that would be useful for our store, and discuss them with me before including them.

   Only interview me and help settle the design for now. Do not write a PRD, implementation plan, or other documentation, and do not implement anything yet. We will use $to-prd after the interview."
3. Supplied the grill-me skill instructions: interview one question at a time, assume beginner knowledge, state the decision being settled, explain options and tradeoffs, recommend an option with reasons, and explore the codebase for questions it can answer.
4. Supplied the to-prd skill instructions and PRD template for later use: synthesize agreed context without interviewing, inspect the repository, and save a PRD with Problem Statement, Solution, User Stories, Implementation Decisions, Out of Scope, and Further Notes; omit specific file paths and code snippets from implementation decisions.
5. "1" — keep username login and require a unique email at signup.
6. "1" — include email verification before shopping with the account.
7. "1" — allow sign-in, browsing, and cart use before verification; block checkout until verified.
8. "1" — allow correction of an unverified email after password confirmation, sending a new link and invalidating links for the previous address.
9. "1" — allow verified email changes with password confirmation and verification of the replacement; retain the old address until completion and notify it afterward.
10. "1" — prompt existing users for email setup after sign-in, retaining account, cart, and order-history access while requiring verification before checkout.
11. "1" — require the current password and the new password entered twice for normal password changes.
12. "1" — preserve the current session and sign out other sessions after a normal change; sign out all sessions and require sign-in after a reset.
13. "1" — use a generic reset-request confirmation and send reset email only to verified account addresses.
14. "3" — make password-reset links expire after 24 hours rather than the recommended 30 minutes.
15. "1" — retain earlier reset links until expiration or a password change/reset; using one invalidates them all.
16. "1" — include password-change email alerts after both normal changes and resets, without passwords or reset links.
17. "1" — make email-verification links expire after 24 hours, with resending available.
18. "1" — use a 60-second cooldown and five sends per hour per account or destination, supplemented by a network-address limit; retain generic reset responses when limited.
19. "1" — retain the existing eight-character minimum and other existing password checks rather than the recommended 12-character minimum.
20. "1" — exclude alternative/manual recovery from this release when the customer cannot access their verified inbox; suggest recovering the email account first.
21. "1" — apply the Security Center and email recovery to customers, employees, and administrators; require verification for anyone checking out through the storefront.
22. "1" — support configurable real email delivery and retain console delivery for local development.
23. "1" — provide one Security Center overview with email, verification status, password controls, and pending replacement email, with dedicated forms and a signed-in navigation link.
24. "1" — allow cancellation or replacement of a pending email change, invalidating its links while retaining the current verified email and checkout access.
25. "1" — verify email without automatic sign-in; offer checkout continuation for the matching signed-in account or direct the user to sign in.
26. "1" — disclose email unavailability at signup with sign-in and reset links, accepting the stated privacy tradeoff and limiting repeated attempts.
27. "1" — do not reserve addresses for pending changes; assign only on successful verification and an availability check, with the first successful verification claiming the address.
28. "1" — require verification of all existing email addresses; missing, invalid, or duplicate addresses must be corrected first.
29. "1" — ignore capitalization and surrounding spaces when matching emails, preserving dots and plus suffixes.
30. "1" — preserve accounts and pending changes when email delivery fails, allow retry, retain generic reset responses, and do not undo successful password changes when alerts fail.
31. "1" — invalidate outstanding reset and verification links when an email change completes, and cancel pending email changes after a password reset.
32. "1" — set a configurable network limit of 30 email requests per hour per network address, counting requests even when no email is sent.
33. "$to-prd

   Create a new PRD in prd/ using the decisions from our interview. Do not create an implementation plan or implement anything yet."
34. Supplied the to-prd skill instructions and template again, requiring synthesis of the agreed conversation into a local PRD without further interviewing.
35. "Clarify that the implementation plan and implementation are deferred to later assignment steps, rather than out of scope for the feature."
36. "Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including any corrections. End the entry with a short summary: the outcome, any places where I deviated from a recommended answer or asked follow-up questions, and anything that went sideways."

### Summary

- **Outcome:** Completed the one-question-at-a-time design interview and created prd/account-security-center.md using the requested template. Agreed on required unique email, verification-gated checkout, email management, password changes and resets, session invalidation, email verification and password-change alerts, request limits, existing-account transition, staff access, and configurable delivery. Preserved prior log entries and placed this entry first. No implementation plan, application changes, tests, seed, commit, or push were performed.
- **Deviations and follow-ups:** The user chose 24-hour reset links instead of the recommended 30 minutes and retained the existing eight-character password minimum instead of the recommended 12. All other selected interview answers matched the recommendations. The user then requested the PRD and corrected its scope wording: implementation planning and implementation are deferred to later assignment steps, not excluded from the feature. Updated the PRD accordingly.
- **Sideways:** No tool failures or implementation issues occurred. The initial PRD placed deferred planning/implementation under Out of Scope; the user's correction moved that distinction into Further Notes. The PRD explicitly identifies details not settled in the interview: a numeric signup-attempt limit, whether resending verification invalidates prior links for an unchanged address, and the operational handling of existing duplicate email records. Inspected repository code and documentation only; no application or browser verification was claimed. The pre-existing untracked to-prd skill directory was left untouched.

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
