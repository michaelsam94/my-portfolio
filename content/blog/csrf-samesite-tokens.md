---
title: "CSRF Defense with SameSite and Tokens"
slug: "csrf-samesite-tokens"
description: "Prevent cross-site request forgery with SameSite cookies, synchronizer tokens, double-submit patterns, and framework defaults in modern web apps."
datePublished: "2025-05-12"
dateModified: "2025-05-12"
tags: ["Security"]
keywords: "CSRF protection, SameSite cookies, CSRF token, synchronizer token, double submit cookie, web security"
faq:
  - q: "What is a CSRF attack?"
    a: "Cross-Site Request Forgery tricks a logged-in user's browser into submitting a request to a site where they have an active session—changing email, transferring funds, or deleting data. The browser automatically attaches session cookies; the server cannot distinguish a forged request from a legitimate one without additional defenses."
  - q: "Does SameSite=Lax prevent all CSRF?"
    a: "SameSite=Lax blocks cookies on cross-site POST requests initiated from third-party pages and most cross-origin form submissions. It does not protect against all attack vectors—top-level GET with side effects (bad practice), SameSite=None cookies, or attacks from same-site subdomains. State-changing endpoints should use POST with CSRF tokens regardless."
  - q: "When do I still need CSRF tokens?"
    a: "Use synchronizer tokens for cookie-based session auth on mutating requests, especially with SameSite=None (required for cross-site embeds), legacy browser support, or defense in depth. Token-based auth (Authorization header) is not vulnerable to classic CSRF because browsers do not auto-attach custom headers on cross-origin form posts."
---

CSRF is the attack where evil.com submits a form to your-bank.com and the browser cheerfully attaches your session cookie because that is what cookies do. The server sees a authenticated request and obeys. Modern browsers mitigated much of this with SameSite cookies, but "much" is not "all." Production apps layer SameSite defaults, CSRF tokens on mutating routes, and correct HTTP verb discipline—not because one fix is insufficient alone, but because defense in depth survives misconfiguration.

## How CSRF works

```html
<!-- attacker.com -->
<form action="https://bank.com/transfer" method="POST">
  <input type="hidden" name="to" value="attacker" />
  <input type="hidden" name="amount" value="10000" />
</form>
<script>document.forms[0].submit()</script>
```

Victim visits attacker.com while logged into bank.com. Browser sends session cookie with POST. Bank processes transfer.

## SameSite cookie attribute

```http
Set-Cookie: session=abc123; Path=/; Secure; HttpOnly; SameSite=Lax
```

| Value | Cross-site GET | Cross-site POST | Use case |
|-------|----------------|-----------------|----------|
| Strict | No cookie | No cookie | High security, breaks some flows |
| Lax | Cookie on top nav | No cookie | Default in modern browsers |
| None | Cookie (requires Secure) | Cookie | Embeds, OAuth, cross-site APIs |

`Lax` blocks the classic CSRF POST from evil.com. Set explicitly—do not rely on browser defaults forever.

```python
# Django 4+ / modern frameworks
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # JS may need token for SPA—see below
```

## Synchronizer token pattern

Server generates unpredictable token bound to session; client submits on mutating requests:

```html
<form method="POST" action="/transfer">
  <input type="hidden" name="_csrf" value="RANDOM_TOKEN" />
  <!-- fields -->
</form>
```

Server validates token matches session before processing.

Express with csurf (deprecated—implement manually or use framework):

```javascript
import crypto from 'crypto';

function issueCsrfToken(req, res) {
  const token = crypto.randomBytes(32).toString('hex');
  req.session.csrfToken = token;
  return token;
}

function validateCsrf(req, res, next) {
  const token = req.body._csrf || req.headers['x-csrf-token'];
  if (token !== req.session.csrfToken) {
    return res.status(403).json({ error: 'Invalid CSRF token' });
  }
  next();
}

app.post('/transfer', validateCsrf, transferHandler);
```

## SPA + API patterns

SPAs reading token from cookie, sending in header (double-submit):

