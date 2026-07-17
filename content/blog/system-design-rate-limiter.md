---
title: "System Design: Distributed Rate Limiter"
slug: "system-design-rate-limiter"
description: "Design a distributed rate limiter using token bucket and sliding window algorithms, with Redis-backed counters that enforce limits across API gateway instances."
datePublished: "2025-11-09"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "distributed rate limiter design, token bucket algorithm, sliding window counter, Redis rate limiting"
faq:
  - q: "Token bucket vs sliding window?"
    a: "Token bucket allows controlled bursts; sliding window enforces hard cap in rolling period."
  - q: "Multi-server rate limiting?"
    a: "Central Redis with atomic Lua scripts; all gateways read/write shared counters."
  - q: "HTTP status for rate limits?"
    a: "429 with Retry-After and X-RateLimit-* headers on success responses too."
faqAnswers:
  - question: "When is system design rate limiter the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design rate limiter?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design rate limiter safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Fifty thousand requests per minute from one API key starved the database until Redis token bucket returned 429 and everyone else recovered.

## Symptoms users report

Production engineering for distributed rate limiting across API gateway instances. Review 1: teams that treat distributed rate limiting across API gateway instances as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## How to confirm root cause

Production engineering for distributed rate limiting across API gateway instances. Review 2: teams that treat distributed rate limiting across API gateway instances as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Fix that sticks

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. Local in-memory counters without shared state — limits fail across instances That mistake is expensive because it only surfaces under real traffic mixes.

            ```typescript
            // Operational hook for distributed rate limiting across API gateway instances
export async function applyPattern(ctx: RequestContext) {
  const start = performance.now();
  try {
    return await execute(ctx);
  } finally {
    reportMetric("system-design-rate-limiter", performance.now() - start);
  }
}
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.

## Reference patterns

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. Local in-memory counters without shared state — limits fail across instances That mistake is expensive because it only surfaces under real traffic mixes.

            ```typescript
            // Operational hook for distributed rate limiting across API gateway instances
export async function applyPattern(ctx: RequestContext) {
  const start = performance.now();
  try {
    return await execute(ctx);
  } finally {
    reportMetric("system-design-rate-limiter", performance.now() - start);
  }
}
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.

## Prevention for the next launch

Production engineering for distributed rate limiting across API gateway instances. Review 5: teams that treat distributed rate limiting across API gateway instances as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Monitoring checklist

Leading indicators catch regressions before tweets do: error rate, queue depth, validation failures, p75 latency sliced by route and device class. Lagging indicators — support tickets, churn, audit findings — confirm whether leading metrics matched user pain.

For distributed rate limiting across API gateway instances, log correlation IDs across client beacons and server logs. Compare canary vs control during rollout. Roll forward only when p75 field metrics hold for at least one full business day in the target geography.

## Lessons for the team

Fifty thousand requests per minute from one API key starved the database until Redis token bucket returned 429 and everyone else recovered.. If I were prioritizing one action this sprint: pick the single user journey where distributed rate limiting across API gateway instances hurts most, instrument it, fix the invariant, and only then generalize.

Performance and reliability work compounds when tied to business metrics — conversion, support volume, integration churn — not abstract Lighthouse scores alone.

## Related reading and specs

Consult MDN and web.dev for API semantics — tutorials often skip edge cases that matter in production. Link runbooks from dashboards, not wikis buried three clicks deep.

## Coordination with backend and platform

Distributed Rate Limiting Across Api Gateway Instances rarely lives entirely in the browser or client. Align cache TTLs, API error shapes, and deploy windows with the teams owning those systems — otherwise you optimize one layer while another invalidates gains.

## Operating distributed rate limiting across API gateway instances after traffic shifts (review 1)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When distributed rate limiting across API gateway instances touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating distributed rate limiting across API gateway instances after traffic shifts (review 2)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When distributed rate limiting across API gateway instances touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating distributed rate limiting across API gateway instances after traffic shifts (review 3)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When distributed rate limiting across API gateway instances touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating distributed rate limiting across API gateway instances after traffic shifts (review 4)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When distributed rate limiting across API gateway instances touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Extended guidance (1)

**Context:** Distributed rate limiting across api gateway instances affects users when when protecting apis from abuse and ensuring fair usage across tenants. Avoid the failure mode where teams local in-memory counters without shared state — limits fail across instances.

Ship the smallest vertical slice with one leading metric — latency, recall, conversion, or accessibility findings. Baseline field p75 on mid-tier mobile hardware before merge; compare after a full business day in target regions. Wire rollback via feature flag or cache purge documented in the PR.

Edge cases include corporate proxies, Save-Data clients, ad blockers, and battery savers. Exercise keyboard-only paths, refresh mid-flow, and back navigation when the surface touches auth or checkout. Security review covers CSP, PII in URLs, and third-party scripts even for UI-only changes.

Coordinate with platform and backend so cache TTLs and error response shapes do not erase frontend wins. Schedule quarterly re-baseline after browser releases and traffic mix shifts.

Document trade-offs in the pull request: if you chose speed over strict correctness, or strictness over iteration velocity, the next engineer needs that context during incident response. Link dashboards from the runbook header so on-call does not hunt wikis during outages.