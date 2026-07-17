---
title: "Mocks, Stubs, and Fakes"
slug: "testing-test-doubles-mocks-stubs"
description: "Test doubles explained: mocks vs stubs vs fakes vs spies, when to use each, mock overuse pitfalls, and testing without mocking the universe."
datePublished: "2026-01-18"
dateModified: "2026-07-17"
tags:
  - "Testing"
  - "Software Engineering"
  - "Quality"
  - "Architecture"
keywords: "mocks stubs fakes, test doubles, Mockito, mock overuse, dependency injection testing, spy vs mock"
faq:
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
---

Over-mocked tests broke on refactor without behavior change — fakes and real Testcontainers caught the wiring bug.

## Symptoms users report

Production engineering for test doubles: mocks, stubs, spies, and fakes. Review 1: teams that treat test doubles: mocks, stubs, spies, and fakes as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## How to confirm root cause

Production engineering for test doubles: mocks, stubs, spies, and fakes. Review 2: teams that treat test doubles: mocks, stubs, spies, and fakes as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Fix that sticks

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. Mocking every collaborator — tests coupled to call order and internal methods That mistake is expensive because it only surfaces under real traffic mixes.

            ```typescript
            // Operational hook for test doubles: mocks, stubs, spies, and fakes
export async function applyPattern(ctx: RequestContext) {
  const start = performance.now();
  try {
    return await execute(ctx);
  } finally {
    reportMetric("testing-test-doubles-mocks-stubs", performance.now() - start);
  }
}
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.

## Reference patterns

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. Mocking every collaborator — tests coupled to call order and internal methods That mistake is expensive because it only surfaces under real traffic mixes.

            ```typescript
            // Operational hook for test doubles: mocks, stubs, spies, and fakes
export async function applyPattern(ctx: RequestContext) {
  const start = performance.now();
  try {
    return await execute(ctx);
  } finally {
    reportMetric("testing-test-doubles-mocks-stubs", performance.now() - start);
  }
}
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.

## Prevention for the next launch

Production engineering for test doubles: mocks, stubs, spies, and fakes. Review 5: teams that treat test doubles: mocks, stubs, spies, and fakes as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.

## Monitoring checklist

Leading indicators catch regressions before tweets do: error rate, queue depth, validation failures, p75 latency sliced by route and device class. Lagging indicators — support tickets, churn, audit findings — confirm whether leading metrics matched user pain.

For test doubles: mocks, stubs, spies, and fakes, log correlation IDs across client beacons and server logs. Compare canary vs control during rollout. Roll forward only when p75 field metrics hold for at least one full business day in the target geography.

## Lessons for the team

Performance and reliability work compounds when tied to business metrics — conversion, support volume, integration churn — not abstract Lighthouse scores alone.

## Related reading and specs

Consult MDN and web.dev for API semantics — tutorials often skip edge cases that matter in production. Link runbooks from dashboards, not wikis buried three clicks deep.

## Coordination with backend and platform

Test Doubles: Mocks, Stubs, Spies, And Fakes rarely lives entirely in the browser or client. Align cache TTLs, API error shapes, and deploy windows with the teams owning those systems — otherwise you optimize one layer while another invalidates gains.

## Operating test doubles: mocks, stubs, spies, and fakes after traffic shifts (review 1)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When test doubles: mocks, stubs, spies, and fakes touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating test doubles: mocks, stubs, spies, and fakes after traffic shifts (review 2)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When test doubles: mocks, stubs, spies, and fakes touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating test doubles: mocks, stubs, spies, and fakes after traffic shifts (review 3)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When test doubles: mocks, stubs, spies, and fakes touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Operating test doubles: mocks, stubs, spies, and fakes after traffic shifts (review 4)

Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

When test doubles: mocks, stubs, spies, and fakes touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.

## Extended guidance (1)

**Context:** Test doubles: mocks, stubs, spies, and fakes affects users when when isolating units from external systems in tests. Avoid the failure mode where teams mocking every collaborator — tests coupled to call order and internal methods.

Ship the smallest vertical slice with one leading metric — latency, recall, conversion, or accessibility findings. Baseline field p75 on mid-tier mobile hardware before merge; compare after a full business day in target regions. Wire rollback via feature flag or cache purge documented in the PR.

Edge cases include corporate proxies, Save-Data clients, ad blockers, and battery savers. Exercise keyboard-only paths, refresh mid-flow, and back navigation when the surface touches auth or checkout. Security review covers CSP, PII in URLs, and third-party scripts even for UI-only changes.

Coordinate with platform and backend so cache TTLs and error response shapes do not erase frontend wins. Schedule quarterly re-baseline after browser releases and traffic mix shifts.

Document trade-offs in the pull request: if you chose speed over strict correctness, or strictness over iteration velocity, the next engineer needs that context during incident response. Link dashboards from the runbook header so on-call does not hunt wikis during outages.

## Contract tests vs mocks

Pact verifies provider against consumer contract — mock generated from contract, not imagination.

## Clock fake

```typescript
vi.useFakeTimers();
vi.setSystemTime(new Date("2026-07-17"));
```

Deterministic expiry tests without `setTimeout` flakiness.

## Spy on module

```typescript
const logSpy = vi.spyOn(console, "error").mockImplementation(() => {});
```

Spies record without full mock replacement.

## Integration test doubles

Testcontainers Postgres is not a mock — real dependency, controlled environment. Doubles spectrum from stub to production.

## Mockito strict stubs

Unused stubbing fails test — catches over-mocking early.

Name the double by intent — if verifying calls, mock; if providing data, stub; if simulating storage, fake.
