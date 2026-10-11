# Plan: Account Security Center

> Source PRD: [Account Security Center](../prd/account-security.md)

The PRD owns requirements; this plan sequences the approved seven vertical slices. Each phase delivers a usable, independently verifiable flow, including persistence and migrations where needed, forms, views, presentation, email behavior, and tests. Basic resend, expired-link guidance, delivery-failure retry, and required request limits belong to Phase 1, before any security email flow is exposed. Phase 3 completes feedback and remaining failure cases. This document authorizes no implementation by itself.

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app and identity**: Extend `accounts` and its existing `User`; retain username login, user identifiers, and Django's `is_staff` / `is_superuser` roles. All roles share self-service controls. Integrate purchase eligibility with `orders`; preserve existing cart and order relationships and historical order snapshots.
- **URLs**: Keep existing named routes under `/accounts/` and the `accounts` namespace. Place the signed-in overview and related actions under `/accounts/security/`; verification and recovery links also live under `/accounts/`. Preserve the existing named checkout route. Exact action paths and names are implementation choices; public links never authenticate their recipient automatically.
- **Account state and relationships**: Persist current email ownership and verification state on the existing account, with at most one pending replacement associated with that account. Keep pending and current addresses distinct. Persist sufficient account-associated link invalidation and request-limit state to enforce the PRD across requests and concurrent operations. Supporting model names and token representation remain implementation choices.
- **Email identity and migration**: Compare addresses after trimming surrounding spaces and ignoring capitalization, without removing dots or plus suffixes. Enforce assigned-address uniqueness at the persistence boundary, including concurrent claims. Pending requests do not reserve an address. Existing addresses start unverified; missing, invalid, and duplicate legacy values cannot become recovery identities without correction. Establish a migration policy before imposing uniqueness that preserves accounts, purchase history, and evidence needed for correction, without arbitrarily trusting or assigning a duplicate address. The PRD does not prescribe the operational duplicate-resolution procedure.
- **Authorization and checkout**: Signed-in actions operate only on the current account, with current-password confirmation for email edits and normal password changes. Verification is required at both the checkout interface and the order-placement boundary, including staff purchases. Unverified accounts retain sign-in, catalog, cart, and order-history access.
- **Links and security events**: Verification and reset links expire after 24 hours. Verification never logs a user in. Email corrections, pending cancellation/replacement, completed email changes, password changes, and resets invalidate links as specified in the PRD. Requesting a new reset link leaves earlier unexpired links usable; successful password changes or resets invalidate all reset links. A reset also cancels pending email replacement.
- **Delivery and limits**: Configure real delivery and sender settings through the existing environment configuration, retaining console delivery and operation without `.env`. No vendor selection. From the first exposed flow, enforce a 60-second cooldown and at most five verification/recovery sends per hour per account or destination, plus a configurable default of 30 email requests per hour per network address. Count network requests even when nothing is sent. Apply limits across exposed signup, resend, correction, replacement, and recovery email paths so alternate routes cannot bypass them. Limit repeated signup attempts; its numeric threshold remains an implementation choice because the PRD does not fix one.
- **Architecture and presentation**: Follow existing Django class-based views, forms owning validation, model/manager behavior, and cross-model workflows using services where appropriate. Retain the existing deliberate deep-module convention. Use the shared page shell, Tailwind, DaisyUI night theme, and HTMX only where needed.
- **Phase verification**: Use pytest and pytest-django with plain shared fixtures; never invoke seed from tests. Each phase includes meaningful end-to-end, authorization, and relevant state-transition tests, with the full suite green at its boundary and Ruff checks passing. Adapt checkout fixtures when verification becomes required while retaining explicit unverified-user coverage.
- **Unfixed details and scope**: Choose and document a consistent same-address verification-resend invalidation policy during implementation; the PRD leaves it open. Do not add MFA, passkeys, recovery codes, support recovery, stronger password requirements, or email-based login.

---

## Phase 1: Signup and initial email verification

**User stories**: 1, 2, 3, 18; basic resend and failure recovery from 9; required limits from 16.

### What to build

Deliver registration through confirmed email ownership, using username login and the existing password policy. New accounts receive verification mail and can sign in before verifying. Provide a usable signed-in verification action with basic resend, expired-link guidance, and retry after delivery failure. Include the account-state migration and email configuration needed for this flow; leave the complete Security Center and legacy-account correction interface for Phase 2.

### Acceptance criteria

