---
title: "Detecting Infrastructure Drift"
slug: "terraform-drift-detection"
description: "Detecting and managing Terraform drift: plan in CI, drift detection tools, manual console changes, import workflows, and policies that keep state aligned with reality."
datePublished: "2025-12-06"
dateModified: "2026-07-17"
tags: ["Terraform", "DevOps", "Infrastructure", "CI/CD"]
keywords: "Terraform drift detection, infrastructure drift, terraform plan CI, Spacelift drift, manual console changes, state reconciliation"
faq:
  - q: "What is infrastructure drift?"
    a: "Drift occurs when real infrastructure differs from what Terraform state and configuration declare — usually because someone changed resources manually in the AWS console, a vendor auto-updated settings, or state was corrupted. The next terraform apply may unexpectedly revert manual fixes or fail because state no longer matches reality."
  - q: "How do you detect Terraform drift automatically?"
    a: "Run terraform plan on a schedule (daily or hourly) in read-only mode against each workspace. Non-empty plans indicate drift. Tools like Spacelift, env0, Terraform Cloud, and driftctl automate scheduled plans and alert on changes. CI pipelines should also plan on every PR that touches .tf files."
  - q: "Should you revert drift or update Terraform code?"
    a: "If the manual change was intentional and correct, codify it in .tf and refresh state. If it was accidental or non-compliant, apply Terraform to revert. Never ignore drift — silent divergence accumulates until apply causes outage. Document emergency console changes and backport to code within SLA (e.g., 24 hours)."
faqAnswers:
  - question: "When is terraform drift detection the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for terraform drift detection?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back terraform drift detection safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Someone scaled the RDS instance in the console during an incident. Terraform state still said `db.t3.medium`. The next routine apply downsized it back — during business hours. That was the day our team implemented scheduled drift detection and a rule: console changes are allowed in emergencies, but the PR that codifies or reverts them ships before the incident is closed.

Drift is inevitable the moment humans have both Terraform and console access. The goal is not zero drift forever — it is detect drift fast, decide intentionally, reconcile state and code.

## How drift happens

- Emergency manual scaling or security group edit
- Autoscaling changing ASG desired count outside Terraform
- Default settings applied by cloud vendor after resource creation
- Multiple tools managing same resource (Terraform + Helm + click-ops)
- State file out of sync after import failure

Terraform compares **configuration + state** to **provider API reality** during plan. Any diff is drift signal.

## Scheduled plan — minimum viable detection

```yaml
# GitHub Actions (simplified)
on:
  schedule:
    - cron: "0 6 * * *"

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init -backend-config=prod.hcl
      - run: terraform plan -detailed-exitcode -no-color
        continue-on-error: true
        id: plan
      - if: steps.plan.outcome == 'failure' && steps.plan.outputs.exitcode == 2
        run: |
          slack-notify "Drift detected in prod — review plan artifact"
```

Exit code 2 = changes present. Fail the job and notify. Read-only credentials (`plan` IAM role) prevent accidental apply from automation.

## Drift detection tools

| Tool | Approach |
| --- | --- |
| Terraform Cloud | Continuous or triggered speculative plans |
| Spacelift / env0 | Scheduled drift runs, policy gates |
| driftctl | Scan cloud vs state, report unmanaged resources |
| native `terraform plan` | Free, DIY scheduling |

driftctl excels at finding **unmanaged** resources — S3 buckets created manually never in state. Complement Terraform plan, do not replace it.

## Responding to detected drift

**1. Triage the plan output.** What changed? Who changed it? Incident ticket?

**2. Choose path:**

- **Adopt change** — update `.tf`, run `terraform apply` to align state intentionally
- **Revert change** — apply to restore declared config
- **Import new resource** — if manually created resource should be managed

```bash
terraform import aws_instance.web i-0abc123
terraform plan  # should show no changes after import + matching config
```

**3. Post-incident:** if emergency console edit, add runbook step to open backport PR.

## Preventing drift culturally and technically

**IAM:** restrict prod write access; break-glass roles with audit logging.

**Policy as code:** OPA/Sentinel/Conftest deny applies that violate tags, instance sizes, public S3.

**Ignore changes for known drift:**

```hcl
resource "aws_autoscaling_group" "web" {
  desired_capacity = 3

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}
```

Use sparingly — you are telling Terraform to stop managing that attribute. Document why.

**Separate concerns:** Terraform owns base infra; HPA/Kubernetes owns pod count; never both manage same field.

## State refresh without apply

`terraform refresh` (deprecated in favor of plan refresh) updates state from real world. Modern `terraform plan` refreshes by default. If plan shows unexpected destroy/create, stop — state may need `terraform state rm` or import, not blind apply.

## Drift in multi-workspace orgs

Standardize:

- One workspace per environment per stack
- Remote state locking (S3 + DynamoDB)
- Mandatory plan on PR merge
- Daily drift scan with Slack routing to service owner

Track **mean time to reconcile drift** as an ops metric.

## Drift in GitOps and Kubernetes

Helm values changed with `kubectl edit` drift from chart defaults. Argo CD and Flux show diff between git desired state and cluster — treat that as drift even when Terraform does not manage the cluster. Align ownership: either import into Terraform/Kubernetes GitOps or block manual kubectl in prod via RBAC.

## Metrics worth dashboarding

For drift detection, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Drift response playbooks

When drift detection finds manual console changes, classify: intentional hotfix (import into Terraform state), mistaken change (revert via apply), or emergency override (document exception with expiry date). Run drift detection on schedule, not just pre-apply — drift between applies accumulates silently. Integrate with Slack alerting showing resource diff summary so on-call can triage without opening full plan output.

## Attribution and change correlation

Tag every manual console change with incident ticket ID in resource tags when possible. Drift plans without attribution waste triage time. Integrate CloudTrail or audit logs with drift alerts — show who changed the security group rule before asking Terraform to revert it.

## Resources

- [Terraform plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [driftctl (Snipcart)](https://github.com/snyk/driftctl)
- [Terraform Cloud drift detection](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/settings/drift-management)
- [Import resource documentation](https://developer.hashicorp.com/terraform/cli/import)
- [AWS Config vs Terraform drift](https://docs.aws.amazon.com/config/latest/developerguide/what-is-config.html)

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## terraform drift detection rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Field notes on terraform drift detection

IaC discipline for terraform drift detection is about state safety and blast radius. Remote state with locking, least-privilege CI roles, and plan review on every merge are non-negotiable.

For terraform drift detection:
- Workspaces or separate state per environment — never one state for prod+dev
- Modules version-pinned; avoid floating `main` tags in prod
- Drift detection on a schedule with human triage, not silent auto-apply in prod
- Policy-as-code (OPA/Sentinel) for public exposure, unencrypted disks, and open security groups

Run `plan` in CI with the same backend credentials pattern as apply, or you will ship surprises.

| Signal | Target | Alarm |
|--------|--------|-------|
| Latency p99 | Team-defined SLO | Page on burn rate |
| Error rate | Baseline − noise | Ticket if sustained |
| Cost per 1k ops | Budget cap | Weekly review |

## What reviewers should challenge in terraform drift detection PRs

Reviewers should challenge assumptions encoded in terraform drift detection: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for terraform drift detection: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for terraform drift detection: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for terraform drift detection: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Capacity planning with terraform drift detection in mind

Roll out terraform drift detection behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Caching interactions with terraform drift detection

Detail 1 (585): for terraform drift detection, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with terraform drift detection becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break terraform drift detection, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about terraform drift detection: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in terraform drift detection

Detail 2 (211): for terraform drift detection, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in terraform drift detection becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break terraform drift detection, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about terraform drift detection: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.