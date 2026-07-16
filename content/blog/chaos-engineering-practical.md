---
title: "Practical Chaos Engineering"
slug: "chaos-engineering-practical"
description: "Practical chaos engineering: forming a steady-state hypothesis, running fault injection safely, structuring game days, and turning findings into real reliability."
datePublished: "2026-06-15"
dateModified: "2026-06-15"
tags: ["SRE", "DevOps", "Reliability"]
keywords: "chaos engineering, fault injection, game days, resilience testing, chaos mesh, steady state hypothesis"
faq:
  - q: "What is chaos engineering?"
    a: "Chaos engineering is the practice of deliberately injecting faults into a system to test its resilience and discover weaknesses before they cause outages. You form a hypothesis about steady-state behavior, inject a controlled failure such as killing a pod or adding latency, and verify whether the system still behaves as expected — turning assumptions about reliability into evidence."
  - q: "Isn't chaos engineering just randomly breaking production?"
    a: "No — that's the caricature. Real chaos engineering is a controlled experiment with a hypothesis, a limited blast radius, an abort condition, and measurement. The randomness is bounded and the goal is learning, not destruction. You start in staging, minimize scope, and only expand once you trust your safeguards."
  - q: "Do I need production to do chaos engineering?"
    a: "Not to start. Staging and pre-production catch plenty of real weaknesses and let you build confidence in your tooling and abort mechanisms. But some failure modes — real traffic patterns, actual data volumes, live dependencies — only appear in production, so mature programs eventually run carefully scoped experiments there."
---

The value of chaos engineering isn't breaking things — it's converting your team's confident assumptions into tested facts. Chaos engineering is the disciplined practice of injecting controlled faults into a system to verify it behaves the way you believe it does under failure. You state what "healthy" looks like, deliberately introduce a failure like a dead node or 500 ms of added latency, and watch whether reality matches your expectation. When it doesn't, you've found a weakness on a Tuesday afternoon instead of during a 2 a.m. page.

I keep seeing chaos engineering dismissed as "randomly killing servers in prod," which is exactly the wrong mental model. Done properly it looks more like a physics experiment than an act of vandalism. Here's how I run it.

## Start with a steady-state hypothesis

You cannot inject a fault usefully until you can describe what "working" means in measurable terms. That's the steady-state hypothesis: a statement about a metric that should hold true regardless of the fault you're about to introduce.

A good hypothesis is specific and measurable:

> "With one of three payment-service replicas killed, checkout success rate stays above 99.5% and p99 latency stays under 800 ms for the duration of the experiment."

Vague hypotheses ("the system should be fine") give you nothing to measure against. The number in your hypothesis should tie back to your service level objectives — if you've done the work of [designing for observability with SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/), you already have the metrics and thresholds. Chaos experiments are, in a sense, SLO tests you run on purpose.

## Control the blast radius

The single most important discipline is limiting scope. Every experiment needs three things before it runs:

1. **A minimal blast radius** — the smallest fault that tests the hypothesis. One replica, not the whole deployment. One availability zone, not the region.
2. **An abort condition** — a clear metric threshold that, if crossed, halts the experiment automatically. "If checkout success drops below 98%, stop and roll back."
3. **A rollback that you've tested** — the mechanism to end the experiment must be more reliable than the thing you're testing.

I start every new experiment in staging, prove the tooling and the abort work, and only then consider production with the tightest possible scope. The teams that get burned are the ones who skip straight to "let's kill a prod database and see what happens" without a tested off-switch.

## Injecting faults

The toolable failure modes are more varied than "kill a process." The useful categories:

| Fault type | Example | What it tests |
| --- | --- | --- |
| Resource | CPU/memory pressure | Autoscaling, limits, OOM handling |
| Network | Latency, packet loss, partition | Timeouts, retries, circuit breakers |
| State | Kill pod, kill node | Failover, leader election, restarts |
| Dependency | Fail a downstream call | Graceful degradation, fallbacks |
| Clock | Skew time | Cert validation, token expiry, cron |

On Kubernetes, [Chaos Mesh](https://chaos-mesh.org/) makes most of these a declarative resource. Here's a network-latency experiment scoped to a single app label:

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: payment-latency
spec:
  action: delay
  mode: one              # exactly one matching pod
  selector:
    namespaces: ["prod"]
    labelSelectors:
      app: payment-service
  delay:
    latency: "500ms"
    jitter: "100ms"
  duration: "180s"       # auto-reverts after 3 minutes
```

Note `mode: one` and `duration` — the blast radius and the abort are encoded in the manifest itself. The experiment reverts automatically even if nobody's watching, which is the kind of safety net you want baked in rather than remembered.

## Game days: the human half

Tooling injects the fault; a game day exercises the people and process around it. A game day is a scheduled session where a team runs one or more experiments together, watches the system respond, and — critically — practices the *response*. Does the right alert fire? Does the on-call engineer know what to do? Is the runbook accurate?

The findings from a game day are usually split evenly between technical gaps ("the retry storm we didn't know about") and human gaps ("nobody had access to the dashboard that mattered"). Both are worth finding in a controlled setting. When a real incident does happen, the muscle memory from game days is what makes the [postmortem](https://blog.michaelsam94.com/incident-management-postmortems/) shorter, because the team has rehearsed the failure and already fixed half of what it would have surfaced.

## Turning findings into reliability

An experiment that surfaces a weakness and then gets forgotten is wasted work. Every finding should become one of three things: a fix (add the missing timeout), a guardrail (an alert or autoscaling policy), or a documented, accepted risk with an owner. Track them like you'd track any other engineering work.

The maturity signal I look for isn't how scary the experiments are — it's whether the same experiment stops finding new problems over time. When killing a random pod is a non-event because the system genuinely handles it, that experiment has done its job and you graduate to a harder one. Reliability is the slope of that curve, not any single dramatic test.

## A senior take on where it fits

Chaos engineering is not a beginner's tool. If your service has no monitoring, no SLOs, and no tested rollback, injecting faults just adds noise — build those first. But once you have observability and a system complex enough that you *can't* fully reason about its failure modes by inspection, chaos engineering is the most honest way to learn how it actually behaves. Distributed systems fail in ways nobody designed, and the only way to find those ways cheaply is to provoke them on your own schedule.

Start small, in staging, with a real hypothesis and a tested abort. Expand scope only as fast as your confidence in the safeguards grows. The goal is a system so well-understood that chaos experiments become boring — and boring, in reliability work, is the highest compliment there is.

## Resources

- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [Chaos Mesh documentation](https://chaos-mesh.org/docs/)
- [Netflix — Chaos Monkey / Simian Army](https://github.com/Netflix/chaosmonkey)
- [Google SRE Book — Testing for Reliability](https://sre.google/sre-book/testing-reliability/)
- [AWS Fault Injection Service](https://docs.aws.amazon.com/fis/)
- [Gremlin — Chaos Engineering resources](https://www.gremlin.com/chaos-engineering/)
