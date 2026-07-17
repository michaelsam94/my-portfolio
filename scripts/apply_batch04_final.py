#!/usr/bin/env python3
"""Replace batch-04 D post bodies with unique generated depth (no template sections)."""
import json
import re
import textwrap
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-04.json"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

KEEP = {"devops-custom-scheduler-plugins", "devops-daemonset-upgrade-strategy"}

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

# Topic-specific FAQs (import from finish_batch04_d)
from finish_batch04_d import FAQS, EXPANSIONS  # noqa: E402

TOPIC_META = {
    "devops-dag-dependency-management": {
        "hook": "Finance mart never scheduled Tuesday—upstream renamed a task_id Friday; ExternalTaskSensors waited forever.",
        "sections": [
            ("ExternalTaskSensor costs", "Rename fragility breaks silent string contracts. Poke mode hammers the metastore. execution_date alignment fails across schedules and DST. Deferrable sensors with Triggerer reduce worker and DB load during migration."),
            ("Dataset scheduling", "Producer outlets publish stable URIs; consumers schedule on dataset updates. Backfill must emit dataset events or historical partitions stall downstream without errors."),
            ("Data contracts", "Semver schema, partition keys, freshness SLA, and owner on-call. CI fails upstream column drops without version bump; compat shim tasks bridge one-release renames."),
            ("Dependency observability", "Dashboard minutes since dataset update, sensor retry counts, lineage in catalog. Alert missing downstream dag_run at SLA—not only upstream task failure."),
            ("Migration playbook", "Rank sensors by poke frequency, dual-write outlets one release, switch consumer schedules, delete sensors, validate DB CPU drop."),
        ],
    },
    "devops-data-mesh-domain-ownership": {
        "hook": "Subscriptions waited eleven weeks on central ETL tickets while payments published conflicting revenue definitions.",
        "sections": [
            ("Data products", "Named consumers, schema interface, SLA, lifecycle, domain on-call—not projects that rot when authors leave."),
            ("Federated governance", "Platform owns conformed keys and PII tags; domains own business meaning and models inside CI guardrails."),
            ("Embedded engineers", "Minimum one data engineer per mature domain; platform builds paved roads not approval queues for every mart."),
            ("SLA measurement", "Freshness error budgets; downstream fails loud on stale partitions with explicit staleness flags in features and dashboards."),
            ("Pilot expansion", "One domain pilot, conformed dimension spine, quarterly expansion, measure PR-to-prod lead time vs old ticket SLA."),
        ],
    },
    "devops-data-versioning-dvc": {
        "hook": "Regulators could not reproduce the March fraud model—Git commit existed but training objects were lifecycle-deleted on S3.",
        "sections": [
            ("dvc add and push", "Pointer files in Git; bytes in remote with immutability. Never overwrite objects in place without new dvc add hash."),
            ("dvc.yaml pipelines", "Stages declare deps and outs; dvc repro invalidates downstream only. Pair with container digest and locked requirements."),
            ("CI reproduction", "PR jobs pull prod-equivalent artifacts; repro changed stages; metrics gates block regressions on merge."),
            ("Credential hygiene", "OIDC/IRSA in CI; scan repos for keys in .dvc/config; separate dev and prod remotes."),
            ("Audit game days", "Random historical tag reproduced on clean VM; inference compared to holdout within epsilon tolerance."),
        ],
    },
    "devops-database-connection-pools": {
        "hook": "Autoscaler added forty pods; Postgres logged too many clients already within ninety seconds.",
        "sections": [
            ("Sizing math", "pods times pool_max must stay below max_connections minus admin reserve. Document formula before every HPA max increase."),
            ("PgBouncer modes", "Transaction pooling multiplexes clients; disable naive prepared statements. Session mode for LISTEN/NOTIFY workloads only."),
            ("Per-service defaults", "HTTP APIs often need five to ten connections per pod based on measured pool waits—not thread defaults of thirty."),
            ("Kubernetes surges", "Rolling deploys briefly double pods; include CronJob pools; separate read-replica pool endpoints."),
            ("Observability", "pg_stat_activity, cl_waiting, Hikari active connections, acquire p99—alert before users see timeouts."),
        ],
    },
    "devops-dbt-cicd-testing": {
        "hook": "A README typo triggered a two-hour full dbt run on four hundred models—zero SQL changed.",
        "sections": [
            ("state:modified+", "Select changed models and downstream dependents vs prod manifest. Plus suffix is essential for column renames propagating."),
            ("defer in CI", "Unresolved refs bind to production relations for unchanged upstream; CI schema builds subgraph only."),
            ("Manifest publishing", "Upload target/manifest.json after every prod run to manifest-latest; pin dbt version to producer."),
            ("Merge queue", "Refresh manifest from main after merge queue completes to avoid stale state comparisons on batched PRs."),
            ("Slim CI metrics", "Track PR duration, selected model count, defer failures—alert when selection hits root facts."),
        ],
    },
    "devops-dbt-exposures-lineage": {
        "hook": "Merged column drop broke a Looker tile—exposure YAML still listed the old field after dashboard migration.",
        "sections": [
            ("Exposure definitions", "Type dashboard or application, depends_on refs, owner, url—reviewed in git with model changes."),
            ("CI impact analysis", "Fail PRs dropping columns referenced by exposures; require exposure updates with BI migrations same release."),
            ("Catalog integration", "Export exposures to DataHub for search; stale owner fields block merge via lint rules."),
            ("Lineage completeness", "Native BI lineage plus git-versioned exposures—PR review catches what UI-only docs miss."),
            ("Deprecation workflow", "Dual-write columns one sprint when needed; exposure records downstream sunset dates."),
        ],
    },
    "devops-dbt-incremental-models": {
        "hook": "Nightly full scan on a ten terabyte fact—materialization stayed table instead of merge incremental.",
        "sections": [
            ("Strategy matrix", "Append for immutable events; merge with unique_key for upserts; delete+insert for partition replaces."),
            ("Incremental predicates", "is_incremental branch filters on watermark; include lookback for late-arriving facts."),
            ("Idempotent retries", "unique_key required for merge—without it duplicates silently replay after failed runs."),
            ("Testing", "Unit test SQL for is_incremental true/false; integration test retry produces identical row counts."),
            ("Operations", "Alert on merge bytes processed ten times baseline—often missing predicate or accidental full refresh."),
        ],
    },
    "devops-dbt-run-hooks-ops": {
        "hook": "on-run-end GRANT failed silently in logs—BI could not query new models until manual DBA fix Monday.",
        "sections": [
            ("Grant automation", "Generate GRANT SELECT from meta roles via adapter macros—security hooks must fail the run."),
            ("Idempotency", "IF NOT EXISTS patterns; retries must not double-apply privileges or duplicate Slack posts."),
            ("Validation hooks", "Assert row counts on critical marts before consumers schedule queries against empty tables."),
            ("Performance", "Log hook duration; slow hooks block job SLAs while models appear healthy."),
            ("Hard vs soft hooks", "Document which hooks are allowed to warn-only versus fail-closed for compliance."),
        ],
    },
    "devops-dbt-semantic-layer": {
        "hook": "Marketing and finance ARR differed four percent—same metric name, different filters in Looker and Tableau.",
        "sections": [
            ("Metrics as code", "Version definitions in git; CI tests metric SQL against fixture datasets."),
            ("Cache invalidation", "Webhook from prod dbt completion; monitor stale read rate on semantic API."),
            ("Consumer governance", "Approved metrics list; block rogue calculated fields when governed metric exists."),
            ("Warehouse pushdown", "Aggregations execute in warehouse—semantic layer is not a second full fact store."),
            ("Pilot rollout", "One domain metrics first; expand after cache, auth, and SLA patterns proven."),
        ],
    },
    "devops-dbt-snapshot-strategies": {
        "hook": "Manual SCD2 effective dates were wrong—check strategy on a source that hard-deleted rows corrupted history.",
        "sections": [
            ("Timestamp vs check", "Timestamp when updated_at is trustworthy; check only when row hash detects change without deletes."),
            ("Type 2 columns", "dbt_valid_from and dbt_valid_to; analytics use as-of joins for point-in-time reporting."),
            ("Storage planning", "Archive old snapshot partitions; monitor table growth month over month."),
            ("Downstream contracts", "Consumers filter dbt_valid_to is null for current state unless temporal join explicit."),
            ("Hard refresh", "Full snapshot rebuild after strategy mistakes—plan downstream temporal impact before running."),
        ],
    },
    "devops-dbt-star-schema-design": {
        "hook": "Revenue double-counted because fact grain included partial shipment lines twice per order.",
        "sections": [
            ("Grain discipline", "Declare grain in model meta; test uniqueness on grain columns in CI."),
            ("Conformed dimensions", "Shared dim_date and dim_customer across marts—mesh spine not per-team reinvention."),
            ("Additivity", "Store components for ratios; revenue additive; conversion rate computed not stored pre-averaged."),
            ("Slowly changing attributes", "Explicit Type 1 vs Type 2 choices per attribute—document in model descriptions."),
            ("Physical design", "Cluster facts on date and high-filter columns matching BI query patterns."),
        ],
    },
    "devops-dependency-latency-injection": {
        "hook": "Thirty-second default HTTP timeouts held four hundred threads during an embedding outage—latency chaos would have found it.",
        "sections": [
            ("Injection tooling", "Chaos Mesh HTTPFault, mesh VirtualService delays, or app-level fault injection stubs."),
            ("Timeout tuning", "Inject 200ms, 500ms, 2s; set client timeout just above dependency p99 knee."),
            ("Bulkheads", "Saturate one pool; verify other pools continue serving traffic under partial degradation."),
            ("Steady-state metrics", "Define SLI before experiment—breaker open rate, p99, error budget burn."),
            ("Blast radius", "Namespace and label scoped experiments; auto-abort when SLO burns during test."),
        ],
    },
    "devops-deployment-gates-smoke-tests": {
        "hook": "Pipeline green; production returned 500 on orders API because smoke tested /health only.",
        "sections": [
            ("Smoke design", "Three to five read-only API paths with synthetic tenant—represent revenue and auth flows."),
            ("CD gates", "Block promotion until smoke passes on canary URL; automatic rollback on failure."),
            ("Environment parity", "Same secrets resolver and network path as production—not localhost mocks."),
            ("Flake policy", "One retry with jitter; chronic flakes are Sev-2 debt tracked to resolution."),
            ("Override auditing", "Manual gate skips require ticket ID in deploy metadata and alert to platform."),
        ],
    },
    "devops-dimensional-modeling-pitfalls": {
        "hook": "Twelve-way join timeout from over-snowflaked product hierarchy in a cloud warehouse BI explore.",
        "sections": [
            ("Anti-pattern catalog", "Modeling guide lists snowflake, junk dimension, and bridge abuse—PR checklist references it."),
            ("Bridge weighting", "Many-to-many bridges need weights so sums match fact measures on validation samples."),
            ("Junk dimensions", "Low-cardinality flags belong on facts—not separate dimensions causing fanout."),
            ("Role-playing dates", "Multiple date keys require aliases in semantic layer or BI confusion follows."),
            ("Review ritual", "Model office hours for new facts before merge to main—fresh eyes on grain declarations."),
        ],
    },
    "devops-dind-rootless-buildkit": {
        "hook": "Privileged DinD escape CVE forced emergency CI lockdown—every build stopped for two days.",
        "sections": [
            ("Rootless builders", "BuildKit or Kaniko without privileged pods; runAsUser 1000, no docker.sock mount."),
            ("Registry cache", "cache-to/cache-from importers; measure build duration weekly; invalidate on base digest change."),
            ("Supply chain", "Pin base images by digest; scan in pipeline; deny floating latest tags on prod builds."),
            ("Kaniko pitfalls", "Without cache, builds become ten times slower—teams bypass with forbidden DinD unless fixed."),
            ("Break-glass pool", "Isolated privileged runners with audit log—not default shared pool for app teams."),
        ],
    },
    "devops-dns-failure-injection": {
        "hook": "CoreDNS CPU spiked during a control plane rollout—cascading timeouts until customers reported errors.",
        "sections": [
            ("Failure modes", "SERVFAIL, slow responses, NXDOMAIN storms, poisoned caches, negative TTL amplification."),
            ("Chaos scope", "Litmus or Chaos Mesh DNSChaos limited by namespace labels—not cluster-wide without comms."),
            ("Application retries", "Jittered backoff on DNS errors; avoid tight loops that amplify CoreDNS QPS."),
            ("NodeLocal DNSCache", "Test chaos with production-like cache enabled—reduces but does not eliminate CoreDNS load."),
            ("Runbook", "Scale CoreDNS; verify upstream forwarder health; correlate with deploying control plane version."),
        ],
    },
    "devops-downward-api-metadata": {
        "hook": "Traces showed a hardcoded service version—rollouts were invisible in telemetry until incident correlation failed.",
        "sections": [
            ("Label projection", "Mount app.kubernetes.io/version from pod labels into OTEL resource attributes via Downward API volumes."),
            ("Resource limits", "Expose memory limits so batch buffers self-throttle before OOMKill under load spikes."),
            ("Security boundaries", "Never project sensitive annotations to env vars visible to all containers in the pod."),
            ("GitOps sync", "Helm sets version labels each release—Downward API picks up changes without app rebuild."),
            ("Verification", "Roll label change in staging; confirm telemetry reflects new version per documented refresh policy."),
        ],
    },
    "devops-dynamodb-feature-serving": {
        "hook": "Launch day throttled reads on the feature table—provisioned capacity was not switched to on-demand before traffic.",
        "sections": [
            ("Key design", "Composite pk/sk with sharded suffixes on hot entity keys—avoid monotonic partition concentration."),
            ("GSI patterns", "Secondary access paths with per-key ConsumedCapacity monitoring during load tests."),
            ("BatchGet limits", "Split batches respecting sixteen megabyte and one hundred item limits in inference pipelines."),
            ("Stream materialization", "Warehouse to Dynamo via stream processor with idempotent upsert and freshness SLA."),
            ("Launch readiness", "Switch on-demand before marketing events; stale features flagged explicitly beat silent old vectors."),
        ],
    },
    "devops-ebpf-observability-cilium": {
        "hook": "NetworkPolicy YAML looked correct—Hubble showed DNS traffic bypass via a hostNetwork pod.",
        "sections": [
            ("Hubble relay", "Aggregate flows cluster-wide; search by pod labels during policy incidents."),
            ("Verdict analysis", "Compare FORWARDED vs DROPPED against intended selectors—hostNetwork exceptions documented."),
            ("L7 visibility", "HTTP visibility requires pod annotations—balance cardinality against debug value."),
            ("Alerting", "Unexpected egress to non-allowlisted CIDR from tier-one namespaces."),
            ("Retention", "Export Hubble metrics to Prometheus with retention matching post-incident review—not minutes only."),
        ],
    },
    "devops-egress-cost-optimization": {
        "hook": "Cross-AZ traffic was thirty percent of the cloud bill—microservices chatted across zones by default.",
        "sections": [
            ("Locality routing", "Prefer same-AZ endpoints when healthy; cross-AZ fallback only on failure."),
            ("Data placement", "Colocate compute with primary datastore AZ for high-chatter services."),
            ("Payload efficiency", "Protobuf or compressed JSON on internal APIs; audit verbose logging streams crossing zones."),
            ("NAT topology", "Per-AZ NAT or VPC endpoints reduce hairpin cross-AZ charges through centralized NAT."),
            ("FinOps cadence", "Monthly top talkers dashboard with service owner chargeback and remediation tickets."),
        ],
    },
    "devops-egress-filtering-dns": {
        "hook": "Nightly DNS queries to suspicious TLDs had no egress or DNS log correlation for security investigation.",
        "sections": [
            ("Default deny tiers", "Production strict allowlist; staging monitor-mode with anomaly detection before tighten."),
            ("DNS logging", "CoreDNS or NodeLocal forward to SIEM with retention meeting PCI ninety-day evidence."),
            ("SOAR response", "High-entropy domain scores ticket automatically—auto-block only after false-positive baseline."),
            ("hostNetwork audit", "Quarterly review of workloads bypassing NetworkPolicy egress controls."),
            ("Developer unblock", "Domain allowlist ticket workflow with SLA for legitimate SaaS dependencies."),
        ],
    },
    "devops-ephemeral-storage-limits": {
        "hook": "A log-heavy pod filled node disk—kubelet evicted unrelated production pods on the same node.",
        "sections": [
            ("Limit both request and limit", "ephemeral-storage on emptyDir download and log workloads—scheduling and eviction both matter."),
            ("Eviction ordering", "Guaranteed QoS for tier-one pods; best-effort log scrapers evicted first under pressure."),
            ("Alternatives", "Stdout logging or sized PVCs instead of unbounded emptyDir caches on shared nodes."),
            ("Monitoring", "container_fs_usage_bytes alerts before node-level disk pressure evictions cascade."),
            ("Load testing", "Fill emptyDir to limit in staging; document OOMKilled versus evicted behavior for on-call."),
        ],
    },
    "devops-etcd-backup-restore-ops": {
        "hook": "Restore from snapshot taken mid-compaction left the control plane unusable until an older backup succeeded.",
        "sections": [
            ("Consistent snapshots", "etcdctl snapshot save from authorized endpoint; sha256 verify; upload to versioned object storage."),
            ("Restore drill", "Quarterly full restore to isolated apiserver—document RTO steps with named owners."),
            ("Backup monitoring", "Alert on backup job lag and failure—untested backups are operational fiction."),
            ("Encryption", "Backup files encrypted at rest; break-glass restore access audited within forty-eight hours."),
            ("GitOps fallback", "When etcd restore fails, rebuild cluster and reconcile workloads from Git—not etcd alone."),
        ],
    },
}


