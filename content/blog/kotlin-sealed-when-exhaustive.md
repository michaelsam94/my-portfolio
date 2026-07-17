---
title: "Exhaustive when with Sealed Classes"
slug: "kotlin-sealed-when-exhaustive"
description: "Exhaustive when with Sealed Classes: production patterns for kotlin teams — design, implementation, testing, security, and operations."
datePublished: "2024-07-23"
dateModified: "2024-07-23"
tags: ["Kotlin", "Sealed"]
keywords: "kotlin, sealed, when, exhaustive, production, engineering, architecture"
faq:
  - q: "What is Exhaustive when with Sealed Classes?"
    a: "Exhaustive when with Sealed Classes covers the engineering practices, APIs, and tradeoffs teams use when implementing this capability in a production Kotlin codebase. It is not a single library call — it is how the module behaves under real users, releases, and failure modes."
  - q: "When should teams prioritize Exhaustive when with Sealed Classes?"
    a: "Prioritize it when build time, test flakiness, and runtime crashes show regression, when the feature is on your critical user journey, or when you are about to scale traffic/devices/tenants and the current approach will not survive the load. Defer only if metrics are flat and the code path is genuinely unused."
  - q: "What are common mistakes with Exhaustive when with Sealed Classes?"
    a: "Copying a tutorial without matching your constraints, skipping measurement until after launch, mixing UI and IO without test seams, and treating edge cases (offline, rotation, permissions) as follow-ups. Another pattern: shipping the demo path without rollback or feature flags."
  - q: "How does Exhaustive when with Sealed Classes fit a modern Kotlin stack?"
    a: "Modern tooling (Kotlin codebase) adds automation, but ownership stays human: you still need explicit contracts, tested migrations, and runbooks. Exhaustive when with Sealed Classes should be observable in production and safe to change in small diffs."
---
Exhaustive when with Sealed Classes is one of those topics that looks straightforward in a slide deck and gets complicated the first time traffic spikes or an auditor asks how you know it works. In kotlin systems, the difference between "we implemented it" and "we can operate it" shows up in metrics, incident history, and how confidently new engineers change the code.
## Problem framing

When exhaustive when with sealed classes is underspecified, every module team invents a partial fix — inconsistent UX, duplicated platform code, or "works on my device" bugs that explode in production. The symptom on dashboards is usually build time, test flakiness, and runtime crashes, but the root cause is missing shared patterns.

The cost is slower releases and fearful refactors. Engineers re-learn the same platform edges (permissions, lifecycle, threading) on every feature. Product loses predictability because nobody can say what will break when you touch related code.

Solid Kotlin engineering turns exhaustive when with sealed classes from a recurring argument into a documented pattern with tests and an owner.

## Design principles that survive production

**Explicit contracts.** Whether the boundary is HTTP, gRPC, SQL, or an internal module API, the contract should be machine-checkable and versioned. Ambiguity is where kotlin sealed when exhaustive bugs hide.

**Observability first.** Logs, metrics, and traces are not "phase two." If you cannot answer "what happened?" for exhaustive when with sealed classes, you do not yet understand the behavior you shipped.

**Fail closed, degrade gracefully.** Authentication, authorization, validation, and quota checks should deny by default. Partial availability beats corrupt state — users forgive slowness more than wrong answers.

**Idempotency and replay safety.** Networks retry. Users double-click. Jobs re-run. Design kotlin sealed when exhaustive flows so duplicates are harmless or detectable.

## Implementation patterns

A practical baseline for exhaustive when with sealed classes in kotlin stacks:

1. **Model the happy path minimally** — ship the smallest flow that satisfies the user story with correct semantics.
2. **Add failure paths next** — timeouts, retries with jitter, circuit breaking, and compensating actions.
3. **Instrument before optimizing** — measure p50/p95 latency, error budgets, and saturation; tune from evidence.
4. **Document operational playbooks** — what to check, what to rollback, who owns downstream dependencies.

For code structure, keep side effects at the edges and core logic pure where possible. Pure functions are trivial to test; IO at the boundary is trivial to mock. That split makes kotlin sealed when exhaustive changes safer because business rules stay isolated from transport details.

