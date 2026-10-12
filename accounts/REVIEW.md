# Account Security Center: complete feature review

Reviewed against all 18 user stories and the implementation decisions in `prd/account-security.md`. The user confirmed Phase 7 passed manual checks before this review. The review changes below require fresh recovery links for browser retesting. No commit is authorized.

## User-story traceability

| Story | Reviewed behavior | Implementation and automated evidence |
| --- | --- | --- |
| 1 | Username signup requires a normalized unique email and Django password confirmation/policy; database uniqueness handles concurrent claims. | `accounts/forms.py` SignupForm; `accounts/models.py` User.Meta; `accounts/test_verification.py` signup, normalization, concurrent claim and password-policy tests. |
| 2 | Ownership links verify only their intended account/address within 24 hours and never log visitors in. | `accounts/verification.py`; `accounts/test_verification.py`; `accounts/test_verification_feedback.py` exact expiry, payload and ownership tests. |
| 3 | Unverified accounts retain username login, catalog, cart mutations and order history. | `accounts/test_verification.py` test_unverified_login_catalog_cart_and_history; `orders/test_verified_checkout.py`. |
| 4 | Checkout UI and transactional order placement reject unverified accounts, preserve carts and offer safe checkout continuation after verification. | `orders/views.py` CheckoutView; `orders/services.py` place_order; `orders/test_verified_checkout.py`, including staff, HTMX, stale state and zero totals. |
| 5 | Signed-in navigation reaches an overview of current email/status, separate pending replacement and actionable password controls. | `templates/base.html`; `templates/accounts/security.html`; `accounts/test_security.py`; `accounts/test_email_replacement.py`. |
| 6 | Correcting an unverified address requires Django current-password verification and an available email; old links fail and cart/account remain. | `accounts/forms.py` EmailCorrectionForm; User.correct_unverified_email; `accounts/test_security.py`. |
| 7 | Verified email replacement requires the current password; old recovery and checkout remain active until atomic verification/claim. | EmailReplacementForm, User.stage_email_replacement, `accounts/verification.py`; `accounts/test_email_replacement.py`; `accounts/test_recovery.py` email-event integration. |
| 8 | Cancel or replace pending requests without reserving the destination; revisions invalidate older links. | User.stage_email_replacement; CancelEmailReplacementView; `accounts/test_email_replacement.py`, including competing claims. |
| 9 | Resend, expiry, superseded/used links, delivery exceptions and zero accepted messages give retry guidance; state survives suppressed/failed sends. | `accounts/verification.py`; `accounts/test_verification_feedback.py`; unchanged-address resends preserve earlier unexpired links. |
| 10 | Migration retains IDs, roles, credentials, carts and order snapshots; invalid/duplicate legacy addresses retain evidence and require correction. | `accounts/migrations/0002_securityrequest_securityrequestlock_and_more.py`; `accounts/test_security_migration.py`; `accounts/test_security.py`. |
| 11 | Django PasswordChangeForm validates current password, matching new passwords and the configured policy. | SecurityPasswordChangeForm; SecurityPasswordChangeView; `accounts/test_password_change.py`. |
| 12 | Only valid active accounts with usable passwords and a verified current email receive Django recovery links; successful reset returns to username sign-in. | `accounts/recovery.py`; RecoveryConfirmView; `accounts/test_recovery.py`, including full signup/verification/checkout/recovery journey. |
| 13 | Unknown, unverified, pending-only, invalid, suppressed and failed-delivery requests use identical generic confirmation and verified-inbox guidance. | RecoveryRequestForm/View; password_reset templates; `accounts/test_recovery.py` generic response and network-accounting tests. |
| 14 | Django PasswordChangeView retains the current session through update_session_auth_hash; Django session hashes reject other sessions. Reset changes the hash without updating any session, invalidates all reset links and cancels pending replacement. | `accounts/test_password_change.py` independent sessions; `accounts/test_recovery.py` independent sessions, simultaneous consumption and pending-link invalidation. |
| 15 | Changes/resets alert only the valid verified current address; email completion notifies the old address after commit. Notification failures never undo changes. | `accounts/passwords.py`; `accounts/verification.py` notify_old_address; password-change, replacement and recovery tests. |
| 16 | Durable shared account/destination cooldown (60 seconds), hourly sends (five), network requests (default 30/hour), and signup attempts (default ten/hour) serialize concurrent requests. Suppressed/ineligible requests count at network level. | SecurityRequestManager; `accounts/test_verification_feedback.py` exact limits/concurrency; `accounts/test_recovery.py` shared limits and concurrent recovery sends. |
| 17 | Customer, employee and administrator accounts use identical self-service controls, ownership checks and verified-checkout requirements. | Role parameterizations in `accounts/test_security.py`, `accounts/test_email_replacement.py`, `accounts/test_password_change.py`, `accounts/test_recovery.py`, `orders/test_verified_checkout.py`. |
| 18 | Environment-configured SMTP backend/sender/TLS/SSL/timeouts; console development defaults and no mandatory .env or vendor. | `config/settings.py`; `accounts/mail_backends.py`; real console-link tests in `accounts/test_verification.py`; delivery-failure coverage across all flows. Real provider delivery requires deployment configuration and was not exercised. |

