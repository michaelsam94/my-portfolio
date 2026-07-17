---
title: "Testing Terraform with Policy as Code"
slug: "terraform-testing-policy-as-code"
description: "Testing Terraform with policy as code: unit tests with terraform test, OPA/Conftest and Sentinel guardrails, and how to layer validation so bad infra never ships."
datePublished: "2026-05-09"
dateModified: "2026-07-17"
tags: ['DevOps', 'Infrastructure as Code', 'Testing']
keywords: "Terraform testing, policy as code, OPA, Sentinel, terraform test, Conftest, IaC validation"
faq:
  - q: "What is policy as code for Terraform?"
    a: "Policy as code means expressing your infrastructure rules — like 'no public S3 buckets' or 'every resource must be tagged with a cost center' — as machine-evaluable code rather than wiki guidelines. Tools like Open Policy Agent (Conftest) or HashiCorp Sentinel evaluate a Terraform plan against these policies and fail the pipeline if any rule is violated, enforcing standards automatically."
  - q: "How is terraform test different from policy as code?"
    a: "They test different things. The native 'terraform test' framework verifies your module behaves correctly — given these inputs, does it produce the expected resources and outputs. Policy as code verifies the resulting infrastructure meets organizational rules like security and tagging. You want both: correctness tests for the module author, policy checks for the whole org."
  - q: "Where in the pipeline should policy checks run?"
    a: "Run them against the plan output, after 'terraform plan' and before 'terraform apply', in CI on every pull request. Evaluating the plan JSON lets you catch violations before anything is provisioned. For defense in depth, many teams also enforce policies at the state or cloud level, but the PR gate is the fastest, cheapest feedback."
faqAnswers:
  - question: "When is terraform testing policy as code the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for terraform testing policy as code?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back terraform testing policy as code safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
One mistyped `acl = "public-read"` in a module default can expose every new S3 bucket across four environments before a human notices in review. Infrastructure as code magnifies mistakes at machine speed. Testing Terraform requires two layers most teams conflate: **module correctness** (does this code build what the author intended?) and **organizational compliance** (is what it builds allowed?). Native `terraform test` handles the first; policy as code (OPA/Conftest, Sentinel, Checkov) handles the second. Wire both into CI between `plan` and `apply`.

## The validation pyramid for infrastructure

```
                    ┌─────────────────┐
                    │  Cloud SCPs     │  Last line — org guardrails
                    ├─────────────────┤
                    │  Policy on plan │  Conftest / Sentinel
                    ├─────────────────┤
                    │  Static analysis│  Checkov / tfsec on .tf
                    ├─────────────────┤
                    │  terraform test │  Module correctness
                    ├─────────────────┤
                    │  fmt / validate │  Syntax and provider schema
                    └─────────────────┘
```

Each layer catches different failure classes. Static analysis runs before plan — fast but misses computed values. Plan-level policy sees resolved attributes. SCPs catch bypass even if CI is compromised.

## Layer 1: module correctness with terraform test

Since Terraform 1.6, `.tftest.hcl` files run modules with assertions:

```hcl
run "blocks_public_access" {
  command = plan
  variables { name = "assets", environment = "prod" }
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

## Mock providers for fast module CI

Terraform 1.7+ mocking enables plan tests without cloud credentials:

```hcl
mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }
}
```

Module CI completes in seconds on every push — reserve real cloud `apply` for weekly integration in ephemeral accounts.

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
    msg := sprintf("S3 public ACLs must be blocked: %s", [resource.address])
}

deny contains msg if {
    some resource in input.resource_changes
    resource.type == "aws_instance"
    resource.change.after.instance_type == "t2.micro"
    input.variables.environment.value == "prod"
    msg := sprintf("t2.micro not allowed in prod: %s", [resource.address])
}
```

```bash
conftest test tfplan.json --policy policies/ --all-namespaces
```

Fail CI on non-zero exit. Policies live in central repo — security team owns Rego, app teams consume gate.

## Policy engine comparison

| Tool | Input | Strength | Integration |
| --- | --- | --- | --- |
| Conftest/OPA | Plan JSON, K8s YAML | Open source, multi-cloud | CLI in any CI |
| HashiCorp Sentinel | Plan, runtime values | Native HCP Terraform | Policy sets in TFC |
| Checkov / tfsec | `.tf` files | Pre-plan, fast feedback | GitHub Action |
| Infracost | Plan JSON | Cost delta policies | FinOps gate |
| AWS SCPs | API calls | Org-wide enforcement | Cannot bypass in account |

Defense in depth: Checkov on PR → plan → Conftest on plan JSON → SCP prevents apply even if CI bypassed.

## Pipeline placement and timing

