---
title: "Composable Terraform Modules"
slug: "terraform-modules-composition"
description: "Build reusable Terraform modules with clear interfaces, composition patterns, and versioning so infrastructure code scales across teams without copy-paste."
datePublished: "2025-12-10"
dateModified: "2026-07-17"
tags: ['Terraform', 'Infrastructure', 'DevOps', 'Modules']
keywords: "Terraform modules, composable infrastructure, module composition patterns, Terraform module versioning, reusable IaC, Terraform registry"
faq:
  - q: "When should I create a Terraform module vs inline resources?"
    a: "Create a module when you'll instantiate the same pattern more than twice — a VPC setup, an ECS service, a standard S3 bucket with encryption and logging. Keep one-off resources inline. Over-modularizing (a module for a single security group rule) adds indirection without reuse benefit. The test: would another team or environment use this exact combination of resources?"
  - q: "How do I version Terraform modules?"
    a: "Tag module repositories with semantic versions (v1.2.0). Consumers pin to a version: source = 'git::https://github.com/org/terraform-modules/vpc?ref=v1.2.0'. Never point production at main/master — a breaking change in the module repo shouldn't break production on the next plan. Use the Terraform Registry for public modules; private registries (Terraform Cloud, Artifactory) for internal modules."
  - q: "What belongs in a module's interface?"
    a: "Inputs: the minimum variables needed to customize behavior (name, environment, CIDR range, instance type). Outputs: everything downstream modules or root modules need (VPC ID, subnet IDs, security group IDs). Hide internal implementation details — consumers shouldn't need to know how many subnets the VPC module creates, just the subnet IDs they can pass to an EC2 module."
faqAnswers:
  - question: "When is terraform modules composition the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for terraform modules composition?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back terraform modules composition safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Four teams copied the same 200-line VPC configuration into their repos. Within six months they diverged: Team A added VPC flow logs; Team B used wrong CIDR sizing; Team C shipped a security group bug the others avoided; Team D never upgraded provider constraints. Module extraction took one week; alignment took one `terraform plan` cycle. One `module "vpc"` call replaced four forks of truth.

Terraform modules are reusable infrastructure packages. Good modules have tight interfaces, tested defaults, semantic versioning, and compose cleanly. Bad modules are 400-line copy-paste blocks with forty undocumented variables and a README that says "see main.tf."

## Module anatomy and repository layout

```
modules/vpc/
  main.tf        # Resources
  variables.tf   # Inputs with descriptions, types, validation
  outputs.tf     # Contract surface for consumers
  versions.tf    # terraform and provider version constraints
  README.md      # Examples, input/output tables (terraform-docs)
  examples/complete/
  tests/vpc.tftest.hcl
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
    error_message = "Use 2-4 AZs for HA; standard prod uses 3."
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

Internal resources stay private. Removing an output is a breaking change requiring major version bump.

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
  source      = "git::https://github.com/org/terraform-modules.git//ecs-service?ref=v1.4.0"
  name        = "api"
  vpc_id      = module.vpc.vpc_id
  subnet_ids  = module.vpc.private_subnet_ids
  cluster_arn = module.ecs_cluster.arn
}
```

Data flows through outputs → inputs. No remote state reads between sibling modules in the same root — keeps plans atomic and dependency graph explicit in one `terraform graph`.

## Versioning, pinning, and upgrade cadence

Tag modules with semver. Consumers **pin**:

```hcl
source = "git::https://github.com/org/terraform-modules.git//vpc?ref=v2.1.0"
```

Never `ref=main` in production. Breaking changes bump major version; document in CHANGELOG.md with migration steps.

| Version bump | When | Example |
| --- | --- | --- |
| Major | Removed/changed output | `private_subnet_ids` split into two outputs |
| Minor | New optional variable | `enable_ipv6 = false` default |
| Patch | Bug fix | Fix NAT route association |

Establish Renovate/Dependabot for module version bumps in consumer repos. Weekly PR with plan diff attached. Major version bumps require platform team office hours.

## Wrapping upstream modules

The public Terraform AWS VPC module is excellent — wrap it to enforce org defaults:

```hcl
module "upstream_vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.1"
  enable_flow_log    = true  # org-mandated
  enable_nat_gateway = true
}
```

Your wrapper adds tagging standards, naming conventions, and policy-compliant defaults without forking upstream. Upgrade upstream minor versions in wrapper; consumers pin wrapper version.

