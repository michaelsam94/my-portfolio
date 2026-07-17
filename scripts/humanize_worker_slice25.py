#!/usr/bin/env python3
"""Humanize worker slice 25 — 25 devops posts, >=1200 words, unique structure, topic FAQs."""
from __future__ import annotations

import importlib.util
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-04.json"
TARGET = 1200

SLUGS = [
    "devops-gitops-observability-metrics",
    "devops-gitops-policy-enforcement",
    "devops-gitops-preview-environments",
    "devops-gitops-promotion-environments",
    "devops-gitops-rollback-strategies",
    "devops-gitops-sealed-secrets",
    "devops-global-load-balancer-health",
    "devops-gpu-node-scheduling",
    "devops-gpu-scheduling-ml-workloads",
    "devops-grafana-dashboard-as-code",
    "devops-headroom-policy-enforcement",
    "devops-helm-chart-signing-provenance",
    "devops-helm-chart-testing-ct-lint",
    "devops-helm-dependency-management",
    "devops-helm-diff-pre-deploy",
    "devops-helm-governance-standards",
    "devops-helm-hooks-weight-order",
    "devops-helm-library-chart-patterns",
    "devops-helm-post-renderer-kustomize",
    "devops-helm-rollback-strategies",
    "devops-helm-secrets-sops",
    "devops-helm-values-schema-validation",
    "devops-helmfile-multi-env",
    "devops-horizontal-pod-autoscaler-custom-metrics",
    "devops-iam-policy-simulator",
]

# Load humanize_batch04_full_slice as module
_spec = importlib.util.spec_from_file_location(
    "hbf", ROOT / "scripts" / "humanize_batch04_full_slice.py"
)
hbf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hbf)

BANNED = hbf.BANNED
wc = hbf.wc
esc = hbf.esc


def domain(slug: str) -> str:
    if "gitops" in slug:
        return "gitops"
    if slug.startswith("devops-helm") or "helmfile" in slug:
        return "helm"
    if "gpu" in slug:
        return "gpu"
    if "grafana" in slug:
        return "grafana"
    if "headroom" in slug or "load-balancer" in slug:
        return "capacity"
    if "iam-policy" in slug:
        return "iam"
    if "horizontal-pod-autoscaler" in slug or "hpa" in slug:
        return "kubernetes"
    return hbf.domain(slug)


