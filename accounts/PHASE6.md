# Phase 6: Signed-in password changes

Account security now links to Change password for every signed-in role, including accounts with missing or unverified email. Django's PasswordChangeForm uses the existing configured validators and checks the current password and new-password confirmation. PasswordChangeView saves the credential and updates the submitting session's authentication hash. Other sessions lose authenticated access on their next request; changing the password also invalidates Django password-reset tokens. Pending email replacements remain pending.

Alerts go only to the current verified recovery address, never to a pending replacement. Delivery failures (including a backend returning zero sent messages) are logged and do not undo credential changes. Alerts contain no passwords or reset links. No migrations or Phase 7 recovery endpoints are introduced; recovery guidance remains informational.

## Browser verification

1. Start `uv run python manage.py tailwind runserver`. Local defaults print emails in the server terminal.
2. Sign in to the same account in a regular browser window and a private window. Open Account security in both.
3. Select Change password. Try an incorrect current password, mismatched confirmation, fewer than eight characters, a common password, a numeric password, and one similar to your username. Confirm errors and that your original password still works.
4. Submit the correct current password and matching acceptable new password. Confirm the success message and that the submitting window can still open Account security.
5. Refresh Account security in the other window. It should redirect to sign-in. Confirm the old password fails and the new one works.
6. With a verified email, confirm the terminal displays a password-change alert addressed to the current email with no password or recovery link. If a replacement email is pending, confirm the alert goes to the current address and the pending request remains.
7. Repeat with an unverified account or one without email: changing the password should succeed without an alert. Repeat with employee and administrator accounts.
8. Sign out and visit `/accounts/security/password/`: it should require sign-in. The form's forgotten-password guidance must not link to a recovery page yet.

Automated tests cover independent sessions, all roles, existing password validators, reset-token invalidation, notification eligibility and delivery failures, ownership isolation, and CSRF enforcement. Recovery links issued through a public reset flow remain Phase 7 work.
