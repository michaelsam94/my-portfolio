---
title: "Policy as Code for Terraform"
slug: "ops-terraform-policy-sentinel-opa"
description: "Enforce infrastructure standards with Terraform policy: OPA/Rego, Sentinel, Checkov, and CI gates that block non-compliant plans before apply."
datePublished: "2026-01-23"
dateModified: "2026-01-23"
tags: ["DevOps", "Terraform", "Policy", "Security"]
keywords: "Terraform policy as code, OPA Rego Terraform, Sentinel HashiCorp, Checkov IaC, infrastructure compliance"
faq:
  - q: "What is policy as code for Terraform?"
    a: "Automated rules that evaluate Terraform plans or state against organizational standards — required tags, forbidden public S3 ACLs, instance size limits — and block apply if violated. Policies live in Git, versioned alongside modules."
  - q: "Should I use OPA, Sentinel, or Checkov?"
    a: "Checkov and tfsec are fastest to adopt for common misconfigurations with built-in rules. OPA/Rego offers maximum flexibility for custom logic across Terraform, Kubernetes, and API payloads. Sentinel is native to Terraform Cloud/Enterprise with HCL-like syntax and tight plan integration."
  - q: "When should policy run in the Terraform workflow?"
    a: "Run static analysis (Checkov) on PR against .tf files for fast feedback. Run OPA/Sentinel against terraform plan JSON before apply — many violations only appear in resolved values after module expansion."
---

A platform engineer merged a module that opened port 22 on every EC2 instance to `0.0.0.0/0`. Code review missed it — the diff was buried in a submodule bump. Policy as code would have blocked the plan with `security group rule violates SG-001`. Humans review intent; policies catch the patterns humans skim past.

## Where policy sits in the pipeline

```
PR opened ──► Checkov/tfsec (static .tf scan)
       │
terraform plan ──► plan JSON ──► OPA/Sentinel evaluate
       │
   pass ──► terraform apply (manual or automated)
   fail ──► block + PR comment with violation details
```

Static scans catch obvious issues early (hardcoded secrets, missing encryption flags). Plan-time policies catch computed values — resolved AMI IDs, effective security group rules after module composition.

## OPA with Rego on plan JSON

Convert plan to JSON:

```bash
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json
```

Policy example — deny S3 buckets without encryption:

```rego
# policies/s3_encryption.rego
package terraform.analysis

deny[msg] {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    resource.change.actions[_] == "create"
    not resource.change.after.server_side_encryption_configuration
    msg := sprintf("S3 bucket %s must have encryption enabled", [resource.address])
}
```

Run with conftest:

```bash
conftest test tfplan.json -p policies/
```

OPA integrates with Spacelift, Atlantis, and custom CI. Same Rego policies can gate Kubernetes admissions — platform teams maintain one policy language.

## HashiCorp Sentinel (Terraform Cloud/Enterprise)

Sentinel uses a HCL-inspired language with Terraform plan imports:

```python
# policy/require-tags.sentinel
import "tfplan/v2" as tfplan

mandatory_tags = ["Environment", "Team", "CostCenter"]

main = rule {
    all tfplan.resource_changes as _, rc {
        rc.type is "aws_instance" implies
        all mandatory_tags as tag {
            rc.change.after.tags contains tag
        }
    }
}
```

Policies attach to workspaces as advisory (log only) then hard-mandatory. Soft-mandatory allows override with justification — useful during migration.

If you're not on TFC/TFE, Sentinel's ecosystem lock-in rarely justifies switching clouds.

## Checkov for breadth, fast adoption

```bash
checkov -d . --framework terraform --quiet --compact
```

Thousands of built-in policies (CIS benchmarks, SOC2 mappings). Custom policies in Python/YAML:

```yaml
# .checkov.yaml or external check
metadata:
  name: "Deny public RDS"
  category: "NETWORKING"
definition:
  cond_type: "attribute"
  resource_types: ["aws_db_instance"]
  attribute: "publicly_accessible"
  operator: "equals"
  value: true
```

Checkov runs in PR checks in 30–60 seconds on medium repos. False positives happen — maintain an allowlist (`skip-check` comments with ticket references).

## Policy design principles

**Start with deny-list for critical risks.** Public RDS, open SG ports, unencrypted buckets, `*` IAM actions. Expand to require-list (tags, regions, instance families).

**Policy exceptions need audit trail.** `count.skip` in Checkov or Sentinel override with mandatory `reason` variable logged to SIEM.

**Test policies like code.** Unit tests for Rego (`opa test policies/`) and Sentinel (mock tfplan fixtures). Broken policy that always passes is worse than no policy.

**Scope by environment.** Staging may allow `t3.micro` spot; prod requires `m6i` and on-demand. Pass `environment` as OPA input:

```bash
conftest test tfplan.json -p policies/ --input environment=production
```

## Real policies we enforce

| ID | Rule | Tool |
|----|------|------|
| NET-001 | No `0.0.0.0/0` on port 22 | OPA |
| NET-002 | ALB must use TLS 1.2+ policy | Checkov |
| TAG-001 | `Team`, `Environment`, `Service` required | Sentinel |
| IAM-001 | No inline policies on users | OPA |
| COST-001 | No `p4d.*` GPU without `CostApproved` tag | OPA |

Violations post as PR comments via Atlantis or GitHub Action annotations. Block merge on `deny` severity; warn on `advisory`.

## Policy rollout strategy

Ship new policies as advisory for two weeks — log violations without blocking apply. Review false positive rate with service teams. Promote to hard-mandatory when noise is acceptable. Sudden mandatory policies on legacy repos block all deploys and erode platform trust.

Version policy repos independently from application Terraform. Pin policy bundle version in CI so a policy change does not surprise teams mid-apply.

## Operational notes

Publish policy violation reports as PR comments with line numbers referencing Terraform resource addresses. Developers fix faster when the comment says `aws_security_group.web` violates NET-001 rather than a generic "policy failed" message. Include remediation snippet in comment when possible.

Export policy evaluation metrics to Prometheus — violations per policy ID, per team tag — to prioritize which rules need clearer remediation docs versus which teams need training.

## Common production mistakes

Teams get terraform policy sentinel opa wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of terraform policy sentinel opa fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When terraform policy sentinel opa misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Open Policy Agent documentation](https://www.openpolicyagent.org/docs/latest/)
- [Conftest — test configuration with OPA](https://www.conftest.dev/)
- [HashiCorp Sentinel language guide](https://developer.hashicorp.com/sentinel/docs)
- [Checkov Terraform policies](https://www.checkov.io/5.Policy%20Index/terraform.html)
- [terraform-json plan format](https://developer.hashicorp.com/terraform/internals/json-format)
