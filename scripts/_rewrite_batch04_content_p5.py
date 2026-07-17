# Part 5: posts 21-25

POSTS_P5 = {}

POSTS_P5["devops-gitlab-ci-child-pipelines"] = (
    {
        "title": "GitLab CI Child Pipelines and DAG Orchestration",
        "description": "Monorepo CI splits into child pipelines triggered per service—needs: rules, needs DAG, artifact passing, and staging deploy locks or races take down shared environments.",
        "datePublished": "2026-05-01",
        "tags": ["DevOps", "CI/CD", "Platform"],
        "keywords": "GitLab CI, child pipelines, trigger, needs DAG, monorepo CI",
        "faq": [
            {
                "q": "When should you use GitLab child pipelines?",
                "a": "When monorepo services have independent deploy cycles, different test suites, or CI duration exceeds reasonable feedback time. Parent pipeline triggers child per changed path—child owns build/test/deploy for one service.",
            },
            {
                "q": "How do child pipelines pass artifacts to siblings?",
                "a": "Artifacts stay within child pipeline by default. Cross-child sharing uses parent pipeline jobs with needs, dotenv reports, or external storage (registry, cache). Prefer container images in registry over large artifact passing between children.",
            },
            {
                "q": "What is the needs keyword in GitLab CI?",
                "a": "needs creates DAG edges between jobs—job starts when listed dependencies complete instead of waiting for entire stage. Use needs: [] for jobs that skip stage ordering. Critical for fast monorepo pipelines and correct deploy ordering.",
            },
            {
                "q": "How do you prevent child pipeline deploy races?",
                "a": "Use resource_group on shared staging deploy jobs, environment stop_in, or sequential needs chains. Without locks, two services deploying simultaneously corrupt shared database migrations.",
            },
        ],
    },
    r"""The monorepo pipeline hit 90 minutes—every push ran every service test. Splitting into child pipelines cut average feedback to 12 minutes, then staging broke when `payments` and `ledger` child pipelines deployed concurrently and applied migrations out of order.

Child pipelines buy speed; DAG and resource locks buy correctness.

## Parent trigger pattern

```yaml
# .gitlab-ci.yml (parent)
stages:
  - triggers
  - report

generate-payments:
  stage: triggers
  rules:
    - changes:
        - services/payments/**/*
  trigger:
    include: services/payments/.gitlab-ci.yml
    strategy: depend
  variables:
    PARENT_PIPELINE_ID: $CI_PIPELINE_ID

generate-ledger:
  stage: triggers
  rules:
    - changes:
        - services/ledger/**/*
  trigger:
    include: services/ledger/.gitlab-ci.yml
    strategy: depend
```

`strategy: depend` — parent fails if child fails—visible in merge request pipeline view.

## Child pipeline structure

```yaml
# services/payments/.gitlab-ci.yml
stages:
  - test
  - build
  - deploy

unit-test:
  stage: test
  script:
    - cd services/payments && npm test

build-image:
  stage: build
  needs: [unit-test]
  script:
    - docker build -t $CI_REGISTRY_IMAGE/payments:$CI_COMMIT_SHA .

deploy-staging:
  stage: deploy
  needs: [build-image]
  resource_group: staging-deploy  # serializes shared env
  environment:
    name: staging
  script:
    - ./deploy.sh staging payments
```

## needs DAG across stages

```yaml
integration-test:
  stage: test
  needs:
    - job: unit-test
      artifacts: true
    - job: contract-test
      artifacts: false
```

Without `needs`, GitLab waits for entire prior stage—kills parallelization benefits.

## Artifact strategy

Anti-pattern: passing 2GB test fixtures parent→child→sibling.

Preferred:

1. Build pushes image to registry in child.
2. Deploy job pulls by digest.
3. Parent collects child dotenv reports for versioning metadata.

```yaml
# child job
report-version:
  script:
    - echo "PAYMENTS_VERSION=$CI_COMMIT_SHA" >> report.env
  artifacts:
    reports:
      dotenv: report.env
```

## Dynamic child pipelines

Generate child config when matrix large:

```yaml
generate-config:
  script:
    - python scripts/generate-child-pipeline.py > child.yml
  artifacts:
    paths:
      - child.yml

trigger-dynamic:
  trigger:
    include:
      - artifact: child.yml
        job: generate-config
```

## Merge train interaction

Document behavior: child pipelines restart on merge train—ensure resource_group covers re-runs idempotently.

## Debugging

Parent pipeline UI links to child—click through for failed job logs. Common failure: `include` path wrong after directory move; rules never trigger child.

Child pipelines turn monorepo CI from batch job to DAG—orchestrated speed without staging demolition derby.
""",
)

