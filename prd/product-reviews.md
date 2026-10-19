# PRD: ThoughtTronix Product Reviews

## Problem Statement

Customers cannot share their experiences with purchased products or read other purchasers' feedback on product pages. ThoughtTronix needs trustworthy reviews tied to actual purchasing accounts, customer control over their own feedback, and staff moderation. Writing or managing a review should not reload the product page, discard a draft, or make readers lose their place.

## Solution

Add public customer reviews to each product detail page. Each purchasing account may have one review per product, containing a whole-star rating and a written comment. Eligible customers publish immediately and manage their own reviews inline; staff can edit or delete any review in the same location.

Use HTMX to update affected reviews, the customer's dedicated review area, and the rating summary without full-page navigation. Provide standard-form fallbacks when HTMX is unavailable.

## User Stories

1. As a visitor, I want to read reviews on a product detail page without signing in, so that I can assess others' purchase experiences.
2. As a visitor, I want to see the average rating and review count, so that I can quickly understand overall feedback.
3. As a reader, I want to see each reviewer's username and a Verified purchaser label, so that I can distinguish reviewers and understand their eligibility.
4. As a reader, I want reviews ordered newest first with ten initially visible and a Load more button, so that I can browse recent feedback without loading everything at once.
5. As a purchasing customer, I want to publish one review per product with a rating and comment, so that I can share my experience without duplicate reviews from my account.
6. As a purchasing customer, I want to review as soon as my order is placed, so that I do not have to wait for staff to update fulfillment status.
7. As a customer, I want review eligibility tied exclusively to my own purchasing account, so that gifts, inheritance, and another person's order do not grant posting rights.
8. As a SoulSear purchaser, I want the same review eligibility as other purchasers, so that the product line does not exclude my feedback or transfer my rights to next of kin.
9. As a past purchaser, I want to review an unavailable product, so that the end of sales does not prevent me from sharing my experience.
10. As a purchaser with an unverified current email address, I want my qualifying purchase to be sufficient for reviewing, so that a separate verification check does not block me.
11. As a review author, I want my existing review to remain visible and editable if my order is later cancelled, so that cancellation does not suppress my feedback.
12. As a review author, I want a dedicated Your review area above the public list, so that I can manage my review without searching through loaded batches.
13. As a review author, I want to edit only my own review using an inline form with Save and Cancel, so that I can revise my feedback without losing my position.
14. As a review author, I want validation errors beside the fields with my inputs retained, so that correcting a mistake does not require rewriting my review.
15. As a review author, I want to confirm deletion inline and cancel if necessary, so that an accidental click does not erase my review.
16. As a customer who deleted a review, I want to create a replacement if I still have a qualifying purchase, so that deletion does not consume a lifetime review allowance.
17. As a staff member, I want to edit or delete any customer's review on its product detail page, so that I can moderate feedback in context.
18. As a reader, I want staff edits identified, so that I know when staff have changed a customer's feedback.
19. As a staff member who purchases products, I want to post my own reviews under the same eligibility rules, so that moderation privileges neither disqualify me nor bypass purchase requirements.
20. As an editor, I want conflicting saves detected and my unsaved draft preserved alongside the latest saved version, so that concurrent customer and staff edits do not silently overwrite each other.
21. As a customer, I want failed saves to preserve my draft and show a nearby error, so that I can retry after a connection problem or signing in again.
22. As a reader or author, I want review changes and summary totals to update together without a full-page reload, so that the page stays accurate while preserving my place.
23. As a customer without working HTMX, I want standard forms for creating, editing, and deleting reviews, so that the feature remains usable.

## Implementation Decisions

