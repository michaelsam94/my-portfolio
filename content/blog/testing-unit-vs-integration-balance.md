---
title: "Balancing Unit and Integration Tests"
slug: "testing-unit-vs-integration-balance"
description: "Finding the right unit vs integration test balance: testing pyramid critique, social tests, test boundaries, ROI by layer, and team-specific ratios."
datePublished: "2026-01-22"
dateModified: "2026-01-22"
tags: ["Testing", "Software Engineering", "Architecture", "Quality"]
keywords: "unit vs integration tests, testing pyramid, testing trophy, test balance, integration test ROI, microservice testing strategy"
faq:
  - q: "What is the testing pyramid?"
    a: "The testing pyramid recommends many fast unit tests at the base, fewer integration tests in the middle, and minimal slow end-to-end tests at the top. The shape reflects cost and speed — unit tests run in milliseconds and pinpoint failures; E2E tests run minutes and diagnose poorly. The pyramid is guidance, not a quota mandate."
  - q: "What is wrong with aiming for 100% unit test coverage?"
    a: "Unit tests with every dependency mocked verify isolated logic but miss wiring bugs, SQL mistakes, schema drift, and serialization mismatches. Over-mocking produces tests that pass when production fails. Some integration coverage at repository and API boundaries catches failures unit tests structurally cannot see."
  - q: "How do you decide what to integration test?"
    a: "Integration test at boundaries where types cross process or I/O: HTTP handlers against real DB (Testcontainers), repository layer against real SQL, message consumers against embedded broker. Skip integrating what unit tests already prove — pure domain calculations, formatters, validators without I/O. One happy-path plus key error integration test per boundary often suffices."
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

## Common production mistakes

Teams get unit vs integration balance wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Testing strategy for unit vs integration balance gives false confidence when mocks return happy paths only, flakey tests are retried until green, and contract tests are never run against staging before deploy.

## Debugging and triage workflow

When unit vs integration balance misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Test Pyramid (Martin Fowler)](https://martinfowler.com/bliki/TestPyramid.html)
- [Testing Trophy (Kent C. Dodds)](https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications)
- [Google Testing Blog — sizes](https://testing.googleblog.com/2010/12/test-sizes.html)
- [Testcontainers](https://testcontainers.com/)
- [Spring Boot @WebMvcTest](https://docs.spring.io/spring-boot/docs/current/reference/htmlsingle/#webmvc-test)