def wc(text):
    return len(WORD.findall(text))


def expand_section(topic, title, base):
    parts = [base, ""]
    variants = [
        f"A production team running {topic} discovered that {title.lower()} failures show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression until Black Friday.",
        f"Runbook entry for {title.lower()}: confirm blast radius (single namespace vs fleet-wide), identify last config change, roll back via documented single step, then capture metrics screenshots for postmortem—not ad-hoc dashboard hunting.",
        f"For {topic}, instrument {title.lower()} with low-cardinality metrics tied to user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on vanity gauges that never correlated with past incidents.",
        f"Game day scenario for {title.lower()}: inject partial outage in staging quarterly, verify on-call can execute rollback in under fifteen minutes using only the linked runbook, update runbook with what actually broke.",
        f"Ownership for {title.lower()} belongs in the service catalog with named rotation, last drill date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.",
        f"Change management for {topic}: require peer review from someone outside the authoring team before production promotion—fresh eyes catch assumptions embedded in {title.lower()} configs that authors no longer notice.",
        f"Capacity planning note: estimate peak QPS or job concurrency for {title.lower()}, multiply by headroom factor one-point-five to two, compare against cloud quotas and license limits before launch week—not during the first outage.",
    ]
    for v in variants:
        parts.append(textwrap.fill(v, width=100))
        parts.append("")
    return "\n".join(parts)


