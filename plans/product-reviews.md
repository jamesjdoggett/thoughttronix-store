# Plan: Product Reviews

> Source PRD: [ThoughtTronix Product Reviews](../prd/product-reviews.md)
>
> Four-phase breakdown approved by the user on 2026-10-18. Phases 1-3 implemented and manually verified by the user on 2026-10-18; phase 4 remains unimplemented.

## Architectural decisions

- **Owning app:** Extend `products` and its existing public product detail experience. Staff moderation happens there; no new back-office screen or separate reviews app.
- **URLs:** Keep `/products/<slug>/` as the public page, with a `#reviews` anchor. Use named routes in the `products` namespace beneath `/products/<slug>/reviews/` for creation and loading, and `/products/<slug>/reviews/<int:pk>/edit/` and `/products/<slug>/reviews/<int:pk>/delete/` for management. Scope every review lookup to its product. GET requests display forms or confirmations; mutations require CSRF-protected POSTs.
- **Models and migrations:** Introduce `Review`, related to `Product` and the configured user model as author. Persist required rating and comment, original creation time, a concurrency revision, and nullable latest staff editor and staff-edit time. A database uniqueness constraint enforces one current author-product pair, including concurrent creates; enforce rating bounds as well. Introduce the schema with the first working publication slice; existing products start without reviews. Product deletion cascades to reviews. Keep existing order-item snapshots and nullable product links unchanged.
- **Eligibility:** Creation requires the signed-in account's own order item linked to this product on a Placed, Shipped, or Delivered order. Cancelled purchases do not qualify, but another qualifying purchase suffices. Do not match contact emails, shipping names, gifts, inherited ownership, or next of kin. SoulSear follows identical rules. Neither current email verification nor product availability adds a restriction. Existing reviews remain public and manageable after cancellation; replacement creation rechecks eligibility.
- **Authorization and attribution:** Authors manage their own reviews; `is_staff` permits management of any review, never creation on someone else's behalf or without a personal qualifying purchase. Preserve authorship and persistent staff attribution through subsequent customer edits. Verified purchaser describes eligibility at creation.
- **Validation and ordering:** Whole-star ratings 1–5; trim comments and require 1–2,000 characters afterward. Escape plain text and preserve line breaks. Order by original creation time descending with a deterministic tie-breaker; edits never reorder reviews. Summaries use all reviews, with a one-decimal average and total count.
- **Rendering and interaction:** Follow existing class-based views, thin views, form validation, model/manager logic, and cross-model workflow conventions. Use existing base-page inheritance, underscore-prefixed HTMX partials, Tailwind/DaisyUI night styling, and HTMX without additional JavaScript. Every mutation introduced in a phase includes both HTMX behavior and standard-form fallback. Enhanced mutations synchronize summary, dedicated Your review area, and any loaded public copy without replacing unrelated open forms or resetting the reader's position.
- **Concurrency:** Compare the submitted revision atomically with the saved revision before updating; protect against concurrent create duplicates at the database boundary. Do not keep full revision history. Conflict and failure responses must preserve the submitted draft; ordinary auth redirects must not navigate an enhanced drafting page away.
- **Phase discipline:** Each phase includes its own migrations where needed, integrated behavior, meaningful pytest coverage using plain fixtures, and browser verification. Never invoke the seed command in tests. Run the full suite and Ruff checks at every phase boundary; build CSS when new styling needs compilation. Do not defer all tests or fallbacks to a final phase. Later phases extend behavior already usable in earlier ones.

---

## Phase 1: Customer review creation, editing, and deletion

**Status:** Complete. Full suite: 542 passed. Ruff lint/format, Django system and migration checks, and production CSS build passed. The user confirmed browser verification passed on 2026-10-18.

**User stories:** 1-3, 5-16, 19, 22-23 (18 distinct stories). Story 19 covers staff personal creation; moderation follows in Phase 2.

**Dependencies:** Existing catalog, account, checkout, order-status, and HTMX foundations. No other review phase is required.

### What to build

**Publish and read.** Deliver the first purchase-to-publication path: an eligible signed-in account submits a rating and comment in Your review, and any visitor can immediately read it on the product page. Introduce Review persistence and eligibility checks with this path. Initially show the ten newest reviews; loading further batches comes in Phase 2. Display the public username, Verified purchaser label, summary, and designed empty state. Publish through HTMX while updating the dedicated area and public list consistently. Provide the same creation path with standard forms.

**Edit your review.** Allow an author to open Save/Cancel editing from either displayed copy. Save updates persisted feedback, the summary, and both loaded copies; Cancel restores saved content. Retain the dedicated management area regardless of list position. Eligibility is not rechecked for managing an existing review.