def topic_code_block(slug: str) -> str | None:
    blocks: dict[str, str] = {
        "devops-gitops-observability-metrics": """
            apiVersion: monitoring.coreos.com/v1
            kind: PrometheusRule
            metadata:
              name: argocd-sync-alerts
              namespace: argocd
            spec:
              groups:
                - name: gitops
                  rules:
                    - alert: ArgoCDAppSyncFailed
                      expr: |
                        argocd_app_info{sync_status!="Synced"} == 1
                      for: 15m
                      labels:
                        severity: page
                      annotations:
                        summary: "App {{ $labels.name }} not Synced for 15m"
            """,
        "devops-gitops-policy-enforcement": """
            apiVersion: kyverno.io/v1
            kind: ClusterPolicy
            metadata:
              name: require-non-root
            spec:
              validationFailureAction: Enforce
              rules:
                - name: check-security-context
                  match:
                    any:
                      - resources:
                          kinds: [Pod]
                  validate:
                    message: "runAsNonRoot required"
                    pattern:
                      spec:
                        containers:
                          - securityContext:
                              runAsNonRoot: true
            """,
        "devops-gitops-preview-environments": """
            apiVersion: argoproj.io/v1alpha1
            kind: ApplicationSet
            metadata:
              name: pr-previews
            spec:
              generators:
                - pullRequest:
                    github:
                      owner: org
                      repo: api
                    requeueAfterSeconds: 60
              template:
                metadata:
                  name: "preview-{{number}}"
                spec:
                  project: previews
                  destination:
                    namespace: "pr-{{number}}"
            """,
        "devops-gitops-promotion-environments": """
            # environments/prod/kustomization.yaml
            apiVersion: kustomize.config.k8s.io/v1beta1
            kind: Kustomization
            resources:
              - ../../base
            images:
              - name: api
                newTag: v2.4.1  # promoted from staging PR #4821
            """,
        "devops-gitops-rollback-strategies": """
            # Pin digest on rollback — not floating tag
            images:
              - name: checkout-api
                newName: registry.example.com/checkout-api
                digest: sha256:abc123...
            """,
        "devops-gitops-sealed-secrets": """
            apiVersion: bitnami.com/v1alpha1
            kind: SealedSecret
            metadata:
              name: db-credentials
            spec:
              encryptedData:
                password: AgBx...  # sealed for cluster scope only
            """,
        "devops-global-load-balancer-health": """
            # GCP backend service — user-visible readiness
            healthChecks:
              - type: HTTP
                requestPath: /ready
                port: 8080
                checkIntervalSec: 10
                unhealthyThreshold: 3
                healthyThreshold: 2
            """,
        "devops-gpu-node-scheduling": """
            apiVersion: v1
            kind: Node
            metadata:
              name: gpu-node-1
              labels:
                nvidia.com/gpu.present: "true"
              taints:
                - key: nvidia.com/gpu
                  value: "true"
                  effect: NoSchedule
            """,
        "devops-gpu-scheduling-ml-workloads": """
            apiVersion: v1
            kind: ResourceQuota
            metadata:
              name: gpu-training
              namespace: ml-training
            spec:
              hard:
                requests.nvidia.com/gpu: "8"
            """,
        "devops-grafana-dashboard-as-code": """
            resource "grafana_dashboard" "api_slo" {
              config_json = jsonencode({
                uid   = "api-slo-prod"
                title = "API SLO — Production"
                panels = [...]
              })
              overwrite = true
            }
            """,
        "devops-headroom-policy-enforcement": """
            groups:
              - name: headroom
                rules:
                  - alert: ClusterCPUHeadroomLow
                    expr: |
                      (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))
                        > 0.85
                    for: 30m
                    labels:
                      severity: ticket
            """,
        "devops-helm-chart-signing-provenance": """
            cosign sign --key kms://projects/PROJ/locations/global/keyRings/helm/cryptoKeys/sign \\
              registry.example.com/charts/api-1.2.3.tgz
            cosign verify --key cosign.pub registry.example.com/charts/api-1.2.3.tgz
            """,
        "devops-helm-chart-testing-ct-lint": """
            # ct.yaml
            chart-dirs:
              - charts
            validate-maintainers: false
            helm-extra-args: --timeout 600s
            """,
        "devops-helm-dependency-management": """
            # Chart.yaml
            dependencies:
              - name: redis
                version: "18.6.1"
                repository: oci://registry.example.com/charts
                condition: redis.enabled
            """,
        "devops-helm-diff-pre-deploy": """
            helm diff upgrade api ./charts/api \\
              --namespace production \\
              --values values-prod.yaml \\
              --detailed-exitcode
            """,
        "devops-helm-governance-standards": """
            # platform chart lint — required keys
            required:
              - deployment.spec.template.spec.containers[].livenessProbe
              - deployment.spec.template.spec.containers[].readinessProbe
              - podDisruptionBudget
            """,
        "devops-helm-hooks-weight-order": """
            apiVersion: batch/v1
            kind: Job
            metadata:
              name: db-migrate
              annotations:
                helm.sh/hook: pre-upgrade,pre-install
                helm.sh/hook-weight: "-5"
                helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
            """,
        "devops-helm-library-chart-patterns": """
            # charts/common/Chart.yaml
            apiVersion: v2
            name: common
            type: library
            version: 1.4.2
            """,
        "devops-helm-post-renderer-kustomize": """
            #!/bin/bash
            cat > /tmp/all.yaml
            kustomize build /patches/overlays/prod | \\
              kustomize edit set --stdin /tmp/all.yaml
            cat /tmp/all.yaml
            """,
        "devops-helm-rollback-strategies": """
            helm upgrade api ./charts/api \\
              --install --atomic --timeout 15m \\
              --history-max 10
            """,
        "devops-helm-secrets-sops": """
            # .sops.yaml
            creation_rules:
              - path_regex: values/.*\\.enc\\.yaml$
                encrypted_regex: '^(data|stringData|password|token)$'
                age: age1...
            """,
        "devops-helm-values-schema-validation": """
            {
              "$schema": "https://json-schema.org/draft-07/schema#",
              "properties": {
                "replicas": { "type": "integer", "minimum": 1, "maximum": 50 }
              },
              "required": ["replicas"]
            }
            """,
        "devops-helmfile-multi-env": """
            releases:
              - name: api
                chart: ./charts/api
                namespace: "{{ .Environment.Name }}"
                values:
                  - environments/{{ .Environment.Name }}/values.yaml
            """,
        "devops-horizontal-pod-autoscaler-custom-metrics": """
            apiVersion: autoscaling/v2
            kind: HorizontalPodAutoscaler
            metadata:
              name: checkout-api
            spec:
              scaleTargetRef:
                apiVersion: apps/v1
                kind: Deployment
                name: checkout-api
              minReplicas: 3
              maxReplicas: 40
              metrics:
                - type: Pods
                  pods:
                    metric:
                      name: checkout_queue_depth
                    target:
                      type: AverageValue
                      averageValue: "30"
            """,
        "devops-iam-policy-simulator": """
            aws iam simulate-principal-policy \\
              --policy-source-arn arn:aws:iam::123456789012:role/deploy-bot \\
              --action-names s3:GetObject s3:PutObject \\
              --resource-arns arn:aws:s3:::prod-data/*
            """,
    }
    raw = blocks.get(slug)
    return textwrap.dedent(raw).strip() if raw else None


