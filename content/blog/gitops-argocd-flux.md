---
title: "GitOps with Argo CD and Flux"
seoTitle: "Argo CD vs Flux: Choosing a GitOps Tool"
slug: "gitops-argocd-flux"
description: "A practical comparison of Argo CD and Flux for GitOps — sync models, multi-tenancy, Helm support, and how to pick the right controller for your platform team."
datePublished: "2026-06-28"
dateModified: "2026-06-28"
tags: ["GitOps", "Kubernetes", "Argo CD", "Flux", "Platform Engineering"]
keywords: "GitOps, Argo CD, Flux CD, Kubernetes deployment, continuous delivery, GitOps comparison, platform engineering"
faq:
  - q: "What is the main difference between Argo CD and Flux?"
    a: "Argo CD is a centralized control plane with a rich UI, application-centric sync, and strong multi-cluster management. Flux is a modular toolkit of controllers (source, kustomize, helm, notification) that composes into a lighter, CNCF-graduated GitOps engine."
  - q: "Can I use Helm with both Argo CD and Flux?"
    a: "Yes. Argo CD renders Helm charts natively inside Application resources. Flux has a dedicated HelmController that watches HelmRelease CRDs and reconciles chart installs independently of Kustomize overlays."
  - q: "Which GitOps tool is better for multi-tenancy?"
    a: "Argo CD's AppProject RBAC and UI make it easier to give teams visibility into their own applications within a shared instance. Flux's namespace-scoped resources and lack of a built-in UI suit teams that prefer Git-as-the-UI and tighter per-namespace isolation."
---

Git is the source of truth. The cluster reconciles to match. That's GitOps — and the two tools most teams actually evaluate are **Argo CD** and **Flux**. I've run both on platform teams supporting mobile backends, charging infrastructure, and internal developer platforms. Neither is universally better. The choice comes down to how your team wants to interact with deployments and how much UI versus composable controllers you want.

## The shared model

Both tools watch a Git repository (or OCI artifact registry), compare desired state to live cluster state, and reconcile the diff. Both support Kustomize overlays, Helm charts, SOPS-encrypted secrets, and multi-environment promotion via branch or directory structure.

Where they diverge is ergonomics and architecture.

## Argo CD: application-centric with a UI

Argo CD treats each deployable unit as an **Application** — a CRD pointing at a Git path, a target cluster, and a sync policy. The web UI is genuinely good: diff views, sync status, rollback, and a visual resource tree that non-platform engineers can read without learning `kubectl`.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ocpp-gateway
  namespace: argocd
spec:
  project: production
  source:
    repoURL: https://github.com/myorg/k8s-manifests
    targetRevision: main
    path: apps/ocpp-gateway/overlays/prod
  destination:
    server: https://kubernetes.default.svc
    namespace: charging
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**Strengths I've leaned on:**

- **AppProject RBAC** scopes teams to their apps without cluster-admin for everyone.
- **Multi-cluster from one instance** — register remote clusters and deploy from a central Argo CD.
- **Sync waves and hooks** for ordered rollouts (CRDs first, then operators, then apps).
- **The UI as onboarding.** New engineers see what's deployed without reading twelve repos.

**Trade-offs:**

- Argo CD itself is a stateful application you must operate, upgrade, and back up.
- The Application CRD model can feel heavyweight for simple "just sync this Kustomize dir" cases.
- Running at scale (hundreds of Applications) needs tuning — repo-server caching, sharding, Redis HA.

## Flux: composable controllers, Git-native

Flux v2 is not one binary — it's a set of controllers: **Source** (Git/OCI/Helm repos), **Kustomize**, **Helm**, **Notification**, and **Image Automation**. Each reconciles independently. There's no built-in UI; your Git history and `flux get` output *are* the interface.

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: platform-manifests
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/myorg/k8s-manifests
  ref:
    branch: main
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: ocpp-gateway
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: platform-manifests
  path: ./apps/ocpp-gateway/overlays/prod
  prune: true
  healthChecks:
    - apiVersion: apps/v1
      kind: Deployment
      name: ocpp-gateway
      namespace: charging