**Delete and replace.** Add inline deletion confirmation with Confirm and Cancel. Confirm removes the current review, synchronizes its displayed copies and summary, and changes Your review to the appropriate eligible creation or ineligible state. Replacement is a new creation subject to current purchase eligibility.

### Acceptance criteria

- [x] In the browser, visit an empty product anonymously and see No reviews yet with a zero count and no misleading numeric average. Place an order, return as its account, publish a review, and see both copies and the correct average/count without a full-page reload.
- [x] Creation accepts only integer ratings 1–5 and trimmed comments of 1–2,000 characters. Invalid inputs remain beside field errors; plain-text markup is escaped and line breaks remain visible.
- [x] Anonymous users and nonpurchasers cannot create via direct requests. Tests cover every qualifying status, cancelled-only and mixed orders, account identity rather than shipping/contact data, SoulSear/next-of-kin rules, unverified current email, unavailable products, and staff personal eligibility.
- [x] Concurrent duplicate submissions leave exactly one review and return useful feedback rather than an unhandled error. A repeat submission does not create a second review.
- [x] Anonymous readers see at most ten reviews in stable newest-first order, with summary totals covering all reviews. The author's dedicated review remains visible even outside that batch.
- [x] With HTMX unavailable, valid creation returns to the product's reviews anchor and invalid submission displays retained inputs in a full page inheriting the base template.
- [x] Automated coverage includes product deletion cascading reviews, unavailable products retaining them, order snapshots surviving product deletion, and a replacement product inheriting neither reviews nor eligibility. In the browser, mark a reviewed product unavailable and confirm it remains readable and reviewable by a past purchaser.

- [x] In the browser, edit a rating and comment, save, and observe both copies and summary update in place. Cancel another edit and verify nothing was persisted and reader position is retained.
- [x] Invalid edits preserve both fields beside validation messages. Original posting order stays unchanged.
- [x] Cancel all of the author's qualifying orders through existing staff controls; their review remains public and editable. Unavailability likewise does not block editing.
- [x] Direct requests from another customer cannot open or save an edit. Tests cover ownership, cancellation, validation, and synchronized HTMX responses.
- [x] Standard forms support editing, validation, and cancellation and return successful submissions to the reviews anchor.

- [x] In the browser, cancel a deletion and see the saved review unchanged; confirm deletion and see both loaded copies removed, totals updated, and No reviews yet when the final review is deleted.
- [x] An eligible author can publish a replacement. After all purchases are cancelled, the author can delete their existing review but cannot replace it until another qualifying order exists.
- [x] A customer cannot delete another customer's review through direct requests. GET confirmation does not mutate data; POST requires CSRF protection.
- [x] HTMX confirmation and deletion preserve page position and unrelated drafts. Standard-form confirmation/cancellation/deletion work and return to the reviews anchor.
- [x] Tests cover permission checks, replacement eligibility, duplicate protection for replacements, and synchronized deletion responses.

---

## Phase 2: Staff moderation and loading additional reviews

**Status:** Complete. Full suite: 550 passed. Ruff lint/format, Django system and migration checks, and production CSS build passed. No new JavaScript or migrations. Prepared 25 qualifying purchaser reviews on local Calm Collar for browser checks. The user confirmed browser verification passed on 2026-10-18.

**User stories:** 4, 12-19, 22-23 (11 distinct stories). Stories 4, 17, and 18 are newly completed; the others extend Phase 1 behavior to moderation and loaded batches.

**Dependencies:** Phase 1: persisted reviews, customer CRUD, eligibility, synchronized displays, and ordinary-form fallbacks.

### What to build

**Moderate in context.** Expose edit and delete controls to staff on product-page reviews using the existing inline interactions and fallback forms. Record latest staff editor and staff-edit time when staff edits another customer's feedback, while preserving its author. Show Edited by staff permanently after such edits, including after later author changes. Staff deleting a review does not ban replacement.

**Load additional reviews.** Add Load more to append ten older reviews per action while keeping existing review cards and open forms intact. Use stable pagination boundaries so intervening creation or deletion does not duplicate or skip surviving reviews. Keep Your review available above the list even when its public position has not been loaded. Ensure mutations target all loaded representations without rebuilding the whole review section.

### Acceptance criteria