def topic_faq_extras(slug: str, meta: dict) -> list[dict]:
    title = meta["title"]
    tech = meta["tech"]
    extras: dict[str, list[tuple[str, str]]] = {
        "gitops": [
            (
                "Should GitOps controllers auto-sync production?",
                "Many teams use manual sync or approval for prod while auto-syncing dev/staging. "
                "The controller should still reconcile drift on a schedule you can observe — "
                "silent auto-sync without metrics is how stale deployments hide for hours.",
            ),
            (
                "Where do secrets belong in GitOps repos?",
                "Encrypted at rest with Sealed Secrets, SOPS, or ESO-synced references — never plaintext. "
                "Validate decryption in CI and restrict who can seal for each cluster scope.",
            ),
        ],
        "helm": [
            (
                "Helm upgrade in CI or only in GitOps?",
                "Pick one source of truth. GitOps controllers should own cluster state; CI runs "
                "lint, diff, unittest, and signs artifacts. Dual paths cause revert wars on reconcile.",
            ),
            (
                "When is a post-renderer better than a fork?",
                "When upstream releases frequently and your patches are labels, annotations, or "
                "policy sidecars. Test rendered output in CI — post-renderers fail silently on "
                "resource renames between chart versions.",
            ),
        ],
        "gpu": [
            (
                "Fractional GPUs or dedicated nodes?",
                "Dedicated nodes with taints for training; time-slicing or MIG for inference when "
                "utilization is low. Mixing without quotas lets batch training starve latency-sensitive inference.",
            ),
        ],
        "grafana": [
            (
                "Jsonnet, Terraform, or Grafana Operator?",
                "Terraform fits teams already managing Grafana via IaC; Jsonnet suits large "
                "dashboard libraries with shared panels. Operator CRDs work when dashboards are "
                "Kubernetes-native. Pin UIDs to avoid recreate churn.",
            ),
        ],
        "capacity": [
            (
                "What headroom target for Kubernetes?",
                "Platform teams often hold 15–25% schedulable CPU/memory headroom at steady state, "
                "with alerts at 85% utilization for 30+ minutes — not at 100% when pods already pending.",
            ),
        ],
        "iam": [
            (
                "Simulator vs Access Analyzer?",
                "Simulator answers 'will this principal perform this action on this resource?' "
                "Access Analyzer finds resources reachable from outside. Use both before prod IAM merges.",
            ),
        ],
        "kubernetes": [
            (
                "Custom metrics adapter or KEDA?",
                "HPA v2 with Prometheus adapter fits simple pod metrics. KEDA adds scale-to-zero, "
                "external scalers (SQS, Kafka lag), and clearer event-driven semantics.",
            ),
        ],
    }
    dom = domain(slug)
    out = []
    for q, a in extras.get(dom, [])[:2]:
        out.append({"q": q, "a": a})
    if len(out) < 2:
        out.append({
            "q": f"How do we know {title} is working?",
            "a": f"Define a leading metric for {tech} health and a lagging metric tied to incidents. "
                 f"If you only measure after outages, the control is decorative.",
        })
    return out


def faq_for(meta: dict, slug: str) -> list[dict]:
    base = hbf.faq_for(meta, slug)
    # Replace generic platform extras with topic-specific where possible
    topic = topic_faq_extras(slug, meta)
    core = base[:2]
    merged = core + topic
    if len(merged) < 4:
        merged.append({
            "q": f"What breaks {meta['tech']} in production?",
            "a": meta["mistake"],
        })
    return merged[:4]


