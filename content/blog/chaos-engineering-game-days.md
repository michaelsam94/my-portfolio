---
title: "Running Chaos Engineering Game Days"
slug: "chaos-engineering-game-days"
description: "Chaos game days inject controlled failures to test system resilience before production incidents do. Plan hypotheses, blast radius limits, rollback procedures, and post-game action items."
datePublished: "2025-01-28"
dateModified: "2025-01-28"
tags: ["DevOps", "Infrastructure", "Chaos Engineering", "SRE"]
keywords: "chaos engineering game day, fault injection testing, resilience testing, chaos monkey, game day planning, failure injection"
faq:
  - q: "What is a chaos engineering game day?"
    a: "A game day is a scheduled exercise where the team injects controlled failures into staging or production — killing pods, adding latency, blocking dependencies — to test whether the system handles them gracefully. The goal is learning, not breaking things. Every experiment has a hypothesis, blast radius limit, and rollback plan."
  - q: "Should chaos experiments run in production?"
    a: "Mature teams run limited experiments in production during low-traffic windows with strict blast radius controls. Start in staging until you've validated monitoring, rollback, and team response. Production game days require leadership approval, on-call awareness, and automatic abort conditions."
  - q: "How is a game day different from disaster recovery testing?"
    a: "DR testing validates backup restoration and failover to a secondary region — a planned, all-hands event. Game days inject small, specific failures to test detection and graceful degradation — 'what if Redis is slow?' not 'what if the region is gone.' Both are valuable; game days happen more frequently."
---

You don't know if your circuit breaker works until something trips it. You don't know if your fallback cache works until the primary database is unreachable. Waiting for production to teach these lessons at 3 AM is expensive. Chaos engineering game days inject controlled failures in daylight, with the team watching dashboards, to find weaknesses before customers do.

## Game day structure

```
Plan (1 week before) → Brief (day of) → Execute → Observe → Debrief → Action items
```

**Duration:** 2–4 hours. Not a full day — attention fades.

**Participants:** On-call engineers, service owners for affected systems, optional observer from leadership.

## Writing hypotheses

Every experiment starts with a hypothesis:

```markdown
## Experiment: Redis primary failure

**Hypothesis:** When Redis primary becomes unavailable, the app falls back
to read-only mode from Redis replica within 30 seconds and serves
cached data with < 5% error rate.

**Blast radius:** staging environment, 10% of traffic via feature flag
**Abort condition:** error rate > 10% for 2 minutes
**Rollback:** restore Redis primary via kubectl, max 5 minutes
**Metrics to watch:** error rate, p95 latency, cache hit ratio, fallback activation
```

No hypothesis = no learning. "Let's break Redis and see what happens" produces chaos, not engineering.

## Experiment examples by maturity

**Level 1 (staging):**
- Kill one app pod — does Kubernetes reschedule?
- Add 500ms latency to database — do timeouts fire?
- Fill disk to 95% — do alerts trigger?

**Level 2 (staging, multi-service):**
- Block payment service — does checkout show graceful error?
- Stop Kafka broker — do consumers reconnect and catch up?
- Simulate DNS failure for external dependency

**Level 3 (production, limited):**
- Kill one canary pod in prod
- Inject latency to 1% of requests via service mesh
- Disable one CDN PoP

## Tools

| Tool | What it does |
|------|-------------|
| Chaos Mesh | K8s-native fault injection (pod kill, network, IO) |
| Litmus | K8s chaos experiments with workflows |
| AWS FIS | EC2, RDS, network fault injection |
| Toxiproxy | TCP proxy for latency/timeout/reset |
| Gremlin | Multi-platform fault injection SaaS |

Chaos Mesh example:

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: kill-api-pod
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: [staging]
    labelSelectors:
      app: api-server
  duration: "30s"
```

## Blast radius controls

Non-negotiable safety rails:

1. **Environment:** staging first, prod only with approval
2. **Traffic percentage:** feature flag or service mesh limits affected requests
3. **Time box:** experiment auto-reverts after duration
4. **Abort button:** one person has authority to stop immediately
5. **Business hours:** never during peak traffic or freeze periods
6. **Monitoring:** dashboards open before injection starts

## During the game day

**Facilitator role:** Runs the experiment, calls abort if needed, keeps time.  
**Observer role:** Watches dashboards, notes timestamps of anomalies.  
**Service owner:** Validates service-specific behavior.

Timeline:
- 0:00 — Brief: review hypothesis, confirm abort conditions
- 0:10 — Baseline: record normal metrics for 10 minutes
- 0:20 — Inject failure
- 0:20–0:50 — Observe (30 min)
- 0:50 — Rollback
- 1:00 — Debrief

Don't fix things during the experiment — note them for debrief. Fixing mid-game corrupts the learning.

## Debrief template

```markdown
## Game Day: [date]

### Hypothesis result
Confirmed / Partially confirmed / Refuted

### What happened
[Timeline of events with metric screenshots]

### Surprises
[Things we didn't expect]

### Action items
| Item | Owner | Due |
|------|-------|-----|
| Add circuit breaker to payment client | @alex | Feb 15 |
| Fix alert threshold on Redis failover | @sam | Feb 10 |

### Follow-up experiments
[What to test next game day]
```

Action items are the product. Game days without follow-up are performance art.

## Building a program

- **Quarterly game days** for the platform team
- **Monthly** for critical payment/auth services
- **Automated steady-state experiments** in CI (kill pod, verify recovery)
- **Blameless culture** — finding a weakness is success, not failure

I've seen teams discover missing timeouts, silent fallback failures, and alerting gaps that would have caused hour-long outages — found in 30 minutes on a Tuesday afternoon.

Schedule the next game day before closing action items from the last one — momentum dies when experiments wait for quarterly planning cycles.

## Steady-state vs game day experiments

Not all chaos needs a calendar invite:

| Type | Frequency | Scope | Tooling |
|------|-----------|-------|---------|
| Steady-state | Continuous | Kill random pod, verify recovery | Chaos Mesh, Litmus |
| Game day | Quarterly | Multi-service failure scenarios | Manual + runbooks |
| Drill | Monthly | Single dependency failure | Fault injection API |

Steady-state catches regressions between game days — a new deploy without circuit breaker surfaces in CI chaos tests, not six months later.

## Blast radius controls

Never run uncontrolled experiments in production without guardrails:

```yaml
# Chaos Mesh experiment scope
spec:
  selector:
    namespaces: [staging]
  mode: one
  action: pod-failure
  duration: "30s"
```

Production game days need: executive approval, comms plan, rollback owner on-call, abort criteria ("error rate > 5% for 2 min → stop"), and customer impact assessment.

## Measuring game day ROI

Track outcomes, not activity:

- Action items closed within SLA (target: 90% within 30 days)
- Incidents in next quarter related to untested failure modes (target: zero)
- Mean time to detect during experiment vs last real incident
- Services with no game day coverage in 12 months (backlog)

Pair with [postmortems blameless culture](https://blog.michaelsam94.com/postmortems-blameless-culture/) when game day experiments surface production weaknesses.

## Common production mistakes

Teams get engineering game days wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of engineering game days fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [Chaos Mesh documentation](https://chaos-mesh.org/docs/)
- [Google SRE — testing for reliability](https://sre.google/sre-book/testing-reliability/)
- [AWS Fault Injection Service](https://docs.aws.amazon.com/fis/latest/userguide/what-is.html)
- [Netflix Chaos Monkey (original)](https://github.com/Netflix/chaosmonkey)
