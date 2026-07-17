---
title: "Monorepo Path Filters and Affected Targets"
slug: "devops-monorepo-path-filters"
description: "Run CI only for changed paths in monorepos with path filters and bazel/gazelle."
datePublished: "2026-05-15"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "CI/CD"
  - "Platform"
keywords: "monorepo, path filters"
faq:
  - q: "Path filter too aggressive?"
    a: "Missed changes to shared libs—use dependency graph (bazel query, nx affected) not only diff paths."
  - q: "Always-run paths?"
    a: "Lockfiles, CI config, shared proto dirs trigger full or widened test suite."
  - q: "False skip incident?"
    a: "Postmortem adds CODEOWNERS path to always-run list—document in platform runbook."
  - q: "Metrics?"
    a: "Track skipped vs executed jobs ratio and wall-clock savings—prove value to skeptics."
---
README typo triggered ninety-minute full test suite; path filters plus nx affected cut median PR CI from forty-seven to eight minutes.

## Path filters

GitHub paths filter with shared lockfile and workflow always-run exceptions.

Production teams running monorepo path filters learned that path filters regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for path filters: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument path filters with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for path filters: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for path filters belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in path filters configs.

Capacity note: estimate peak concurrency for path filters, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for monorepo path filters: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for path filters: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Dependency graph

nx affected or bazel query rdeps—not diff paths alone for shared libs.

Production teams running monorepo path filters learned that dependency graph regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for dependency graph: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument dependency graph with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for dependency graph: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for dependency graph belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in dependency graph configs.

Capacity note: estimate peak concurrency for dependency graph, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for monorepo path filters: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for dependency graph: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Safety net

Nightly full suite; CODEOWNERS on shared libs trigger widened tests on touch.

Production teams running monorepo path filters learned that safety net regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for safety net: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument safety net with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for safety net: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for safety net belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in safety net configs.

Capacity note: estimate peak concurrency for safety net, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for monorepo path filters: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for safety net: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## False skip response

Postmortem adds path to always-run; document in platform runbook.

Production teams running monorepo path filters learned that false skip response regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for false skip response: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument false skip response with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for false skip response: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for false skip response belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in false skip response configs.

Capacity note: estimate peak concurrency for false skip response, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for monorepo path filters: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for false skip response: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Metrics

Skipped versus executed jobs; wall-clock savings; false skip incident count.

Production teams running monorepo path filters learned that metrics regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for metrics: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument metrics with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for metrics: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for metrics belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in metrics configs.

Capacity note: estimate peak concurrency for metrics, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for monorepo path filters: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for metrics: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.