- [x] In the browser, staff edits another customer's review; readers see the customer's username, Verified purchaser, and Edited by staff. A later customer edit retains the staff label and internal latest-staff-edit attribution.
- [x] Staff can confirm or cancel deletion of another customer's review; confirmed deletion updates the public list and summary, and the author's next visit offers replacement when eligible.
- [x] A staff purchaser can create and manage their own review under ordinary author rules. Moderation cannot create for another account or bypass staff's own purchase requirement.
- [x] Tests verify staff versus nonstaff permissions, author preservation, staff attribution persistence, replacement after moderation, and full-page and partial responses. Browser-check moderation with HTMX enabled and disabled.

- [x] With more than twenty reviews, anonymously load 10, then 10, then the remainder; the control disappears at the end. All batches retain original newest-first order without duplicates.
- [x] In the browser, open an edit form, type a draft, then load more. Its inputs and page position remain intact. An author whose review is older than the first batch can manage it immediately in Your review.
- [x] Once the author's public copy is loaded, editing or deleting through either location synchronizes both; summary totals always include unloaded reviews.
- [x] Create or delete a review between loading batches; subsequent batches do not duplicate or skip surviving older reviews. Tests cover stable ordering ties and pagination boundaries as well as mutation synchronization.
- [x] With HTMX unavailable, a standard navigation control lets readers reach older reviews while preserving access to the summary and dedicated area; author mutation fallbacks remain usable.

---

## Phase 3: Concurrent editing and conflict handling

**Status:** Complete. Full suite: 560 passed; after final snapshot cleanup and expanded coverage, all 78 review tests passed (567 tests collected overall). Ruff lint/format, Django system and migration checks, Git whitespace checks, and a forced production CSS build passed. No new migrations or custom JavaScript. The user confirmed browser verification passed on 2026-10-18.

**User stories:** 14, 20, 22-23 (4 distinct stories). Story 20 is newly completed; the others extend validation and synchronization to conflict recovery.

**Dependencies:** Phases 1-2: author/staff editing, revision state, loaded representations, and attribution.

### What to build

**Resolve conflicts.** Complete the revision-based editing experience for customer/staff and multiple-tab races. Reject stale saves atomically, retain the submitted rating and comment, and present the latest saved version beside the draft with an explanation. Another explicit save may proceed against the displayed latest revision; another intervening change must trigger another conflict. Handle deletion while an edit is open without resurrecting a review or losing the draft.

### Acceptance criteria

- [x] In two browser sessions, open the same review, save one edit, and submit the other. The newer saved version survives; the second editor sees their intact draft and the latest saved version for comparison before explicitly retrying.
- [x] A second concurrent change before retry produces another conflict. Tests exercise the atomic stale-revision guard rather than only form-open checks.
- [x] Conflicts leave persisted summaries and other saved displays accurate, preserve attribution, and do not replace unrelated open forms or lose page position.
- [x] Delete a review in another session while editing it; the pending editor receives useful feedback with their draft retained, and a failed edit cannot recreate it.
- [x] Conflict feedback and explicit retry work with both HTMX and standard forms. Tests cover customer/staff races and multiple tabs of the same account.

---

## Phase 4: Failed saves, expired sessions, and final integration verification

**User stories:** 14, 21-23 (4 distinct stories) directly; final integration verification covers all 23 stories.

**Dependencies:** Phases 1-3: complete customer/staff workflows, incremental loading, and conflict-aware retry.

### What to build

**Recover failures and verify integration.** Finish the failure paths around the working create/edit workflows. Use declarative HTMX behavior and server responses to retain drafts and show nearby feedback on transport failures, server errors, expired authentication, and stale CSRF state. Offer sign-in in another tab, keeping the drafting page available for retry. Recover current CSRF state without discarding fields. Do not add custom JavaScript or promise draft survival after refresh/closing the page.

### Acceptance criteria

- [ ] In browser developer tools, interrupt a create or edit save, then restore connectivity. Rating, comment, page position, and nearby retry feedback remain; retry succeeds without duplicating a review.
- [ ] Expire a session while a form is open and submit it. The drafting page stays in place with its draft; sign in in another tab and return to retry successfully, including when login rotates the CSRF token.
- [ ] A rejected CSRF request or server failure preserves inputs and shows a nearby error. Failed requests do not falsely update saved copies or summary totals.
- [ ] Tests verify enhanced failure/authentication responses do not redirect the drafting page, drafts remain available, permissions are rechecked on retry, and successful responses still synchronize affected displays. Manually verify transport behavior that server tests cannot prove.
- [ ] Run the full suite, Ruff checks, and CSS build as applicable. Browser-check create, edit, delete, staff moderation, loading, conflicts, and recovery together; repeat ordinary CRUD with HTMX disabled. Confirm no additional JavaScript was introduced.