- **Review data and uniqueness:** Persist the product, author, required rating, required comment, creation time, and the state needed for edit-conflict detection and staff attribution. Enforce at most one current review for each author-product pair, including concurrent submissions; this is not a lifetime limit.
- **Rating and comment validation:** Accept whole-star ratings from 1 through 5. Trim surrounding whitespace from comments and require 1–2,000 characters afterward; whitespace-only comments are invalid. Render comments as plain text with line breaks preserved.
- **Purchase eligibility:** At creation, require a signed-in account with an order item linked to the product on its own Placed, Shipped, or Delivered order. Cancelled orders do not qualify. Another qualifying order is sufficient even if other orders were cancelled. Do not infer eligibility from shipping names or the order's contact email.
- **Nontransferable eligibility:** Only the purchasing account qualifies. Gift recipients, inherited owners, and next of kin gain no eligibility from someone else's purchase. SoulSear purchasers follow the same rules as all other purchasers; their next of kin do not inherit review rights. There is no ownership-claim or transfer process.
- **Existing reviews after cancellation:** Check purchase eligibility when creating a review. Once created, the review remains public and its author can continue editing or deleting it even if all qualifying purchases are later cancelled.
- **Account and availability rules:** Do not add a separate current-email-verification requirement. Product unavailability does not prevent eligible creation or management of existing reviews.
- **Authorization:** Customers can edit and delete only their own reviews. Staff, using the existing staff flag, can edit and delete any customer's review. Enforce these permissions on the server, not merely by hiding controls. Staff can create reviews only for themselves and only with a qualifying purchase; they cannot create reviews for another customer.
- **Publication and location:** Publish immediately, without approval. Display reviews publicly on the product detail page. Provide staff moderation controls there, rather than adding a dedicated back-office review screen.
- **Identity and attribution:** Show the author's username and Verified purchaser label. Preserve the customer as author after staff edits. Show Edited by staff after a staff edit and retain the latest staff editor and staff-edit time internally. The label and attribution persist through later customer edits. Do not retain full previous versions.
- **Ordering and loading:** Order by original posting time, newest first; edits do not move reviews. Initially load ten and append ten more per HTMX Load more action. Preserve existing reviews, reader position, and any open form when appending.
- **Your review area:** Show the signed-in author's review and management controls in a dedicated area above the public list, regardless of whether its normal list position has been loaded. The review also appears in its normal public-list position. Update both representations together whenever both are present. Eligible customers without a current review can create one inline in this section.
- **Summary and empty state:** Show the average rating to one decimal place and the total review count above the reviews. Show No reviews yet when empty. Creation, rating edits, and deletion update the summary with the review changes; do not leave duplicate representations or totals stale.
- **Inline editing:** Replace the selected review's text with a form containing Save and Cancel. Cancel restores the saved review without persisting the draft. Validation errors appear near the affected fields and preserve the entered rating and comment.
- **Inline deletion:** Delete first reveals an inline confirmation with Confirm and Cancel. Confirm deletes through HTMX; Cancel leaves the review unchanged. Remove any loaded representations and update the summary and Your review area without full-page navigation or loss of position.
- **Replacement reviews:** After either customer or staff deletion, allow a replacement only if the account meets creation eligibility at that time. Staff deletion does not impose a reposting ban. If all purchases have since been cancelled, the deleted review cannot be replaced until a qualifying purchase exists.
- **Concurrent editing:** Detect when another editor saved after a form was opened. Do not silently overwrite that saved version. Retain the unsaved rating and comment, explain the conflict, and present the latest saved version for comparison before another attempt.
- **Failed requests and expired sessions:** Keep the draft and page position on a failed save and show feedback near the form. On session expiry, allow the customer to sign in in another tab and return to retry rather than navigating the drafting page away. Draft preservation covers failed requests; refreshing or closing the page may discard the draft.
- **HTMX and fallback behavior:** Successful creation, editing, and deletion replace only the relevant page sections and synchronize other affected displays. Normal enhanced operation must not reload the full page or make customers lose their place. Without HTMX, standard forms must still support these actions and return the customer to the product's reviews section after submission.
- **Product deletion:** Permanently deleting a product also deletes its reviews. Existing order-history snapshots remain governed by the current order behavior. A newly created product does not inherit deleted reviews or purchase eligibility from the deleted product. Marking a product unavailable preserves reviews.
- **Existing architecture:** Extend the product detail experience using the existing product, order-item, user, staff-authorization, and HTMX partial-response patterns. Keep views thin, put validation in forms, and follow the repository's model/manager and cross-model workflow conventions. Use named, namespaced URLs, existing page inheritance, Tailwind and DaisyUI styling, and HTMX without introducing additional JavaScript.

## Out of Scope

- Implementing the feature or producing an implementation plan as part of this PRD task.
- Ownership transfers, gift-recipient eligibility, next-of-kin access, and staff-approved ownership claims.
- Prepublication approval, pending reviews, reposting bans, or a dedicated back-office reviews section.
- Staff-created reviews on behalf of customers.
- Fractional-star ratings, review titles, rich text, attachments, replies, and helpfulness voting.
- Rating breakdowns, review search, alternate sorting, and catalog-level rating displays.
- Full revision history, recovery of deleted reviews, and archived reviews for deleted products.
- Draft persistence across refreshes or closing the page.

## Further Notes

The purchasing account is the system's definition of a qualifying purchaser; the feature does not establish who physically received or used the product. Verified purchaser records qualification at creation, not a promise that the order remains uncancelled forever.

The six business requirements are mandatory: one current review per customer per product; both rating and written comment required; purchase-based, nontransferable eligibility including SoulSear owners and excluding their next of kin; customer management restricted to their own reviews; staff editing and deletion of any customer's review; and smooth HTMX creation, editing, and deletion without full-page reloads or lost position.

Future implementation verification should cover those requirements together with cancellation after publication, replacement eligibility, unavailable products, staff attribution, concurrent submissions and edits, both displayed copies of an author's review, summary updates, incremental loading, failed-request draft retention, and standard-form fallbacks. Follow existing pytest and fixture conventions, never invoke the seed command in tests, and keep the suite green at implementation phase boundaries.
