---
title: "AI Agents: Otp Brute Force Protection"
slug: "agent-otp-brute-force-protection"
description: "Rate-limit and harden OTP verification for agent account linking and step-up auth — entropy math, constant-time checks, progressive lockouts, and detection without locking out entire offices."
datePublished: "2025-12-22"
dateModified: "2025-12-22"
tags: ["AI Agents", "Security", "Authentication", "OTP"]
keywords: "OTP brute force protection, TOTP rate limiting, agent step-up authentication, constant-time OTP verify, credential stuffing OTP"
faq:
  - q: "How many guesses does a 6-digit OTP allow?"
    a: "A uniform 6-digit code has 10^6 = 1,000,000 possibilities. Without rate limits, an attacker submitting 100 guesses per second exhausts the space in under three hours. Real TOTP windows and lockouts must shrink effective attempts to single digits per user."
  - q: "Should OTP verification use the same rate limit for IP and user?"
    a: "Layer both. Per-user limits stop targeted attacks on one account; per-IP and global limits stop distributed sprays across many users. CAPTCHA or proof-of-work gates kick in when IP buckets exceed thresholds — before user lockout affects legitimate shared-NAT offices."
  - q: "Why constant-time comparison for OTP?"
    a: "Early-exit string comparison leaks how many digits matched via response timing — microsecond differences exploitable over many samples. Hash both sides and use `crypto.timingSafeEqual`, or use a vetted library like PyOTP that already constant-times."
  - q: "Do agent platforms need OTP if they use OAuth?"
    a: "Yes for step-up flows: linking a destructive tool (production deploy, treasury transfer), recovering API keys, or confirming human-in-the-loop approvals. OAuth proves identity once; OTP proves possession right now before irreversible agent actions."
---

Security researchers breached a staging agent console in eleven minutes last quarter — not by cracking AES, but by POSTing six-digit codes to `/v1/link-account/verify` faster than the team thought possible. The OTP implementation was textbook: HMAC-SHA1 TOTP, thirty-second window, codes stored nowhere (derived on the fly). What was missing: per-user attempt counters, IP-level throttling, constant-time comparison, and alerts when failure velocity crossed a floor. OTP brute force protection is not about picking longer codes; it is about shrinking the **effective** search space under adversarial throughput.

## Attack surface on agent OTP flows

Typical flows that need hardening:

1. **Email/SMS magic OTP** — user enters code to bind Slack or GitHub to an agent workspace
2. **TOTP step-up** — existing session must re-enter authenticator app code before enabling `deploy:production` tools
3. **Recovery codes** — single-use backup after device loss; higher value, lower entropy per code

Each endpoint is independent from OAuth token validation. Attackers bypass the IdP entirely and hammer verification directly.

```
Attacker                         Your API
   │                                 │
   │  POST /verify { user, code }    │  × 50,000/min
   │ ───────────────────────────────►│
   │◄─────────────────────────────── │  401 invalid (fast)
   │                                 │  no lockout → game over
```

## Entropy and window math

| OTP type | Space | Notes |
|----------|-------|-------|
| 6-digit numeric | 10^6 | Common; needs aggressive limits |
| 8-digit numeric | 10^8 | Better; still not sufficient alone |
| TOTP (6 digit, ±1 window) | ~3 × 10^6 effective | Accept current ± adjacent intervals |
| Alphanumeric 8 | 36^8 ≈ 2.8×10^12 | Recovery codes; single-use |

Assume attackers get **ten** valid guesses per account before lockout. For 6-digit TOTP with ±1 window, probability of success per lockout cycle is roughly 3×10^-5 — acceptable if lockouts escalate and alerts fire.

## Layered rate limiting

```python
import hashlib
import hmac
import time
from dataclasses import dataclass

@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_sec: int | None = None

class OtpRateLimiter:
    def __init__(self, redis):
        self.r = redis

    def _key(self, namespace: str, value: str) -> str:
        digest = hashlib.sha256(value.encode()).hexdigest()[:32]
        return f"otp:{namespace}:{digest}"

    def check_and_bump(self, user_id: str, ip: str) -> RateLimitResult:
        limits = [
            ("user", user_id, 5, 900),      # 5 fails / 15 min → lockout
            ("ip", ip, 30, 3600),           # 30 fails / hour → captcha
            ("global", "all", 5000, 60),    # platform fuse
        ]
        for namespace, ident, max_fails, window in limits:
            key = self._key(namespace, ident)
            count = self.r.incr(key)
            if count == 1:
                self.r.expire(key, window)
            if count > max_fails:
                ttl = self.r.ttl(key)
                return RateLimitResult(False, ttl if ttl > 0 else window)
        return RateLimitResult(True)

    def reset_user(self, user_id: str) -> None:
        self.r.delete(self._key("user", user_id))
```

On success, call `reset_user`. On failure, increment before returning generic error — never reveal whether the user exists.

## Constant-time verification

```typescript
import { timingSafeEqual, createHmac } from "crypto";
import { authenticator } from "otplib";

authenticator.options = { window: 1 }; // ±30s

export function verifyTotp(secret: string, code: string): boolean {
  // Normalize input — reject non-digits early (not secret-dependent)
  if (!/^\d{6}$/.test(code)) {
    // Burn fixed time to avoid format oracle
    timingSafeEqual(Buffer.alloc(32), Buffer.alloc(32));
    return false;
  }

  const expected = authenticator.generate(secret);
  // otplib check already constant-time; for email OTP compare hashes:
  const a = createHmac("sha256", "otp-pepper").update(code).digest();
  const b = createHmac("sha256", "otp-pepper").update(expected).digest();
  return timingSafeEqual(a, b);
}
```