```kotlin
// Isolate kotlin sealed when exhaustive logic for testability
interface ExhaustivewhenwithSealedClassesGateway {
  suspend fun execute(input: Request): Result<Response>
}

class DefaultExhaustivewhenwithSealedClassesGateway(
  private val client: HttpClient,
  private val metrics: Metrics,
) : ExhaustivewhenwithSealedClassesGateway {
  override suspend fun execute(input: Request): Result<Response> = runCatching {
    metrics.count(" kotlin-sealed-when-exhaustive.attempt")
    client.post("/v1/when-exhaustive") {
      setBody(input)
      timeout { request = 2_000 }
    }.body()
  }.onFailure { metrics.count("kotlin-sealed-when-exhaustive.error") }
}
```


## Operational concerns

Runbooks for exhaustive when with sealed classes should fit on one page: symptoms, dashboards, mitigation, rollback. If mitigation requires a senior engineer's tribal knowledge, the system is not operable yet.

Production kotlin sealed when exhaustive work is mostly operability: dashboards, alerts, runbooks, and ownership. Define SLOs that reflect user experience — availability, latency, correctness — not vanity metrics. Alerts should page on symptoms (SLO burn) and ticket on causes (error logs), avoiding noise that trains teams to ignore pages.

Rollouts for exhaustive when with sealed classes benefit from progressive delivery: canary by percentage or by tenant cohort, with automatic rollback when error rate or latency regresses beyond thresholds. Pair deploys with feature flags so you can disable logic paths without redeploying.

Capacity planning ties directly to cost and reliability. Measure peak QPS, payload sizes, fan-out factor, and dependency limits. Load test with production-shaped traffic; synthetic "hello world" tests miss queue backlogs and downstream contention.

## Security and compliance angles

Even when exhaustive when with sealed classes is not "security software," it participates in your trust boundary. Apply least privilege to service accounts, rotate credentials, and validate all inputs at the trust perimeter. For regulated workloads, maintain an audit trail that answers who changed what, when, and from where.

Secrets belong in managed stores — not environment variables checked into templates. For PII-adjacent flows, minimize retention and prefer tokenization over copying raw fields. Document data flows for kotlin sealed when exhaustive so security reviews do not rely on tribal knowledge.

## Testing strategy

Unit tests cover pure logic: validation, mapping, state transitions, and edge cases. Contract tests protect API boundaries that exhaustive when with sealed classes depends on. Integration tests with real containers — databases, brokers, sandboxes — catch configuration mistakes mocks hide.

For critical kotlin paths, add property-based or fuzz testing where generative input explores weird combinations. Replay production traffic (sanitized) into staging before large refactors. Chaos experiments — dependency latency, partial outages — validate that retries and fallbacks actually work.

## Migration and evolution

Legacy systems rarely block greenfield designs; they constrain sequencing. Strangle kotlin sealed when exhaustive functionality behind a stable interface, migrate callers incrementally, and delete old paths once traffic drops to zero. Maintain a migration tracker with explicit decommission dates so "temporary" bridges do not ossify.

Versioning policy should be boring: additive changes only in minor versions, breaking changes only with deprecation windows and communication. Where exhaustive when with sealed classes spans mobile, web, and backend, coordinate release trains so clients never lead servers into incompatible states.

## Related concepts

Exhaustive when with Sealed Classes intersects with broader kotlin topics — see companion notes on [kotlin-sealed patterns](https://blog.michaelsam94.com/kotlin-sealed/) and [production observability](https://blog.michaelsam94.com/designing-for-observability-slos/) when wiring metrics and alerts. Treat those links as adjacent reading, not prerequisites: the goal here is a self-contained operational understanding you can apply without chasing every rabbit hole.

## The takeaway

Exhaustive when with Sealed Classes rewards disciplined boring engineering: clear contracts, measurable SLOs, secure defaults, and rollout paths that fail safely. The teams that struggle usually lack visibility or ownership, not intelligence. Start with the user-visible outcome, instrument it, iterate with small diffs, and document the failure modes you actually hit — that is how kotlin sealed when exhaustive becomes a maintainable asset instead of incident fuel.

## Resources

- [kotlinlang.org/docs/home.html](https://kotlinlang.org/docs/home.html)

- [developer.android.com/kotlin](https://developer.android.com/kotlin)

- [kotlinlang.org/docs/multiplatform.html](https://kotlinlang.org/docs/multiplatform.html)

- [github.com/JetBrains/compose-multiplatform](https://github.com/JetBrains/compose-multiplatform)
