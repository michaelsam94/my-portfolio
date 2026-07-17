---
title: "Self-Service Infrastructure"
slug: "platform-engineering-self-service-infra"
description: "Enable self-service infrastructure without chaos: Internal Developer Platforms, Terraform modules, policy guardrails, and approval workflows that scale platform teams."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags: ["Platform Engineering", "DevOps", "Infrastructure", "IDP"]
keywords: "self-service infrastructure, internal developer platform, platform engineering IDP, Terraform self service, infrastructure portal"
faq:
  - q: "What is self-service infrastructure?"
    a: "Developers provision approved infrastructure — databases, queues, namespaces, S3 buckets — through a portal or GitOps workflow without filing tickets and waiting for platform engineers. Guardrails enforce security, cost, and naming standards automatically."
  - q: "How do you prevent self-service from becoming shadow IT?"
    a: "All paths go through audited automation with policy checks — Terraform Cloud, Crossplane, or Backstage actions backed by approved modules. Nothing is created via console click. IAM scopes limit what each team can provision; tags enforce cost attribution."
  - q: "When should self-service require human approval?"
    a: "Production resources with high blast radius — public ingress, cross-account access, GPU instances, PHI storage — benefit from automated plan review plus platform approval. Dev/staging environments can be fully automated with tighter quotas."
---

Platform team's Jira queue had 200 open "need RDS instance" tickets. Median turnaround: nine days. Developers spun up Docker Postgres locally and called it staging. Self-service infrastructure doesn't eliminate platform engineers — it eliminates **ticket-driven provisioning** so platform work shifts to paved roads, policy, and reliability.

## The self-service stack

```
Developer portal (Backstage / custom UI)
        │
        ▼
Orchestration (Terraform Cloud, Crossplane, Humanitec)
        │
        ▼
Approved modules / compositions
        │
        ▼
Policy gates (OPA, Sentinel, Checkov)
        │
        ▼
Cloud API (AWS, GCP, Azure)
```

Every layer is auditable. Console access is read-only for debugging, not creation.

## Terraform module self-service

Expose curated modules via private registry:

```hcl
# Developer PR to infra-requests repo
module "checkout_db" {
  source  = "app.terraform.io/acme/postgres/aws"
  version = "~> 2.1"

  environment = "staging"
  team        = "payments"
  instance_class = "db.t4g.medium"  # constrained by module variable validation
}
```

Module enforces:
```hcl
variable "instance_class" {
  type = string
  validation {
    condition     = contains(["db.t4g.micro", "db.t4g.small", "db.t4g.medium"], var.instance_class)
    error_message = "Staging limited to t4g micro/small/medium. Request exception for larger."
  }
}
```

Terraform Cloud workspace runs plan on PR; apply on merge. No platform engineer clicks Apply.

## Crossplane for Kubernetes-native self-service

```yaml
apiVersion acme.io/v1alpha1
kind: PostgresInstance
metadata:
  name: checkout-staging
  namespace: team-payments
spec:
  size: small
  environment: staging
```

Composite Resource Definition (XRD) maps to managed resources (RDS, security groups, secrets) via Composition. Developers apply YAML in their namespace; Crossplane reconciles.

RBAC limits who can create `PostgresInstance` in which namespaces.

## Portal-driven flows

Backstage software template for infra:

1. Developer selects "PostgreSQL database"
2. Form: environment, team, size tier
3. Action opens PR in gitops-infra repo OR triggers Terraform Cloud run
4. PR auto-assigned to platform bot for policy check
5. Merge → provision → credentials in Vault → linked in catalog

Slack notification when ready. No ticket number.

## Guardrails that matter

| Risk | Guardrail |
|------|-----------|
| Cost explosion | Instance size enums, quota per team tag |
| Security | No public SG rules in module defaults |
| Sprawl | Naming convention enforced, TTL on ephemeral envs |
| Orphans | Mandatory `team` tag; weekly untagged resource report |
| Prod mistakes | Separate AWS account; prod requires approval workflow |

Policy-as-code blocks bad plans before resources exist — cheaper than cleanup.

## Approval workflows

Fully automated for dev/staging. Production adds:

```
PR opened → terraform plan comment → policy pass
    → platform approval (CODEOWNERS) → apply
```

Or risk-based: standard module + staging tested → auto-apply prod; custom sizing → human review.

Audit log: who requested, what module version, plan output, approver.

## Operating the IDP

**Product manage the portal.** If UI is confusing, developers revert to Slack asks.

**SLO the platform.** Provisioning success rate, time-to-ready, failed applies. Your customers are internal dev teams.

**Feedback loop.** Monthly office hours; track "why did you bypass self-service?" themes.

**Deprecation.** Old module versions get EOL dates; scorecard flags services on deprecated modules.

We cut infra ticket volume 70% in two quarters after self-service Postgres, S3 buckets, and K8s namespaces shipped — platform headcount didn't change; project work replaced toil.

## Cost visibility in self-service

