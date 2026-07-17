"""Extended content for batch-04 chunk 7 rewrite (slugs 6-25)."""

CONTENT_EXT = {}

CONTENT_EXT["devops-jenkins-shared-libraries"] = {
    "faqs": [
        {"q": "How should shared libraries be versioned?", "a": "Pin @Library('my-lib@1.2.3') or branch for dev only. Never float @main in production pipelines—breaking library changes become silent prod failures."},
        {"q": "What belongs in a shared library vs Jenkinsfile?", "a": "Libraries hold reusable steps: deploy, notify, credential wrappers, policy checks. Jenkinsfile keeps repo-specific stages and parameters. Business logic in Groovy libraries is hard to unit test—keep thin."},
        {"q": "How do I test shared library changes?", "a": "Use Jenkins Pipeline Unit tests, `@Library` with feature branch in test Jenkins, and replay builds. Require library PR reviews separate from consumer repos."},
        {"q": "How prevent credential sprawl in libraries?", "a": "Centralize withCredentials blocks in library functions. Never pass secret strings as parameters logged by default. Audit library method signatures for credential IDs only."},
    ],
    "hook": "Copy-pasted Groovy deploy scripts diverged until prod used a stale credentialsId string—Jenkins shared libraries exist to centralize pipeline logic, but unversioned @Library annotations turn libraries into undeployed production code.",
    "sections": [
        ("## The fork explosion problem", ["Every repo copying deploy Groovy grows drift. One team updates kubectl auth; another does not. Shared libraries version pipeline behavior like application code.", "Governance: platform owns library repo, product teams consume semver tags. Breaking changes require migration guide and deprecation window."]),
        ("## Library structure that scales", ["vars/ for global steps callable as `deployK8s()`. src/ for Groovy classes with unit tests. resources/ for templates. Keep vars thin—delegate to tested classes.",], """```groovy
// vars/deployK8s.groovy
def call(Map cfg) {
  def d = new com.acme.Deployer(this)
  d.run(cfg)
}
```"""),
        ("## Version pinning in Jenkinsfiles", ["Production: `@Library('platform-lib@2.14.0') _`. Staging may track `@2.14` patch line. Document upgrade cadence aligned with Jenkins LTS.",]),
        ("## Testing before merge", ["Pipeline Unit mocks steps. Integration job on test controller imports branch library and runs golden pipelines. Block merge without green library CI.",]),
        ("## Secrets and audit", ["Wrap withCredentials in library—callers pass credentialId name only. Log stage names, never env values. Library changes affecting prod deploy path need two-person review.",]),
    ],
}

CONTENT_EXT["devops-job-backoff-limits-parallelism"] = {
    "faqs": [
        {"q": "What does backoffLimit control?", "a": "Maximum pod failures before Job marks Failed. Default 6. Poison messages retrying forever throttle the API—set explicit limits and dead-letter handling."},
        {"q": "How tune parallelism vs completions?", "a": "parallelism caps concurrent pods; completions is total successful finishes. For 1000 items with DB limit 10 connections, parallelism=10 not 100."},
        {"q": "When use indexed vs work queue completion mode?", "a": "Indexed for static shard count. Work queue pattern with external queue when job count unknown—native Job less ideal; consider Argo Workflows."},
        {"q": "How handle Job failures in CI pipelines?", "a": "Set ttlSecondsAfterFinished to clean pods. Alert on Job Failed condition. Expose failure reason in logs with item identifier for poison detection."},
    ],
    "hook": "A poison Kafka message retried ten thousand times before backoff exhausted—cluster API throttled and unrelated Deployments stalled. Kubernetes Job backoff and parallelism are load shedders for batch systems, not defaults to accept.",
    "sections": [
        ("## backoffLimit is your circuit breaker", ["Each pod failure increments backoff counter. Without limit, misconfigured command loops forever. Set backoffLimit aligned with retry policy—often 3–6 for idempotent work, 0 for fail-fast validation jobs.",]),
        ("## Parallelism and downstream protection", ["parallelism=50 hammering Postgres max_connections=100 kills the database. Size from downstream concurrency budget divided by connections per worker.",], """```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: score-batch
spec:
  backoffLimit: 4
  parallelism: 8
  completions: 800
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: worker
          image: scorer:1.0
```"""),
        ("## activeDeadlineSeconds for hung work", ["Jobs without deadline leave pods stuck on external call. Set deadline above p99 runtime × retries. Failed deadline marks Job Failed—alert and inspect.",]),
        ("## Poison message handling", ["Log failing item ID on stderr. After backoff exhausted, route item to DLQ via sidecar or post-job hook. Never infinite retry on same payload.",]),
        ("## Indexed Jobs for deterministic sharding", ["completionMode: Indexed assigns completion index per pod—useful for parallel file processing with known partition count.",]),
    ],
}

