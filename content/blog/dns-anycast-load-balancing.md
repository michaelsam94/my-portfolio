---
title: "Anycast DNS and Load Balancing"
slug: "dns-anycast-load-balancing"
description: "Anycast advertises the same IP from multiple locations; BGP routes clients to the nearest PoP. How it works for CDNs, DNS resolvers, and DDoS absorption."
datePublished: "2025-10-24"
dateModified: "2025-10-24"
tags: ["DevOps", "Infrastructure"]
keywords: "anycast DNS, BGP anycast, CDN routing, Cloudflare anycast, global load balancing, GeoDNS"
faq:
  - q: "What is IP anycast?"
    a: "Anycast announces the same IP address from multiple geographic locations via BGP. Routers deliver packets to the topologically nearest announcement based on routing tables — not to all nodes. Used for DNS resolvers (1.1.1.1), CDN edges, and absorbing traffic near users."
  - q: "How is anycast different from GeoDNS?"
    a: "GeoDNS returns different IP addresses per client region based on DNS resolver location — application-layer steering. Anycast uses one IP globally; BGP steers at network layer. Anycast is faster to converge for failover; GeoDNS offers finer application-aware routing control."
  - q: "What are anycast tradeoffs?"
    a: "Anycast breaks TCP session stickiness if routing changes mid-connection — problematic for stateful protocols unless connection migration handled. All PoPs must accept and route anycast IP correctly; misconfiguration causes flapping. UDP-heavy workloads (DNS, QUIC) suit anycast well."
---

When you query `1.1.1.1`, you're not hitting one machine in San Francisco — you're hitting the Cloudflare rack closest to your ISP's peering point. Same IP, many servers, BGP picks the path. That's anycast, and it's how much of the internet scales global services without shipping users a region-specific hostname.

## Unicast, multicast, anycast