```
PR opened
  → terraform fmt -check
  → terraform validate
  → checkov -d .
  → terraform plan -out=plan.bin
  → terraform show -json > plan.json
  → conftest test plan.json
  → terraform test
Merge → apply with approval gate
```

Policy on **plan output** catches resources about to change, including destroys and replacements. Target under two minutes for static + plan + policy on typical root module.

## Testing destructive changes

Policies can require explicit approval for `delete` actions:

```rego
deny contains msg if {
    some resource in input.resource_changes
    resource.change.actions[_] == "delete"
    resource.type == "aws_rds_cluster"
    not input.metadata.labels.approved_destroy
    msg := sprintf("RDS destroy requires data platform approval: %s", [resource.address])
}
```

Load destroy policies only for prod plan artifacts — dev sandboxes remain fast.

## Negative and positive test fixtures

Maintain regression fixtures for policy rules:

```
testdata/bad_plan_public_s3.json    # must fail s3.rego
testdata/good_plan_compliant.json   # must pass all deny rules
```

CI runs Conftest against fixtures on every policy repo PR — refactors cannot silently weaken rules.

## Exception and waiver workflow

Break-glass `policy_waiver` label on PR requires two security approvers; Conftest skips deny rules only for labeled plans; waivers expire in 7 days if not applied. Log waivers to SIEM with approver identity — compliance reviews quarterly.

Pin Conftest policy bundle git SHA in CI workflow, not floating main — deploy pipeline must not change compliance rules mid-apply without explicit policy repo release.

## Cost estimation as policy

Integrate Infracost on plan JSON — policy denies PR if monthly delta exceeds `$500` without `cost-approved` label. FinOps and security evaluate same plan artifact.

## Consumer repo testing

Root modules run `terraform test` against pinned child module versions in CI — catches module upgrade breaking consumer assumptions before merge even when module's own tests passed.

## Measuring policy effectiveness

Track policy violations caught pre-apply, mean time to add policy after incident, and waiver count. Goal: incidents from misconfig trend down while PR velocity stays flat.

## Synthesis

`terraform test` for module contracts; Conftest/Sentinel on plan JSON for org rules; static analysis upstream; SCPs downstream. The pipeline between plan and apply is where **infrastructure governance becomes enforceable** — not wiki guidance, but code that blocks the merge.

## Static analysis upstream of plan

Checkov and tfsec scan `.tf` files before plan — catches hardcoded secrets in HCL:

```bash
checkov -d . --framework terraform
terraform plan -out=plan.bin
terraform show -json plan.bin > plan.json
conftest test plan.json --policy policies/
```

Static analysis catches issues earlier; plan policy catches computed values resolved only at plan time.

## Ephemeral environments for apply tests

Spin ephemeral env per PR in sandbox account for integration confidence beyond plan-level tests. Cost-controlled with TTL and small instance sizes.

## Policy version pinning in CI

```yaml
- uses: actions/checkout@v4
  with:
    repository: org/terraform-policies
    ref: v2.4.1
    path: policies
```

Infrastructure deploy pipeline must not change compliance rules mid-apply without explicit policy repo release.

## Developer experience metrics

Track policy violation rate per team over time. Rising violations after new rule indicate unclear error messages — iterate policy messages until developers self-serve fixes without platform team Slack pings.

## Signed OPA policy bundles

Cosign-sign policy bundles; CI verifies signature before `conftest test`. Tampered Rego cannot weaken public S3 deny rule without detection.

## Plan JSON schema validation

Validate `tfplan.json` against Terraform plan schema before Conftest — malformed plan from provider crash should fail CI loudly, not produce empty policy pass.

## Checkov skip comment audit

`checkov:skip` comments require ticket ID in same line — monthly grep finds skips without tickets.

## Sentinel vs OPA trade-offs

Sentinel integrates natively with HCP Terraform policy sets — evaluate at plan and apply in managed runs. OPA/Conftest runs anywhere — preferred for multi-cloud and polyglot pipelines. Many orgs run Conftest in CI and Sentinel in TFC for defense in depth.

## Policy rollout strategy

Start new policies in advisory mode for two weeks — log violations without blocking. Measure false positive rate before switching to enforce mode. Grandfather existing violations with ticket-linked exception tags expiring quarterly.

## Integration with HCP Terraform run tasks

Run tasks execute Conftest against plan JSON in Terraform Cloud before apply gate — same policies as CI, enforced at apply time for teams using VCS-driven workflows.

## Resources

- [Terraform test documentation](https://developer.hashicorp.com/terraform/language/tests)
- [Conftest](https://www.conftest.dev/)
- [OPA Rego language](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [Checkov](https://www.checkov.io/)