# Phase 2: Security overview and account adoption

All signed-in roles share /accounts/security/. Unverified users receive an adoption prompt after username sign-in without changing their redirect destination or access to purchases and carts. Password changes, recovery, verified-address replacement, and checkout gating remain later phases.

Adding or correcting an unverified email requires the current password. Email validation and normalization match signup; the existing database uniqueness constraint arbitrates competing claims. Conditional updates reject stale account state, including verification, another correction, or password changes during submission. Legacy evidence remains intact and historical order email snapshots are untouched.

Migration 0003 adds an email revision counter. Each correction advances it so previous verification links cannot become usable again if the account returns to an earlier address. Phase 1 links without a revision remain usable only at revision zero. Same-address resends retain the Phase 1 policy.

Correction POSTs count network requests even for invalid forms. Delivery reuses the existing account/destination limits without double-counting the network request. A suppressed or failed send preserves the correction; retry from Verify email after the applicable wait.

## Browser verification

1. Run `uv run python manage.py migrate` and `uv run python manage.py tailwind runserver`. Default console email delivery prints links in the server terminal.
2. Sign in with an existing unverified account. Confirm the add-or-verify prompt and Account security navigation. Open it and check the current email (or missing-address state), Unverified status, and password guidance.
3. Open Add or correct email. Try a wrong current password, invalid email, and an email assigned to another account with different capitalization and surrounding spaces. Each must show an error and preserve the current address.
4. Submit the correct password and an available address. Confirm the saved normalized email, then follow the terminal's verification link. Return to Account security and confirm Verified. No email correction form should remain available for this verified account.
5. To check stale links, use another unverified account: send verification, retain its link, then correct the address before following it. The old link must fail. Changing back to the original address must not revive it. Rapid corrections/resends should show wait feedback; after 60 seconds, retry from Verify email.
6. Confirm existing cart contents and order history remain intact. Repeat the overview and adoption flow with employee and administrator accounts. In a private window, /accounts/security/ and /accounts/security/email/ must redirect to sign-in.
7. For delivery failure, temporarily configure Django's SMTP backend with localhost and an unused port, then restart. Submit an available correction: the address must persist with a failure message. Restore console delivery, restart, and retry from Verify email after the cooldown.

Automated coverage includes legacy missing/invalid/duplicate-evidence states, role access, ownership isolation, password and email validation, uniqueness conflicts, stale links, sending failures, rate limits, and preserved account/cart/order data. Tests never seed the database.
