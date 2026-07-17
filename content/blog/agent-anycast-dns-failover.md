---
title: "AI Agents: Anycast Dns Failover"
slug: "agent-anycast-dns-failover"
description: "Designing anycast DNS failover for global agent API endpoints — BGP health withdrawal, health probe semantics, TTL tradeoffs, and drills that prove failover works."
datePublished: "2026-04-09"
dateModified: "2026-04-09"
tags: ["AI", "Agent", "Anycast"]
keywords: "anycast DNS failover, BGP route withdrawal, global load balancing, health checks API gateway, Route53 latency routing, Cloudflare load balancing, agent API availability"
faq:
  - q: "How does anycast DNS failover differ from DNS round-robin?"
    a: "Anycast advertises the same IP prefix from multiple PoPs via BGP; routing pulls clients to the nearest healthy edge. Failover withdraws BGP announcements or stops advertising the prefix from a failed site — traffic reroutes at network layer, often faster than waiting for DNS TTL expiry. DNS round-robin returns multiple A records with no health awareness; clients may persist to dead IPs until TTL expires."
  - q: "What health checks work for LLM agent API backends?"
    a: "Use lightweight synthetic inference or auth endpoints that validate the full path: edge TLS, gateway auth, model router reachability, and optional GPU queue depth signal. Avoid marking healthy when only nginx responds — agents need end-to-end confirmation that orchestration and model backends accept work."
  - q: "What TTL should agent API DNS records use?"
    a: "For anycast with BGP failover, authoritative TTL can be higher (300–3600s) because failover happens at routing layer. For unicast multi-region with DNS-based failover, use lower TTL (30–60s) on critical records — accepting increased query load and cache churn. Streaming agent sessions may need connection draining beyond TTL math."
  - q: "How do you test anycast failover without causing an outage?"
    a: "Run controlled drills: withdraw BGP from one PoP in staging mirrors, use traffic shadowing, and monitor RUM latency split by region. Production drills use maintenance windows with canary prefixes or weighted traffic shift before full withdrawal. Verify synthetic probes from external vantage points detect the change within your SLO."
---
The incident lasted eleven minutes. A GPU rack in `eu-west` lost power; our agent API stayed "up" because Cloudflare still announced the anycast prefix — but packets landed on black-holed backends until health checks failed three consecutive times, then BGP withdrew. European users saw 30-second hangs on streaming completions while TCP retried dead paths. Anycast DNS failover wasn't broken; our **health probe semantics** and **draining policy** were. Global agent APIs — long-lived SSE streams, fat payloads, bursty tool callbacks — punish naive failover configs that work fine for static marketing sites.

This is how to architect anycast and DNS failover when the product is an agent platform, not a CDN-hosted brochure.

## Anycast vs DNS failover: complementary layers

**Ananycast** (network layer): Same IP announced from multiple locations. Internet routing delivers packets to topologically nearest healthy site. Failure removes advertisement; routers converge to alternate sites — typically seconds to low minutes depending on prefix size and provider.

**DNS failover** (name layer): Authoritative DNS changes answers (A/AAAA/CNAME) or uses routing policies (latency, geolocation, weighted) based on health. Clients cache per TTL; stale records persist until expiry unless apps bypass cache.

Production agent stacks use both:

```
Client → DNS resolves api.agents.example.com → anycast IP (or CNAME to provider)
       → BGP routes to nearest PoP
       → PoP health check fails → withdraw route OR DNS policy shifts weight
       → Client reroutes (BGP) or re-resolves (DNS)
```

Anycast handles regional brownouts fast. DNS handles blue-green region migrations, multi-cloud backends without shared anycast, and gradual traffic shifts during deploys.

## Health probes that match agent reality

A `/healthz` returning 200 from kubelet proves the pod exists — not that agents can complete work. Probes should reflect user-visible success:

```python
# probe/agent_readiness.py — run from each PoP edge controller
import httpx
import time

PROBE_PROMPT = "Reply with exactly: OK"
MAX_LATENCY_MS = 8000
TIMEOUT_S = 10

def check_agent_path(base_url: str, api_key: str) -> tuple[bool, dict]:
    start = time.monotonic()
    try:
        r = httpx.post(
            f"{base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "probe-model-smallest",
                "messages": [{"role": "user", "content": PROBE_PROMPT}],
                "max_tokens": 5,
            },
            timeout=TIMEOUT_S,
        )
        latency_ms = (time.monotonic() - start) * 1000
        body_ok = r.status_code == 200 and "OK" in r.json()["choices"][0]["message"]["content"]
        healthy = body_ok and latency_ms < MAX_LATENCY_MS
        return healthy, {"latency_ms": latency_ms, "status": r.status_code}
    except Exception as e:
        return False, {"error": str(e)}
```

Tune probe intervals and failure thresholds for **flapping resistance**:

- **Interval:** 10–30s at edge; 5s only if convergence SLO demands it
- **Unhealthy threshold:** 3 consecutive failures (~30–90s) before withdrawal
- **Healthy threshold:** 2 consecutive successes before readvertising — prevents oscillation

Include **dependency checks** as degraded states: if vector DB is down, drain new sessions but allow in-flight streams to complete (HTTP 503 with `Retry-After` on new connections).

## BGP withdrawal and convergence behavior

When a PoP goes unhealthy, your provider (Cloudflare, Fastly, AWS Global Accelerator, self-managed BGP on metal) stops announcing the prefix from that site or shifts weight in traffic manager.

Factors affecting convergence:

