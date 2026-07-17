---
title: "Helm OCI Registry Migration"
slug: "devops-helm-oci-registry-migration"
description: "Migrate Helm charts from HTTP chart museums to OCI registries with cosign signing, CI updates, and consumer cutover without breaking deploy pipelines."
datePublished: "2026-11-10"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Helm"
  - "Supply Chain"
keywords: "Helm OCI, chart registry migration, helm push, OCI artifacts, chart museum deprecation"
faq:
  - q: "Why OCI for charts?"
    a: "Same registry as container images—unified auth, cosign sign charts like images."
  - q: "helm push migration?"
    a: "Re-publish semver charts to oci://registry; update helm repo URLs in CI and Argo."
  - q: "Helm 3 OCI gotchas?"
    a: "Chart version in tag and metadata must match; avoid mutable tags for prod."
  - q: "Air-gapped mirror?"
    a: "oras copy charts between registries—document sync job in DR runbook."
---
Classic helm repo index lagged behind OCI push; migration to oci:// unified auth with container registry and enabled cosign sign on chart layers.

## Push workflow

helm package; helm push oci://registry/chart; semver tag immutable.

Production teams running helm oci registry migration learned that push workflow regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for push workflow: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument push workflow with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for push workflow: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for push workflow belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in push workflow configs.

Capacity note: estimate peak concurrency for push workflow, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm oci registry migration: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for push workflow: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Consumer update

Chart.yaml repository oci URL; Argo repo type oci; CI login same as docker.

Production teams running helm oci registry migration learned that consumer update regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for consumer update: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument consumer update with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for consumer update: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for consumer update belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in consumer update configs.

Capacity note: estimate peak concurrency for consumer update, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm oci registry migration: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for consumer update: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Gotchas

Chart version in artifact must match tag; avoid mutable latest for prod.

Production teams running helm oci registry migration learned that gotchas regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for gotchas: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument gotchas with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for gotchas: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for gotchas belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in gotchas configs.

Capacity note: estimate peak concurrency for gotchas, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm oci registry migration: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for gotchas: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Mirror DR

oras copy charts to DR registry; sync job in runbook.

Production teams running helm oci registry migration learned that mirror dr regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for mirror dr: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument mirror dr with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for mirror dr: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for mirror dr belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in mirror dr configs.

Capacity note: estimate peak concurrency for mirror dr, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm oci registry migration: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for mirror dr: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Legacy coexist

Dual publish during migration window; deprecate http index with deadline.

Production teams running helm oci registry migration learned that legacy coexist regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for legacy coexist: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument legacy coexist with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for legacy coexist: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for legacy coexist belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in legacy coexist configs.

Capacity note: estimate peak concurrency for legacy coexist, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm oci registry migration: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for legacy coexist: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