For email OTP, store `HMAC(pepper, code)` in Redis with TTL — compare hashes, never plaintext codes in logs.

## Progressive lockout without punishing NAT

Blunt permanent lockouts after five failures strand entire companies behind one IP. Escalation ladder:

1. **Attempts 1–3** — generic "invalid code" (same HTTP status and body length)
2. **Attempts 4–5** — add 2^n second delay server-side (2, 4, 8… capped at 30s)
3. **Attempt 6+** — user-level lockout 15 minutes; require password re-auth or support channel
4. **IP > 30/hour** — CAPTCHA or Turnstile token required on next request
5. **Global fuse** — disable OTP verify platform-wide; page on-call (DDoS or bug)

```python
async def verify_otp_endpoint(request):
    user_id = request.user_id  # from session, not from body
    ip = request.client_ip
    code = request.json.get("code", "")

    rl = limiter.check_and_bump(user_id, ip)
    if not rl.allowed:
        return json({"error": "too_many_attempts"}, status=429,
                    headers={"Retry-After": str(rl.retry_after_sec)})

    if not verify_totp(user_secrets[user_id], code):
        await audit.log("otp_fail", user_id=user_id, ip=ip)
        await metrics.increment("otp_verify_failure")
        # Generic message — no "wrong digit" hints
        return json({"error": "invalid_code"}, status=401)

    limiter.reset_user(user_id)
    await metrics.increment("otp_verify_success")
    return json({"status": "verified"})
```

## Detection and response metrics

Track:

- `otp_verify_failure_rate` by tenant — spike may mean credential stuffing list
- `otp_lockout_total` — product signal for UX friction
- `otp_verify_latency_p99` — timing attacks often correlate with abnormal latency profiles
- Ratio of failures to SMS/email sends — pre-gen attack if sends are low but verify traffic high

Alert when failures exceed 10× baseline for ten minutes. Auto-enable CAPTCHA tier-wide before manual triage.

## Testing brute force defenses

```python
def test_lockout_after_five_failures(client, user):
    for _ in range(5):
        r = client.post("/verify", json={"code": "000000"})
        assert r.status_code == 401
    r = client.post("/verify", json={"code": "000000"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers

def test_no_user_enumeration(client):
    r1 = client.post("/verify", json={"code": "123456"})  # valid session user
    r2 = client.post("/verify-unauthenticated", json={"email": "nobody@x.com", "code": "123456"})
    assert r1.status_code == r2.status_code  # both 401, same body shape
```

Load-test with gradual ramp — ensure Redis INCR does not become the bottleneck before OTP logic does.

## Agent-specific considerations

Step-up OTP before enabling high-risk tools should bind verification to a **intent nonce**:

```json
{
  "intent": "enable_tool:github.merge_production",
  "nonce": "n_8f2a…",
  "expires_at": "2025-12-22T18:05:00Z"
}
```

The verify endpoint checks OTP **and** that the nonce matches the pending action in session — preventing replay of a generic "verified" flag for a different destructive operation five minutes later.

Human-in-the-loop approvals that display OTP in Slack must rate-limit by channel ID as well — compromised webhook should not get unlimited guesses.

## Closing note

Six digits is fine when the surrounding controls make billion-guess attacks impossible. Layer per-user, per-IP, and global limits; compare codes in constant time; escalate lockouts gradually; instrument failure velocity; bind successful verification to explicit intent. The staging breach postmortem ended with those controls plus a mandatory CAPTCHA after twenty IP-level failures — no code length change required.

## SMS and email OTP — delivery-side limits

TOTP apps sidestep SMS intercept, but many agent products still email six-digit codes for first-time linking. Rate-limit **sends** separately from **verifies**:

```python
SEND_LIMITS = [
    ("user", 3, 3600),   # max 3 OTP emails per hour per user
    ("ip", 10, 3600),    # max 10 send requests per IP per hour
]

def request_otp(user_id: str, ip: str) -> None:
    if not send_limiter.allow(user_id, ip):
        raise RateLimitError("wait_before_resend")
    code = secrets.randbelow(1_000_000)
    store_hash(user_id, hash_code(code), ttl=600)
    mailer.send_otp(user_id, code)  # never log code
```

Resend buttons must enforce sixty-second cooldown in UI **and** server — client-only timers do not stop scripts. Invalidate prior code hash when issuing a new one so only the latest OTP validates.

## Compliance logging without leaking secrets

Audit logs should record `otp_verify_failure` with `user_id`, `ip`, `user_agent`, and coarse `failure_reason` enum — never the submitted code. Retention policies differ: SOC2 often wants ninety days of auth events; GDPR may require deletion on erasure requests. Structured JSON logs integrate with SIEM rules:

```json
{"event":"otp_verify_failure","user_id":"u_123","ip":"203.0.113.4","attempt":4,"tenant":"acme"}
```

Correlate spikes with WAF blocks and geo anomalies before assuming brute force versus misconfigured mobile clock skew.

## Resources

- [RFC 6238 — TOTP: Time-Based One-Time Password Algorithm](https://datatracker.ietf.org/doc/html/rfc6238)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [NIST SP 800-63B Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [Redis INCR rate limiting pattern](https://redis.io/docs/latest/commands/incr/)
- [Cloudflare Turnstile (CAPTCHA alternative)](https://developers.cloudflare.com/turnstile/)
