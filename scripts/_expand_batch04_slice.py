#!/usr/bin/env python3
"""Insert topic-specific expansion sections before ## Resources."""
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"

EXPANSIONS = {
    "devops-gitops-observability-metrics": """
## Building an SLO for GitOps delivery latency

Define an SLI: time from merge to `Synced` + `Healthy` on the production Application. Measure with:

```promql
histogram_quantile(0.99,
  sum(rate(argocd_app_reconcile_bucket[1h])) by (le, name)
)
```

Pair with Git commit timestamp exported as external label via CI webhook to Argo CD notification events. Target example: 99% of tier-1 apps sync within 10 minutes of merge. Error budget burn when repo-server git latency exceeds 30s p95—often precedes widespread sync delays.

During the six-hour silent failure class of incidents, reconciliation **succeeded** but pointed at stale revision because auto-sync was paused after a partial manual sync. Add metric or alert on `spec.syncPolicy.automated` being null for tier-1 apps outside maintenance windows. Flux equivalent: alert on `gotk_suspend_status` or missing reconciliation when source revision advanced.

## Multi-cluster and ApplicationSet cardinality

ApplicationSet generates hundreds of Applications—metrics cardinality explodes if every panel breaks out by app name globally. Pattern: recording rules producing `gitops:sync_failed:ratio5m` by `project` and `cluster`, drill-down dashboards parameterized by `$app`. Keep high-cardinality labels in Loki logs (`application=checkout-api`) for investigation, not in 90-day Prometheus retention.

Runbooks should include `argocd app get APP -o yaml | yq '.status.conditions'` as first step—conditions explain ComparisonError vs SyncError faster than aggregate metrics.
""",
    "devops-gitops-policy-enforcement": """
## Layering Kyverno with OPA for complex rules

Kyverno excels at Kubernetes object validation; OPA/Gatekeeper excels at compositional Rego (CIDR math, image digest parsing). A practical split: Kyverno for 80% of pod and metadata policies; Gatekeeper ConstraintTemplate for "image must be digest-pinned AND from registry X unless annotation break-glass present."

Test policies against **negative fixtures** in CI—manifests that must fail:

```yaml
# tests/policy/bad-privileged-pod.yaml — expect deny
spec:
  containers:
    - name: x
      securityContext:
        privileged: true
```

Policy coverage report: percentage of namespaces with enforce-mode policies, count of PolicyExceptions expiring this week. Auditors ask for evidence policies run on every path—including `kubectl apply` and Helm hooks—not only GitOps sync. Audit webhook logs for bypass attempts via cluster-admin.

When GitOps sync fails policy at admission, developers see Argo CD sync error but root cause is policy—train support to link to PolicyReport:

```bash
kubectl get policyreport -A -o wide | grep fail
```

Policy version pinning: bundle policies in Git tagged `policy/v2026.07`; clusters pull tagged bundle. Emergency policy rollback is revert Git tag, not hand-edit live ClusterPolicy—same discipline as app rollback.
""",
    "devops-gitops-preview-environments": """
## Contract testing across preview boundaries

Preview value is integration validation—wire consumer-driven contract tests in CI after preview URL healthy:

```yaml
- run: |
    export PREVIEW_URL="https://pr-${PR}.preview.example.com"
    npm run pact:verify -- --baseUrl=$PREVIEW_URL
```

Frontend preview calling real staging API (shared dependency) avoids full stack cost but misses API contract changes in the same PR—document hybrid preview modes. For backend-only PRs, mock frontend with schemathesis or Postman collection against preview OpenAPI spec.

## Cost attribution and chargeback

Tag preview namespaces with labels `preview/pr`, `preview/owner`, `preview/created_at`. Prometheus kube-state-metrics → weekly report of CPU-hours per team. Teams exceeding preview budget get CI label requirement `preview: approved` from EM. Idle preview detection: zero ingress traffic 48h → auto-delete Application via ApplicationSet plugin or cron.

DNS wildcard TLS renewal failures take down all previews—monitor cert expiry separately from prod. Private previews via VPN-only ingress reduce security scan noise from bots hitting public PR URLs.
""",
    "devops-gitops-promotion-environments": """
## Automating promotion with policy gates

Promotion PRs should carry machine-readable metadata:

```yaml
# .promotion.yaml in PR
from_env: staging
to_env: prod
digest: sha256:abc123
staging_verified_at: "2026-07-16T18:00:00Z"
soak_hours: 72
tests:
  - e2e-checkout passed
  - load-test-p95 < 400ms
```

CI validates soak window before allowing prod overlay merge. OPA/conftest rejects prod image digest not present in staging overlay history—prevents skip-ahead deploys.

## Handling configuration-only vs image-only promotions

Not every promotion changes image—ConfigMap-only changes need same staging soak. Separate promotion tracks in Git:

```
deploy/overlays/staging/patches/feature-flags.yaml
deploy/overlays/prod/patches/feature-flags.yaml
```

Promotion PR updates prod patch only after flag validated in staging. Feature flags decouple code deploy from exposure but GitOps still records flag state—avoid live-only flag edits in vendor UI without Git backport.

Hotfix backport automation: when prod hotfix PR merges, bot opens sibling PR to dev/staging with same digest and config patch—assign to on-call if not merged in 24h. Metrics: `gitops_overlay_drift{env}` when prod digest != staging digest beyond SLA.
""",
    "devops-gitops-rollback-strategies": """
## Automated rollback triggers

Combine SLO burn with GitOps rollback bot—carefully:

1. Page on checkout error budget burn 5x
2. Bot opens revert PR on prod overlay (human approve)
3. Optional: Argo CD sync rollback only if revert PR not merged in 15m

Fully automated Git revert without human approval risks revert scope bugs—prefer HPA/manual scale mitigations first.

Document **forward-fix vs rollback** decision tree in runbook: data migrations incompatible → forward-fix only; bad image digest → rollback fast.

## OCI and Helm rollback in GitOps

HelmRelease rollback in Flux:

```bash
flux suspend helmrelease api -n prod
# git revert chart version
flux resume helmrelease api -n prod
```

Helm release history in cluster != Git—`helm history` after GitOps rollback should match Git-declared chart version post-alignment PR. Store `helm.sh/release.v1` revision in deployment annotations via post-sync hook for cross-reference during incidents.
""",
    "devops-gitops-sealed-secrets": """
## Multi-cluster sealing workflows

SealedSecrets are cluster-specific—same plaintext sealed with cluster A cert cannot decrypt on cluster B. CI pipeline:

```bash
for cluster in staging prod; do
  kubeseal --cert certs/${cluster}.pem < secret.yaml > sealed/${cluster}/secret.yaml
done
```

GitOps repo layout mirrors cluster paths—prevents wrong seal copied to prod overlay. Rotation runbook: generate new secret in Vault → re-seal → merge → rolling restart → revoke old credential after overlap.

SOPS with AWS KMS cross-account: `creation_rules` per path `secrets/prod/**` uses prod KMS key; developers without decrypt on prod key cannot accidentally decrypt prod secrets locally—least privilege by path regex.

Compare ESO vs sealed for compliance: auditors often prefer no ciphertext in Git (ESO) vs encrypted at rest in Git (SOPS/Sealed)—pick based on whether Git access or KMS access is smaller trust circle.
""",
    "devops-global-load-balancer-health": """
## Cloud-specific gotchas

**GCP HTTP(S) LB:** Health checks originate from Google probe IP ranges—document in firewall rules; forgetting this marks all backends unhealthy after NetworkPolicy tightening.

**AWS NLB TCP health checks:** TLS termination on target—TCP open while HTTP app dead; use TLS listener + HTTPS health check or ALB.

**Connection draining + WebSockets:** PreStop alone insufficient—graceful WS close in app; drain interval 300s+ for long-lived connections.

Global load balancing health aggregation: use **weighted routing** only after regional health stable 2 consecutive intervals—prevents flapping traffic between regions during partial outages.

Synthetic monitoring external to LB (Checkly, Datadog Synthetics) validates user path including CDN and WAF—LB health green while CDN serves stale cache is separate failure class; do not conflate.
""",
    "devops-gpu-node-scheduling": """
## Capacity planning for GPU pools

Model: `total_gpus = nodes × gpus_per_node × (1 - headroom_pct)`. Headroom 20% for inference pools absorbs deploy surge (old+new pods during rolling update). Training pools may run at higher utilization with queue—Kueue holds work instead of over-provisioning idle GPUs.

Driver and CUDA compatibility matrix pinned in node image README—upgrade node pool only after CI validates ML container matrix against new driver version. NVIDIA Data Center GPU Manager (DCGM) exporter alerts: `XID errors`, `ECC errors`, thermal throttle—schedule node cordon before hard failure.

Mixed instance types in one pool complicates MIG—homogeneous node pools per MIG profile. Autoscaler scale-down must respect training job checkpoints—use PodDisruptionBudgets or Kueue preemption policies preventing eviction of checkpointing pods without grace.
""",
    "devops-gpu-scheduling-ml-workloads": """
## FinOps and quota negotiation

Publish monthly GPU-hours per team from Kueue workload status—finance chargeback drives rational quota requests. Burst quota: teams borrow from shared burst pool with automatic payback via lower priority when inference critical.

Experiment tracking integration: label jobs with `ml.experiment/id`—identify abandoned sweeps still holding GPUs (no metric progress 2h → alert → preempt). Jupyter notebook pods on GPU nodes without t tolerations—admission deny unless `notebook-gpu` quota.

Network: RDMA/RoCE training needs dedicated NCCL topology—schedule with `topology.kubernetes.io/zone` affinity; inference may not need—split schedulers by network profile. Multi-tenant GPU clusters in regulated industries may require confidential computing or dedicated nodes per tenant—scheduling becomes compliance boundary, not just performance.
""",
    "devops-grafana-dashboard-as-code": """
## Folder permissions and RBAC as code

Dashboard JSON without folder RBAC leaks metrics to wrong teams—Terraform:

```hcl
resource "grafana_folder_permission" "checkout" {
  folder_uid = grafana_folder.checkout.uid
  permissions {
    role       = "Viewer"
    permission = "View"
  }
  permissions {
    team_id    = grafana_team.checkout.id
    permission = "Edit"
  }
}
```

Anonymous dashboard links for exec summaries—avoid; use Grafana reporting PDF or embedded read-only service account with IP allowlist.

Version dashboard JSON alongside app releases—tag `observability/checkout/v2.3` matching app `v2.3` so rollback includes dashboard rollback. Breaking panel query changes should appear in changelog same as API breaking changes for on-call continuity.
""",
    "devops-headroom-policy-enforcement": """
## Automating headroom reports

Weekly bot posting to #platform:

```
Cluster prod-east: CPU requests at 78% allocatable (target 75%) — 3% over
Top consumers: checkout (18%), data-pipeline (12%)
Action: checkout requested quota increase PR #441
```

Integrate with Karpenter/Cluster Autoscaler: headroom policy sets `NodePool` max CPU minus buffer—cannot scale beyond economic and operational cap even if pending pods exist—forces prioritization conversation.

Application-level headroom: JDBC pool max connections × pod count must leave 30% DB headroom—alert when `(sum pool size) / db_max_connections > 0.7`. Connection pool exhaustion mimics CPU headroom incidents—include in same capacity review ritual quarterly.
""",
    "devops-helm-chart-signing-provenance": """
## Notary and policy controllers

Sigstore policy-controller in cluster can require signature from specific issuer before admission—pairs with cosign sign in CI. Example ClusterImagePolicy matches `oci://harbor.example.com/charts/*` requires signature from `https://token.actions.githubusercontent.com` with subject matching repo.

Air-gapped environments: sign on connected CI, transfer signed OCI artifact via sneakernet; verify offline with cosign public key in vault. Document difference between chart signature (integrity) and SBOM attestation (vulnerability response)—both needed for complete supply chain story.

Incident response: if key compromise suspected, rotate key, re-sign all active chart versions, revoke old key, audit `helm list` + registry logs for unsigned pulls during exposure window.
""",
    "devops-helm-chart-testing-ct-lint": """
## Extending ct with chart-specific integration tests

Beyond install, run application-specific tests post-install:

```bash
ct install --charts charts/api
kubectl wait --for=condition=ready pod -l app=api -n ct-test --timeout=300s
curl -sf http://$(kubectl get svc -n ct-test api -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')/health
```

NetworkPolicy-enabled charts need Kind CNI supporting policies—kind config:

```yaml
kind: Cluster
networking:
  disableDefaultCNI: false
```

Chart maintainers publish **compatibility matrix** in README: Kubernetes 1.28–1.30 tested via ct on each release tag. Consumers trust matrix more than semver alone for infra charts.
""",
    "devops-helm-dependency-management": """
## Renovate PR review checklist

For dependency bump PRs:

- Read upstream CHANGELOG for breaking values renames
- Check CVE fixed vs introduced in subchart
- Run `helm diff upgrade` against staging release if available
- Verify CRD version skew if subchart ships CRDs

Vendor tgz in `charts/` directory—verify digest in Chart.lock matches after update:

```bash
helm dependency build
diff Chart.lock expected.lock
```

Monorepo with 40 charts: ct list-changed only runs affected—ensure shared library bump triggers all dependent charts in changed detection via custom script scanning Chart.yaml dependencies graph.
""",
    "devops-helm-diff-pre-deploy": """
## Integrating diff with change management

Attach helm diff output to change ticket ID—SOC2 change control evidence. Redact secrets but keep resource names and field paths reviewers need.

For multi-release helmfile, aggregate diff summary:

```bash
helmfile -e prod diff | diffstat
```

Large diffs: filter to critical kinds:

```bash
helm diff upgrade ... | grep -E '^[+-].*kind: (Deployment|ConfigMap|Secret|Ingress)'
```

Post-deploy verification: re-run diff expecting empty—confirms release secret matches intended. Non-empty after deploy signals manual kubectl edit drift—open remediation ticket.
""",
    "devops-helm-governance-standards": """
## Measuring adoption

Platform KPIs:

- Percent internal charts using `platform-lib` >= 1.4
- Mean policy violations per PR (trend down)
- Time for new service to first compliant deploy (< 1 day on paved road)

Developer survey: "Did chart scaffold block you?"—if yes, fix scaffold not exceptions. Golden path `helm create` fork with org template repo:

```bash
helm create my-api --starter-chart=https://github.com/org/helm-starter
```

Quarterly **chart audit**: random sample 10 charts, manual rubric review—automated policy catches known rules; human review catches wrong abstractions.

Third-party chart lifecycle: deprecate chart version when upstream EOL—automated issue on consumer repos still pinned to deprecated version 30 days before removal from catalog.
""",
    "devops-helm-hooks-weight-order": """
## Helm hook testing in CI matrix

Test upgrade path from N-1 chart version to N with hooks—ct install fresh misses upgrade ordering bugs:

```bash
helm install test charts/api --version 1.0.0 -f ci/test-values.yaml
helm upgrade test charts/api --version 1.1.0 -f ci/test-values.yaml --wait
kubectl logs job/test-api-migrate
```

Simulate hook failure—upgrade must fail closed with `--atomic`:

```bash
# ci/bad-migration-values.yaml forces migration exit 1
helm upgrade test charts/api -f ci/bad-migration-values.yaml --atomic; test $? -ne 0
```

Hook log retention: ship hook logs to Loki before pod delete—`hook-succeeded` delete policy loses evidence; use sidecar or cluster logging agent guaranteed delivery.
""",
    "devops-helm-library-chart-patterns": """
## Semver contract for library consumers

Breaking template change checklist:

- Major version bump
- Migration guide with before/after `helm template` diff snippet
- Deprecation warning in template for one minor:

```yaml
{{- if .Values.legacyServicePort }}
{{- fail "legacyServicePort removed in platform-lib 2.0 — use .Values.ports.http" }}
{{- end }}
```

Cross-chart integration test repo clones 5 representative consumers—runs on every platform-lib publish before marking release latest in Harbor.

Avoid **global** mutable state in library templates—pure functions of `.Values` and `.Release` only. Hidden `lookup` calls break GitOps deterministic render in Argo CD unless live cluster lookup enabled—document if used sparingly for Secret references.
""",
    "devops-helm-rollback-strategies": """
## Mapping Helm revisions to observability

Annotate deploy events:

```yaml
# post-sync Job
metadata:
  annotations:
    helm.sh/revision: "{{ .Release.Revision }}"
```

Loki query `{app="checkout"} |= "revision"` correlates latency spike start with revision number—speeds rollback target selection.

Database rollback coordination: maintain `schema_migrations` table version in release notes—rollback to revision before migration N requires app version compatible with schema N-1. Helm rollback without DBA involvement is unsafe for coupled schema—flag charts with hooks affecting schema as **non-rollbackable** without runbook.

Helm `--cleanup-on-fail` vs `--atomic`: cleanup removes failed new resources; atomic restores previous revision—prefer atomic for production; understand difference during incident stress.
""",
    "devops-helm-secrets-sops": """
## Age key ceremony

Generate age key in HSM-backed ceremony; split key shards to security + platform leads; reconstruct only in break-glass. Document `sops updatekeys` migration when rotating age recipients—re-encrypt all files in single maintenance window.

Helm values file merge order matters—later files override:

```bash
helm upgrade -f values.yaml -f values-prod.yaml -f secrets.prod.enc.yaml
```

Document order in README—wrong order applies prod secrets to wrong keys. CI validates secrets file only referenced in prod helmfile environment block.

Detect accidental decryption in logs—helm-secrets debug mode off in CI; scan CI logs for `BEGIN PRIVATE KEY` patterns. Pre-commit hook runs `sops filestatus` ensuring all matching files encrypted.
""",
    "devops-helm-values-schema-validation": """
## IDE and DX integration

JSON Schema `$id` published to internal HTTPS endpoint—VS Code yaml.schemas setting auto-validates values files on edit:

```json
"yaml.schemas": {
  "https://schemas.example.com/charts/api-values.schema.json": "charts/api/values*.yaml"
}
```

Consumer repos wrapping platform chart inherit schema via `values.schema.json` `$ref` to parent schema extended with team-specific required fields—composition without duplication.

Fuzz testing: generate random valid JSON from schema (quicktype/fake schema) → helm template — catches template nil pointer errors on edge values platform teams did not anticipate.
""",
    "devops-helmfile-multi-env": """
## helmfile with monorepo triggers

Only run helmfile diff when relevant paths change:

```yaml
# GitHub Actions paths filter
paths:
  - deploy/helmfile.yaml
  - deploy/environments/**
  - deploy/values/**
```

Multiple helmfiles per team in monorepo—root helmfile uses `helmfiles:` inclusion:

```yaml
helmfiles:
  - path: teams/platform/helmfile.yaml
  - path: teams/checkout/helmfile.yaml
```

State backend: helmfile itself stateless—Helm release secrets in cluster are state. Document disaster recovery: backup etcd or export `helm list -A` after each platform helmfile apply for inventory cross-check.

Drift detection: scheduled job `helmfile -e prod diff` posts to Slack if non-zero—GitOps not managing same releases implies imperative drift from manual helm upgrades.
""",
    "devops-horizontal-pod-autoscaler-custom-metrics": """
## Metric reliability for autoscaling

HPA decisions on stale metrics cause under/over scaling—Prometheus `rate()` lookback must exceed scrape interval; adapter rule evaluation interval < HPA sync period. Runbook: if Prometheus down, HPA holds last scale—do not assume scale-to-min; set `behavior.scaleDown` conservative during metrics outages.

Custom metrics RBAC: prometheus-adapter needs permission to list pods/nodes for resource mapping—lock down adapter ServiceAccount; compromised adapter exposes metrics API surface.

Load test acceptance criteria for new HPA metric: scale from min to max within SLO time at 2× expected peak traffic; scale down within 10m after load stops without oscillation > 2 cycles. Document metric in service runbook alongside CPU thresholds—on-call must know which dashboard proves HPA input sane.
""",
    "devops-iam-policy-simulator": """
## Organization-wide policy simulation

For AWS Organizations, use `simulate-principal-policy` on account member role plus separate SCP simulation via IAM Access Analyzer custom policy checks. Document effective permission as intersection:

```
Effective = (Identity policies) ∩ (Permissions boundary) ∩ (SCP) ∩ (Session policy) ∩ (Resource policy)
```

Terraform `iam_policy` attachment drift detection—weekly job compares live AWS policy version ID to Terraform state; drift triggers revert or intentional import.

GCP Policy Simulator batch for service account before GKE workload identity bind—verify cannot reach `storage.objects.delete` on production bucket. Azure: Entra PIM activation time-limited—simulator before activation approval workflow.

Post-change validation window: CloudTrail Lake query `errorCode=AccessDenied` grouped by `userIdentity.arn` for changed role—unexpected denies mean production broken; unexpected allows mean policy too broad—both block complete ticket closure.
""",
}


def main():
    for slug, text in EXPANSIONS.items():
        path = BLOG / f"{slug}.md"
        content = path.read_text()
        marker = "\n## Resources\n"
        if marker not in content:
            print(f"SKIP {slug}: no Resources section")
            continue
        if text.strip() in content:
            print(f"SKIP {slug}: already expanded")
            continue
        path.write_text(content.replace(marker, text + marker))
        print(f"OK {slug}")


if __name__ == "__main__":
    main()
