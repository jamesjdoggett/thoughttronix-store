# PRD: Customer Wishlist

## Problem Statement

Customers need to remember products they are interested in without putting them in a cart intended for a purchase. They need a persistent place to return to those products, manage their interests, and optionally share the products with others without exposing their account information.

## Solution

Give each signed-in account one personal wishlist, accessible from the navbar and saved across visits and devices. Customers can save or remove products while browsing and review a compact list of saved products with current prices and availability. Adding a product to the cart leaves it saved.

Wishlists start private. Owners can explicitly enable a read-only sharing link, disable it to revoke access, and enable sharing again to obtain a new link. Anyone with an active link can view the products without signing in, but cannot identify the owner or modify the list.

## User Stories

1. As a signed-in customer, I want one persistent personal wishlist, so that I can return to products across visits and devices.
2. As an unverified account holder or staff member, I want to use my own wishlist without additional account requirements, so that I can save products immediately after signing in.
3. As a customer, I want to save products from catalog cards and product detail pages, so that I can record interest wherever I browse.
4. As a customer, I want buttons to show whether a product is saved and let me remove it with another click, so that I can manage interest in place.
5. As a customer, I want repeated saves to keep one entry without changing its position, so that double-clicks and actions in multiple tabs do not duplicate or reorder products.
6. As a signed-out visitor, I want a "Sign in to save" link that returns me to the product after sign-in, so that I can deliberately save it using my signed-in account.
7. As a customer whose session expires, I want to sign in and return before retrying my action, so that an earlier action is not silently applied to a different account.
8. As a customer, I want a navbar wishlist link with a saved-product count, so that I can find my list and confirm saves at a glance.
9. As a customer, I want compact rows with images, names, current prices, availability, and relevant actions, so that I can review and manage my list easily on desktop and mobile.
10. As a customer, I want the most recently saved products first and 20 products per page, so that recent interests are easy to find and long lists remain manageable.
11. As a customer, I want immediate save and removal updates with ordinary forms as a fallback, so that I can use the wishlist with or without HTMX.
12. As a customer, I want to add an available saved product to my cart without removing it from my wishlist, so that preparing a purchase does not erase my saved interest.
13. As a customer, I want previously saved unavailable products to remain clearly labeled, so that I retain my interest if they become available again.
14. As a customer, I want helpful feedback if a product becomes unavailable before my save completes, so that I understand why it was not added.
15. As a customer, I want permanently deleted products removed from my wishlist, so that it contains no dead entries.
16. As a customer, I want only me to access and manage my private wishlist, so that other customers and staff cannot inspect or change it through private wishlist features.
17. As a wishlist owner, I want to enable sharing explicitly and revoke the link later, so that I control whether others can view my products.
18. As a wishlist owner, I want sharing controls and a selectable sharing link on my wishlist page, so that sharing does not require a separate settings page.
19. As a wishlist owner, I want shared pages to omit my username, email, and account details, so that sharing products does not identify my account.
20. As a shared-link visitor, I want to view saved products without signing in and open available products in the catalog, so that I can explore the owner's interests without changing their list.
21. As a shared-link visitor, I want unavailable products to show their name, image, current price, and an "Unavailable" label without a product link, so that I can understand the complete list without a buying action.
22. As a visitor with an invalid or revoked sharing link, I want a helpful "Wishlist unavailable" page with a catalog link, so that I can continue browsing without learning private account or sharing history.
23. As a wishlist owner, I want an empty-state explanation and a "Browse products" link, so that I know how to start saving.
24. As a shared-link visitor, I want an empty list to say "No products saved" and link to the catalog, so that an empty shared page still provides a useful next step.
25. As a customer, I want to save products without notifications or an arbitrary list-size limit, so that saving remains a simple record of interest.

## Implementation Decisions