CONTENT_EXT["devops-k8s-cost-allocation-kubecost"] = {
    "faqs": [
        {"q": "Kubecost vs OpenCost—which should I run?", "a": "OpenCost is open-core metrics exporter; Kubecost adds UI, recommendations, and enterprise allocation. Many teams start OpenCost + Grafana, add Kubecost when finance needs showback dashboards."},
        {"q": "How allocate shared cluster overhead?", "a": "Split idle node cost by CPU-request share or uniform per namespace. Document method—GPU nodes should not land entirely on whoever triggered scale-up unless fair."},
        {"q": "Which labels are required for allocation?", "a": "team, cost-center, environment at minimum on namespaces and optionally pods via admission webhook. Missing labels bucket to 'unallocated' visible in monthly report."},
        {"q": "How reconcile Kubecost to cloud bill?", "a": "Compare monthly Kubecost cluster total to CUR Kubernetes-attributed spend within 5–10%. Investigate gaps from RDS, ELB, or unlabeled resources outside cluster agent scope."},
    ],
    "hook": "One namespace consumed 60% of cluster spend but had no labels until finance escalated—Kubecost allocation only works when labels, shared cost rules, and reconciliation to CUR are designed together.",
    "sections": [
        ("## Showback vs chargeback politics", ["Showback reports cost by team without invoice. Chargeback moves budget. Start showback with engineering-friendly dashboards before finance automates invoices.",]),
        ("## Label enforcement at admission", ["Kyverno or OPA require labels on Namespace create. Mutate pods missing team label from namespace metadata. Unallocated bucket shames teams into compliance faster than email.",]),
        ("## GPU and shared infrastructure", ["GPU nodes cost 8× CPU—attribute by pod requesting nvidia.com/gpu. Ingress controllers and monitoring stack: split by request share or fixed platform overhead percentage.",]),
        ("## Kubecost allocation config", ["Define allocation aggregations: namespace, label:team, controller. Export CSV monthly for FinOps. Set savings insights thresholds to avoid alert fatigue.",], """```yaml
kubecostProductConfigs:
  labelMappingConfigs:
    team: team
    environment: env
```"""),
        ("## Reconciliation ritual", ["Monthly: Kubecost total vs AWS Cost Explorer EKS line items. Document delta sources—EBS not in agent, cross-AZ traffic, control plane fee.",]),
    ],
}

CONTENT_EXT["devops-karpenter-nodepool-tuning"] = {
    "faqs": [
        {"q": "How does Karpenter differ from Cluster Autoscaler?", "a": "Karpenter provisions nodes directly from NodePool specs without managed node groups—faster scale, richer instance selection, consolidation for downscale."},
        {"q": "What is consolidation and when disable it?", "a": "Karpenter removes underutilized nodes by rescheduling pods. Aggressive consolidation disrupts batch jobs—use budgets, disruption budgets, or separate NodePools for batch vs latency tiers."},
        {"q": "How restrict instance types?", "a": "requirements with In operator on instance-type, instance-category, capacity-type. Too broad picks wrong shape; too narrow causes pending pods during stockouts."},
        {"q": "Spot interruption handling?", "a": "Mix on-demand base capacity with spot burst. PodDisruptionBudgets and multiple replicas. Karpenter drift handles replacement—apps must tolerate eviction."},
    ],
    "hook": "Spot reclamation spiked and batch jobs restarted repeatedly because consolidation was too aggressive—Karpenter NodePool tuning balances cost, speed, and workload disruption tolerance.",
    "sections": [
        ("## NodePool as policy object", ["Each pool expresses instance families, arch, capacity-type, limits, and taints. Split pools: latency-sensitive on-demand, batch on spot, GPU dedicated.",]),
        ("## Consolidation budgets", ["consolidationPolicy: WhenUnderutilized with consolidateAfter delay lets jobs finish. Batch pool: WhenEmpty or longer After to prevent thrashing.",], """```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general
spec:
  disruption:
    consolidationPolicy: WhenUnderutilized
    consolidateAfter: 5m
  limits:
    cpu: "1000"
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand", "spot"]
```"""),
        ("## Instance selection tradeoffs", ["Allow c,m,r families with generation ≥5. Exclude metal unless needed. ARM Graviton saves cost—verify image multi-arch.",]),
        ("## Limits prevent invoice shock", ["cpu and memory limits on NodePool cap maximum fleet size. Alert at 80% limit during scale events.",]),
        ("## Observability", ["Track karpenter_nodes_created, pending pods duration, interruption rate. Correlate spot spikes with job restart metrics.",]),
    ],
}

