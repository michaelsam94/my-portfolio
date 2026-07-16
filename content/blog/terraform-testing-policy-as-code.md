---
title: "Testing Terraform with Policy as Code"
slug: "terraform-testing-policy-as-code"
description: "Testing Terraform with policy as code: unit tests with terraform test, OPA/Conftest and Sentinel guardrails, and how to layer validation so bad infra never ships."
datePublished: "2026-05-09"
dateModified: "2026-05-09"
tags: ["DevOps", "Infrastructure as Code", "Testing"]
keywords: "Terraform testing, policy as code, OPA, Sentinel, terraform test, Conftest, IaC validation"
faq:
  - q: "What is policy as code for Terraform?"
    a: "Policy as code means expressing your infrastructure rules — like 'no public S3 buckets' or 'every resource must be tagged with a cost center' — as machine-evaluable code rather than wiki guidelines. Tools like Open Policy Agent (Conftest) or HashiCorp Sentinel evaluate a Terraform plan against these policies and fail the pipeline if any rule is violated, enforcing standards automatically."
  - q: "How is terraform test different from policy as code?"
    a: "They test different things. The native 'terraform test' framework verifies your module behaves correctly — given these inputs, does it produce the expected resources and outputs. Policy as code verifies the resulting infrastructure meets organizational rules like security and tagging. You want both: correctness tests for the module author, policy checks for the whole org."
  - q: "Where in the pipeline should policy checks run?"
    a: "Run them against the plan output, after 'terraform plan' and before 'terraform apply', in CI on every pull request. Evaluating the plan JSON lets you catch violations before anything is provisioned. For defense in depth, many teams also enforce policies at the state or cloud level, but the PR gate is where you get the fastest, cheapest feedback."
---

The scariest thing about infrastructure as code is that a typo can now provision a publicly readable bucket across your entire fleet in one `apply`. Testing Terraform with policy as code is how you stop that: you combine unit tests that prove your modules do what you intend with automated policy checks that prove the resulting infrastructure obeys your organization's rules — public-access bans, mandatory tags, allowed instance types — and you wire both into CI so nothing non-compliant ever reaches production. The rules stop being a wiki page people ignore and become a gate the pipeline enforces.

I treat this as two distinct layers that people constantly conflate. One tests *correctness* ("does my module create the right resources?"). The other tests *compliance* ("is the resulting infra allowed?"). You need both, and they use different tools.

## Layer one: native module tests

Since Terraform 1.6, there's a built-in test framework. You write `.tftest.hcl` files that run your module with given inputs and assert on the plan or the applied state. This is the author's safety net — refactor a module with confidence that its contract hasn't changed.

```hcl
# tests/defaults.tftest.hcl
run "creates_private_bucket" {
  command = plan

  variables {
    name        = "app-assets"
    environment = "prod"
  }

  assert {
    condition     = aws_s3_bucket.this.bucket == "app-assets-prod"
    error_message = "Bucket name should include the environment suffix"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.this.block_public_acls == true
    error_message = "Public ACLs must be blocked by default"
  }
}
```

`command = plan` runs fast and touches nothing real; use it for logic and naming assertions. Switch to `command = apply` (against a throwaway environment) when you need to test behavior that only materializes after creation. The rule I follow: plan-level tests for structure and defaults, a smaller set of apply-level tests for things you genuinely can't verify from a plan. This is the same testing discipline you'd apply anywhere, extended to the [infrastructure-as-code layer with OpenTofu or Terraform](https://blog.michaelsam94.com/infrastructure-as-code-opentofu-terraform/).

## Layer two: policy as code

Module tests prove *your* module is correct. They don't stop a developer from writing perfectly correct HCL that provisions a compliant-looking but organizationally-forbidden resource. That's what policy as code is for — org-wide rules evaluated against the plan, independent of who wrote the module.

The two dominant tools:

| Tool | Language | Best for |
| --- | --- | --- |
| OPA / Conftest | Rego | Open source, multi-tool, cloud-agnostic |
| HashiCorp Sentinel | Sentinel | HCP Terraform / Enterprise integration |

Both work by evaluating the Terraform plan (exported as JSON) against policies. With Conftest and OPA, a "no public S3 buckets" rule in Rego looks like this:

```rego
package terraform.s3

import rego.v1

deny contains msg if {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket_public_access_block"
    resource.change.after.block_public_acls == false
    msg := sprintf("S3 bucket '%s' must block public ACLs", [resource.address])
}
```

And the pipeline step that enforces it:

```bash
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
conftest test tfplan.json --policy ./policies
```

If any `deny` rule matches, `conftest` exits non-zero and the pipeline fails. The developer sees the violation on their pull request, fixes it, and re-pushes — long before anything is provisioned. That fast, pre-apply feedback loop is the whole game.

## What to actually enforce

Don't try to encode every rule on day one; you'll produce a wall of policy nobody understands. Start with the rules that map to real, expensive failures:

- **Security invariants.** No public buckets, no `0.0.0.0/0` on sensitive ports, encryption at rest required, no hardcoded credentials. This is where policy as code prevents genuine incidents.
- **Cost guardrails.** Restrict instance types and sizes, forbid resources without a `cost-center` tag, cap counts. Tag enforcement alone pays for the whole effort at invoice time.
- **Consistency.** Naming conventions, required tags, approved regions.

Each policy should carry a clear error message that tells the developer *what to do*, not just that they failed. "S3 bucket must block public ACLs" is fine; "policy violation in rule 47" is user-hostile.

## Layering it into the pipeline

The stages, in order, on every pull request:

1. `terraform fmt -check` and `terraform validate` — syntax and basic sanity.
2. `terraform test` — module correctness.
3. `terraform plan` → export JSON → `conftest`/Sentinel — policy compliance.
4. Human review of the plan diff for anything the machines can't judge.
5. `terraform apply` — only after all the above pass.

Everything before step 5 is cheap and touches nothing real, which is exactly why it belongs in a [fast CI/CD pipeline](https://blog.michaelsam94.com/fast-cicd-pipelines/) as an early gate. The point is to shift every catchable failure as far left as possible, where it costs a re-push instead of an incident. And because these checks run on plan output, secrets management stays clean — the plan should never contain plaintext secrets in the first place, which is a policy you can also enforce, alongside proper [secrets management](https://blog.michaelsam94.com/secrets-management/).

## The senior-engineer caveat

Policy as code is a guardrail, not a strategy. I've seen teams write hundreds of policies and mistake that for security, when half the rules were untested and some contradicted each other. Test your policies too — OPA and Conftest both support unit-testing Rego. And keep a pragmatic escape hatch: a documented, auditable exception process for the legitimate case that violates a rule, because a policy with no exception path gets bypassed entirely, which is worse than a policy with a logged override.

The endgame is a pipeline where a developer can move fast *because* the guardrails catch the dangerous mistakes automatically. Correctness tests protect the module author from themselves; policy checks protect the organization from everyone. Layer them properly and "someone provisioned a public bucket" moves from a recurring incident to something the machine simply won't let you merge.

## Resources

- [Terraform — the test framework](https://developer.hashicorp.com/terraform/language/tests)
- [Open Policy Agent (OPA)](https://www.openpolicyagent.org/docs/latest/)
- [Conftest — test configuration with OPA](https://www.conftest.dev/)
- [HashiCorp Sentinel documentation](https://developer.hashicorp.com/sentinel)
- [Rego policy language reference](https://www.openpolicyagent.org/docs/latest/policy-language/)
- [tfsec / Trivy for Terraform scanning](https://github.com/aquasecurity/trivy)
