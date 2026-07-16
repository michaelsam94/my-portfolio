---
title: "Mocks, Stubs, and Fakes"
slug: "testing-test-doubles-mocks-stubs"
description: "Test doubles explained: mocks vs stubs vs fakes vs spies, when to use each, mock overuse pitfalls, and testing without mocking the universe."
datePublished: "2026-01-18"
dateModified: "2026-01-18"
tags: ["Testing", "Software Engineering", "Quality", "Architecture"]
keywords: "mocks stubs fakes, test doubles, Mockito, mock overuse, dependency injection testing, spy vs mock"
faq:
  - q: "What is the difference between a mock and a stub?"
    a: "A stub provides canned answers to calls during a test — it returns predefined data and has no assertion about how it was used. A mock is a test double that records interactions and verifies expected calls (method X called once with argument Y). Stubs enable state verification on the system under test; mocks enable behavior verification on collaborators."
  - q: "What is a fake?"
    a: "A fake is a working implementation with shortcuts — an in-memory repository instead of Postgres, FakeMailer that stores sent emails in a list. Fakes test against real behavior of the collaborator type without I/O cost. They are more maintainable than mocks when the collaborator interface is stable and used across many tests."
  - q: "When does mocking become harmful?"
    a: "Mocking hurts when tests verify implementation details (internal method call order) instead of outcomes, when mocks duplicate production interfaces so faithfully they become second implementations, or when integration bugs hide because every dependency is mocked. Prefer fakes or real dependencies (Testcontainers) at system boundaries; mock only what is slow, non-deterministic, or external."
---

The test verified that `emailService.send()` was called once. Production failed because the email body was wrong — nobody asserted content, only that the method fired. The mock passed; the user never received a password reset. Test doubles are tools; the failure mode is testing that your code talked to a fake instead of testing that your code works.

Gerard Meszaros cataloged test doubles — stubs, mocks, fakes, spies, dummies — and the vocabulary still matters because teams say "mock" when they mean "stub" and write brittle tests coupled to call counts.

## Taxonomy

| Double | Purpose |
| --- | --- |
| **Dummy** | Fills parameter slot; never used |
| **Stub** | Returns canned responses |
| **Spy** | Records calls; real or partial implementation |
| **Mock** | Pre-programmed expectations; fails on unexpected calls |
| **Fake** | Simplified working implementation |

## Stub example

```java
PaymentGateway stub = id -> PaymentResult.success("txn-123");
OrderService service = new OrderService(stub, repo);
service.checkout(order);
assertThat(order.getStatus()).isEqualTo(PAID);
```

Stub enables test; assertion is on **system under test state**.

## Mock example (Mockito)

```java
@Mock PaymentGateway gateway;
@InjectMocks OrderService service;

@Test
void chargesOnCheckout() {
  when(gateway.charge(any())).thenReturn(success("txn-1"));
  service.checkout(order);
  verify(gateway, times(1)).charge(argThat(c -> c.amount() == 999));
}
```

Mock verifies **interaction** with collaborator. Useful when side effect is the outcome (send email, charge card) and return value alone is insufficient — but assert meaningful arguments, not just `times(1)`.

## Fake example

```java
class FakeOrderRepo implements OrderRepository {
  private final Map<OrderId, Order> store = new HashMap<>();
  public void save(Order o) { store.put(o.id(), o); }
  public Optional<Order> find(OrderId id) { return Optional.ofNullable(store.get(id)); }
}

@Test
void persistsOrder() {
  FakeOrderRepo repo = new FakeOrderRepo();
  OrderService service = new OrderService(realGateway, repo);
  service.checkout(order);
  assertThat(repo.find(order.id())).isPresent();
}
```

Fake survives interface additions better than 50 mock setups — one fake class, many tests.

## When to use what

```
External API (Stripe)     → Mock at unit boundary OR contract test + fake
Database                  → Fake repo unit tests; Testcontainers integration
Clock / random            → Stub/fixed Clock
Logger                    → Dummy or spy in rare cases
Complex collaborator      → Fake if reused; stub for one-off return
```

## Mock overuse smells

- Test breaks when refactoring **private** method extraction — coupled to call path
- More mock setup lines than code under test
- `verify` on every method — testing implementation, not behavior
- Mocks return mocks (deep stub chains)

**London vs Chicago school:** London mocks collaborators at unit boundaries; Chicago uses real objects where practical and tests state. Modern consensus: Chicago-ish with selective mocks/fakes.

## Spies — use sparingly

```javascript
const spy = vi.spyOn(console, "error").mockImplementation(() => {});
// ... trigger error path
expect(spy).toHaveBeenCalledWith(expect.stringContaining("payment failed"));
spy.mockRestore();
```

Spies on real objects for cross-cutting concerns. Prefer injecting a `Logger` interface.

## DI makes doubles swappable

Constructor injection:

```kotlin
class NotifyUser(private val mailer: Mailer, private val repo: UserRepo)
```

Tests pass `FakeMailer`; production passes `SmtpMailer`. No framework magic required.

## Partial integration beats total mock

```java
@MockBean ExternalCreditBureauClient  // slow, external
@Autowired OrderService              // real
@Autowired FakeOrderRepo configured  // @TestConfiguration
```

Spring test slice tests real wiring with one mocked boundary — catches bean misconfiguration unit tests miss.




## Contract tests vs mocks at service boundaries

At HTTP boundaries, prefer contract tests or recorded interactions (VCR) over hand-written mocks that drift from OpenAPI. Mocks excel inside a service unit test; fakes and contract tests excel at the edge where schema changes propagate silently. Align with Pact or schema validation so doubles update when API evolves.

## When to use each double

| Double | Use when |
|--------|----------|
| Stub | Return fixed data, no behavior verification |
| Mock | Verify interaction (called once with X) |
| Fake | In-memory DB, real logic, test-only |
| Spy | Real object + call recording |

Prefer fakes over mocks for repository tests — mock-heavy tests break on refactor without behavior change.

## Common production mistakes

Teams get test doubles mocks stubs wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Testing strategy for test doubles mocks stubs gives false confidence when mocks return happy paths only, flakey tests are retried until green, and contract tests are never run against staging before deploy.

## Debugging and triage workflow

When test doubles mocks stubs misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Metrics worth dashboarding

For test doubles mocks stubs, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Resources

- [Mocks Aren't Stubs (Martin Fowler)](https://martinfowler.com/articles/mocksArentStubs.html)
- [Test Double (xUnit patterns)](https://martinfowler.com/bliki/TestDouble.html)
- [Mockito documentation](https://javadoc.io/doc/org.mockito/mockito-core/latest/org/mockito/Mockito.html)
- [Testcontainers](https://testcontainers.com/)
- [Growing Object-Oriented Software, Guided by Tests](https://www.amazon.com/Growing-Object-Oriented-Software-Guided-Tests/dp/0321503627)
