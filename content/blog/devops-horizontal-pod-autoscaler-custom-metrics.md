---
title: "HPA with Custom and External Metrics"
slug: "devops-horizontal-pod-autoscaler-custom-metrics"
description: "Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2."
datePublished: "2026-03-03"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Observability"
keywords: "HPA, custom metrics, KEDA"
faq:
  - q: "When should teams prioritize HPA with Custom and External Metrics?"
    a: "When CPU/memory do not correlate with user-visible latency or backlog."
  - q: "What is the most common mistake with HPA v2?"
    a: "Scaling on CPU alone during I/O-bound spikes never adds pods."
  - q: "Custom metrics adapter or KEDA?"
    a: "HPA v2 with Prometheus adapter fits simple pod metrics. KEDA adds scale-to-zero, external scalers (SQS, Kafka lag), and clearer event-driven semantics."
  - q: "How do we know HPA with Custom and External Metrics is working?"
    a: "Define a leading metric for HPA v2 health and a lagging metric tied to incidents. If you only measure after outages, the control is decorative."
---
Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only.

## What changes when you leave the tutorial


Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2.

Production hpa with custom and external metrics fails on retries, partial outages, and human process gaps — not on the happy-path tutorial.

## Design constraints you cannot ignore


Prefer defaults that fail closed: deny, queue, or degrade safely rather than return silently wrong data.

Document who may change HPA v2 in production, how rollback works, and which environments are allowed to diverge.

## Step-by-step in production order


1. Inventory consumers and SLAs. 2. Implement enforcement on the write/promote path. 3. Add observability. 4. Drill failure modes. 5. Expand scope.

Validate each step with someone who did not write the original HPA v2 config — fresh eyes catch assumptions.

## Edge cases that bypass happy-path tests


Edge cases: late-arriving data, duplicate events, schema drift mid-run, credential rotation during job execution, and traffic spikes during deploy.

For each, document drop vs retry vs dead-letter vs fail-closed — and test it.

## Observability hooks


Structured logs with run_id, partition, and validation outcome. Metrics with bounded labels — never high-cardinality user IDs on Prometheus.

Traces across orchestrator, worker, and warehouse when requests cross team boundaries.

## Summary


HPA with Custom and External Metrics earns its keep when it prevents silent corruption, unsafe deploys, or unbounded cost — not when it decorates a architecture diagram.

## Reference configuration


```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: checkout-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: checkout-api
  minReplicas: 3
  maxReplicas: 40
  metrics:
    - type: Pods
      pods:
        metric:
          name: checkout_queue_depth
        target:
          type: AverageValue
          averageValue: "30"

```

## Metric adapter reliability

Custom metrics HPA depends on metrics-server or prometheus-adapter availability. Alert on adapter scrape failures and stale metric timestamps — HPA with missing metrics stops scaling silently while backlog grows.

## HPA v2 metrics wiring

Register custom metrics APIs via prometheus-adapter or use KEDA ScaledObject. Verify metrics appear in `kubectl get --raw /apis/external.metrics.k8s.io`. Stale metrics timestamps mean HPA stops scaling — alert on adapter health.

## Scale behavior tuning

Set `behavior.scaleUp.stabilizationWindowSeconds` to avoid flapping on noisy queue metrics. Scale-down slower than scale-up for latency-sensitive tiers. Document max replicas with finance — unbounded max replicas is a cost incident.

## When HPA v2 becomes load-bearing

When CPU/memory do not correlate with user-visible latency or backlog. At that point hpa with custom and external metrics stops being a platform nice-to-have and becomes part of the release contract. Teams that defer instrumentation until after the first GitOps or Helm incident usually rebuild dashboards under pager pressure — metrics added during calm weeks have sane cardinality and alert text.

## What the incident looked like

Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only. On-call infrastructure graphs stayed green because the failure mode lived in the gap between declared state and user-visible behavior. Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2. The fix was not another controller restart — it was making HPA v2 observable on the same timeline as application deploys.

## The mistake to design against

Scaling on CPU alone during I/O-bound spikes never adds pods. Platform reviews should treat that failure as a design requirement, not a footnote. Encode the guard in CI, admission, or plan-time policy so the bad change fails before merge. Document the exception process for break-glass — who approves, how long it lasts, and how Git catches up afterward.

## How Kubernetes teams operationalize HPA v2

Name primary and secondary owners. Link dashboards from the service runbook index on-call already opens. Run a quarterly drill: break HPA v2 safely in staging, confirm alerts route to the right rotation, and verify rollback restores the previous known-good state without manual cluster surgery.

## Rollout and evidence

Wave changes: internal consumers, small canary cohort, 48-hour soak, then full promote. Keep the prior artifact revision hot-swappable for one release cycle. Store CI artifacts — rendered manifests, policy reports, simulator output — so incident review can answer what changed without reconstructing history from memory.

## Cross-team interfaces

Application, security, and finance teams consume outcomes from HPA v2 differently. Publish a short interface doc: what the control blocks, what it logs, and who to ping when a false positive stops a legitimate deploy. Ambiguous ownership is how configs drift until the next audit or customer-visible outage.

## Capacity and cost angles

Even when hpa with custom and external metrics is primarily about correctness, it affects cost: retries, idle GPU nodes, oversized autoscale max, or LB flapping all show up on the invoice after a misconfigured gate. Review HPA v2 settings when traffic doubles or when finance flags a new line item — not only after hard outages.

Runbooks for HPA v2 should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where HPA v2 was involved — even if the root cause was elsewhere.

Staging must exercise the same HPA v2 code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only. Capture that story in the team onboarding doc so new engineers understand why hpa with custom and external metrics exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

Security and compliance reviews increasingly ask for evidence, not assertions. Export audit logs showing who changed HPA v2 settings, which CI job validated the change, and when the last game day passed. OIDC-federated deploy roles beat long-lived keys stored in CI secrets.

FinOps partners care when misconfigured HPA v2 causes retry storms, idle GPU nodes, or runaway autoscale. Add a quarterly joint review with finance when this control touches capacity: right-size max replicas, GPU quotas, and LB pools using production metrics — not spreadsheet guesses.

Runbooks for HPA v2 should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where HPA v2 was involved — even if the root cause was elsewhere.

Staging must exercise the same HPA v2 code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only. Capture that story in the team onboarding doc so new engineers understand why hpa with custom and external metrics exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

Security and compliance reviews increasingly ask for evidence, not assertions. Export audit logs showing who changed HPA v2 settings, which CI job validated the change, and when the last game day passed. OIDC-federated deploy roles beat long-lived keys stored in CI secrets.

## Further reading

- https://kubernetes.io/docs/home/
- https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/
