---
title: "IaC Security Scanning"
slug: "iac-security-scanning-checkov"
description: "Scan Terraform, Kubernetes, and CloudFormation for misconfigurations with Checkov: CI integration, custom policies, suppressions, and fixing findings that matter."
datePublished: "2025-07-01"
dateModified: "2025-07-01"
tags: ["Security", "DevOps", "Infrastructure", "CI/CD"]
keywords: "Checkov IaC scanning, Terraform security scanning, infrastructure as code security, Checkov CI integration, IaC misconfiguration, policy as code"
faq:
  - q: "What does Checkov scan?"
    a: "Checkov analyzes Infrastructure as Code files — Terraform (.tf), CloudFormation (.yaml/.json), Kubernetes manifests, Helm charts, Dockerfiles, and ARM templates — against hundreds of built-in policies covering CIS benchmarks, SOC2, and common misconfigurations like public S3 buckets, open security groups, and missing encryption."
  - q: "Should Checkov block CI on every finding?"
    a: "Not initially. Start in advisory mode (report only), triage findings, fix or suppress false positives, then enable hard-fail on critical/high severity. Blocking on all 200+ checks day one creates alert fatigue and teams disable the scanner. Phase in enforcement by severity."
  - q: "How do I handle Checkov findings that are intentional?"
    a: "Use inline suppressions with a reason and optional expiry: # checkov:skip=CKV_AWS_20: reason='Public ALB is intentional for this marketing site'. Suppressions should require justification and periodic review. Avoid blanket directory-level skips."
---

We shipped a Terraform module that opened port 22 to 0.0.0.0/0 on a production security group. It passed `terraform plan`, passed code review, and passed CI — because CI didn't scan the IaC. Checkov would have flagged it in four seconds. Infrastructure-as-code moves fast; manual review doesn't scale. Automated policy scanning catches the misconfigurations that look boring until they're breached.

## What Checkov catches

Checkov runs static analysis on IaC files against 750+ policies:

- S3 buckets with public ACLs
- Security groups allowing 0.0.0.0/0 on sensitive ports
- RDS instances without encryption at rest
- IAM policies with `"Action": "*"` and `"Resource": "*"`
- Kubernetes pods running as root or with privileged containers
- Missing logging on CloudTrail, VPC flow logs, ALB access logs

Each finding has an ID (e.g., `CKV_AWS_20`), severity, and a link to the rationale.

## Running Checkov locally

```bash
pip install checkov
checkov -d terraform/
```

Output:

```
Check: CKV_AWS_20: "S3 Bucket has an ACL defined which allows public READ access"
        FAILED for resource: aws_s3_bucket.logs
        File: /terraform/s3.tf:12-25
```

Scan specific frameworks:

```bash
checkov --framework terraform kubernetes dockerfile -d .
```

## CI integration

GitHub Actions:

```yaml
name: IaC Security Scan
on: [pull_request]

jobs:
  checkov:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: terraform/
          framework: terraform
          soft_fail: false
          output_format: sarif
          output_file_path: checkov.sarif

      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: checkov.sarif
```

SARIF upload surfaces findings directly in the PR diff view — reviewers see security issues alongside code changes.

## Phased rollout

**Week 1 — Advisory:**
```bash
checkov -d terraform/ --soft-fail
```
Report only. Triage findings. Fix the obvious ones.

**Week 2-3 — Severity gate:**
```bash
checkov -d terraform/ --check HIGH,CRITICAL
```
Block PRs on high and critical only.

**Week 4+ — Full enforcement:**
```bash
checkov -d terraform/ --compact
```
All checks fail the build. Low-severity findings get fixed or suppressed with justification.

## Suppressions done right

Inline skip with reason:

```hcl
resource "aws_security_group_rule" "alb_https" {
  # checkov:skip=CKV_AWS_23: "Public HTTPS ingress required for ALB"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
}
```

Bulk suppression file for known exceptions:

```yaml
# .checkov.yml
skip-check:
  - CKV_AWS_144  # Cross-region replication not needed for dev
  - CKV_AWS_145  # S3 encryption with AWS-managed key acceptable in dev

branch: main  # only enforce on main-bound PRs
```

Review suppressions quarterly. A suppression without an expiry becomes permanent debt.

## Custom policies

When built-in checks don't cover your org's rules, write custom policies in Python or YAML:

```python
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck
from checkov.common.models.enums import CheckResult, CheckCategories

class S3BucketNamingConvention(BaseResourceCheck):
    def __init__(self):
        super().__init__(
            id="CKV_CUSTOM_001",
            name="S3 bucket names must start with company prefix",
            categories=[CheckCategories.CONVENTION],
            supported_resources=["aws_s3_bucket"]
        )

    def scan_resource_conf(self, conf):
        name = conf.get("bucket", [None])[0]
        if name and name.startswith("acme-"):
            return CheckResult.PASSED
        return CheckResult.FAILED

check = S3BucketNamingConvention()
```

Custom policies encode org-specific conventions that generic scanners can't know.

## Pairing with other tools

Checkov covers misconfigurations. It doesn't replace:

| Tool | Covers |
|------|--------|
| **tfsec** | Terraform-specific (similar overlap with Checkov) |
| **Trivy** | Container image vulnerabilities |
| **Snyk IaC** | Dependency + IaC combined |
| **OPA/Conftest** | Custom Rego policies on any JSON/YAML |

Pick one primary IaC scanner to avoid duplicate findings. Checkov or tfsec, not both on the same PR.

## Pre-commit hook integration

Catch misconfigurations before they reach CI:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/bridgecrewio/checkov
    rev: 3.2.0
    hooks:
      - id: checkov
        args: ["--framework", "terraform", "--quiet"]
```

Developers see findings on `git commit`, not 20 minutes later in a CI queue. Pair with `terraform fmt` and `tflint` for a complete local Terraform gate.

## Measuring scanner effectiveness

Track metrics monthly:

- **Findings per PR** — trending down means developers are learning
- **False positive rate** — suppressions added vs genuine fixes
- **Time to remediate** — critical findings should close within 48 hours
- **Repeat findings** — same check failing twice on the same module means the team needs training, not more suppressions

Share a dashboard with security and platform teams. A scanner nobody looks at is security theater.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get iac security scanning checkov wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of iac security scanning checkov fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When iac security scanning checkov misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Checkov documentation](https://www.checkov.io/) — installation, configuration, and policy reference
- [Checkov GitHub](https://github.com/bridgecrewio/checkov) — source, issue tracker, and custom policy examples
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services) — the baseline many Checkov policies enforce
- [Bridgecrew Checkov Action](https://github.com/bridgecrewio/checkov-action) — GitHub Actions integration
