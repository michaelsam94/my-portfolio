---
title: "Helm Chart Testing with chart-testing and helm-unittest"
slug: "devops-helm-chart-testing-ct-lint"
description: "Validate Helm charts before release with ct lint/install and helm-unittest."
datePublished: "2026-10-10"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Helm"
keywords: "chart-testing, helm-unittest"
faq:
  - q: "What does chart-testing (ct) lint catch?"
    a: "Missing Chart.yaml fields, invalid templates, wrong indentation, and version bump requirements on changed charts."
  - q: "ct install versus lint only?"
    a: "Lint in every PR; install against kind cluster for charts touching CRDs, hooks, or ingress classes—catch runtime template errors."
  - q: "Version bump policy?"
    a: "Any chart file change requires Chart.yaml version increment—ct enforces so OCI/registry consumers get immutable semver."
  - q: "Monorepo chart paths?"
    a: "ct list-changed against merge base—only test charts touched in PR plus dependents."
---
A merged Chart.yaml typo left templates unrenderable in prod only when CRD subchart installed—ct install in kind would have caught it in nine minutes.

## ct lint in CI

chart_schema.yaml and yaml lint on every changed chart in monorepo—list-changed against merge base.

Production teams running helm chart testing ct lint learned that ct lint in ci regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ct lint in ci: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ct lint in ci with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ct lint in ci: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ct lint in ci belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ct lint in ci configs.

Capacity note: estimate peak concurrency for ct lint in ci, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart testing ct lint: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ct lint in ci: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## ct install scope

Full install for charts touching CRDs, webhooks, or ingress—lint-only insufficient for runtime failures.

Production teams running helm chart testing ct lint learned that ct install scope regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ct install scope: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ct install scope with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ct install scope: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ct install scope belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ct install scope configs.

Capacity note: estimate peak concurrency for ct install scope, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart testing ct lint: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ct install scope: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Version bump enforcement

Any file change requires Chart version increment—immutable semver for OCI consumers.

Production teams running helm chart testing ct lint learned that version bump enforcement
regressions appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations
until load replay used production timestamps.

Runbook for version bump enforcement: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument version bump enforcement with low-cardinality metrics tied to user-visible SLIs—error
rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for version bump enforcement: quarterly staging injection with rollback under fifteen
minutes using linked runbook only—update runbook with what broke.

Ownership for version bump enforcement belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in version bump enforcement configs.

Capacity note: estimate peak concurrency for version bump enforcement, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm chart testing ct lint: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for version bump enforcement: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Fixture values

ci/lint-values.yaml and ci/install-values.yaml exercise required fields—schema validation plus render.

Production teams running helm chart testing ct lint learned that fixture values regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for fixture values: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument fixture values with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for fixture values: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for fixture values belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in fixture values configs.

Capacity note: estimate peak concurrency for fixture values, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart testing ct lint: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for fixture values: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Flake control

Kind cluster reuse with cleanup; timeout budgets per chart tier documented.

Production teams running helm chart testing ct lint learned that flake control regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for flake control: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument flake control with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for flake control: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for flake control belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in flake control configs.

Capacity note: estimate peak concurrency for flake control, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart testing ct lint: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for flake control: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
