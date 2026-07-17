---
title: "Terraform State and Backends"
slug: "terraform-state-management-backends"
description: "Managing Terraform state: remote backends, S3 locking, state partitioning, sensitive data, import, move blocks, and recovery from state corruption."
datePublished: "2025-12-14"
dateModified: "2026-07-17"
tags: ['Terraform', 'DevOps', 'Infrastructure', 'Security']
keywords: "Terraform state management, S3 backend, DynamoDB locking, remote state, state partitioning, terraform state corruption"
faq:
  - q: "Why does Terraform need state?"
    a: "Terraform state maps resource identifiers in configuration to real cloud resource IDs, tracks metadata for dependency ordering, and records attributes needed for other resources. Without state, Terraform cannot know whether to create or update an existing resource on apply. State is the source of truth for Terraform's view of the world — distinct from but synchronized with actual infrastructure."
  - q: "What is the recommended remote backend for Terraform?"
    a: "AWS S3 with DynamoDB table for state locking is the most common open-source pattern: durable, versioned state files and mutual exclusion during apply. Terraform Cloud and HCP Terraform provide managed remote state with RBAC and run history. GCS and Azure Blob with native locking are equivalents on other clouds."
  - q: "How should you partition Terraform state?"
    a: "Split by blast radius and team ownership — separate state per environment (dev/staging/prod) and per domain (network, compute, data). Smaller states plan faster and limit damage from bad apply. Use terraform_remote_state data source or stack outputs (Terraform 1.5+ stacks) to pass references between partitions — never duplicate resource management across states."
---

Terraform state is a JSON mapping that says your RDS instance is `db-A1B2C3` and that the application security group depends on the VPC module output. Lose state, corrupt it, or let two applies run concurrently, and you spend an afternoon running `terraform import` while production waits. Remote backends with locking are table stakes; the engineering maturity shows in partitioning strategy, secrets handling, and refactoring without destroy-and-recreate.

## Why state exists and what it stores

Terraform is declarative but not clairvoyant. On apply it must decide: create new resource or update existing? State stores:

- Resource type → cloud ID (`aws_instance.web` → `i-0abc123`)
- Attributes needed for dependencies (subnet_id, arn)
- Metadata for provisioners and lifecycle rules
- Sensitive values in plaintext (passwords, keys)

State is Terraform's worldview — synchronized with reality via refresh, distinct from reality itself. **Drift** is state/reality divergence (someone changed a security group in the console). **Misconfiguration** is state/code divergence (HCL changed but not applied).

## Local state is for solo experiments only

`terraform.tfstate` on a laptop fails teams immediately:

| Problem | Consequence |
| --- | --- |
| No locking | Concurrent applies corrupt JSON |
| Not shared | Teammate recreates duplicate VPC |
| No versioning | No rollback after bad apply |
| Committed to git | Secrets leak in history |

Remote backend minimum (AWS example):

```hcl
terraform {
  backend "s3" {
    bucket         = "org-terraform-state"
    key            = "prod/network/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:eu-west-1:123456789012:key/abc-def"
  }
}
```

Enable **S3 versioning** on the bucket — previous state versions are undo when someone applies badly. Noncurrent versions transition to Glacier after 90 days for cost control while preserving ransomware recovery window.

## Locking mechanics and stuck locks

DynamoDB conditional write creates lock row per operation. Stuck lock after CI crash:

```bash
terraform force-unlock LOCK_ID
```

Only after confirming no running apply via CI logs and team channel. Force-unlock during active apply → state corruption and duplicate resources. Establish two-person rule for production force-unlock — second engineer confirms no active apply in Terraform Cloud UI.

HCP Terraform / Terraform Cloud provide managed locking and run queuing per workspace.

## Partitioning strategy by blast radius

Monolithic prod state → 45-minute plans, everyone blocked, one bad resource destroys morale.

| Split dimension | Example state key | Typical owner |
| --- | --- | --- |
| Environment | `prod/`, `staging/` | Platform |
| Domain/layer | `prod/network/`, `prod/data/` | Network / Data teams |
| Team ownership | `platform/vpc/`, `payments/rds/` | Service teams |
| Region | `prod-eu-west/`, `prod-us-east/` | Platform |

Rule: **one resource, one state file.** Never manage the same `aws_s3_bucket` from two roots.

Cross-stack references via remote state:

```hcl
data "terraform_remote_state" "network" {
  backend = "s3"
  config = {
    bucket = "org-terraform-state"
    key    = "prod/network/terraform.tfstate"
    region = "eu-west-1"
  }
}

resource "aws_instance" "app" {
  subnet_id = data.terraform_remote_state.network.outputs.private_subnet_ids[0]
}
```

Trade-off: partitioning increases coordination — network change outputs must be applied before app layer consumes new subnet IDs. Document apply order in runbooks.

## Sensitive data in state

