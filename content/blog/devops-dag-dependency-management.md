---
title: "Cross-DAG Dependencies and Data Contracts"
slug: "devops-dag-dependency-management"
description: "Manage cross-DAG deps with datasets, external sensors, and contracts."
datePublished: "2026-08-26"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Data Pipelines"
  - "Platform"
keywords: "DAG dependencies, Airflow datasets, data contracts, ExternalTaskSensor, cross-DAG"
faq:
  - q: "When should ExternalTaskSensor be replaced with Airflow Datasets?"
    a: "When upstream completion—not a specific task_id—is the dependency signal. Datasets remove poll loops, express lineage natively, and decouple schedules."
  - q: "Why do ExternalTaskSensors overload the Airflow metadata database?"
    a: "Poke-mode sensors query task state every interval; hundreds of sensors can generate thousands of SQL statements per minute against the metastore."
  - q: "What belongs in a cross-DAG data contract?"
    a: "Stable dataset URI, schema version, partition semantics, freshness SLA, owner team, and breaking-change policy enforced in CI."
  - q: "How do you detect cross-DAG deadlocks before production?"
    a: "Import all DAGs in CI and fail on cycles; alert on sensors in up_for_retry >1 hour; alert when downstream expected start passes without dag_run."
---
Finance mart never scheduled Tuesday—upstream renamed a task_id Friday; ExternalTaskSensors waited forever.

## ExternalTaskSensor costs

Rename fragility breaks silent string contracts. Poke mode hammers the metastore. execution_date alignment fails across schedules and DST. Deferrable sensors with Triggerer reduce worker and DB load during migration.

A production team running dag dependency management discovered that externaltasksensor costs
failures show up only when upstream dependencies shift traffic mix—staging load tests with uniform
QPS missed the regression until Black Friday.

Runbook entry for externaltasksensor costs: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dag dependency management, instrument externaltasksensor costs with low-cardinality metrics tied
to user-visible outcomes: error rate, tail latency, freshness, or cost per successful
operation—avoid paging on vanity gauges that never correlated with past incidents.

Game day scenario for externaltasksensor costs: inject partial outage in staging quarterly, verify
on-call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for externaltasksensor costs belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers should deploy a safe canary within one week using
that doc alone.

Change management for dag dependency management: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in
externaltasksensor costs configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for externaltasksensor costs, multiply
by headroom factor one-point-five to two, compare against cloud quotas and license limits before
launch week—not during the first outage.

## Dataset scheduling

Producer outlets publish stable URIs; consumers schedule on dataset updates. Backfill must emit dataset events or historical partitions stall downstream without errors.

A production team running dag dependency management discovered that dataset scheduling failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for dataset scheduling: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dag dependency management, instrument dataset scheduling with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for dataset scheduling: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for dataset scheduling belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dag dependency management: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in dataset
scheduling configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for dataset scheduling, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Data contracts

Semver schema, partition keys, freshness SLA, and owner on-call. CI fails upstream column drops without version bump; compat shim tasks bridge one-release renames.

A production team running dag dependency management discovered that data contracts failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for data contracts: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dag dependency management, instrument data contracts with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for data contracts: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for data contracts belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dag dependency management: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in data contracts
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for data contracts, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Dependency observability

Dashboard minutes since dataset update, sensor retry counts, lineage in catalog. Alert missing downstream dag_run at SLA—not only upstream task failure.

A production team running dag dependency management discovered that dependency observability
failures show up only when upstream dependencies shift traffic mix—staging load tests with uniform
QPS missed the regression until Black Friday.

Runbook entry for dependency observability: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dag dependency management, instrument dependency observability with low-cardinality metrics tied
to user-visible outcomes: error rate, tail latency, freshness, or cost per successful
operation—avoid paging on vanity gauges that never correlated with past incidents.

Game day scenario for dependency observability: inject partial outage in staging quarterly, verify
on-call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for dependency observability belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers should deploy a safe canary within one week using
that doc alone.

Change management for dag dependency management: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in dependency
observability configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for dependency observability, multiply
by headroom factor one-point-five to two, compare against cloud quotas and license limits before
launch week—not during the first outage.

## Migration playbook

Rank sensors by poke frequency, dual-write outlets one release, switch consumer schedules, delete sensors, validate DB CPU drop.

A production team running dag dependency management discovered that migration playbook failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for migration playbook: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dag dependency management, instrument migration playbook with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for migration playbook: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for migration playbook belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dag dependency management: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in migration
playbook configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for migration playbook, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## ExternalTaskSensor versus Dataset scheduling

```python
wait_stripe = ExternalTaskSensor(
    task_id="wait_stripe_extract",
    external_dag_id="payments_raw",
    external_task_id="extract_stripe_charges",  # breaks on rename
    mode="reschedule",
    poke_interval=300,
)

@task(outlets=[Dataset("warehouse://raw/stripe/charges")])
def extract_charges():
    ...

with DAG("finance_mart", schedule=[Dataset("warehouse://raw/stripe/charges")]):
    build_mart()
```

Migrate high-churn sensors first by ranking metastore poke frequency. Dual-write dataset outlets for one release while sensors remain, then delete sensors and watch DB CPU fall.

## Backfill and contract CI

Historical replays fail when upstream backfill does not emit dataset events. Standardize a backfill playbook: announce cross-team, freeze consumer deploys, run upstream with bounded concurrency, verify dataset timestamps, then trigger downstream with documented execution_date alignment. Store contracts in git beside dbt models—consumer CI fails when upstream drops columns without schema_version bump.
