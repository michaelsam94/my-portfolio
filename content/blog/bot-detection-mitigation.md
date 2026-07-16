---
title: "Bot Detection and Mitigation"
slug: "bot-detection-mitigation"
description: "Bots scrape pricing, brute-force logins, and spam forms. Layer bot detection with rate limiting, behavioral signals, CAPTCHA challenges, and device fingerprinting without blocking legitimate users."
datePublished: "2024-12-19"
dateModified: "2024-12-19"
tags: ["Security", "Backend", "Bot Detection"]
keywords: "bot detection mitigation, rate limiting bots, CAPTCHA alternatives, device fingerprinting, web scraping prevention, bot management"
faq:
  - q: "What signals indicate bot traffic?"
    a: "High request rate from single IP or ASN, missing or generic User-Agent strings, no JavaScript execution (headless browsers often miss client-side challenges), perfect timing patterns (exactly 1 req/sec), missing cookies or referrer headers, and TLS fingerprint mismatches (curl vs Chrome JA3 hash)."
  - q: "When should I use CAPTCHA?"
    a: "Deploy CAPTCHA as a progressive challenge — not on every page load. Trigger on suspicious signals: failed login attempts, form submission from datacenter IP, rate limit threshold exceeded. Cloudflare Turnstile and hCaptcha are less painful than reCAPTCHA v2 checkboxes. Invisible challenges preserve UX for humans."
  - q: "Can rate limiting alone stop bots?"
    a: "Rate limiting stops naive bots and reduces abuse volume but not distributed scrapers using residential proxy networks. Combine rate limits with behavioral analysis, honeypot fields, and proof-of-work challenges. Rate limits are necessary but not sufficient."
---

Your pricing page gets 50,000 requests overnight from six ASNs in Virginia. Login attempts hit 200/minute with rotated credentials. Signup form submissions include URLs in every field. Bots aren't a future problem — they're hitting your endpoints right now, and the difference between "annoying" and "incident" is whether you detect them before they exfiltrate data or exhaust your infrastructure budget.

## Defense layers

```
Edge (CDN/WAF) → Rate limiting → Behavioral signals → Challenge → Application logic
```

No single layer catches everything. Layered defense raises attacker cost.

## Rate limiting

Token bucket per IP + per account:

```typescript
async function checkRateLimit(key: string, limit: number, windowSec: number): Promise<boolean> {
  const current = await redis.incr(key);
  if (current === 1) await redis.expire(key, windowSec);
  return current <= limit;
}

// Middleware
app.use('/api/', async (req, res, next) => {
  const ip = req.ip;
  const allowed = await checkRateLimit(`rl:ip:${ip}`, 100, 60);
  if (!allowed) return res.status(429).json({ error: 'rate_limit_exceeded' });
  next();
});
```

Tier limits by endpoint sensitivity:

| Endpoint | Limit | Window |
|----------|-------|--------|
| Login | 5 | 1 min per IP |
| Signup | 3 | 1 hour per IP |
| API read | 100 | 1 min per key |
| Search | 30 | 1 min per session |

## Honeypot fields

Hidden form fields bots fill but humans don't see:

```html
<input type="text" name="website" tabindex="-1" autocomplete="off"
       style="position:absolute;left:-9999px" aria-hidden="true">
```

```typescript
if (req.body.website) {
  // bot — silently accept but discard
  return res.status(200).json({ success: true });
}
```

Zero UX cost, catches unsophisticated form bots.

## Behavioral signals

Score requests and challenge above threshold:

```typescript
interface BotScore {
  signals: string[];
  score: number; // 0 = human, 100 = definite bot
}

function scoreRequest(req: Request): BotScore {
  const signals: string[] = [];
  let score = 0;

  if (!req.headers['user-agent']) { signals.push('no_ua'); score += 30; }
  if (isDatacenterIp(req.ip)) { signals.push('datacenter_ip'); score += 20; }
  if (!req.headers['accept-language']) { signals.push('no_lang'); score += 10; }
  if (req.headers['sec-fetch-site'] === undefined && isBrowserUA(req)) {
    signals.push('missing_sec_fetch'); score += 25;
  }
  if (await isHighVelocity(req.ip)) { signals.push('high_velocity'); score += 30; }

  return { signals, score };
}
```

Score > 60 → CAPTCHA challenge. Score > 80 → block.

## JavaScript challenges

Issue a token only after client-side proof:

```typescript
// Server generates challenge
const challenge = { nonce: randomBytes(16).toString('hex'), difficulty: 4 };
await redis.set(`challenge:${challenge.nonce}`, 'pending', 'EX', 300);

// Client solves (proof of work or simple JS execution)
// Server verifies token on subsequent requests
app.use(async (req, res, next) => {
  const token = req.headers['x-bot-token'];
  if (!token || !await redis.get(`verified:${token}`)) {
    return res.status(403).json({ challenge: generateChallenge() });
  }
  next();
});
```

Cloudflare, Akamai, and DataDome implement this at the edge — building custom is for specific compliance or cost requirements.

## TLS/JA3 fingerprinting

