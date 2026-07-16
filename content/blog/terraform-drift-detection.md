---
title: "Detecting Infrastructure Drift"
slug: "terraform-drift-detection"
description: "Detecting and managing Terraform drift: plan in CI, drift detection tools, manual console changes, import workflows, and policies that keep state aligned with reality."
datePublished: "2025-12-06"
dateModified: "2025-12-06"
tags: ["Terraform", "DevOps", "Infrastructure", "CI/CD"]
keywords: "Terraform drift detection, infrastructure drift, terraform plan CI, Spacelift drift, manual console changes, state reconciliation"
faq:
  - q: "What is infrastructure drift?"
    a: "Drift occurs when real infrastructure differs from what Terraform state and configuration declare — usually because someone changed resources manually in the AWS console, a vendor auto-updated settings, or state was corrupted. The next terraform apply may unexpectedly revert manual fixes or fail because state no longer matches reality."
  - q: "How do you detect Terraform drift automatically?"
    a: "Run terraform plan on a schedule (daily or hourly) in read-only mode against each workspace. Non-empty plans indicate drift. Tools like Spacelift, env0, Terraform Cloud, and driftctl automate scheduled plans and alert on changes. CI pipelines should also plan on every PR that touches .tf files."
  - q: "Should you revert drift or update Terraform code?"
    a: "If the manual change was intentional and correct, codify it in .tf and refresh state. If it was accidental or non-compliant, apply Terraform to revert. Never ignore drift — silent divergence accumulates until apply causes outage. Document emergency console changes and backport to code within SLA (e.g., 24 hours)."
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

## Common production mistakes

Teams get drift detection wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Terraform patterns for drift detection rot when emergency console edits never get codified, `ignore_changes` blocks multiply without documentation, and drift detection runs monthly instead of daily on production workspaces.

## Debugging and triage workflow

When drift detection misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Metrics worth dashboarding

For drift detection, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Resources

- [Terraform plan command](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [driftctl (Snipcart)](https://github.com/snyk/driftctl)
- [Terraform Cloud drift detection](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/settings/drift-management)
- [Import resource documentation](https://developer.hashicorp.com/terraform/cli/import)
- [AWS Config vs Terraform drift](https://docs.aws.amazon.com/config/latest/developerguide/what-is-config.html)
