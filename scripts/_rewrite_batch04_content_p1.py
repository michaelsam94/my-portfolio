# Part 1: posts 1-8 — imported by _rewrite_batch04_content.py

POSTS_P1 = {}

POSTS_P1["devops-experiment-tracking-governance"] = (
    {
        "title": "Experiment Tracking Governance and Retention",
        "description": "MLflow and W&B adoption at scale needs naming conventions, tiered artifact retention, and PII scrubbing in params—before a full disk stops training jobs and auditors find emails in run metadata.",
        "datePublished": "2026-07-17",
        "tags": ["DevOps", "MLOps", "Platform"],
        "keywords": "experiment tracking, MLflow governance, artifact retention, W&B, PII in metadata, MLOps compliance",
        "faq": [
            {
                "q": "How long should ML experiment artifacts be retained?",
                "a": "Tier by outcome: production-bound runs that produced a deployed model keep artifacts for the model's lifetime plus your compliance window (often 3–7 years). Exploratory runs without a registered model typically need 30–90 days. Failed CI smoke runs can expire in 7 days. Encode tiers in lifecycle policies rather than one global TTL.",
            },
            {
                "q": "What metadata should never appear in experiment params?",
                "a": "Direct identifiers (email, phone, SSN), raw free-text user queries, full payment tokens, and unredacted IP addresses. Use hashed entity IDs, bucketed cohort labels, and reference external tables for join-back during debugging. Scrub in CI before `mlflow.log_param` executes.",
            },
            {
                "q": "Who owns experiment naming conventions in a multi-team org?",
                "a": "Platform MLOps owns the schema (`{team}/{project}/{objective}/{date}`), data science leads approve exceptions, and CI rejects non-conforming experiment names on merge to shared tracking servers. Individual notebook runs on local SQLite are exempt; anything synced to the central server is not.",
            },
            {
                "q": "How do you prevent run spam from hyperparameter sweeps?",
                "a": "Require parent run IDs for sweeps, cap concurrent child runs per user via orchestrator quotas, and auto-archive parent groups when the sweep completes. Optuna and Ray Tune integrations should tag `sweep_id` so retention jobs delete the entire tree atomically.",
            },
        ],
    },
    r"""The MLflow tracking server ran out of disk on a Thursday—not because models grew, but because three teams had been logging every grid-search permutation for eight months with no retention policy. Training jobs failed with 507 errors. Worse: a compliance review found customer email addresses in `log_param` calls from a churn model notebook someone promoted to "production experiment" status.

Experiment tracking is infrastructure once more than one team touches the same server. Governance is not bureaucracy; it is how you keep the artifact store queryable, affordable, and audit-safe.

## Naming runs so humans and robots can find them

Ad hoc experiment names (`test2_final_v3`) do not survive team turnover. Adopt a path-like convention:

```
{team}/{project}/{objective}/{YYYYMMDD}-{short-hash}
```

Examples:

| Bad | Good |
|-----|------|
| `my_run` | `fraud/risk-v2/xgb-baseline/20260717-a3f9` |
| `prod_retrain` | `recs/homefeed/two-tower/20260701-prod-candidate` |

MLflow experiment names map to folders in the artifact backend. S3 lifecycle rules can prefix-match on `fraud/` vs `sandbox/` if teams honor boundaries.

Enforce in CI when training code runs on shared runners:

```python
import re
import mlflow

EXPERIMENT_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]*/[a-z][a-z0-9-]*/[a-z][a-z0-9-]*/\d{8}-[a-z0-9]{4,8}$"
)

def start_run(experiment_name: str, **kwargs):
    if not EXPERIMENT_PATTERN.match(experiment_name):
        raise ValueError(f"Experiment name must match governance pattern: {experiment_name}")
    mlflow.set_experiment(experiment_name)
    return mlflow.start_run(**kwargs)
```

## Retention tiers that finance and legal will sign

One global "delete after 90 days" policy breaks two ways: it deletes the artifact bundle for a model still serving traffic, or it keeps every failed notebook run forever.

Define tiers explicitly:

| Tier | Criteria | Artifact retention | Param/metric retention |
|------|----------|-------------------|------------------------|
| Production | Registered in model registry, `stage=Production` | Life of model + 3y | Full |
| Candidate | Registered, `stage=Staging` | 180 days | Full |
| Validated | Tagged `validated=true`, not registered | 90 days | Full |
| Exploratory | Default | 30 days | 30 days |
| CI smoke | Tag `ci=true` | 7 days | 7 days |

Implement with S3 lifecycle rules on prefix + MLflow scheduled jobs that mark runs archived, then delete artifact roots after grace period. Keep the **run record** (params, metrics, lineage) longer than large artifacts if storage is tight—metrics are kilobytes; parquet exports are terabytes.

```yaml
# mlflow-retention-job (CronJob sketch)
apiVersion: batch/v1
kind: CronJob
metadata:
  name: mlflow-retention
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: retention
              image: mlflow-retention:1.2.0
              env:
                - name: MLFLOW_TRACKING_URI
                  value: "https://mlflow.internal"
                - name: DRY_RUN
                  value: "false"
              args:
                - "--apply-tiers"
                - "--archive-exploratory-after-days=30"
                - "--delete-artifacts-after-archive-days=7"
          restartPolicy: OnFailure
```

Always run `--dry-run` weekly and diff output to a Slack channel before flipping production deletion.

## PII and secrets in metadata

Params and tags are replicated to every engineer's laptop when they `mlflow ui`. They land in backup tapes. Treat them like logs, not scratch space.

Block list at log time:

```python
FORBIDDEN_PARAM_KEYS = {"email", "user_email", "phone", "ssn", "query_text"}
FORBIDDEN_VALUE_PATTERN = re.compile(r"@|^\d{3}-\d{2}-\d{4}$")

def safe_log_param(key: str, value: str):
    if key.lower() in FORBIDDEN_PARAM_KEYS:
        raise PolicyViolation(f"Param key '{key}' is forbidden")
    if FORBIDDEN_VALUE_PATTERN.search(str(value)):
        raise PolicyViolation(f"Param value looks like PII")
    mlflow.log_param(key, value)
```

Pre-commit hooks scanning for `mlflow.log_param("email"` catch most mistakes. For sweeps that log entire config dicts, wrap `mlflow.start_run` context manager with a sanitizing filter.

## Access control and cost visibility

Central tracking servers need RBAC aligned to experiment prefixes. Fraud team engineers read `fraud/*`; they do not list `hr/*`. MLflow 2.x supports basic auth; larger orgs front it with OAuth2 proxy and map groups to experiment ACLs.

Chargeback: export per-team storage from the artifact backend monthly. Teams burning 40% of disk on unbounded sweeps get a ticket before you add another PVC.

## What to alert on

- Artifact store utilization above 75% (page platform), 85% (block new runs).
- Runs without tier tags older than 14 days (weekly report to team leads).
- Single run artifact size above 10 GB (often someone logged raw training data by mistake).
- Failed retention job executions.

## Rollout sequence

Week 1: announce naming schema, add CI lint, no deletion. Week 2: tag existing runs heuristically (`prod` in name → Candidate tier). Week 3: dry-run retention. Week 4: enforce with 14-day warning emails. Skipping the warning email step is how you lose the churn model's only reproducible training snapshot.

Experiment tracking governance is boring until the disk is full or the auditor arrives. Both happen on the same day if you wait long enough.
""",
)

