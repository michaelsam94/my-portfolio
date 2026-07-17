---
title: "GPU Node Scheduling and Fractional GPUs"
slug: "devops-gpu-node-scheduling"
description: "Schedule ML workloads on GPU nodes with device plugins, taints, and MIG."
datePublished: "2026-03-12"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "MLOps"
keywords: "GPU scheduling, device plugin"
faq:
  - q: "When should teams prioritize GPU Node Scheduling and Fractional GPUs?"
    a: "Before production ML training or inference on Kubernetes."
  - q: "What is the most common mistake with GPU device plugin?"
    a: "Missing taints let non-GPU workloads consume expensive GPU nodes."
  - q: "Fractional GPUs or dedicated nodes?"
    a: "Dedicated nodes with taints for training; time-slicing or MIG for inference when utilization is low. Mixing without quotas lets batch training starve latency-sensitive inference."
  - q: "How do we know GPU Node Scheduling and Fractional GPUs is working?"
    a: "Define a leading metric for GPU device plugin health and a lagging metric tied to incidents. If you only measure after outages, the control is decorative."
---
Training jobs pending-scheduled for hours because GPU nodes ran default workloads. This post is about making gpu node scheduling and fractional gpus boring in the best way — predictable under load, auditable under review, and reversible under stress.

## What broke first on dashboards


Training jobs pending-scheduled for hours because GPU nodes ran default workloads.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to missing taints let non-gpu workloads consume expensive gpu nodes.

GPU device plugin was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move GPU device plugin into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```yaml
apiVersion: v1
kind: Node
metadata:
  name: gpu-node-1
  labels:
    nvidia.com/gpu.present: "true"
  taints:
    - key: nvidia.com/gpu
      value: "true"
      effect: NoSchedule

```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put GPU device plugin on the critical path for one tier-1 workflow and measure what it catches.

## Scheduling latency vs utilization

GPU nodes are expensive idle. Track pending pod duration for `nvidia.com/gpu` requests, node occupancy, and preemption events. Right-size MIG profiles from inference batch shapes — wrong profile wastes silicon.

## Node pool design

Label GPU nodes with instance type, driver version, and MIG profile. Use `nvidia.com/gpu` resource requests explicitly — limits alone do not schedule. Separate pools for training (large memory) and inference (low latency).

## Quotas and fairness

ResourceQuota per namespace on GPU requests prevents one team from monopolizing the pool. PriorityClass lets inference preempt best-effort training when SLO burn accelerates — document preemption policy for ML leads.

## Observability

Scrape DCGM metrics: utilization, memory used, temperature, XID errors. Correlate with pod pending time and scheduler events. A node with zero utilization but full allocation often indicates stuck GPU contexts.

## When GPU device plugin becomes load-bearing

Before production ML training or inference on Kubernetes. At that point gpu node scheduling and fractional gpus stops being a platform nice-to-have and becomes part of the release contract. Teams that defer instrumentation until after the first GitOps or Helm incident usually rebuild dashboards under pager pressure — metrics added during calm weeks have sane cardinality and alert text.

## What the incident looked like

Training jobs pending-scheduled for hours because GPU nodes ran default workloads. On-call infrastructure graphs stayed green because the failure mode lived in the gap between declared state and user-visible behavior. Schedule ML workloads on GPU nodes with device plugins, taints, and MIG. The fix was not another controller restart — it was making GPU device plugin observable on the same timeline as application deploys.

## The mistake to design against

Missing taints let non-GPU workloads consume expensive GPU nodes. Platform reviews should treat that failure as a design requirement, not a footnote. Encode the guard in CI, admission, or plan-time policy so the bad change fails before merge. Document the exception process for break-glass — who approves, how long it lasts, and how Git catches up afterward.

## How Kubernetes teams operationalize GPU device plugin

Name primary and secondary owners. Link dashboards from the service runbook index on-call already opens. Run a quarterly drill: break GPU device plugin safely in staging, confirm alerts route to the right rotation, and verify rollback restores the previous known-good state without manual cluster surgery.

## Rollout and evidence

Wave changes: internal consumers, small canary cohort, 48-hour soak, then full promote. Keep the prior artifact revision hot-swappable for one release cycle. Store CI artifacts — rendered manifests, policy reports, simulator output — so incident review can answer what changed without reconstructing history from memory.

## Cross-team interfaces

Application, security, and finance teams consume outcomes from GPU device plugin differently. Publish a short interface doc: what the control blocks, what it logs, and who to ping when a false positive stops a legitimate deploy. Ambiguous ownership is how configs drift until the next audit or customer-visible outage.

## Capacity and cost angles

Even when gpu node scheduling and fractional gpus is primarily about correctness, it affects cost: retries, idle GPU nodes, oversized autoscale max, or LB flapping all show up on the invoice after a misconfigured gate. Review GPU device plugin settings when traffic doubles or when finance flags a new line item — not only after hard outages.

Runbooks for GPU device plugin should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where GPU device plugin was involved — even if the root cause was elsewhere.

Staging must exercise the same GPU device plugin code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Training jobs pending-scheduled for hours because GPU nodes ran default workloads. Capture that story in the team onboarding doc so new engineers understand why gpu node scheduling and fractional gpus exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

Security and compliance reviews increasingly ask for evidence, not assertions. Export audit logs showing who changed GPU device plugin settings, which CI job validated the change, and when the last game day passed. OIDC-federated deploy roles beat long-lived keys stored in CI secrets.

FinOps partners care when misconfigured GPU device plugin causes retry storms, idle GPU nodes, or runaway autoscale. Add a quarterly joint review with finance when this control touches capacity: right-size max replicas, GPU quotas, and LB pools using production metrics — not spreadsheet guesses.

Runbooks for GPU device plugin should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where GPU device plugin was involved — even if the root cause was elsewhere.

Staging must exercise the same GPU device plugin code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Training jobs pending-scheduled for hours because GPU nodes ran default workloads. Capture that story in the team onboarding doc so new engineers understand why gpu node scheduling and fractional gpus exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

Security and compliance reviews increasingly ask for evidence, not assertions. Export audit logs showing who changed GPU device plugin settings, which CI job validated the change, and when the last game day passed. OIDC-federated deploy roles beat long-lived keys stored in CI secrets.

FinOps partners care when misconfigured GPU device plugin causes retry storms, idle GPU nodes, or runaway autoscale. Add a quarterly joint review with finance when this control touches capacity: right-size max replicas, GPU quotas, and LB pools using production metrics — not spreadsheet guesses.

## Further reading

- https://opentelemetry.io/docs/
