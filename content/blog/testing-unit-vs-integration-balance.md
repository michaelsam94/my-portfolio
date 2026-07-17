---
title: "Balancing Unit and Integration Tests"
slug: "testing-unit-vs-integration-balance"
description: "Finding the right unit vs integration test balance: testing pyramid critique, social tests, test boundaries, ROI by layer, and team-specific ratios."
datePublished: "2026-01-22"
dateModified: "2026-07-17"
tags:
  - "Testing"
  - "Software Engineering"
  - "Architecture"
  - "Quality"
keywords: "unit vs integration tests, testing pyramid, testing trophy, test balance, integration test ROI, microservice testing strategy"
faq:
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
---

A team proud of 95% unit coverage shipped a release where every API returned 500. The ORM entity had a renamed column; unit tests mocked the repository. Integration tests existed but only for checkout — catalog, search, and auth untested against real Postgres. The pyramid was wide at the bottom and hollow in the middle.

"Unit vs integration" is the wrong debate framed as rivalry. The right question: **at which boundary does the next dollar of test investment catch the most likely bugs?**

## Pyramid, trophy, honeycomb — pick a metaphor, keep the physics

**Pyramid (classic):** many unit, some integration, few E2E.

**Testing trophy (Kent C. Dodds):** emphasize integration for UI; static analysis base.

**Honeycomb (Spotify etc.):** integration at service boundaries, thin E2E, unit for algorithms.

Metaphors disagree on frontend vs backend emphasis. Shared truth:

- Fast tests run on every commit
- Slow tests run less often but exist
- No layer alone proves the system works

## What unit tests excel at

- Pure functions, pricing rules, state machines
- Edge cases combinatorially (property tests)
- Regression on algorithm bugs
- TDD feedback loop speed

```kotlin
@Test
fun `discount does not stack above cap`() {
  val total = calculator.applyDiscounts(base = 100.eur, codes = listOf("50OFF", "40OFF"))
  assertEquals(10.eur, total) // 90% max combined
}
```

No database needed.

## What integration tests excel at

- SQL queries (wrong join, missing index behavior)
- Transaction boundaries and rollback
- HTTP serialization (JSON naming, date formats)
- Auth middleware + handler wiring
- Migration compatibility

```java
@DataJpaTest
class OrderRepositoryTest {
  @Test
  void findsByCustomerAndStatus() {
    // H2 or Testcontainers Postgres
    repo.save(shippedOrderFor(customerId));
    assertThat(repo.findActive(customerId)).hasSize(1);
  }
}
```

One test catches `@Column(name = "cust_id")` typo that mocked repo hides.

## What E2E tests excel at

- Critical user journeys cross multiple services
- Deploy smoke — "did we wire the environment?"
- Regression on CSS/flow breaks

Cap count. Make them stable.

## Practical allocation — backend service

Starting point for a typical REST microservice:

| Layer | % of tests (rough) | Examples |
| --- | --- | --- |
| Unit | 60–70% | domain, validators, mappers |
| Integration | 25–35% | repo, API @WebMvcTest + Testcontainers |
| E2E | 5–10% | smoke in staging |

Adjust up integration for data-heavy services; up unit for calculation engines.

## Practical allocation — frontend SPA

| Layer | Emphasis |
| --- | --- |
| Unit | hooks, reducers, utils |
| Integration (RTL) | component + mocked API |
| E2E (Playwright) | checkout, login |

Component integration tests give trophy-shaped ROI for UI.

## Anti-patterns on both sides

**Ice cream cone** — many E2E, no unit — slow CI, flaky, vague failures.

**Unit-only fortress** — mocked everything — green CI, red prod.

**Integration swamp** — full stack test per endpoint — 45-minute builds, duplicated coverage.

## Test boundaries map

Draw boxes:

```
[Browser E2E] → [API HTTP] → [Service] → [Repo] → [DB]
                  ↑              ↑           ↑
               contract      unit domain   integration
               + few IT      heavy unit    heavy IT
```

Each arrow is a potential integration test; not every arrow needs ten.