- **Components and architecture:** Add wishlist functionality with its own Django URL namespace, models, class-based views, forms where validation is needed, full-page templates, and HTMX partials. Integrate with the existing account model, catalog cards including category listings, product detail pages, navbar, and cart behavior. Keep domain logic in models and managers and views thin; follow the existing architecture rather than introducing another deliberate deep module.
- **Ownership:** A wishlist has a one-to-one relationship with the configured user model. Each saved-product entry belongs to a wishlist and references an existing product. Entries record when they were saved. Sharing settings belong to the wishlist rather than the user.
- **Database integrity:** Enforce one wishlist per account and a unique wishlist/product pair at the database level. Repeated saves, including simultaneous requests, leave one entry and preserve its original save time. Entries represent membership, not quantities. Removing and later saving again creates a fresh save time.
- **Deletion:** Deleting an account cascades to its wishlist and entries and invalidates its sharing link. Deleting a wishlist removes its entries. Permanently deleting a product cascades to its saved entries; no product-name or price snapshot is retained.
- **Authentication:** Any authenticated account can use its own wishlist, including unverified accounts, staff, and administrators. Guest wishlists and verification requirements are not part of this feature. Existing checkout verification requirements continue to apply at checkout.
- **Authorization:** Resolve private lists and entry mutations through the authenticated owner. Never accept a supplied owner identity as authority. Staff status grants no additional wishlist access. A sharing token grants read-only access to the corresponding shared page and never authorizes mutations.
- **Page addresses:** The owner's page is `/account/wishlist/`, exactly as chosen, despite existing account routes using a plural accounts prefix. Shared pages use `/wishlists/shared/<random-token>/`. Use named Django routes in a wishlist namespace. Product links use existing slug-based catalog URLs. Mutation route spelling remains an implementation detail.
- **Request safety:** Save, remove, enable sharing, and disable sharing require POST and CSRF protection. GET requests do not perform those user actions. Validate any return destination used for sign-in or form fallback as a local destination.
- **Signed-out and expired-session behavior:** Catalog cards and product detail pages show signed-out visitors a "Sign in to save" link. After sign-in, return to the product and require a fresh Save click. If a session expires before an action, perform a full-page sign-in redirect, including for an HTMX request, then return without replaying the action. Never carry a pending mutation across account switching.
- **Save controls:** Available products show "Save to wishlist" or "Saved" according to the current account's membership. Clicking "Saved" removes immediately without confirmation. Use explicit save and remove operations rather than interpreting a retried save as a toggle, so duplicate save requests cannot undo a save.
- **Availability:** Only currently available products can be newly saved; validate availability when processing the request and give helpful feedback if it changed after page load. Existing saved unavailable products remain visible and removable. Their buying actions are disabled until availability returns. A deleted product cannot be newly saved.
- **Catalog boundary:** The current public catalog and detail views include unavailable products. This feature does not change that existing behavior. The decision to omit unavailable-product links on shared wishlists is a wishlist presentation rule, not a catalog restriction.
- **Live product data:** Read names, images, prices, and availability from current product records rather than save-time snapshots. Use existing product image behavior, including placeholders. Wishlist prices do not reserve or lock a purchase price.
- **Navbar:** For authenticated users, show a direct wishlist link with the total number of distinct saved products across all pages, including unavailable products. Update it after successful save and removal actions. Do not require a wishlist record merely to display a zero count.
- **List presentation:** Owner and shared pages use compact product rows, most recently saved first, with deterministic ordering when save times tie. Both paginate at 20 products. Owner rows show relevant individual management and cart actions; shared rows show viewing controls only. There is no explicit product-count cap.
- **Cart integration:** Owner rows provide Add to cart for available products, using existing cart rules, including incrementing an existing cart line. A successful cart addition leaves the wishlist entry intact and updates the cart feedback. Unavailable products cannot be added to the cart. Shared pages do not offer direct add-to-cart or save-to-my-wishlist actions; visitors use available product links to reach the regular catalog controls.
- **HTMX and fallback:** Save and removal update relevant controls, list contents, empty states, and the navbar count in place. Ordinary POST forms provide full-page behavior when HTMX is unavailable. After removal, pagination must still resolve to a valid page, including when the last row on the current page is removed. Sharing controls and owner-page cart actions must also remain usable through ordinary forms. Use Tailwind and DaisyUI styling and no JavaScript beyond HTMX.
- **Sharing lifecycle:** Lists are private by default. Enabling sharing creates a unique, cryptographically hard-to-guess token with no account identifier. An active link shows the current list rather than a frozen snapshot. Disabling sharing invalidates that link; enabling again produces a new token, and earlier links remain invalid. Owners manage this on their wishlist page through Enable sharing, a selectable link, Open shared page, and Disable sharing.
- **Shared-page privacy:** Anyone holding an active link can view without signing in, including another account or the owner. Use a generic "Shared wishlist" title and omit the owner's username, email, greeting, and other identifying account information. Ensure the shared-page content does not expose the owner's identity through the normal site shell. This does not remove the ordinary signed-in viewer's own navigation or disclose another user's private wishlist.
- **Shared unavailable entries:** Show their current name, image, price, and "Unavailable" label without a product link or buying action. Permanently deleted products disappear from shared pages as they do from owner pages.
- **Invalid sharing links:** Invalid tokens, disabled sharing, and deleted owners all produce the same generic "Wishlist unavailable" page with an HTTP 404 response and a catalog link. Do not distinguish account existence or revocation history.
- **Empty states:** Owner pages explain how saving works and offer Browse products. Shared pages say No products saved and link to the catalog, without owner-specific guidance or identity. Enabled sharing can remain active for an empty list.
- **Template conventions:** Full pages use the existing project shell and night theme. HTMX responses use app partials that do not extend the full-page shell. Keep controls clearly labeled and usable on mobile.

## Out of Scope

- Guest or browser-local wishlists, guest-to-account merging, and automatic save or removal after sign-in.
- Multiple named lists, custom list titles, notes, quantities, manual ordering, and alternative sort controls.
- Publicly discoverable wishlist directories, owner lookup, owner identity on shared pages, collaborative editing, and staff oversight of private wishlists.
- Shared-page shortcuts to save to the viewer's wishlist or add directly to their cart.
- Automatic removal when adding to cart or purchasing, bulk removal, Clear wishlist, Add all to cart, and removal confirmation dialogs.
- Price-drop alerts, restock alerts, email subscriptions, suggested products, and wishlist analytics.
- Historical records for deleted products, saved-price snapshots, inventory reservations, and purchase-price guarantees.
- Changes to the catalog's existing visibility rules, checkout requirements, or account security policies.
- A separate sharing settings page, clipboard scripting, and custom JavaScript beyond HTMX.

## Further Notes

This PRD records the decisions reached in the wishlist interview. It does not authorize implementation or introduce an implementation plan.

The existing store provides useful precedents: one cart per user, database uniqueness for cart/product membership, owner-scoped cart and order access, HTMX partial responses and navbar badge updates, and cascading product deletion from carts. Completed orders intentionally preserve historical product information; wishlists instead use live catalog data.

An earlier interview statement incorrectly said the public catalog excludes unavailable products. Repository inspection confirmed that current catalog and detail views do not apply that restriction. The agreed wishlist behavior remains as stated above; no catalog change is implied.

Implementation validation should cover account eligibility and owner isolation, POST and CSRF requirements, repeated and concurrent saves, availability changes, cascading deletion, sharing defaults and revocation, shared-page privacy, authentication redirects without action replay, cart independence, pagination, counts, empty states, and HTMX versus ordinary-form behavior. Follow the project's pytest and shared-fixture conventions, never invoke the demo seed command in tests, and keep the suite green at implementation phase boundaries.