CONTENT_EXT["devops-kill-switch-incident-response"] = {
    "faqs": [
        {"q": "What should a kill switch do?", "a": "Stop ingress traffic, revoke OAuth tokens, scale Deployments to zero, or disable feature flags—pre-tested actions runnable in under 60 seconds with audit log."},
        {"q": "How avoid killing the wrong namespace?", "a": "Runbooks with explicit cluster/context/namespace triple confirmation. Automation via labeled buttons in incident tool, not copy-paste kubectl from wiki."},
        {"q": "Should kill switches live in GitOps?", "a": "Pre-defined manifests or Argo CD Applications suspended sync for emergency scale-to-zero. Practice revert path—GitOps restore after containment."},
        {"q": "How often test kill switches?", "a": "Quarterly game day in staging with production-identical RBAC. Measure time-to-isolate. Untested switches fail during panic."},
    ],
    "hook": "Ransomware spread and nobody had a pre-tested way to isolate the namespace fast—the kill switch runbook was a wiki page with wrong kubectl context. Infrastructure kill switches are compiled procedures, not improvisation.",
    "sections": [
        ("## Layers of containment", ["Ingress deny at load balancer, NetworkPolicy default deny, scale workload to zero, revoke IAM/OIDC tokens, disable SaaS API keys—in order from fastest blast reduction to thorough.",]),
        ("## Pre-built automation", ["Lambda or GitHub workflow `incident-isolate` parameterized by service ID. Writes audit entry to SIEM. Requires break-glass role with MFA.",], """```yaml
# emergency-scale-zero.yaml — pre-applied via kubectl apply -f
apiVersion: apps/v1
kind: Deployment
metadata:
  name: compromised-api
spec:
  replicas: 0
```"""),
        ("## Feature flag kill path", ["LaunchDarkly or open-source flag off disables code path without redeploy. Pair with infra isolation for defense in depth.",]),
        ("## Communication coupling", ["Kill switch triggers status page update template and legal notification checklist. Technical containment without comms amplifies customer anger.",]),
        ("## Recovery and un-kill", ["Document order to restore: tokens, scale up, ingress, flags. Verify malware eradicated before re-enabling—otherwise switch becomes yo-yo.",]),
    ],
}

CONTENT_EXT["devops-kubeflow-pipelines-ops"] = {
    "faqs": [
        {"q": "How isolate teams in Kubeflow Pipelines?", "a": "Multi-user mode with Profiles, namespace per team, RBAC on artifacts bucket prefix. Shared namespace deletes cross-team runs."},
        {"q": "What causes pipeline pod OOM?", "a": "Feature engineering steps without resource templates—set pipeline task cpu/memory defaults and pod spec overrides per step."},
        {"q": "How use caching safely?", "a": "KFP caching keys on step signature—bump when non-code inputs change. Stale cache serves wrong model—disable cache for prod promotion pipelines."},
        {"q": "Where store artifacts?", "a": "S3/MinIO with versioning and per-namespace prefix. Lifecycle policy for intermediate artifacts; retain final models per governance retention."},
    ],
    "hook": "Pipeline pod OOM on feature engineering with no resource templates—and shared namespace let one team's cleanup job delete another's artifacts. Kubeflow Pipelines operations is multi-tenant Kubernetes with ML-specific failure modes.",
    "sections": [
        ("## Profiles and namespace isolation", ["Each team Profile creates namespace, SA, and bucket prefix. Pipeline runs scoped—no cluster-admin for data scientists.",]),
        ("## Resource templates by step type", ["Light SQL sensor: 0.5 CPU. Spark step: separate operator or high limits. Default too low OOMs; too high wastes cluster.",], """```python
@dsl.component(base_image="python:3.11")
def preprocess():
    pass

task = preprocess()
task.set_cpu_limit("4")
task.set_memory_limit("16Gi")
```"""),
        ("## Artifact store hygiene", ["Versioned S3, IAM per profile, lifecycle on `/tmp` prefixes. Monitor bucket growth—intermediate parquet accumulates silently.",]),
        ("## Metadata DB backups", ["MySQL/PostgreSQL backing KFP needs backup like any prod DB. Lost metadata means lost lineage even if artifacts exist.",]),
        ("## Upgrades and SDK compatibility", ["Pin KFP SDK in CI to cluster version. Upgrade controller in maintenance window; replay golden pipeline before reopening.",]),
    ],
}

CONTENT_EXT["devops-kubernetes-rbac-break-glass"] = {
    "faqs": [
        {"q": "What is break-glass access?", "a": "Time-bound emergency cluster-admin or namespace-admin granted via PAM or automation when normal access insufficient during incident."},
        {"q": "How auto-expire break-glass?", "a": "Temporary RoleBinding with TTL controller, or external PAM session ending removes binding. Never permanent emergency ClusterRoleBinding."},
        {"q": "What audit evidence is required?", "a": "Who requested, approver, start/end time, commands run via kubectl audit logs shipped to SIEM. Regulators ask for this after incidents."},
        {"q": "Break-glass vs shared kubeconfig?", "a": "Shared static kubeconfig is untraceable—replace with individual identity, MFA, and session recording even in crisis."},
    ],
    "hook": "On-call shared a static kubeconfig with cluster-admin—no audit trail when someone deleted the wrong CRD during an incident. Break-glass RBAC must be identity-bound, time-bound, and logged.",
    "sections": [
        ("## Normal access should suffice 95% of time", ["Tiered RBAC: developers edit namespace, SRE cluster read + targeted escalate. Break-glass only when RBAC gap blocks recovery.",]),
        ("## PAM-integrated elevation", ["Tools like Teleport, StrongDM, or cloud PAM grant 1-hour cluster-admin with ticket ID. Approval chain for prod.",], """```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: break-glass-alice-20260717
  labels:
    break-glass: "true"
    expires: "2026-07-17T18:00:00Z"
roleRef:
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: User
    name: alice@corp.com
```"""),
        ("## Automation for expiry", ["Cron or controller deletes bindings with break-glass label past expires annotation. Alert if binding older than 4 hours.",]),
        ("## Post-incident review", ["Every break-glass use gets retro: was RBAC fix needed? Could runbook avoid admin? Document in ticket.",]),
        ("## kubectl audit configuration", ["Audit policy logs RequestResponse for break-glass users. Ship to immutable store.",]),
    ],
}

