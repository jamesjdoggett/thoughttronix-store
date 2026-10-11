# Phase 3: Verification feedback and failure recovery

Signed-in verification and email-correction requests now identify account cooldown, destination cooldown, account hourly, destination hourly, or network suppression and state the seconds until retry. When account and destination limits overlap, feedback reports the longer wait. Waits are calculated using the same database reservation that enforces the limits. Invalid forms, verified/missing-address requests, failed delivery, and suppressed requests still count at the network level. Repeated network requests may extend the wait; they do not consume extra send reservations when suppressed.

The 60-second cooldown and rolling-hour windows permit a send exactly at the boundary. Verification links remain valid at exactly 24 hours and expire afterward, following Django timestamp-signing behavior. Send reservations refresh account state under the database mutex so a stale request cannot reserve delivery for a previously corrected or already verified address.

## Link policy

Resending for an unchanged address leaves earlier unexpired links valid. The first valid visit verifies the signed account and current address; subsequent visits report that the email is already verified and make no account changes. Correction advances the Phase 2 revision counter and permanently invalidates earlier links, including when returning to an old address. Expired links, malformed links, and superseded/unavailable links have separate recovery guidance. Signed payload structure is checked before querying account data.

Public links never authenticate their recipient. A different signed-in account remains unchanged and receives sign-in guidance. Verification takes a database write lock before reading account state, including on SQLite, so simultaneous visits finish with one verification and one already-verified result. Transient SQLite lock contention is retried.

Email backends that raise an exception or report zero accepted messages are treated as delivery failures. Account/address state and attempted-send accounting remain intact. Retry after the cooldown, subject to hourly and network limits. This phase adds no schema migration and leaves checkout behavior for Phase 4.

## Browser verification

1. Run `uv run python manage.py migrate` if earlier migrations are pending, then `uv run python manage.py tailwind runserver`. With default settings, email links print in the server terminal.
2. Sign in with an unverified account that has a valid email. Open Account security, then Verify email. Confirm the resend policy and limit guidance. Send a link and immediately resend: feedback should identify the account cooldown and give the remaining seconds. Wait at least 60 seconds and resend successfully.
3. Keep both links. Open the earlier link while signed in to the matching account: it should verify the address and offer Continue shopping. Open either link again: it should say the email is already verified. A resend POST from a previously opened Verify email tab should say no new email is needed.
4. Open a valid link in a private window: verification must not sign you in. Open it while signed in to another account: that session must stay on its own account, with sign-in guidance for the link's account. Its security overview must remain unchanged.
5. For another unverified account, retain a link, then correct its email using the current password. The retained link should report that it was invalidated or is no longer available. Change back to the old address and confirm the old link still fails. Alter a character in a token to see complete-link and resend guidance.
6. To check hourly feedback, use a fresh unverified account, send five times at least 60 seconds apart, then request again. It should identify the five-per-hour account limit and show remaining seconds. Suppression must leave the address unverified and saved. Account and destination boundary cases are covered automatically.
7. For a shorter network-limit check, temporarily set `SECURITY_EMAIL_NETWORK_LIMIT=2` in local environment configuration and restart. Use a fresh account/session/network window; if prior requests already count, wait for the displayed window to clear. Repeated requests should identify network suppression and a retry time even when no message is sent. Restore the setting afterward. Suppressed requests also count, so repeated attempts can extend this wait.
8. To simulate delivery failure, temporarily use `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST=127.0.0.1`, and an unused `EMAIL_PORT`, then restart. Request verification (or correct an unverified address): failure guidance must preserve the saved address. Immediate retries must show cooldown feedback. Restore console delivery, restart, wait at least 60 seconds, and retry successfully, subject to other limits.

Expiry at 24 hours, exact rate boundaries, malformed signed payloads, shared destination limits, and simultaneous requests are automated checks; browser verification does not require waiting a full day or reproducing concurrency manually.
