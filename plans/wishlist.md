# Plan: Customer Wishlist

> Source PRD: [Customer Wishlist](../prd/customer-wishlist.md), based on the Define customer wishlist feature discussion.

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app:** A dedicated wishlist Django app owns the feature and its URL namespace. Use class-based views, forms where validation is needed, and domain logic in models and managers. Do not introduce another deliberate deep module.
- **URLs:** The private owner page is `/account/wishlist/`; shared pages use `/wishlists/shared/<random-token>/`. All routes are named in the wishlist namespace. Product links use existing slug-based URLs. Mutation route spelling remains an implementation choice.
- **Models and migrations:** A wishlist has a one-to-one relationship with the configured user model. Each entry references its wishlist and a current product and records its save time. Database constraints enforce one wishlist per account and one entry per wishlist/product pair. Introduce the persistence schema and constraints with the first slice; introduce sharing persistence with the sharing slice. Exact model and field names remain implementation choices.
- **Membership and deletion:** Repeated and concurrent saves preserve one entry and its original save time. Removing and saving again creates a fresh save time. Account deletion cascades to the wishlist and entries; wishlist and product deletion cascade to affected entries. No quantities or product snapshots are stored.
- **Authentication and authorization:** Every authenticated account is eligible, including unverified accounts, staff, and administrators. Resolve private reads and mutations through the authenticated owner. Staff status grants no access to another account's wishlist. Sharing tokens authorize shared-page reads only.
- **Request safety:** Save, remove, enable sharing, and disable sharing require POST and CSRF protection. GET does not perform these actions. Save and remove are explicit operations, not a toggle. Validate sign-in and fallback return destinations as local URLs.
- **Sign-in behavior:** Signed-out visitors return to the product after signing in and must click Save again. Expired sessions trigger a full-page sign-in redirect, including for HTMX requests, and return without replaying a mutation or carrying it across account switching.
- **Live catalog data:** Use current product names, prices, images, placeholders, and availability. New saves require availability at request processing time. Previously saved unavailable products remain visible and removable; deleted products disappear. Existing catalog visibility stays unchanged.
- **Presentation:** Owner and shared lists use compact mobile-friendly rows, newest saves first with deterministic tie ordering, and 20 products per page. Authenticated navigation shows a total distinct-product count including unavailable entries, without requiring a wishlist record just to display zero.
- **Templates and interactions:** Full pages extend the existing project shell and use the night theme, Tailwind, and DaisyUI. HTMX responses use app partials without the full-page shell. Ordinary forms remain usable. No JavaScript beyond HTMX.
- **Cart boundary:** Reuse existing cart rules and feedback. Adding to cart increments existing lines and preserves wishlist membership; unavailable products cannot be added. Existing checkout verification requirements remain in force.
- **Sharing:** Lists start private. Sharing settings belong to the wishlist. Enabling creates a unique, cryptographically hard-to-guess token without an account identifier; disabling revokes it. Re-enabling generates a new token and never restores an older link. Shared pages show the live list, expose no owner identity, and permit viewing only.
- **Scope:** Individual actions only; no guest lists, bulk actions, notifications, explicit list-size cap, purchase-price reservation, or changes to account security policy.
- **Validation:** Each phase includes relevant migrations, model behavior, request handling, templates, and tests as needed to deliver its complete user path. Use pytest and shared fixtures, never invoke the seed command in tests, and keep the full suite green at every phase boundary. Run relevant lint, migration consistency, Django, and CSS build checks when affected.

---

## Phase 1: Save from product details and manage a private list

**User stories:** 1–2, 5–7, 13–16, 23, 25; product-detail portions of 3–4 and ordinary-form behavior from 11.

### What to build

Deliver a complete ordinary-form path from a product detail page to the customer's persistent private wishlist. Customers can save an available product, see its saved state, remove it immediately from the detail page or wishlist, and return across sessions and devices. The owner page presents compact rows using current product data and explains how to begin when empty. Include persistence, database integrity, account eligibility, availability feedback, and safe authentication returns in this first usable slice.

