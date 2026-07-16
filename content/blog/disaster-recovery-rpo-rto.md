---
title: "Planning for RPO and RTO"
slug: "disaster-recovery-rpo-rto"
description: "RPO and RTO define how much data you can lose and how fast you must recover. Backup tiers, failover drills, and aligning spend with business impact."
datePublished: "2025-09-30"
dateModified: "2025-09-30"
tags: ["DevOps", "Infrastructure"]
keywords: "RPO RTO, disaster recovery, business continuity, backup strategy, failover, recovery point objective"
faq:
  - q: "What is RPO?"
    a: "Recovery Point Objective (RPO) is the maximum acceptable age of data recovered after an outage — how much data loss measured in time is tolerable. RPO of one hour means backups or replication must be at most one hour stale; zero RPO requires synchronous replication."
  - q: "What is RTO?"
    a: "Recovery Time Objective (RTO) is the maximum acceptable downtime before service restoration. RTO of four hours means systems must be operational within four hours of disaster declaration. Lower RTO requires hot standby, automation, and rehearsed runbooks."
  - q: "How do RPO and RTO drive infrastructure decisions?"
    a: "Stricter RPO/RTO costs more — synchronous multi-region replication, active-active failover, continuous backup versus daily snapshots. Tier services by business impact: payment processing gets minutes RPO/RTO; internal wiki gets days. Document tiers and test against them quarterly."
---

Disaster recovery plans love diagrams with arrows between regions. What actually matters fits on an index card: **how much data can we lose** (RPO) and **how long can we stay down** (RTO). Everything else — backup vendor, multi-cloud fantasy, runbook font — follows from those two numbers.

## Definitions with teeth

**RPO (Recovery Point Objective)** — time-based data loss tolerance.

- RPO 24h → daily backups OK; lose up to yesterday
- RPO 5min → continuous replication or frequent incremental backup
- RPO 0 → synchronous write to secondary before ack (latency + cost)

**RTO (Recovery Time Objective)** — downtime tolerance.

- RTO 8h → restore from backup, manual DNS flip acceptable
- RTO 15min → warm standby, automated failover
- RTO ~0 → active-active with health-checked traffic shift

RPO is about **data**; RTO is about **service**. They decouple — you can have RPO 0 and RTO 2h if failover automation lags replication.

## Tiering services

| Tier | Example | Typical RPO | Typical RTO |
|---|---|---|---|
| Tier 0 | Payments, auth | 0–1 min | < 5 min |
| Tier 1 | Core API, orders | 5–15 min | < 1 h |
| Tier 2 | Analytics, CRM sync | 1–24 h | 4–24 h |
| Tier 3 | Internal tools | 24 h+ | Best effort |

Finance and product sign tiers — engineering implements and prices options.

## Architecture patterns by tier

**Tier 0–1:**

- Multi-AZ with auto-failover (RDS, Cloud SQL HA)
- Cross-region async replication with monitored lag
- Runbook-tested promote replica + DNS/connection string update
- Chaos drills: kill primary during business hours in staging

**Tier 2:**

- Hourly snapshots + WAL/binlog shipping
- Infrastructure as code to rebuild environment
- Documented restore procedure with time estimates

**Tier 3:**

- Daily backups, restore when someone notices

## Backup types and RPO

| Method | RPO capability |
|---|---|
| Nightly full snapshot | Up to 24h |
| Hourly incremental | ~1h |
| Continuous WAL/archive | Minutes |
| Sync replication | ~0 (commit on replica) |

Verify backups restore — untested backup is wishful thinking. Monthly restore drill to isolated environment; measure actual RTO.

```bash
# Example: measure restore time in drill
time pg_restore -d recovery_test latest.dump
# Compare elapsed to documented RTO
```

## Failover mechanics

Document sequence:

1. Declare incident — who decides failover
2. Stop writes to failed region (prevent split-brain)
3. Promote replica / shift traffic (Route53, Global Load Balancer)
4. Validate data integrity spot checks
5. Communicate status — internal and external
6. Post-incident: failback plan when primary healthy

