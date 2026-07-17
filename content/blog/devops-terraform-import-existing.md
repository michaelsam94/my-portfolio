---
title: "Terraform Import for Existing Resources"
slug: "devops-terraform-import-existing"
description: "Import brownfield resources without recreation."
datePublished: "2026-04-16"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Terraform"
  - "Platform"
keywords: "Terraform import, brownfield"
faq:
  - q: "When should teams prioritize Terraform Import for Existing Resources?"
    a: "When bringing existing cloud resources under IaC."
  - q: "What is the most common mistake with terraform import?"
    a: "Import without plan review—unintended destroys in apply."
  - q: "Can engineers run apply locally?"
    a: "Discourage for shared workspaces — CI with plan comments, OIDC, and policy gates. Local plan is fine; local apply without locking is how duplicate VPCs happen."
  - q: "How do module tests differ from integration tests?"
    a: "Module tests assert outputs and resource shapes with mock providers; integration tests apply to ephemeral accounts. Both belong in the publish pipeline."
---
Import recreated RDS instance—brief outage during wrong resource address. This post is about making terraform import for existing resources boring in the best way — predictable under load, auditable under review, and reversible under stress.

## What broke first on dashboards


Import recreated RDS instance—brief outage during wrong resource address.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to import without plan review—unintended destroys in apply.

terraform import was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move terraform import into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```yaml
# terraform-import-existing — plan-time guard
resource "null_resource" "example" {
  triggers = {
    validated = var.environment != "prod" || var.approved
  }
}
```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put terraform import on the critical path for one tier-1 workflow and measure what it catches.

## Plan review discipline

Every infrastructure PR gets a speculative plan comment, cost delta when available, and policy check output. Reviewers approve the plan — not just the HCL diff. Destroy operations require explicit approval workflow outside normal merge paths.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Operating terraform import at scale

After the first successful deploy of terraform import for existing resources, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of terraform import settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Terraform pipelines touch ingestion, serving, and finance. Document interfaces where terraform import gates hand off to downstream owners so failures are not bounced without context.

## Further reading

- https://developer.hashicorp.com/terraform/docs
- https://developer.hashicorp.com/terraform/language/tests