## for_each vs count: stable resource addressing

`count` shifts indices when list order changes — destroys wrong resources:

```hcl
resource "aws_subnet" "private" {
  for_each = { for s in var.subnets : s.name => s }
  cidr_block = each.value.cidr
}
```

Document in module README — consumers learn after painful RDS recreation if you do not warn explicitly.

## Provider alias patterns for multi-region

Multi-region modules pass provider aliases explicitly:

```hcl
module "replica_bucket" {
  source = "./s3-replica"
  providers = { aws.replica = aws.west }
}
```

Module README lists required provider configurations — implicit defaults cause cryptic plan errors in consumer roots.

## Testing modules before release

Terraform 1.6+ native tests in `tests/*.tftest.hcl`:

```hcl
run "subnet_count_matches_az" {
  command = plan
  variables { name = "test", az_count = 3 }
  assert {
    condition     = length(aws_subnet.private) == 3
    error_message = "Expected one private subnet per AZ"
  }
}
```

Run `terraform test` in module repo CI before tagging release. `examples/complete/` runs `terraform init -backend=false`, `validate`, and `test` on every PR.

## Terragrunt for DRY environment config

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

Parent `terragrunt.hcl` generates `backend.hcl` and `provider.tf` — environments differ only in inputs.

## Anti-patterns that rot module libraries

| Anti-pattern | Why it hurts | Fix |
| --- | --- | --- |
| Kitchen-sink module | VPC + RDS + ECS in one module | Split by domain |
| Leaky `map(any)` passthrough | Consumers bypass defaults | Explicit variables |
| Hidden IAM role names | Collisions across environments | Prefix with `var.name` |
| Unpinned providers in module | Consumer resolution breaks | Pin in `versions.tf` |

## terraform-docs and README discipline

`terraform-docs` generates input/output tables from variable blocks — README stays synchronized with code. Module PRs without updated `examples/complete` diff rejected in CODEOWNERS review — documentation drift is the leading cause of module misconfiguration.

## Governance: CODEOWNERS and RFC for breaking changes

Platform team owns `modules/vpc/CODEOWNERS`. Major version requires RFC: migration guide, `terraform state mv` commands, deprecation window. Release candidate tags tested against three consumer roots before GA. Private Terraform Registry resolves modules faster than `git::` clone every CI plan.

## When NOT to module

- One-off migration resources
- Single security group rule unique to one app
- Prototypes exploring provider behavior

The test: **will another team instantiate this exact pattern twice?** If no, inline until pattern stabilizes.

## Synthesis

Module when pattern repeats; minimal validated interface; semver pin; compose via outputs; test before tag; wrap upstream for org defaults. Modules are **APIs for infrastructure** — design them with the same rigor as public library contracts.

## Module composition patterns in practice

Three composition patterns cover most org layouts:

| Pattern | Structure | Best for |
| --- | --- | --- |
| Layered stack | network → data → compute → app | Platform team owns lower layers |
| Service module | One module per deployable service | Product teams own full stack slice |
| Wrapper + upstream | Thin org wrapper around registry module | Enforcing defaults without fork |

Layered stacks apply in dependency order — network state must apply before compute state reads subnet IDs.

## Consumer contract tests

Downstream roots snapshot expected `module.vpc` outputs in `tests/fixtures/expected_outputs.json` — CI fails when module minor version removes output field platform apps depend on.

## Changelog and semver contract

Every module tag requires CHANGELOG.md entry. Consumers subscribe to GitHub Releases RSS. Deprecation window: six months README banner before removing module input.

## Examples directory enforced in CI

`examples/complete/` runs `terraform init -backend=false`, `validate`, and `test` on every PR. Broken examples block merge before consumers copy broken patterns.

## Private registry over git sources

Terraform Cloud private registry resolves modules faster than `git::` clone every CI plan. Publish on tag push; consumers pin `version = "2.1.0"` not floating git ref. Release notes changelog is contract.

## Variable validation UX

Validation `error_message` must say how to fix: "az_count must be 2-4 for HA; use 3 for standard prod" not "Invalid value." Plan-time errors are UX for other teams consuming your module.

## Module upgrade communication

Publish migration notes in platform newsletter when releasing major module versions — not only GitHub Releases.

## Resources

- [Terraform module documentation](https://developer.hashicorp.com/terraform/language/modules)
- [terraform-docs](https://terraform-docs.io/)
- [Semantic Versioning](https://semver.org/)