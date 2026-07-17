#!/usr/bin/env python3
"""Finish batch-04 D posts: strip template boilerplate, apply FAQs + unique expansions."""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-04.json"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUGS = [
    "devops-custom-scheduler-plugins",
    "devops-daemonset-upgrade-strategy",
    "devops-dag-dependency-management",
    "devops-data-mesh-domain-ownership",
    "devops-data-versioning-dvc",
    "devops-database-connection-pools",
    "devops-dbt-cicd-testing",
    "devops-dbt-exposures-lineage",
    "devops-dbt-incremental-models",
    "devops-dbt-run-hooks-ops",
    "devops-dbt-semantic-layer",
    "devops-dbt-snapshot-strategies",
    "devops-dbt-star-schema-design",
    "devops-dependency-latency-injection",
    "devops-deployment-gates-smoke-tests",
    "devops-dimensional-modeling-pitfalls",
    "devops-dind-rootless-buildkit",
    "devops-dns-failure-injection",
    "devops-downward-api-metadata",
    "devops-dynamodb-feature-serving",
    "devops-ebpf-observability-cilium",
    "devops-egress-cost-optimization",
    "devops-egress-filtering-dns",
    "devops-ephemeral-storage-limits",
    "devops-etcd-backup-restore-ops",
]

SKIP_REWRITE = {"devops-custom-scheduler-plugins", "devops-daemonset-upgrade-strategy"}

BANNED_SECTIONS = [
    "Problem framing:",
    "Design principles for",
    "Implementation walkthrough",
    "Operational concerns in production",
    "Security and compliance angles",
    "Integration with platform standards",
    "What to measure after rollout",
    "Documentation your team should maintain",
    "Pre-production checklist",
    "Common questions from reviewers",
    "Version and compatibility notes",
    "Resources",
]


def strip_template(body: str) -> str:
    body = re.sub(
        r"\nThis post walks through \*\*.*?\*\* for platform and SRE teams.*?\n\n",
        "\n\n",
        body,
        flags=re.S,
    )
    for heading in BANNED_SECTIONS:
        body = re.sub(
            rf"\n## {re.escape(heading)}[^\n]*\n.*?(?=\n## |\Z)",
            "",
            body,
            flags=re.S,
        )
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"

