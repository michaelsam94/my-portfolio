# Part 4: terraform posts

POSTS["terraform-drift-detection"] = {
    "meta": {
        "title": "Detecting Infrastructure Drift",
        "description": "Detecting and managing Terraform drift: plan in CI, drift detection tools, manual console changes, import workflows, and policies that keep state aligned with reality.",
        "datePublished": "2025-12-06",
        "tags": ["Terraform", "DevOps", "Infrastructure", "CI/CD"],
        "keywords": "Terraform drift detection, infrastructure drift, terraform plan CI, Spacelift drift, manual console changes, state reconciliation",
        "faq": [
            {
                "q": "What is infrastructure drift?",
                "a": "Drift occurs when real infrastructure differs from what Terraform state and configuration declare — usually because someone changed resources manually in the AWS console, a vendor auto-updated settings, or state was corrupted. The next terraform apply may unexpectedly revert manual fixes or fail because state no longer matches reality.",
            },
            {
                "q": "How do you detect Terraform drift automatically?",
                "a": "Run terraform plan on a schedule (daily or hourly) in read-only mode against each workspace. Non-empty plans indicate drift. Tools like Spacelift, env0, Terraform Cloud, and driftctl automate scheduled plans and alert on changes. CI pipelines should also plan on every PR that touches .tf files.",
            },
            {
                "q": "Should you revert drift or update Terraform code?",
                "a": "If the manual change was intentional and correct, codify it in .tf and refresh state. If it was accidental or non-compliant, apply Terraform to revert. Never ignore drift — silent divergence accumulates until apply causes outage. Document emergency console changes and backport to code within SLA (e.g., 24 hours).",
            },
        ],
    },
    "body": r'''
During a database incident someone scaled RDS from `db.t3.medium` to `db.r6g.xlarge` in the AWS console. Traffic recovered. Three days later a routine `terraform apply` on an unrelated change downsized the instance back — during peak business hours. Nobody had updated the `.tf` files or refreshed state. That afternoon we implemented scheduled drift detection and a rule: emergency console changes are allowed, but the PR that codifies or reverts them must merge before the incident ticket closes.

Drift is not a moral failure — it is an inevitable consequence of giving humans both Terraform and click-ops access. The goal is not eternal zero drift; it is **detect fast, decide intentionally, reconcile state and code before the next apply surprises production**.

## What drift actually is

Terraform `plan` compares three views:

1. **Configuration** — your `.tf` files (desired)
2. **State** — `terraform.tfstate` (Terraform's belief about reality)
3. **Real infrastructure** — provider API responses (actual)

Drift appears when any pair diverges. Common causes:

- Emergency manual scaling, security group edits, tag changes in console
- Autoscaling groups changing desired count outside Terraform
- Cloud vendor default settings applied post-create (encryption, versioning)
- Multiple tools managing one resource (Terraform + Helm hooks + console)
- Failed `import` leaving state incomplete
- State corruption or stale workspace on someone's laptop

Drift is silent until apply. The plan output is your early warning system.

## Minimum viable detection: scheduled read-only plan

```yaml
# GitHub Actions — daily drift scan
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

jobs:
  drift-prod-network:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init -backend-config=backends/prod-network.hcl
      - run: terraform plan -detailed-exitcode -no-color -lock=false
        id: plan
        continue-on-error: true
      - name: Notify on drift
        if: steps.plan.outputs.exitcode == '2'
        run: |
          ./scripts/post-slack.sh "#infra" "Drift in prod-network — see plan artifact"
```

Exit codes: `0` = no changes, `2` = changes present (drift or pending work), `1` = error. Use IAM role with **read-only** plan permissions — automation must not apply accidentally.

Run per workspace/state partition, not one monolithic root module. Smaller blast radius, faster plans, clearer ownership.

## CI plan on every infrastructure PR

PR pipeline:

```
terraform fmt -check
terraform validate
tflint / checkov (policy)
terraform plan -out=plan.binary
terraform show -json plan.binary > plan.json  # policy as code input
```

Post plan summary as PR comment. Block merge on unexpected destroys. Drift detection in CI catches intentional code changes; scheduled plan catches console changes nobody committed.

## Tooling landscape

| Tool | Strength |
| --- | --- |
| `terraform plan` (native) | Authoritative desired vs actual for managed resources |
| Terraform Cloud / HCP | Continuous speculative plans, drift notifications |
| Spacelift / env0 | Scheduled drift runs, policy gates, audit trail |
| driftctl | Finds **unmanaged** cloud resources absent from state |
| AWS Config / CloudTrail | Who changed what, when — complements plan |

driftctl answers "what exists in AWS but not in state?" — S3 buckets created manually, stray security groups. Terraform plan answers "what does state think vs reality for resources we manage?" Use both; they are complementary.

## Triage workflow when drift fires

**Step 1 — Identify the diff.** Resource type, attribute, old vs new value. Cross-reference CloudTrail for actor and ticket.

**Step 2 — Classify intent:**

- **Intentional emergency fix** — codify in `.tf`, open PR, apply to align declaratively
- **Accidental or non-compliant** — revert via `terraform apply` to declared config
- **New unmanaged resource** — `terraform import` + matching `.tf` block
- **Vendor-side change** — decide adopt (update code) or revert (apply)

**Step 3 — Reconcile before next unrelated apply.** Drift left idle becomes outage roulette.

```bash
# Import manually created instance
terraform import aws_instance.web i-0abc123def456
terraform plan   # should converge after matching resource block added
```

## Preventing drift culturally and technically

**Culture:** incident runbooks include "backport infra changes within 24h." Console access is break-glass, logged, time-limited IAM roles.

**Technical guardrails:**

- Deny broad console write via IAM for production accounts (exceptions via approval workflow)
- Service Control Policies blocking public S3 ACLs regardless of console
- Auto-remediation Lambda for known drift patterns (re-enable S3 versioning) — use cautiously
- Separate state per domain so one team's console experiment does not block all infra

## Drift vs pending changes

Scheduled plan shows drift AND legitimate unapplied commits. Track baseline: compare plan against last successful apply git SHA. Tools like Terraform Cloud associate runs with VCS revision; drift-only alerts trigger when plan differs with clean main branch.

## State refresh without apply

`terraform apply -refresh-only` updates state from real infrastructure without changing resources — useful after manual changes while writing the codifying PR. Does not replace updating `.tf`.

## Measuring program health

Metrics: `drift_detected_count` per workspace, `mean_time_to_reconcile_hours`, `unmanaged_resource_count` from driftctl. Executive summary: "prod had 3 drift events this month, MTTR 4 hours."

## When apply causes damage

If drift detection was ignored and apply reverted a critical manual scale-up, rollback via:

1. Re-apply manual fix (fastest)
2. `terraform state` operations + targeted apply
3. Restore state version from S3 versioning (last resort)

Practice game-day: inject drift in staging, verify detection and runbook.

## Synthesis

Scheduled read-only plan per workspace, PR plans, driftctl for unmanaged resources, triage classify adopt/revert/import, cultural backport SLA. Drift management is **continuous reconciliation discipline** — Terraform is only truthful when reality, state, and code agree.
''',
}

