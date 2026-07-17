---
title: "AI Agents: Account Enumeration Prevention"
slug: "agent-account-enumeration-prevention"
description: "Account enumeration leaks whether emails exist in your system — through response text, status codes, and timing. Here is how to design login, signup, and reset flows that resist it without lying to legitimate users."
datePublished: "2025-12-24"
dateModified: "2025-12-24"
tags: ["AI", "Agent", "Account"]
keywords: "account enumeration, authentication security, user enumeration, OWASP, password reset, login timing attacks, credential stuffing"
faq:
  - q: "What is account enumeration?"
    a: "Account enumeration is when an attacker learns whether a specific email, phone, or username is registered by observing differences in API responses, HTTP status codes, error messages, or response timing across login, signup, password reset, and MFA enrollment endpoints."
  - q: "Is account enumeration a critical vulnerability?"
    a: "It is typically rated medium severity (CVSS ~5.3) but enables targeted phishing, credential stuffing, and social engineering. For high-profile users or B2B products, confirming account existence is a meaningful reconnaissance step before account takeover attempts."
  - q: "Should login and signup return the same message for unknown emails?"
    a: "Yes for the user-visible message. Both should say something like 'If an account exists, we sent instructions' or 'Invalid email or password' on login. Internally, log the distinction for security monitoring, but never expose it in HTML, JSON error fields, or redirect behavior."
  - q: "Does CAPTCHA prevent enumeration?"
    a: "CAPTCHA raises the cost of bulk enumeration but does not fix semantic leaks. An attacker solving one CAPTCHA per probe still learns account existence if responses differ. Use CAPTCHA for rate limiting abuse, not as a substitute for uniform responses."
---
Security reviewers flag account enumeration in nearly every auth audit. Developers push back: "We need to tell users their email isn't registered so they can sign up." Both sides are half right.

Enumeration matters because attackers compile lists of valid accounts before credential stuffing, SIM swap targeting, and spear-phishing. A password reset flow that says "no account found" is a free oracle. Login endpoints that return 404 vs 401 leak the same information. Timing differences between "user not found" and "wrong password" paths complete the picture.

The fix is not obscurity theater. It is consistent semantics, constant-time code paths, and rate limits — without trapping legitimate users in vague error loops.

## The attack surface map

Enumeration vectors appear anywhere identity is resolved:

| Endpoint | Leaky behavior | Safe behavior |
|----------|----------------|---------------|
| Login | "User not found" vs "Wrong password" | Single message: "Invalid credentials" |
| Signup | "Email already registered" | "Check your email to continue" (same for new/existing) |
| Password reset | "Email not found" | "If an account exists, we sent a reset link" |
| MFA enrollment | "Phone not associated" | Generic failure |
| Invite acceptance | "Invalid user" vs "Invite expired" | Uniform messaging where feasible |
| OAuth linking | Provider-specific errors | Normalize at API boundary |

Mobile apps leak through UI copy and animation timing as much as APIs. iOS and Android clients must share the same response contract as web.

## Uniform responses without lying awkwardly

Product teams worry that generic messages confuse users. The pattern that works:

**Login:** Always "Invalid email or password." Never specify which failed. Offer password reset link on the same screen.

**Signup with email verification:** Whether the email is new or existing-unverified, respond: "We sent a verification link to your email." For existing verified accounts, send a "someone tried to sign up" notification instead of creating a duplicate.

**Password reset:** Always: "If an account exists for this email, you will receive reset instructions within a few minutes." Send email only when account exists; send nothing when it does not — but the user cannot tell which happened.

```typescript
interface ResetRequest {
  email: string;
}

async function requestPasswordReset(req: ResetRequest): Promise<{ message: string }> {
  const GENERIC = "If an account exists, reset instructions were sent.";

  // Always consume similar time — see timing section below
  const user = await userRepo.findByEmail(normalizeEmail(req.email));

  if (user && user.isActive) {
    const token = await resetTokenService.issue(user.id, { ttlMinutes: 30 });
    await emailQueue.enqueue("password_reset", {
      to: user.email,
      token,
      locale: user.locale,
    });
  } else {
    // No email sent — attacker learns nothing from response
    await timingPad.randomDelay(200, 400);
  }

  // Log internally for abuse detection — never return to client
  auditLog.info("password_reset_requested", {
    emailHash: hashEmail(req.email),
    accountFound: !!user,
  });

  return { message: GENERIC };
}
```

## Timing side channels

Even identical JSON responses leak through latency:

- User-not-found skips bcrypt verification (~50ms saved)
- User-not-found skips database joins on MFA devices
- Password reset skips email queue enqueue

Attackers run statistical timing analysis over hundreds of requests. Mitigations:

**Constant-work authentication.** Always run bcrypt (or Argon2id) against a dummy hash when the user does not exist.