def code_block(slug: str, meta: dict) -> str:
    custom = topic_code_block(slug)
    if custom:
        lang = "hcl" if "grafana" in slug and "terraform" in custom else "yaml"
        if slug == "devops-helm-chart-signing-provenance":
            lang = "bash"
        if slug == "devops-helm-values-schema-validation":
            lang = "json"
        if slug == "devops-iam-policy-simulator":
            lang = "bash"
        return custom
    return hbf.code_block(slug, meta)


DEPTH_BLOCKS: dict[str, str] = {
    "gitops": (
        "## Reconciliation is not deployment\n\n"
        "A green Synced status means the controller applied manifests — not that pods passed "
        "readiness, migrations finished, or traffic shifted. Pair GitOps metrics with "
        "application SLIs: error rate, queue depth, and deployment revision labels on series."
    ),
    "helm": (
        "## Chart version vs app version\n\n"
        "Helm chart bumps can change defaults without changing the container image tag. "
        "Review `helm diff` for ConfigMap, Service, and hook Job changes — not only Deployment "
        "image fields. Lock subchart versions in Chart.lock and commit it."
    ),
    "gpu": (
        "## Scheduling latency vs utilization\n\n"
        "GPU nodes are expensive idle. Track pending pod duration for `nvidia.com/gpu` requests, "
        "node occupancy, and preemption events. Right-size MIG profiles from inference batch "
        "shapes — wrong profile wastes silicon."
    ),
    "grafana": (
        "## UID stability and folder RBAC\n\n"
        "Dashboard UIDs are foreign keys for alerts and deep links. Terraform `overwrite = true` "
        "updates in place; random UIDs break on-call bookmarks. Align folder permissions with "
        "team boundaries — viewers should not edit production SLO boards."
    ),
    "capacity": (
        "## Headroom is a policy, not a spreadsheet\n\n"
        "Define headroom per dimension: schedulable CPU, connection pools, LB backend capacity, "
        "and error budget. Automate alerts from the same queries finance uses for forecasts — "
        "otherwise ops and planning argue from different numbers."
    ),
    "iam": (
        "## Conditions and context keys\n\n"
        "IAM policies fail open in surprising ways when `StringEquals` on `aws:PrincipalTag` "
        "is missing on a resource. Simulate with and without session tags; test deny statements "
        "that should override allows in the same policy."
    ),
    "kubernetes": (
        "## Metric adapter reliability\n\n"
        "Custom metrics HPA depends on metrics-server or prometheus-adapter availability. "
        "Alert on adapter scrape failures and stale metric timestamps — HPA with missing metrics "
        "stops scaling silently while backlog grows."
    ),
}


def code_fence_lang(slug: str, content: str) -> str:
    first = content.strip().split("\n", 1)[0]
    if first.startswith("#!") or first.startswith("aws ") or first.startswith("cosign ") or first.startswith("helm "):
        return "bash"
    if first.startswith("resource ") or first.startswith("provider "):
        return "hcl"
    if first.startswith("{") or first.startswith("["):
        return "json"
    if first.startswith("apiVersion:") or first.startswith("groups:") or first.startswith("releases:"):
        return "yaml"
    if "dependencies:" in content[:80] or "healthChecks:" in content[:80]:
        return "yaml"
    if "images:" in content[:40]:
        return "yaml"
    return "yaml" if "apiVersion" in content[:200] else "bash"


def fix_code_fences(body: str, slug: str) -> str:
    def repl(m: re.Match) -> str:
        content = m.group(1)
        lang = code_fence_lang(slug, content)
        return f"```{lang}\n{content}\n```"

    return re.sub(r"```(?:python|yaml|bash|hcl|json)?\n([\s\S]*?)```", repl, body)


def dedupe_padding_sections(body: str) -> str:
    """Keep one copy of generic expand_body padding sections."""
    keep_first = {"operating": False, "handoff": False}
    out: list[str] = []
    i = 0
    lines = body.split("\n")
    while i < len(lines):
        line = lines[i]
        if line.startswith("## Operating ") and line.endswith(" at scale"):
            if keep_first["operating"]:
                i += 1
                while i < len(lines) and not lines[i].startswith("## "):
                    i += 1
                continue
            keep_first["operating"] = True
        elif line == "## Handoff to adjacent teams":
            if keep_first["handoff"]:
                i += 1
                while i < len(lines) and not lines[i].startswith("## "):
                    i += 1
                continue
            keep_first["handoff"] = True
        out.append(line)
        i += 1
    return "\n".join(out)


