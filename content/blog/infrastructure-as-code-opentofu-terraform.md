---
title: "Infrastructure as Code with OpenTofu and Terraform"
seoTitle: "Infrastructure as Code: OpenTofu and Terraform"
slug: "infrastructure-as-code-opentofu-terraform"
description: "OpenTofu vs Terraform for IaC — remote state, modules, the licensing fork, and patterns that survive when platform teams maintain production infrastructure."
datePublished: "2026-06-30"
dateModified: "2026-06-30"
tags: ["Infrastructure as Code", "Terraform", "OpenTofu", "DevOps"]
keywords: "Infrastructure as Code, Terraform, OpenTofu, IaC, provisioning, state management, remote state"
faq:
  - q: "What is the difference between OpenTofu and Terraform?"
    a: "OpenTofu is an open-source fork of Terraform created after HashiCorp relicensed Terraform under the BUSL in 2023. It stays MPL-licensed, is largely a drop-in replacement, and is governed by the Linux Foundation. The core HCL workflow — plan, apply, state — is the same, with some features diverging over time."
  - q: "Why is Terraform state so important?"
    a: "State is Terraform's map between your configuration and the real resources it created. It tracks resource IDs, dependencies, and metadata so plans know what already exists. Lose or corrupt it and Terraform can't tell what it owns, which is why remote, locked, versioned state is non-negotiable for teams."
  - q: "Should I switch from Terraform to OpenTofu?"
    a: "For most teams the switch is low-risk because OpenTofu is largely drop-in for existing configs. Decide based on licensing comfort, whether you rely on features exclusive to one, and your CI tooling support. Test in a non-production workspace before committing."
---

Infrastructure as Code means your servers, networks, databases, and DNS records are defined in version-controlled files rather than clicked into existence in a web console. You describe the desired end state, the tool figures out the diff against reality, and it makes the changes. The payoff is that infrastructure becomes reviewable, repeatable, and recoverable — a new environment is a `git clone` and an `apply`, not a two-day archaeology project of remembering what someone set up last year.

Terraform has been the default IaC tool for a decade. Then in 2023 HashiCorp changed its license to the Business Source License, the community forked it into OpenTofu under the Linux Foundation, and now there are two. For most working engineers the day-to-day is nearly identical, so I'll cover the shared workflow and flag where the fork matters.

## The core loop is the same

Both tools use HCL and the same plan/apply cycle. You declare resources, run `plan` to preview changes, and `apply` to make them. The commands are `terraform` and `tofu` respectively but otherwise mirror each other.

```hcl
resource "aws_s3_bucket" "assets" {
  bucket = "acme-prod-assets"
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}
```

```bash
tofu init      # download providers, configure backend
tofu plan      # show what will change — read this every time
tofu apply     # make it so
```

The discipline that separates people who trust IaC from people who fear it is one habit: **read the plan.** Every `apply` in production should be gated on a human actually reading the diff, because the plan will happily tell you it's about to destroy and recreate your database because you changed an immutable attribute. Catching that in the plan is a shrug; catching it after apply is an incident.

## State is the thing that will hurt you

Terraform/OpenTofu keeps a **state file** — the mapping between your config and the real resources it created, including IDs and dependency order. This file is the tool's entire understanding of the world. Three rules I treat as non-negotiable:

1. **Never store state locally for shared infra.** A state file on someone's laptop means only they can apply, and it's one lost machine from disaster. Use a remote backend — S3, GCS, Azure Blob, or a managed backend.
2. **Lock it.** Concurrent applies against the same state corrupt it. Use a backend that supports locking (S3 with a lock table or S3 native locking, for instance) so two pipelines can't stomp each other.
3. **Version and encrypt it.** State can contain secrets in plaintext. Enable bucket versioning so you can recover a clobbered state, and encrypt at rest.

```hcl
terraform {
  backend "s3" {
    bucket       = "acme-tfstate"
    key          = "prod/network/terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true   # native S3 state locking
  }
}
```

Split state by blast radius. One giant state file for the whole company means every change re-plans everything and one mistake can wreck unrelated systems. Separate state per environment and per bounded area — networking, data, apps — so a change to the app layer can't accidentally touch the VPC.

## Modules keep it sane

Copy-pasting resource blocks across environments is how IaC rots. Modules are the reusable unit: parameterize a chunk of infrastructure once, then instantiate it per environment with different inputs.

```hcl
module "api_service" {
  source        = "./modules/ecs-service"
  name          = "payments-api"
  cpu           = 512
  memory        = 1024
  desired_count = var.environment == "prod" ? 6 : 1
}
```

Keep modules small and composable rather than building one mega-module with fifty inputs. A good module does one thing — a service, a bucket-with-sane-defaults, a DNS zone — and hides the boilerplate. This is the same instinct behind [clean architecture applied pragmatically](https://blog.michaelsam94.com/clean-architecture-pragmatically/): sharp boundaries, sensible defaults, no leaky abstractions.

## The OpenTofu fork, practically

Here's the decision most teams face, boiled down:

| Consideration | Notes |
|---|---|
| License | OpenTofu is MPL (open); Terraform is BUSL |
| Governance | OpenTofu under Linux Foundation; Terraform by HashiCorp |
| Config compatibility | Largely drop-in for existing HCL |
| Feature drift | Diverging slowly; some features are exclusive to each |
| Tooling/ecosystem | Both widely supported; check your CI and Cloud provider |

For a new project I'd default to OpenTofu for the open license and community governance. For an existing Terraform estate, the migration is usually straightforward — point your CI at `tofu` instead of `terraform` and test in a throwaway workspace first — but confirm you're not depending on a feature that only one of them has before committing.

## Patterns that survive real teams

**Run it in CI, not from laptops.** Applies should happen in a pipeline with an audit trail, not from whoever's terminal. This gives you the same review-and-merge discipline you'd want from [GitOps](https://blog.michaelsam94.com/gitops-argocd-flux/) and keeps cloud credentials out of individual hands.

**Never hardcode secrets.** Feed them from a secrets manager or environment, and remember state can capture them — see [secrets management](https://blog.michaelsam94.com/secrets-management/) for how to handle this properly.

**Use `plan` as a PR check.** Post the plan output on the pull request so reviewers see exactly what infrastructure the change touches. A speculative plan on every PR catches destructive diffs before merge.

**Pin provider versions.** An unpinned provider upgrade can change plan behavior under you. Lock versions in the `required_providers` block and bump them deliberately.

**Import, don't recreate.** When you inherit click-ops infrastructure, `import` it into state rather than destroying and rebuilding. The generated-config workflows in recent versions make this far less painful than it used to be.

## Where to start

Put one small, non-critical piece of infrastructure — a bucket, a DNS zone — under IaC with remote, locked, versioned state. Wire `plan` into your PR checks and `apply` into a pipeline. Get the team used to reading plans before they apply. Once that loop feels natural, expand outward, splitting state by blast radius as you go. The goal isn't to codify everything overnight; it's to make "how was this set up?" a question you answer with `git blame` instead of a shrug.

## Resources

- [OpenTofu documentation](https://opentofu.org/docs/)
- [Terraform documentation](https://developer.hashicorp.com/terraform/docs)
- [OpenTofu — migrating from Terraform](https://opentofu.org/docs/intro/migration/)
- [Terraform — remote state backends](https://developer.hashicorp.com/terraform/language/state/remote)
- [Terraform — module composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition)
- [CNCF — OpenTofu project](https://www.cncf.io/projects/opentofu/)