### Acceptance criteria

- [x] Migrations establish one wishlist per account, unique wishlist/product membership, save times, and cascading deletion relationships.
- [x] A signed-in customer, unverified account, staff member, or administrator can save from product details and view or remove their own entries at `/account/wishlist/`.
- [x] Available products show Save to wishlist or Saved as appropriate; Saved submits an explicit removal without confirmation. Ordinary POST forms return to a validated local destination.
- [x] Repeated saves and simultaneous requests leave one entry and preserve its original save time. Removing and saving again records a fresh time. Tests exercise duplicate requests and database integrity, including concurrent-save behavior supported by the configured database.
- [x] Signed-out visitors see Sign in to save and return to the product without an automatic save. Expired-session submissions return through sign-in without replay, including when the next login uses a different account.
- [x] Private access and mutations are owner-scoped; supplied owner identities and staff privileges cannot grant access to another account's list. Mutation GETs and missing-CSRF submissions cannot change membership.
- [x] New saves reject unavailable products with helpful feedback when availability changes after page load; deleted products cannot be saved. Already saved unavailable products remain labeled and removable.
- [x] Owner rows display current names, images or existing placeholders, prices, and availability on desktop and mobile. Empty lists explain saving and offer Browse products.
- [x] Account, wishlist, and product deletion remove the appropriate dependent entries. Saving triggers no notifications and imposes no arbitrary product-count limit.
- [x] Relevant tests and the full existing suite pass.

---

## Phase 2: Save throughout the catalog and navigate long lists

**User stories:** 8–10; remaining catalog/category portions of 3–4.

### What to build

Extend the working save/remove path to catalog cards, including category listings. Add a direct navbar wishlist link with the complete saved-product count, and make long private lists navigable with stable newest-first ordering and 20-product pages. Continue to use ordinary forms so the whole browsing path works without HTMX.

### Acceptance criteria

- [x] Catalog cards and category listings show the current account's Save to wishlist or Saved state and support explicit save/removal forms.
- [x] Signed-out card controls say Sign in to save and return to the selected product after sign-in without applying an action.
- [x] All authenticated accounts see the navbar wishlist link and total distinct saved-product count, including unavailable products across every page.
- [x] Rendering navigation with a zero count does not require creating a wishlist record.
- [x] Successful ordinary-form saves and removals render updated membership and navbar counts on return, preserving a validated local browsing destination.
- [x] Owner rows appear newest first, with deterministic ordering for tied save times, and paginate at 20 products without an explicit total-size cap.
- [x] Removing the last entry on a page returns to a valid remaining page; removing the final entry displays the owner empty state and zero count.
- [x] Tests cover catalog/category controls, account-specific state, counts, ordering ties, pagination boundaries, and deletion effects on counts; the full suite passes.

---

## Phase 3: Update saves and removals with HTMX

**User stories:** 11; immediate-update portions of 4, 7–8, 10, 14, 23.

### What to build

Enhance the established save/remove journeys with immediate partial updates. Catalog and detail controls, owner rows, navbar totals, pagination, and empty states reflect successful actions without a full-page reload. Preserve the ordinary-form path and make authentication expiry and availability changes understandable during asynchronous interactions.

### Acceptance criteria

- [x] HTMX saves and removals update relevant Save to wishlist/Saved controls and the navbar count in place, using app partials that do not extend the full-page shell.
- [x] Owner-page removal refreshes the list, pagination, and empty state as needed, including removal of the last row on the current page or in the entire list.
- [x] Availability changes produce visible helpful feedback and do not falsely mark a rejected product as saved or increase the count.
- [x] Repeated asynchronous saves remain idempotent and do not toggle membership or change the original save time.
- [x] An expired-session HTMX submission triggers a full-page sign-in redirect, returns to a safe viewing destination, and requires a fresh action after login.
- [x] Ordinary forms retain equivalent save/remove behavior when HTMX is absent; POST, CSRF, owner isolation, and local-return validation remain enforced.
- [x] Tests verify partial responses, updated controls and counts, pagination recovery, empty states, authentication redirects, and full-page fallbacks; the full suite passes.

