---
title: "Helm Dependency Management and Subchart Patterns"
slug: "devops-helm-dependency-management"
description: "Manage Helm dependencies: conditions, aliases, OCI registries, Chart.lock."
datePublished: "2026-10-11"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Helm"
keywords: "Helm dependencies, Chart.lock"
faq:
  - q: "Helm dependency update workflow?"
    a: "Chart.lock committed; renovate or dependabot bumps; CI runs ct lint and helm template on lock changes."
  - q: "Subchart version pinning?"
    a: "Pin exact semver in Chart.yaml dependencies—floating ranges break reproducible deploys when upstream publishes breaking minors."
  - q: "Vendor vs remote dependency?"
    a: "Vendor tgz into charts/ for air-gapped; document update ritual—remote repos need helm repo credentials in CI."
  - q: "Breaking subchart upgrades?"
    a: "Read upstream changelog; run helm diff against staging; migrate values keys with schema validation."
---
A floating subchart semver range pulled a breaking minor Friday evening; twenty releases failed template render because ingress API version changed upstream.

## Pin exact versions

Chart.yaml dependencies semver exact; Chart.lock committed; renovate opens tested bump PRs.

Production teams running helm dependency management learned that pin exact versions regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for pin exact versions: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument pin exact versions with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for pin exact versions: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for pin exact versions belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in pin exact versions configs.

Capacity note: estimate peak concurrency for pin exact versions, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm dependency management: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for pin exact versions: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Update ritual

helm dependency update, ct lint, helm template, helm diff staging—changelog review mandatory.

Production teams running helm dependency management learned that update ritual regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for update ritual: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument update ritual with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for update ritual: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for update ritual belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in update ritual configs.

Capacity note: estimate peak concurrency for update ritual, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm dependency management: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for update ritual: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Air-gapped vendoring

charts/*.tgz vendored with oras copy mirror job—document refresh cadence.

Production teams running helm dependency management learned that air-gapped vendoring regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for air-gapped vendoring: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument air-gapped vendoring with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for air-gapped vendoring: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for air-gapped vendoring belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in air-gapped vendoring configs.

Capacity note: estimate peak concurrency for air-gapped vendoring, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm dependency management: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for air-gapped vendoring: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Breaking migrations

Values key renames documented in consumer UPGRADE.md—schema validation catches typos not semantics.

Production teams running helm dependency management learned that breaking migrations regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for breaking migrations: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument breaking migrations with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for breaking migrations: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for breaking migrations belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in breaking migrations configs.

Capacity note: estimate peak concurrency for breaking migrations, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm dependency management: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for breaking migrations: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Security patches

Dependabot on chart deps; CVE SLA per severity tied to platform policy.

Production teams running helm dependency management learned that security patches regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for security patches: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument security patches with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for security patches: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for security patches belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in security patches configs.

Capacity note: estimate peak concurrency for security patches, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm dependency management: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for security patches: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
