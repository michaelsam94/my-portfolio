---
title: "Blue-Green vs Canary Deployments"
slug: "ops-blue-green-vs-canary"
description: "Choose between blue-green and canary deployments: traffic switching, rollback speed, infrastructure cost, and how to implement each with Kubernetes and load balancers."
datePublished: "2025-12-30"
dateModified: "2026-07-17"
tags: ["DevOps", "Deployment", "Kubernetes", "SRE"]
keywords: "blue-green deployment, canary deployment, progressive delivery, zero downtime deploy, Kubernetes rollout"
faq:
  - q: "What is the main difference between blue-green and canary deployments?"
    a: "Blue-green runs two full environments and switches 100% of traffic at once. Canary routes a small percentage of traffic to the new version first, validates metrics, then gradually increases. Blue-green gives instant rollback; canary limits blast radius but takes longer to fully roll out."
  - q: "When is blue-green deployment worth the double infrastructure cost?"
    a: "When rollback must be instant (financial trading, payment processing), when your app can't serve mixed versions safely (schema migrations without backward compatibility), or when traffic is low enough that running two full stacks is cheap."
  - q: "How small should the first canary slice be?"
    a: "Start with 1–5% of traffic or a fixed internal/user-beta cohort. Measure error rate, latency, and business metrics for at least one full request cycle (often 15–30 minutes) before increasing. Jumping straight to 50% defeats the purpose."
---

A bad deployment used to mean a bad hour. We picked blue-green for our payment API because rollback had to be a load balancer flip, not a gradual retreat. For the marketing site, we picked canary because nobody wanted to pay for two full CDN origins to A/B test a hero image change. Both patterns solve "ship without downtime." They optimize for different failure budgets.

## Blue-green: two stacks, one switch

Blue (current) and green (new) are complete parallel environments — separate deployments, sometimes separate databases or read replicas. Traffic sits on blue until you validate green, then you switch 100%.

```
                    ┌─────────┐
  Users ──────────► │   LB    │
                    └────┬────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        ┌──────────┐         ┌──────────┐
        │ Blue v1  │         │ Green v2 │  (idle or soak traffic)
        │ (active) │         │ (standby)│
        └──────────┘         └──────────┘
```

Kubernetes implementation without a service mesh: two Deployments, one Service, swap selector labels:

```yaml
# Active service points to version label
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
    slot: blue   # flip to green after validation
```

Or use two Services (`api-blue`, `api-green`) and update the Ingress/backend target. AWS ALB weighted target groups achieve the same at the load balancer layer.

**Rollback:** flip the selector back. Sub-minute if health checks pass on the old stack. Keep blue running for at least one release cycle — deleting it immediately is how teams discover green had a slow memory leak.

**Cost:** 2× compute during overlap. For GPU or large JVM heaps, that hurts. Schedule green at reduced replicas during soak, scale to match blue before the switch.

## Canary: progressive traffic shift

Canary keeps one baseline deployment and adds a canary replica set. The load balancer or mesh routes increasing traffic to the new version:

| Stage | Canary weight | Duration | Gate |
|-------|---------------|----------|------|
| 1 | 5% | 15 min | Error rate < baseline + 0.1% |
| 2 | 25% | 30 min | p99 latency < baseline × 1.1 |
| 3 | 50% | 30 min | Business KPI stable |
| 4 | 100% | — | Promote canary to primary |

With Istio:

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api
spec:
  hosts: [api.internal]
  http:
    - route:
        - destination:
            host: api
            subset: stable
          weight: 95
        - destination:
            host: api
            subset: canary
          weight: 5
