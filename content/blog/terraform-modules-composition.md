---
title: "Composable Terraform Modules"
slug: "terraform-modules-composition"
description: "Build reusable Terraform modules with clear interfaces, composition patterns, and versioning so infrastructure code scales across teams without copy-paste."
datePublished: "2025-12-10"
dateModified: "2025-12-10"
tags: ["Terraform", "Infrastructure", "DevOps", "Modules"]
keywords: "Terraform modules, composable infrastructure, module composition patterns, Terraform module versioning, reusable IaC, Terraform registry"
faq:
  - q: "When should I create a Terraform module vs inline resources?"
    a: "Create a module when you'll instantiate the same pattern more than twice — a VPC setup, an ECS service, a standard S3 bucket with encryption and logging. Keep one-off resources inline. Over-modularizing (a module for a single security group rule) adds indirection without reuse benefit. The test: would another team or environment use this exact combination of resources?"
  - q: "How do I version Terraform modules?"
    a: "Tag module repositories with semantic versions (v1.2.0). Consumers pin to a version: source = 'git::https://github.com/org/terraform-modules/vpc?ref=v1.2.0'. Never point production at main/master — a breaking change in the module repo shouldn't break production on the next plan. Use the Terraform Registry for public modules; private registries (Terraform Cloud, Artifactory) for internal modules."
  - q: "What belongs in a module's interface?"
    a: "Inputs: the minimum variables needed to customize behavior (name, environment, CIDR range, instance type). Outputs: everything downstream modules or root modules need (VPC ID, subnet IDs, security group IDs). Hide internal implementation details — consumers shouldn't need to know how many subnets the VPC module creates, just the subnet IDs they can pass to an EC2 module."
---

We had four teams copying the same 200-line VPC configuration into their Terraform repos, diverging within months. Team A added flow logs; team B didn't. Team C used different CIDR sizing. Team D's version had a security group bug that the others avoided. Module extraction took a week; alignment took a day. One `module "vpc"` call replaced four divergent copies.

Terraform modules are reusable packages of infrastructure code. Good modules have clear interfaces, sensible defaults, and compose with other modules. Bad modules are copy-pasted resource blocks with 40 undocumented variables.

## Module structure

```
modules/
  vpc/
    main.tf        # Resource definitions
    variables.tf   # Input variables with descriptions and defaults
    outputs.tf     # Output values for downstream consumers
    versions.tf    # Provider version constraints
    README.md      # Usage examples and input/output documentation
```

Keep modules focused. A VPC module creates VPCs, subnets, route tables, and NAT gateways. It doesn't also create ECS clusters — that's a separate module that consumes VPC outputs.

## Defining a clean interface

```hcl
variable "name" {
  description = "Name prefix for all VPC resources"
  type        = string
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones (determines subnet count)"
  type        = number
  default     = 2
  validation {
    condition     = var.az_count >= 2 && var.az_count <= 4
    error_message = "AZ count must be between 2 and 4."
  }
}
```

Every variable has a description, a type, and a default where sensible. Validation blocks catch errors at plan time, not apply time.

## Composition patterns

Modules compose by passing outputs to inputs:

```hcl
module "vpc" {
  source     = "../../modules/vpc"
  name       = "production"
  cidr_block = "10.1.0.0/16"
  az_count   = 3
}

module "app" {
  source     = "../../modules/ecs-service"
  name       = "api"
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
}
```

Each module is independent. The root module wires them together. Adding a cache layer means adding a module block — no changes to VPC or app modules.

## Root module vs child module responsibilities

**Root module (environment):** Instantiates child modules, wires outputs to inputs, defines backend configuration, sets environment-specific values.

**Child module (reusable):** Creates resources for one concern, accepts variables, exposes outputs, contains no backend or provider configuration.

```hcl
# Good — caller decides instance type
variable "instance_type" { type = string }
resource "aws_instance" "app" {
  instance_type = var.instance_type
}
```

## Versioning and consumption

Pin module versions in production:

```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.8.1"
  name    = "production"
  cidr    = "10.1.0.0/16"
}
```

Release internal modules with changelogs. Breaking changes require a major version bump.

## Testing modules

```bash
terraform fmt -check -recursive modules/
terraform validate
tflint --module
checkov -d modules/vpc/
```

Include an `examples/` directory with working configurations that serve as both documentation and test fixtures. Use `terraform test` (native since 1.6) or Terratest for integration validation.

## Publishing internal modules

Treat module repos like libraries: semver tags, changelog, deprecation notices. Consumers pin versions; maintainers support N-1 major. Run example root modules in `examples/` directory as living documentation — CI applies and destroys them weekly to prove modules still compose. Broken examples are the first signal interface drift broke consumers.

## Composition over inheritance in module design

Prefer small modules composed at the root over mega-modules with boolean flags. A `database` module plus `monitoring` module beats `database_with_optional_monitoring = true`. Callers see explicit dependencies in plan output. When modules grow flags, split them — the combinatorial test matrix explodes otherwise.

## Module testing in CI pipelines

Run `terraform validate` and `tflint` on every PR touching modules. For published modules, tag releases only after integration tests pass in a sandbox account. Document breaking changes in CHANGELOG with migration snippets — consumers upgrading across major versions should find copy-paste steps, not archaeology in git history.

## Variable and output contracts

Module interfaces are APIs — document every variable:

```hcl
variable "vpc_cidr" {
  description = "CIDR block for VPC. Must not overlap with peered VPCs."
  type        = string
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Must be valid IPv4 CIDR."
  }
}
```

Outputs should expose only what consumers need — leaking internal resource IDs encourages tight coupling. Use `sensitive = true` on outputs containing secrets.

## State management across modules

Root module owns state; child modules inherit:

```hcl
# root/main.tf
module "network" { source = "./modules/network" }
module "eks" {
  source     = "./modules/eks"
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids
  depends_on = [module.network]
}
```

Explicit `depends_on` when module outputs aren't referenced directly but ordering matters (IAM before EKS). `-target` applies are escape hatches, not deployment strategy — document why if used.

## Anti-patterns in module composition

- **Monolithic root module** — 2000-line main.tf with no modules; untestable
- **Circular module dependencies** — module A needs output from B needs output from A
- **Unpinned module sources** — `source = "git::..."` without ref tag
- **Copy-paste modules** — fork instead of parameterizing; drift guaranteed

Pair with [Terraform drift detection](https://blog.michaelsam94.com/terraform-drift-detection/) when composed modules drift from declared state.

## Common production mistakes

Teams get modules composition wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Terraform patterns for modules composition rot when emergency console edits never get codified, `ignore_changes` blocks multiply without documentation, and drift detection runs monthly instead of daily on production workspaces.

## Resources

- [Terraform module documentation](https://developer.hashicorp.com/terraform/language/modules)
- [terraform-aws-modules (community reference)](https://github.com/terraform-aws-modules)
- [Terratest for module integration testing](https://terratest.gruntwork.io/)
- [Standard module structure — Terraform docs](https://developer.hashicorp.com/terraform/language/modules/develop/structure)
- [Semantic versioning for Terraform modules](https://developer.hashicorp.com/terraform/language/modules/develop/composition)
