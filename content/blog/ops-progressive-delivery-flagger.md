---
title: "Progressive Delivery with Flagger"
slug: "ops-progressive-delivery-flagger"
description: "Automate canary analysis with Flagger: metric templates, traffic splitting on Istio and NGINX, rollback triggers, and GitOps integration for hands-off rollouts."
datePublished: "2026-01-13"
dateModified: "2026-01-13"
tags: ["DevOps", "Kubernetes", "Flagger", "Progressive Delivery"]
keywords: "Flagger canary, progressive delivery Kubernetes, automated canary analysis, Istio Flagger, GitOps rollout"
faq:
  - q: "What does Flagger automate in a canary deployment?"
    a: "Flagger creates a canary deployment, shifts traffic weight incrementally through your service mesh or ingress, runs metric checks at each step, promotes the canary on success, or rolls back on failure — all from a Canary CRD without manual VirtualService edits."
  - q: "Which metrics should Flagger use for rollback decisions?"
    a: "Request success rate (5xx ratio), request duration (p99 latency vs baseline), and any business metric you can expose to Prometheus. Avoid CPU — it's a lagging indicator. Flagger compares canary metrics against the primary deployment during each analysis interval."
  - q: "Does Flagger require Istio?"
    a: "No. Flagger supports Istio, Linkerd, App Mesh, NGINX Ingress, Contour, Gloo, and others via provider-specific traffic routing. You need a metrics source (Prometheus, Datadog, CloudWatch) and a supported ingress/mesh."
---

Manual canary deploys follow the same script: bump weight to 10%, stare at Grafana, bump to 25%, someone misclicks and jumps to 100%, rollback, postmortem. Flagger encodes the script into a CRD and removes the misclick. We adopted it after an Istio VirtualService edit took production to 50% canary at 4 AM because the on-call engineer pasted the wrong YAML block.

## How Flagger fits in the cluster

Flagger watches a target Deployment (via a `Canary` resource), creates a canary replica set, and manipulates traffic routing through your provider:

```
Canary CRD ──► Flagger controller
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Deployment   Service/Mesh   Prometheus
   (primary +   (traffic       (metric
    canary)      weights)       checks)
```

On success, Flagger scales down the primary and promotes the canary. On failure, it routes 100% back to primary and scales down the canary.

## A minimal Canary resource

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: api
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  progressDeadlineSeconds: 600
  service:
    port: 8080
  analysis:
    interval: 1m
    threshold: 5        # max failed checks before rollback
    maxWeight: 50
    stepWeight: 10
    metrics:
      - name: request-success-rate
        thresholdRange:
          min: 99
        interval: 1m
      - name: request-duration
        thresholdRange:
          max: 500        # milliseconds p99
        interval: 1m
  provider:
    type: istio
    address: istio-public-gateway.istio-system.svc
```

This runs: 10% → 20% → ... → 50% canary weight, checking every minute. If success rate drops below 99% for five consecutive checks, rollback.

## Metric templates

Flagger ships built-in metrics (`request-success-rate`, `request-duration`) that query Prometheus for Istio/Linkerd telemetry. Custom metrics use `MetricTemplate`:

```yaml
apiVersion: flagger.app/v1beta1
kind: MetricTemplate
metadata:
  name: checkout-conversion
  namespace: production
spec:
  provider:
    type: prometheus
    address: http://prometheus:9090
  query: |
    sum(rate(checkout_completed_total{namespace="{{ namespace }}"}[1m]))
    /
    sum(rate(checkout_started_total{namespace="{{ namespace }}"}[1m]))
```

Wire business metrics into rollback decisions. A canary with healthy latency but 3% lower conversion should not promote.

## GitOps workflow

Flagger modifies live cluster state (VirtualServices, Deployment replicas). With Argo CD:

- Store Deployment manifest and Canary CRD in Git
- Argo CD syncs Deployment; Flagger manages canary lifecycle
- Add `ignoreDifferences` for fields Flagger owns:

```yaml
spec:
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas
    - group: networking.istio.io
      kind: VirtualService
      jsonPointers:
        - /spec/http
```

Alternatively, use Argo Rollouts if you want the entire progressive delivery state in Git without controller-managed drift. Flagger vs Rollouts is partly taste — Flagger integrates cleanly with existing Deployments; Rollouts replaces the Deployment controller pattern.

## Webhooks for smoke tests

Run integration tests at each canary step:

```yaml
webhooks:
  - name: smoke-test
    type: pre-rollout
    url: http://flagger-loadtester.test/
    timeout: 30s
    metadata:
      cmd: "curl -sd 'test' http://api-canary:8080/health | grep ok"
  - name: load-test
    type: rollout
    url: http://flagger-loadtester.test/
    metadata:
      cmd: "hey -z 1m -q 10 -c 2 http://api-canary:8080/"
```

The loadtester service runs commands in a pod with mesh access to canary endpoints. Pre-rollout hooks block promotion; rollout hooks run during traffic shift.

## Operating Flagger in production

**Start conservative.** `stepWeight: 5`, `maxWeight: 30` until you trust metrics. Aggressive ramps hide gradual leaks.

**Align HPA with canary.** Both primary and canary need headroom. If HPA maxes primary at 20 pods and canary gets 50% traffic with 2 pods, you're load-testing failure.

**Notifications.** Flagger supports Slack, Teams, Rocket, and generic webhooks. Post canary start, promotion, and rollback events to `#deploys`.

**Manual gating.** `canary.skip-analysis: "true"` annotation pauses for approval — useful for regulated environments that still want automated traffic mechanics.

## Load testing during canary analysis

Flagger's loadtester webhooks shine when synthetic traffic hits the canary subset before real users do. Configure `hey` or `k6` scripts that exercise critical endpoints — checkout, auth, search — not just `/health`. Health can pass while business logic fails under canary traffic mix.

Match load profile to expected canary weight. If canary receives 10% traffic, load test at 10% of peak RPS against canary endpoints specifically. Watch canary pod CPU separately from primary — asymmetric load exposes HPA misconfiguration early.

## Operational notes

Flagger integrates with Slack and Microsoft Teams notifiers — configure `AlertProvider` CRDs so canary failures page the same channel as other production alerts. Include direct links to Grafana dashboards filtered by canary pod labels in notification templates. On-call should not hunt for the right dashboard during a rollback.

Keep Flagger and mesh versions pinned together in dependency lockfiles.

## Common production mistakes

Teams get progressive delivery flagger wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of progressive delivery flagger fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When progressive delivery flagger misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Flagger documentation](https://docs.flagger.app/)
- [Flagger Istio tutorial](https://docs.flagger.app/tutorials/istio-progressive-delivery)
- [Flagger metric templates](https://docs.flagger.app/usage/metrics)
- [Weaveworks Flagger GitHub](https://github.com/fluxcd/flagger)
- [Argo Rollouts comparison and alternatives](https://argoproj.github.io/argo-rollouts/)