POSTS_P1["devops-external-dns-automation"] = (
    {
        "title": "External DNS Automation for Kubernetes Ingress",
        "description": "ExternalDNS syncs Ingress and Gateway API hostnames to Route53 or Cloud DNS—but txt-owner-id scoping and policy=sync vs upsert-only determine whether a typo deletes production records.",
        "datePublished": "2026-10-07",
        "tags": ["DevOps", "Networking", "Kubernetes"],
        "keywords": "ExternalDNS, Route53, Cloud DNS, Kubernetes ingress DNS, txt-owner-id, Gateway API",
        "faq": [
            {
                "q": "What is the txt-owner-id flag in ExternalDNS?",
                "a": "It writes a TXT record alongside each managed A/AAAA/CNAME proving ownership. ExternalDNS only modifies records bearing its owner ID. Two clusters with different owner IDs can coexist in one zone without fighting—critical for split staging/prod or multi-cluster fleets.",
            },
            {
                "q": "Should ExternalDNS use sync or upsert-only policy?",
                "a": "Upsert-only creates and updates records it manages but never deletes. Sync deletes records in the zone that match its sources but are no longer desired—dangerous with `--domain-filter` misconfiguration. Start upsert-only in production; move to sync only after txt-owner-id scoping and dry-run validation in a sandbox zone.",
            },
            {
                "q": "How does ExternalDNS work with Gateway API HTTPRoute?",
                "a": "ExternalDNS 0.14+ watches Gateway API resources when configured with `sources: [gateway-httproute, gateway-grpcroute, gateway-tcproute]`. It reads hostnames from HTTPRoute `spec.hostnames` and targets from the associated Gateway status addresses—same ownership TXT pattern as Ingress.",
            },
            {
                "q": "Why did ExternalDNS delete unrelated Route53 records?",
                "a": "Usually `policy: sync` combined with overly broad `domainFilter` or missing txt-owner-id, so ExternalDNS treated legacy manual records as orphaned. Fix: narrow filters, unique owner ID per cluster, upsert-only until confident, and maintain a zone inventory outside ExternalDNS management tagged `manual-do-not-delete`.",
            },
        ],
    },
    r"""Someone deleted `api.example.com` at 3 a.m.—not a human with the AWS console, but ExternalDNS running with `policy: sync`, a mistyped `--domain-filter`, and the same txt-owner-id as last month's decommissioned cluster. Traffic routed to a stale load balancer for forty minutes until Route53 TTL expired.

ExternalDNS is a reconciliation loop: it watches Kubernetes sources (Ingress, Service, Gateway API routes), computes desired DNS records, and applies them to Route53, Google Cloud DNS, Azure DNS, or a dozen other providers. The controller is simple; the blast radius is not.

## Sources and record types

Typical Ingress annotation flow:

```
Ingress host: shop.example.com
  → ExternalDNS reads spec.rules[].host
  → Targets Ingress status.loadBalancer.ingress[0].hostname (or IP)
  → Creates/updates A, AAAA, or CNAME + ownership TXT
```

For Gateway API, the source is HTTPRoute hostnames paired with Gateway `.status.addresses`. Mixed clusters during migration may run both sources—ensure hostname ownership is exclusive per environment.

| Source | Hostname from | Target from |
|--------|---------------|-------------|
| Ingress | `spec.rules[].host` | Ingress LB status |
| Service (LoadBalancer) | annotation `external-dns.alpha.kubernetes.io/hostname` | Service LB status |
| HTTPRoute | `spec.hostnames[]` | Parent Gateway addresses |
| Istio Gateway | derived virtual service hosts | Gateway LB |

## Deployment hardening

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: external-dns
  namespace: external-dns
spec:
  template:
    spec:
      serviceAccountName: external-dns
      containers:
        - name: external-dns
          image: registry.k8s.io/external-dns/external-dns:v0.14.2
          args:
            - --source=ingress
            - --source=gateway-httproute
            - --provider=aws
            - --aws-zone-type=public
            - --domain-filter=example.com
            - --txt-owner-id=eks-prod-us-east-1
            - --txt-prefix=externaldns-
            - --policy=upsert-only
            - --registry=txt
            - --interval=1m
            - --log-level=info
            - --events
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
```

Key flags explained:

- **`domain-filter`**: restrict to zones you own. Never run unfiltered in prod.
- **`txt-owner-id`**: unique per cluster/environment. Document in runbook.
- **`policy=upsert-only`**: no deletions until you trust the config.
- **`registry=txt`**: ownership via TXT records (default for AWS).

IAM should be least privilege:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["route53:ChangeResourceRecordSets"],
      "Resource": "arn:aws:route53:::hostedzone/Z1234567890ABC"
    },
    {
      "Effect": "Allow",
      "Action": ["route53:ListHostedZones", "route53:ListResourceRecordSets"],
      "Resource": "*"
    }
  ]
}
```

Deny `route53:DeleteHostedZone`. ExternalDNS should not need it.

## Multi-cluster and split horizon

Staging and production clusters often share a parent zone (`staging.shop.example.com` vs `shop.example.com`). Give each cluster a distinct owner ID. For private zones associated with VPCs, run a separate ExternalDNS deployment with `--aws-zone-type=private` and `--zone-id-filter`.

Split-horizon (different answers inside corp network vs public internet) is **not** ExternalDNS's job alone—you need two deployments targeting different zones or provider views, with clear annotation conventions so app teams know which Ingress class gets which zone.

## Observability and change review

ExternalDNS emits Kubernetes events on record changes. Ship them to your log aggregator:

```
Normal  Synced ingress default/shop-ingress  CREATE A shop.example.com -> elb-123.us-east-1.elb.amazonaws.com
```

Alert on:

- Error loop rate sustained > 5 minutes (provider API throttling, IAM drift).
- Record pointing to LB that no longer exists (orphaned ingress status).
- Any DELETE event when policy is supposed to be upsert-only (config regression).

GitOps teams sometimes require PR approval for new hostnames via OPA Gatekeeper: reject Ingress without `external-dns.alpha.kubernetes.io/hostname` annotation matching an allowlist ConfigMap maintained by networking.

## Migration from manual DNS

Inventory existing records. Tag manual entries with TXT `managed-by=terraform-networking` outside ExternalDNS prefix. Enable ExternalDNS on a single low-risk hostname first; verify A and TXT records. Expand domain-filter gradually. Only after two weeks of clean upserts consider `policy: sync` for that owner ID—and keep Terraform-managed apex records (`example.com` MX, SPF) in a separate zone or with labels ExternalDNS ignores.

ExternalDNS removes toil until it removes production. Scope owner IDs, start upsert-only, and treat sync policy like a loaded weapon— useful, but never casual.
""",
)