POSTS_P5["devops-gitops-disaster-recovery"] = (
    {
        "title": "GitOps Disaster Recovery Runbooks",
        "description": "When the cluster or registry vanishes, GitOps recovery rebuilds from Git—if repos are mirrored, secrets recoverable, and bootstrap is rehearsed.",
        "datePublished": "2026-05-28",
        "tags": ["DevOps", "GitOps", "SRE"],
        "keywords": "GitOps disaster recovery, cluster rebuild, Argo CD bootstrap, Flux recovery",
        "faq": [
            {
                "q": "Can you rebuild a Kubernetes cluster entirely from GitOps?",
                "a": "Yes for workload definitions if Git holds desired state, container images exist in registry, and secrets are recoverable from Vault/SOPS backup. Cluster infrastructure (VPC, node pools) typically rebuilds from Terraform/Crossplane—then GitOps bootstrap installs apps.",
            },
            {
                "q": "Why mirror Git repos for GitOps DR?",
                "a": "If GitHub/GitLab is unavailable during incident, unmirrored Git blocks recovery. Maintain read mirror (second provider or self-hosted Gitea) and document which mirror bootstrap uses. Test failover quarterly.",
            },
            {
                "q": "What is the GitOps bootstrap chicken-and-egg problem?",
                "a": "GitOps controller (Argo CD/Flux) must exist to sync from Git, but its install manifest is in Git. Solution: store minimal bootstrap manifests outside Git (runbook + sealed secrets) or use managed Argo CD SaaS with pre-provisioned credentials.",
            },
            {
                "q": "How often should GitOps DR drills run?",
                "a": "Full cluster rebuild drill annually in isolated account; bootstrap-only drill quarterly. Measure RTO against target (often 4–8 hours for full prod parity, 1 hour for critical tier-1 subset).",
            },
        ],
    },
    r"""Region-wide control plane degradation left engineers with kubectl errors and a Slack thread titled "what now." Terraform rebuilt EKS in two hours. GitOps recovery stalled three more because Argo CD's repo credential lived only in the old cluster's etcd and nobody had run bootstrap from the runbook since it referenced a decommissioned GitHub org.

GitOps promises recovery from Git. That promise requires Git, images, secrets, and bootstrap to survive independently of any one cluster.

## Recovery layers

```
Layer 0: Infrastructure (Terraform) — VPC, EKS, IAM
Layer 1: Bootstrap — GitOps controller, External Secrets, cert-manager
Layer 2: Platform — ingress, monitoring, policy
Layer 3: Applications — product workloads
```

GitOps covers layers 1–3 once layer 0 exists.

## Prerequisites checklist

| Asset | DR requirement |
|-------|----------------|
| Git repos | Geo-redundant mirror, deploy keys in Vault |
| Container images | Cross-region registry replication |
| Secrets | Vault backup or SOPS keys in HSM/offsite |
| Terraform state | Remote backend with versioning |
| DNS | Terraform or provider API access documented |

## Flux bootstrap runbook excerpt

```bash
# 1. Fresh cluster from Terraform
terraform apply -target=module.eks

# 2. Install Flux CLI components
flux install --namespace=flux-system

# 3. Bootstrap from mirror (not primary if primary down)
export GITHUB_TOKEN=$(vault read -field=token secret/flux-bootstrap)
flux bootstrap github \
  --owner=org-fleet-mirror \
  --repository=fleet-infra \
  --branch=main \
  --path=clusters/prod-us-east-1

# 4. Verify reconciliation
flux get kustomizations --all-namespaces
```

Store bootstrap token and mirror URL in runbook vault path tested quarterly.

## Argo CD pattern

Pre-render `argocd-install.yaml` + `root-app.yaml` in break-glass S3 bucket:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  source:
    repoURL: https://git-mirror.internal/fleet.git
    path: clusters/prod
  destination:
    server: https://kubernetes.default.svc
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Apply install manifest via runbook before root Application.

## Registry without images = hollow GitOps

Enable ECR replication or harbor geo-replication. DR drill includes pulling one image from secondary region without primary online.

## RTO/RPO targets

Document honestly:

- **RPO Git state**: 0 if Git is HA; minutes if only primary GitHub
- **RPO etcd**: irrelevant if Git is source of truth—cluster is cattle
- **RTO tier-1 apps**: target from drill measurements, not wishes

## Drill scenario

Tabletop month 1: walk runbook. Month 6: rebuild dev cluster from zero. Month 12: rebuild prod-like env without touching prod primary Git—use mirror only.

Capture gaps: missing SOPS key, outdated Terraform module pin, External Secrets provider down.

GitOps DR is not "clone repo and kubectl apply." It is rehearsed bootstrap, mirrored sources, and secrets that outlive any single cluster.
""",
)