CONTENT_EXT["devops-litmus-chaos-experiments"] = {
    "faqs": [
        {"q": "Litmus vs Chaos Mesh?", "a": "Both run Kubernetes chaos CRDs. Litmus emphasizes experiment hub and game day workflows; Chaos Mesh rich network IO faults. Pick one per cluster to avoid conflicting controllers."},
        {"q": "Should chaos run in production?", "a": "Yes with blast radius limits: namespace selectors, off-peak windows, abort on SLO burn. Staging-only chaos misses prod config drift."},
        {"q": "How define steady-state?", "a": "Prometheus SLI queries evaluated before/during experiment—error rate, latency, queue depth. Abort chaos when steady-state violates threshold."},
        {"q": "How integrate with CI?", "a": "Litmus in staging pipeline post-deploy runs pod-delete experiment; fail build if steady-state breaks. Not replacement for quarterly game days."},
    ],
    "hook": "First prod outage from untested dependency timeout—no chaos coverage meant retries amplified the blast. Litmus experiments validate resilience assumptions before customers do.",
    "sections": [
        ("## ChaosEngine anatomy", ["ChaosEngine selects app label, lists experiments, sets abort conditions. Run in app namespace with service account scoped to chaos verbs only.",], """```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: checkout-chaos
spec:
  appinfo:
    appns: checkout
    applabel: "app=checkout"
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"
```"""),
        ("## Blast radius containment", ["Namespace allowlist, exclude kube-system, label chaos-enabled=true required on target. NetworkChaos scoped to single Deployment.",]),
        ("## Steady-state probes", ["HTTP probe or PromQL: `rate(http_errors[1m]) < 0.01`. Litmus aborts experiment when probe fails.",]),
        ("## Game day cadence", ["Quarterly cross-team: hypothesize, run, document gaps. Update runbooks with actual failure modes found.",]),
        ("## Prod guardrails", ["Business hours blackout, automatic rollback link, executive comms template if customer impact.",]),
    ],
}

CONTENT_EXT["devops-load-test-production-shadow"] = {
    "faqs": [
        {"q": "Shadow vs replay traffic?", "a": "Shadow duplicates live requests to staging without client impact. Replay uses recorded traffic later—better for mutation-safe read paths."},
        {"q": "How prevent shadow writes mutating data?", "a": "Route shadow to read-only DB replica, synthetic tenant IDs, or middleware stripping mutation verbs. Shadow POST caused prod corruption is a classic failure."},
        {"q": "What tooling captures production shape?", "a": "GoReplay, Envoy tap, service mesh duplicate cluster, or Kafka mirror with scrubbed PII. Synthetic load misses payload size distribution."},
        {"q": "When is shadow load testing worth cost?", "a": "Before doubling traffic, major migrations, or when staging never matches prod payload complexity."},
    ],
    "hook": "Load test used synthetic JSON while production choked on 2MB payloads—shadow load testing against real paths exposes capacity lies staging tells.",
    "sections": [
        ("## Production-shaped traffic definition", ["Match method mix, payload percentiles, header sets, and auth patterns. Scrub PII at capture—GDPR applies to shadow stores too.",]),
        ("## Read-only shadow architecture", ["Duplicate request to staging cluster reading replica. Block POST/PUT/PATCH at shadow gateway or use separate shadow database reset nightly.",], """```yaml
# Istio mirror example
apiVersion: networking.istio.io/v1
kind: VirtualService
spec:
  http:
    - route:
        - destination:
            host: prod
      mirror:
        host: staging-shadow
      mirrorPercentage:
        value: 5.0
```"""),
        ("## Measuring shadow fidelity", ["Compare staging p99 under shadow to prod p99 at same RPS fraction—not equal absolute latency but proportional saturation signals.",]),
        ("## Capacity sign-off criteria", ["Staging handles 2× shadow RPS with CPU <70% and error rate flat. Document headroom for failover absorbing full prod.",]),
        ("## Teardown and cost", ["Shadow clusters auto-scale down off-peak. Mirror percentage tunable—5% often enough for statistical shape.",]),
    ],
}

