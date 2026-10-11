# Phase 1 email verification

Signup continues to use Django UserCreationForm and username authentication, with the existing password validators. Verification uses Django timestamp signing with a 24-hour lifetime and is bound to the account ID and exact current email. Verification never signs anyone in. Resending leaves earlier links to the same unchanged address usable until expiry; repeated verification is harmless.

## Migration policy

0002 preserves account IDs, roles, password hashes, and all cart/order relationships. All existing addresses start unverified. Valid unique addresses are trimmed and lowercased. Every member of a duplicate normalized-address group, and every invalid address, has its original value retained in the non-editable legacy_email field and its assigned email cleared. No duplicate claimant is arbitrarily preferred. Empty addresses remain empty. Phase 2 will supply the correction interface. The migration does not rewrite historical order email snapshots. Reversing the schema does not restore conflicting email assignments automatically.

## Limits

Signup POSTs are limited to 10 attempts per rolling hour per REMOTE_ADDR (SECURITY_SIGNUP_LIMIT). All exposed signup and resend POSTs count against 30 requests per rolling hour per REMOTE_ADDR (SECURITY_EMAIL_NETWORK_LIMIT), including invalid forms, suppressed sends, and failed delivery. Signup's initial email belongs to that same request and is not double-counted. Proxy-supplied headers are not trusted.

Attempted email sends share a 60-second cooldown and five-per-rolling-hour maximum for both account ID and normalized destination. Failed sends consume a reservation and become retryable after cooldown. Database transactions write to a singleton mutex before reading limits and recording reservations, serializing workers including on SQLite; transient SQLite contention is retried. Email delivery occurs after committing the reservation. Accounting rows persist; operators may archive rows older than the active hour when needed.

## Email configuration

Without .env, emails print in the development server terminal using accounts.mail_backends.ConsoleEmailBackend, a Django console-backend subclass that keeps verification URLs intact. Django 6's standard console backend can display quoted-printable soft line breaks inside long URLs; the development subclass uses the RFC 998-character line limit when serializing messages. SMTP delivery retains Django's standard email serialization. If EMAIL_BACKEND is explicitly configured for console delivery, use accounts.mail_backends.ConsoleEmailBackend. Configure EMAIL_BACKEND, DEFAULT_FROM_EMAIL, EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, EMAIL_USE_SSL and EMAIL_TIMEOUT for real delivery. Django's SMTP backend is django.core.mail.backends.smtp.EmailBackend. Select TLS or SSL as required by your provider. No provider is selected here.

## Browser check

Run `uv run python manage.py migrate`, then `uv run python manage.py tailwind runserver`. Register at /accounts/signup/ with a fresh username and valid email. Find the verification URL in the server terminal. Before following it, sign in using the username and password and confirm catalog/cart access. Open Verify email in the navigation and try resending immediately (wait feedback), then after 60 seconds (new email). Follow the link while signed in and confirm Email verified and Continue shopping. Open the same link in a private window and confirm it offers sign-in without logging you in. Alter the token in the URL to see invalid-link guidance. Try another signup with the same email in different capitalization and surrounding spaces; it must show This email is unavailable. Missing/invalid email and mismatched/weak passwords must fail validation.

For delivery-failure testing, temporarily configure the SMTP backend with EMAIL_HOST=127.0.0.1 and an unused EMAIL_PORT, then restart the server. Signup should preserve the account and explain retry. Restore console delivery, restart, sign in and retry after 60 seconds. Expiry and concurrent limits are covered automatically; browser testing does not require waiting 24 hours.

This phase does not gate checkout, add an email correction interface, change passwords, or expose password recovery.