POSTS_P5["devops-gitops-drift-detection"] = (
    {
        "title": "GitOps Drift Detection and Self-Heal",
        "description": "Self-heal reverts kubectl edits fast—drift detection alerts tell you someone broke glass. Ignore diffs on Secrets carefully or plaintext drift hides in encrypted fields.",
        "datePublished": "2026-05-21",
        "tags": ["DevOps", "GitOps", "SRE"],
        "keywords": "GitOps drift, self-heal, Argo CD diff, Flux drift detection",
        "faq": [
            {
                "q": "What is GitOps drift?",
                "a": "Live cluster state differs from Git-declared desired state—manual kubectl edit, failing hook, or emergency scale. Drift detection surfaces differences; self-heal automatically reconciles back to Git.",
            },
            {
                "q": "Should self-heal be enabled in production?",
                "a": "Yes for most platform and app resources—it prevents silent manual changes accumulating. Pair with drift alerts and audit logs so break-glass edits trigger review, not surprise when reverted mid-incident.",
            },
            {
                "q": "How do you handle legitimate drift on Secrets?",
                "a": "Use ignoreDifferences (Argo CD) or compare only metadata/keys existence—not decoded values. External Secrets Operator rotates data fields; ignoring entire Secret hides malicious plaintext injection—prefer ESO-only mutation with OPA denying manual Secret creates.",
            },
            {
                "q": "How is Flux drift detection configured?",
                "a": "HelmRelease and Kustomization support spec.driftDetection mode enabled. Reports diffs in status; optional remediation policies. Combine with notification Controller alerts on drift events.",
            },
        ],
    },
    r"""On-call scaled Deployment replicas to zero during a payment incident—correct move. Argo CD self-heal scaled back to three within three minutes—also correct per policy, wrong per incident. Without drift alert, nobody knew why pods respawned until postmortem grep.

Self-heal without visibility feels like haunted infrastructure. Drift detection without self-heal accumulates skeleton edits.

## Argo CD configuration

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: checkout
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - RespectIgnoreDifferences=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers:
        - /spec/replicas  # allow HPA to own replicas — OR use sync option
    - group: ""
      kind: Secret
      name: checkout-tls
      jsonPointers:
        - /data
```

Choose explicitly: HPA-managed replicas should use `"RespectIgnoreDifferences"` on `/spec/replicas` **or** remove replicas from Git letting HPA fully own field.

## Drift notifications

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-notifications-cm
data:
  trigger.on-sync-failed: |
    - when: app.status.sync.status == 'OutOfSync'
      send: [slack-drift]
  template.slack-drift: |
    message: |
      {{.app.metadata.name}} drifted from Git
      {{range $c := .app.status.conditions}}
      {{$c.message}}
      {{end}}
```

Page platform on unexpected OutOfSync persisting > 15 minutes.

## Flux HelmRelease drift

```yaml
spec:
  driftDetection:
    mode: enabled
  upgrade:
    remediation:
      remediateLastFailure: true
```

Status field `lastAttemptedRevision` vs live helm manifest diff visible in `flux get helmreleases`.

## Break-glass procedure

1. Annotate Application: `argocd.argoproj.io/sync-options: DisableAutoSync=true` or flux suspend.
2. Perform manual intervention.
3. Either revert Git to match emergency state or undo manual change.
4. Remove suspend; document in incident ticket.

Skipping step 4 leaves Git lying about prod.

## Secrets drift trap

Ignoring all `/data` on Secrets hides attacker-added keys. Better:

- Deny manual Secret create via OPA except ESO service account.
- Ignore only known rotation keys: `/data/tls.crt`, `/data/tls.key`.
- Alert on Secret metadata generation change without ESO annotation update.

## Audit integration

Export Argo CD application events and Flux notification events to SIEM. Correlate drift with Kubernetes audit log user identity.

## Metrics

```promql
argocd_app_info{sync_status="OutOfSync"}
gotk_reconcile_condition{kind="Kustomization",status="False"}
```

Drift dashboards by team namespace—shame is less effective than visibility.

GitOps drift policy: self-heal by default, alert on every revert, suspend only with annotation and ticket—never silent kubectl in prod.
""",
)