POSTS["terraform-modules-composition"] = {
    "meta": {
        "title": "Composable Terraform Modules",
        "description": "Build reusable Terraform modules with clear interfaces, composition patterns, and versioning so infrastructure code scales across teams without copy-paste.",
        "datePublished": "2025-12-10",
        "tags": ["Terraform", "Infrastructure", "DevOps", "Modules"],
        "keywords": "Terraform modules, composable infrastructure, module composition patterns, Terraform module versioning, reusable IaC, Terraform registry",
        "faq": [
            {
                "q": "When should I create a Terraform module vs inline resources?",
                "a": "Create a module when you'll instantiate the same pattern more than twice — a VPC setup, an ECS service, a standard S3 bucket with encryption and logging. Keep one-off resources inline. Over-modularizing (a module for a single security group rule) adds indirection without reuse benefit. The test: would another team or environment use this exact combination of resources?",
            },
            {
                "q": "How do I version Terraform modules?",
                "a": "Tag module repositories with semantic versions (v1.2.0). Consumers pin to a version: source = 'git::https://github.com/org/terraform-modules/vpc?ref=v1.2.0'. Never point production at main/master — a breaking change in the module repo shouldn't break production on the next plan. Use the Terraform Registry for public modules; private registries (Terraform Cloud, Artifactory) for internal modules.",
            },
            {
                "q": "What belongs in a module's interface?",
                "a": "Inputs: the minimum variables needed to customize behavior (name, environment, CIDR range, instance type). Outputs: everything downstream modules or root modules need (VPC ID, subnet IDs, security group IDs). Hide internal implementation details — consumers shouldn't need to know how many subnets the VPC module creates, just the subnet IDs they can pass to an EC2 module.",
            },
        ],
    },
    "body": r'''
Four teams copied the same 200-line VPC configuration into their repos. Within six months they diverged: Team A added VPC flow logs; Team B used wrong CIDR sizing; Team C shipped a security group bug the others avoided; Team D never upgraded provider constraints. Module extraction took one week; alignment took one `terraform plan` cycle. One `module "vpc"` call replaced four forks of truth.

Terraform modules are reusable infrastructure packages. Good modules have tight interfaces, tested defaults, semantic versioning, and compose cleanly. Bad modules are 400-line copy-paste blocks with forty undocumented variables and a README that says "see main.tf."

## Anatomy of a maintainable module

```
modules/vpc/
  main.tf        # Resources
  variables.tf   # Inputs with descriptions, types, validation
  outputs.tf     # Contract surface for consumers
  versions.tf    # terraform and provider version constraints
  README.md      # Examples, input/output tables (terraform-docs)
  tests/         # terraform test files
```

**Single responsibility:** a VPC module creates VPC, subnets, route tables, NAT, flow logs. It does not also deploy ECS clusters. An `ecs-service` module **consumes** VPC outputs.

## Interface design: minimum viable surface

Expose only what callers must customize:

```hcl
variable "name" {
  description = "Prefix for resource names"
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of AZs (2-4)"
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 4
    error_message = "Use 2-4 AZs for HA."
  }
}
```

Every variable gets `description`, `type`, sensible `default`, and `validation` where constraints exist. Catch misconfig at plan time, not when NAT gateway billing surprises finance.

Outputs export what downstream modules need — nothing more:

```hcl
output "vpc_id" { value = aws_vpc.this.id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
```

Internal resources (`aws_route_table_association.private[2]`) stay private.

## Composition at the root module

Root modules wire environment-specific values and orchestrate child modules:

```hcl
module "vpc" {
  source     = "git::https://github.com/org/terraform-modules.git//vpc?ref=v2.1.0"
  name       = "production"
  cidr_block = "10.1.0.0/16"
  az_count   = 3
}

module "api_service" {
  source       = "git::https://github.com/org/terraform-modules.git//ecs-service?ref=v1.4.0"
  name         = "api"
  vpc_id       = module.vpc.vpc_id
  subnet_ids   = module.vpc.private_subnet_ids
  cluster_arn  = module.ecs_cluster.arn
}
```

Data flows through outputs → inputs. No remote state reads between sibling modules in the same root — keeps plans atomic.

## Versioning and consumer pinning

Tag modules with semver. Consumers **pin**:

```hcl
source = "git::https://github.com/org/terraform-modules.git//vpc?ref=v2.1.0"
```

Never `ref=main` in production. Breaking changes bump major version; document in CHANGELOG.

Private Terraform Registry or Terragrunt catalog centralizes discovery. Teams search "vpc" and get blessed module with scorecard (Checkov pass rate, adoption count).

## Wrapping upstream modules

The public Terraform AWS VPC module is excellent — wrap it to enforce org defaults:

```hcl
module "upstream_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.1"
  # org-mandated: flow logs on, single NAT for non-prod
  enable_flow_log = true
  ...
}
```

Your wrapper adds tagging standards, naming conventions, and policy-compliant defaults without forking upstream.

## When NOT to module

- One-off migration resources
- Single security group rule unique to one app
- Prototypes exploring provider behavior

The test: **will another team instantiate this exact pattern twice?** If no, inline until pattern stabilizes.

## Testing modules

Terraform 1.6+ native tests in `tests/*.tftest.hcl`:

```hcl
run "private_subnets_per_az" {
  command = plan
  variables { name = "test", az_count = 3 }
  assert {
    condition     = length(var.az_count) == 3
    error_message = "Expect subnet count to match az_count"
  }
}
```

Run in CI on module repo before tagging release.

## Documentation generation

`terraform-docs` generates input/output tables from variable blocks — README stays synchronized. Include copy-paste example in README, not "see variables.tf."

## Anti-patterns that rot module libraries

- **Kitchen-sink modules** — `application-stack` module doing VPC + RDS + ECS + CloudFront; impossible to upgrade piecemeal
- **Leaky abstractions** — exposing raw `map(any)` passthrough for all provider arguments
- **Hidden dependencies** — module creates IAM roles with hardcoded names colliding across environments
- **Unpinned providers** inside modules confusing consumers' provider resolution

## Terragrunt and DRY environments

Terragrunt wraps Terraform for DRY backend config and provider generation:

```hcl
terraform {
  source = "git::...//vpc?ref=v2.1.0"
}
inputs = {
  name       = "staging"
  cidr_block = "10.2.0.0/16"
}
```

Generate `backend.hcl` and `provider.tf` from parent `terragrunt.hcl` — environments differ only in inputs.

## Synthesis

Module when pattern repeats; minimal validated interface; semver pin; compose via outputs; test before tag; wrap upstream for org defaults. Modules are **APIs for infrastructure** — design them with the same rigor as public library contracts.
''',
}