Automate steps 2–4 where RTO demands it; human gate for declaration prevents flapping.

## Split-brain and data divergence

Async replication failover with lag → **lost transactions** equal lag window. Accept or use sync quorum for zero RPO tiers.

Split-brain (two primaries) corrupts data — use STONITH, consensus-based leaders (etcd, Raft), or cloud-managed failover with fencing.

## Cost reality

Active-active multi-region doubles infrastructure minimum. Most companies tier honestly instead of pretending everything is Tier 0.

Calculate **cost of downtime** vs DR spend: `$lost_revenue_per_hour × expected outage probability` compared to replication and drill costs.

## Compliance mapping

SOC2, HIPAA, PCI often require documented RPO/RTO and annual tests. Auditors want drill logs, not slide decks.

## Runbook essentials

- Contact tree and decision authority
- Per-system restore commands (copy-paste ready)
- Dependency order (database before app servers)
- Communication templates
- Last successful drill date and actual measured RTO

Update runbooks when architecture changes — stale runbooks kill RTO faster than disasters.

## DR tier classification

Classify systems into tiers with explicit RPO/RTO targets:

| Tier | RPO | RTO | Example systems | Strategy |
|---|---|---|---|---|
| 0 — Critical | 0 | <15 min | Payment processing | Sync replication, active-active |
| 1 — High | <1 hour | <1 hour | User auth, core API | Async replication, warm standby |
| 2 — Medium | <4 hours | <4 hours | Analytics, search | Daily backups, cold standby |
| 3 — Low | <24 hours | <24 hours | Internal tools, logs | Weekly backups, rebuild from IaC |

Don't assign Tier 0 to everything — cost scales exponentially. Honest tiering beats aspirational SLAs that aren't funded.

## Game day exercises

DR drills prove RTO/RPO claims — schedule quarterly:

```
Game day script:
1. Simulate primary region failure (network partition or kill switch)
2. Execute failover runbook — timed
3. Verify application functional in DR region
4. Measure actual RTO (time to recovery)
5. Verify data loss within RPO (compare record counts)
6. Fail back to primary — timed separately
7. Document gaps between expected and actual RTO/RTO
```

Actual measured RTO is always longer than planned — update runbooks with real timings, not estimates.

## Backup validation

Backups that aren't tested aren't backups:

```bash
# Monthly backup restore test
pg_restore -d restore_test backup_2024-12-27.dump
psql restore_test -c "SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '1 day'"
# Compare count with production — should match within RPO window
```

Automate restore test monthly. Alert if restore fails or row count diverges beyond RPO tolerance.

## Failure modes

- **DR never tested** — runbook errors discovered during actual disaster
- **Async replication with unknown lag** — RPO violated on failover
- **Split-brain after failover** — two primaries corrupt data
- **Backup restore never validated** — backup corrupted or incomplete
- **All systems Tier 0** — DR cost unsustainable; honest tiering abandoned

## Production checklist

- Every system assigned DR tier with documented RPO/RTO
- Failover runbook with copy-paste commands (not prose)
- Game day exercise quarterly with measured actual RTO
- Backup restore validated monthly
- Split-brain prevention (STONITH or consensus-based failover)
- Runbook updated within 1 week of architecture changes

Drill failover quarterly with timed runbooks — RTO numbers in slide decks mean nothing until someone executes restore under pressure.

## Resources

- [AWS — Disaster recovery whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-workloads-on-aws.html)
- [Google Cloud — DR planning guide](https://cloud.google.com/architecture/dr-scenarios-planning-guide)
- [NIST SP 800-34 — Contingency planning](https://csrc.nist.gov/publications/detail/sp/800-34/rev-1/final)
- [Azure — RTO and RPO targets](https://learn.microsoft.com/en-us/azure/architecture/framework/resiliency/disaster-recovery-azure-applications)
- [ISO 22301 — Business continuity management](https://www.iso.org/standard/75106.html)
