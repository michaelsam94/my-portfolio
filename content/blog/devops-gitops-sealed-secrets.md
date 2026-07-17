---
title: "Sealed Secrets and SOPS in GitOps"
slug: "devops-gitops-sealed-secrets"
description: "Encrypt secrets in Git with Sealed Secrets or SOPS for GitOps repos."
datePublished: "2026-05-22"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "GitOps"
  - "Security"
keywords: "Sealed Secrets, SOPS, GitOps"
faq:
  - q: "When should teams prioritize Sealed Secrets and SOPS in GitOps?"
    a: "When GitOps repos must contain Kubernetes Secret manifests."
  - q: "What is the most common mistake with Sealed Secrets?"
    a: "Sealed secret key loss—cannot rotate or unseal during disaster."
  - q: "Should GitOps controllers auto-sync production?"
    a: "Many teams use manual sync or approval for prod while auto-syncing dev/staging. The controller should still reconcile drift on a schedule you can observe — silent auto-sync without metrics is how stale deployments hide for hours."
  - q: "Where do secrets belong in GitOps repos?"
    a: "Encrypted at rest with Sealed Secrets, SOPS, or ESO-synced references — never plaintext. Validate decryption in CI and restrict who can seal for each cluster scope."
---
If Sealed Secrets is not on your promote path today, you do not have sealed secrets and sops in gitops — you have a checklist item.

## What changes when you leave the tutorial


Encrypt secrets in Git with Sealed Secrets or SOPS for GitOps repos.

Production sealed secrets and sops in gitops fails on retries, partial outages, and human process gaps — not on the happy-path tutorial.

## Design constraints you cannot ignore


Prefer defaults that fail closed: deny, queue, or degrade safely rather than return silently wrong data.

Document who may change Sealed Secrets in production, how rollback works, and which environments are allowed to diverge.

## Step-by-step in production order


1. Inventory consumers and SLAs. 2. Implement enforcement on the write/promote path. 3. Add observability. 4. Drill failure modes. 5. Expand scope.

Validate each step with someone who did not write the original Sealed Secrets config — fresh eyes catch assumptions.

## Edge cases that bypass happy-path tests


Edge cases: late-arriving data, duplicate events, schema drift mid-run, credential rotation during job execution, and traffic spikes during deploy.

For each, document drop vs retry vs dead-letter vs fail-closed — and test it.

## Observability hooks


Structured logs with run_id, partition, and validation outcome. Metrics with bounded labels — never high-cardinality user IDs on Prometheus.

Traces across orchestrator, worker, and warehouse when requests cross team boundaries.

## Summary


Sealed Secrets and SOPS in GitOps earns its keep when it prevents silent corruption, unsafe deploys, or unbounded cost — not when it decorates a architecture diagram.

## Reference configuration


```yaml
apiVersion: bitnami.com/v1alpha1
kind: SealedSecret
metadata:
  name: db-credentials
spec:
  encryptedData:
    password: AgBx...  # sealed for cluster scope only

```

## Reconciliation is not deployment

A green Synced status means the controller applied manifests — not that pods passed readiness, migrations finished, or traffic shifted. Pair GitOps metrics with application SLIs: error rate, queue depth, and deployment revision labels on series.

## Argo CD metrics that matter

Export `argocd_app_info`, `argocd_app_sync_total`, and reconciliation histograms. Alert when sync status stays `OutOfSync` or `Unknown` beyond your deployment SLO. Dashboard rows: application, project, cluster — not only controller pod CPU.

## Flux controller signals

For Flux, watch `gotk_reconcile_duration_seconds`, `gotk_reconcile_condition`, and source fetch errors. A failed GitRepository or HelmRepository blocks every downstream Kustomization — page on source errors before child sync failures cascade.

## Silent failure modes

Auto-sync disabled with no alert is a common gap: manifests drift in Git while clusters run stale config. Compare live image digests against Git-declared digests on a schedule. Health status `Healthy` in Argo does not guarantee pod readiness.

## Dashboard layout for on-call

