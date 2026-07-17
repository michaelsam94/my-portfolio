---
title: "Service Worker Stale-While-Revalidate"
slug: "web-performance-service-worker-stale-while-revalidate"
description: "Cache-first with background update for assets and API GET responses — fast paint with eventual freshness."
datePublished: "2026-06-15"
dateModified: "2026-07-17"
tags:
  - "Performance"
  - "PWA"
  - "Caching"
keywords: "stale while revalidate service worker, workbox SWR, cache strategies, offline first"
faq:
  - q: "When is stale-while-revalidate appropriate?"
    a: "Static assets and API responses with explicit max-age. Never SWR price, inventory, or auth-sensitive data without short TTL and background revalidation alerts."
  - q: "How to update SW cache on deploy?"
    a: "Version cache names; skipWaiting plus clients.claim with user-visible 'Update available' prompt — not silent overwrite mid-session."
  - q: "SWR vs network-first?"
    a: "Network-first for HTML documents that change frequently; SWR for hashed static assets. Match strategy to content volatility."
faqAnswers:
  - question: "When is web performance service worker stale while revalidate the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for web performance service worker stale while revalidate?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back web performance service worker stale while revalidate safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Stale-while-revalidate served a week-old pricing page from cache while sales ran a promotion — users saw wrong prices until hard refresh.

## The question behind the ticket

Production engineering for service worker stale-while-revalidate with freshness bounds. Review 1: teams that treat service worker stale-while-revalidate with freshness bounds as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Answer with nuance

Production engineering for service worker stale-while-revalidate with freshness bounds. Review 2: teams that treat service worker stale-while-revalidate with freshness bounds as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Implementation walkthrough

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. Unbounded SWR without max-age, version headers, or skipWaiting coordination That mistake is expensive because it only surfaces under real traffic mixes.

            ```typescript
            const worker = new Worker(new URL("./compute.worker.ts", import.meta.url), { type: "module" });
const buffer = new ArrayBuffer(1024 * 1024);
worker.postMessage({ type: "process", buffer }, [buffer]);
worker.onmessage = (e) => updateUI(e.data);
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.

## Security angle

Frontend and backend changes share an attack surface. Treat user content, URL parameters, and webhook bodies as hostile input. Prefer fail-closed verification, short-lived credentials, and constant-time comparisons for crypto.

Content Security Policy, Subresource Integrity, and Trusted Types stack for DOM XSS defense. Security work without tests regresses — add CI checks that fail on unsafe patterns.

## Testing beyond happy path

Production engineering for service worker stale-while-revalidate with freshness bounds. Review 5: teams that treat service worker stale-while-revalidate with freshness bounds as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Day-two operations

Production engineering for service worker stale-while-revalidate with freshness bounds. Review 6: teams that treat service worker stale-while-revalidate with freshness bounds as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## What I'd ship this week

Stale-while-revalidate served a week-old pricing page from cache while sales ran a promotion. If I were prioritizing one action this sprint: pick the single user journey where service worker stale-while-revalidate with freshness bounds hurts most, instrument it, fix the invariant, and only then generalize.

Performance and reliability work compounds when tied to business metrics — conversion, support volume, integration churn — not abstract Lighthouse scores alone.

## Related reading and specs

Consult MDN and web.dev for API semantics — tutorials often skip edge cases that matter in production. Link runbooks from dashboards, not wikis buried three clicks deep.

## Coordination with backend and platform

Service Worker Stale-While-Revalidate With Freshness Bounds rarely lives entirely in the browser or client. Align cache TTLs, API error shapes, and deploy windows with the teams owning those systems — otherwise you optimize one layer while another invalidates gains.

## Operating service worker stale-while-revalidate with freshness bounds after traffic shifts (review 1)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When service worker stale-while-revalidate with freshness bounds touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating service worker stale-while-revalidate with freshness bounds after traffic shifts (review 2)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When service worker stale-while-revalidate with freshness bounds touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating service worker stale-while-revalidate with freshness bounds after traffic shifts (review 3)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When service worker stale-while-revalidate with freshness bounds touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating service worker stale-while-revalidate with freshness bounds after traffic shifts (review 4)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When service worker stale-while-revalidate with freshness bounds touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating service worker stale-while-revalidate with freshness bounds after traffic shifts (review 5)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When service worker stale-while-revalidate with freshness bounds touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Extended guidance (1)

**Context:** Service worker stale-while-revalidate with freshness bounds affects users when when offline-capable caching must balance speed with content freshness. Avoid the failure mode where teams unbounded swr without max-age, version headers, or skipwaiting coordination.

Ship the smallest vertical slice with one leading metric — latency, recall, conversion, or accessibility findings. Baseline field p75 on mid-tier mobile hardware before merge; compare after a full business day in target regions. Wire rollback via feature flag or cache purge documented in the PR.

Edge cases include corporate proxies, Save-Data clients, ad blockers, and battery savers. Exercise keyboard-only paths, refresh mid-flow, and back navigation when the surface touches auth or checkout. Security review covers CSP, PII in URLs, and third-party scripts even for UI-only changes.

Coordinate with platform and backend so cache TTLs and error response shapes do not erase frontend wins. Schedule quarterly re-baseline after browser releases and traffic mix shifts.

Document trade-offs in the pull request: if you chose speed over strict correctness, or strictness over iteration velocity, the next engineer needs that context during incident response. Link dashboards from the runbook header so on-call does not hunt wikis during outages.