```

**Strengths I've leaned on:**

- **Modularity.** Need image automation but not Helm? Install only those controllers.
- **CNCF graduated.** Strong community, wide cloud-provider integration.
- **Namespace-scoped tenancy.** Each team gets Kustomizations in their namespace without a shared control plane UI.
- **Smaller operational footprint** than a full Argo CD HA stack for teams that don't need the UI.

**Trade-offs:**

- No first-class UI — you'll wire Grafana dashboards or use the Flux CLI.
- Multi-cluster requires either a Flux instance per cluster or a management-cluster pattern with Cluster API.
- The composable model has a steeper initial learning curve.

## Head-to-head

| Concern | Argo CD | Flux |
|---|---|---|
| Web UI | Built-in, excellent | None (third-party or CLI) |
| Helm support | Native in Application | Dedicated HelmController |
| Multi-cluster | Central instance, many clusters | Per-cluster or mgmt pattern |
| Secret encryption | SOPS, Vault plugins | SOPS native, ESO integration |
| Image auto-update | Argo CD Image Updater (addon) | Built-in Image Automation |
| CNCF status | Incubating (via Argo project) | Graduated |
| Learning curve | Lower (UI helps) | Higher (more CRDs) |
| Resource footprint | Heavier (UI + repo-server + Redis) | Lighter (pick controllers) |

## How I choose

**Pick Argo CD** when:

- Multiple product teams share a platform and need a self-service UI to see and sync their apps.
- You're managing several clusters from one place and want a single pane of glass.
- Onboarding speed matters — the UI reduces "how do I check prod?" questions.

**Pick Flux** when:

- Your team lives in Git and PRs and doesn't want another dashboard to maintain.
- You want minimal control-plane overhead on edge or cost-sensitive clusters. This pairs naturally with [Kubernetes cost optimization](https://blog.michaelsam94.com/kubernetes-cost-optimization-finops/) — fewer control-plane pods means fewer nodes reserved for platform overhead.
- You need fine-grained controller composition (image automation without the rest).

On the EV charging platform, we used Argo CD because ops engineers and field-support staff needed to see charger-gateway deployment status without kubectl access. On a later internal-tools cluster where only platform engineers touched deployments, Flux was the better fit — less to operate, and the team already reviewed everything through PRs.

## Patterns that work regardless of tool

1. **One repo (or mono-repo path) per environment overlay.** `base/` + `overlays/staging/` + `overlays/prod/`. Never maintain separate prod manifests that drift.
2. **Automated sync with prune in non-prod; manual or gated sync in prod.** Self-heal everywhere; auto-prune only where you're confident.
3. **SOPS or External Secrets for secrets.** Never commit plaintext. Both tools integrate cleanly.
4. **Health checks and sync waves.** CRDs and namespaces before Deployments. Jobs before Deployments that depend on migrations.
5. **Audit trail in Git.** Every production change is a merged PR. The GitOps controller is the enforcer, not the author.

GitOps doesn't replace CI — it replaces `kubectl apply` from laptops. Build and test in CI; GitOps reconciles the result. If your [CI/CD pipelines are slow](https://blog.michaelsam94.com/fast-cicd-pipelines/), fix that upstream. GitOps sync is fast; waiting forty minutes for a test suite is not.

## Resources

- [Argo CD documentation](https://argo-cd.readthedocs.io/en/stable/)
- [Flux documentation](https://fluxcd.io/flux/)
- [CNCF GitOps Working Group](https://github.com/cncf/tag-app-delivery/tree/main/gitops-wg)
- [OpenGitOps principles](https://opengitops.dev/)
- [Weaveworks GitOps guide (Flux creators)](https://www.weave.works/technologies/gitops/)
- [Kubernetes documentation — ConfigMaps and Secrets](https://kubernetes.io/docs/concepts/configuration/)
