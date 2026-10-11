## Problem Statement

ThoughtTronix customers currently register and sign in with a username and password, without providing an email address. They have no storefront interface for changing their password or recovering a forgotten password. Losing a password can therefore mean losing access to their account and order history.

Customers need a clear place to manage their recovery address and password, confidence that the recovery address belongs to them, and notification when their password changes. Existing accounts must be able to adopt these capabilities without losing access to their past purchases.

## Solution

Provide an Account Security Center for customers, employees, and administrators. Keep username-based sign-in, require a unique email at signup, and verify ownership through an emailed link. Allow signed-in users to view their email and verification status, correct or change their email, resend verification, and change their password.

Users may sign in, browse, manage their cart, and view order history before verification, but checkout requires a verified email. Forgotten-password recovery sends a time-limited link to the verified address. Email verification and password-change alerts are the two additional security features explicitly agreed during the interview.

## User Stories

1. As a new customer, I want to register with a username, password, and unique email, so that I can keep using username login and have an account recovery address.
2. As a customer, I want to verify my email through an emailed link, so that my recovery address is confirmed as mine.
3. As an unverified customer, I want to browse and manage my cart before verification, so that I can prepare a purchase before completing account setup.
4. As a customer approaching checkout, I want a clear verification requirement and a way to continue afterward, so that I can complete my purchase.
5. As an account holder, I want one overview of my email, verification status, pending email change, and password controls, so that I can understand and manage my account security.
6. As an unverified account holder, I want to correct a mistyped email after confirming my password, so that I can verify the right address without creating another account or losing my cart.
7. As a verified account holder, I want to verify a replacement email while my current email remains active, so that I retain recovery access during the change.
8. As an account holder, I want to cancel or replace a pending email change, so that I can correct mistakes without waiting for expiration.
9. As an account holder, I want to resend verification and recover from expired links or temporary sending failures, so that I can finish setup when email is available.
10. As an existing account holder, I want to add or verify my email while retaining access to my account and order history, so that I can adopt the new security requirements without losing access to past purchases.
11. As a signed-in account holder, I want to change my password by supplying my current password and confirming the new one, so that I can update my credentials securely.
12. As an account holder who forgot my password, I want to reset it through my verified inbox, so that I can regain account access.
13. As an account holder, I want password reset requests to avoid revealing whether my email is registered or verified, so that my account information remains private through that flow.
14. As an account holder, I want other sessions signed out after a password change and all sessions signed out after a reset, so that old sessions no longer retain access.
15. As an account holder, I want email alerts after password changes and resets and notification at my old address after an email change, so that I can notice unexpected changes.
16. As an account holder, I want limits on security email requests, so that these features cannot easily be used to flood my inbox.
17. As an employee or administrator, I want the same self-service security controls as customers, so that I can manage my own credentials and recovery address.
18. As a store operator, I want configurable real email delivery with working local development defaults, so that deployed users receive email and developers can run the app without email credentials.

## Implementation Decisions

