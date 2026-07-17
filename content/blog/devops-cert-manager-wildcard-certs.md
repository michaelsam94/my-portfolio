---
title: "Wildcard TLS with cert-manager and DNS Providers"
slug: "devops-cert-manager-wildcard-certs"
description: "Automate wildcard cert renewal with DNS-01 and limited IAM scope."
datePublished: "2026-10-08"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Networking"
  - "Security"
keywords: "wildcard TLS, cert-manager"
faq:
  - q: "When should teams prioritize Wildcard TLS with cert-manager and DNS Providers?"
    a: "Many subdomains under one service mesh or ingress."
  - q: "What is the most common mistake with wildcard certificates?"
    a: "Wildcard cert shared across prod and dev—compromise blast radius."
  - q: "How do we know Wildcard TLS with cert-manager and DNS Providers is working?"
    a: "Define a leading metric tied to wildcard certificates health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---
Wildcard cert expired—HTTP challenge impossible for internal-only hosts.

## Why this shows up under real load


Wildcard cert expired—HTTP challenge impossible for internal-only hosts. That is the difference between demo-grade wildcard certificates and production-grade wildcard certificates.

Prioritize Wildcard TLS with cert-manager and DNS Providers many subdomains under one service mesh or ingress.

## Decision guide for platform teams


| Situation | Do | Avoid |
|-----------|-----|-------|
| Tier-1 downstream | Fail closed on wildcard certificates | Warn-only gates |
| Staging parity | Same suite as prod, smaller data | Different expectations |
| Incident response | One-click rollback path | Manual console edits |

## Configuration patterns that survived review


Patterns we kept for wildcard certificates:

## Rollout without blocking the business


Roll out in waves: internal consumers, 10% traffic or partitions, soak 48h, then full promote. Keep previous artifact version hot-swappable for one release cycle.

Pair rollout with shadow validation where possible — run new checks without blocking, compare results, then enforce.

## Monitoring and on-call signals


Dashboards for wildcard certificates belong in the same folder on-call opens first. Link runbooks from alert annotations — not a wiki nobody trusts.

Delete alerts that never fire; add thresholds that would have caught your last incident.

## Lessons from production


Wildcard TLS with cert-manager and DNS Providers is load-bearing once traffic and teams scale. Treat changes like any tier-1 deploy: feature flags, observability, rollback.

Document org-specific decisions — CIDRs, cluster names, approval gates — in internal docs that stay current.

## Reference configuration


```python
# Operational hook for wildcard certificates
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_cert_manager_wildcard_certs():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Networking pipelines touch ingestion, serving, and finance. Document interfaces where wildcard certificates gates hand off to downstream owners so failures are not bounced without context.

## Operating wildcard certificates at scale

After the first successful deploy of wildcard tls with cert-manager and dns providers, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of wildcard certificates settings with the on-call rotation — not only the primary author.

## Further reading

- https://opentelemetry.io/docs/
