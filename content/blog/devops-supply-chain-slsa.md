---
title: "SLSA and Supply Chain Security for Artifacts"
slug: "devops-supply-chain-slsa"
description: "Implement SLSA provenance, signed commits, and verified builds."
datePublished: "2026-10-27"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Security"
  - "Supply Chain"
keywords: "SLSA, supply chain security"
faq:
  - q: "When should teams prioritize SLSA and Supply Chain Security for Artifacts?"
    a: "Software supply chain compliance initiatives."
  - q: "What is the most common mistake with SLSA provenance?"
    a: "Provenance generated in same pipeline it attests—weak trust."
  - q: "Fail open or fail closed on scanner outage?"
    a: "Fail closed for merge to main when scanning CI is down; break-glass with audit for incidents. Never silently skip secret scans on release branches."
  - q: "How do we know SLSA and Supply Chain Security for Artifacts is working?"
    a: "Define a leading metric tied to SLSA provenance health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---
Dependency confusion package almost merged—provenance check missing.

## Why this shows up under real load


Dependency confusion package almost merged—provenance check missing. That is the difference between demo-grade SLSA provenance and production-grade SLSA provenance.

Prioritize SLSA and Supply Chain Security for Artifacts software supply chain compliance initiatives.

## Decision guide for platform teams


| Situation | Do | Avoid |
|-----------|-----|-------|
| Tier-1 downstream | Fail closed on SLSA provenance | Warn-only gates |
| Staging parity | Same suite as prod, smaller data | Different expectations |
| Incident response | One-click rollback path | Manual console edits |

## Configuration patterns that survived review


Patterns we kept for SLSA provenance:

## Rollout without blocking the business


Roll out in waves: internal consumers, 10% traffic or partitions, soak 48h, then full promote. Keep previous artifact version hot-swappable for one release cycle.

Pair rollout with shadow validation where possible — run new checks without blocking, compare results, then enforce.

## Monitoring and on-call signals


Dashboards for SLSA provenance belong in the same folder on-call opens first. Link runbooks from alert annotations — not a wiki nobody trusts.

Delete alerts that never fire; add thresholds that would have caught your last incident.

## Lessons from production


SLSA and Supply Chain Security for Artifacts is load-bearing once traffic and teams scale. Treat changes like any tier-1 deploy: feature flags, observability, rollback.

Document org-specific decisions — CIDRs, cluster names, approval gates — in internal docs that stay current.

## Reference configuration


```python
# Operational hook for SLSA provenance
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_supply_chain_slsa():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Evidence for auditors

Security controls for production paths need immutable logs: who changed policy, which CI run scanned artifacts, and which break-glass session touched RBAC. Prefer OIDC over long-lived keys; rotate with overlap windows.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Security pipelines touch ingestion, serving, and finance. Document interfaces where SLSA provenance gates hand off to downstream owners so failures are not bounced without context.

## Operating SLSA provenance at scale

After the first successful deploy of slsa and supply chain security for artifacts, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SLSA provenance settings with the on-call rotation — not only the primary author.

## Further reading

- https://opentelemetry.io/docs/
