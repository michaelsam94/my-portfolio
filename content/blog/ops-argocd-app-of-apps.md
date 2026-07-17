---
title: "The App-of-Apps Pattern in Argo CD"
slug: "ops-argocd-app-of-apps"
description: "Structure Argo CD with the app-of-apps pattern: bootstrap repos, Application CRDs, environment layering, and how to avoid the sync loops that waste on-call time."
datePublished: "2025-12-23"
dateModified: "2026-07-17"
tags: ["DevOps", "GitOps", "Argo CD", "Kubernetes"]
keywords: "Argo CD app of apps, GitOps bootstrap, Application CRD, Argo CD patterns, Kubernetes deployment"
faq:
  - q: "What is the app-of-apps pattern in Argo CD?"
    a: "It's a bootstrap Application that points to a directory of other Application manifests (or Helm charts that generate them). Argo CD syncs the parent, which creates child Applications, each managing a workload or platform component. One repo commit can roll out changes across your entire cluster fleet."
  - q: "How do you bootstrap the first app-of-apps?"
    a: "Install Argo CD, then apply a single root Application manually (or via Terraform) that points to your bootstrap repo path — typically `bootstrap/root-app.yaml`. That root app owns everything else. Never hand-apply child Applications outside Git; you'll drift immediately."
  - q: "How do you prevent app-of-apps sync loops?"
    a: "Avoid Applications that manage resources Argo CD itself modifies (like other Application status fields). Use `ignoreDifferences` for known drift, separate platform apps from app apps, and don't nest more than two levels unless you enjoy debugging recursive sync failures at 2 AM."
---

Our staging cluster had forty-seven Applications before we adopted app-of-apps, and half of them were created by someone kubectl-applying YAML "just to test something." Production was worse — nobody knew which repo owned the ingress controller. The app-of-apps pattern didn't fix our culture overnight, but it gave us one front door: a bootstrap repo where every Application is declared, reviewed, and synced.

## What app-of-apps actually is

An Argo CD `Application` is a CRD that says "keep cluster state matching this Git path." App-of-apps is an Application whose source path contains *other* Application definitions:

```
bootstrap-repo/
├── root-app.yaml          # Applied once manually or via Terraform
└── apps/
    ├── platform/
    │   ├── ingress.yaml
    │   ├── cert-manager.yaml
    │   └── external-dns.yaml
    └── workloads/
        ├── api-staging.yaml
        └── api-production.yaml
```

The root Application syncs `apps/`, which creates child Applications. Each child syncs its own repo/path. Git remains the source of truth at every level.

```yaml
# bootstrap/root-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/acme/gitops-bootstrap.git
    targetRevision: main
    path: apps
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

`prune: true` deletes Applications removed from Git — essential, but scary the first time. Test in staging with `prune: false` until you trust your repo layout.

## Layering environments without copy-paste

Don't duplicate Application YAML per environment. Common patterns:

**Kustomize overlays.** Base Application templates in `base/`, overlays in `overlays/staging` and `overlays/prod` patch image tags, replica counts, and destination clusters.

**ApplicationSet.** Generate Applications from a matrix of `(cluster, app)` pairs. One ApplicationSet replaces twenty hand-written files when you manage five clusters × four services.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: api-apps
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - cluster: staging
            url: https://staging-api.k8s.internal
          - cluster: production
            url: https://prod-api.k8s.internal
  template:
    metadata:
      name: 'api-{{cluster}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/acme/api-deploy.git
        targetRevision: main
        path: 'overlays/{{cluster}}'
      destination:
        server: '{{url}}'
        namespace: api
```

We moved to ApplicationSet when our cluster count hit three. Manual Application files don't scale; they also don't get updated when someone adds a fourth cluster.

## Repo structure that reviewers can follow

Split repos by blast radius:

- **Bootstrap repo** — root app, platform apps (ingress, monitoring, Argo CD self-management)
- **App deploy repos** — one per service team, Kustomize/Helm for that service's manifests
- **Policy repo** (optional) — OPA/Gatekeeper or Kyverno policies synced as their own Application

Never put application manifests and bootstrap manifests in the same repo if different teams own them. The platform team shouldn't need approval from the payments team to update cert-manager.

## Sync policies that match your risk tolerance

Platform components (CNI, CSI, cert-manager): manual sync or automated with `allowEmpty: false` and sync windows. Workload apps in staging: full auto-sync with self-heal. Production workloads: automated sync only after CI passes, or manual promotion via PR that changes `targetRevision`.

Use `syncOptions`:
- `CreateNamespace=true` for team-owned namespaces
- `ServerSideApply=true` for CRDs and large resources
- `ApplyOutOfSyncOnly=true` on large apps to shorten sync time

## Failure modes I've debugged

**Recursive app creation.** An Application pointed at a path that included its own manifest. Argo CD created copies until we hit etcd object limits. Fix: exclude bootstrap paths from child app sources.

**Drift from manual kubectl.** Self-heal reverts emergency hotfixes. That's correct behavior — route emergencies through Git revert, not kubectl patch. Train on-call on `argocd app sync --force` vs fixing Git.

**Secret leakage in Application repos.** Application CRDs reference repo URLs and paths; they shouldn't contain credentials. Use Argo CD repo credentials or OIDC, and sealed-secrets/SOPS for manifests.

**Orphaned resources.** Deleting an Application without `prune` leaves deployments running. With `prune`, deleting an app from Git destroys production. Use `resources-finalizer.argocd.argoproj.io` finalizer and staged rollout of prune enablement.

## Bootstrapping multi-cluster fleets

When ApplicationSet generates apps across clusters, store cluster credentials in Argo CD cluster secrets and label clusters by environment. A common pattern: one bootstrap repo branch per environment (`main` → prod registry path, `staging` → staging path) so a merged PR cannot accidentally sync prod manifests to staging clusters.

For cluster add-ons that must exist before workloads — CNI, metrics-server, external-secrets — order sync waves with annotations:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
```

Negative waves sync first. Document wave numbers in the bootstrap README so new platform engineers do not assign conflicting waves. We run `argocd app sync root --dry-run` in CI on bootstrap PRs to catch YAML errors before they block cluster onboarding.

## Common production mistakes

Teams get argocd app of apps wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of argocd app of apps fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When argocd app of apps misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## AppProject boundaries and blast radius

Without `AppProject` RBAC, any developer's Application can deploy cluster-scoped resources to production. Structure projects:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: platform
spec:
  destinations:
    - namespace: kube-system
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
```

Workload apps get narrow namespaces; platform team owns cluster-scoped apps. CI service accounts receive tokens scoped to one project — leaked staging token cannot touch prod cluster resources.

## Secrets and config management in GitOps

Never commit raw secrets to bootstrap repo. Use External Secrets Operator, SOPS-encrypted files, or Argo CD vault plugins. Document sealed-secrets rotation — app-of-apps makes secret drift visible when sealed secret updates don't propagate to child apps referencing old versions.

## Disaster recovery bootstrap

Store root Application manifest and repo credentials in break-glass vault — total cluster loss means re-applying single `root-app.yaml` restores entire GitOps tree. Test annual fire drill: new empty cluster to production parity from bootstrap only.

## Sync windows and maintenance

`syncPolicy.syncOptions: [CreateNamespace=true]` plus maintenance windows pauses auto-sync during black Friday — manual sync freeze prevents mid-traffic Deployment churn from innocent Git commits.

## Resources

- [Argo CD Application specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/)
- [ApplicationSet documentation](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/)
- [Argo CD best practices (CNCF)](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
- [GitOps working group patterns](https://opengitops.dev/)
- [Kustomize overlays reference](https://kubectl.docs.kubernetes.io/references/kustomize/)