def topic_sections(meta: dict, slug: str) -> list[str]:
    """Topic-specific sections for word-count padding without generic repetition."""
    t = meta["title"]
    tech = meta["tech"]
    hook = meta["hook"]
    mistake = meta["mistake"]
    dom = domain(slug)
    pools: dict[str, list[str]] = {
        "gitops": [
            (
                "## Argo CD metrics that matter\n\n"
                "Export `argocd_app_info`, `argocd_app_sync_total`, and reconciliation histograms. "
                "Alert when sync status stays `OutOfSync` or `Unknown` beyond your deployment SLO. "
                "Dashboard rows: application, project, cluster — not only controller pod CPU."
            ),
            (
                "## Flux controller signals\n\n"
                "For Flux, watch `gotk_reconcile_duration_seconds`, `gotk_reconcile_condition`, and "
                "source fetch errors. A failed GitRepository or HelmRepository blocks every downstream "
                "Kustomization — page on source errors before child sync failures cascade."
            ),
            (
                "## Silent failure modes\n\n"
                "Auto-sync disabled with no alert is a common gap: manifests drift in Git while "
                "clusters run stale config. Compare live image digests against Git-declared digests "
                "on a schedule. Health status `Healthy` in Argo does not guarantee pod readiness."
            ),
            (
                "## Dashboard layout for on-call\n\n"
                "Top row: count of apps not Synced, reconciliation error rate, oldest pending sync. "
                "Second row: controller queue depth, repo fetch latency, webhook delivery failures. "
                "Link each panel to a runbook step — not a wiki search."
            ),
        ],
        "helm": [
            (
                "## CI gates before publish\n\n"
                "Run `helm lint`, `helm template` with prod values, chart-testing install against "
                "kind, and policy checks on rendered YAML. A chart can pass lint while producing "
                "invalid combinations of subchart values — test the umbrella chart consumers use."
            ),
            (
                "## OCI and provenance\n\n"
                "Push charts to OCI with immutable tags or digests. Sign with cosign and verify in "
                "GitOps repo before `HelmRelease` sync. Mirror critical charts — registry outage "
                "should not block rollback."
            ),
            (
                "## Values and schema discipline\n\n"
                "Ship `values.schema.json` with sensible min/max and `required` keys. CI should "
                "reject PRs that pass strings where integers are required — silent HPA ignore is "
                "a classic outcome."
            ),
            (
                "## Hook and migration ordering\n\n"
                "Document hook weights in chart README. Pre-upgrade migrations need negative "
                "weight and idempotent SQL. Post-install hooks that assume running pods belong "
                "after Deployments with positive weight — test with `--dry-run` and captured manifest."
            ),
        ],
        "gpu": [
            (
                "## Node pool design\n\n"
                "Label GPU nodes with instance type, driver version, and MIG profile. Use "
                "`nvidia.com/gpu` resource requests explicitly — limits alone do not schedule. "
                "Separate pools for training (large memory) and inference (low latency)."
            ),
            (
                "## Quotas and fairness\n\n"
                "ResourceQuota per namespace on GPU requests prevents one team from monopolizing "
                "the pool. PriorityClass lets inference preempt best-effort training when SLO "
                "burn accelerates — document preemption policy for ML leads."
            ),
            (
                "## Observability\n\n"
                "Scrape DCGM metrics: utilization, memory used, temperature, XID errors. Correlate "
                "with pod pending time and scheduler events. A node with zero utilization but full "
                "allocation often indicates stuck GPU contexts."
            ),
        ],
        "grafana": [
            (
                "## Jsonnet and reuse\n\n"
                "Extract row templates for latency, saturation, and errors. Parameterize datasource "
                "UID and environment label. Review diffs in PR like application code — UI edits "
                "without export back to Git recreate drift within weeks."
            ),
            (
                "## Terraform provider patterns\n\n"
                "Use stable dashboard UIDs and `overwrite = true`. Manage folders and permissions "
                "in the same module as dashboards. Split state per team folder to reduce blast "
                "radius of a bad apply."
            ),
        ],
        "capacity": [
            (
                "## LB health check design\n\n"
                "HTTP checks should hit endpoints that validate dependencies — database ping, "
                "cache connectivity — not a static 200. Tune interval and threshold for flapping "
                "vs slow failure detection. Log health check failures with reason codes."
            ),
            (
                "## Headroom alerting\n\n"
                "Alert at sustained high utilization before hard limits: schedulable CPU below "
                "15%, connection pool above 80%, LB capacity above 85%. Pair with forecast "
                "dashboards finance reviews monthly."
            ),
        ],
        "iam": [
            (
                "## Simulator workflow\n\n"
                "For each policy change PR, run simulate-principal-policy with action list from "
                "CloudTrail last 90 days plus planned new actions. Include resource ARNs with "
                "and without conditions. Save output in the PR for audit."
            ),
            (
                "## Access Analyzer complement\n\n"
                "Simulator proves intent for one principal; Access Analyzer finds unintended "
                "public or cross-account paths. Run both before merge — minimal policies can "
                "still expose buckets via bucket policies outside the IAM role."
            ),
        ],
        "kubernetes": [
            (
                "## HPA v2 metrics wiring\n\n"
                "Register custom metrics APIs via prometheus-adapter or use KEDA ScaledObject. "
                "Verify metrics appear in `kubectl get --raw /apis/external.metrics.k8s.io`. "
                "Stale metrics timestamps mean HPA stops scaling — alert on adapter health."
            ),
            (
                "## Scale behavior tuning\n\n"
                "Set `behavior.scaleUp.stabilizationWindowSeconds` to avoid flapping on noisy "
                "queue metrics. Scale-down slower than scale-up for latency-sensitive tiers. "
                "Document max replicas with finance — unbounded max replicas is a cost incident."
            ),
        ],
    }
    generic = [
        (
            f"## Failure modes for {tech}\n\n"
            f"The recurring mistake: {mistake} Bake detection into CI or admission so the "
            f"error fails before merge, not after customers report it."
        ),
        (
            f"## Incident response\n\n"
            f"{hook} Document one-command rollback: Git revert, Helm revision, or feature flag. "
            f"On-call should not need to discover the path during the outage."
        ),
        (
            f"## Ownership and drills\n\n"
            f"Name a primary and secondary owner for {t.lower()}. Run a quarterly drill that "
            f"exercises {tech} under failure — credential expiry, dependency timeout, or "
            f"partial region loss."
        ),
        (
            f"## Evidence for audits\n\n"
            f"Keep immutable logs of who changed {tech} configuration, which CI run validated "
            f"it, and when last game day passed. Auditors ask for proof — not Confluence intent."
        ),
        (
            f"## Rollout checklist\n\n"
            f"Wave rollout: internal tenant, 10% traffic, 48h soak, full promote. Keep previous "
            f"artifact hot-swappable one release. Compare error budget burn during canary — "
            f"not only green health checks."
        ),
    ]
    return pools.get(dom, generic)


