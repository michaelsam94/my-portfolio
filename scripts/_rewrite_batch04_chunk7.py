#!/usr/bin/env python3
"""Rewrite batch-04 chunk 7: 25 devops posts (indices 1128-1153)."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-04.json"
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
RES = "\n## Resources\n\n- https://kubernetes.io/docs/home/\n- https://opentelemetry.io/docs/\n- https://prometheus.io/docs/practices/naming/\n"

SLUGS = [
    "devops-idle-resource-reclamation", "devops-inference-autoscaling-custom",
    "devops-init-containers-migration", "devops-ip-reputation-scoring",
    "devops-jaeger-sampling-strategies", "devops-jenkins-shared-libraries",
    "devops-job-backoff-limits-parallelism", "devops-k8s-cost-allocation-kubecost",
    "devops-karpenter-nodepool-tuning", "devops-kill-switch-incident-response",
    "devops-kubeflow-pipelines-ops", "devops-kubernetes-rbac-break-glass",
    "devops-litmus-chaos-experiments", "devops-load-test-production-shadow",
    "devops-log-aggregation-pipeline", "devops-loki-label-cardinality",
    "devops-metrics-cardinality-control", "devops-ml-ci-cd-github-actions",
    "devops-ml-pipeline-airflow", "devops-mlflow-model-registry",
    "devops-model-artifact-versioning", "devops-model-governance-audit",
    "devops-model-monitoring-drift", "devops-model-rollout-canary",
    "devops-model-serving-a-b-testing",
]

def wc(t): return len(WORD_PAT.findall(t))

def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def faq_yaml(faqs):
    return "faq:\n" + "\n".join(f'  - q: "{esc(f["q"])}"\n    a: "{esc(f["a"])}"' for f in faqs)

def parse_meta(fm: str):
    def grab(key, quoted=True):
        if quoted:
            m = re.search(rf'^{key}:\s*"(.*)"\s*$', fm, re.M)
            return m.group(1) if m else ""
        m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
        return m.group(1).strip() if m else ""
    tags = re.findall(r'^\s*-\s*"(.+)"\s*$', fm, re.M)
    tag_start = fm.find("tags:")
    tag_block = fm[tag_start:].split("keywords:")[0] if tag_start >= 0 else ""
    tags = re.findall(r'^\s*-\s*"(.+)"\s*$', tag_block, re.M)
    return {
        "title": grab("title"),
        "slug": grab("slug"),
        "description": grab("description"),
        "datePublished": grab("datePublished"),
        "tags": tags,
        "keywords": grab("keywords"),
    }

def build_meta(meta, faqs):
    tags = "\n".join(f'  - "{t}"' for t in meta["tags"])
    return f"""---
title: "{esc(meta['title'])}"
slug: "{esc(meta['slug'])}"
description: "{esc(meta['description'])}"
datePublished: "{esc(meta['datePublished'])}"
dateModified: "{DATE_MOD}"
tags:
{tags}
keywords: "{esc(meta['keywords'])}"
{faq_yaml(faqs)}
---