CONTENT_EXT["devops-log-aggregation-pipeline"] = {
    "faqs": [
        {"q": "Fluent Bit vs Fluentd?", "a": "Fluent Bit lighter for node log collection; Fluentd heavier routing. Most K8s stacks: Fluent Bit DaemonSet → optional Fluentd aggregator → OpenSearch/Loki."},
        {"q": "How parse multiline stack traces?", "a": "multiline.parser regex matching timestamp or exception start lines. Unparsed stacks break grep during outages."},
        {"q": "What causes log loss under spike?", "a": "Missing backpressure: buffer limits, retry to disk, and output throttle. Fluent Bit mem_buf_limit and storage.path prevent drop on OpenSearch bulk reject."},
        {"q": "OpenSearch index strategy?", "a": "Daily indices by cluster/environment, ISM policy hot-warm-delete. Avoid single giant index—recovery and query both suffer."},
    ],
    "hook": "Unparsed multiline stack traces made grep useless during an outage—Fluent Bit to OpenSearch pipelines need parsers, backpressure, and index lifecycle designed for incident queries.",
    "sections": [
        ("## DaemonSet collection path", ["Fluent Bit tails /var/log/containers, adds kubernetes metadata, forwards to aggregator or directly OpenSearch.",]),
        ("## Parser pipeline", ["docker json parser → kubernetes filter → nest modifier for app fields. Multiline for Java/Python stacks.",], """```ini
[MULTILINE_PARSER]
    name          java_multiline
    type          regex
    flush_timeout 1000
    rule          "start_state" "/^(\\d{4}-|\\tat)/" "cont"
    rule          "cont" "/^(\\tat|\\s+at|\\ Caused by:)/" "cont"
```"""),
        ("## Backpressure configuration", ["storage.type filesystem when output slow. Retry_Limit false with exponential backoff. Monitor fluentbit_output_dropped_records.",]),
        ("## OpenSearch indexing", ["Index template maps @timestamp, level, trace_id. ISM: 7d hot, 30d warm, 90d delete unless compliance requires longer.",]),
        ("## Correlation fields", ["Inject trace_id in app logs—same field OpenTelemetry uses. Incident search starts at trace, expands to all pod logs.",]),
    ],
}

CONTENT_EXT["devops-loki-label-cardinality"] = {
    "faqs": [
        {"q": "Which labels should Loki allow?", "a": "Low cardinality: cluster, namespace, app, level, environment. Never user_id, request_id, or URL path as labels—use structured metadata or log line JSON."},
        {"q": "Structured metadata vs labels?", "a": "Loki 3.x structured metadata carries high-cardinality fields indexed lightly. Still avoid unbounded keys—same discipline as labels."},
        {"q": "How detect cardinality explosions?", "a": "Monitor loki_discarded_samples_total, ingester memory, query timeouts. cortex/loki limits per-user streams."},
        {"q": "Recording rules for expensive LogQL?", "a": "Pre-aggregate metric queries from logs via recording rules sparingly—prefer metrics pipeline for counters, logs for detail."},
    ],
    "hook": "user_id as a Loki label OOM'd the ingester and queries timed out—label cardinality in Loki is a hard scalability constraint, not a suggestion.",
    "sections": [
        ("## Index-free does not mean label-free", ["Loki indexes labels, not line content. Each unique label combination is a stream. Million users as label values equals million streams.",]),
        ("## Label naming standard", ["| Allowed | Forbidden as label |", "|---------|-------------------|", "| namespace, app, level | user_id, trace_id, http_path |", "Document in PR checklist for logging changes.",]),
        ("## Promtail/Alloy pipeline discipline", ["Extract dynamic fields to JSON line, not labels. relabel_configs keep only approved keys.",], """```yaml
pipeline_stages:
  - json:
      expressions:
        user_id: user_id
  - labels:
      level:
      app:
  # user_id stays in log line, NOT labels
```"""),
        ("## Query performance", ["Narrow label selectors first `{namespace=\"checkout\"}`, then filter line content `| json | user_id=\"u123\"`. Reverse order scans everything.",]),
        ("## Limits and overrides", ["ingestion_rate_mb, max_streams_per_user in limits config. Per-tenant overrides for noisy neighbors.",]),
    ],
}

