---
title: "Passwordless Auth with Magic Links"
slug: "passwordless-magic-links"
description: "Implement magic link authentication securely: token design, expiry, replay prevention, email deliverability, and when magic links beat passkeys."
datePublished: "2026-02-02"
dateModified: "2026-02-02"
tags: ["Security", "Authentication", "Passwordless", "Web"]
keywords: "magic link authentication, passwordless login, email login link, secure token auth, passwordless email"
faq:
  - q: "Are magic links less secure than passwords?"
    a: "They shift risk from credential reuse to email account compromise. A user with a weak Gmail password is vulnerable either way. Magic links eliminate password database breaches and phishing of site-specific passwords, but you must protect link tokens as single-use secrets with short TTL."
  - q: "How long should a magic link token last?"
    a: "15 minutes for login links is standard. Shorter (5 minutes) for high-sensitivity actions; up to 30 minutes if email delays are common in your user base. Never make login links valid for hours or reusable."
  - q: "When should you choose magic links over passkeys?"
    a: "Magic links work everywhere email works — no device biometric required, no WebAuthn browser support concerns. Use them for low-to-medium sensitivity apps, first-time onboarding, or as a fallback. High-security or high-frequency login apps should push passkeys once users are enrolled."
---

Magic links feel like a hack — "click this URL and you're in" — but Slack, Notion, and half of B2B SaaS rely on them for first login. We shipped magic links before passkeys because our users are on corporate laptops that block biometric APIs and email is the one identity factor every enterprise already has.

Done wrong, magic links are bearer tokens in inbox clothing. Done right, they're single-use, short-lived, and bound to the login attempt that requested them.

## Threat model

| Threat | Mitigation |
|--------|------------|
| Token intercepted in transit | HTTPS only; HSTS |
| Token forwarded/leaked | Single-use; short TTL; optional IP/UA binding |
| Email account compromise | Out of scope — same as password reset |
| Brute force token guess | 256-bit entropy; rate limit requests |
| Open redirect on callback | Allowlist redirect URLs |

Don't put PII in the link query string. Log token hashes, not raw tokens.

## Token design

Generate cryptographically random tokens:

```python
import secrets
token = secrets.token_urlsafe(32)  # 256 bits
token_hash = hashlib.sha256(token.encode()).hexdigest()
# Store token_hash, user_id, expires_at, used_at in DB
```

Email contains: `https://app.acme.com/auth/verify?token=<raw_token>`

On verify: hash incoming token, lookup row, check expiry and `used_at IS NULL`, mark used, create session.

**Single-use is non-negotiable.** Reused links are a session fixation vector. Return generic error on reuse without revealing whether the account exists.

## Request and verify flow

```
User enters email ──► POST /auth/magic-link
                           │
                     rate limit (5/hr/email)
                           │
                     always return 200 ("Check your email")
                           │
                     send email async (queue)
                           │
User clicks link ──► GET /auth/verify?token=...
                           │
                     validate + mark used
                           │
                     set session cookie ──► redirect /dashboard
```

Always return 200 on request — prevents email enumeration. Same message whether account exists or not. Optionally create account on first login (passwordless signup pattern).

```typescript
// Rate limit by email + IP
await rateLimiter.consume(`magic:${email}:${ip}`, 5, { windowMs: 3600_000 });

// Queue email — don't block request on SMTP
await queue.publish('send-magic-link', { userId, token, email });
```

## Email deliverability affects auth

Magic link auth fails when email lands in spam. Requirements:

- SPF, DKIM, DMARC on sending domain
- Dedicated transactional subdomain (`auth.acme.com`)
- Link domain matches app domain (or clearly documented redirect)
- Plain-text alternative with full URL (some clients strip HTML links)

Monitor bounce rates and time-to-inbox. If corporate filters block your domain, offer SSO alternative.

## Optional hardening

**Bind to login request metadata.** Store `ip_hash` and `user_agent_hash` at request time; verify loosely on click (same /24, same browser family). Reduces forward-to-attacker risk; increases false rejects on mobile network switches — tune carefully.

**PKCE-style for mobile deep links.** Mobile apps open `acme://auth?token=...` — use one-time exchange endpoint so the token never hits server logs in Referer headers.

**Step-up for sensitive actions.** Magic link for login; require passkey or TOTP before billing changes even if session is valid.

## Session after verification

Set HTTP-only, Secure, SameSite=Lax session cookie. Rotate session ID on login. Don't embed long-lived JWT in URL fragment — browsers leak URLs via Referer and history.

Session duration: 7–30 days with sliding expiration for consumer apps; shorter for admin panels.

## Magic links vs passkeys vs passwords

| Method | UX friction | Security profile | Best for |
|--------|-------------|------------------|----------|
| Password | Medium | Reuse, phishing | Legacy |
| Magic link | Low (if email fast) | Email compromise | B2B onboarding, mobile-light |
| Passkey | Lowest (return users) | Phishing-resistant | Consumer, repeat login |

We run magic link + optional passkey enrollment post-login. 60% of users never add a passkey and stay on magic links — that's fine for our threat model.

## Mobile deep links and app handoff

Magic links opened on mobile should deep link into native apps when installed — universal links (iOS) and app links (Android). Web fallback stays magic link flow. Test email clients (Gmail app, Outlook) — they wrap links through redirectors that break one-time tokens if not allowlisted.

Token entropy: 256 bits minimum. Shorter tokens get brute forced at scale even with rate limits.

## Magic link security

- Single use, 15-minute expiry
- Bind to IP / device fingerprint loosely (warn on mismatch, don't block mobile networks)
- Rate limit requests per email: 3/hour
- HTTPS only, no link prefetch (use POST confirmation for sensitive actions)

Pair with WebAuthn as upgrade path after first magic link login.

## Common production mistakes

Teams get magic links wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of magic links fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When magic links misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OWASP Forgot Password Cheat Sheet (applies to magic links)](https://cheatsheetseries.owasp.org/cheatsheetseries/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- [NIST Digital Identity Guidelines (SP 800-63B)](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [Postmark email authentication guide](https://postmarkapp.com/guides/email-authentication)
- [Auth.js magic link provider](https://authjs.dev/getting-started/providers/email)
- [Resend transactional email docs](https://resend.com/docs)
