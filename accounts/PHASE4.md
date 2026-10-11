# Phase 4: Verified checkout and continuation

Checkout GET and POST require verified email for every role, before pricing or coupon actions. HTMX requests use HX-Redirect to open the full Security Center. The transactional order service checks persisted verification state after obtaining its write lock, so stale caller objects and zero-total purchases cannot bypass eligibility. Rejection preserves cart lines and coupon selection. Order email snapshots are unchanged.

Security controls carry only `next=/checkout/`; all other destinations are ignored. Correction and resend preserve this continuation. Successful verification (including a repeat visit) offers Continue to checkout only to the matching signed-in account. Other visitors receive sign-in guidance with a fixed local checkout destination; verification never authenticates them.

Existing order regression fixtures use a verified customer within the orders test directory. Explicit unverified tests cover all roles, GET/POST, HTMX, service calls, stale state, zero totals, retained history, cart mutations, login, correction/resend continuation, and rejected external destinations. No schema changes or Phase 5 behavior are introduced.

## Browser verification

1. Run `uv run python manage.py migrate`, then `uv run python manage.py tailwind runserver`. Default console email delivery prints links in the terminal.
2. Register or sign in with an unverified account. Add a product, change its quantity, and view order history. These remain available.
3. Open `/checkout/`. Confirm Account security explains verification is required and the cart is saved. Use Add or correct email if needed, entering your current password; otherwise choose Verify email. The checkout reminder should survive correction and resend.
4. Open the emailed link in the same signed-in browser. Click Continue to checkout. Confirm the cart remains intact, then submit a valid checkout. Try a valid coupon as well; totals and confirmation should work as before.
5. Open the link again in a private window or while signed in as another account. Confirm it offers sign-in guidance, does not authenticate the visitor or switch accounts, and does not show Continue to checkout directly.
6. Repeat the unverified checkout gate using an employee and an administrator. Visit `/accounts/security/?next=https://example.com`; it must offer no external continuation.

Automated tests exercise direct POST/service attempts, HTMX redirects, stale account state, and zero-total rejection without needing crafted browser requests.