CONTENT_EXT["devops-metrics-cardinality-control"] = {
    "faqs": [
        {"q": "What causes Prometheus cardinality explosions?", "a": "Unbounded labels: http route paths, user IDs, build IDs on every gauge. Each label combo is a new series."},
        {"q": "Relabel at scrape vs in app?", "a": "Fix at source when possible—stop exporting bad labels. Relabel drop in scrape_config as safety net; recording rules cannot undo exported cardinality already in TSDB."},
        {"q": "How audit cardinality?", "a": "Prometheus tsdb analyze or cortex cardinality dashboard. Top 10 metric names by series count monthly review."},
        {"q": "HTTP metrics best practice?", "a": "Label route with template /users/:id not /users/12345. Use RED metrics with bounded cardinality."},
    ],
    "hook": "Prometheus TSDB hit 2TB from an unbounded path label on HTTP metrics—cardinality control needs naming standards, relabel drops, and code review on instrumentation.",
    "sections": [
        ("## Series math", ["`http_requests_total{method,status,route}` with 10 methods, 20 statuses, 500 routes = 100k series per service. Multiply by replicas and jobs.",]),
        ("## Relabel drop example", ["Drop path label, keep route template via metric_relabel in scrape or replace in app middleware.",], """```yaml
metric_relabel_configs:
  - source_labels: [path]
    regex: "/users/\\d+"
    target_label: route
    replacement: "/users/:id"
  - action: labeldrop
    regex: path
```"""),
        ("## Governance in CI", ["Lint prometheus rules and client instrumentation in PR. Block new high-cardinality labels without platform approval.",]),
        ("## Aggregation for dashboards", ["Recording rules pre-aggregate expensive queries. histogram_quantile on high-cardinality labels kills query nodes.",]),
        ("## Alerting on growth", ["Alert when tsdb_head_series grows >20% week-over-week. Early intervention before compactor OOM.",]),
    ],
}

CONTENT_EXT["devops-ml-ci-cd-github-actions"] = {
    "faqs": [
        {"q": "What tests gate model deploy?", "a": "Unit tests on preprocessing, schema validation on input data, eval metrics vs holdout threshold, and smoke inference on sample batch—not only pickle loads."},
        {"q": "How cache model artifacts in CI?", "a": "S3 with content hash in path; GitHub cache for deps only. Never commit model binaries to git."},
        {"q": "How detect training-serving skew?", "a": "Run same preprocessing code path in CI against golden fixtures exported from prod logging sample."},
        {"q": "Environment promotion flow?", "a": "PR triggers train+eval; merge to main registers staging artifact; manual or automated promotion after staging shadow metrics pass."},
    ],
    "hook": "Broken preprocessing shipped because CI only verified the model pickle loaded—ML CI/CD must gate data validation and eval thresholds, not artifact existence.",
    "sections": [
        ("## Pipeline stages", ["lint → unit test → data validation (Great Expectations/pandera) → train → eval → register artifact → deploy staging.",]),
        ("## GitHub Actions pattern", ["Reusable workflow for train job on self-hosted GPU runner. OIDC to cloud storage without long-lived keys.",], """```yaml
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/
      - run: python eval.py --min-auc 0.82
```"""),
        ("## Eval thresholds as code", ["Fail CI if AUC drops >1% from baseline or fairness metric violates policy. Store baseline in registry tag.",]),
        ("## Deployment workflow", ["Separate workflow_dispatch promote with approver environment. Writes MLflow stage transition audit.",]),
        ("## Secrets and data", ["Training data in private bucket; CI reads subset. No prod PII in GitHub artifacts.",]),
    ],
}

CONTENT_EXT["devops-ml-pipeline-airflow"] = {
    "faqs": [
        {"q": "KubernetesPodOperator vs SparkSubmitOperator?", "a": "K8s pod for containerized ML steps with isolated deps. Spark on K8s operator for large distributed transforms—pick per step size."},
        {"q": "How avoid XCom bloat?", "a": "Pass S3 paths in XCom, not dataframes. Large XCom kills metadata DB and task queue."},
        {"q": "Sensor deadlock prevention?", "a": "Use reschedule mode, timeouts, and SLA alerts on DAG. ExternalTaskSensor chains need explicit execution_delta."},
        {"q": "Airflow vs Kubeflow for ML?", "a": "Airflow when ML mixes SQL, sensors, cron schedules with enterprise ops familiarity. Kubeflow when native pipeline DAG and experiment tracking integration primary."},
    ],
    "hook": "Sensor deadlock blocked retraining for a week with no SLA alert—Airflow ML pipelines need timeout discipline and object-store-sized XComs.",
    "sections": [
        ("## DAG design for ML", ["Separate extract, validate, train, evaluate, register, deploy tasks. validate fails fast before GPU spend.",]),
        ("## KubernetesPodOperator example", ["Pod per task with service account for S3. Resources explicit.",], """```python
train = KubernetesPodOperator(
    task_id="train",
    name="train",
    namespace="ml",
    image="trainer:2.1",
    cmds=["python", "train.py"],
    arguments=["--out", "s3://models/{{ ds }}/"],
    get_logs=True,
)
```"""),
        ("## XCom with paths only", ["`return s3://bucket/path` not dataframe.to_json(). Downstream pulls from S3.",]),
        ("## SLAs and alerting", ["sla=timedelta(hours=4) on retrain DAG. PagerDuty on sla_miss callback.",]),
        ("## Metadata DB ops", ["Postgres backup, pool size tuned for worker count. Clean old task instances per retention policy.",]),
    ],
}

