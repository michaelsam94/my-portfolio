---
title: "Helm Secrets with SOPS"
slug: "devops-helm-secrets-sops"
description: "Encrypt Helm values with SOPS; decrypt in CI and GitOps."
datePublished: "2026-10-12"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Helm"
  - "Security"
keywords: "Helm secrets, SOPS"
faq:
  - q: "Why SOPS with Helm?"
    a: "Encrypted values in Git for GitOps; decrypt at render time in CI or Argo CD with KMS-backed keys."
  - q: "SOPS key hygiene?"
    a: "Age or PGP keys in KMS/HSM—not in same repo as encrypted files; rotation playbook with re-encrypt all files."
  - q: "Helm Secrets plugin vs Argo CD SOPS?"
    a: "Pick one decrypt path—dual decrypt causes drift between local helm and cluster state."
  - q: "Encrypted file scope?"
    a: "Encrypt only secret values leaves structure reviewable in PR—`.sops.yaml` creation rules per path pattern."
---
Plaintext database passwords lived in values.yaml Git history; SOPS encryption fixed audit finding but Argo and local helm used different decrypt keys until sync failed silently.

## SOPS creation rules

.sops.yaml maps path regex to KMS or age keys—encrypt only secret leaves structure reviewable in PR.

Production teams running helm secrets sops learned that sops creation rules regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for sops creation rules: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument sops creation rules with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for sops creation rules: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for sops creation rules belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in sops creation rules configs.

Capacity note: estimate peak concurrency for sops creation rules, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm secrets sops: least privilege on automation roles, short-lived credentials,
immutable audit logs for production changes—break-glass expires in forty-eight hours with mandatory
retrospective.

FinOps tie-in for sops creation rules: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Single decrypt path

Argo CD SOPS plugin OR helm-secrets in CI—not both with divergent keys.

Production teams running helm secrets sops learned that single decrypt path regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for single decrypt path: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument single decrypt path with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for single decrypt path: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for single decrypt path belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in single decrypt path configs.

Capacity note: estimate peak concurrency for single decrypt path, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for helm secrets sops: least privilege on automation roles, short-lived credentials,
immutable audit logs for production changes—break-glass expires in forty-eight hours with mandatory
retrospective.

FinOps tie-in for single decrypt path: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Key rotation

Generate new age key in KMS, sops updatekeys on all files, dual-trust window, revoke old key.

Production teams running helm secrets sops learned that key rotation regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

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

Security review for helm secrets sops: least privilege on automation roles, short-lived credentials,
immutable audit logs for production changes—break-glass expires in forty-eight hours with mandatory
retrospective.

FinOps tie-in for key rotation: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## GitOps flow

Encrypted values in repo; decrypt at render; never commit decrypted prod to branch.

Production teams running helm secrets sops learned that gitops flow regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for gitops flow: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument gitops flow with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for gitops flow: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for gitops flow belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in gitops flow configs.

Capacity note: estimate peak concurrency for gitops flow, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm secrets sops: least privilege on automation roles, short-lived credentials,
immutable audit logs for production changes—break-glass expires in forty-eight hours with mandatory
retrospective.

FinOps tie-in for gitops flow: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Audit

CloudTrail on KMS decrypt; alert on decrypt from unexpected principal.

Production teams running helm secrets sops learned that audit regressions appear when traffic mix
shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for audit: confirm blast radius, identify last config change, execute single-step rollback,
capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument audit with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for audit: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for audit belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in audit configs.

Capacity note: estimate peak concurrency for audit, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for helm secrets sops: least privilege on automation roles, short-lived credentials,
immutable audit logs for production changes—break-glass expires in forty-eight hours with mandatory
retrospective.

FinOps tie-in for audit: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

```yaml
creation_rules:
  - path_regex: \.enc\.yaml$
    age: age1...
    encrypted_regex: ^(data|stringData)$
```
Decrypt path must match in Argo CD and CI—dual keys caused silent OutOfSync.
