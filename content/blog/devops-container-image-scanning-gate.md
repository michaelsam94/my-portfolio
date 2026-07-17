---
title: "Container Image Scanning Gates in CI/CD"
slug: "devops-container-image-scanning-gate"
description: "Block deploy on critical CVE with Trivy/Grype and exception workflow."
datePublished: "2026-10-22"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Security"
  - "CI/CD"
keywords: "container scanning, Trivy"
faq:
  - q: "Gate on what severity?"
    a: "Block CRITICAL fixable CVEs; warn HIGH with SLA; exception ticket with expiry for unfixable base."
  - q: "Scan timing?"
    a: "Scan in CI after build; rescan on schedule—new CVE DB entries affect old digests."
  - q: "Distroless false positives?"
    a: "Tune policy for minimal images; use VEX statements when upstream documents non-exploitable."
  - q: "Admission vs CI gate?"
    a: "Both—CI prevents merge; admission catches bypass or retagged images."
---
Critical CVE in base image merged Friday; admission gate now blocks CRITICAL fixable CVEs in prod namespace—exception ticket with expiry for unfixable.

## CI gate

Trivy or grype scan after build; fail on CRITICAL fixable; HIGH SLA warn.

Production teams running container image scanning gate learned that ci gate regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ci gate: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ci gate with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for ci gate: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for ci gate belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ci gate configs.

Capacity note: estimate peak concurrency for ci gate, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for container image scanning gate: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ci gate: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Scheduled rescan

New CVE DB entries affect old digests—weekly rescan deployed images.

Production teams running container image scanning gate learned that scheduled rescan regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for scheduled rescan: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument scheduled rescan with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for scheduled rescan: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for scheduled rescan belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in scheduled rescan configs.

Capacity note: estimate peak concurrency for scheduled rescan, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image scanning gate: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for scheduled rescan: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Admission

Policy controller verify in cluster catches retag bypass of CI.

Production teams running container image scanning gate learned that admission regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for admission: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument admission with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for admission: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for admission belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in admission configs.

Capacity note: estimate peak concurrency for admission, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for container image scanning gate: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for admission: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Exceptions

VEX or ticket with expiry; quarterly review of open exceptions.

Production teams running container image scanning gate learned that exceptions regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for exceptions: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument exceptions with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for exceptions: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for exceptions belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in exceptions configs.

Capacity note: estimate peak concurrency for exceptions, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for container image scanning gate: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for exceptions: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Distroless tuning

Reduce false positives; document base image update cadence.

Production teams running container image scanning gate learned that distroless tuning regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for distroless tuning: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument distroless tuning with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for distroless tuning: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for distroless tuning belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in distroless tuning configs.

Capacity note: estimate peak concurrency for distroless tuning, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image scanning gate: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for distroless tuning: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.