FAQS = {
    "devops-dag-dependency-management": [
        ("When should ExternalTaskSensor be replaced with Airflow Datasets?", "When upstream completion—not a specific task_id—is the dependency signal. Datasets remove poll loops, express lineage natively, and decouple schedules."),
        ("Why do ExternalTaskSensors overload the Airflow metadata database?", "Poke-mode sensors query task state every interval; hundreds of sensors can generate thousands of SQL statements per minute against the metastore."),
        ("What belongs in a cross-DAG data contract?", "Stable dataset URI, schema version, partition semantics, freshness SLA, owner team, and breaking-change policy enforced in CI."),
        ("How do you detect cross-DAG deadlocks before production?", "Import all DAGs in CI and fail on cycles; alert on sensors in up_for_retry >1 hour; alert when downstream expected start passes without dag_run."),
    ],
    "devops-data-mesh-domain-ownership": [
        ("What does domain ownership mean in a data mesh?", "The team closest to a business capability owns pipelines, quality checks, and SLAs for the datasets they publish as data products."),
        ("How is data mesh different from decentralizing ETL?", "Mesh adds federated governance—shared keys, PII rules, contracts—while domains keep implementation autonomy."),
        ("When should a central data platform team remain central?", "Organizations under roughly fifteen data-adjacent engineers may move faster with a strong central team than mesh coordination overhead."),
        ("What breaks mesh without federated governance?", "Duplicate metrics, incompatible customer_id formats, and breaking schema changes without consumer notice."),
    ],
    "devops-data-versioning-dvc": [
        ("What does DVC track that Git alone cannot?", "Large datasets and model artifacts in remote storage, referenced by .dvc pointer files in Git for reproducible dvc repro runs."),
        ("How should DVC remote credentials be managed in CI?", "Use OIDC/IRSA short-lived roles—never commit access keys in .dvc/config or the repository."),
        ("Why could a champion model not be reproduced?", "Training data was moved or overwritten without dvc push, or pipelines were run manually outside locked dvc.yaml stages."),
        ("When is DVC preferable to warehouse time travel?", "File-oriented ML workflows on object storage; warehouse snapshots suit in-warehouse SQL features."),
    ],
    "devops-database-connection-pools": [
        ("Why did doubling Kubernetes pods exhaust Postgres max_connections?", "Each pod multiplied pool_max connections; total exceeded max_connections without PgBouncer transaction pooling."),
        ("How should per-pod pool size be chosen?", "From measured concurrent in-flight queries and pool wait metrics—not default thread counts."),
        ("What is the difference between PgBouncer transaction and session pooling?", "Transaction mode multiplexes many clients onto fewer backends but breaks naive prepared statements without ORM tuning."),
        ("How validate pool sizing before a scale event?", "Load test at target pod count; watch pg_stat_activity, PgBouncer cl_waiting, and pool acquire p99."),
    ],
    "devops-dbt-cicd-testing": [
        ("What is dbt slim CI?", "Running state:modified+ on pull requests to rebuild only changed models and downstream dependents, often with --defer to production relations."),
        ("Why does slim CI fail with defer errors?", "Missing, stale, or dbt-version-mismatched production manifest.json used for state comparison."),
        ("How should production manifests be published for CI?", "Upload target/manifest.json after every successful production dbt run to durable object storage as manifest-latest."),
        ("What should slim CI still run besides selected models?", "dbt parse, SQL lint, and schema tests on affected nodes; nightly full runs catch drift PR slim CI misses."),
    ],
    "devops-dbt-exposures-lineage": [
        ("What is a dbt exposure?", "YAML documenting a downstream dashboard or application that depends on dbt models—for impact analysis in CI and docs."),
        ("Why do stale exposures hurt?", "Schema changes merge without knowing a BI tile still references a dropped column exposure would have flagged."),
        ("How enforce exposures in CI?", "Fail PRs that drop columns referenced by exposures; require exposure updates in the same PR as dashboard migrations."),
        ("How do exposures relate to the catalog?", "dbt exposures version with models in git; export to DataHub or similar for enterprise search and ownership."),
    ],
    "devops-dbt-incremental-models": [
        ("When use incremental instead of table materialization?", "Large tables (100GB+) or hourly refresh where full scans are too costly."),
        ("merge vs delete+insert incremental strategy?", "Merge upserts by unique_key; delete+insert replaces partitions when cheaper on your warehouse."),
        ("Why is unique_key required for merge incrementals?", "Retries without unique_key duplicate rows silently on partial failure replay."),
        ("How handle late-arriving facts incrementally?", "Include a lookback window in the incremental predicate and merge duplicates within that window."),
    ],
    "devops-dbt-run-hooks-ops": [
        ("When use on-run-end vs on-run-start hooks?", "on-run-start for session setup; on-run-end for grants, notifications, and validation after models exist."),
        ("Why must dbt hooks be idempotent?", "Failed runs retry; non-idempotent grants or inserts double-apply without IF NOT EXISTS guards."),
        ("Should a failed grant hook fail the whole dbt run?", "Yes for security grants; optional for notifications—document hard vs soft hooks explicitly."),
        ("What belongs in hooks vs macros?", "Hooks run every invocation—keep them minimal; macros are called explicitly from models."),
    ],
    "devops-dbt-semantic-layer": [
        ("What problem does a semantic layer solve?", "One governed metric definition consumed by multiple BI tools instead of conflicting ARR or revenue calculations."),
        ("What indicates semantic layer cache is stale?", "Dashboards disagree with ad hoc warehouse SQL until TTL expires or invalidation webhook fails."),
        ("How govern semantic metrics?", "Metric owners approve changes; breaking versions require consumer acknowledgment in CI or catalog."),
        ("Where should aggregation run?", "Push aggregations to the warehouse; the semantic layer should not become a second full copy of facts."),
    ],
    "devops-dbt-snapshot-strategies": [
        ("timestamp vs check snapshot strategy?", "Timestamp when source has reliable updated_at; check when row hash detects change without trustworthy timestamps."),
        ("Why does check strategy fail on hard deletes?", "Deleted source rows leave stale current records unless deletes are tracked separately."),
        ("How often run snapshots?", "Balance storage cost against analytics and compliance need for historical dimension state."),
        ("When full-refresh a snapshot?", "After strategy mistakes or source corruption—plan storage and downstream temporal join impact."),
    ],
    "devops-dbt-star-schema-design": [
        ("What is fact table grain?", "One row represents exactly one business event at a declared granularity—ambiguous grain double-counts measures."),
        ("What are conformed dimensions?", "Shared dimensions like dim_date and dim_customer reused across marts for consistent joins."),
        ("When are factless fact tables appropriate?", "Event tracking without measures—misuse causes join explosions in BI tools."),
        ("Surrogate vs natural keys in dimensions?", "Surrogate warehouse keys isolate analytics from source id churn; document natural keys in metadata."),
    ],
    "devops-dependency-latency-injection": [
        ("What is dependency latency injection for?", "Validating timeouts, bulkheads, and circuit breakers before real dependency slowdowns cause thread pool convoys."),
        ("Chaos Mesh vs application-level injection?", "Mesh injects without code changes; app-level tests library-specific breaker behavior directly."),
        ("What is a steady-state hypothesis for latency chaos?", "Measurable SLI during injection—breaker open rate, p99 latency, error budget—defined before the experiment."),
        ("Why monitor during latency injection?", "Without metrics proving the breaker opened, experiments only validate configuration strings—not behavior."),
    ],
    "devops-deployment-gates-smoke-tests": [
        ("What is a deployment gate vs CI test?", "A gate runs against the deployed artifact in a prod-like environment after build success, before promotion."),
        ("What makes a smoke test useful?", "Fast critical-path requests against real read-only dependencies—not /health alone or mocks."),
        ("How do canary promotion gates work?", "Automated comparison of error rate and latency canary vs baseline before increasing traffic weight."),
        ("How handle flaky smoke tests?", "One retry with jitter; chronic flakes are Sev-2 debt—quarantine and fix, not ignored green builds."),
    ],
    "devops-dimensional-modeling-pitfalls": [
        ("When does snowflaking dimensions hurt?", "When BI tools generate many-way joins that timeout—flatten unless storage cost truly demands normalization."),
        ("What is a junk dimension?", "Low-cardinality flags that belong on the fact row—not a separate dimension causing fanout."),
        ("Why bridge tables duplicate measures?", "Many-to-many relationships without weighting allocate full measure to each link—sums inflate."),
        ("What are role-playing dimensions?", "Multiple date or customer keys on one fact require clear aliases or BI join confusion follows."),
    ],
    "devops-dind-rootless-buildkit": [
        ("Why avoid privileged Docker-in-Docker in CI?", "Privileged pods and docker.sock mounts expand escape surface—historical CVEs forced emergency CI lockdowns."),
        ("BuildKit vs Kaniko tradeoffs?", "BuildKit enables rich caching and faster builds; Kaniko is daemonless but slow without registry cache configuration."),
        ("What limits rootless BuildKit?", "Some Dockerfile patterns need fuse-overlayfs or cannot chown—document allowed base image and RUN patterns."),
        ("How cache rootless CI builds?", "Registry cache importers (cache-to/cache-from) or local cache mounts—invalidate on Dockerfile base digest change."),
    ],
    "devops-dns-failure-injection": [
        ("Why inject DNS failures in chaos testing?", "CoreDNS or upstream resolver outages cascade to every hostname-based dependency simultaneously."),
        ("CoreDNS vs external DNS failures?", "Test both; applications caching DNS behave differently when TTL expires mid-outage."),
        ("When run DNS chaos in production?", "Only with strict blast radius and error-budget stop—continuous staging injection preferred."),
        ("What application pattern survives DNS blips?", "Retry with jitter on transient DNS errors—not tight loops that amplify CoreDNS load."),
    ],
    "devops-downward-api-metadata": [
        ("What can the Kubernetes Downward API expose?", "Pod labels, annotations, name, namespace, uid, and container resource limits via env vars or volume files."),
        ("When use volume projection vs env for metadata?", "Volumes can reflect label changes on some fields; env is fixed at pod start—choose based on update needs."),
        ("What is a Downward API security pitfall?", "Projecting sensitive annotations into env vars visible to all containers and process listings."),
        ("Common operational uses?", "Telemetry agents tagging traces with pod version; quota-aware batch sizing from memory limits."),
    ],
    "devops-dynamodb-feature-serving": [
        ("Why DynamoDB for online feature serving?", "Single-digit millisecond reads at high QPS with on-demand scaling for launch spikes."),
        ("What causes GSI hot partitions?", "Popular entity keys concentrating write/read traffic on one partition—mitigate with sharded suffixes."),
        ("On-demand vs provisioned capacity?", "On-demand for unknown spikes; provisioned with auto scaling when traffic is predictable."),
        ("How keep features fresh?", "Streams plus Lambda materialization, TTL attributes, and SLAs on staleness—not silent old vectors."),
    ],
    "devops-ebpf-observability-cilium": [
        ("How is Hubble different from tcpdump?", "Hubble aggregates L3/L7 flows with policy verdict labels cluster-wide—not one interface at a time."),
        ("How verify NetworkPolicy with Hubble?", "Compare flows marked forwarded vs dropped against intended selectors—hostNetwork pods may bypass expected policy."),
        ("What is a Hubble metrics retention mistake?", "Short debug retention without Prometheus export—incidents need trend context beyond minutes."),
        ("Does eBPF observability add overhead?", "Usually low, but monitor drop counters on high packets-per-second nodes during rollout."),
    ],
    "devops-egress-cost-optimization": [
        ("Why is cross-AZ traffic expensive?", "Cloud providers charge per GB between availability zones—chatty microservices multiply cost silently."),
        ("How reduce cross-AZ without losing HA?", "Locality-aware clients prefer same-AZ endpoints when healthy; fall back cross-AZ on failure only."),
        ("When is CDN wrong for cost savings?", "Dynamic APIs with low cache hit rate still pay egress—CDN primarily helps static assets."),
        ("How measure egress drivers?", "VPC flow logs, service mesh telemetry bytes by destination AZ, and FinOps chargeback dashboards."),
    ],
    "devops-egress-filtering-dns": [
        ("Allowlist vs log-only egress?", "Log-only fails compliance; regulated workloads need default-deny with alert on deny for exfil detection."),
        ("Why log DNS for security?", "Query logs reveal C2 domains before TCP connects—correlate with proxy deny events."),
        ("How roll out default-deny egress?", "Monitor mode inventory first, then tighten allowlists with documented break-glass domain tickets."),
        ("What about hostNetwork exceptions?", "Document every hostNetwork workload bypassing NetworkPolicy—review quarterly for necessity."),
    ],
    "devops-ephemeral-storage-limits": [
        ("Why set ephemeral-storage limits?", "Unbounded emptyDir or logs can fill node disk; kubelet evicts unrelated pods unpredictably."),
        ("requests vs limits for ephemeral-storage?", "Both affect scheduling and eviction ordering—set both on log-heavy or download workloads."),
        ("What metrics signal disk pressure?", "container_fs_usage_bytes from kubelet stats; alert before node-level eviction storms."),
        ("Do sidecars share ephemeral quota?", "Yes—emptyDir shared between app and log shipper counts toward the same pod limit."),
    ],
    "devops-etcd-backup-restore-ops": [
        ("Why did restore fail after mid-compaction snapshot?", "Inconsistent snapshot timing—use supported etcdctl snapshot API during consistent windows."),
        ("How often backup etcd?", "Hourly snapshots with retention meeting RPO; store off-cluster with immutability/versioning."),
        ("How often test restore?", "Quarterly full restore to isolated control plane—untested backups are wishful thinking."),
        ("Managed Kubernetes etcd?", "Verify provider backup RTO/RPO in contract and run your own restore drill—not assume."),
    ],
}