```javascript
// Server sets readable cookie (not HttpOnly)
// Set-Cookie: csrf=TOKEN; SameSite=Strict; Secure

const csrf = document.cookie.match(/csrf=([^;]+)/)?.[1];
fetch('/api/transfer', {
  method: 'POST',
  headers: { 'X-CSRF-Token': csrf },
  credentials: 'include',
  body: JSON.stringify(payload),
});
```

Server compares header token to cookie token—attacker cannot read cross-origin cookie to forge header.

Alternative: keep session HttpOnly; embed token in HTML shell or `/api/csrf` endpoint requiring same-origin fetch.

## JWT in Authorization header

```javascript
fetch('/api/transfer', {
  headers: { Authorization: `Bearer ${accessToken}` },
});
```

Cross-site forms cannot set Authorization header—classic CSRF does not apply. XSS stealing token is the threat instead.

## GET must not mutate

```http
GET /account/delete?id=123  ← never
POST /account/delete         ← with CSRF token
```

SameSite does not block cross-site GET with cookies on top-level navigation in Lax mode for some flows—idempotent GET prevents accidental side effects.

## OAuth and SameSite=None

Embedded widgets and cross-site OAuth flows need `SameSite=None; Secure`. Re-enable CSRF tokens on all state-changing cookie-auth endpoints—Lax protection absent.

## Framework defaults

- **Django** — CSRF middleware on by default
- **Rails** — authenticity_token in forms
- **Spring Security** — CsrfFilter with cookie or session token
- **Next.js Server Actions** — built-in origin check + POST-only

Verify custom API routes do not bypass middleware.

## Testing CSRF defenses

```bash
# Should fail without token
curl -X POST https://app.com/transfer \
  -H "Cookie: session=victim" \
  -d "to=attacker&amount=100"

# Should succeed with valid token
curl -X POST https://app.com/transfer \
  -H "Cookie: session=victim; csrf=TOKEN" \
  -H "X-CSRF-Token: TOKEN" \
  -d "..."
```

Integration tests assert 403 on missing token for cookie-auth POST routes.

## CSRF in SPA + API architectures

Single-page apps with separate API backends confuse CSRF defenses:

| Auth model | CSRF risk | Defense |
|------------|-----------|---------|
| Cookie session to API | High | SameSite + CSRF token header |
| Bearer token in memory | Low | No cookie = no CSRF |
| Cookie + CORS locked origin | Medium | SameSite Strict + origin check |

If your SPA uses `fetch` with `credentials: 'include'`, CSRF tokens are mandatory even with SameSite=Lax — subdomain takeover and older browsers remain risks.

```javascript
// Axios interceptor pattern
axios.defaults.headers.common['X-CSRF-Token'] =
  document.querySelector('meta[name="csrf-token"]').content;
```

Double-submit cookie pattern works when custom headers aren't feasible — token in cookie and form field, server compares.

## OAuth and CSRF

OAuth `state` parameter prevents CSRF on authorization callbacks — unrelated to form CSRF but often confused:

```javascript
const state = crypto.randomUUID();
sessionStorage.setItem('oauth_state', state);
window.location = `${AUTH_URL}?state=${state}&...`;
// Callback validates state matches sessionStorage
```

PKCE prevents authorization code interception — combine with `state` for defense in depth on public clients.

## Incident response

If CSRF vulnerability discovered in production:

1. Rotate session signing keys (invalidates all sessions)
2. Enable SameSite=Strict on session cookies immediately
3. Deploy CSRF middleware before public disclosure timeline
4. Audit logs for suspicious POST patterns from foreign Referer headers

Pair with [API security OWASP top 10](https://blog.michaelsam94.com/api-security-owasp-api-top-10/) for broader API hardening beyond CSRF.

## Common production mistakes

Teams get samesite tokens wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of samesite tokens fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [MDN SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [Chromium SameSite updates](https://www.chromium.org/updates/same-site/)
- [RFC 6265bis SameSite specification](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis)
