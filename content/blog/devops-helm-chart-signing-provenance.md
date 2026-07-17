---
title: "Helm Chart Signing and Provenance"
slug: "devops-helm-chart-signing-provenance"
description: "Sign charts with cosign and verify before install."
datePublished: "2026-10-17"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Helm"
  - "Security"
keywords: "Helm signing, cosign"
faq:
  - q: "Helm provenance .prov files?"
    a: "Sign chart package digest; helm install --verify in CI and prod pipelines rejects tampered tgz."
  - q: "Notation vs legacy provenance?"
    a: "Modern OCI charts may use cosign/notation signatures—align verify step with registry type."
  - q: "Key rotation?"
    a: "Dual-sign period with old and new keys trusted; revoke compromised key in verify config immediately."
  - q: "Who holds signing key?"
    a: "Release bot with HSM-backed key—developers PR charts, bot signs after ct passes."
---
Supply chain audit required proof charts unchanged since CI build; unsigned tgz from mirror bucket failed compliance until provenance verify wired in install pipeline.

## Sign chart packages

helm package then sign with provenance or cosign; verify in CD before apply.

Production teams running helm chart signing provenance learned that sign chart packages regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for sign chart packages: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument sign chart packages with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for sign chart packages: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for sign chart packages belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in sign chart packages configs.

Capacity note: estimate peak concurrency for sign chart packages, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm chart signing provenance: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for sign chart packages: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Release bot signing

Humans PR chart changes; bot signs after ct passes—keys in HSM not laptops.

Production teams running helm chart signing provenance learned that release bot signing regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for release bot signing: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument release bot signing with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for release bot signing: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for release bot signing belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in release bot signing configs.

Capacity note: estimate peak concurrency for release bot signing, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm chart signing provenance: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for release bot signing: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Key rotation

Dual-trust old and new public keys during rotation window; revoke compromised immediately.

Production teams running helm chart signing provenance learned that key rotation regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for key rotation: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument key rotation with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for key rotation: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for key rotation belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in key rotation configs.

Capacity note: estimate peak concurrency for key rotation, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart signing provenance: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for key rotation: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## OCI parity

Same verify for oci:// charts—notation or cosign attach to chart layer.

Production teams running helm chart signing provenance learned that oci parity regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for oci parity: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument oci parity with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for oci parity: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for oci parity belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in oci parity configs.

Capacity note: estimate peak concurrency for oci parity, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm chart signing provenance: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for oci parity: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Consumer enforce

Install pipeline --verify fails closed; no skip flag in prod without ticket.

Production teams running helm chart signing provenance learned that consumer enforce regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for consumer enforce: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument consumer enforce with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for consumer enforce: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for consumer enforce belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in consumer enforce configs.

Capacity note: estimate peak concurrency for consumer enforce, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for helm chart signing provenance: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for consumer enforce: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