```typescript
const DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$..."; // precomputed

async function verifyLogin(email: string, password: string): Promise<boolean> {
  const user = await userRepo.findByEmail(email);
  const hash = user?.passwordHash ?? DUMMY_HASH;

  const valid = await argon2.verify(hash, password);
  if (!user || !valid) {
    return false;
  }
  return true;
}
```

**Pad response times** to a minimum threshold with jitter on all auth paths.

**Rate limit by IP and identifier** — exponential backoff after failures, CAPTCHA at threshold.

Measure p50 and p95 latency separately for hit and miss paths in staging. If delta exceeds 20ms, you have work to do.

## Signup: the duplicate email problem

Signup is the hardest endpoint because product wants to steer existing users to login.

Options ranked by enumeration resistance:

1. **Email verification for all paths.** New signup sends verify link. Existing verified account triggers "login attempt notice" email. Same API response either way.

2. **Magic link login-only.** No password signup; every entry point sends a link. Removes "already exists" branch entirely.

3. **Split flow after email entry (careful).** Single "continue" button, then server-side routing — but only after email verification proves ownership. Do not reveal existence before verification.

Avoid: inline validation that turns the email field red with "already registered" on blur.

## OAuth and SSO leakage

Social login buttons leak through account linking:

- "Google account not linked" vs "Google auth failed"
- Auto-provisioning errors that mention existing email

Normalize OAuth callback errors to a single landing page. Log provider error codes server-side.

For enterprise SSO, "domain not configured" may be acceptable — attackers can DNS-enumerate tenants anyway. Still avoid per-user SSO existence checks on public forms.

## Rate limiting and detection

Uniform responses stop casual enumeration; rate limits stop bulk scanning.

```python
# Redis sliding window — limit by IP + email hash
def check_rate_limit(ip: str, email: str) -> bool:
    keys = [
        f"auth:ip:{ip}",
        f"auth:email:{sha256(email.lower())}",
    ]
    for key in keys:
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 3600)
        if count > 50:  # tune per endpoint
            return False
    return True
```

Alert on:

- High distinct email probes from single IP
- Password reset requests with >90% non-existent rate (internal metric only)
- Geographic anomalies on login probes

Honeypot accounts (canary emails) that should never receive traffic trigger immediate blocks.

## Logging for defenders, not attackers

Internal logs should record:

- `accountFound` boolean on auth attempts
- Normalized email hash (not plaintext in shared logs)
- Request ID correlating WAF, app, and email delivery

Never echo `accountFound` to client-facing error payloads, GraphQL extensions, or mobile debug builds shipped to App Store.

## Testing enumeration resistance

Automated tests belong in CI:

```typescript
describe("enumeration resistance", () => {
  const existingUser = "registered@example.com";
  const unknownUser = "nobody@example.com";

  it("login responses are indistinguishable", async () => {
    const res1 = await api.post("/login", {
      email: existingUser,
      password: "wrong-password",
    });
    const res2 = await api.post("/login", {
      email: unknownUser,
      password: "wrong-password",
    });

    expect(res1.status).toBe(res2.status);
    expect(res1.body.error).toBe(res2.body.error);
    // timing: compare median of 20 requests, assert delta < 30ms
  });

  it("password reset returns generic message", async () => {
    for (const email of [existingUser, unknownUser]) {
      const res = await api.post("/password-reset", { email });
      expect(res.body.message).toMatch(/if an account exists/i);
    }
  });
});
```

Include mobile client contract tests — product designers love specific error copy that breaks your API discipline.

## Balancing UX and security

Legitimate users forget whether they registered. Offer:

- Passwordless magic link from the same form as login
- Account recovery via verified phone without confirming registration status upfront
- Support path that does not expose account existence to unauthenticated callers

Customer support consoles can look up accounts after verifying identity through other channels — that privilege belongs behind authenticated staff tools, not public APIs.

## Compliance and breach notification angles

GDPR and state privacy laws do not exempt enumeration risks. Confirming that someone uses your service can itself be sensitive (health, dating, financial apps). In those verticals, enumeration resistance is a privacy requirement, not a nice-to-have CVSS item.

Document auth flow decisions in your security appendix for SOC 2 and ISO 27001 audits. Reviewers ask for evidence that user enumeration was considered.

Account enumeration prevention is unglamorous backend work: same bytes out regardless of truth, same CPU burned on fake and real lookups, alerts on probing patterns. It will not get a launch blog post. It will keep your user list out of an attacker's spreadsheet — and that is worth the product negotiation.

## Resources

- [OWASP: Testing for Account Enumeration](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/03-Identity_Management_Testing/04-Testing_for_Account_Enumeration_and_Guessable_User_Account)
- [CWE-204: Observable Response Discrepancy](https://cwe.mitre.org/data/definitions/204.html)
- [NIST SP 800-63B: Digital Identity Guidelines (Authentication)](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [Have I Been Pwned: Understanding credential stuffing](https://haveibeenpwned.com/Passwords)
- [PortSwigger Web Security Academy: Username enumeration](https://portswigger.net/web-security/authentication/password-based/lab-username-enumeration-via-different-responses)
