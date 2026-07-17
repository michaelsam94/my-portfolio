---
title: "AI Agents: Ip Reputation Scoring"
slug: "agent-ip-reputation-scoring"
description: "Ip Reputation Scoring: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-12-06"
dateModified: "2025-12-06"
tags: ["AI", "Agent"]
keywords: "agent, ip, reputation, scoring, ai, production, engineering, architecture"
faq:
  - q: "Why do agent platforms need IP reputation scoring beyond standard WAF rules?"
    a: "Agents expose expensive tool endpoints—LLM calls, code execution, database writes—that attackers probe with credential stuffing and prompt injection at scale. IP reputation adds a cheap first gate before token spend, complementing auth and rate limits with signals about datacenter origin, historical abuse, and botnet membership."
  - q: "Should agents block or challenge low-reputation IPs automatically?"
    a: "Default to challenge (CAPTCHA, proof-of-work, or stricter rate limits) for ambiguous scores; block only high-confidence bad IPs from curated feeds. Hard blocks on noisy feeds cause false positives for corporate NAT and mobile carriers—agents lose legitimate users silently if you block without observability."
  - q: "How do you combine IP reputation with agent session identity?"
    a: "Score the effective reputation as min(ip_score, account_score) after authentication, or blend with device signals. Pre-auth, IP reputation gates ingress; post-auth, user reputation should dominate so one bad IP does not permanently stain a verified account without separate fraud review."
  - q: "What latency budget is realistic for IP lookup in agent request paths?"
    a: "Target sub-5 ms p99 with local LRU cache and async refresh from threat intel feeds. Never block the hot path on synchronous third-party API calls—serve stale cache with TTL and background updates; fail open with alert if feeds are unreachable unless you operate in high-security mode."
---
Within six hours of launching a public coding agent, 40% of unauthenticated `/api/agent/run` traffic originated from ASNs associated with residential proxy rotation and known scanner blocklists. Rate limiting alone burned cloud budget—each request still hit auth parsing and partial orchestration. IP reputation scoring dropped that noise by 78% before any LLM token was spent, while legitimate corporate NAT users passed via cached neutral scores and stepped-up challenges only on anomaly spikes.

IP reputation scoring assigns a risk signal to source addresses using threat feeds, historical behavior, ASN heuristics, and your own telemetry. For agent platforms, it is an **economics and abuse** control—not a substitute for authentication. This deep dive covers signal sources, scoring architecture, cache design, integration with agent middleware, and the operational tradeoffs between fail-open and fail-closed postures.

## Signal sources and score composition

Composite scores work better than single feeds:

| Signal | Weight (example) | Notes |
|--------|------------------|-------|
| Commercial threat intel (Spamhaus, etc.) | High for listed IPs | False positives on shared NAT |
| Historical agent abuse (your logs) | Highest when present | First-party ground truth |
| ASN classification (hosting vs ISP) | Medium | Datacenter egress often higher risk for consumer agents |
| Geo velocity | Medium | Same account impossible travel |
| Request pattern heuristics | Low pre-auth | Synergy with rate limits |

```
Request ──▶ Edge middleware ──▶ IP reputation service ──▶ {score, labels, ttl}
                  │                      │
                  │                      ├── local cache (Redis)
                  │                      └── async feed ingest
                  ▼
         allow | challenge | throttle | block
                  │
                  ▼
            Agent orchestrator
```

Normalize scores to 0–100 for policy consistency. Store **labels** (`TOR_EXIT`, `SCANNER`, `DATACENTER`, `FIRST_PARTY_ABUSE`) for explainability in security dashboards—not just a number.

## Scoring service implementation

```python
from dataclasses import dataclass
from enum import Enum
import time


class Action(Enum):
    ALLOW = "allow"
    CHALLENGE = "challenge"
    THROTTLE = "throttle"
    BLOCK = "block"


@dataclass
class ReputationResult:
    ip: str
    score: int  # 0 = benign, 100 = malicious
    labels: list[str]
    cached: bool
    as_of: float


class IpReputationScorer:
    def __init__(self, cache, feeds, first_party_store):
        self.cache = cache
        self.feeds = feeds
        self.first_party = first_party_store

    def score(self, ip: str) -> ReputationResult:
        cached = self.cache.get(ip)
        if cached and not self._expired(cached):
            return cached

        labels = []
        score = 0

        if self.first_party.is_banned(ip):
            labels.append("FIRST_PARTY_ABUSE")
            score = max(score, 95)

        for feed in self.feeds:
            hit = feed.lookup(ip)
            if hit:
                labels.extend(hit.labels)
                score = max(score, hit.severity)

        asn = self.feeds.asn_info(ip)
        if asn and asn.category == "hosting":
            labels.append("DATACENTER")
            score = max(score, 35)

        result = ReputationResult(
            ip=ip,
            score=min(score, 100),
            labels=sorted(set(labels)),
            cached=False,
            as_of=time.time(),
        )
        self.cache.set(ip, result, ttl=self._ttl_for(score))
        return result

    def _ttl_for(self, score: int) -> int:
        if score >= 80:
            return 3600
        if score >= 40:
            return 900
        return 300

    def _expired(self, result: ReputationResult) -> bool:
        age = time.time() - result.as_of
        return age > self._ttl_for(result.score)
```

First-party bans override commercial feeds—your incident data is authoritative.

## Policy mapping and agent-specific thresholds

Agent endpoints cost money. Tighter thresholds on unauthenticated routes:

```typescript
import { Action, ReputationResult } from "./reputation";

interface PolicyContext {
  route: string;
  authenticated: boolean;
  tenantTier: "free" | "paid" | "enterprise";
}

export function decideAction(
  rep: ReputationResult,
  ctx: PolicyContext,
): Action {
  const { score, labels } = rep;

  if (labels.includes("FIRST_PARTY_ABUSE")) return Action.BLOCK;

  if (!ctx.authenticated && ctx.route.startsWith("/api/agent/")) {
    if (score >= 75) return Action.BLOCK;
    if (score >= 45) return Action.CHALLENGE;
    if (score >= 25) return Action.THROTTLE;
  }

  if (ctx.authenticated && ctx.tenantTier === "enterprise") {
    // Prefer friction over false blocks for paying customers
    if (score >= 85) return Action.CHALLENGE;
    return Action.ALLOW;
  }

  if (score >= 90) return Action.BLOCK;
  if (score >= 60) return Action.CHALLENGE;
  return Action.ALLOW;
}
```

Log every `BLOCK` and `CHALLENGE` with IP, labels, route, and session ID for false-positive review.

## Caching and feed ingestion

Synchronous feed API calls on every request do not scale. Pattern:

1. **Edge cache** — Redis with millions of keys; LRU eviction for long tail
2. **Background ingester** — refresh hot IPs every 5 min; cold on first touch
3. **Bloom filter** — fast negative for clearly benign ranges (optional)

Fail-open vs fail-closed when feeds are stale:

- **Fail-open (default)** — allow with alert if feeds down >15 min; avoids outage
- **Fail-closed** — block unauthenticated agent runs only; requires on-call runbook

Document the business choice explicitly—security vs availability.

## IPv6, NAT, and carrier-grade CGNAT

IPv6 /64 allocations behave differently from IPv4 /32. Scoring entire /64 too aggressively blocks mobile users; too loosely misses rotating addresses within a subnet.

Practices:

- Store reputation at /64 granularity for IPv6 with higher challenge threshold
- Exempt known enterprise egress ranges via allowlist file
- Decay scores over time—yesterday's scanner IP may be reassigned

```python
def normalize_ip_key(ip: str) -> str:
    import ipaddress
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address):
        network = ipaddress.ip_network(f"{addr}/64", strict=False)
        return str(network)
    return str(addr)
```

## Integration with agent observability

Metrics to emit:

- `ip_reputation_decisions_total{action, route}`
- `ip_reputation_score_histogram`
- `ip_reputation_cache_hit_rate`
- `ip_reputation_feed_lag_seconds`
- `estimated_tokens_saved` — blocked requests × avg tokens that would have run

Correlate with `agent_tool_invocations` to prove ROI to finance—not just security.

## Privacy and compliance

IP addresses are personal data in GDPR contexts. Retention policies: aggregate scores after 30 days; delete raw IP logs per DPA. Document legitimate interest for abuse prevention.

Do not sell reputation data derived from user traffic without consent.

## Testing and false-positive management

- **Fixture IPs** — known Tor exits, your office NAT, major cloud provider ranges
- **Replay** — sanitized production logs through scorer; measure block rate drift after feed updates
- **Appeal path** — support workflow to allowlist false positives with expiry
- **Game day** — disable primary feed; verify fail-open behavior

Run A/B on challenge vs block thresholds before tightening production policy.

## Agent prompt injection and IP reputation

IP reputation does not detect prompt injection from benign IPs—the complement is content moderation and tool sandboxing. Reputation reduces **volume** of automated probing so downstream defenses see signal, not noise.

Combine with per-tenant rate limits and token budgets for defense in depth.

## Feeding first-party abuse back into scores

Commercial feeds lag your own attack patterns. Close the loop:

1. **Detection** — rate limit trips, tool sandbox escapes, prompt injection classifiers fire
2. **Label** — mark `(ip, asn, fingerprint)` tuples in abuse store with decay TTL
3. **Promotion** — repeated offenses within 24h elevate to `FIRST_PARTY_ABUSE`
4. **Review** — weekly export of blocked IPs for false-positive appeals

```python
def record_abuse_event(ip: str, event_type: str, store) -> None:
    store.increment(f"abuse:{ip}", window_hours=24)
    count = store.get_count(f"abuse:{ip}")
    if count >= 5 and event_type in ("tool_escape", "credential_stuff"):
        store.ban(ip, reason="FIRST_PARTY_ABUSE", ttl_hours=72)
        notify_security_dashboard(ip, count, event_type)
```

Decay matters—café Wi-Fi NAT should not stay banned for months after one abusive client. TTL bans with exponential backoff for repeat offenders balance abuse prevention and user experience.

## Deployment at the edge vs origin

Low-latency scoring belongs at CDN edge when possible (Cloudflare, Fastly compute). Origin scoring adds RTT on every agent request.

Pattern:

- Edge: coarse decision from cached score + ASN allow/deny lists
- Origin: refine with account context post-auth

Keep edge and origin policy versions in sync via config hash header—debug "edge allowed, origin blocked" mismatches quickly during incidents.

Document which decisions are edge-final vs origin-final in runbooks so on-call does not chase the wrong layer.

## The takeaway

IP reputation scoring protects agent economics by filtering high-volume abuse before expensive orchestration. Compose first-party abuse data with threat feeds, cache aggressively, map scores to allow/challenge/throttle/block with tier-aware policies, and measure false positives relentlessly. It is a gate—not authentication—and must fail gracefully when feeds lag.

## Resources

- [Spamhaus IP blocklist documentation](https://www.spamhaus.org/blocklists/)
- [MaxMind minFraud and GeoIP](https://dev.maxmind.com/)
- [Cloudflare IP reputation and Bot Management](https://developers.cloudflare.com/bots/)
- [OWASP Automated Threats to Web Applications](https://owasp.org/www-project-automated-threats-to-web-applications/)
- [Companion: Rate Limit Token Bucket](/agent-rate-limit-token-bucket/)
- [Companion: Behavioral Anomaly Login](/agent-behavioral-anomaly-login/)