## Findings and fixes

- Recovery previously used a custom signed-payload and credential-fingerprint implementation. Replaced it with Django PasswordResetTokenGenerator. The only override is hash input: omit last_login so sign-in does not consume a link, and include email_revision so an email change permanently invalidates it even after returning to the same address. Django performs token cryptography, constant-time comparison, expiry and secret-fallback checks. PASSWORD_RESET_TIMEOUT is explicitly 86400 seconds.
- Replaced custom reset confirmation dispatch with Django PasswordResetConfirmView. Django checks each link, stores the secret in the requesting browser's session and redirects to a set-password URL before rendering, preventing the reset secret from leaking through the form URL. Custom code only filters recovery eligibility and atomically updates credentials/pending state; automatic login remains disabled.
- The atomic update already uses inherited User.set_password for Django password hashing. Added Django password_validation.password_changed after the successful update because QuerySet.update bypasses AbstractBaseUser.save's notification hook. SetPasswordForm continues to own confirmation and policy validation.
- Added regression tests for token-free form URLs/browser binding, target-account binding, unusable passwords, password-change hook invocation, older prototype-link retry guidance and malformed requests. Existing expiry, reuse, login independence, sessions, email events, concurrency and role tests now run through Django's confirmation journey.
- Updated stale recovery wording and pending-email punctuation. Ran the requested repository-wide formatter, including the pre-existing formatting-only issue in orders/test_coupon_selector.py.
- Earlier prototype reset links intentionally become invalid; their old URL route now gives a new-request link. No schema or local database changes are needed.

## Reflection: Django components

1. Authentication: `LoginView`, used by SignInView in `accounts/views.py:113`, with SignInForm(AuthenticationForm) in `accounts/forms.py:42`. SignInView calls the parent form_valid at `accounts/views.py:118`; Django's installed source `.venv/Lib/site-packages/django/contrib/auth/views.py:106` calls auth_login at line 108. AuthenticationForm delegates credential checks to Django's authentication backend; the app does not compare login password hashes itself.
2. Authentication/access control: `LoginRequiredMixin` protects SecurityOverviewView in `accounts/views.py:127` and EmailCorrectionView in `accounts/views.py:152`. The installed implementation `.venv/Lib/site-packages/django/contrib/auth/mixins.py:71` checks request.user.is_authenticated and invokes standard no-permission handling. SessionMiddleware and AuthenticationMiddleware are configured in `config/settings.py:52` and `config/settings.py:55`.
3. Password management: `PasswordChangeView`, inherited by SecurityPasswordChangeView in `accounts/views.py:136`, uses SecurityPasswordChangeForm(PasswordChangeForm) in `accounts/forms.py:12`. The parent call at `accounts/views.py:144` invokes Django's form save and update_session_auth_hash (`.venv/Lib/site-packages/django/contrib/auth/views.py:360` and line 364). PasswordChangeForm's current-password check is at `.venv/Lib/site-packages/django/contrib/auth/forms.py:537`; the configured validators start at `config/settings.py:106`.

Recovery also uses PasswordResetConfirmView, PasswordResetTokenGenerator, SetPasswordForm and inherited User.set_password. Email ownership, request limits, pending-state transitions and checkout eligibility remain application policy.

## Final validation

- `uv run ruff format`: 72 files unchanged on the final run.
- `uv run ruff check .`: all checks passed.
- `uv run pytest`: 409 passed in 203.39 seconds, no warnings.
- Focused recovery suite: 35 passed after the review fixes.
- Django system check, migration consistency, forced production CSS build and git diff whitespace checks passed.

No remaining PRD gaps were found in this review. Actual SMTP-provider delivery was not exercised. The user-approved manual pass preceded the recovery refactor; browser retesting should request a fresh email and confirm the redirect to set-password, reset success, and revoked sessions. No commit or push was performed.