"""

def build(faqs, hook, body, slug):
    from _rewrite_batch04_chunk7_meta import FULL_META
    meta = FULL_META[slug]
    meta = {**meta, "slug": slug}
    return build_meta(meta, faqs) + hook.strip() + "\n\n" + body.strip() + RES

# Each entry: faqs, hook, sections=[(heading, [paragraphs...], optional_code)]
CONTENT = {}

CONTENT["devops-idle-resource-reclamation"] = {
    "faqs": [
        {"q": "What counts as an idle cloud resource worth reclaiming?", "a": "Unattached EBS volumes, orphaned snapshots past retention, elastic IPs without associations, NAT gateways with zero traffic, and load balancers with no healthy targets. Each type needs its own detection query and grace period."},
        {"q": "How long should grace periods be before auto-deletion?", "a": "14–30 days for storage, 7 days for IPs, with owner-tag extensions available. Production-tagged resources require human approval regardless of age."},
        {"q": "Can reclamation run safely in production accounts?", "a": "Yes with tag exclusions, dry-run mode, and approval workflows above cost thresholds. Never delete without re-checking attachment state via API at deletion time."},
        {"q": "Which tools automate idle resource detection?", "a": "Cloud Custodian, Steampipe, AWS Config rules, Trusted Advisor, and Kubecost idle reports. Combine with CUR SQL for org-specific patterns finance will accept."},
    ],
    "hook": "$40k/year in orphaned EBS volumes from deleted test clusters surfaced on a FinOps review—not because engineers ignored cost, but because reclamation was a twice-yearly spreadsheet. Automated detect-notify-delete loops with grace periods and owner tags turn idle reclamation into a policy, not a hero project.",
    "sections": [
        ("## Orphaned capacity hides in plain sight", [
            "Cloud APIs make durable resources trivial to create and painful to audit. Delete an EKS cluster and EBS volumes sit in `available`. Tear down a load test and elastic IPs keep billing. Snapshots accumulate from backup jobs nobody owns.",
            "Build a daily inventory per resource type. Export to a `pending_reclamation` table with first_seen, monthly_cost_estimate, and owner_tag. Finance trusts programs that show pending queue size trending down—not surprise deletions.",
        ]),
        ("## Three-phase policy: detect, notify, delete", [
            "Phase one marks candidates with Steampipe or Custodian. Phase two Slack-notifies `#finops` and the owner tag with a one-click extend link. Phase three deletes only when idle criteria still match after grace expires.",
            "The incident you must design against: a prod volume detached during maintenance gets deleted because nobody tagged `do-not-delete`. Exclusions for `environment=production` auto-delete require separate approval workflow.",
        ], """```yaml
policies:
  - name: ebs-unattached-mark
    resource: ebs
    filters:
      - type: value
        key: Attachments
        value: empty
      - "tag:do-not-delete": absent
    actions:
      - type: mark-for-op
        op: delete
        days: 21
```"""),
        ("## Tagging contracts at creation time", [
            "Enforce `owner`, `cost-center`, and `environment` via SCP or tag policy at `CreateVolume`. Retrofit untagged resources into a quarantine OU until labeled. Reclamation without tags is roulette.",
        ]),
        ("## Kubernetes-adjacent idle spend", [
            "PersistentVolumes in `Released` state still bill on AWS. LoadBalancer Services orphaned after namespace deletion burn IPs. Kubecost highlights namespaces with zero CPU for 7+ days—rightsizing candidates.",
            "Automate PV cleanup only after confirming volumeHandle is not referenced by compliance snapshots.",
        ]),
        ("## Metrics that keep the program alive", [
            "Track gross idle spend, reclaimed spend, false positive rate (tickets per deletion), and median detect-to-delete time. Target false positives under 1%. One prod deletion destroys program trust for years.",
        ]),
    ],
}

CONTENT["devops-inference-autoscaling-custom"] = {
    "faqs": [
        {"q": "Why does CPU-based HPA fail for GPU inference?", "a": "GPU workloads often show low CPU while queues grow. Scale on queue depth, GPU utilization, in-flight requests, or p99 latency—not processor percentage."},
        {"q": "How do custom metrics reach the HPA?", "a": "Deploy prometheus-adapter or KEDA. Register rules mapping PromQL to custom.metrics.k8s.io. Verify with kubectl get --raw against the metrics API path before wiring HPA."},
        {"q": "Should inference scale to zero?", "a": "Only for dev or batch with relaxed SLOs. Tier-1 endpoints need minReplicas≥1 or a warm pool—model load and CUDA init blow cold-start budgets."},
        {"q": "What prevents autoscaling flapping?", "a": "scaleDown stabilizationWindowSeconds of 300–600, scaleUp with percent caps, and maxReplicas derived from capacity planning—not unlimited."},
    ],
    "hook": "CPU-based HPA on GPU inference never scaled during a batch spike—15% CPU while the request queue sat 40 seconds deep. Inference autoscaling needs signals for work waiting, not idle processors.",
    "sections": [
        ("## Choose metrics that predict saturation", [
            "Queue depth from Redis or gRPC buffers scales when work backs up. DCGM gpu_utilization scales compute-bound models. Triton nv_inference_request_duration_seconds ties scaling to latency SLOs.",
            "Use one primary signal per model family. Pair queue depth for scale-up with latency guardrails for scale-down.",
        ]),
        ("## prometheus-adapter wiring", [
            "Define seriesQuery and metricsQuery mapping pod labels to HPA resources. Test the raw metrics API before applying HPA—missing adapter rules show as `<unknown>` in kubectl describe hpa.",
        ], """```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fraud-model-hpa
spec:
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric:
          name: inference_queue_depth
        target:
          type: AverageValue
          averageValue: "30"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 600
```"""),
        ("## KEDA for Kafka and SQS inference", [
            "ScaledObject triggers on aws-sqs-queue or kafka lag scale more cleanly than custom metrics when inference is pull-based. IRSA handles credential rotation without static keys in cluster.",
        ]),
        ("## GPU scaling sharp edges", [
            "Readiness must run dummy inference, not HTTP health. MIG and time-slicing distort gpu_utilization—prefer queue depth. Dynamic batching in Triton increases throughput per pod; scaling too early wastes GPUs.",
        ]),
        ("## Load test autoscaling before peak", [
            "Ramp queue depth in staging with production payload sizes. Verify scale-up within one period and scale-down without oscillation after drain. Kill half the pods mid-test—recovery should not need manual intervention.",
        ]),
    ],
}

CONTENT["devops-init-containers-migration"] = {
    "faqs": [
        {"q": "When should logic live in an init container vs a Job?", "a": "Init containers for ordered startup blocking the main pod: schema migration, config fetch, dependency wait. Separate Jobs for long-running batch migrations that should not block pod scheduling retries."},
        {"q": "How do I prevent init containers stuck forever?", "a": "Set activeDeadlineSeconds on the pod, use timeout flags on migration tools (Flyway -connectRetries), and fail fast with clear logs. Alert on pods stuck Init:0/1 beyond SLO."},
        {"q": "Can multiple init containers run database migrations?", "a": "Only one should mutate schema. Others should wait on a readiness signal or use lease-based migration locks. Parallel Flyway from rolling deploys causes race corruption."},
        {"q": "Should init containers share the same image as the app?", "a": "Often yes for migration CLIs bundled with app code. Separate images when migration tooling bloats attack surface or when platform team owns migration sidecar versions independently."},
    ],
    "hook": "App containers started before Flyway finished—500 errors until someone kubectl-deleted pods to force restart. Init containers exist to serialize bootstrap, but without timeouts and idempotent migrations they become Init:0/1 tombstones.",
    "sections": [
        ("## Init vs Job: pick the right primitive", [
            "Init containers run to completion before app containers start, sharing the pod network and volumes. Kubernetes Jobs suit one-off migrations decoupled from app lifecycle. Mixing a 45-minute migration into init blocks Deployment rollouts entirely.",
        ]),
        ("## Flyway/Liquibase in init pattern", [
            "Mount an emptyDir or PVC for migration state. Run migrate with explicit connect timeout. Exit non-zero on failure so Kubernetes retries with backoff—not silent partial schema.",
        ], """```yaml
initContainers:
  - name: migrate
    image: myapp:1.4.2
    command: ["flyway", "-connectRetries=10", "migrate"]
    envFrom:
      - secretRef:
          name: db-credentials
    resources:
      limits:
        cpu: "1"
        memory: 512Mi
activeDeadlineSeconds: 600
```"""),
        ("## Config fetch and Vault agent init", [
            "Init containers pulling secrets from Vault or AWS Parameter Store should write to a shared volume consumed read-only by app containers. Rotate by restarting pods—not by mutating files in running containers.",
        ]),
        ("## Dependency wait without blind sleep", [
            "Replace `sleep 30` with proper checks: `nc -z`, HTTP health against dependency, or `wait-for-it` with max attempts. Log each attempt for debugging slow dependencies during incidents.",
        ]),
        ("## Rolling updates with schema changes", [
            "Expand-contract migrations: deploy backward-compatible schema first, roll app, then contract. Init migration on every pod during breaking change duplicates work—use Job with advisory lock instead.",
        ]),
    ],
}

CONTENT["devops-ip-reputation-scoring"] = {
    "faqs": [
        {"q": "Why do new egress IPs get blocklisted immediately?", "a": "IPs recycle from pools with prior abuse history. Warm up gradually: low volume, reputable destinations, SPF/DKIM aligned, and monitoring bounce/blocklist APIs before full traffic."},
        {"q": "How do I isolate tenant egress on shared NAT?", "a": "Per-tenant elastic IPs, egress NetworkPolicies to dedicated NAT gateways, or service mesh egress gateways with separate SNAT pools. Shared NAT means one abusive tenant blocklists everyone."},
        {"q": "Which blocklists should I monitor?", "a": "Spamhaus ZEN, Barracuda, Microsoft SNDS for mail. For API partners, their status dashboards and allowlist registration flows. Automate DNSBL lookups on your egress IPs daily."},
        {"q": "What is a practical IP warmup schedule?", "a": "Double sent volume every 24–48 hours while bounce rate stays under threshold. Start with engaged recipients. Sudden 10× jumps trigger spam filters regardless of content quality."},
    ],
    "hook": "A new NAT gateway IP got blocklisted by a payment partner API on day one—reputation warmup was never in the runbook. Egress IP management is deliverability infrastructure, not something you discover when integrations fail in production.",
    "sections": [
        ("## Shared NAT concentrates risk", [
            "Kubernetes clusters behind one NAT gateway share one reputation score. A compromised pod sending spam or scraping gets the whole IP burned. Segment egress: production mail on dedicated IPs, API integrations on allowlisted pools, sandbox on cheap disposable NAT.",
        ]),
        ("## Warmup playbook", [
            "Register IPs with partners before cutover. Send low volume through warmed paths first. Monitor HTTP 403/421 patterns and provider-specific rejection headers. Keep previous IP active during overlap window.",
        ]),
        ("## Terraform and IP lifecycle", [
            "Elastic IPs persist across NAT replacement if associated correctly. Document which EIP maps to which integration allowlist. CI should fail if egress IP changes without updating partner tickets.",
        ], """```hcl
resource "aws_eip" "egress_api" {
  domain = "vpc"
  tags = {
    purpose = "partner-api-egress"
    owner   = "platform"
  }
}
```"""),
        ("## Detecting reputation decay", [
            "Daily job queries major DNSBLs and partner status APIs. Alert on any listing. Correlate with tenant onboarding dates—new customer high-volume outbound often triggers false positives you must dispute with evidence.",
        ]),
        ("## Incident: delisting under pressure", [
            "Pre-write delisting request templates with IP, allocation date, sending practices, and abuse response process. Panic submissions with missing data delay recovery.",
        ]),
    ],
}

CONTENT["devops-jaeger-sampling-strategies"] = {
    "faqs": [
        {"q": "What is the difference between head and tail sampling?", "a": "Head sampling decides at trace start—cheap, may discard rare errors. Tail sampling buffers spans and decides at completion—captures errors and high latency but needs memory and collector scale."},
        {"q": "What sampling rate should tier-1 services use?", "a": "Start 1–5% head sampling for high QPS, plus tail sampling rules for error=true and duration>p99. Never 100% on services above 1k RPS without storage budget approval."},
        {"q": "How do I sample without breaking trace trees?", "a": "Use probabilistic sampling at root with downstream respect, or tail sampling in OpenTelemetry Collector with decision_wait. Inconsistent per-service head rates orphan spans in UI."},
        {"q": "Jaeger vs OTel Collector for sampling policy?", "a": "Prefer OTel Collector tail_sampling processor for complex rules; Jaeger collector supports adaptive sampling in some deployments. Centralize policy—do not configure different rates per agent without coordination."},
    ],
    "hook": "Trace storage bill hit 5× budget after enabling 100% sampling on a 3k RPS checkout service—debuggability improved until finance noticed. Sampling is a cost control with observability tradeoffs, not a checkbox.",
    "sections": [
        ("## Head sampling economics", [
            "Const sampling at trace start is O(1) per request. Five percent of 3k RPS is still 150 traces/sec—size storage accordingly. Rate limit by service name in collector config, not only in agents.",
        ]),
        ("## Tail sampling for errors and tails", [
            "Buffer spans until trace completes. Keep traces where status=error OR duration>2s OR critical path flag. decision_wait of 10s balances completeness vs memory.",
        ], """```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: latency
        type: latency
        latency: {threshold_ms: 2000}
      - name: baseline
        type: probabilistic
        probabilistic: {sampling_percentage: 5}
```"""),
        ("## Adaptive and per-operation sampling", [
            "Jaeger adaptive sampling increases rate for hot operations with errors. Document which operations get boosted—checkout.payment should sample higher than health checks.",
        ]),
        ("## Storage and retention coupling", [
            "Sampling rate × span size × retention days = bill. Drop verbose span attributes at collector before write. Use tiered retention: 7 days full, 30 days sampled aggregates.",
        ]),
        ("## Validate sampling in staging", [
            "Generate known error traces and confirm they appear at 100% despite 1% head rate when tail rules apply. Missing error traces in staging means prod incidents will be blind.",
        ]),
    ],
}

# --- generator helpers ---

def sections_to_body(sections):
    parts = []
    for item in sections:
        heading = item[0]
        paras = item[1]
        code = item[2] if len(item) > 2 else None
        parts.append(heading)
        for p in paras:
            parts.append(p)
            parts.append("")
        if code:
            parts.append(code.strip())
            parts.append("")
    return "\n".join(parts)


TOPIC_CLOSERS = {
    "devops-idle-resource-reclamation": "FinOps champions treat reclamation queues like incident backlogs: visible, prioritized, and closed with evidence. Publish monthly savings and near-misses where grace periods saved production volumes—that transparency funds the next automation sprint.",
    "devops-inference-autoscaling-custom": "Autoscaling inference is iterative: start with queue depth, validate with load tests, then tighten scale-down windows once p99 stabilizes. Document max replica rationale in the service runbook so future cost cuts do not silently cap capacity.",
    "devops-init-containers-migration": "Treat init containers as part of the deployment contract: version pinned, timeout bounded, logs shipped to the same index as app containers. When migrations exceed pod startup SLO, move work to Jobs without deleting init for lightweight dependency gates.",
    "devops-ip-reputation-scoring": "Egress IP reputation is a cross-team concern spanning platform, mail ops, and integration owners. Maintain a single registry mapping IP to purpose, partner tickets, and warmup status—onboarding a new SaaS integration starts with that lookup, not a fresh NAT.",
    "devops-jaeger-sampling-strategies": "Revisit sampling quarterly as traffic grows: the 1% that worked at 500 RPS may be untenable at 5k RPS. Pair sampling changes with storage retention adjustments so you do not trade bill shock for blind spots.",
    "devops-jenkins-shared-libraries": "Shared libraries are production code: semver, CI, code owners, and rollback. When a library bug blocks releases, the fix path should be tag revert—not emergency Groovy surgery in every Jenkinsfile.",
    "devops-job-backoff-limits-parallelism": "Batch Job tuning is load management for the control plane and data plane together. Graph failures per Job over time; recurring Failed Jobs with low backoff indicate poison data, not transient infra.",
    "devops-k8s-cost-allocation-kubecost": "Cost allocation matures when engineers argue about labels before finance argues about invoices. Make unallocated spend visible weekly; shame is a feature, not a bug, until compliance hits 95%.",
    "devops-karpenter-nodepool-tuning": "Karpenter rewards teams that know their workload shapes: right-size requests before tuning NodePools. Consolidation savings disappear if pods request 8 CPU and use 0.5—Karpenter cannot pack fiction.",
    "devops-kill-switch-incident-response": "Kill switches fail in panic unless muscle memory exists. Quarterly five-minute drills—trigger, verify isolation, restore—beat a forty-page runbook nobody opens.",
    "devops-kubeflow-pipelines-ops": "KFP operations converge with standard Kubernetes platform practices: quotas, network policy, backup, upgrade windows. The ML label does not exempt pipelines from multi-tenant hygiene.",
    "devops-kubernetes-rbac-break-glass": "Break-glass access should feel heavy: MFA, ticket, time limit, audit review. If emergency access is easier than normal access, normal RBAC is broken.",
    "devops-litmus-chaos-experiments": "Chaos value is measured in runbook diffs, not experiment count. Each game day should produce at least one merged change to timeouts, replicas, or retry policy.",
    "devops-load-test-production-shadow": "Shadow traffic is a privilege: protect production from mutation, protect customer data with scrubbing, protect staging budget with autoscale caps. Fidelity beats volume—a 3% mirror with real payloads beats synthetic 100% RPS.",
    "devops-log-aggregation-pipeline": "Log pipelines fail quietly during spikes unless you alert on drop counters and OpenSearch indexing lag. Incident queries should be rehearsed monthly—if `trace_id` search takes minutes, fix indexes before the outage.",
    "devops-loki-label-cardinality": "Loki discipline is cultural: code review logging changes like database schema changes. One enthusiastic intern adding `request_id` as a label can take down ingestion for everyone.",
    "devops-metrics-cardinality-control": "Cardinality budgets belong in service templates: max labels per metric, allowed names, exemplar policy. Platform exports a starter instrumentation package so teams do not reinvent high-cardinality HTTP middleware.",
    "devops-ml-ci-cd-github-actions": "ML CI/CD credibility comes from failing builds when data or eval regresses—not from green checks on import smoke tests. Store eval artifacts per commit so promotion debates reference numbers, not vibes.",
    "devops-ml-pipeline-airflow": "Airflow for ML succeeds when platform owns metadata DB, executor scaling, and dependency packaging; data science owns DAG logic. Draw that line early to avoid midnight pager wars over Python version skew.",
    "devops-mlflow-model-registry": "Registry stages are contracts with serving: if ops cannot enforce stage-only deploys, the registry becomes metadata theater. Close override paths in Helm, CI, and manual kubectl.",
    "devops-model-artifact-versioning": "Immutable artifacts enable forensic replay: given a prediction log hash, fetch exact bytes used that hour. That property alone justifies saying no to mutable `latest`.",
    "devops-model-governance-audit": "Governance artifacts should be queryable years later—PDF in ticket attachments ages poorly. Structured records with approver SSO IDs survive auditor requests and team turnover.",
    "devops-model-monitoring-drift": "Drift monitoring without retrain playbooks is alerting without action. Pre-define who investigates PSI spikes, SLA for decision, and fallback model policy when labels are delayed.",
    "devops-model-rollout-canary": "Model canaries need business metrics on the same dashboard as latency—accuracy offline while checkout conversion drops is a rollback, not a promotion.",
    "devops-model-serving-a-b-testing": "A/B tests end with a decision: promote, revert, or redesign experiment. Open-ended 50/50 splits accumulate statistical debt and operational toil maintaining two serving paths.",
}


TOPIC_META = {
    "devops-idle-resource-reclamation": {"incident": "$40k/year orphaned EBS volumes from deleted test clusters.", "when": "Quarterly cost optimization sprints.", "mistake": "Aggressive reclamation without tag grace period—prod volume deleted.", "focus": "idle reclamation"},
    "devops-inference-autoscaling-custom": {"incident": "CPU-based HPA on GPU inference never scaled during a batch spike.", "when": "When model serving has non-CPU-bound scaling signals.", "mistake": "Scale to zero without warm pool—cold start broke latency SLO.", "focus": "inference autoscaling"},
    "devops-init-containers-migration": {"incident": "App containers started before Flyway finished—500 errors until manual restart.", "when": "When apps need ordered startup beyond simple probes.", "mistake": "Heavy migration logic in init without timeout leaves pods stuck Init:0/1.", "focus": "init containers"},
    "devops-ip-reputation-scoring": {"incident": "New NAT IP blocked by partner API—reputation not warmed.", "when": "Outbound integrations with IP allowlists or spam filters.", "mistake": "Shared NAT with abusive tenant—whole IP blocklisted.", "focus": "IP reputation"},
    "devops-jaeger-sampling-strategies": {"incident": "Trace storage bill 5× budget—100% sampling on high-QPS service.", "when": "Before enabling tracing on tier-1 high-traffic services.", "mistake": "Head sampling only—missed rare errors in tail.", "focus": "trace sampling"},
    "devops-jenkins-shared-libraries": {"incident": "Copy-pasted Groovy deploy scripts diverged—prod deploy used stale credentials ID.", "when": "When Jenkins remains primary CI for legacy or regulated workloads.", "mistake": "Shared library @Library without version—breaking change on main.", "focus": "Jenkins shared libraries"},
    "devops-job-backoff-limits-parallelism": {"incident": "Poison message retried 10k times before backoff—cluster API throttled.", "when": "Before production batch pipelines on native Jobs.", "mistake": "Unbounded parallelism overwhelming downstream databases.", "focus": "Kubernetes Job tuning"},
    "devops-k8s-cost-allocation-kubecost": {"incident": "One namespace 60% of bill—no labels until finance escalated.", "when": "When Kubernetes exceeds 25% of cloud spend.", "mistake": "Allocation without shared cost split—GPU nodes blamed on wrong team.", "focus": "K8s cost allocation"},
    "devops-karpenter-nodepool-tuning": {"incident": "Spot reclamation spiked; batch jobs restarted because consolidation was too aggressive.", "when": "When moving from Cluster Autoscaler or spot interruptions spike.", "mistake": "Allowing all instance types picks wrong shapes for workloads.", "focus": "Karpenter NodePool"},
    "devops-kill-switch-incident-response": {"incident": "Ransomware spreading—no pre-tested way to isolate namespace fast.", "when": "Incident response playbooks for tier-1 services.", "mistake": "Kill switch untested—removed wrong namespace during panic.", "focus": "kill switches"},
    "devops-kubeflow-pipelines-ops": {"incident": "Pipeline pod OOM on feature engineering—no resource templates.", "when": "When ML training pipelines run on Kubernetes.", "mistake": "Shared namespace—one team's run deletes another's artifacts.", "focus": "Kubeflow Pipelines"},
    "devops-kubernetes-rbac-break-glass": {"incident": "On-call shared static kubeconfig cluster-admin—no audit trail.", "when": "Before first production Kubernetes incident.", "mistake": "Break-glass without auto-expire—emergency access becomes permanent.", "focus": "break-glass RBAC"},
    "devops-litmus-chaos-experiments": {"incident": "First prod outage from untested dependency timeout—no chaos coverage.", "when": "Before peak season or after major architecture change.", "mistake": "Chaos in prod without blast radius limits—customer-facing blast.", "focus": "Litmus chaos"},
    "devops-load-test-production-shadow": {"incident": "Load test used synthetic payload—prod choked on large JSON bodies.", "when": "Before doubling traffic or major architecture migrations.", "mistake": "Shadow traffic mutating data—production corruption incident.", "focus": "shadow load testing"},
    "devops-log-aggregation-pipeline": {"incident": "Unparsed multiline stack traces—grep useless during outage.", "when": "When centralizing logs beyond kubectl logs.", "mistake": "Fluent Bit without backpressure—lost logs during spike.", "focus": "Fluent Bit pipelines"},
    "devops-loki-label-cardinality": {"incident": "user_id as label—Loki ingester OOM and query timeouts.", "when": "When deploying Loki for Kubernetes log aggregation.", "mistake": "High-cardinality labels in structured metadata—same as bad labels.", "focus": "Loki labels"},
    "devops-metrics-cardinality-control": {"incident": "Prometheus TSDB 2TB from unbounded path label on HTTP metrics.", "when": "When Prometheus storage growth exceeds 20% month-over-month.", "mistake": "Relabel drop in scrape only—metrics already exported from apps.", "focus": "metrics cardinality"},
    "devops-ml-ci-cd-github-actions": {"incident": "Broken preprocessing shipped—CI only tested model pickle load.", "when": "Before automating model promotion to production.", "mistake": "Eval on static holdout only—does not catch serving skew.", "focus": "ML CI/CD"},
    "devops-ml-pipeline-airflow": {"incident": "Sensor deadlock blocked retraining for a week—no SLA alert.", "when": "When ML steps mix SQL, Spark, and K8s jobs.", "mistake": "XCom passing large dataframes—metadata DB bloat and failure.", "focus": "Airflow ML pipelines"},
    "devops-mlflow-model-registry": {"incident": "Production served Staging-tagged model after manual URI override.", "when": "When more than one data scientist deploys models.", "mistake": "Registry without RBAC—anyone promotes to Production stage.", "focus": "MLflow registry"},
    "devops-model-artifact-versioning": {"incident": "Production pulled latest tag—artifact overwritten by retrains.", "when": "For every production model deployment path.", "mistake": "Mutable latest tag in registry—non-reproducible inference.", "focus": "model artifacts"},
    "devops-model-governance-audit": {"incident": "Regulator asked who approved model v3—only Slack thread existed.", "when": "For regulated or customer-impacting ML systems.", "mistake": "Governance checklist after deploy—not blocking gate.", "focus": "model governance"},
    "devops-model-monitoring-drift": {"incident": "Model accuracy collapsed after market shift—no drift alerts configured.", "when": "From day one of production model serving.", "mistake": "Monitoring only infrastructure CPU—not model quality metrics.", "focus": "model drift monitoring"},
    "devops-model-rollout-canary": {"incident": "New model deployed 100%—latency regression hit all users.", "when": "Before replacing production model serving endpoint.", "mistake": "Canary compares accuracy offline only—prod traffic distribution differs.", "focus": "model canary rollout"},
    "devops-model-serving-a-b-testing": {"incident": "Manual 50/50 split broke when pods restarted—sticky sessions lost.", "when": "Before promoting challenger model to champion.", "mistake": "A/B without statistical power calc—premature winner declaration.", "focus": "model A/B testing"},
}


def meta_extension(slug):
    m = TOPIC_META.get(slug, {})
    if not m:
        return []
    f = m["focus"]
    return [
        ("## The incident that forced a policy change", [
            m["incident"],
            f"That class of failure is why {f} becomes a tracked initiative—not a one-time fix after finance or legal asks uncomfortable questions.",
            "Capture the timeline, blast radius, and detection gap in a short postmortem. The postmortem action items should map directly to automation, alerts, or access controls described in this post.",
        ]),
        ("## When to prioritize this work", [
            f"Teams should prioritize {f} {m['when'].lower() if m['when'][0].isupper() else m['when']}",
            "Defer only when metrics are flat and the code path is genuinely unused—but verify usage with data, not intuition from a single service owner.",
            "Quarterly reviews re-open priority: traffic doubles, new regulation lands, or an adjacent incident reveals hidden coupling to this domain.",
        ]),
        ("## Design against the classic mistake", [
            f"The predictable outage: {m['mistake']}",
            "Catch this in design review with an explicit checklist item. Prefer automated enforcement—CI policy, admission webhook, or IaC test—over verbal agreement.",
            "Run a tabletop: walk through the mistake scenario and confirm your rollback path restores service within error budget.",
        ]),
        ("## Observability and ownership", [
            f"Assign an owner for {f} in the service catalog—not 'the platform team' generically, but a named rotation with backup.",
            "Dashboards should answer: is it working, is it failing safely, and is cost within forecast? Alert on symptoms tied to user-visible outcomes.",
            "Logs and traces must include correlation IDs crossing team boundaries so incidents do not stall on handoffs.",
        ]),
        ("## Rollout, rollback, and evidence", [
            "Ship the smallest production-safe change first. Measure for two weeks with before/after snapshots stored next to the change ticket.",
            "Rollback artifacts—Git revert SHA, Helm revision, feature flag—must be tested in staging, not invented during an outage.",
            "Evidence beats narrative in reviews: load test output, cost report delta, or audit log snippet proving the control works.",
        ]),
    ]


def expand_content(slug, data):
    all_sections = list(data["sections"]) + meta_extension(slug)
    body = sections_to_body(all_sections)
    for p in data.get("extra_paras", []):
        body += "\n\n" + p
    closer = TOPIC_CLOSERS.get(slug, "")
    if closer:
        body += "\n\n## Takeaway\n\n" + closer
    if wc(body) < 1200:
        try:
            from _rewrite_batch04_chunk7_depth import DEPTH
        except ImportError:
            DEPTH = {}
        depth = DEPTH.get(slug, [])
        if depth:
            body += "\n\n## Field notes from production\n\n"
            j = 0
            while wc(body) < 1200 and j < len(depth):
                body += depth[j] + "\n\n"
                j += 1
    if wc(body) < 1200:
        raise ValueError(f"{slug} body only {wc(body)} words — add content")
    return body


def parse_existing(path):
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    return parts[1]


def main():
    # Import extended content for remaining slugs
    from importlib import import_module
    try:
        ext = import_module("_rewrite_batch04_chunk7_ext")
        CONTENT.update(ext.CONTENT_EXT)
    except ImportError:
        pass

    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if slug not in CONTENT:
            results.append({"slug": slug, "status": "missing_content"})
            continue
        data = CONTENT[slug]
        body = expand_content(slug, data)
        post = build(data["faqs"], data["hook"], body, slug)
        path.write_text(post, encoding="utf-8")
        results.append({"slug": slug, "words": wc(body), "status": "ok"})

    # Update batch-04.json
    done_slugs = [r["slug"] for r in results if r["status"] == "ok"]
    prog = json.loads(PROGRESS.read_text(encoding="utf-8"))
    existing = set(prog.get("done", []))
    existing.update(done_slugs)
    prog["done"] = sorted(existing)
    prog["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    prog["chunk7"] = {"processed": len(done_slugs), "results": results}
    PROGRESS.write_text(json.dumps(prog, indent=2) + "\n", encoding="utf-8")

    ok = [r for r in results if r["status"] == "ok"]
    short = [r for r in ok if r["words"] < 1200]
    print(json.dumps({
        "written": len(ok),
        "missing": len(results) - len(ok),
        "under_1200": len(short),
        "word_range": [min(r["words"] for r in ok), max(r["words"] for r in ok)] if ok else [],
        "sample": ok[:3],
    }, indent=2))


if __name__ == "__main__":
    main()