- [ ] Signup requires username, password confirmation, and a valid available email; casing and surrounding spaces cannot bypass uniqueness, including concurrent signup. Dots and plus suffixes remain significant.
- [ ] Unavailable-email signup shows “This email is unavailable” with sign-in and reset guidance. Until Phase 7 exposes recovery, guidance does not link to a nonexistent reset page. Repeated signup attempts are limited using a documented threshold.
- [ ] Migration preserves existing account identifiers, roles, carts, and orders, marks legacy addresses unverified, and safely accommodates missing, invalid, and duplicate legacy data under a documented policy.
- [ ] Verification succeeds only for the intended account and address within 24 hours, does not sign anyone in, and gives a signed-in matching account an appropriate next step; other visitors receive sign-in guidance. Invalid or expired links give a useful route to request another email.
- [ ] Signed-in unverified users can resend and retry failed delivery without creating another account. Failed initial delivery preserves the account and explains how to retry.
- [ ] Required cooldown, account/destination hourly limits, and network request limits apply from the first email request, including suppressed sends. Concurrent requests cannot bypass limits; signed-in users receive basic wait feedback.
- [ ] Delivery configuration supports a real backend and sender without selecting a vendor; local console delivery works with no `.env`.
- [ ] Tests verify signup, verification, expiry, basic resend, failure retry, limits, and continued username sign-in, catalog, and cart access before verification.

---

## Phase 2: Security overview and existing-account adoption

**User stories**: 5, 6, 10, 17; existing-address verification from 2.

### What to build

Give all signed-in roles an Account Security overview and a complete path for adding, correcting, or verifying a legacy recovery address. Show current verification status and available password guidance; introduce actionable password controls as their flows arrive. Reuse Phase 1 verification, delivery, and limits.

### Acceptance criteria

- [ ] Signed-in navigation exposes Account security to customers, employees, and administrators; anonymous visitors must sign in to use account controls.
- [ ] The overview displays the current address or missing-address state, verification status, and password guidance. Pending replacement is displayed separately when Phase 5 introduces it.
- [ ] Existing unverified users receive an add-or-verify prompt after signing in without losing access to their account, cart, or order history.
- [ ] Adding or correcting an unverified address requires the current password and a valid available normalized address. Missing, invalid, or duplicate legacy addresses cannot be verified without correction.
- [ ] Correction invalidates links for the previous address, sends verification to the corrected address, and preserves the correction if sending fails so the user can retry under existing limits.
- [ ] Tests cover all roles, wrong-password rejection, ownership isolation, legacy-address states, uniqueness, stale links, sending failure, and preserved purchases and carts.

---

## Phase 3: Verification feedback and remaining failure cases

**User stories**: 9, 16; refinement of 18.

### What to build

Finish verification feedback and recovery from edge cases on the already working verification flows. Make cooldown, hourly suppression, invalid links, repeated visits, and delivery failures understandable without adding a separate infrastructure-only phase or deferring Phase 1 protections.

### Acceptance criteria

- [ ] Signed-in verification requests explain cooldown and hourly waits with useful retry guidance, including account, destination, and network suppression.
- [ ] Expired, malformed, invalidated, already-used, and superseded links produce useful outcomes without verifying the wrong address or mutating another signed-in account.
- [ ] Repeated verification visits and resends follow a documented policy for links to the same unchanged address, while preserving required invalidation after address correction.
- [ ] Temporary sending failures and suppressed requests preserve account state and remain retryable; repeated retries cannot bypass required limits.
- [ ] Tests exercise exact cooldown/hourly boundaries, shared account/destination limits, network requests that send nothing, concurrent attempts, link edge cases, and recovery after delivery becomes available.

---

## Phase 4: Verified checkout and continuation

**User stories**: 3, 4; purchase access for 10 and 17.

### What to build

Require verified email ownership before checkout and order placement while retaining the existing cart and history experience. Carry a safe continuation through the Security Center and verification so eligible users can return to checkout.

### Acceptance criteria

- [ ] Unverified customers, employees, and administrators receive a clear verification requirement on checkout, with access to add/correct an address and resend verification.
- [ ] Both checkout requests and direct order-placement attempts reject unverified accounts without creating orders or emptying carts, including HTMX and zero-total purchases where applicable.
- [ ] Sign-in, catalog, cart mutations, and order history remain available before verification.
- [ ] Verification offers “Continue to checkout” to the matching signed-in account. Anonymous or differently signed-in visitors receive appropriate sign-in guidance without automatic authentication; continuation destinations cannot cause external redirects.
- [ ] Once verified, existing checkout, pricing, coupon, and order behavior works as before. Historical order email snapshots remain unchanged.
- [ ] Tests verify GET/POST and service-boundary enforcement, all roles, continuation, cart preservation, and existing checkout regressions.