POSTS_P5["devops-gitops-helm-kustomize-hybrid"] = (
    {
        "title": "GitOps with Helm and Kustomize Hybrid Repos",
        "description": "Platform ships Helm charts; app teams patch with Kustomize overlays—helmCharts in kustomization.yaml unifies both in one GitOps apply if versions are pinned.",
        "datePublished": "2026-05-29",
        "tags": ["DevOps", "GitOps", "Helm"],
        "keywords": "Helm Kustomize hybrid, helmCharts, GitOps, post-renderer",
        "faq": [
            {
                "q": "How do Kustomize and Helm work together in GitOps?",
                "a": "Kustomize helmCharts field renders upstream charts with specified version and values, outputting manifests into kustomize resource tree. Overlays then patch, add labels, or inject sidecars—single kustomize build output synced by Flux or Argo CD.",
            },
            {
                "q": "Should platform publish Helm charts or Kustomize bases?",
                "a": "Publish versioned Helm charts for reusable components (database operators, ingress). Provide Kustomize overlays per environment for org-specific patches. Consumers use helmCharts in env overlay rather than forking chart templates.",
            },
            {
                "q": "What breaks when helmCharts version is unpinned?",
                "a": "kustomize build fetches latest matching chart on each build—silent upstream drift between laptop and CI. Pin version field exactly; bump intentionally in PR with changelog review.",
            },
            {
                "q": "Helm post-renderer vs Kustomize patches?",
                "a": "Post-renderer mutates helm template output at install time—good for CLI/HelmRelease. helmCharts in Kustomize renders at build time—patches are standard strategic merge patches in overlay. Pick one mutation layer to avoid fighting double patches.",
            },
        ],
    },
    r"""Platform standardized on Helm charts. Application teams standardized on Kustomize overlays. Two years of `$ helm template | kustomize edit add` in bash scripts ended when someone discovered Kustomize native `helmCharts`—and broke prod when `version` floated and pulled a chart with CRD schema changes.

Hybrid repos work when Helm owns package boundaries and Kustomize owns environment deltas—not when both mutate the same field twice.

## Repository layout

```
fleet/
├── charts/                    # platform-published charts (optional)
├── base/
│   └── redis/
│       ├── kustomization.yaml
│       └── helm-values.yaml
└── overlays/
    ├── staging/
    │   └── redis/
    │       ├── kustomization.yaml
    │       └── replica-patch.yaml
    └── prod/
        └── redis/
            ├── kustomization.yaml
            └── resources-patch.yaml
```

## Base kustomization with helmCharts

```yaml
# base/redis/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
helmCharts:
  - name: redis
    repo: https://charts.bitnami.com/bitnami
    version: 18.6.1
    releaseName: redis
    namespace: cache
    valuesFile: helm-values.yaml
```

## Overlay patches

```yaml
# overlays/prod/redis/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../../base/redis
patches:
  - path: resources-patch.yaml
commonLabels:
  cost-center: "CC-4421"
  environment: prod
```

```yaml
# resources-patch.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis-master
spec:
  template:
    spec:
      containers:
        - name: redis
          resources:
            requests:
              memory: 4Gi
```

## Flux Kustomization

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: redis-prod
spec:
  interval: 5m
  path: ./overlays/prod/redis
  sourceRef:
    kind: GitRepository
    name: fleet
  prune: true
```

CI runs `kustomize build --enable-helm` before merge—catch chart fetch failures early.

## Version pin discipline

```yaml
helmCharts:
  - name: redis
    version: 18.6.1  # exact — never omit
```

Renovate or Dependabot PR bumps version with CI diff of rendered manifests.

## When to use HelmRelease instead

Use Flux HelmRelease when:

- Native helm test hooks required
- Helm release history rollback primary ops path
- OCI chart registry without kustomize helm support maturity

Use helmCharts kustomize when:

- Single kustomize build output preferred
- Heavy json6902 patches across many resources
- Argo CD Application without helm-controller

## CRD ordering

Chart upgrades bringing new CRDs need server-side apply or separate CRD kustomization wave—sync waves in Argo CD or dependsOn in Flux.

Hybrid GitOps succeeds when charts are pinned products and overlays are thin environment skin—not second copies of chart logic.
""",
)

