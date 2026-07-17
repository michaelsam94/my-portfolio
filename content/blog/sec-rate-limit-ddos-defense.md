---
title: "Defending Against DDoS at the Edge"
slug: "sec-rate-limit-ddos-defense"
description: "Mitigate DDoS and abuse at the edge: CDN scrubbing, rate limits, autoscaling traps, and layered defenses before traffic hits origin."
datePublished: "2025-06-08"
dateModified: "2026-07-17"
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

## Challenge suspicious traffic

JS challenges and CAPTCHA impose cost on bots while browsers pass. Enable geo-fencing only as temporary measure—legitimate users use VPNs. Managed rulesets from Cloudflare, AWS Shield, or Fastly update faster than custom regex during zero-days.

## Protect expensive endpoints

Search, report generation, and password reset are abuse magnets. Stricter limits, proof-of-work, or require authentication earlier in funnel. Move heavy work async with queue admission control.

## Autoscaling is not defense

Scaling into attack raises cost; attackers win economically. Set max replicas and shed load with 503 + Retry-After rather than infinite scale. Budget alerts on egress and compute anomalies.

## Observability

Dashboard: requests at edge vs origin, challenge solve rate, top paths, ASNs. Run game days simulating L7 flood against staging with approval.

1. Confirm attack vs viral traffic (referrer, geographic skew)
2. Enable heightened WAF sensitivity
3. Tighten rate limits on targeted routes
4. Communicate status page if user-visible
5. Post-incident: add limit on exploited vector, file abuse report with upstream ISP/host

Hide origin IP; firewall allowlists CDN ranges only. Leaked origin IPs get bypass attacks—rotate and block direct access when discovered.

Game days simulate L7 flood against staging with approval. Runbooks link flag names to dashboards for payment_provider_enabled style kill switches.

Autoscaling into attack raises cost—set max replicas and shed load with 503 Retry-After rather than infinite scale. Budget alerts on egress anomalies catch economic denial of service.

Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Design choices that matter for sec rate limit ddos defense

Security work around sec rate limit ddos defense fails when it is treated as a checklist instead of a feedback loop. Start from a threat model: who is the adversary, what is the asset, and which control fails closed if misconfigured. For sec rate limit ddos defense, I write the abuse cases first — credential stuffing, dependency CVE, log exfiltration, CSRF on cookie sessions — then map each to a detection signal and an owner.

### Controls that actually change outcomes

| Control | Where enforced | Failure mode |
|---------|----------------|--------------|
| Input validation | API edge | Injection / mass assignment |
| Authn | IdP + resource server | Stolen session / token |
| Authz | Policy engine | Broken object level auth |
| Secrets | Vault / KMS | Long-lived plaintext keys |

Wire these into CI where possible. A control that only lives in a wiki page will not survive the next on-call rotation.

### Incident-shaped verification

Run a tabletop: assume the primary control for sec rate limit ddos defense failed at 02:00. Who gets paged? What is the first command? How do you revoke access or roll credentials without cascading outages? If you cannot answer in under five minutes, the design is incomplete.

### Measurement

Track mean time to remediate findings related to sec rate limit ddos defense, false-positive rate of scanners, and number of production changes that bypass the gate. Celebrate burn-down of legacy exceptions with expiry dates — permanent exceptions are just vulnerabilities with paperwork.

### Pitfalls specific to this domain

Avoid denylist-only validation, logging secrets "temporarily," and blocking every advisory at severity informational. Prefer allowlists, structured redaction, and severity+reachability for gates. Document the dual-credential or dual-key window whenever rotation is involved so operators do not revoke early.

## Resources

- [Cloudflare DDoS protection documentation](https://developers.cloudflare.com/ddos-protection/)
- [AWS Shield documentation](https://docs.aws.amazon.com/waf/latest/developerguide/shield-chapter.html)
- [OWASP Denial of Service Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [RFC 6585: 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585.html)
- [NIST SP 800-189 DDoS guidance](https://csrc.nist.gov/publications/detail/sp/800-189/final)