---

## Phase 4: Add saved products to the cart

**User stories:** 12–13.

### What to build

Let an owner add an available saved product to their cart directly from its wishlist row. Apply existing cart rules and update cart feedback while keeping the product saved. Support both HTMX and ordinary forms, including account expiry and changes in product availability.

### Acceptance criteria

- [x] Available owner rows provide Add to cart; adding creates a cart line or increments the existing line according to existing cart rules.
- [x] Successful additions preserve wishlist membership, save time, ordering, and wishlist count.
- [x] Cart feedback and the navbar cart count reflect additions through HTMX; ordinary forms provide a usable full-page result and return to the wishlist.
- [x] Saved unavailable products remain visible and removable but provide no enabled buying action. Requests cannot add a product that becomes unavailable after page load.
- [x] Cart actions require authentication, POST, and CSRF protection and use the authenticated account's cart. Expired sessions return through sign-in without replaying the action.
- [x] Existing checkout verification requirements continue to apply, and purchasing does not remove saved interest.
- [x] Tests cover new and existing cart lines, unavailable products, wishlist independence, feedback, authentication, and ordinary-form fallbacks; the full suite passes.

---

## Phase 5: Enable and revoke private sharing links

**User stories:** 17–22, 24; shared-page portions of 9–10, 13, 15–16.

### What to build

Deliver sharing controls and their public read-only destination together. Owners explicitly enable sharing on their wishlist page, obtain a selectable link, open the shared page, and disable access. Visitors with an active link see the current paginated list without learning the owner's account identity or gaining mutation privileges. Invalid and revoked links lead to the same useful generic unavailable page.

### Acceptance criteria

- [x] Sharing persistence is introduced by migration and defaults existing and new lists to private. Settings belong to the wishlist.
- [x] Owner-page controls provide Enable sharing, a selectable active URL, Open shared page, and Disable sharing without a separate settings page or clipboard scripting. Controls work through ordinary forms.
- [x] Only the authenticated owner can enable or disable sharing, using POST with CSRF protection. A token never authorizes a mutation.
- [x] Enabling produces a unique cryptographically hard-to-guess token with no account identifier. Disabling revokes it; re-enabling generates a new token and all previously revoked links remain invalid.
- [x] `/wishlists/shared/<random-token>/` works without sign-in and for signed-in viewers, including the owner. It reflects current membership and live product data, newest first with deterministic tie ordering and 20 products per page.
- [x] Shared pages use the generic Shared wishlist title and reveal no owner's username, email, greeting, or account identifiers in page content or the site shell. A signed-in viewer's normal navigation still describes that viewer's account.
- [x] Available shared products link to their existing catalog detail URLs. Unavailable entries show their current name, image, price, and Unavailable label with no product link or buying action.
- [x] Shared pages offer no owner management, direct add-to-cart, or save-to-my-wishlist actions. Other accounts and staff cannot use sharing to inspect private owner views or change the list.
- [x] Empty shared lists say No products saved and link to the catalog. Sharing may remain enabled while empty.
- [x] Invalid tokens, disabled sharing, and deleted owners return the same generic Wishlist unavailable page with HTTP 404 and a catalog link, without exposing account existence or revocation history.
- [x] Product deletion removes shared entries; account or wishlist deletion invalidates shared access. Existing catalog visibility remains unchanged.
- [x] Tests cover private defaults, token lifecycle and uniqueness, owner authorization, POST/CSRF, anonymous and signed-in viewing, shell privacy, current data, pagination, unavailable entries, deletion, empty states, and indistinguishable invalid-link responses; the full suite passes.
