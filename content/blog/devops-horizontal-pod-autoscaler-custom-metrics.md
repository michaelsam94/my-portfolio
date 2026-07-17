---
title: "HPA with Custom and External Metrics"
slug: "devops-horizontal-pod-autoscaler-custom-metrics"
description: "Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2."
datePublished: "2026-03-03"
dateModified: "2026-03-03"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Observability"
keywords: "HPA, custom metrics, KEDA"
faq:
  - q: "What is HPA?"
    a: "HPA covers operational practices for HPA v2 in production kubernetes environments: design, rollout, observability, failure modes, and day-two maintenance—not a one-time setup task."
  - q: "When should teams prioritize HPA?"
    a: "When CPU/memory do not correlate with user-visible latency or backlog."
  - q: "What mistakes break HPA?"
    a: "Scaling on CPU alone during I/O-bound spikes never adds pods."
---

Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only.

This post walks through **HPA with Custom and External Metrics** for platform and SRE teams shipping reliable infrastructure. Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2. You will get concrete configuration patterns, operational guardrails, and review questions that catch mistakes before production—not after an incident writes the requirements doc.

## Problem framing: HPA with Custom and External Metrics

Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only.


Platform teams treat **HPA v2** as solved after the first successful deploy. Production disagrees: edge cases around horizontal pod autoscaler custom metrics, dependency failures, and human process gaps show up under real load. The sections below capture patterns that survive review, incident response, and gradual traffic growth—not just a green CI badge.

## Design principles for HPA v2

Explicit contracts beat tribal knowledge. Document who owns HPA v2 configuration, which environments may change it, and how rollback works when a change misbehaves. Prefer defaults that **fail closed**—deny, queue, or degrade safely rather than return partial wrong answers.


A common failure mode: Scaling on CPU alone during I/O-bound spikes never adds pods. Bake guards into CI, admission control, or plan-time policy so the mistake is caught before merge—not discovered by customers or auditors.


```yaml
# devops-horizontal-pod-autoscaler-custom-metrics
apiVersion: apps/v1
kind: Deployment
metadata:
  name: horizontal_pod_autoscaler_custom_metrics
  labels:
    app.kubernetes.io/part-of: devops-horizontal-pod-autoscaler-custom-metrics
spec:
  replicas: 3
  selector:
    matchLabels:
      app: horizontal_pod_autoscaler_custom_metrics
  template:
    metadata:
      labels:
        app: horizontal_pod_autoscaler_custom_metrics
    spec:
      containers:
        - name: app
          image: app:1.0.0
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
```

## Implementation walkthrough

Start with the smallest production-safe slice of **HPA with Custom and External Metrics**. Ship observability first: structured logs, metrics with low-cardinality labels, and traces where requests cross team boundaries. Without telemetry, you cannot prove the change helped or hurt after rollout.


Automate repetitive steps—CLI scripts, GitOps repos, or pipeline jobs—so on-call engineers do not hand-edit production during incidents. Keep runbooks next to dashboards with the three golden signals: latency, errors, and saturation for HPA v2.

## Operational concerns in production

Day-two operations for kubernetes work is mostly guardrails: capacity headroom, alert routing, and ownership rotation. Define SLOs tied to user-visible outcomes—not vanity metrics like pod count alone. Page on symptom-based alerts (error budget burn, queue age, failed reconciliation) and ticket on causes.


Run game days or fault injection in staging quarterly for horizontal pod autoscaler custom metrics. Inject latency, credential expiry, and partial outages. Update this runbook with what broke—not generic advice copied from vendor docs.

## Security and compliance angles

Even when HPA with Custom and External Metrics is not labeled security software, it participates in your trust boundary. Apply least privilege to service accounts and CI roles. Rotate secrets on a schedule with overlap windows. Validate inputs at the perimeter—especially when HPA v2 accepts configuration from multiple teams.


For regulated workloads, maintain an immutable audit trail: who changed HPA v2 settings, when, and from which pipeline or break-glass session. Prefer short-lived credentials and OIDC federation over long-lived keys in environment variables.

## Integration with platform standards

Align HPA v2 with org-wide pod security, network policy, and secret management baselines. If External Secrets Operator syncs credentials, verify rotation does not require chart upgrades. If service mesh mTLS is mandatory, confirm sidecar injection labels in rendered manifests before merge.


Capacity planning should precede rollout: estimate peak QPS, bytes per second, or concurrent jobs; multiply by headroom (typically 1.5–2×); compare against quotas and cloud limits. File increase requests before launch week, not during an incident.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.

## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.

## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.

## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.

## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.


## Resources

- https://kubernetes.io/docs/home/
- https://github.com/kubernetes/community/tree/master/contributors/devel/sig-architecture