- **Unicast** — one IP → one destination
- **Multicast** — one IP → subscribed group
- **Anycast** — one IP → nearest of several destinations (from router's perspective)

Client doesn't know multiple servers share the address — routing decides.

## BGP announcement

Each PoP announces `203.0.113.0/24` via BGP to peers. Internet routes packets to **shortest AS path** / closest PoP. If London PoP dies, withdrawal causes reroute to next nearest — automatic failover at routing layer.

```
User in Berlin → BGP → Frankfurt PoP (203.0.113.1)
User in NYC    → BGP → Newark PoP   (203.0.113.1 same IP)
```

## Anycast for DNS resolvers

Public DNS (`8.8.8.8`, `1.1.1.1`) uses anycast — queries hit nearby resolver, low latency, DDoS traffic absorbed distributedly.

**Authoritative DNS** anycast serves your zone from global edges — queries resolve fast worldwide.

Contrast **GeoDNS**: `api.example.com` returns `us-east IP` or `eu-west IP` based on resolver geo — different IPs, DNS TTL caching affects failover speed.

## CDN edge anycast

Cloudflare, Fastly, Akamai edges anycast front IPs — HTTP hits nearest cache node. Cache miss fetches origin; hit serves locally.

Pair with **Anycast + shared state** challenges — edge caches local; purges propagate via control plane.

## Failover properties

Withdraw BGP route at failed site — convergence typically seconds to minutes depending on ISP. Faster than DNS TTL flip (often 300s default).

**Caveat:** some clients cache stale routes; monitoring route propagation during incidents matters.

## TCP and stateful protocols

TCP connection tied to one PoP mid-session. If routing changes (PoP failure, path shift), connection breaks — client retries, lands new PoP.

Mitigations:

- Short-lived connections (HTTP/1.1 keep-alive limits)
- QUIC/HTTP3 connection IDs with migration (emerging)
- Stateless request design

UDP DNS queries — perfect anycast fit (single packet/request).

## Anycast vs load balancer VIP

Data center **LB VIP** often anycast internally or ECMP hashes flows to LBs sharing VIP. Same concept, smaller scope.

Global anycast = internet-scale VIP.

## DDoS absorption

Attack traffic spreads to nearest edges with scrubbing capacity — not centralized origin drowning. Cloudflare/AWS Shield leverage anycast topology.

Rate limits and WAF at edge before origin sees traffic.

## Operational requirements

- **Same anycast IP config** on all PoPs — health checks withdraw bad nodes
- **Anti-spoofing / BCP38** — prevent becoming reflection amplifier
- **Consistent backend** — any PoP can serve or proxy; no PoP-specific state without replication
- **Monitoring** — per-PoP metrics, BGP looking glass, RIPE Atlas probes

## When not to use anycast

Stateful long-lived TCP without retry logic. Small single-region apps — complexity unjustified. Regulatory data residency requiring guaranteed EU-only processing — GeoDNS or regional endpoints explicit, not global anycast.

Hybrid common: anycast for static/CDN, GeoDNS for API region pinning.

## BGP and anycast routing mechanics

Anycast works because BGP advertises the same IP prefix from multiple locations:

```
PoP New York:  announces 203.0.113.0/24  (AS 64500)
PoP London:    announces 203.0.113.0/24  (AS 64500)
PoP Tokyo:     announces 203.0.113.0/24  (AS 64500)
```

Each upstream router picks the nearest PoP based on BGP path selection (shortest AS path, then closest metric). User in Berlin → London PoP. User in Sydney → Tokyo PoP. No DNS involved — routing decides.

Withdraw the BGP announcement from a failing PoP and traffic reroutes within seconds:

```bash
# Bird BGP daemon — withdraw route on health check failure
bird> withdraw route 203.0.113.0/24
# Traffic reroutes to next-nearest PoP within BGP convergence time (~30-60s)
```

Health checks must be independent per PoP — don't share a health check endpoint that all PoPs proxy to one origin.

## Anycast vs GeoDNS comparison

| | Anycast | GeoDNS |
|---|---|---|
| Routing | BGP path selection | DNS resolver location |
| Failover speed | 30–60s (BGP convergence) | TTL-dependent (60–300s) |
| Granularity | Per-router (city-level) | Per-DNS resolver (region-level) |
| Stateful apps | Problematic (TCP breaks on reroute) | Better (sticky sessions possible) |
| Setup complexity | BGP + anycast IP on all PoPs | DNS provider with geo routing |

Use anycast for stateless HTTP/CDN. Use GeoDNS when users need consistent regional endpoints (data residency, sticky sessions).

## DDoS mitigation with anycast

Anycast naturally distributes attack traffic:

```
10 Gbps attack from botnet
  → splits across 20 PoPs
  → ~500 Mbps per PoP
  → each PoP's scrubbing capacity handles it
```

Without anycast, 10 Gbps hits one origin. With anycast, each PoP absorbs its share. Combine with rate limiting and WAF at each PoP edge before traffic reaches origin.

Cloudflare, AWS Shield, and Akamai all use anycast topology for this reason — attack surface distributed by design.

## Failure modes

- **PoP serves stale/different content** — inconsistent backend state across PoPs
- **BGP route leak** — traffic redirected to wrong PoP or AS
- **Stateful TCP without retry** — connection breaks when BGP reroutes mid-session
- **Health check shared across PoPs** — all PoPs fail together; false withdrawal
- **No BCP38 anti-spoofing** — your anycast IP used in reflection attacks

## Production checklist

- Same anycast IP configuration on all PoPs
- Independent health checks per PoP
- BCP38 anti-spoofing enabled on all edge routers
- BGP route withdrawal tested (failover drill quarterly)
- Per-PoP metrics and alerting (latency, error rate, traffic volume)
- Stateless application design or session replication for anycast endpoints

## Resources

- [Cloudflare — What is Anycast?](https://www.cloudflare.com/learning/cdn/glossary/anycast-network/)
- [RIPE — Anycast best practices](https://www.ripe.net/publications/docs/ripe-501)
- [RFC 7094 — Architectural considerations for IP Anycast](https://www.rfc-editor.org/rfc/rfc7094)
- [AWS Global Accelerator — Anycast IPs](https://docs.aws.amazon.com/global-accelerator/latest/dg/what-is-global-accelerator.html)
- [Google Cloud — Cloud CDN and anycast](https://cloud.google.com/cdn/docs/overview)
