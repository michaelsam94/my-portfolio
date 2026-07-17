---
title: "Container Image Signing with Cosign in CI"
slug: "devops-container-image-signing-cosign"
description: "Sign and verify container images in CI/CD with cosign and policy controllers."
datePublished: "2026-05-08"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "CI/CD"
  - "Security"
keywords: "cosign, image signing, supply chain"
faq:
  - q: "Cosign sign in CI when?"
    a: "After image build and vulnerability gate pass; sign digest not floating tag."
  - q: "Admission verify?"
    a: "Kyverno or policy-controller requires cosign signature from trusted issuer before pod schedules."
  - q: "Rekor transparency?"
    a: "Optional public log for audit; private deployments may use internal transparency log."
  - q: "Keyless signing?"
    a: "OIDC federation from GitHub/GitLab to cosign—short-lived certificates reduce long-lived key risk."
---
A retagged image bypassed CI scan; admission policy without cosign verify allowed deploy until policy-controller required signature from trusted GitHub OIDC issuer.

## Sign digest in CI

cosign sign after build and scan pass—never sign mutable latest tag only.

Production teams running container image signing cosign learned that sign digest in ci regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for sign digest in ci: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument sign digest in ci with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for sign digest in ci: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for sign digest in ci belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in sign digest in ci configs.

Capacity note: estimate peak concurrency for sign digest in ci, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image signing cosign: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for sign digest in ci: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Admission verify

Kyverno verifyImages or policy-controller cluster policy—reject unsigned in prod namespaces.

Production teams running container image signing cosign learned that admission verify regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for admission verify: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument admission verify with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for admission verify: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for admission verify belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in admission verify configs.

Capacity note: estimate peak concurrency for admission verify, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image signing cosign: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for admission verify: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Keyless OIDC

GitHub Actions federated identity to cosign—no long-lived COSIGN_PRIVATE_KEY in repo.

Production teams running container image signing cosign learned that keyless oidc regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for keyless oidc: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument keyless oidc with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for keyless oidc: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for keyless oidc belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in keyless oidc configs.

Capacity note: estimate peak concurrency for keyless oidc, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image signing cosign: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for keyless oidc: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Transparency

Rekor optional; internal log for air-gapped with same verify UX.

Production teams running container image signing cosign learned that transparency regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for transparency: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument transparency with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for transparency: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for transparency belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in transparency configs.

Capacity note: estimate peak concurrency for transparency, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for container image signing cosign: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for transparency: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Exceptions

Break-glass unsigned deploy requires ticket and auto-expire namespace label.

Production teams running container image signing cosign learned that exceptions regressions appear
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

Security review for container image signing cosign: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for exceptions: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

```bash
cosign sign --yes "${IMAGE}@${DIGEST}"
cosign verify --certificate-identity-regexp='https://github.com/org/repo' "${IMAGE}@${DIGEST}"
```
Admission policy rejects pods in prod without verified signature from trusted issuer.