Show estimated monthly cost in the provisioning form before submit — pulled from Infracost or internal pricing API. Engineers choose smaller instance when they see "$240/mo" next to the dropdown.

Quota enforcement per team tag prevents one enthusiastic intern from provisioning ten GPU instances via API loop bug.

## Operational notes

Provide dry-run mode in self-service portal — show Terraform plan summary without apply. Engineers learn cost and blast radius before committing. Dry-run logs feed audit trail for compliance.

Run game days where developers provision and tear down resources via self-service only — no platform Slack rescue. Game day gaps become portal UX fixes within two sprints.

Publish monthly self-service usage report to engineering leadership — provisioning volume, failure rate, top resource types — justifies platform headcount and identifies templates needing polish.

Align self-service resource TTL defaults with finance policy — ephemeral environments auto-destroy after seven days unless extended via ticket, preventing silent cost accumulation.

Self-service portals fail adoption when error messages expose raw Terraform stderr — translate failures into actionable fixes with links to docs and example PRs teams can copy.

## Self-service guardrails

Developers get:
- Terraform module catalog (VPC, RDS, S3)
- Policy-as-code limits (max instance size, allowed regions)
- Auto-generated IAM roles scoped to service

Platform team reviews module PRs, not every infra PR from 40 teams.


## Quota and rate limits per team

Self-service without quotas becomes cost incident. Enforce max RDS instances and CPU cores per team namespace in Terraform policy. Soft quota warns in Slack; hard quota blocks apply.

## GitOps request flow

Developer PR to infra-requests repo triggers terraform plan comment. Merge applies. Audit trail in Git beats console clicks.

## Environment lifecycle automation

Ephemeral preview environments TTL 72 hours — CronJob deletes orphaned namespaces without active PR. Self-service create must include expires_at label.

## Drift detection

Scheduled Terraform plan against prod detects manual console changes. Drift report to service owner with import or destroy choices.

## Crossplane vs Terraform Cloud choice

Terraform Cloud excels when modules mature and state management is central pain. Crossplane fits Kubernetes-native teams wanting CRD-based claims (`PostgresClaim`) reconciled continuously. Hybrid common: Crossplane for K8s-adjacent, TFC for VPC and IAM — document boundary so developers know which portal to open.

## Cost anomaly detection on self-service tags

Tag every provisioned resource with `team`, `cost-center`, `created-by-scaffolder:true`. AWS Cost Anomaly Detection on team dimension — alert when staging RDS left on db.r6g.2xlarge after demo. Self-service without cost feedback repeats orphan resource story.

## Break-glass procedures

When Terraform state lock stuck or Crossplane claim wedged, documented break-glass: who can force-unlock, who approves, max duration before audit review. Self-service without break-glass leads to platform engineers becoming human unlock buttons; with break-glass, audit trail preserves accountability.

## Multi-cloud module interfaces

Abstract variables: `database_class`, `backup_retention_days`, `network_isolation_level`. AWS module maps to RDS; GCP to Cloud SQL — developer portal shows same form. Divergence in capability (read replica lag monitoring) documented in template output README, not hidden until deploy fails.

## Audit trail retention

CloudTrail plus Terraform Cloud run logs retained seven years for SOC2 — self-service apply events include actor GitHub username, module version, and resource ARNs created. Auditor asks who provisioned public S3 bucket — git blame on infra-requests PR answers in minutes.

## Self-service database provisioning tiers

Dev: auto Postgres small instance, destroy after 7 days. Staging: auto with backup disabled, max 100GB. Prod: plan-only in PR, apply after DBA approval annotation on PR. Developer sees same form; policy engine branches on environment field — reduces prod ticket volume without blocking dev velocity.

## Closing notes

Terraform plan output attached to every self-service PR gives reviewers diff without console access — transparency replaces tribal knowledge about what will change in AWS.

## Additional guidance

Policy-as-code rejects public S3 ACLs and missing encryption at plan time — developer sees Terraform error in PR comment, not audit finding weeks later. Guardrails encode compromise between speed and compliance; exceptions require ticket linked in PR description for auditor sampling.

Run game day deleting random Terraform-managed resource in staging — verify self-service recreate path works and drift detection alerts — quarterly exercise prevents discovered broken recreate workflow during real prod incident when someone manually deleted RDS thinking clone.

Publish monthly self-service usage report: resources created, average time-to-provision, top modules — proves platform ROI to finance.

Measure median minutes from merged infra PR to resource ready — SLO under fifteen minutes for dev databases keeps developers choosing self-service over local docker postgres calling it staging.

## Resources

- [Backstage documentation](https://backstage.io/docs/overview/what-is-backstage)
- [Crossplane concepts guide](https://docs.crossplane.io/latest/concepts/)
- [Terraform Cloud run triggers](https://developer.hashicorp.com/terraform/cloud-docs/run/run-triggers)
- [Humanitec platform orchestration](https://developer.humanitec.com/)
- [CNCF IDP whitepaper](https://tag-app-delivery.cncf.io/whitepapers/platforms/)