```

Argo Rollouts and Flagger automate weight changes and metric analysis — manual VirtualService edits don't survive on-call at 3 AM.

## Decision matrix

| Factor | Blue-green | Canary |
|--------|------------|--------|
| Rollback speed | Seconds (traffic flip) | Minutes (weight reduction) |
| Infrastructure cost | High (dual stack) | Low (fractional extra pods) |
| Mixed-version tolerance | Poor unless designed | Required |
| DB migration coupling | Often needs separate strategy | Same |
| Confidence before full cutover | Binary (soak then switch) | Gradual metric gates |

**Pick blue-green** when versions can't coexist (breaking API contract without versioning), when you need instant rollback for compliance, or when traffic is small.

**Pick canary** when you want metric-gated promotion, when infra cost matters, or when you already run a service mesh / ingress controller with weight support.

## Database migrations break both patterns

Neither blue-green nor canary fixes schema changes. The expand-contract pattern is mandatory:

1. **Expand:** deploy migration that adds new column/table (backward compatible)
2. **Deploy app** that writes to both old and new
3. **Contract:** remove old column after backfill

Blue-green with a shared database requires both app versions to work against the same schema during the switch window. Plan migrations *before* picking a deployment strategy.

## Common mistakes

**Health checks that lie.** `/health` returns 200 while the app can't reach Postgres. Canary traffic hits real errors. Add dependency checks or synthetic canaries.

**Sticky sessions.** Users bounce between versions mid-session if load balancer affinity isn't aligned with canary weights. Enable session affinity or accept mixed-version sessions.

**Monitoring the wrong signals.** CPU on canary pods looks fine while checkout conversion drops 2%. Wire business metrics into promotion gates.

**Forgetting background workers.** You canaried the API but deployed the new worker at 100%. Queue consumers process incompatible message formats. Deploy workers with the same progressive strategy or version your message schema.

## Decision matrix

| Factor | Blue-green | Canary |
|--------|------------|--------|
| Rollback speed | Seconds (switch) | Minutes (ramp down) |
| Infra cost | 2× during deploy | ~1× |
| Risk detection | All-at-once | Gradual |
| DB migrations | Hard — need expand-contract | Easier with feature flags |

Use blue-green for schema-compatible releases; canary for behavior changes needing metric comparison.

## Common production mistakes

Teams get blue green vs canary wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of blue green vs canary fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When blue green vs canary misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Database coupling breaks pure blue-green

Blue-green assumes instant traffic switch. Schema migrations coupling both colors need **expand/contract** migrations — green must read/write compatible schema with blue until cutover completes. Document which deploy strategy each service uses in its README; platform teams defaulting blue-green on stateful services cause split-brain writes.

## Canary analysis metrics

Flagger (or Argo Rollouts) needs metric templates beyond HTTP 5xx:

| Metric | Why |
|--------|-----|
| p99 latency | Slow burn regressions |
| Business KPI (checkout success) | User-visible |
| Error budget burn | SLO-linked rollback |

Define minimum canary duration — 2 minutes catches crashloops, not memory leaks. 30–60 minutes for consumer-facing APIs.

## Smoke tests in the cutover path

Blue-green switch should run automated smoke against green internal URL before LB flip — `POST /checkout/test` with synthetic card in staging mirror. Canary uses same smoke as analysis metric input.

## Session affinity complications

Sticky sessions on blue while green receives 10% canary — users hit both versions; ensure schema backward compatibility for session serialization across versions.

## DNS TTL and blue-green

DNS flip for blue-green needs low TTL pre-cutover — 300s TTL means 5 min straggler traffic to old color. Prefer LB weighted switch over DNS when possible.

## Feature flags vs traffic split

Canary splits traffic; feature flags split code paths — combining both without matrix causes "10% traffic sees 50% enabled flag" confusion. Document interaction in deploy runbook.
## Database blue-green with read replicas

Blue writes primary, green validates against replica lag <1s before cutover — cutover with 10s lag duplicates writes to wrong color briefly.

## Resources

- [Argo Rollouts canary strategy](https://argoproj.github.io/argo-rollouts/features/canary/)
- [Kubernetes Deployment rolling update docs](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)
- [Istio traffic management](https://istio.io/latest/docs/concepts/traffic-routing/)
- [Martin Fowler on blue-green deployment](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Expand-contract migration pattern](https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern)