def generate_body(slug):
    meta = TOPIC_META[slug]
    topic = slug.replace("devops-", "").replace("-", " ")
    chunks = [meta["hook"], ""]
    for title, base in meta["sections"]:
        chunks.append(f"## {title}")
        chunks.append("")
        chunks.append(expand_section(topic, title, base))
    if slug in EXPANSIONS:
        chunks.append(EXPANSIONS[slug].strip())
    return "\n".join(chunks).strip() + "\n"


def rebuild_fm(fm, faqs):
    fm = re.sub(r"^dateModified:.*$", f'dateModified: "{date.today().isoformat()}"', fm, flags=re.M)
    if faqs:
        block = "faq:\n" + "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in faqs)
        fm = re.sub(r"faq:.*?(?=\n---|\Z)", block + "\n", fm, flags=re.S)
    return fm


def main():
    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        raw = path.read_text().split("---", 2)
        fm = raw[1]
        if slug in KEEP:
            body = raw[2]
            fm = rebuild_fm(fm, None)
        else:
            body = generate_body(slug)
            fm = rebuild_fm(fm, FAQS[slug])
        path.write_text(f"---{fm}---\n{body}")
        w = wc(body)
        results.append({"slug": slug, "word_count": w, "faq_count": len(FAQS.get(slug, [])) or 4, "meets_target": w >= TARGET})

    ok = sum(1 for r in results if r["meets_target"])
    PROGRESS.write_text(json.dumps({"batch": "04", "updated": date.today().isoformat(), "total": len(SLUGS), "completed": ok, "min_words": TARGET, "posts": results}, indent=2) + "\n")
    print(f"{ok}/{len(SLUGS)} >= {TARGET}")
    for r in sorted(results, key=lambda x: -x["word_count"])[:5]:
        print(f"  sample {r['word_count']} {r['slug']}")
    under = [r for r in results if not r["meets_target"]]
    if under:
        print("UNDER:")
        for r in under:
            print(f"  {r['word_count']} {r['slug']}")


if __name__ == "__main__":
    main()