Headless Chrome, curl, and Python requests have distinct TLS handshake fingerprints (JA3/JA4 hashes). Match against known bot fingerprints at the load balancer or WAF level. False positives happen with unusual browser configs — use as a signal, not sole block criterion.

## Protecting specific assets

**Pricing/catalog scraping:** Require authenticated API keys, rate limit aggressively, serve slightly different data per session (canary traps), and monitor for sequential ID enumeration.

**Account takeover:** Rate limit login, detect credential stuffing (same password across many usernames from one IP), enforce MFA, and alert on impossible travel.

**API abuse:** Issue per-key quotas, require signed requests, and revoke keys with anomalous patterns.

## Monitoring

Dashboard:
- Request rate by ASN and country
- 429 response rate
- CAPTCHA challenge pass/fail ratio
- Login failure rate by IP
- Honeypot trigger count

Sudden honeypot triggers or CAPTCHA fail spikes = new bot campaign.

## Layered bot detection architecture

Combine signals — no single signal is sufficient:

```
Layer 1: Rate limiting (429)           — cheap, blocks volume
Layer 2: TLS/JA3 fingerprint           — blocks known bot libraries
Layer 3: Behavioral signals            — mouse movement, timing patterns
Layer 4: CAPTCHA/Turnstile             — blocks automated solvers
Layer 5: Honeypots                     — catches scrapers ignoring robots.txt
Layer 6: ML classifier                 — catches sophisticated bots
```

```python
async def bot_score(request: Request) -> float:
    score = 0.0
    if request.headers.get("user-agent", "") in KNOWN_BOT_UAS:
        score += 0.3
    if ja3_fingerprint(request) in KNOWN_BOT_JA3:
        score += 0.4
    if request_rate(request.ip) > RATE_THRESHOLD:
        score += 0.2
    if honeypot_triggered(request):
        score += 1.0  # immediate block
    if not behavioral_signals_present(request):
        score += 0.3
    return score

# score > 0.7 → CAPTCHA challenge
# score > 0.9 → block
```

Score-based approach avoids hard blocks on ambiguous signals — legitimate users with unusual configs get CAPTCHA, not 403.

## Credential stuffing detection

Distinct from scraping — credential stuffing targets login endpoints:

```python
CREDENTIAL_STUFFING_SIGNALS = {
    "same_password_many_usernames": 0.9,  # one password, 50 usernames
    "high_login_failure_rate": 0.7,        # >80% failures from IP
    "sequential_username_pattern": 0.8,    # user1, user2, user3...
    "impossible_travel": 0.6,            # login from two countries in 5 min
}

async def detect_credential_stuffing(ip: str, window_minutes: int = 15) -> bool:
    attempts = await get_login_attempts(ip, window_minutes)
    if len(attempts) < 10:
        return False
    unique_usernames = len(set(a.username for a in attempts))
    failure_rate = sum(1 for a in attempts if not a.success) / len(attempts)
    return unique_usernames > 20 and failure_rate > 0.8
```

Rate limit login endpoints aggressively: 5 attempts per username per 15 minutes, 100 attempts per IP per hour.

## Honeypot implementation

Invisible traps for scrapers that ignore robots.txt:

```html
<!-- Hidden from humans, visible to scrapers -->
<a href="/admin/users/export" aria-hidden="true"
   style="position:absolute;left:-9999px" tabindex="-1">
  Admin Export
</a>
```

```python
@app.get("/admin/users/export")
async def honeypot(request: Request):
    await bot_registry.block_ip(request.client.host, reason="honeypot")
    await alert("Honeypot triggered", ip=request.client.host)
    return Response(status_code=404)  # don't reveal it's a trap
```

Any request to honeypot URL = bot. Block IP immediately, no CAPTCHA opportunity.

## Failure modes

- **Single signal blocking** — JA3 fingerprint alone blocks legitimate unusual browsers
- **No rate limiting on login** — credential stuffing succeeds before detection
- **CAPTCHA on every request** — destroys UX for legitimate users
- **Honeypot visible to humans** — accessibility tools expose hidden links; use aria-hidden carefully
- **No monitoring dashboard** — bot campaign undetected until server overload

## Production checklist

- Multi-layer scoring (rate limit + fingerprint + behavioral + CAPTCHA)
- Login endpoint: 5 attempts/username/15min, 100 attempts/IP/hour
- Honeypot URLs on sensitive paths — block on trigger without CAPTCHA
- CAPTCHA/Turnstile for ambiguous scores (0.7–0.9), hard block above 0.9
- Dashboard: 429 rate, CAPTCHA pass/fail, honeypot triggers, login failure rate
- Alert on honeypot spike or CAPTCHA fail rate >50%

## Resources

- [OWASP Automated Threats to Web Applications](https://owasp.org/www-project-automated-threats-to-web-applications/)
- [Cloudflare Bot Management](https://developers.cloudflare.com/bots/)
- [Cloudflare Turnstile (CAPTCHA alternative)](https://developers.cloudflare.com/turnstile/)
- [JA3 TLS fingerprinting](https://github.com/salesforce/ja3)
- [Redis rate limiting patterns](https://redis.io/docs/reference/patterns/rate-limiting/)