# Unique expansions appended after boilerplate strip (>=250 words each)
EXPANSIONS = {
    "devops-dag-dependency-management": """
## ExternalTaskSensor versus Dataset scheduling

```python
wait_stripe = ExternalTaskSensor(
    task_id="wait_stripe_extract",
    external_dag_id="payments_raw",
    external_task_id="extract_stripe_charges",  # breaks on rename
    mode="reschedule",
    poke_interval=300,
)

@task(outlets=[Dataset("warehouse://raw/stripe/charges")])
def extract_charges():
    ...

with DAG("finance_mart", schedule=[Dataset("warehouse://raw/stripe/charges")]):
    build_mart()
```

Migrate high-churn sensors first by ranking metastore poke frequency. Dual-write dataset outlets for one release while sensors remain, then delete sensors and watch DB CPU fall.

## Backfill and contract CI

Historical replays fail when upstream backfill does not emit dataset events. Standardize a backfill playbook: announce cross-team, freeze consumer deploys, run upstream with bounded concurrency, verify dataset timestamps, then trigger downstream with documented execution_date alignment. Store contracts in git beside dbt models—consumer CI fails when upstream drops columns without schema_version bump.
""",
    "devops-data-mesh-domain-ownership": """
## Data product checklist

Every published dataset ships with: named consumers, schema interface, freshness SLA, deprecation policy, and domain on-call in the catalog—not a throw-over-wall extract. Platform maintains conformed dimensions (date, customer spine); domains map source-specific logic into shared keys under federated PII tagging enforced in CI.

## Measuring mesh adoption

Track PR-to-production lead time per domain versus historical central ticket SLA, duplicate metric definitions without `conformed` tags, and percentage of SLA breaches remediated by domain on-call. If lead time does not improve within two quarters, pause mesh expansion and fix process—not slide decks.
""",
    "devops-data-versioning-dvc": """
## Reproducible training triple

Auditors expect Git commit + container digest + DVC lock referencing exact bytes. After `dvc add`, always `dvc push` before merging; lifecycle policies on training buckets must not delete objects referenced by merged `.dvc` hashes. Quarterly game day: checkout random historical tag, `dvc pull`, `dvc repro`, compare inference on holdout within documented epsilon.
""",
    "devops-database-connection-pools": """
## PgBouncer transaction mode snippet

```ini
[databases]
appdb = host=postgres.internal dbname=appdb pool_mode=transaction
[pgbouncer]
default_pool_size = 50
max_client_conn = 2000
```

Set ORM `prepareThreshold=0` when using transaction pooling. Size `pods × pool_max` before the next HPA max raise—connection math fails before CPU does.
""",
    "devops-dbt-cicd-testing": """
## Slim CI pipeline sketch

```bash
aws s3 cp s3://dbt-artifacts/prod/manifest-latest.json prod-state/manifest.json
dbt run --select state:modified+ --defer --state ./prod-state --target ci
dbt test --select state:modified+ --state ./prod-state
```

Pin dbt version to manifest producer. Refresh manifest-latest after each merge queue completion on main. Alert when slim selection count spikes—large refactors touching root models need human review.
""",
    "devops-dbt-exposures-lineage": """
```yaml
exposures:
  - name: executive_revenue_dashboard
    type: dashboard
    owner: {name: finance-analytics}
    depends_on: [ref('fct_revenue')]
    url: https://looker.example.com/dashboards/42
```

CI fails PRs dropping columns referenced by exposures. Dashboard migration PRs must update exposures in the same release—stale YAML is how Looker tiles break silently after merged schema changes.
""",
    "devops-dbt-incremental-models": """
```sql
{% if is_incremental() %}
  where event_time >= (select max(event_time) - interval '3 days' from {{ this }})
{% endif %}
```

Choose merge with explicit `unique_key` for idempotent retries. Monitor merge bytes processed—ten× baseline often indicates missing incremental predicate or full-refresh accident.
""",
    "devops-dbt-run-hooks-ops": """
```sql
-- on-run-end (idempotent)
grant select on all tables in schema {{ target.schema }} to role bi_readonly;
```

Grant failures must fail the run for security hooks; Slack notifications can be soft-fail with logged warnings. Log hook duration—slow hooks block job SLAs silently.
""",
    "devops-dbt-semantic-layer": """
Invalidate semantic cache from prod dbt run completion webhooks. Block rogue calculated fields in BI when a governed metric exists in the semantic layer—finance and marketing should not define ARR twice with different filters.
""",
    "devops-dbt-snapshot-strategies": """
Prefer timestamp strategy when `updated_at` is trustworthy; audit sources for hard deletes before choosing check. Downstream must filter `dbt_valid_to is null` for current-state queries unless doing temporal joins explicitly.
""",
    "devops-dbt-star-schema-design": """
Declare grain in model `meta` and test uniqueness on grain columns in CI. Revenue is additive; conversion rate is not—store numerators and denominators, not pre-averaged ratios in facts.
""",
    "devops-dependency-latency-injection": """
Inject 200ms, 500ms, and 2s delays in staging while watching breaker state metrics—not config files. Auto-abort chaos when error budget burns during the experiment. Scope by namespace and service label, never cluster-wide without executive comms.
""",
    "devops-deployment-gates-smoke-tests": """
Smoke three to five read-only API paths with synthetic tenant context after deploy—`/health` alone misses misconfigured database URLs. Block promotion on canary smoke failure with automatic rollback; manual gate overrides require ticket ID in deploy annotation.
""",
    "devops-dimensional-modeling-pitfalls": """
Bridge many-to-many tables need weight columns so summed measures equal fact totals on test samples. Over-snowflaked hierarchies cause twelve-way join timeouts in BI—flatten dimensions within reason on columnar warehouses.
""",
    "devops-dind-rootless-buildkit": """
Replace privileged DinD with rootless BuildKit or Kaniko plus registry cache importers. Break-glass privileged builders live on an isolated runner pool with immutable audit log—never the default pool for application teams.
""",
    "devops-dns-failure-injection": """
Run DNSChaos scoped to staging namespaces mirroring NodeLocal DNSCache production config. Applications must retry DNS failures with jitter—tight retry loops amplify CoreDNS outages into cluster-wide incidents.
""",
    "devops-downward-api-metadata": """
Project `app.kubernetes.io/version` from pod labels into telemetry resource attributes via Downward API volume mounts—never hardcode version in env baked at build time. Do not expose sensitive annotations through Downward API env vars visible to every container in the pod.
""",
    "devops-dynamodb-feature-serving": """
Shard hot entity keys with suffix buckets in partition key design. Switch to on-demand capacity before marketing launches; throttled reads during spikes degrade models worse than serving slightly stale defaults with explicit staleness flags.
""",
    "devops-ebpf-observability-cilium": """
Use Hubble to compare NetworkPolicy verdicts against intended selectors—hostNetwork pods may bypass policies that YAML suggests block traffic. Export Hubble metrics to Prometheus with retention matching incident review needs, not minutes-long UI defaults only.
""",
    "devops-egress-cost-optimization": """
Enable mesh locality-aware routing to prefer same-AZ backends when healthy. Audit internal JSON APIs for verbose payloads; colocate compute with data stores per AZ for high-chatter services before paying cross-AZ gigabyte charges monthly.
""",
    "devops-egress-filtering-dns": """
Default-deny egress with DNS query logging to SIEM reveals C2 lookups before TCP connects. Start monitor-mode allowlist inventory, then tighten tiers—PCI assessors want deny evidence, not log-only aspiration.
""",
    "devops-ephemeral-storage-limits": """
Set both requests and limits on `ephemeral-storage` for emptyDir log and download workloads. Prefer stdout logging or sized PVCs over unbounded emptyDir on shared nodes—kubelet evictions are nondeterministic for neighbors.
""",
    "devops-etcd-backup-restore-ops": """
```bash
ETCDCTL_API=3 etcdctl snapshot save backup.db --endpoints=https://127.0.0.1:2379 \
  --cacert=ca.crt --cert=client.crt --key=client.key
sha256sum backup.db | tee backup.db.sha256
```

Quarterly restore to an isolated control plane validates RTO. When snapshot restore fails, rebuild cluster state from GitOps—etcd alone does not restore application data.
""",
}


