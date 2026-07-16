---
title: "Defending Against DDoS at the Edge"
slug: "sec-rate-limit-ddos-defense"
description: "Mitigate DDoS and abuse at the edge: CDN scrubbing, rate limits, autoscaling traps, and layered defenses before traffic hits origin."
datePublished: "2025-06-08"
dateModified: "2025-06-08"
tags: ["Security", "DDoS", "Edge", "Infrastructure"]
keywords: "DDoS mitigation edge, rate limiting CDN, Cloudflare DDoS, WAF rate limit, volumetric attack defense, origin protection"
faq:
  - q: "Should rate limiting happen at CDN or application?"
    a: "Both. Edge rate limits absorb volumetric abuse and protect origin capacity cheaply. Application limits enforce business rules—per-user quotas, expensive endpoint throttles—with finer identity context. Edge alone cannot distinguish authenticated users behind NAT; origin alone drowns when traffic never reaches your code."
  - q: "What is the first sign of a layer 7 DDoS?"
    a: "Elevated 499/502 rates, cache miss storms on anonymous GETs, spike in unique User-Agents hitting login, or TLS handshake latency climbing while bandwidth looks normal. Layer 7 attacks mimic legitimate HTTP and exhaust CPU on WAF and app servers rather than saturating pipes."
  - q: "When do I enable under-attack mode?"
    a: "Enable managed challenge or under-attack mode when origin error rate exceeds SLO despite autoscaling, or when attack traffic exceeds baseline by an order of magnitude for sustained intervals. Pre-configure runbooks with DNS TTL lowered beforehand so failover to scrubbing center is fast."
---

Your API stayed up during the traffic spike—because Cloudflare cached static assets while origin melted on uncached `/api/search` POSTs at 200k RPS from a botnet. Volumetric DDoS still exists, but application-layer floods targeting expensive endpoints are the daily headache. Defense belongs at the edge first: absorb, classify, challenge, drop—before packets consume your Kubernetes bill.


## Architecture: edge before origin

```
Client → CDN/WAF → Rate limiter → Load balancer → App
                ↓
         DDoS scrubbing (always-on or on-demand)
```

Hide origin IP; allow inbound only from CDN provider ranges. Leaked origin IPs get bypass attacks—rotate and firewall.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Rate limiting strategies

| Layer | Key | Limit example |
|-------|-----|---------------|
| Edge | IP + path | 1000 req/min per IP on /api/* |
| Edge | API key header | 10000 req/hour per key |
| App | User ID | 10 exports/day |

Token bucket at edge; sliding window in Redis at app for authenticated fairness.

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
limit_req zone=api burst=200 nodelay;
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Challenge suspicious traffic

JS challenges and CAPTCHA impose cost on bots while browsers pass. Enable geo-fencing only as temporary measure—legitimate users use VPNs. Managed rulesets from Cloudflare, AWS Shield, or Fastly update faster than custom regex during zero-days.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Protect expensive endpoints

Search, report generation, and password reset are abuse magnets. Stricter limits, proof-of-work, or require authentication earlier in funnel. Move heavy work async with queue admission control.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Autoscaling is not defense

Scaling into attack raises cost; attackers win economically. Set max replicas and shed load with 503 + Retry-After rather than infinite scale. Budget alerts on egress and compute anomalies.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Observability

Dashboard: requests at edge vs origin, challenge solve rate, top paths, ASNs. Run game days simulating L7 flood against staging with approval.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


1. Confirm attack vs viral traffic (referrer, geographic skew)
2. Enable heightened WAF sensitivity
3. Tighten rate limits on targeted routes
4. Communicate status page if user-visible
5. Post-incident: add limit on exploited vector, file abuse report with upstream ISP/host

Hide origin IP; firewall allowlists CDN ranges only. Leaked origin IPs get bypass attacks—rotate and block direct access when discovered.

Game days simulate L7 flood against staging with approval. Runbooks link flag names to dashboards for payment_provider_enabled style kill switches.

Autoscaling into attack raises cost—set max replicas and shed load with 503 Retry-After rather than infinite scale. Budget alerts on egress anomalies catch economic denial of service.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

## Resources

- [Cloudflare DDoS protection documentation](https://developers.cloudflare.com/ddos-protection/)
- [AWS Shield documentation](https://docs.aws.amazon.com/waf/latest/developerguide/shield-chapter.html)
- [OWASP Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [RFC 6585: 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585.html)
- [NIST SP 800-189 DDoS guidance](https://csrc.nist.gov/publications/detail/sp/800-189/final)