CONTENT_EXT["devops-mlflow-model-registry"] = {
    "faqs": [
        {"q": "What are MLflow stages?", "a": "None, Staging, Production, Archived—transitions gated by permissions and optional manual approval webhooks."},
        {"q": "How prevent wrong model in prod?", "a": "Serving reads Production stage URI only—block manual run_id override in prod configs. CI promotes after eval pass."},
        {"q": "Registry HA?", "a": "Backend store in managed Postgres/S3; track server behind load balancer. Artifact store versioning on S3."},
        {"q": "Link models to source run?", "a": "Tags: git_sha, data_version, eval_metrics JSON. Lineage API for audit."},
    ],
    "hook": "Production served a Staging-tagged model after manual URI override—MLflow registry stages only work when serving configs cannot bypass them.",
    "sections": [
        ("## Stage transitions as gates", ["None→Staging automatic on register. Staging→Production requires approver + passing integration tests.",]),
        ("## RBAC on transitions", ["MLflow auth or proxy restricting Production transition to ml-ops role. Data scientists register; ops promotes.",], """```python
client.transition_model_version_stage(
    name="fraud-detector",
    version=7,
    stage="Production",
    archive_existing_versions=True,
)
```"""),
        ("## Serving contract", ["Helm values: model_uri `@models/fraud-detector/Production`. No `@latest`. Startup fails if stage empty.",]),
        ("## Tags for lineage", ["git_sha, training_data_snapshot, fairness_report_url on each version.",]),
        ("## Cleanup archived versions", ["Lifecycle policy deletes artifact objects for Archived >90d retaining metadata.",]),
    ],
}

CONTENT_EXT["devops-model-artifact-versioning"] = {
    "faqs": [
        {"q": "Why not use latest tag for models?", "a": "Mutable tags break reproducibility—retrain overwrites artifact under same tag. Use immutable version IDs or content hashes."},
        {"q": "Object storage immutability?", "a": "S3 Object Lock or versioning prevents accidental overwrite. WORM for regulated models."},
        {"q": "How tie artifact to code?", "a": "Manifest JSON listing model hash, preprocessing hash, requirements lockfile hash, git SHA—verified at deploy."},
        {"q": "Garbage collection?", "a": "Retain Production + last N challengers; delete orphaned hashes after TTL with registry reference check."},
    ],
    "hook": "Production pulled latest tag while a retrain overwrote the artifact—immutable versioning and content-addressed storage are baseline for reproducible inference.",
    "sections": [
        ("## Content-addressed paths", ["s3://models/fraud/v7/sha256-abc123/model.onnx not s3://models/fraud/latest/model.onnx.",]),
        ("## Manifest file", ["Each deploy references manifest listing all blobs and hashes. CI verifies before kubectl apply.",], """```json
{
  "model_version": "7",
  "artifacts": {
    "model.onnx": "sha256:abc...",
    "preprocess.pkl": "sha256:def..."
  },
  "git_sha": "a1b2c3d"
}
```"""),
        ("## Registry integration", ["MLflow logs artifact URI with version number. Serving pins version integer, not floating tag.",]),
        ("## Rollback", ["Previous manifest in Git—revert deploy points to sha256-previous instantly without retrain.",]),
        ("## Compliance retention", ["Object lock 7 years for regulated verticals—automate legal hold tags.",]),
    ],
}

CONTENT_EXT["devops-model-governance-audit"] = {
    "faqs": [
        {"q": "What must model audit trails capture?", "a": "Who approved promotion, training data snapshot, hyperparameters, bias/fairness eval results, and deployment timestamp—not Slack threads alone."},
        {"q": "Pre-deploy vs post-deploy governance?", "a": "Pre-deploy blocking gates for regulated use cases. Post-deploy checklist-only fails audits."},
        {"q": "How store approvals?", "a": "Signed records in governance DB or MLflow tags with approver identity from SSO—not editable wiki."},
        {"q": "Third-party model governance?", "a": "Vendor model cards, license, and subprocessors documented same as internal models."},
    ],
    "hook": "Regulator asked who approved model v3—only a Slack thread existed. Model governance audit trails must be immutable, searchable, and tied to identity.",
    "sections": [
        ("## Approval workflow", ["Ticket ID required to transition Production. Webhook writes audit row: approver, timestamp, eval summary hash.",]),
        ("## Bias and fairness artifacts", ["Store report PDF and metric JSON per version. Block promotion if disparity ratio exceeds policy.",], """```yaml
governance:
  required_artifacts:
    - bias_report
    - data_sheet
  approvers_group: ml-governance
```"""),
        ("## Immutable audit store", ["Append-only table or S3 with Object Lock. SIEM correlation for deploy events.",]),
        ("## Periodic recertification", ["Quarterly review: still fit for purpose? Data drift? Re-approve or archive.",]),
        ("## Incident linkage", ["Model version in every prediction log enables trace-back when outcome challenged legally.",]),
    ],
}

