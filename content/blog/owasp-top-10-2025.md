---
title: "The OWASP Top 10 for Engineers"
slug: "owasp-top-10-2025"
description: "OWASP Top 10 2025 explained for builders: broken access control, security misconfiguration, injection, and concrete mitigations in modern web stacks."
datePublished: "2026-01-27"
dateModified: "2026-01-27"
tags: ["Security", "OWASP", "Web Security", "Engineering"]
keywords: "OWASP Top 10 2025, web application security, broken access control, injection prevention, security misconfiguration"
faq:
  - q: "How often does the OWASP Top 10 change?"
    a: "Major revisions arrive every three to four years based on CWE data, industry surveys, and community input. The 2025 edition reorganizes categories to reflect API-first architectures, supply chain risk, and misconfiguration prevalence in cloud-native deployments."
  - q: "Which OWASP category causes the most breaches in practice?"
    a: "Broken access control consistently ranks first — IDOR, missing function-level checks, and JWT scope confusion. Injection drops in frequency but remains catastrophic when it occurs. Security misconfiguration (exposed buckets, default credentials) spikes with cloud adoption."
  - q: "Should backend or frontend engineers own OWASP mitigations?"
    a: "Both. Backend owns authorization, input validation, and secure defaults. Frontend owns XSS prevention, secure token storage, and CSP. Security reviews fail when teams assume the other layer handled it."
---

Security training slides mention OWASP once a year and disappear. The Top 10 isn't a compliance checkbox — it's a prioritized list of ways production systems actually get owned. I've triaged incidents in five of these categories. The patterns repeat because frameworks make the happy path easy and the secure path requires explicit work.

## A01: Broken Access Control

The classic: change `/api/orders/12345` to `/api/orders/12346` and read someone else's order. Also: admin endpoints without role checks, GraphQL fields exposed without field-level auth, and "security through obscurity" UUIDs.

**Fix at the code layer:**
```python
def get_order(order_id: str, current_user: User) -> Order:
    order = db.get_order(order_id)
    if order.tenant_id != current_user.tenant_id:
        raise Forbidden()  # same response as 404 to prevent enumeration
    return order
```

Centralize authorization — policy engines (OPA, Cedar), RBAC middleware, or at minimum consistent `authorize(user, action, resource)` calls. Test with horizontal privilege escalation cases in CI.

## A02: Cryptographic Failures

Not "weak crypto algorithms" alone — storing passwords in MD5, TLS disabled on internal services, secrets in logs, and PII in plaintext columns.

Checklist:
- bcrypt/argon2 for passwords; never roll your own
- TLS 1.2+ everywhere, including service-to-service
- Encrypt PII at rest with KMS-managed keys
- No secrets in Git, client bundles, or error responses

## A03: Injection

SQL injection survives because ORMs get bypassed with raw queries. Also: command injection in shell wrappers, LDAP injection, template injection (SSTI).

```python
# Vulnerable
db.execute(f"SELECT * FROM users WHERE email = '{email}'")

# Safe
db.execute("SELECT * FROM users WHERE email = %s", (email,))
```

Lint for string concatenation in queries. Parameterized statements always. For shell: avoid shell entirely (`subprocess` with list args, no `shell=True`).

## A04: Insecure Design

Flaws in architecture that code can't patch — no rate limiting on password reset, missing fraud detection on coupon redemption, trust boundary violations between tenant isolation layers.

Threat modeling before build: STRIDE on data flow diagrams. Ask "what happens if this API is called 10,000 times per second with valid tokens?"

## A05: Security Misconfiguration

Default admin passwords, directory listing enabled, debug mode in prod, S3 buckets with public ACLs, Kubernetes dashboards without auth, CORS `*`.

Automate: Checkov/tfsec on IaC, CIS benchmarks on AMIs, periodic external attack surface scans. Misconfiguration is where "we'll harden later" accumulates.

## A06–A10: Supply chain, auth, logging, SSRF

**Vulnerable components:** Dependabot, SBOM generation, pin dependencies, verify checksums. Log4Shell taught the cost of transitive trust.

**Authentication failures:** MFA for admin, secure session cookies (`HttpOnly`, `Secure`, `SameSite`), no long-lived refresh tokens in localStorage.

**Logging failures:** Log auth events, access denials, and input validation failures — not passwords or full credit card numbers. Centralize logs; alert on brute-force patterns.

**SSRF:** Block internal metadata URLs (`169.254.169.254`), validate outbound URLs, network-segment internal services from app subnets.

## Making OWASP actionable in sprints

Don't "fix OWASP." Pick one category per quarter for the team that owns the risk:

| Quarter | Focus | Deliverable |
|---------|-------|-------------|
| Q1 | Access control | IDOR test suite + policy middleware |
| Q2 | Misconfiguration | IaC policy gates in CI |
| Q3 | Injection | SAST rule + raw query audit |
| Q4 | Auth | MFA rollout + session audit |

Map findings to CWE IDs in your bug tracker. Trend data beats annual panic.

## Building security into CI

Shift-left checks that map to Top 10 categories:

- SAST (Semgrep, CodeQL) on every PR — injection, XSS patterns
- Dependency scan (Dependabot, Snyk) — vulnerable components
- IaC scan (Checkov) — misconfiguration
- DAST weekly on staging — access control, auth failures

Fail builds on critical findings; waivers require ticket with expiry. Security champions in each squad triage medium findings — do not ignore yellow forever.

## Operational notes

Run tabletop exercises mapping Top 10 categories to your architecture — "where would injection enter our GraphQL layer?" — quarterly. Exercises surface gaps documentation misses and train new hires on actual attack surfaces, not abstract categories.

Map each Top 10 category to an existing security control owner on call — access control issues route to identity team, misconfiguration to platform. Routing clarity speeds incident triage when scanner findings spike after a release.

## Prioritize by exploitability in your stack

Map Top 10 to your architecture:
- API-heavy: Broken Auth (#1), SSRF, excessive data exposure
- LLM features: add LLM Top 10 overlay
- Mobile: MASVS cross-reference

Annual pen test validates; continuous SAST/SCA catches regressions between tests.

## Common production mistakes

Teams get top 10 2025 wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of top 10 2025 fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When top 10 2025 misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OWASP Top 10 project page](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE Top 25 Most Dangerous Weaknesses](https://cwe.mitre.org/top25/)
- [OWASP ASVS (Application Security Verification Standard)](https://owasp.org/www-project-application-security-verification-standard/)
- [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