POSTS["terraform-state-management-backends"] = {
    "meta": {
        "title": "Terraform State and Backends",
        "description": "Managing Terraform state: remote backends, S3 locking, state partitioning, sensitive data, import, move blocks, and recovery from state corruption.",
        "datePublished": "2025-12-14",
        "tags": ["Terraform", "DevOps", "Infrastructure", "Security"],
        "keywords": "Terraform state management, S3 backend, DynamoDB locking, remote state, state partitioning, terraform state corruption",
        "faq": [
            {
                "q": "Why does Terraform need state?",
                "a": "Terraform state maps resource identifiers in configuration to real cloud resource IDs, tracks metadata for dependency ordering, and records attributes needed for other resources. Without state, Terraform cannot know whether to create or update an existing resource on apply. State is the source of truth for Terraform's view of the world — distinct from but synchronized with actual infrastructure.",
            },
            {
                "q": "What is the recommended remote backend for Terraform?",
                "a": "AWS S3 with DynamoDB table for state locking is the most common open-source pattern: durable, versioned state files and mutual exclusion during apply. Terraform Cloud and HCP Terraform provide managed remote state with RBAC and run history. GCS and Azure Blob with native locking are equivalents on other clouds.",
            },
            {
                "q": "How should you partition Terraform state?",
                "a": "Split by blast radius and team ownership — separate state per environment (dev/staging/prod) and per domain (network, compute, data). Smaller states plan faster and limit damage from bad apply. Use terraform_remote_state data source or stack outputs (Terraform 1.5+ stacks) to pass references between partitions — never duplicate resource management across states.",
            },
        ],
    },
    "body": r'''
Terraform state is a JSON mapping that says your RDS instance is `db-A1B2C3` and that the application security group depends on the VPC module output. Lose state, corrupt it, or let two applies run concurrently, and you spend an afternoon running `terraform import` while production waits. Remote backends with locking are table stakes; the engineering maturity shows in partitioning strategy, secrets handling, and refactoring without destroy-and-recreate.

## Why state exists

Terraform is declarative but not clairvoyant. On apply it must decide: create new resource or update existing? State stores:

- Resource type → cloud ID (`aws_instance.web` → `i-0abc123`)
- Attributes needed for dependencies (subnet_id, arn)
- Metadata for provisioners and lifecycle

State is Terraform's worldview — synchronized with reality via refresh, distinct from reality itself. Drift is state/reality divergence; misconfiguration is state/code divergence.

## Local state is for solo experiments only

`terraform.tfstate` on a laptop fails teams immediately:

- No locking → concurrent applies corrupt JSON
- Not shared → teammate recreates duplicate VPC
- No versioning → no rollback

Remote backend minimum (AWS example):

```hcl
terraform {
  backend "s3" {
    bucket         = "org-terraform-state"
    key            = "prod/network/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

Enable **S3 versioning** on the bucket — previous state versions are undo when someone applies badly.

## Locking mechanics

DynamoDB conditional write creates lock row per operation. Stuck lock after CI crash:

```bash
terraform force-unlock LOCK_ID
```

Only after confirming no running apply via CI logs and team channel. Force-unlock during active apply → state corruption and duplicate resources.

HCP Terraform / Terraform Cloud provide managed locking and run queuing per workspace.

## Partitioning strategy

Monolithic prod state → 45-minute plans, everyone blocked, one bad resource destroys morale.

| Split dimension | Example state key |
| --- | --- |
| Environment | `prod/`, `staging/` |
| Domain/layer | `prod/network/`, `prod/data/`, `prod/apps/` |
| Team ownership | `platform/vpc/`, `payments/rds/` |

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

Terraform 1.5+ `terraform stack` and HCP Stacks evolve this — explicit outputs, no duplicated resources.

Trade-off: partitioning increases coordination — network change outputs must be applied before app layer consumes new subnet IDs.

## Sensitive data in state

State contains secrets in plaintext — RDS passwords, TLS private keys, initial bootstrap tokens. Mitigations:

- Mark outputs `sensitive = true` (hides CLI, not state file)
- Use remote state with encryption at rest (S3 SSE-KMS)
- Restrict IAM: only CI role and break-glass humans read state
- Prefer referencing Secrets Manager / SSM for runtime secrets; accept bootstrap secrets in state once

Never commit state to Git. `.gitignore` `*.tfstate*`.

## Import, remove, and move workflows

**Import** existing cloud resource into state:

```bash
terraform import aws_s3_bucket.logs my-corp-logs-prod
```

Match resource block exactly or plan shows destroy/recreate.

**Terraform 1.1+ `moved` blocks** refactor without destroy:

```hcl
moved {
  from = aws_instance.web
  to   = module.compute.aws_instance.web
}
```

Plan shows move, not destroy+create — critical for stateful resources.

**`terraform state rm`** when resource should leave Terraform management but stay in cloud — dangerous; document why.

## Recovery from corruption

1. Stop all applies
2. Restore previous state version from S3 versioning
3. `terraform plan` — verify alignment with reality
4. `terraform apply -refresh-only` if needed
5. Postmortem: how did corruption happen?

Backup state before manual `state pull/push` operations.

## Workspace vs directory partitioning

`terraform workspace` shares same backend key prefix with workspace suffix — lightweight but easy to accidentally apply wrong workspace. Directory-based roots (`envs/prod/network`) with explicit backend keys are clearer for large orgs.

## CI integration

Pipeline holds state credentials via OIDC to AWS — no long-lived keys. Separate plan and apply roles; apply role more restricted, requires approval environment in GitHub Actions.

State locking timeout in CI — set reasonable `lock_timeout` for queued jobs.

## Observability

Log every apply: who, git SHA, workspace, resource count changed. Terraform Cloud provides run history; DIY teams ship logs to SIEM.

Alert on state file size growth (symptom of unmanaged `count` explosion) and lock duration anomalies.

## Synthesis

Remote versioned backend, DynamoDB locks, partition by blast radius, encrypt and IAM-restrict state, use `moved` blocks for refactors, import for adoption. State management is **the operational database of your infrastructure** — protect it like production data because it is.
''',
}

