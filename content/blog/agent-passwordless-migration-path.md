---
title: "AI Agents: Passwordless Migration Path"
slug: "agent-passwordless-migration-path"
description: "A phased plan to migrate existing password users to passkeys, magic links, and SSO—covering account recovery, IdP cutover, and rollback without locking anyone out."
datePublished: "2025-12-26"
dateModified: "2025-12-26"
tags: ["AI", "Agent", "Passwordless"]
keywords: "passwordless migration, passkey rollout, auth transition, account recovery, SSO cutover, dual authentication"
faq:
  - q: "How long should password and passwordless methods run in parallel?"
    a: "Plan six to eighteen months depending on user base and regulatory constraints. Parallel operation is not failure—it is risk management. Set explicit sunset dates only after enrollment and recovery metrics stabilize for two consecutive release cycles."
  - q: "What is the safest order: passkeys first or magic links first?"
    a: "Magic links and OTP email establish passwordless habits on every device class without hardware dependencies. Passkeys come next for returning users. SSO-first makes sense for workforce accounts where the IdP already owns primary authentication."
  - q: "How do you migrate users who never log in?"
    a: "Do not force passwordless on dormant accounts at login—they have no session to upgrade. Trigger enrollment on next successful auth or via a verified email campaign with a time-limited setup link, not a blanket credential wipe."
  - q: "What rollback looks like if passkey adoption stalls?"
    a: "Feature-flag passwordless UI off, keep password backend hot, and preserve enrolled passkeys for users who already migrated. Never delete passkey records during rollback—you will need them when you retry."
---
Passwordless migration is less about picking FIDO2 over magic links and more about sequencing trust transitions across millions of accounts that already have passwords, security questions nobody remembers, and SMS 2FA wired into billing workflows. The teams that stumble usually treat migration as a frontend swap. The teams that succeed run it like a data migration with auth invariants: every account must remain reachable, every privileged action must remain step-up protected, and every rollback must take minutes—not a weekend restore from backup.

## Start with an auth inventory, not a vendor demo

Before changing login UI, map every authentication surface:

- Web and mobile native login
- API keys and machine tokens (out of scope for passwordless UI but in scope for session policy)
- Admin impersonation and support tools
- Partner SSO and SAML/OIDC federation
- Legacy OAuth apps still on resource-owner password grants

For each surface, record: primary factor today, backup factor, account recovery path, and whether the account is human, service, or shared inbox. Shared and service accounts often block a naive "remove passwords everywhere" mandate.

Export counts: monthly active logins by method, password reset volume, 2FA recovery tickets, and SSO vs local auth split. These baselines become your migration scoreboard.

## Four phases with explicit exit criteria

### Phase 0 — Instrumentation and feature flags

Wrap every auth method behind flags: `auth.password.enabled`, `auth.magic_link.enabled`, `auth.passkey.enabled`, `auth.sso.required_for_domain`. Ship flags before shipping UX so rollback is a config change.

Add structured events: `auth_method_used`, `enrollment_started`, `enrollment_completed`, `recovery_started`, `recovery_completed`, with `failure_reason` enums stable enough for dashboards.

Exit criteria: 100% of auth attempts emit events; staging can toggle any method independently.

### Phase 1 — Additive enrollment (password remains default)

Users log in with passwords as today. After login, prompt optional enrollment: passkey, additional email factor, or security key. Never block access for skipping.

For mobile, deep-link enrollment into the app after email verification so users do not create passkeys on the wrong RP ID in an in-app browser.

Exit criteria: ≥15% of MAU have a second factor or passkey without support ticket spike.

### Phase 2 — Passwordless as equal choice

Login screen presents passkey / magic link / password with equal visual weight (not a tiny "other options" link). Magic links get short TTL (10–15 minutes), single use, and rate limits per email and IP.

Implement **account chooser** UX for magic links: reveal whether an email exists only after token verification to reduce enumeration—return the same HTTP response for unknown emails but skip sending mail.

Exit criteria: ≥40% of logins use passwordless methods; password reset tickets flat or down.

### Phase 3 — Passwordless default, password exception

New registrations are passwordless-only. Returning users see passwordless first; password appears after explicit "Use password instead" for stragglers.

Corporate domains on SSO: redirect to IdP before any local auth renders—local passwords become a support-only break-glass.

Exit criteria: password logins <20% of total; recovery SLA unchanged.

### Phase 4 — Password sunset with grace

Disable password login for cohorts that enrolled passkeys or SSO. Email cohorts 30 and 7 days ahead with recovery instructions. Keep password enabled for accounts without passwordless factors until manually verified or until a hard regulatory deadline.

## Dual-auth middleware pattern

Keep one session issuance path regardless of front-door method. Authentication adapters normalize to a `VerifiedIdentity` struct:

