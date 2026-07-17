---
title: "Helm Values Schema Validation"
slug: "devops-helm-values-schema-validation"
description: "Enforce values.schema.json on charts to reject invalid input early."
datePublished: "2026-10-13"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Helm"
keywords: "Helm values schema"
faq:
  - q: "Why values.schema.json?"
    a: "Fail helm template in CI on typos and wrong types before apply—prevents silent nil defaults breaking prod."
  - q: "Required vs optional values?"
    a: "Mark prod-critical fields required; document defaults in schema descriptions for IDE autocomplete."
  - q: "Schema on library charts?"
    a: "Consumer charts extend schema—library exposes helper JSON schema fragments for shared keys."
  - q: "Breaking schema changes?"
    a: "Semver major on chart when removing or retyping required fields—consumers pin until migration."
---
A typo replicas: "three" passed review because YAML quoted string; schema validation in CI now fails non-integer before helm apply.

## values.schema.json

JSON Schema on chart values—required prod fields, types, enums, descriptions for IDE hints.

Production teams running helm values schema validation learned that values.schema.json regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for values.schema.json: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument values.schema.json with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for values.schema.json: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for values.schema.json belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in values.schema.json configs.

Capacity note: estimate peak concurrency for values.schema.json, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm values schema validation: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for values.schema.json: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## CI integration

helm lint with schema on every PR; kubeconform optional for rendered manifests.

Production teams running helm values schema validation learned that ci integration regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for ci integration: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ci integration with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ci integration: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ci integration belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ci integration configs.

Capacity note: estimate peak concurrency for ci integration, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm values schema validation: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ci integration: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Library chart schemas

Subchart schema fragments composed in parent—document required consumer overrides.

Production teams running helm values schema validation learned that library chart schemas
regressions appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations
until load replay used production timestamps.

Runbook for library chart schemas: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument library chart schemas with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for library chart schemas: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for library chart schemas belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in library chart schemas configs.

Capacity note: estimate peak concurrency for library chart schemas, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm values schema validation: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for library chart schemas: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Breaking changes

Major chart bump when removing required key or changing type—migration guide in CHANGELOG.

Production teams running helm values schema validation learned that breaking changes regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for breaking changes: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument breaking changes with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for breaking changes: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for breaking changes belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in breaking changes configs.

Capacity note: estimate peak concurrency for breaking changes, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm values schema validation: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for breaking changes: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Examples

values.yaml annotated to satisfy schema—copy-paste safe for service teams.

Production teams running helm values schema validation learned that examples regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for examples: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument examples with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for examples: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for examples belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in examples configs.

Capacity note: estimate peak concurrency for examples, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm values schema validation: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for examples: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.