State contains secrets in plaintext — RDS passwords, TLS private keys, bootstrap tokens. Mitigations:

- Mark outputs `sensitive = true` (hides CLI output, not state file)
- Remote state with encryption at rest (S3 SSE-KMS)
- Restrict IAM: only CI role and break-glass humans read state
- Prefer referencing Secrets Manager / SSM for runtime secrets; accept bootstrap secrets in state once

Never commit state to Git. `.gitignore` must include `*.tfstate*`.

CI drift detection uses read-only IAM role without `s3:PutObject` on state bucket — compromised drift scanner cannot corrupt state.

## Import, move, and remove workflows

**Import** existing cloud resource into state:

```bash
terraform import aws_s3_bucket.logs my-corp-logs-prod
```

Resource block must match exactly or plan shows destroy/recreate.

**Terraform 1.1+ `moved` blocks** refactor without destroy:

```hcl
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}
```

Plan shows move, not destroy+create — critical for stateful resources.

**Terraform 1.7+ `removed` block** drops resources from state without destroy:

```hcl
removed {
  from = aws_instance.legacy
  lifecycle { destroy = false }
}
```

Always `terraform state pull > backup.json` before manual state surgery.

## Recovery from corruption

1. Stop all applies
2. Restore previous state version from S3 versioning (note version ID)
3. `terraform plan` — verify alignment with reality
4. `terraform apply -refresh-only` if needed to sync attributes
5. Postmortem: root cause (concurrent apply, manual edit, force-unlock during apply)

Test state bucket restore from version ID quarterly — untested backup is wishful thinking.

## Workspace vs directory partitioning

`terraform workspace` shares same backend key prefix with workspace suffix — lightweight but easy to accidentally apply wrong workspace. Directory-based roots (`envs/prod/network`) with explicit backend keys are clearer for large orgs.

Naming convention: `{env}-{region}-{domain}` not generic `terraform.tfstate`.

## CI integration and access patterns

Pipeline holds state credentials via OIDC to AWS — no long-lived keys. Separate plan and apply roles; apply role more restricted, requires approval environment in GitHub Actions. CI role scoped to `org-terraform-state/prod/*` prefix — staging role cannot read prod state.

Log every apply: who, git SHA, workspace, resource count changed. Terraform Cloud provides run history; DIY teams ship logs to SIEM.

## State migration between backends

```bash
terraform init -migrate-state
```

Interactive migration copies local to S3. Automate in CI carefully — backup first. Backend block changes require team coordination freeze window.

## Object Lock and compliance

S3 Object Lock in governance mode prevents state deletion for retention period — protects against ransomware credential abuse deleting state bucket. Trade-off: cannot delete state until retention expires.

## Observability and size management

Alert on state file size growth, lock duration anomalies (> 30 minutes), and failed apply rate per workspace:

```bash
terraform state pull | jq '.resources | length'
```

Trending up signals resource sprawl — review whether resources belong in this state partition.

## Read-only plan role for drift detection

CI drift detection uses IAM role without `s3:PutObject` on state bucket — compromised drift scanner cannot corrupt state, only read and plan. Separate `terraform-plan-readonly` role from `terraform-apply-write` role.

## Synthesis

Remote versioned backend, DynamoDB locks, partition by blast radius, encrypt and IAM-restrict state, use `moved` blocks for refactors, import for adoption. State management is **the operational database of your infrastructure** — protect it like production data because it is.

## Disaster recovery drills for state

Quarterly restore state from S3 version to scratch workspace and run plan-only — verifies backup usability. Document RTO for state recovery in platform runbook.

Steps for drill:
1. Pick random workspace from last week's applies
2. `aws s3api list-object-versions` on state key
3. Restore to isolated bucket prefix
4. `terraform init -reconfigure` pointing at restored copy
5. `terraform plan` — expect no changes if infrastructure unchanged

## KMS grants for state access

Lambda or ECS tasks running Terraform need `kms:Decrypt` on state bucket key. Prefer KMS key alias in backend block over raw key ID.

## Force-unlock ceremony

Two-person rule for production `terraform force-unlock` — second engineer confirms no active apply in CI queue via Terraform Cloud UI screenshot in ticket.

## State file size management

Terraform 1.7+ `removed` block cleanly removes resources from state without destroy when adopting new resource address. Review quarterly whether resources belong in current state partition.

## Workspace naming convention

Use `{env}-{region}-{domain}` state key paths in S3 — `prod-eu-west-network` not generic `terraform.tfstate`. On-call finds correct state in incident without opening nearly identical keys.

## HCP Terraform run history

Managed Terraform Cloud provides run history with plan artifacts — use for audit instead of DIY S3 plan storage when org size justifies SaaS cost.

## Resources

- [Terraform backend documentation](https://developer.hashicorp.com/terraform/language/settings/backends/s3)
- [State locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [Import documentation](https://developer.hashicorp.com/terraform/cli/import)
- [Moved block](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring)