CONTENT_EXT["devops-model-monitoring-drift"] = {
    "faqs": [
        {"q": "Data drift vs concept drift?", "a": "Data drift: input feature distribution shifts. Concept drift: relationship features→target changes. Monitor both; retrain triggers differ."},
        {"q": "Which statistical tests?", "a": "PSI, KL divergence, Kolmogorov-Smirnov for numeric; chi-square for categorical. Thresholds tuned per feature business impact."},
        {"q": "Prediction drift without labels?", "a": "Monitor output score distribution vs training baseline. Sudden shift may indicate upstream bug or real drift."},
        {"q": "Infrastructure metrics insufficient?", "a": "CPU healthy while accuracy collapses—model quality metrics required: latency, error rate, business KPI, drift scores."},
    ],
    "hook": "Model accuracy collapsed after a market shift with no drift alerts—monitoring GPU CPU misses the signal that matters: input and outcome distributions.",
    "sections": [
        ("## Feature drift pipeline", ["Batch job compares prod logged features to training snapshot daily. PSI >0.2 pages ML on-call.",]),
        ("## Concept drift with delayed labels", ["When labels arrive days later, track rolling accuracy by cohort. Alert on 7-day window drop >5%.",], """```python
psi = compute_psi(reference=train["amount"], current=prod_last_week["amount"])
if psi > 0.25:
    alert("feature amount drift")
```"""),
        ("## Dashboard layers", ["Infra: latency, GPU. Model: score histogram, missing feature rate, drift PSI table. Business: conversion, fraud rate.",]),
        ("## Retrain triggers", ["Automated retrain proposal ticket when multiple features drift—not auto-deploy without eval gate.",]),
        ("## Shadow comparison", ["Log challenger model scores alongside champion without serving—detect drift impact before promotion.",]),
    ],
}

CONTENT_EXT["devops-model-rollout-canary"] = {
    "faqs": [
        {"q": "Canary vs shadow for models?", "a": "Canary serves fraction of traffic with challenger responses. Shadow runs challenger offline on prod inputs—zero user impact, higher compute."},
        {"q": "Which metrics gate promotion?", "a": "Latency p99, error rate, business KPI (conversion, fraud catch), and fairness—not offline accuracy alone."},
        {"q": "Traffic split mechanics?", "a": "Service mesh VirtualService weights, KServe canaryTrafficPercent, or inference gateway header-based routing."},
        {"q": "Rollback criteria?", "a": "Automated revert if canary error rate 2× champion or KPI drops beyond confidence interval for preset duration."},
    ],
    "hook": "New model deployed 100% and latency regression hit all users—canary and shadow deployments compare production behavior before committing traffic.",
    "sections": [
        ("## Shadow first, canary second", ["Shadow logs challenger predictions; compare offline metrics. Canary when shadow KPI neutral or better.",]),
        ("## KServe canaryTrafficPercent", ["InferenceService with canary spec routes percentage. Monitor nv_inference_request_success per revision.",], """```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: fraud
spec:
  predictor:
    canaryTrafficPercent: 10
    model:
      modelFormat:
        name: sklearn
      storageUri: s3://models/fraud/v8
```"""),
        ("## Statistical guardrails", ["Bayesian or frequentist test on business metric with minimum sample size—avoid premature winner on noise.",]),
        ("## User cohort stickiness", ["Hash user_id for consistent variant assignment across requests. Random per-request breaks session coherence.",]),
        ("## Rollback automation", ["Flagger or custom controller sets canary to 0% on SLO burn.",]),
    ],
}

CONTENT_EXT["devops-model-serving-a-b-testing"] = {
    "faqs": [
        {"q": "How assign users to A/B variants?", "a": "Consistent hash on user_id or session_id modulo 100. Store assignment in cookie or feature flag service—not random per request."},
        {"q": "Statistical power before starting?", "a": "Pre-calculate sample size for minimum detectable effect on primary KPI. Underpowered tests declare winners randomly."},
        {"q": "Multiple model variants?", "a": "Multivariate tests need larger samples—often sequential A/B then A/B/C after power check."},
        {"q": "Metrics beyond accuracy?", "a": "Business outcomes: revenue, retention, fraud dollars caught. Model metric alone misleads when product tradeoffs exist."},
    ],
    "hook": "Manual 50/50 split broke when pods restarted—sticky sessions lost and users flipped variants mid-checkout. Production model A/B needs consistent hashing and power analysis.",
    "sections": [
        ("## Assignment layer", ["Envoy header injection or app middleware sets variant from hash(user_id, experiment_salt). Persist in structured log for analysis.",]),
        ("## Implementation sketch", ["",], """```python
def variant(user_id: str, experiment: str) -> str:
    bucket = int(hashlib.sha256(f"{experiment}:{user_id}".encode()).hexdigest(), 16) % 100
    return "challenger" if bucket < 50 else "champion"
```"""),
        ("## Logging for analysis", ["Every prediction log: user_id, variant, model_version, score, outcome label when available.",]),
        ("## Power calculator", ["Before launch: MDE 2%, alpha 0.05, power 0.8 → required N users. Stop early only with sequential testing protocol.",]),
        ("## Ethics and compliance", ["Document experiment in governance registry. Exclude vulnerable populations if policy requires.",]),
    ],
}