| Factor | Effect |
|--------|--------|
| Prefix size (/24 vs /32) | Larger aggregates propagate faster; some providers filter long prefixes |
| BGP hold timers | Local preference and provider tuning dominate user-visible cutover |
| Active TCP sessions | Existing connections don't magically migrate — they reset or hang |
| QUIC vs TCP | QUIC connection migration can help mobile clients; most agent SDKs use HTTP/2 TCP |

For streaming agent responses, **connection draining** matters as much as BGP:

```yaml
# drain policy pseudocode — edge controller
on_health_degraded:
  stop_admitting_new_connections: true
  max_drain_seconds: 120
  force_close_after: 180
on_health_recovered:
  require_warmup_probes: 2
  ramp_weight_percent: [10, 50, 100]  # over 3 minutes
```

Without draining, users mid-stream see truncated completions — functionally an outage even if failover "worked."

## DNS TTL and resolver behavior

Agent mobile and web clients cache DNS aggressively. If you rely on DNS failover without anycast:

```dns
api.agents.example.com.  60  IN  A  203.0.113.10   ; primary
api.agents.example.com.  60  IN  A  198.51.100.20   ; secondary (backup via health policy)
```

60-second TTL means up to one minute of sticky bad IPs after failure — plus resolver-specific minimums (some ISPs clamp to 300s).

**Recommendations:**

- **Anycast front door:** TTL 300–3600s acceptable; failover at IP routing layer
- **DNS-only multi-region:** TTL 30–60s on API records; monitor authoritative QPS increase
- **Never CNAME chains** deep enough to multiply TTL confusion

Use **split-horizon DNS** cautiously for internal agent workers calling regional backends — external anycast IP for customers, internal service discovery for east-west mesh traffic.

## Architecture patterns by scale

**Managed anycast (Cloudflare, Fastly):** Fastest path for most teams. Load balancing pools map origins per region; health monitors drive steering. Agent APIs terminate TLS at edge; origin pools per GPU cluster.

**Cloud DNS + GLB (GCP Cloud Load Balancing, AWS Route 53 + Global Accelerator):** Anycast IP via provider accelerator; health checks on regional backend services. Good when agents already live on one cloud with multi-region GKE/EKS.

**Self-managed BGP (Equinix Metal, bare metal):** Maximum control, highest ops burden. Justified at massive scale or regulatory data residency requiring owned prefixes.

Example Route 53 latency policy with health check:

```hcl
resource "aws_route53_record" "agent_api" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "api.agents.example.com"
  type    = "A"
  set_identifier = "eu-west"

  latency_routing_policy {
    region = "eu-west-1"
  }

  health_check_id = aws_route53_health_check.eu.id
  records         = [aws_globalaccelerator.accelerator.ip_sets[0].ip_addresses[0]]
}
```

Pair with **synthetic monitoring from external vantage points** (Catchpoint, Datadog Synthetics, ThousandEyes) — provider-internal health can mark healthy while transcontinental paths fail.

## Observability and failover SLOs

Dashboard per region/PoP:

- Request rate and error rate (4xx/5xx split)
- p50/p99 TTFB and stream inter-chunk latency
- Active BGP announcement status
- Health probe success rate and latency
- DNS answer distribution from external resolvers

Define failover SLO: "95% of clients converge to healthy PoP within 90 seconds of simulated regional failure." Measure with quarterly game days.

Alert on **asymmetric routing**: `eu-west` errors spike while `us-east` idle — health checks may not have fired if edge still accepts TCP but origins reject inference load.

Log `X-Edge-Location` or equivalent response headers; correlate user reports with PoP assignment.

## Runbook: regional failure checklist

1. Confirm scope: single origin pool vs entire region vs global DNS issue (`dig +trace`, BGP looking glass)
2. Check health probe dashboard — false negative? dependency blip?
3. If intentional drain: verify weight at 0%, connections draining
4. If unintentional: manual BGP withdrawal or set pool unhealthy to force convergence
5. Communicate status page — agent APIs degrade subtly (slow streams) before hard 503s
6. Post-incident: probe gap analysis, drain timer tuning, client SDK retry idempotency review

Client SDKs should retry idempotent requests with exponential backoff and **region-agnostic endpoints** — hardcoding regional hostnames defeats anycast.

Webhooks and async tool callbacks need the same thinking: if your agent calls customer systems from `eu-west` workers but failover shifts orchestration to `us-east`, egress IP allowlists on customer firewalls break unless you publish stable anycast egress ranges or proxy callbacks through region-neutral infrastructure. Failover planning that ignores outbound paths causes silent tool failures long after user-facing API health returns green.

Document **RTO and RPO for inference availability** separately from data persistence. DNS and BGP failover restore API reachability quickly; in-flight agent state in regional Redis or unfinished tool sagas may not survive regional loss without cross-region replication you planned explicitly.

Anycast DNS failover for agent platforms is a stack: BGP or traffic-manager steering, probes that validate inference paths, drain policies for long streams, TTL choices matched to your layer, and game days that prove eleven-minute hangs become ninety-second blips. The network will fail; design so routing and DNS argue in your favor when they do.

## Resources

- [Cloudflare Load Balancing and health monitors](https://developers.cloudflare.com/load-balancing/)
- [AWS Route 53 health checks and failover routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover.html)
- [Google Cloud load balancing overview (global anycast)](https://cloud.google.com/load-balancing/docs/load-balancing-overview)
- [RIPE Atlas — Internet measurement probes](https://atlas.ripe.net/)
- [BGP best practices (RFC 7454)](https://datatracker.ietf.org/doc/html/rfc7454)
