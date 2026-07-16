---
title: "The OWASP API Security Top 10"
slug: "api-security-owasp-api-top-10"
description: "The OWASP API Security Top 10 explained for engineers: broken auth, excessive data exposure, rate limiting gaps, and practical mitigations for each."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Security", "API", "Backend", "OWASP"]
keywords: "OWASP API Security Top 10, API security risks, broken object level authorization, API security checklist, BOLA API security"
faq:
  - q: "What is the OWASP API Security Top 10?"
    a: "The OWASP API Security Top 10 is a standard awareness document listing the most critical security risks for APIs. It covers broken object-level authorization, broken authentication, excessive data exposure, lack of rate limiting, and other common API vulnerabilities. It serves as a checklist for API security reviews and threat modeling."
  - q: "What is the most common API security vulnerability?"
    a: "Broken Object Level Authorization (BOLA, API1) — where an API endpoint accepts a resource ID without verifying the requesting user owns or has permission to access that resource. Example: changing /api/orders/123 to /api/orders/456 and accessing another user's order. It accounts for the majority of API breaches."
  - q: "How do I protect against BOLA?"
    a: "Never trust client-supplied resource IDs without authorization checks. Every endpoint that accesses a resource by ID must verify the authenticated user has permission to access that specific resource. Use policy engines or middleware that checks ownership before returning data."
---

The OWASP API Security Top 10 is the checklist your API should pass before it handles real user data — and BOLA (Broken Object Level Authorization) is number one because it's embarrassingly easy to exploit and devastatingly common. I've reviewed APIs where changing `user_id=123` to `user_id=124` in the request returned another user's entire profile. No hacking tools needed — just increment a number. The Top 10 isn't theoretical; each entry maps to vulnerabilities I've found in production code reviews.

## The list (2023 edition)

| # | Risk | One-line summary |
|---|------|-----------------|
| API1 | Broken Object Level Authorization (BOLA) | Access other users' resources by changing IDs |
| API2 | Broken Authentication | Weak tokens, credential stuffing, no MFA |
| API3 | Broken Object Property Level Authorization | Mass assignment, excessive field exposure |
| API4 | Unrestricted Resource Consumption | No rate limits, expensive queries |
| API5 | Broken Function Level Authorization | Regular users access admin endpoints |
| API6 | Unrestricted Access to Sensitive Business Flows | No bot protection on critical flows |
| API7 | Server Side Request Forgery (SSRF) | API fetches attacker-controlled URLs |
| API8 | Security Misconfiguration | Default creds, verbose errors, missing headers |
| API9 | Improper Inventory Management | Shadow APIs, deprecated endpoints exposed |
| API10 | Unsafe Consumption of APIs | Trusting third-party API responses |

## API1: BOLA — the big one

Every endpoint with a resource ID is vulnerable unless you check ownership:

```python
# VULNERABLE
@app.get("/api/orders/{order_id}")
def get_order(order_id: str, user: User = Depends(get_current_user)):
    return db.get_order(order_id)  # any user can access any order

# FIXED
@app.get("/api/orders/{order_id}")
def get_order(order_id: str, user: User = Depends(get_current_user)):
    order = db.get_order(order_id)
    if order.user_id != user.id:
        raise HTTPException(403, "Not authorized")
    return order
```

Better: enforce at the data layer:

```python
def get_order_for_user(order_id: str, user_id: str) -> Order:
    order = db.query("SELECT * FROM orders WHERE id = %s AND user_id = %s", order_id, user_id)
    if not order:
        raise NotFound()  # don't reveal whether order exists
    return order
```

Test: create two users, authenticate as user A, try to access user B's resources. Automate this in integration tests.

## API2: Broken Authentication

Mitigations:
- Short-lived tokens with refresh rotation ([JWT vs sessions](https://blog.michaelsam94.com/api-authentication-jwt-vs-sessions/))
- Rate limit login endpoints (5 attempts per minute per IP)
- MFA for sensitive accounts
- Invalidate all sessions on password change
- Use [OAuth PKCE](https://blog.michaelsam94.com/oauth-pkce-mobile/) for mobile clients

## API3: Excessive Data Exposure

Return only what the client needs:

```python
# VULNERABLE — returns all fields including internal ones
return user  # {id, email, password_hash, ssn, internal_notes, ...}

# FIXED — explicit response model
class UserResponse(BaseModel):
    id: str
    name: str
    email: str

return UserResponse(id=user.id, name=user.name, email=user.email)
```

Use response DTOs/serializers that whitelist fields. Never return database models directly.

## API4: Unrestricted Resource Consumption

Implement [rate limiting](https://blog.michaelsam94.com/api-rate-limiting-algorithms/) at the [gateway](https://blog.michaelsam94.com/api-gateway-patterns/) and service level:

- Per-user rate limits on all endpoints
- Per-endpoint limits on expensive operations (export, search, bulk)
- Request size limits (max body size, max query params)
- Pagination required on list endpoints (max page size cap)
- Query timeouts on database calls

## API5: Broken Function Level Authorization

Separate admin and user routes with explicit role checks:

```python
def require_admin(user: User = Depends(get_current_user)):
    if "admin" not in user.roles:
        raise HTTPException(403)
    return user

@app.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: str):
    ...
```

Don't rely on "security through obscurity" — admin endpoints on non-obvious paths are still discoverable.

## API7: SSRF

When your API fetches URLs on behalf of users:

```python
# VULNERABLE
@app.post("/api/fetch")
def fetch_url(url: str):
    return requests.get(url).text  # attacker fetches internal services

# FIXED
ALLOWED_DOMAINS = {"api.example.com", "cdn.example.com"}

def safe_fetch(url: str):
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_DOMAINS:
        raise BadRequest("Domain not allowed")
    if parsed.hostname in ("localhost", "169.254.169.254"):
        raise BadRequest("Internal URLs blocked")
    return requests.get(url, timeout=5, allow_redirects=False)
```

Block internal IPs, metadata endpoints, and redirect chains.

## Security review checklist

Before shipping any API endpoint:

- [ ] Resource ID access checks ownership (BOLA)
- [ ] Authentication required (unless explicitly public)
- [ ] Response returns minimum necessary fields
- [ ] Rate limited appropriately
- [ ] Role/permission checked for admin functions
- [ ] Input validated (type, length, format)
- [ ] Errors don't leak internal details
- [ ] Logged with request ID (no sensitive data in logs)

Run this checklist in PR review for every new endpoint. Automate what you can — static analysis tools catch some patterns, but BOLA requires intentional authorization logic.

## Common production mistakes

Teams get security owasp api top 10 wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

API design for security owasp api top 10 frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.

## Debugging and triage workflow

When security owasp api top 10 misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OWASP API Security Top 10 (2023)](https://owasp.org/API-Security/editions/2023/en/0x00-header/)
- [OWASP BOLA prevention cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html)
- [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
- [API authentication patterns](https://blog.michaelsam94.com/api-authentication-jwt-vs-sessions/)
- [Threat modeling with STRIDE](https://blog.michaelsam94.com/threat-modeling-stride/)