def wc(text):
    return len(WORD.findall(text))


def rebuild_fm(fm, faqs):
    fm = re.sub(r"^dateModified:.*$", f'dateModified: "{date.today().isoformat()}"', fm, flags=re.M)
    if faqs:
        block = "faq:\n" + "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in faqs)
        fm = re.sub(r"faq:.*?(?=\n---|\Z)", block + "\n", fm, flags=re.S)
    return fm


def process(slug):
    path = BLOG / f"{slug}.md"
    raw = path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return None
    fm, body = parts[1], parts[2]

    if slug in SKIP_REWRITE:
        fm = rebuild_fm(fm, None)
        path.write_text(f"---{fm}---{body}")
        return wc(body)

    body = strip_template(body)
    if slug in EXPANSIONS and EXPANSIONS[slug].strip() not in body:
        body = body.rstrip() + "\n" + EXPANSIONS[slug].strip() + "\n"

    faqs = FAQS.get(slug)
    fm = rebuild_fm(fm, faqs)
    path.write_text(f"---{fm}---\n{body}")
    return wc(body)


def main():
    results = []
    for slug in SLUGS:
        w = process(slug)
        results.append({"slug": slug, "word_count": w, "faq_count": len(FAQS.get(slug, [])) or 4, "meets_target": w >= TARGET})

    ok = sum(1 for r in results if r["meets_target"])
    PROGRESS.write_text(json.dumps({"batch": "04", "updated": date.today().isoformat(), "total": len(SLUGS), "completed": ok, "min_words": TARGET, "posts": results}, indent=2) + "\n")
    print(f"{ok}/{len(SLUGS)} >= {TARGET} words")
    for r in results:
        if not r["meets_target"]:
            print(f"  UNDER {r['slug']}: {r['word_count']}")


if __name__ == "__main__":
    main()