POSTS["terraform-testing-policy-as-code"] = {
    "meta": {
        "title": "Testing Terraform with Policy as Code",
        "description": "Testing Terraform with policy as code: unit tests with terraform test, OPA/Conftest and Sentinel guardrails, and how to layer validation so bad infra never ships.",
        "datePublished": "2026-05-09",
        "tags": ["DevOps", "Infrastructure as Code", "Testing"],
        "keywords": "Terraform testing, policy as code, OPA, Sentinel, terraform test, Conftest, IaC validation",
        "faq": [
            {
                "q": "What is policy as code for Terraform?",
                "a": "Policy as code means expressing your infrastructure rules — like 'no public S3 buckets' or 'every resource must be tagged with a cost center' — as machine-evaluable code rather than wiki guidelines. Tools like Open Policy Agent (Conftest) or HashiCorp Sentinel evaluate a Terraform plan against these policies and fail the pipeline if any rule is violated, enforcing standards automatically.",
            },
            {
                "q": "How is terraform test different from policy as code?",
                "a": "They test different things. The native 'terraform test' framework verifies your module behaves correctly — given these inputs, does it produce the expected resources and outputs. Policy as code verifies the resulting infrastructure meets organizational rules like security and tagging. You want both: correctness tests for the module author, policy checks for the whole org.",
            },
            {
                "q": "Where in the pipeline should policy checks run?",
                "a": "Run them against the plan output, after 'terraform plan' and before 'terraform apply', in CI on every pull request. Evaluating the plan JSON lets you catch violations before anything is provisioned. For defense in depth, many teams also enforce policies at the state or cloud level, but the PR gate is the fastest, cheapest feedback.",
            },
        ],
    },
    "body": r'''
One mistyped `acl = "public-read"` in a module default can expose every new S3 bucket across four environments before a human notices in review. Infrastructure as code magnifies mistakes at machine speed. Testing Terraform requires two layers most teams conflate: **module correctness** (does this code build what the author intended?) and **organizational compliance** (is what it builds allowed?). Native `terraform test` handles the first; policy as code (OPA/Conftest, Sentinel, Checkov) handles the second. Wire both into CI between `plan` and `apply`.

## Layer 1: module correctness with terraform test

Since Terraform 1.6, `.tftest.hcl` files run modules with assertions:

```hcl
# tests/private_bucket.tftest.hcl
run "blocks_public_access" {
  command = plan

  variables {
    name        = "assets"
    environment = "prod"
  }

  assert {
    condition     = aws_s3_bucket.this.bucket == "assets-prod"
    error_message = "Bucket name must include environment suffix"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.this.block_public_acls == true
    error_message = "Public ACLs must be blocked"
  }
}
```

`command = plan` — fast, no cloud cost, catches logic and naming. Reserve `command = apply` for integration tests in ephemeral accounts verifying behavior plan cannot see (actual IAM propagation, connectivity checks).

Run `terraform test` in module repo CI before tagging releases. Module authors own these tests like unit tests in application code.

## Layer 2: policy as code on plan JSON

Module tests prove **your** module works. They do not stop a developer from writing correct HCL that provisions forbidden resources — public RDS, `t2.micro` in prod, missing `cost_center` tag.

Export plan to JSON:

```bash
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
```

Evaluate with Conftest (OPA/Rego):

```rego
package terraform.s3

import rego.v1

deny contains msg if {
    some resource in input.resource_changes
    resource.type == "aws_s3_bucket_public_access_block"
    resource.change.after.block_public_acls == false
    msg := sprintf("S3 public ACLs blocked required: %s", [resource.address])
}

deny contains msg if {
    some resource in input.resource_changes
    resource.type == "aws_instance"
    resource.change.after.instance_type == "t2.micro"
    msg := sprintf("t2.micro not allowed in prod: %s", [resource.address])
}
```

```bash
conftest test tfplan.json --policy policies/
```

Fail CI on non-zero exit. Policies live in central repo — security team owns Rego, app teams consume gate.

## Alternative policy engines

| Tool | When to use |
| --- | --- |
| Conftest/OPA | Open source, multi-cloud, works on K8s manifests too |
| HashiCorp Sentinel | Native HCP Terraform / Enterprise policy sets |
| Checkov / tfsec | Static analysis on `.tf` before plan — catches issues earlier |
| Cloud SCPs | AWS Organizations guardrails — last line of defense |

Defense in depth: Checkov on PR → plan → Conftest on plan JSON → SCP prevents apply even if CI bypassed.

## Pipeline placement

```
PR opened
  → terraform fmt -check
  → terraform validate
  → checkov -d .                    # static
  → terraform plan -out=plan.bin
  → terraform show -json > plan.json
  → conftest test plan.json         # policy
  → terraform test                  # module tests (module repos)
  → post plan summary to PR
Merge → apply with approval gate
```

Policy on **plan output** catches resources about to change, including destroys and replacements. Static analysis alone misses computed values resolved only at plan.

## Testing destructive changes

Policies can require explicit approval for `delete` actions:

```rego
deny contains msg if {
    some resource in input.resource_changes
    resource.change.actions[_] == "delete"
    not input.metadata.labels["approved_destroy"]
    msg := sprintf("Destroy requires security approval: %s", [resource.address])
}
```

Or use Sentinel/OPA in Terraform Cloud run tasks to block applies with destroys in production workspaces.

## Ephemeral environments for apply tests

For integration confidence, spin ephemeral env per PR:

```bash
terraform workspace new pr-1234
terraform apply -auto-approve
terraform test -filter=tests/integration/*.tftest.hcl
terraform destroy -auto-approve
```

Cost-controlled with TTL and small instance sizes. Catch provider behavior plan mocks miss.

## Policy authoring workflow

1. Incident or audit finding → encode as failing test against historical bad plan JSON
2. Add Rego rule
3. Fix existing infra or grandfather with exception tag
4. Enable enforce mode

Grandfather pattern:

```rego
deny contains msg if {
    ...
    not resource.change.after.tags["policy_exception"]
}
```

Exceptions expire — review quarterly.

## Developer experience

Fast feedback: static analysis and plan-level tests complete in under two minutes. Slow integration nightly. Clear error messages — "S3 bucket `module.foo.aws_s3_bucket.x` must set `block_public_acls=true`" not "policy violation line 0."

## Measuring effectiveness

Track: policy violations caught pre-apply, bypass count, mean time to add policy after incident. Goal: incidents from misconfig trend down while PR velocity stays flat.

## Synthesis

`terraform test` for module contracts; Conftest/Sentinel on plan JSON for org rules; static analysis upstream; SCPs downstream. The pipeline between plan and apply is where **infrastructure governance becomes enforceable** — not wiki guidance, but code that blocks the merge.
''',
}