Top row: count of apps not Synced, reconciliation error rate, oldest pending sync. Second row: controller queue depth, repo fetch latency, webhook delivery failures. Link each panel to a runbook step — not a wiki search.

## When Sealed Secrets becomes load-bearing

When GitOps repos must contain Kubernetes Secret manifests. At that point sealed secrets and sops in gitops stops being a platform nice-to-have and becomes part of the release contract. Teams that defer instrumentation until after the first GitOps or Helm incident usually rebuild dashboards under pager pressure — metrics added during calm weeks have sane cardinality and alert text.

## What the incident looked like

Plaintext Secret committed—history scrub required audit finding. On-call infrastructure graphs stayed green because the failure mode lived in the gap between declared state and user-visible behavior. Encrypt secrets in Git with Sealed Secrets or SOPS for GitOps repos. The fix was not another controller restart — it was making Sealed Secrets observable on the same timeline as application deploys.

## The mistake to design against

Sealed secret key loss—cannot rotate or unseal during disaster. Platform reviews should treat that failure as a design requirement, not a footnote. Encode the guard in CI, admission, or plan-time policy so the bad change fails before merge. Document the exception process for break-glass — who approves, how long it lasts, and how Git catches up afterward.

## How GitOps teams operationalize Sealed Secrets

Name primary and secondary owners. Link dashboards from the service runbook index on-call already opens. Run a quarterly drill: break Sealed Secrets safely in staging, confirm alerts route to the right rotation, and verify rollback restores the previous known-good state without manual cluster surgery.

## Rollout and evidence

Wave changes: internal consumers, small canary cohort, 48-hour soak, then full promote. Keep the prior artifact revision hot-swappable for one release cycle. Store CI artifacts — rendered manifests, policy reports, simulator output — so incident review can answer what changed without reconstructing history from memory.

## Cross-team interfaces

Application, security, and finance teams consume outcomes from Sealed Secrets differently. Publish a short interface doc: what the control blocks, what it logs, and who to ping when a false positive stops a legitimate deploy. Ambiguous ownership is how configs drift until the next audit or customer-visible outage.

## Capacity and cost angles

Even when sealed secrets and sops in gitops is primarily about correctness, it affects cost: retries, idle GPU nodes, oversized autoscale max, or LB flapping all show up on the invoice after a misconfigured gate. Review Sealed Secrets settings when traffic doubles or when finance flags a new line item — not only after hard outages.

Runbooks for Sealed Secrets should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where Sealed Secrets was involved — even if the root cause was elsewhere.

Staging must exercise the same Sealed Secrets code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Plaintext Secret committed—history scrub required audit finding. Capture that story in the team onboarding doc so new engineers understand why sealed secrets and sops in gitops exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

Security and compliance reviews increasingly ask for evidence, not assertions. Export audit logs showing who changed Sealed Secrets settings, which CI job validated the change, and when the last game day passed. OIDC-federated deploy roles beat long-lived keys stored in CI secrets.

FinOps partners care when misconfigured Sealed Secrets causes retry storms, idle GPU nodes, or runaway autoscale. Add a quarterly joint review with finance when this control touches capacity: right-size max replicas, GPU quotas, and LB pools using production metrics — not spreadsheet guesses.

Runbooks for Sealed Secrets should fit on one printed page: prerequisites, rollback, and the three metrics on-call checks first. Link that page from alert annotations so nobody searches Confluence during a SEV. Update the runbook after every incident where Sealed Secrets was involved — even if the root cause was elsewhere.

Staging must exercise the same Sealed Secrets code paths as production, including failure modes you expect to handle. A green staging deploy without negative tests gives false confidence. Inject faults quarterly: expired credentials, slow dependencies, and partial outages shaped like your last postmortem.

Plaintext Secret committed—history scrub required audit finding. Capture that story in the team onboarding doc so new engineers understand why sealed secrets and sops in gitops exists. Architecture diagrams age quickly; incident narratives and concrete guardrails stay memorable. Prefer automated enforcement over reviewer vigilance — humans miss typos at 5 p.m. on Fridays.

## Further reading

- https://opentelemetry.io/docs/
