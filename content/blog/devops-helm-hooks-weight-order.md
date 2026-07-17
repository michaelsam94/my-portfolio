---
title: "Helm Hooks: Weights, Ordering, and Cleanup"
slug: "devops-helm-hooks-weight-order"
description: "Configure pre/post install hooks with correct weights and delete policies."
datePublished: "2026-10-19"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Helm"
keywords: "Helm hooks, hook-weight"
faq:
  - q: "Hook weights explained?"
    a: "Lower weight runs first among same hook type; negative weights run before positive on pre-install."
  - q: "Hook delete policies?"
    a: "before-hook-creation vs hook-succeeded—wrong policy leaves stale hook pods blocking upgrades."
  - q: "Database migration hooks?"
    a: "Run pre-upgrade with weight -5; backup Job weight -10; app Deploy weight 0—document in runbook."
  - q: "Hook failures block release?"
    a: "Yes for migrations; optional for smoke Jobs only if documented—failed hook leaves release pending."
---
Database migration hook ran after Deployment rollout because weight defaulted wrong; bad schema served traffic for eleven minutes until manual scale-down.

## Weight ordering

pre-upgrade backup Job weight -10, migration weight -5, app Deploy weight 0—document standard.

Production teams running helm hooks weight order learned that weight ordering regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for weight ordering: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument weight ordering with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for weight ordering: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for weight ordering belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in weight ordering configs.

Capacity note: estimate peak concurrency for weight ordering, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm hooks weight order: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for weight ordering: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Delete policies

before-hook-creation cleans stale hook pods; hook-succeeded retains for debug only when needed.

Production teams running helm hooks weight order learned that delete policies regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for delete policies: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument delete policies with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for delete policies: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for delete policies belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in delete policies configs.

Capacity note: estimate peak concurrency for delete policies, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm hooks weight order: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for delete policies: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Idempotent migrations

Hooks must tolerate retry—partial migration leaves release pending with clear logs.

Production teams running helm hooks weight order learned that idempotent migrations regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for idempotent migrations: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument idempotent migrations with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for idempotent migrations: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for idempotent migrations belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in idempotent migrations configs.

Capacity note: estimate peak concurrency for idempotent migrations, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm hooks weight order: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for idempotent migrations: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Test hooks in CI

ct install on kind runs full hook chain with test database container.

Production teams running helm hooks weight order learned that test hooks in ci regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for test hooks in ci: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument test hooks in ci with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for test hooks in ci: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for test hooks in ci belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in test hooks in ci configs.

Capacity note: estimate peak concurrency for test hooks in ci, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm hooks weight order: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for test hooks in ci: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Argo sync waves

Align helm hook weights with Argo sync wave annotations when hybrid GitOps.

Production teams running helm hooks weight order learned that argo sync waves regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for argo sync waves: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument argo sync waves with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for argo sync waves: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for argo sync waves belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in argo sync waves configs.

Capacity note: estimate peak concurrency for argo sync waves, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm hooks weight order: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for argo sync waves: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