---

## Phase 5: Replacement email lifecycle

**User stories**: 7, 8; old-address notification from 15; pending-address overview from 5.

### What to build

Allow a verified account holder to request, cancel, or replace a pending email change. Keep the current verified address active until a replacement is successfully verified and claimed, then notify the old address. Extend the overview, verification flows, and request limits through the complete replacement lifecycle.

### Acceptance criteria

- [ ] Requesting a replacement requires the current password and a valid available normalized address. The overview separately shows current and pending addresses.
- [ ] While replacement is pending, current-address recovery eligibility and verified checkout access remain active. Sending failure preserves the pending request and permits retry.
- [ ] Cancellation or replacement invalidates the earlier pending request's links. Expired links provide an appropriate retry path under existing limits.
- [ ] Pending requests do not reserve addresses. Verification rechecks availability atomically; competing requests can yield only one successful claim, and losers receive guidance to choose another address.
- [ ] Successful replacement activates the verified new address, clears pending state, notifies the old address, and invalidates outstanding account verification and reset links. Notification failure does not leave account state partially changed.
- [ ] Tests cover password checks, cancellation/replacement, delivery failures, stale links, concurrent claims, old-address notification, all roles, and retained checkout/recovery eligibility while pending. Phase 7 adds direct reset-flow integration coverage.

---

## Phase 6: Signed-in password changes

**User stories**: 11, 14, 15, 17.

### What to build

Activate Security Center password changes using the current password and confirmed new password. Preserve the submitting session, invalidate other sessions and outstanding reset links, and send an alert to the verified recovery address without coupling credential success to alert delivery.

### Acceptance criteria

- [ ] Password changes require the correct current password and matching new-password confirmation, using the existing minimum-eight-character, common-password, numeric-password, and similarity validators. Existing passwords remain usable until changed.
- [ ] Customers, employees, and administrators share the flow, including accounts without verified email. Users unable to supply their password receive recovery guidance; the recovery page becomes actionable in Phase 7.
- [ ] A successful change preserves the submitting session and denies subsequent authenticated access through other existing sessions. Outstanding reset links become invalid.
- [ ] A password-change alert goes only to the verified address and contains neither passwords nor reset links. Sending failure does not undo a successful change.
- [ ] Tests use multiple independent sessions and cover validation failures, all roles, verified/unverified alert behavior, and delivery failure. Phase 7 verifies invalidation against issued reset links.

---

## Phase 7: Forgotten-password recovery

**User stories**: 12, 13, 14, 15, 16, 17.

### What to build

Complete the public email-based recovery journey, connect earlier recovery guidance to it, and verify security-event interactions across the finished feature. Eligible accounts receive time-limited reset links; everyone sees the same request confirmation. A reset restores credential access through a subsequent username sign-in.

### Acceptance criteria

- [ ] Recovery requests normalize email consistently and send only to a verified current address. Pending replacement, missing, invalid, unknown, and unverified addresses do not receive reset mail.
- [ ] All requests show the same generic confirmation, including ineligible addresses, rate suppression, and delivery failure. General guidance explains verified-email eligibility, links to sign-in, and suggests recovering inbox access first when needed, without offering support recovery or revealing submitted-address status.
- [ ] Existing cooldown and account/destination limits apply to recovery, alongside verification sends; network-level accounting includes requests that send nothing. Recovery responses remain generic under all limits.
- [ ] Reset links expire after 24 hours, work once, and remain usable when another reset is requested. Invalid or expired pages offer a new request without automatic login.
- [ ] Reset validates new-password confirmation with the same password policy as signup and normal changes; success invalidates all outstanding reset links and all authenticated sessions, cancels pending email replacement and its links, and returns to sign-in.
- [ ] Reset sends a password-change alert to the verified address without secrets or reset links. Delivery failure never undoes successful credential changes.
- [ ] Integration tests verify normal password changes and completed email changes invalidate issued reset links; pending email changes retain old-address recovery until completion; a successful reset prevents an older pending request from taking over the address.
- [ ] Tests cover generic responses, expiry boundaries, simultaneous/repeated link use, session invalidation, email eligibility, limits, failures, all roles, and full signup-to-verification-to-checkout and recovery journeys. The full suite and Ruff checks pass at the final phase boundary.
