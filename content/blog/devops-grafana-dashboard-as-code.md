---
title: "Grafana Dashboards as Code with Jsonnet or Terraform"
slug: "devops-grafana-dashboard-as-code"
description: "Version control Grafana dashboards and provision via GitOps."
datePublished: "2026-06-03"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "GitOps"
keywords: "Grafana as code, dashboards"
faq:
  - q: "Grafonnet vs JSON?"
    a: "Jsonnet modules reduce duplication—env-specific overrides in libsonnet parameters."
  - q: "CI for dashboards?"
    a: "lint jsonnet, render JSON, grafana diff or preview API—no manual UI save in prod folder."
  - q: "UID stability?"
    a: "Fixed dashboard UIDs in code—import without duplicate dashboards on re-apply."
  - q: "Folder permissions?"
    a: "Terraform or Grafana operator manages folder RBAC—code owns structure not individuals."
---
Manual dashboard edits in UI diverged from git; jsonnet Grafonnet modules plus CI lint restored single source of truth and fixed UID duplicates on import.

## Jsonnet structure

lib/ panels reusable; environments/prod params for datasource UID differences.

Production teams running grafana dashboard as code learned that jsonnet structure regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for jsonnet structure: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument jsonnet structure with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for jsonnet structure: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for jsonnet structure belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in jsonnet structure configs.

Capacity note: estimate peak concurrency for jsonnet structure, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for grafana dashboard as code: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for jsonnet structure: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## CI pipeline

jsonnetfmt lint; render to JSON; optional grafana API diff on PR preview.

Production teams running grafana dashboard as code learned that ci pipeline regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ci pipeline: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ci pipeline with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ci pipeline: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ci pipeline belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ci pipeline configs.

Capacity note: estimate peak concurrency for ci pipeline, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for grafana dashboard as code: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ci pipeline: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## UID stability

Fixed dashboard UIDs in code—re-import without duplicate dashboards.

Production teams running grafana dashboard as code learned that uid stability regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for uid stability: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument uid stability with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for uid stability: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for uid stability belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in uid stability configs.

Capacity note: estimate peak concurrency for uid stability, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for grafana dashboard as code: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for uid stability: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## RBAC as code

Terraform or Grafana operator for folder permissions—not manual UI sharing.

Production teams running grafana dashboard as code learned that rbac as code regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for rbac as code: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument rbac as code with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for rbac as code: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for rbac as code belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in rbac as code configs.

Capacity note: estimate peak concurrency for rbac as code, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for grafana dashboard as code: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for rbac as code: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Anti-pattern

Screenshot-driven dashboard requests without code change—product process routes through PR.

Production teams running grafana dashboard as code learned that anti-pattern regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for anti-pattern: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument anti-pattern with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for anti-pattern: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for anti-pattern belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in anti-pattern configs.

Capacity note: estimate peak concurrency for anti-pattern, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for grafana dashboard as code: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for anti-pattern: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