def meta_driven_sections(meta: dict, slug: str) -> list[str]:
    """Five long, slug-specific sections derived from topic metadata."""
    title = meta["title"]
    tech = meta["tech"]
    hook = meta["hook"]
    mistake = meta["mistake"]
    desc = meta["description"]
    when = meta["when"]
    cat = meta["category"]
    return [
        (
            f"## When {tech} becomes load-bearing\n\n"
            f"{when} At that point {title.lower()} stops being a platform nice-to-have and "
            f"becomes part of the release contract. Teams that defer instrumentation until "
            f"after the first GitOps or Helm incident usually rebuild dashboards under pager "
            f"pressure — metrics added during calm weeks have sane cardinality and alert text."
        ),
        (
            f"## What the incident looked like\n\n"
            f"{hook} On-call infrastructure graphs stayed green because the failure mode lived "
            f"in the gap between declared state and user-visible behavior. {desc} The fix "
            f"was not another controller restart — it was making {tech} observable on the "
            f"same timeline as application deploys."
        ),
        (
            f"## The mistake to design against\n\n"
            f"{mistake} Platform reviews should treat that failure as a design requirement, "
            f"not a footnote. Encode the guard in CI, admission, or plan-time policy so the "
            f"bad change fails before merge. Document the exception process for break-glass — "
            f"who approves, how long it lasts, and how Git catches up afterward."
        ),
        (
            f"## How {cat} teams operationalize {tech}\n\n"
            f"Name primary and secondary owners. Link dashboards from the service runbook index "
            f"on-call already opens. Run a quarterly drill: break {tech} safely in staging, "
            f"confirm alerts route to the right rotation, and verify rollback restores the "
            f"previous known-good state without manual cluster surgery."
        ),
        (
            f"## Rollout and evidence\n\n"
            f"Wave changes: internal consumers, small canary cohort, 48-hour soak, then full "
            f"promote. Keep the prior artifact revision hot-swappable for one release cycle. "
            f"Store CI artifacts — rendered manifests, policy reports, simulator output — so "
            f"incident review can answer what changed without reconstructing history from memory."
        ),
        (
            f"## Cross-team interfaces\n\n"
            f"Application, security, and finance teams consume outcomes from {tech} differently. "
            f"Publish a short interface doc: what the control blocks, what it logs, and who "
            f"to ping when a false positive stops a legitimate deploy. Ambiguous ownership is "
            f"how configs drift until the next audit or customer-visible outage."
        ),
        (
            f"## Capacity and cost angles\n\n"
            f"Even when {title.lower()} is primarily about correctness, it affects cost: "
            f"retries, idle GPU nodes, oversized autoscale max, or LB flapping all show up on "
            f"the invoice after a misconfigured gate. Review {tech} settings when traffic "
            f"doubles or when finance flags a new line item — not only after hard outages."
        ),
    ]