POSTS_P5["devops-gitops-multi-cluster"] = (
    {
        "title": "GitOps for Multi-Cluster Fleet Management",
        "description": "ApplicationSet and Flux Cluster reconciliation propagate manifests across fleets—separate branches or paths per environment so staging never syncs to prod by selector typo.",
        "datePublished": "2026-05-24",
        "tags": ["DevOps", "GitOps", "Platform"],
        "keywords": "GitOps multi-cluster, ApplicationSet, Flux Cluster, fleet management",
        "faq": [
            {
                "q": "What is Argo CD ApplicationSet?",
                "a": "ApplicationSet generates Argo CD Application resources from generators—cluster list, Git directories, SCM provider API. One template drives many cluster-specific Applications with parameterized paths and values.",
            },
            {
                "q": "How do you prevent staging changes syncing to production clusters?",
                "a": "Separate Git paths (clusters/prod vs clusters/staging), separate ApplicationSet generators with explicit cluster labels, and RBAC denying prod cluster registration without approval. Never single branch/path to all clusters without label selectors validated in CI.",
            },
            {
                "q": "How does Flux manage multiple clusters?",
                "a": "Flux Cluster API (multi-tenancy) or one Flux instance per cluster with shared Git repo paths. Fleet repos use directory per cluster; each cluster's bootstrap watches only its path—platform hub optionally aggregates status.",
            },
            {
                "q": "How many clusters can one ApplicationSet manage?",
                "a": "Practical limits depend on Argo CD control plane sizing—hundreds of Applications work with tuned controller sharding. Beyond ~500 clusters, consider hierarchical ApplicationSets or regional Argo CD instances.",
            },
        ],
    },
    r"""One ApplicationSet typo in the cluster generator label selector pushed payment service staging manifest to four production clusters before sync wave paused on the fifth—rollback was Git revert, but four regions had already picked up bad image digests.

Multi-cluster GitOps scales repetition—not judgment. Environment separation must be structural, not conventional.

## Fleet repo structure

```
fleet/
├── clusters/
│   ├── prod-us-east-1/
│   │   └── kustomization.yaml
│   ├── prod-eu-west-1/
│   │   └── kustomization.yaml
│   └── staging-us-east-1/
│       └── kustomization.yaml
├── apps/
│   ├── checkout/
│   │   ├── base/
│   │   └── overlays/
│   │       ├── prod/
│   │       └── staging/
└── applicationsets/
    └── checkout.yaml
```

Each cluster kustomization references only its environment overlay.

## ApplicationSet cluster generator

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: checkout-fleet
  namespace: argocd
spec:
  generators:
    - clusters:
        selector:
          matchLabels:
            env: prod
            fleet: payments
  template:
    metadata:
      name: "checkout-{{name}}"
    spec:
      project: payments
      source:
        repoURL: https://git.example.com/fleet.git
        targetRevision: main
        path: "apps/checkout/overlays/{{metadata.labels.env}}"
      destination:
        server: "{{server}}"
        namespace: storefront
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

Register clusters with explicit labels—never wildcard prod+staging.

## Staging vs prod isolation

| Control | Implementation |
|---------|----------------|
| Path | `overlays/staging` vs `overlays/prod` |
| Branch | optional release branch for prod |
| Cluster label | `env=staging` enforced at registration |
| Argo CD AppProject | prod denies `--force` sync from staging SA |

CI validates ApplicationSet templates cannot reference `overlays/staging` when generator selects `env=prod`.

## Flux multi-cluster pattern

Bootstrap each cluster pointing at unique path:

```bash
flux bootstrap github ... --path=clusters/prod-us-east-1
```

Management cluster optionally uses Flux Cluster API to deploy to spoke clusters—evaluate operational complexity vs Argo CD hub-spoke.

## Promotion workflow

```
1. Merge app change to staging overlay
2. Soak in staging clusters (ApplicationSet env=staging)
3. PR promoting same commit SHA to prod overlay (copy image digests)
4. Prod ApplicationSet sync after approval
```

Image digests promoted—not tags floating separately per region.

## Observability

Aggregate sync status:

```promql
sum by (cluster) (argocd_app_info{sync_status!="Synced"})
```

Fleet dashboard: clusters OutOfSync, last sync time, Git revision lag per region.

## DR and cluster registration

Cluster secrets (Argo CD cluster register) stored in Vault with rotation. New region DR: register cluster, apply ApplicationSet—apps materialize from existing prod overlay path.

Multi-cluster GitOps is copy automation with guardrails—labels, paths, and promotion PRs prevent staging imagination from becoming production reality.
""",
)
