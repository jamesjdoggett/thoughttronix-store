# Phase 5: Replacement email lifecycle

Verified users of every role can request a replacement with their current password, replace a pending request, cancel it, and resend verification. Current email and verification remain active until completion. Pending addresses do not reserve ownership. Atomic claims share the existing database mutex and uniqueness constraint; competing claims return useful unavailable-address guidance. Cancellation and replacement increment a pending revision, invalidating earlier pending links. Resends for an unchanged pending request preserve earlier links for 24 hours.

Completion increments the account email revision, clears pending state, and changes the verified current address. This invalidates account verification links and Django reset tokens (which include the current email). Phase 7 will add direct recovery-flow integration tests. Old-address notification occurs after transaction commit; notification failure is logged and cannot undo or partially apply the claim. Existing account/destination/network limits include replacement requests and resends; invalid replacement forms count toward network limits. Failed delivery preserves pending state for retry.

No Phase 6 password-change flow is introduced.

## Browser verification

1. Run `uv run python manage.py migrate`, then `uv run python manage.py tailwind runserver`. With the default console backend, email links appear in the server terminal.
2. Sign in with a verified account (or register and verify first). Open `/accounts/security/`, select Change email, and try an incorrect current password, an invalid email, and an address already assigned to another account. Each should show a validation error.
3. Submit a new address with your correct password. Confirm the overview shows the current verified address and pending replacement separately. Add an item and open checkout: access and cart contents should remain available.
4. Open Verify replacement email and resend immediately. Confirm cooldown feedback. Wait at least 60 seconds and resend; hourly and network limits still apply.
5. Copy a pending verification link, cancel the change, and open that link. It must be invalidated. Request another replacement, copy its link, then choose Change email again and request a different replacement. The earlier pending link must again be invalidated.
6. Open the newest link. Confirm the new address is verified, pending state disappears, and the terminal shows a notification addressed to the old email. Reopening that completed link must not repeat the change or notification.
7. In two accounts, request the same currently unused replacement address before opening either link. Both requests may be staged. Open the first link, then the second: only the first succeeds; the second explains that another address is needed.
8. Open a valid link in a private browser window. Verification must not sign you in. Repeat the core flow with an employee and administrator.

Automated tests cover expiry, sending/notification failures, token invalidation, shared limits, retained recovery eligibility, and simultaneous competing claims.