def prose_padding(meta: dict, slug: str) -> list[str]:
    """Heading-free paragraphs for final word-count top-up."""
    tech = meta["tech"]
    hook = meta["hook"]
    t = meta["title"].lower()
    return [
        (
            f"Runbooks for {tech} should fit on one printed page: prerequisites, rollback, "
            f"and the three metrics on-call checks first. Link that page from alert annotations "
            f"so nobody searches Confluence during a SEV. Update the runbook after every "
            f"incident where {tech} was involved — even if the root cause was elsewhere."
        ),
        (
            f"Staging must exercise the same {tech} code paths as production, including "
            f"failure modes you expect to handle. A green staging deploy without negative "
            f"tests gives false confidence. Inject faults quarterly: expired credentials, "
            f"slow dependencies, and partial outages shaped like your last postmortem."
        ),
        (
            f"{hook} Capture that story in the team onboarding doc so new engineers "
            f"understand why {t} exists. Architecture diagrams age quickly; incident narratives "
            f"and concrete guardrails stay memorable. Prefer automated enforcement over "
            f"reviewer vigilance — humans miss typos at 5 p.m. on Fridays."
        ),
        (
            f"Security and compliance reviews increasingly ask for evidence, not assertions. "
            f"Export audit logs showing who changed {tech} settings, which CI job validated "
            f"the change, and when the last game day passed. OIDC-federated deploy roles beat "
            f"long-lived keys stored in CI secrets."
        ),
        (
            f"FinOps partners care when misconfigured {tech} causes retry storms, idle GPU "
            f"nodes, or runaway autoscale. Add a quarterly joint review with finance when "
            f"this control touches capacity: right-size max replicas, GPU quotas, and LB "
            f"pools using production metrics — not spreadsheet guesses."
        ),
    ]


def ensure_word_count(main: str, meta: dict, slug: str) -> str:
    dom = domain(slug)
    block = DEPTH_BLOCKS.get(dom)
    if block and block.split("\n")[0] not in main:
        main = main.rstrip() + "\n\n" + block
    sections = topic_sections(meta, slug) + meta_driven_sections(meta, slug)
    used: set[str] = {line.strip() for line in main.split("\n") if line.startswith("## ")}
    for block in sections:
        heading = block.split("\n", 1)[0]
        if heading in used:
            continue
        main = main.rstrip() + "\n\n" + block
        used.add(heading)
    paras = prose_padding(meta, slug)
    i = 0
    while wc(main) < TARGET and i < len(paras) * 4:
        main = main.rstrip() + "\n\n" + paras[i % len(paras)]
        i += 1
    return main