```python
from dataclasses import dataclass
from enum import Enum

class AuthMethod(str, Enum):
    PASSWORD = "password"
    MAGIC_LINK = "magic_link"
    PASSKEY = "passkey"
    SSO = "sso"

@dataclass(frozen=True)
class VerifiedIdentity:
    user_id: str
    method: AuthMethod
    amr: tuple[str, ...]  # authentication methods references for token claims
    session_version: int

def issue_session(identity: VerifiedIdentity) -> Session:
    session = Session.create(
        user_id=identity.user_id,
        auth_method=identity.method.value,
        amr=list(identity.amr),
        version=identity.session_version,
    )
    audit.log("session_issued", user_id=identity.user_id, method=identity.method.value)
    return session
```

Password and passkey flows differ at the edge; session and authorization middleware stay identical. That separation is what makes rollback safe.

## Account recovery without reintroducing passwords

Recovery is where migrations fail audit. Rules:

1. **Never** email a temporary password in plain text.
2. **Always** require equal-or-stronger verification than enrollment (if passkey + email enrolled, recovery needs both channels or human identity proofing).
3. **Issue new credentials**; do not "unlock" old passkeys remotely.

```typescript
async function startRecovery(email: string): Promise<void> {
  const user = await users.findByEmail(email);
  // Constant-time path whether or not user exists
  const token = user ? await recoveryTokens.issue(user.id, { ttlMinutes: 15 }) : null;
  if (token) {
    await mailer.sendRecovery(email, token);
  }
  await delay(jitterMs(200, 400)); // reduce timing oracle
}

async function completeRecovery(token: string, newPasskey: RegistrationPayload) {
  const { userId } = await recoveryTokens.consume(token); // single-use
  await sessions.revokeAllForUser(userId);
  await passkeys.register(userId, newPasskey);
  await audit.record("recovery_passkey_enrolled", { userId });
}
```

Maintain printed backup codes for high-value accounts—generated once, shown once, stored hashed.

## Enterprise IdP and SCIM interactions

Workforce migration often means OIDC/SAML becomes primary while local passwords atrophy. Coordinate:

- **JIT provisioning** — first SSO login creates the shadow user; map `sub` and `email` with immutable external ID.
- **Domain verification** — auto-route `@corp.com` to IdP; prevent duplicate local accounts.
- **SCIM deprovisioning** — disable local sessions within minutes of IdP suspend; passkeys alone do not help if the IdP already cut access.
- **Break-glass** — two break-glass local admins stored offline; rotate quarterly with recorded ceremony.

Document which system owns MFA. If the IdP enforces MFA, do not stack a second SMS gate on your side unless compliance requires step-up at the app layer.

## Metrics that tell you to pause or accelerate

| Metric | Healthy trend | Pause signal |
|--------|---------------|--------------|
| Passwordless login share | Up week over week | Flat after major UX push |
| Enrollment funnel completion | >60% start→finish | Drop on one OS version |
| Recovery tickets / 1k MAU | Flat or down | Spike after phase change |
| Session duration post-migration | Stable | Collapse (auth loops) |
| Failed auth rate | <1% | Climb on magic link TTL issues |

Review weekly during phase changes; monthly once stable. Tie phase gates to these numbers in writing so product cannot skip Phase 2 because of a launch deadline.

## Communication templates that reduce support load

Users fear lockout more than they fear passwords. Every phase-change email needs: what is changing, what they should do, what happens if they ignore it, and a single support link with pre-filled context.

In-app banners beat email for active users. Dormant users get email only—do not expire passwords on accounts that have not logged in since 2019 without a verified recovery address.

## Rollback you can execute at 3 a.m.

1. Disable `auth.passkey.required` and `auth.passwordless_default` flags.
2. Restore login UI component that lists password first (keep deployed, hidden behind flag).
3. Leave enrolled passkeys active—users who enrolled can still use them.
4. Post status page note only if password login was briefly unavailable; silent rollback if caught in canary.

Run rollback drills in staging quarterly. Measure time-to-flag-off and confirm sessions issued during passwordless-only mode remain valid or fail gracefully per your security policy.

Passwordless migration is a multi-quarter program: inventory first, parallel methods second, aggressive UX third, sunset last—with recovery and rollback rehearsed as seriously as the happy path.

## Resources

- [NIST SP 800-63B Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [FIDO Alliance: Passwordless sign-in UX guidelines](https://fidoalliance.org/white-paper-fido-authentication-user-experience-guidelines/)
- [OAuth 2.0 for Browser-Based Apps (RFC 8252)](https://www.rfc-editor.org/rfc/rfc8252)
- [Microsoft identity platform: Plan passwordless deployment](https://learn.microsoft.com/en-us/entra/identity/authentication/howto-authentication-passwordless-deployment)