- Extend the existing accounts functionality rather than introducing a separate identity system. Customers, employees, and administrators use the same Security Center and email recovery rules. Preserve the existing Django staff and superuser role model.
- Keep username-based login. Signup requires a unique email in addition to the existing username and password fields.
- Compare email addresses without regard to capitalization or surrounding spaces across signup, email changes, and recovery. Preserve dots and plus suffixes rather than applying provider-specific transformations.
- For an email already assigned to another account, signup displays “This email is unavailable” and links to sign-in and password reset. This deliberately accepts disclosure of email availability through signup. Limit repeated signup attempts; a separate numeric signup limit was not selected during the interview.
- Provide a signed-in “Account security” navigation link. The overview shows the current email, verification status, password controls, and any pending replacement email separately. Dedicated forms may handle individual actions.
- Verification is required for checkout, including storefront purchases by staff. Unverified users retain sign-in, catalog, cart, and order-history access.
- Existing users are prompted to add or verify an email after signing in. Do not automatically trust previously stored addresses. Missing, invalid, or duplicate existing addresses must be corrected before verification and checkout. Email recovery remains unavailable until an address is verified.
- Correcting an unverified email requires the current password and an available unique address. Send verification to the corrected address and invalidate verification links for the previous address. Preserve the account and cart.
- Changing a verified email requires the current password and verification of the replacement. The current verified address remains active for recovery, and checkout remains available until the replacement is verified.
- Permit cancellation or replacement of a pending email change. Either action invalidates links for that pending request.
- Pending changes do not reserve the replacement address. Assign it only after successful verification and an availability check. If it has become unavailable, explain that another address must be chosen. Where multiple requests target the same unused address, only the first successful verification may claim it.
- After an email change completes, notify the old address and invalidate outstanding password-reset and email-verification links for the account.
- Email-verification links expire after 24 hours and can be resent. A valid link verifies the address without automatically signing anyone in. If the matching account is already signed in, offer an appropriate next step, including “Continue to checkout”; otherwise, direct the user to sign in.
- Password changes require the current password, a new password, and confirmation of the new password. Users who cannot supply the current password use email recovery.
- Retain the existing password policy: minimum eight characters, with checks against common passwords, entirely numeric passwords, and passwords too similar to account details. Apply it consistently to signup, password changes, and resets. Existing passwords remain usable until changed.
- A normal password change preserves the current session and signs out other sessions. A successful password reset signs out all sessions and returns the user to sign-in without automatic login.
- The forgotten-password page accepts an email address and always shows the same confirmation, such as “If an eligible account matches that email, we’ll send a reset link.” Send reset email only for an account with a verified address. Explain generally that recovery requires a verified email and provide a sign-in link without disclosing the submitted address’s status.
- Password-reset links expire after 24 hours. Requesting another link does not invalidate earlier links. Each link works only once; a successful password change or reset invalidates all outstanding reset links. Expired-link pages provide a way to request another email.
- A successful password reset also cancels any pending email change, preventing an earlier request from subsequently replacing the recovery address.
- Send a password-change alert to the verified email after both normal changes and forgotten-password resets. Alerts contain neither passwords nor reset links.
- For verification and recovery emails, enforce a 60-second cooldown between sends and at most five sends per hour per account or destination address. Supplement these with a configurable limit of 30 email requests per hour per network address. Count network-level requests even when no email is sent.
- Password-reset responses remain generic when limits suppress delivery. Signed-in verification requests can show a clear wait message.
- Support real email delivery through configuration, retaining console delivery for local development. The app must still run without an environment configuration file. Deployment requires an email provider and sender address; no provider was selected during the interview.
- If email delivery fails, preserve the created unverified account or pending email change and allow retrying. Signed-in verification flows explain sending failures; reset requests retain their generic response. Failure to deliver a password-change alert does not undo a successful password change.
- Follow the existing Django architecture and presentation conventions: forms own validation, views remain thin, model or manager behavior owns local logic, and cross-model workflows use services as appropriate. Use the existing page shell, Tailwind and DaisyUI styling, named namespaced URLs, and HTMX only where needed. No specific new internal component structure was selected during the interview.

## Out of Scope

- Switching login from usernames to email addresses.
- Manual support recovery or another recovery method when a user lacks access to their verified inbox. Explain this boundary and suggest recovering the email account first.
- Additional security features beyond the agreed email verification and password-change alerts, such as multifactor authentication, passkeys, a device-management interface, or recovery codes.
- New password complexity requirements or a longer minimum password length.
- Automatically signing users in through verification or password-reset links.
- Selecting an email-delivery vendor during this design exercise.

## Further Notes

The 24-hour password-reset lifetime was an explicit user choice. The design intentionally keeps earlier reset links usable when a new link is requested, until expiration or a security event invalidates them.

Email privacy differs deliberately by flow: reset requests conceal account eligibility, whereas signup reveals that an email is unavailable. Implementations must preserve this agreed distinction.

The interview did not choose a precise signup-attempt limit, whether resending verification invalidates earlier links for the same unchanged address, or the operational procedure for resolving pre-existing duplicate email records. These details must remain consistent with the agreed uniqueness, ownership-verification, and link-invalidation rules rather than being treated as additional approved scope.

This PRD records the completed design interview. Creating the implementation plan and implementing the feature are deferred to later assignment steps; they are not out of scope for the feature. This assignment step produces only the PRD and does not authorize those later steps yet.