## Measuring balance

Track:

- CI duration per layer
- Production bugs by "would unit/integration/E2E have caught?"
- Flake rate by layer

Retro quarterly. Shift investment toward layer that would have prevented last quarter's incidents.

## Team size matters

Solo dev: lean pyramid, pragmatic E2E smoke. Platform team: contract tests + consumer-driven pacts. Monolith team: integration tests cheaper relative to microservices — use them.

## What belongs in each layer

| Layer | Test | Example | Speed |
|-------|------|---------|-------|
| Unit | Pure logic, no I/O | Price calculation, validators | < 1ms |
| Integration | Real DB/API, one boundary | Repository with Testcontainers Postgres | 1–5s |
| Contract | Consumer/provider agreement | Pact HTTP interaction | 100ms |
| E2E | Full user journey | Playwright checkout flow | 30–120s |

Unit tests for mappers and validators. Integration tests for SQL you can't trust to mock. E2E for three critical revenue paths, not every form field.

## Flake management by layer

Flakes compound — one flaky E2E blocks 20 developers:

```yaml
# pytest markers
@pytest.mark.integration  # runs in parallel job
@pytest.mark.e2e          # serial, 2 retries max
```

Quarantine flaky tests within 24 hours — fix or delete, never `@pytest.mark.skip` indefinitely. Track flake rate per test in CI dashboard.

## Evolving the balance over time

Revisit the pyramid quarterly using incident retros. If last quarter's outages were SQL bugs, invest in repository integration tests. If UI regressions dominated, add Playwright smoke — not necessarily more unit tests. The ratio is a hypothesis you adjust with evidence, not a religion.

Pair with [testing mutation testing](https://blog.michaelsam94.com/testing-mutation-testing/) to find unit tests that pass but never assert meaningful behavior.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## The integration test honeycomb

Unit tests prove logic; integration tests prove wiring. The costly mistake is mocking everything in "integration" tests until they prove nothing. Test containers (Testcontainers, Docker Compose in CI) give real Postgres and Redis without shared staging environments. One integration test per critical path — checkout, signup, password reset — catches config errors unit tests miss. Keep integration suite under ten minutes or teams skip it.

## Contract tests at service boundaries

Pact or schema-based contract tests sit between unit and integration: fast, no shared environment, catch API shape drift. One breaking change in notifications service should fail consumer CI before deploy — integration tests that mock the downstream prove wiring, not contract agreement.

## Flaky test budget

Track flaky test rate weekly. Above 2% of CI runs, freeze feature work for one day and fix or quarantine flakes. Quarantined tests must have owner and expiry — quarantine is not permanent exile. Teams that tolerate flakes stop trusting red builds and ship regressions.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [Test Pyramid (Martin Fowler)](https://martinfowler.com/bliki/TestPyramid.html)
- [Testing Trophy (Kent C. Dodds)](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Google Testing Blog — sizes](https://testing.googleblog.com/2010/12/test-sizes.html)
- [Testcontainers](https://testcontainers.com/)
- [Spring Boot @WebMvcTest](https://docs.spring.io/spring-boot/docs/current/reference/htmlsingle/#webmvc-test)

## Consumer-driven contracts

Pact on API boundary — integration without full E2E stack running.

## Slice tests

Spring `@WebMvcTest`, Nest testing module with real controller + mocked service — middle layer between unit and full integration.

## Frontend MSW integration

MSW in Vitest with real React Query stack — integration of data layer without backend.

## Defect taxonomy retro

Tag last quarter prod bugs: "mock wouldn't catch" vs "unit would catch" — data drives investment.

## Test debt budget

Allow +5 integration tests per sprint without deleting unit tests — gradual rebalance.

## Flaky integration fixes

Quarantine flaky integration with ticket — zero tolerance long-term; delete if not fixed in 30 days.

Balance is empirical — pyramid poster is starting point, production escape data is truth.

## Contract tests at boundaries

Pact or similar at service edges replaces some integration tests — faster CI with same breaking-change detection.