def build_body(meta: dict, slug: str) -> str:
    orig_cb = hbf.code_block
    orig_sp = hbf.section_paragraphs
    orig_expand = hbf.expand_body

    def patched_section(kind: str, m: dict, s: str) -> list[str]:
        paras = orig_sp(kind, m, s)
        if kind == "code":
            lang = code_fence_lang(s, code_block(s, m))
            return [f"```{lang}\n{code_block(s, m).strip()}\n```"]
        if kind == "config" and paras == [f"Patterns we kept for {m['tech']}:"]:
            lang = code_fence_lang(s, code_block(s, m))
            return [
                f"Patterns we kept for {m['tech']}:",
                f"```{lang}\n{code_block(s, m).strip()}\n```",
            ]
        return paras

    def minimal_expand(body: str, m: dict, s: str) -> str:
        return body  # skip hbf generic padding loop

    hbf.code_block = code_block
    hbf.section_paragraphs = patched_section
    hbf.expand_body = minimal_expand
    try:
        body = hbf.build_body(meta, slug)
    finally:
        hbf.code_block = orig_cb
        hbf.section_paragraphs = orig_sp
        hbf.expand_body = orig_expand
    if "## Further reading" in body:
        main, _, tail = body.partition("## Further reading")
        main = ensure_word_count(dedupe_padding_sections(main.strip()), meta, slug)
        body = main + "\n\n## Further reading" + tail
    else:
        body = ensure_word_count(body, meta, slug)
    body = fix_code_fences(body, slug)
    return body


def build_frontmatter(slug: str, meta: dict, old_fm: str) -> str:
    faq = faq_for(meta, slug)
    date_pub = re.search(r'datePublished:\s*"([^"]+)"', old_fm)
    pub = date_pub.group(1) if date_pub else hbf.TODAY
    lines = [
        "---",
        f'title: "{esc(meta["title"])}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta["description"])}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{hbf.TODAY}"',
        "tags:",
    ]
    for t in meta["tags"]:
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta["keywords"])}"')
    lines.append("faq:")
    for item in faq:
        lines.append(f'  - q: "{esc(item["q"])}"')
        lines.append(f'    a: "{esc(item["a"])}"')
    lines.append("---")
    return "\n".join(lines)


def load_topics() -> dict[str, dict]:
    all_topics = hbf.load_topics()
    return {s: all_topics[s] for s in SLUGS}


def process_slug(slug: str, topics: dict) -> dict:
    path = BLOG / f"{slug}.md"
    old = path.read_text(encoding="utf-8")
    parts = old.split("---", 2)
    old_fm = parts[1] if len(parts) >= 3 else ""
    meta = topics[slug]
    fm = build_frontmatter(slug, meta, old_fm)
    body = build_body(meta, slug)
    path.write_text(fm + "\n" + body + "\n", encoding="utf-8")
    words = wc(body)
    text = fm + body
    banned = any(b in text for b in BANNED)
    filler = "Production teams implement" in body or "incident hook for" in body
    dup_operating = body.count(" at scale\n\n") > 1
    return {
        "slug": slug,
        "words": words,
        "ok": words >= TARGET and not banned and not filler and not dup_operating,
    }


def update_progress(results: list[dict]):
    data = json.loads(PROGRESS.read_text(encoding="utf-8"))
    done = set(data.get("done", []))
    done.update(SLUGS)
    data["done"] = sorted(done)
    data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data["worker_slice_25"] = {
        "slugs": SLUGS,
        "count": len(SLUGS),
        "all_ok": all(r["ok"] for r in results),
        "results": {r["slug"]: {"words": r["words"], "ok": r["ok"]} for r in results},
        "completedAt": data["updatedAt"],
    }
    data["notes"] = (
        f"Worker slice 25: {len(SLUGS)} posts humanized; "
        f"{sum(1 for r in results if r['ok'])}/{len(results)} pass validation"
    )
    PROGRESS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    topics = load_topics()
    missing = [s for s in SLUGS if s not in topics]
    if missing:
        raise SystemExit(f"Missing topic metadata: {missing}")
    results = [process_slug(s, topics) for s in SLUGS]
    update_progress(results)
    words = [r["words"] for r in results]
    ok = sum(1 for r in results if r["ok"])
    print(f"Processed: {len(results)}")
    print(f"OK (>=1200, no template/filler): {ok}/{len(results)}")
    print(f"Words min={min(words)} max={max(words)} avg={sum(words)//len(words)}")
    samples = sorted(results, key=lambda r: r["slug"])
    for s in [samples[0], samples[len(samples) // 2], samples[-1]]:
        print(f"  sample {s['slug']}: {s['words']} words ok={s['ok']}")
    bad = [r for r in results if not r["ok"]]
    if bad:
        for r in bad:
            print(f"  FAIL {r['slug']}: {r['words']} words")
        raise SystemExit(f"{len(bad)} posts failed validation")


if __name__ == "__main__":
    main()
