#!/usr/bin/env python3
"""Expand batch-04 posts to >=1200 words with unique supplemental sections."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

EXPANSIONS = {
    "devops-experiment-tracking-governance": r"""

## MLflow and W&B operational differences

MLflow stores artifacts on a filesystem or object store backend tied to the tracking URI; W&B integrates cloud hosting with built-in retention tiers on paid plans. Governance patterns transfer: both need experiment naming, param scrubbing, and lifecycle jobs. MLflow's `experiments` API allows programmatic tier tagging:

```python
client.set_experiment_tag(experiment_id, "retention_tier", "production")
client.set_experiment_tag(experiment_id, "data_classification", "internal")
```

W&B teams use team projects as isolation boundaries—mirror the same prefix conventions in project names. Do not mix sandbox and production projects without access controls; W&B's shared dashboards leak params across project members by default.

## Integrating retention with model registry

The model registry is the linkage between experiment runs and production retention. When a run transitions to `Production` stage, trigger a webhook that:

1. Tags the parent experiment `tier=production`.
2. Extends artifact lifecycle on the underlying storage prefix.
3. Opens a catalog entry linking Git commit, Docker image, and run ID.

Deregistering a model should not instantly delete artifacts—grace period of 30 days allows rollback after bad deploy.

## Audit questions compliance teams ask

Prepare answers before audit season:

- Can you prove who accessed experiment metadata containing customer cohorts?
- Are deleted runs removed from backups on what schedule?
- Can a data scientist export all params to CSV without approval?

If answers involve "we don't know," fix logging and export ACLs before legal asks.

## Runbook: tracking server disk pressure

1. Identify top 10 experiments by artifact size (`du` on backend or MLflow admin API).
2. Pause new run creation if utilization > 90% (nginx 503 on tracking URI).
3. Run retention dry-run targeting `exploratory` and `ci` tiers first.
4. Page team leads for top offenders—often unbounded hyperparameter sweeps.
5. Add PVC or expand object store quota only after retention executes—otherwise growth repeats in weeks.

Disk pressure incidents are retention policy failures seen late—not capacity surprises.
""",

    "devops-external-dns-automation": r"""

## Annotation reference for application teams

Standardize Ingress annotations in your platform docs:

```yaml
metadata:
  annotations:
    external-dns.alpha.kubernetes.io/hostname: api.staging.example.com
    external-dns.alpha.kubernetes.io/ttl: "300"
    external-dns.alpha.kubernetes.io/aws-weight: "100"
```

The hostname annotation is mandatory when Ingress spec hosts differ from desired public name or when using LoadBalancer Services without Ingress rules. TTL defaults vary by provider—lower TTL during migration windows speeds rollback propagation.

## Troubleshooting reconciliation loops

ExternalDNS logs `level=info msg="All records are already up to date"` when healthy. Error patterns:

- **`AccessDenied`**: IAM policy missing `ChangeResourceRecordSets` on hosted zone ARN.
- **`Throttling`**: Route53 rate limit— increase `--interval` or request quota increase.
- **Conflicting ownership TXT**: two clusters share owner ID—fix immediately before records flap.

Use `kubectl logs -n external-dns deploy/external-dns --since=10m | grep -i error` as first incident command.

## Terraform coexistence

Many orgs manage apex MX/SPF/DKIM in Terraform while ExternalDNS manages service hostnames. Establish zone tagging: Terraform resources carry `managed-by=terraform-networking`; ExternalDNS TXT prefix `externaldns-*` proves controller ownership. Quarterly script diffs Terraform state vs Route53 vs ExternalDNS desired set—three-way drift catches manual console edits.

## Performance at scale

Clusters with 500+ Ingress objects benefit from:

- `--events` disabled if etcd watch pressure high (trade visibility).
- Sharding ExternalDNS by `--label-filter` across two deployments.
- Provider-specific batch change APIs where available.

Watch ExternalDNS CPU during mass Ingress rollout events—record updates batch but provider APIs serialize.

ExternalDNS succeeds when application teams treat DNS as declarative as Kubernetes itself—hostname in manifest, owner ID in platform runbook, deletions policy documented before first prod deploy.
""",

    "devops-fact-table-grain-design": r"""

## Slowly changing dimensions and grain

When dimension attributes change (`customer_segment` from SMB to Enterprise), grain of the fact table determines whether historical facts retroactively reflect new segment or keep original. Type 1 overwrite changes history in place—dangerous for financial facts. Type 2 dimension rows with `valid_from`/`valid_to` preserve history; fact grain stays at line level while dimension joins pick correct version by `order_date`.

Document in model catalog: "Revenue facts attach to customer segment **as of order date** via Type 2 join"—not today's segment.

## Aggregate tables vs fact grain shift

Teams accelerate dashboards with pre-aggregated tables (`daily_revenue_by_region`). These are facts with coarser grain—label them explicitly:

```sql
-- GRAIN: one row per region per calendar day
CREATE TABLE f_daily_revenue_region ...
```

Never join line-level facts to daily aggregate facts without aggregation—fan-out duplicates measures.

## dbt testing package examples

```yaml
# schema.yml
models:
  - name: f_order_lines
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [order_line_id]
    columns:
      - name: line_revenue
        tests:
          - not_null
      - name: order_id
        tests:
          - relationships:
              to: ref('d_order')
              field: order_id
```

Add custom test comparing `SUM(line_revenue)` to staging source totals within 0.01% tolerance daily.

## Facilitating analyst self-service

Publish grain and additivity in Looker `explore` descriptions or dbt exposures docs. Analysts writing ad hoc SQL skip the catalog—office hours reviewing one bad query pay for themselves when you show duplicated shipping on a board slide.

Grain design is product management for data: you are deciding what question one row answers for the next three years.
""",

    "devops-fault-injection-staging": r"""

## Choosing fault types by architecture

Map architecture components to experiment catalog:

| Component | Fault | Validates |
|-----------|-------|-----------|
| Redis cache | Latency, deny | Timeout, cache miss storm |
| PostgreSQL | Connection reset | Pool recovery, retry budget |
| Kafka | Consumer lag spike | Backpressure, DLQ |
| Upstream HTTP | 503 bursts | Circuit breaker, fallback |
| kube-dns | NXDOMAIN | Retry without tight loop |

Prioritize faults on dependencies with strict SLOs and retry-heavy clients.

## Measuring experiment value

Track **experiments run**, **hypotheses failed**, **incidents prevented** (counterfactual is hard—track regressions caught in staging before prod). Failed hypotheses are successes: they produce fix PRs before customers notice.

## Coordination with feature flags

When staging shares feature flag provider with prod, ensure chaos events do not flip prod flags—use dedicated staging LaunchDarkly environment keys in application config. Misconfigured SDK keys caused a staging chaos test to disable prod payment flow once—that belongs in game day comms checklist.

## Litmus vs Chaos Mesh selection

Litmus excels at predefined experiments with ChaosCenter UI; Chaos Mesh integrates tightly with Kubernetes scheduling and network policies. Pick one per cluster to avoid overlapping controllers fighting experiment CRDs.

Staging fault injection is insurance premium—pay it in CPU and engineer hours or pay out in prod incident multiples.
""",

    "devops-feast-online-offline-sync": r"""

## Event-time vs processing-time in streaming features

Kafka-based feature pipelines often stamp `processing_time` at consumer flush. Training labels anchored on `business_time` need explicit lag documentation:

```
expected_online_lag = processing_time - business_time (p99)
```

If p99 is 45 minutes, offline training snapshots must exclude last 45 minutes of labels or include lag as model feature. Hiding lag guarantees skew at boundary windows.

## Redis cluster sizing for Feast online store

Memory estimate:

```
memory ≈ entity_count × avg_feature_bytes × feature_views × replication_factor × 1.3 overhead
```

Review monthly as entity cardinality grows—materialization adds keys monotonically until TTL evicts. Scale vertically before horizontal sharding complexity unless Redis Cluster operations are mature in your org.

## Disaster recovery for feature stores

Backup registry to cross-region bucket versioned hourly. Offline store inherits warehouse DR. Online store rebuild strategy: rematerialize from offline after Redis region failure—document RTO as materialization duration for full entity set, not Redis restore alone.

## Coordinating with model deployment

Model promotion checklist item: "online/offline parity sample passed in last 24h." Block canary deploy if materialization lag exceeded SLA since last successful job. Models are only as fresh as features—they do not drift independently of feature lag.

Training-serving consistency is a joint SLA between data platform and ML engineering—put it in writing with numeric thresholds, not Slack goodwill.
""",

    "devops-feature-flag-cd-integration": r"""

## Provider comparison for CD integration

| Provider | Strength | CD integration pattern |
|----------|----------|------------------------|
| LaunchDarkly | Mature SDKs, audit | Terraform flags + API audit in pipeline |
| Unleash | Self-hosted option | Admin API + unleash-server in cluster |
| Flagsmith | Open source | Environment keys per stage in deploy |

All support server-side SDK keys as Kubernetes Secrets synced by ESO—rotate keys without redeploying app when provider allows dual-active keys.

## Org-scale flag taxonomy

Prefix flags by domain: `checkout.new_payment_flow`, `recs.model_v4_shadow`. Reject PRs adding unprefixed keys in shared monorepos—grep CI catches `flags.set("darkMode"` without owner prefix.

## Incident response with flags

Runbook order during bad deploy:

1. Disable exposure flag (seconds).
2. Scale previous Deployment if needed (minutes).
3. Git revert (minutes to tens of minutes).

Train on-call on provider UI path—OAuth login failures during incident are common if SSO only documented for engineers.

## Measuring flag health

Metrics: `flag_stale_count`, `flag_enabled_prod_count`, `flag_change_events`. Dashboard per team quarterly review—teams with >20 stale flags lose merge privileges until cleanup sprint completes (political but effective).

Flags in CD pipelines connect product velocity to operational safety—only when cleanup is enforced as deploy is.
""",

    "devops-feature-store-backfill": r"""

## Incremental vs full backfill decision tree

- **New FeatureView, empty online store**: full offline backfill then batched materialize.
- **Logic fix mid-quarter**: dual-write versioned columns; offline recompute partition only for affected date range.
- **New entity type added**: backfill entity dimension table first; verify join keys before feature computation.

## Warehouse cost control during backfill

BigQuery slot consumption spikes on full-table scans—reserve slots or schedule backfill off-peak. Use partitioned inserts aligned to warehouse partition keys to avoid expensive cross-partition shuffles.

## Communicating backfill status

Public dashboard for ML consumers:

| Feature | Offline complete % | Online complete % | ETA |
|---------|-------------------|-------------------|-----|

Reduces Slack "is it done yet" during multi-day backfills.

## Legal and retention during backfill

Backfilling historical windows may reprocess data subjects who requested deletion—verify retention policies and legal holds before recomputing PII-derived features across multi-year spans.

Backfill is a project, not a job—a project with load tests, checkpoints, and a communication channel.
""",

    "devops-feature-store-feast": r"""

## High availability patterns

Run Redis Sentinel or Cluster for online store; registry on versioned S3 with cross-region replication. Materialization jobs `concurrencyPolicy: Forbid` prevents dueling writers. Inference pods mount feature repo via init container git-sync or baked ConfigMap for read-only FeatureView definitions—avoid writable repos in serving path.

## Multi-environment promotion

```
dev feature repo → staging apply → prod apply (manual approval)
```

Same Git flow as application code. Never `feast apply` prod from laptop without PR—registry drift starts there.

## Feast UI and developer experience

Feast UI helps discover FeatureViews—not a substitute for DataHub lineage. Deploy UI read-only behind SSO for data scientists; disable apply from UI in prod entirely.

## Cost line items

Feast operational cost = Redis memory + warehouse query slots for materialization + engineer maintenance. Showback Redis memory by `feature_view` key prefix if Redis supports key tracking—helps chargeback conversations with ML teams.

Operating Feast is operating a database whose clients are models—availability and freshness SLAs belong in the same tier list as OLTP dependencies.
""",

    "devops-feature-store-governance": r"""

## Feature lifecycle states

```
proposed → experimental → stable → deprecated → retired
```

Transitions require catalog tickets. Experimental features live max 90 days without promotion or deprecation—automated report names owners who miss deadline.

## Conflict resolution when definitions disagree

Two teams define `user_txn_count_7d` differently—catalog shows both; serving namespace collision breaks inference. Platform council picks canonical definition or forces rename (`user_txn_count_7d_recs` vs `_fraud`). Technical merge is rarely possible without retraining all consumers.

## Legal and privacy reviews

Features derived from GDPR-covered attributes need DPIA references in catalog. Block `feast apply` prod for FeatureViews tagged `pii=raw` without exception approval—Gatekeeper on Git push or CI policy check.

## Incentives for ownership

Teams owning stable tier-1 features get priority platform support; teams ignoring SLA breaches get features frozen at deprecated until remediation—carrot and stick beats voluntary ownership slides.

Governance converts "who broke the feature store" into "who fixes it by Friday."
""",

    "devops-feature-store-materialization": r"""

## Partitioning large materializations

For billion-row FeatureViews, partition materialization by `entity_id % N` or geographic shard—parallel jobs with disjoint entity ranges merge cleanly in online store. Document maximum safe parallelism from Redis write load tests.

## Dependency management

Materialization DAG in Airflow should include upstream data quality tasks—Great Expectations suite pass on source partition before Feast job triggers. Prevents materializing garbage after silent upstream schema drop.

## Version skew during materialization deploy

Rolling out new materialization container version while jobs run—use Kubernetes job completion before deploying new image, or feature flag new transformation logic inside job reading from Git tag.

## Handoff to on-call

Runbook one-pager: "Materialization red" → check Airflow sensor, warehouse lag, Redis memory, recent feature repo merge. Link Grafana dashboard with lag and row count panels—on-call should not grep logs first.

Materialization is the cron job that matters—treat missed runs like missed payroll.
""",

    "devops-feature-store-monitoring": r"""

## Alert routing

Tier-1 feature alerts page ML platform and consumer model on-call jointly—data bugs and model bugs look identical in prediction drift. Tier-2 alerts ticket producer team only.

## Baseline selection for drift

Training baseline window should represent production traffic mix—seasonal retail models need quarterly baseline refresh, not one static histogram from January.

## Cost of monitoring

Statistical profiling on full offline tables is expensive—sample 1% entities stratified by region for nightly profile; full scan weekly.

## Integration with incident management

PagerDuty service `feature-store` linked to runbooks per FeatureView—reduces MTTR when on-call is generic platform rotation unfamiliar with fraud vs recs features.

Monitoring features costs compute—it costs less than shipping null-heavy vectors to production payment models.
""",

    "devops-feature-store-point-in-time": r"""

## AS OF joins in warehouses without Feast

Teams on Snowflake/BigQuery can validate Feast output using native AS OF joins—build confidence during Feast migration before decommissioning legacy SQL feature pipelines.

## Time travel table formats

Iceberg/Delta time travel enables reproducing offline store at historical snapshot—useful for debugging leakage accusations months later. Align Feast offline store snapshot strategy with table format capabilities.

## Edge cases: timezone boundaries

Global products with labels at local midnight but UTC warehouse storage create leakage at zone boundaries—standardize on UTC in entity_df or explicit `timezone` column in join logic. Document for every consumer market.

## Education for data scientists

Mandatory onboarding module: 30-minute lab proving leakage with intentional bug—fixes stick better than policy PDF.

Point-in-time correctness is cultural before it is technical—Feast encodes rules engineers must still understand when writing raw SQL escapes.
""",

    "devops-feature-store-schema-evolution": r"""

## Cross-team communication templates

Schema change announcement minimum: impact summary, consumer actions, timeline, rollback. Post to catalog webhook and Slack—email optional, Slack mandatory.

## Automated consumer detection

Graph registry dependencies: which training pipelines import FeatureView schema hash—block deprecation until hash count zero in last 30 days of pipeline runs.

## Emergency rollback

Keep previous FeatureView version materializing in parallel during risky changes—serving flag flips in seconds without redeploy if vector mapping supports both.

Schema evolution rewards pessimism—assume something breaks in inference at 2 a.m.; design parallel paths until proven safe.
""",

    "devops-finops-showback-chargeback": r"""

## Negotiating shared costs with finance

Finance may demand precise allocation impossible without transaction-level metering—propose phased maturity: (1) namespace showback, (2) label refinement, (3) chargeback with dispute process. Perfect allocation delayed beats political chargeback on day one.

## Kubernetes-specific gotchas

Init containers, sidecars, and DaemonSets consume cluster resources—allocate DaemonSet cost evenly or by node affinity labels. Ephemeral storage overages surprise teams—include in reports when CSI metrics available.

## Multi-cloud normalization

Kubecost normalizes SKUs across clouds for single dashboard—useful for acquisitions running GKE and EKS simultaneously. Document exchange rate assumptions if showing global exec single currency view.

## Behavior change stories

Showback works when teams act: right-sizing request after seeing idle cost, deleting orphaned namespaces, choosing spot for batch. Publish monthly "saved $" from optimizations—positive reinforcement beats shame-only reports.

FinOps maturity is a staircase—labels, showback, optimization, chargeback—in that order unless you enjoy budget meetings without data.
""",

    "devops-flux-helm-controller": r"""

## Testing HelmRelease changes

Render locally: `flux build helmrelease` patterns or `helm template` with equivalent values. CI kubeconform validation on rendered manifests catches invalid enums before merge.

## Multi-namespace releases

HelmRelease `targetNamespace` vs release namespace—chart hooks running in wrong namespace cause subtle failures. Document where Helm stores release secrets (`sh.helm.release.v1.*` in target namespace).

## Coordination with image automation

HelmRelease values image tags updated by ImageUpdateAutomation setters—ensure chart templates reference `.Values.image.tag` not hardcoded digest in templates platform does not control.

## helm-controller scaling

Large fleets: increase `--concurrent` reconciles carefully—too high overwhelms API server during mass upgrade events. Stagger HelmRelease intervals (`interval: 5m` with random offset) avoids thundering herd.

HelmRelease operational maturity is knowing reconciliation is continuous—not an upgrade button you press once.
""",

    "devops-flux-image-automation": r"""

## Signing and verification

Cosign sign images in CI; admission policy verifies signature before deploy—image automation only promotes signed tags matching policy. Prevents registry compromise pushing malicious digest that automation obediently commits.

## Monorepo setter markers

Multiple images in one repo need distinct `$imagepolicy` comments—CI lint validates marker uniqueness and matching ImagePolicy names exist.

## Observability for automation lag

Metric: time from CI push to Git commit from automation to Flux deploy—SLA for "idea to prod" narratives. Breakdown isolates slow registry scan vs slow Git push vs slow reconcile.

Image automation removes toil until policy is too loose—then it removes reproducibility. Semver ranges are production contracts.
""",

    "devops-game-day-planning": r"""

## Customer communication templates

Pre-write status page text: "We are conducting planned resilience testing. No customer impact expected." Legal review once, reuse quarterly. Update only dates and contact info day-of.

## Blameless culture enforcement

Executives attend retrospective without assigning individual blame—game days fail culturally if first question is "who clicked kill pod."

## Combining with compliance exercises

SOC2 and ISO auditors appreciate game day evidence—store hypothesis results, abort criteria, and observer sign-offs as audit artifacts. Chaos engineering becomes compliance asset with paperwork discipline.

## Scaling game days across regions

Run regional game days staggered—global simultaneous chaos overlaps on-call handoffs badly. Coordinate via central calendar with regional owners.

Game days compound—each quarter builds muscle memory so real incidents feel familiar, not novel panic.
""",

    "devops-gateway-api-httproute-canary": r"""

## Session affinity and canaries

Sticky sessions route returning users to same backend version—canary weight metrics skew if affinity ignores weights. Verify controller behavior or disable affinity during canary window.

## gRPC and TCPRoute canaries

HTTPRoute patterns extend to GRPCRoute with weighted backendRefs where implementation supports—inventory gRPC services separately during Gateway API migration; don't assume HTTP canary config copies verbatim.

## Security policy attachment

Gateway API ReferenceGrant controls cross-namespace backend access—canary Service in namespace B needs ReferenceGrant from HTTPRoute namespace A. Missing grant shows as 403, misdiagnosed as canary weight bug.

Canary traffic splitting is observability exercise—weigh errors separately per backendRef or you fly blind at 10% traffic.
""",

    "devops-gateway-api-migration": r"""

## Training platform teams

Two-hour workshop: Gateway, HTTPRoute, ReferenceGrant, TLS listener—hands-on lab deploying ping service. Migration velocity depends on app team confidence, not platform enthusiasm.

## Vendor controller upgrades

Gateway API CRD version bumps require controller upgrade ordering—upgrade controller before applying v1 HTTPRoute manifests cluster-wide. Check release notes for deprecated v1beta1 removal dates.

## Cost of dual stack

Two load balancers during migration doubles ingress cost briefly—finance heads-up prevents mid-migration cost panic. Typically 2–6 weeks dual stack.

Migration completes when Ingress objects count zero in prod clusters—not when platform declares victory in slide deck.
""",

    "devops-github-actions-reusable-workflows": r"""

## GHES version compatibility

Verify `workflow_call`, `secrets: inherit`, and reusable workflow nesting depth on your GitHub Enterprise Server version—older GHES lacks features assumed in platform docs.

## Billing implications

Reusable workflows still consume minutes on caller repo billing—central platform repo minutes plus consumer minutes for duplicate checkout steps if not cached. Shared artifact cache strategy reduces duplicate `npm ci` cost.

## Security review for third-party actions inside reusable workflows

Pin actions to SHA in platform repo—consumers inherit pinned versions without pinning themselves. Supply chain compromise in `actions/checkout@v4` tag affects all consumers—platform team monitors Dependabot for actions too.

## Deprecation process

Six-month notice, `@v1` frozen except critical CVE patches, migration guide with diff examples. Deleting workflow without deprecation breaks CI silently on next run—archive with redirect message job first.

Platform CI via reusable workflows scales trust—consumers trust platform semver more than they trust themselves copying YAML.
""",

    "devops-gitlab-ci-child-pipelines": r"""

## include:local vs remote triggers

Child pipeline YAML can live in same repo (`include: local`) or separate CI config repo—central CI repo versioned tags help platform teams like reusable workflows. Monorepo prefers colocated `services/foo/.gitlab-ci.yml` changed alongside code.

## Pipeline badges and visibility

Parent pipeline badge in README should link to latest default branch pipeline—child failures visible to service owners without navigating monorepo root pipeline graph confusion.

## Merge request pipelines

Rules must trigger child on MR when service paths change—`rules: changes` with `merge_request_event` source. Missing MR trigger merges broken code that main branch child would catch.

Child pipelines are organizational boundary—service team owns child YAML even in monorepo; platform owns parent trigger patterns and resource_group conventions.
""",

    "devops-gitops-disaster-recovery": r"""

## Testing without production risk

DR rebuild target: isolated AWS account `dr-sandbox` quarterly—never first drill in prod account under pressure. Terraform workspace `dr` duplicates modules with scaled-down node counts.

## Secrets recovery hierarchy

1. Vault HA cluster (primary)
2. Sealed secrets backup keys in HSM
3. Break-glass SOPS age keys in physical safe

Document key ceremony—who can access HSM vs who approves bootstrap.

## Communication during DR

Status page internal-only mode updates for employees during rebuild—customer-facing page only if customer-visible services actually impaired. GitOps DR often invisible to customers if multi-region still serves—communicate internally anyway to stop duplicate incident bridges.

DR confidence is binary until tested—you either rebuilt this quarter or you have a hypothesis.
""",

    "devops-gitops-drift-detection": r"""

## Comparison with mutating admission

OPA/Gatekeeper denies non-compliant creates; GitOps self-heal reverts compliant-but-manual edits. Together: prevent bad config at door, revert good config drift inside house.

## Flux vs Argo drift UX

Argo CD UI diff familiar to app teams; Flux relies on `flux diff` CLI and notifications—invest in Slack integration templates so Flux shops do not lose visibility advantage.

## Historical drift analytics

Track drift events per namespace monthly—namespaces with chronic drift need better Git self-service or training, not louder self-heal surprises.

Drift is feedback that Git is not the path of least resistance—fix friction, not just revert harder.
""",

    "devops-gitops-helm-kustomize-hybrid": r"""

## Local dev parity

Developers run `kustomize build --enable-helm` locally matching CI—document helm version pin in CONTRIBUTING.md. "Works in CI only" erodes trust in hybrid pattern.

## Binary artifacts in Git

Some teams render helmCharts output to committed manifests for air-gapped clusters—trade dynamic build for auditable static YAML. Regenerate via CI bot on chart bump PRs.

## Licensing and chart provenance

Verify chart repo license and supply chain—helmCharts pulls from remote repos; compromised chart mirror is organizational risk. Allowlist chart repos in CI policy.

Hybrid repos fail when teams fight over who patches what—platform owns chart version, app team owns overlay patches, argument ends at CODEOWNERS file.
""",

    "devops-gitops-multi-cluster": r"""

## Cluster registration security

Argo CD cluster secrets contain bearer tokens—rotate on schedule, restrict who can add clusters to Argo CD project. Compromised cluster registration pushes malicious Application to hub—treat hub as tier-0 security asset.

## Fleet-wide config changes

Global ConfigMap change (DNS resolver) needs ApplicationSet rolling update strategy—sync wave ordering ensures platform components before apps. Document waves in README.

## Cost of hub-spoke Argo CD

Single hub managing 50 clusters concentrates failure—hub outage blocks visibility and sync, though workloads keep running. Run hub in HA mode with etcd backup matching DR runbook.

## Federation vs GitOps

Some teams confuse multi-cluster service mesh federation with GitOps fleet—orthogonal concerns. ApplicationSet deploys manifests; mesh handles traffic between clusters post-deploy.

Fleet GitOps scales when every cluster knows its lane—path, label, and promotion PR—not when one ApplicationSet heroically manages everything everywhere.
""",
}


EXPANSIONS2 = {
    "devops-experiment-tracking-governance": r"""

## Cross-team negotiation on retention tiers

Finance wants seven-year artifact retention for all ML experiments because models touch revenue recognition. Engineering wants seven-day retention for CI smoke tests because disk costs scale linearly with engineer count times commit frequency. The workable policy assigns tiers by registry stage and experiment tags—not by loudest stakeholder. Document tier assignment in a one-page policy PDF linked from the MLflow UI banner so data scientists see rules before clicking Run.

Quarterly tier review catches experiments miscategorized as production when no model ever registered—often 15–20% of storage in mature orgs. Automated reports listing experiments with `tier=production` but no registry model older than 90 days trigger cleanup tickets.

## Instrumentation for governance metrics

Export Prometheus metrics from retention jobs: `mlflow_retention_runs_archived_total`, `mlflow_retention_bytes_freed`, `mlflow_retention_job_failures`. Grafana dashboard panel showing artifact growth rate week-over-week—inflection points precede disk incidents by two to three weeks when teams onboard new computer vision project dumping PNG artifacts in params.

## Vendor-specific notes

Weights & Biases `delete_runs` API requires admin key—audit who holds it. MLflow open source needs custom scripts for bulk delete; commercial Databricks MLflow adds workspace admin policies. Regardless of vendor, param export for legal hold must preserve run ID linkage without exporting forbidden PII fields—legal hold is not exemption from scrubbing laws.

Governance maturity model: (1) naming CI, (2) retention tiers, (3) PII scrubbing, (4) chargeback by team, (5) automated compliance reports. Most orgs stall at step two until first disk incident—plan step two before the incident, not during.
""",

    "devops-external-dns-automation": r"""

## PrivateLink and internal DNS patterns

Services exposed only via AWS PrivateLink still need DNS names resolvable inside corporate network. ExternalDNS can manage private hosted zones associated with VPC—separate controller deployment with `--aws-zone-type=private` and `--domain-filter=internal.example.com`. Do not run public and private controllers with same owner ID against overlapping logical names—split IDs per zone class.

## Testing ExternalDNS changes safely

Before enabling sync policy on new cluster, run ExternalDNS with `--dry-run` or `--policy=upsert-only` and compare desired records JSON against Route53 inventory script output. Include negative tests: delete Ingress in staging, verify upsert-only does not delete, verify sync deletes only owned TXT-marked records.

## Edge cases with wildcard Ingress

Wildcard hostnames (`*.apps.example.com`) produce wildcard DNS records—not all providers handle them identically. Document whether your ExternalDNS version creates `*.apps` or per-host records from individual Ingress objects. Mixed behavior breaks cert-manager HTTP-01 challenges when unexpected wildcard shadows specific host.

Platform networking team should review ExternalDNS PRs changing domain-filter or owner ID with same rigor as firewall rule changes—both are perimeter controls.
""",

    "devops-fact-table-grain-design": r"""

## Bridge tables and many-to-many grain

Promotions applied unpredictably to subset of order lines need bridge table `f_order_line_promotion` at grain `(order_line_id, promotion_id)`—not promotion columns duplicated on line fact. Analysts joining line fact to promotion dimension without bridge double-count revenue when one line carries three promotions.

## Factless facts and measureless fact tables

Event tracking sometimes uses factless fact tables recording `(customer_id, event_type_id, date_key)` without numeric measure—grain is one row per event. Semi-additive rules still apply when counting events across time versus distinct customers across time. Document count distinct semantics in semantic layer.

## Historical restatements

Source systems restate revenue after returns—grain decision includes whether fact rows update in place (Type 1) or append adjustment rows (Type 3 incremental). Finance usually demands adjustment rows preserving original report numbers—model separate `f_order_lines` immutable insert and `f_order_adjustments` at grain `(order_line_id, adjustment_seq)`.

Warehouse design reviews without grain sentence on whiteboard should end early—schedule follow-up when author can articulate one row equals what.
""",

    "devops-fault-injection-staging": r"""

## Building organizational buy-in

Staging chaos fails when product managers fear delayed releases. Frame fault injection as release gate reducing prod incidents—show incident count before/after continuous staging chaos program. One prevented Sev-1 pays for quarters of engineer time building Litmus schedules.

## Data setup for realistic failures

Anonymized prod snapshot refresh weekly beats synthetic generators for cardinality surprises—index bloat and slow queries appear only with real skew. Mask PII during copy; preserve join key distribution and null rates.

## Recording experiment results

Store chaos experiment outcomes in git `chaos/results/2026-Q2-redis-latency.md` with hypothesis, graphs screenshot links, pass/fail. Audit trail for regulators asking how you validate resilience—game days and automated staging chaos both count with documentation.

Resilience is a habit measured in experiments per month, not declarations in architecture diagrams.
""",

    "devops-feast-online-offline-sync": r"""

## Contract testing between producers and consumers

Define protobuf or JSON schema for feature vectors at serving boundary—consumer contract tests validate producer materialization output matches schema nightly. Feast schema alone insufficient when inference code flattens nested structures differently than training dataframe export.

## Handling entity cold start

New entities appear in online store after first materialization window—serving must default sensibly when `get_online_features` returns nulls. Training excludes cold start period or imputes—document mismatch until backfill completes for new merchant onboarding burst.

## Multi-region Feast

Materialization per region from regional warehouse partition reduces cross-region warehouse egress. Online Redis per region—avoid single global Redis unless latency SLO allows and conflict resolution for concurrent materialization is solved.

Sync SLAs multiply by region count—central platform dashboard aggregates regional lag with worst-region highlighting for global model deployments.
""",

    "devops-feature-flag-cd-integration": r"""

## OpenFeature and vendor abstraction

OpenFeature SDK abstraction allows swapping flag providers without code rewrite—platform teams wrap provider in internal library enforcing audit logging on every evaluation in prod. CD pipelines validate OpenFeature hook registration in staging before prod deploy.

## Flag-driven database migrations

Expand-contract migrations gated by flags need careful ordering: deploy code reading both columns, backfill, enable flag, remove old column in later deploy. CD pipeline stages must enforce sequence—feature flag off during dual-read phase prevents partial migration states.

## Audit requirements

SOC2 often asks for flag change history—export LaunchDarkly audit log to immutable S3 daily. Tie flag change ticket ID in commit message when automation enables prod flags.

Decouple deploy from release only when release lever is observable, reversible, and owned—flags without audit trail are shadow deploys with extra steps.
""",

    "devops-feature-store-backfill": r"""

## Parallelism and warehouse locks

Parallel backfill jobs on same partition cause lock contention in Snowflake—serialize by partition key or use warehouse multi-cluster with job queue. Monitor warehouse credit burn during backfill weekends—FinOps surprise follows unbounded parallelism.

## Validation sampling

After backfill, stratified sample 0.01% entities across regions compare offline vs recomputed ad hoc SQL—catches systematic formula bugs missed by row count checks alone.

## User communication

When backfill delays model launch, status page internal message with ETA reduces parallel Slack pings to data platform—communication is operational requirement not optional nicety.

Backfill projects succeed with checkpoints, load tests, and explicit done criteria—not heroics on single threaded script overnight.
""",

    "devops-feature-store-feast": r"""

## Security hardening

Feast registry bucket encryption at rest with KMS; inference service account read-only on registry path; materialization write scoped to job role only. Redis AUTH and TLS in transit mandatory for prod—feature vectors are sensitive inference inputs.

## Performance tuning

Batch `get_online_features` for inference micro-batching—single entity lookup per request wastes Redis round trips. Benchmark batch size 32 vs 128 for your feature width—latency trough varies by payload size.

## Upgrade testing matrix

Maintain compatibility table Feast SDK version × Python version × Redis version validated in CI—upgrade one axis at a time in staging. Registry format changes rare but catastrophic when skipped in release notes.

Feast ops checklist: registry backup daily, materialization alerts wired, SDK pins documented, parity job green—four greens before declaring production ready.
""",

    "devops-feature-store-governance": r"""

## Onboarding new teams

Feature store onboarding kit: template FeatureView PR, SLA worksheet, catalog entry template, example materialization job. Self-service without kit produces inconsistent tags and missing owners—platform debt accumulates invisible until incident.

## Metrics for governance health

Track `% FeatureViews with owner tag`, `% deprecated views past removal date`, mean SLA breach count per team. Executive dashboard quarterly—teams below threshold get platform pairing sprint not punishment.

## Integration with model risk management

Regulated banks map features to model risk inventory—catalog export feeds GRC tool with owner and validation status. Manual spreadsheet sync fails audit; automate webhook on `feast apply` prod merge.

Ownership without enforcement is suggestion—CI gates and SLA metrics convert policy into behavior.
""",

    "devops-feature-store-materialization": r"""

## Dead letter handling

Materialization failures after partial window write leave online store inconsistent—job must record last successful watermark and refuse to advance on failure without explicit override. Override requires ticket ID logged in job annotation for audit.

## Seasonality adjustments

Black Friday multiplies entity update rate tenfold—pre-scale Redis and materialization job CPU two weeks ahead; revert scale-down after Cyber Monday. Historical metrics year-over-year predict needed headroom.

## Developer local testing

`feast materialize` against dev registry and local Redis stack—document docker-compose for data scientists validating FeatureView before prod PR. Reduces prod-only surprise failures.

Materialization operations excellence is boring repetition: sensors, metrics, locks, runbooks—excitement means something broke.
""",

    "devops-feature-store-monitoring": r"""

## Anomaly detection on job duration

Sudden 50% drop in materialization duration often means empty source partition—not success. Alert on duration anomaly in both directions. Row count zero is hard failure; row count 10% below median is soft investigation ticket.

## Feature importance linkage

When SHAP shows sudden feature importance collapse, cross-check feature null rate dashboard—common joint signature of upstream feed failure.

## Post-incident feature reviews

After prod model incident, add monitoring if missing—blameless review asks "what metric would have caught this 24h earlier?" not only "who merged bad SQL."

Feature monitoring maturity correlates with model incident frequency—teams with dashboards rarely fly blind twice on same failure mode.
""",

    "devops-feature-store-point-in-time": r"""

## Workshop exercises for teams

Hands-on lab: inject deliberate leakage via future-dated join, show AUC inflation, fix with correct timestamp filter—participants remember lab better than policy wiki. Repeat annually as onboarding refresher.

## Late label arrival

Labels arrive days after events—training snapshot must exclude recent label window or accept label revision pipeline. Document label finalization SLA alongside feature freshness SLA—both define trainable dataset boundary.

## Feast performance for large historical pulls

`get_historical_features` on billion-row entity sets needs chunked entity_df batches—memory exhaustion in training pipeline masquerades as leakage bug when job OOM kills mid-join.

Temporal correctness plus operational chunking—both required for production training pipelines at scale.
""",

    "devops-feature-store-schema-evolution": r"""

## Column semantics documentation

Schema change PR must update human-readable column docstring in FeatureView—`risk_score` unit, bounds, meaning of zero vs null. Inference bugs often trace to engineer assuming zero default safe when zero means highest risk tier.

## Simulation before prod apply

Replay yesterday's entity sample through new schema transformation in staging—compare output distribution KL divergence vs production schema. Threshold breach blocks prod apply automatically in CI pipeline.

## Coordination with embedding stores

Vector features version separately from tabular—embedding model version bump is schema change requiring retrain even if column names unchanged. Link embedding artifact version in catalog metadata field.

Schema evolution discipline separates mature ML platforms from notebook collections pretending to be infrastructure.
""",

    "devops-finops-showback-chargeback": r"""

## Executive narrative

Translate Kubernetes showback into business terms: cost per customer transaction, cost per model inference million—finance understands unit economics not milli-CPU. Monthly email to VPs with top delta drivers and recommended actions beats raw Grafana links.

## Anomaly detection on spend

Alert when namespace cost 3× weekly median—often orphaned load test namespace left running GPU nodes. Automated `kubectl delete namespace` never—ticket owner with 48h cleanup deadline first.

## Sustainability angle

Idle capacity carbon reporting increasingly requested by ESG committees—idle node share metric from OpenCost supports corporate sustainability report footnote on cloud efficiency initiatives.

FinOps succeeds when engineers change behavior without finance in every standup—visibility plus fair allocation plus easy rightsizing beats mandate from CFO alone.
""",

    "devops-flux-helm-controller": r"""

## Helm test hooks in GitOps

Charts with `helm test` pods need manual or CI-triggered test job post-sync—helm-controller does not run tests by default. Document which releases require post-sync test Job in runbook—payments chart yes, internal debug chart no.

## Values drift from external sources

ValuesFrom Secret updates trigger reconcile—ensure ESO rotation does not restart entire release unnecessarily; use checksum annotation pattern selectively to avoid thundering herd pod restarts on unrelated secret key rotation.

## Fleet partitioning

Shard helm-controller responsibility by namespace prefix or dedicated helm-controller instances for platform vs tenant charts—isolates blast when one bad chart template loops CrashBackOff on upgrade.

HelmRelease mastery is reading status conditions fluently during incident—`Stalled`, `Remediated`, `FetchFailed` each different playbooks.
""",

    "devops-flux-image-automation": r"""

## Air-gapped registries

ImageRepository with insecure registry or cert pinned for on-prem Harbor—document CA trust bundle in helm-controller and image-reflector-controller mounts. Automation fails silently on TLS verify error until logs checked.

## Multiple policies per repository

Separate ImagePolicy for staging (allows rc tags) vs prod (semver strict)—same ImageRepository, different policies, different ImageUpdateAutomation paths writing to different Git directories.

## Rollback via Git revert

Fastest rollback image automation incident: revert automation commit on main—Flux deploys previous digest within reconcile interval. Keep revert runbook one command not hunting previous tag in registry UI under stress.

Automation trust equals semver discipline plus PR review on prod paths—machines commit; humans still accountable for policy range.
""",

    "devops-game-day-planning": r"""

## Regulatory and contractual notifications

B2B contracts sometimes require advance notice of testing affecting shared infrastructure—legal template email 72h before prod game day when multi-tenant dependencies exist. Missing notification clause burns partner trust worse than brief latency blip.

## Diversity of scenarios

Rotate scenarios: dependency failure, operator error simulation (misconfigure flag), data corruption dry-run with restore—resilience beyond infrastructure includes human and data paths.

## Measuring game day ROI

Track action items closed vs opened, incidents in following quarter related to untested paths—builds budget case for chaos program headcount.

Game days are organizational muscle—skip quarters and confidence atrophies like untested backup tapes.
""",

    "devops-gateway-api-httproute-canary": r"""

## Mutual TLS and canary

When Gateway terminates mTLS, canary backends must present valid certs trusted by Gateway—certificate mismatch surfaces only on canary weight non-zero. Include cert validation in staging canary rehearsal.

## External traffic vs mesh traffic

East-west canary via service mesh differs from north-south Gateway canary—document which layer owns weight changes for hybrid mesh+Gateway deployments to avoid double-splitting traffic mathematically wrong.

## Load test during canary

Synthetic load during 50/50 split validates backend capacity at combined QPS—canary version undersized causes errors misread as code regression. Scale v2 replicas before weight increase not after errors appear.

Canary is capacity test disguised as deployment strategy—weight without headroom is wishful thinking.
""",

    "devops-gateway-api-migration": r"""

## Partner and vendor coordination

Third-party webhooks whitelisting old Ingress IP require lead time—inventory external integrations before migration cutover. Payment provider callback URL IP allowlist updates lag DNS by days sometimes.

## Documentation debt

Maintain migration runbook per hostname: current Ingress name, target HTTPRoute name, owner team, cutover date, rollback DNS steps—wiki table updated weekly during program not after incident.

## Post-migration cleanup

Delete orphaned cloud load balancers from old Ingress controller—FinOps ghost charges accumulate when LB forgotten after DNS moved. Terraform destroy or cloud console audit month after migration wave.

Migration done when Ingress count zero and finance confirms old LB decommissioned—not merely when HTTPRoute applies clean.
""",

    "devops-github-actions-reusable-workflows": r"""

## Organization permissions

`workflow_call` across private repos requires org setting allowing access—document enable path for new repos onboarding to platform workflows. Failed first CI with opaque "workflow not found" wastes half-day commonly.

## Caching strategy

Centralize cache keys in reusable workflow—`cache: npm-${{ hashFiles('**/package-lock.json') }}`—consumers inherit cache benefit without duplicating config. Document cache eviction when platform rotates Node version major.

## Breaking change communication

Platform Slack channel `#ci-platform`, subscribe all tech leads—post before merging breaking reusable workflow major. Include consumer repo grep results showing affected count.

Reusable workflows compound leverage and blast radius—semver and comms are not optional politeness they are availability controls.
""",

    "devops-gitlab-ci-child-pipelines": r"""

## Pipeline duration metrics

Track p50/p95 parent+child duration per service path—justifies further split or hardware upgrade. Monorepo critics need data showing 12m p95 vs previous 90m or skepticism returns each reorg.

## Security scanning placement

Container scan and SAST in child pipeline before deploy—parent never skips security because child omitted stage. Platform template child includes mandatory security jobs non-overridable via `rules: never` guard.

## Fail fast on shared steps

Lint monorepo-wide in parent once; service-specific test in child—avoid duplicating expensive lint N times unless lint rules path-scoped per service requires duplication.

Child pipelines encode monorepo sociology in YAML—boundaries teams negotiate in architecture reviews should appear as trigger path rules and resource groups.
""",

    "devops-gitops-disaster-recovery": r"""

## Immutable infrastructure alignment

GitOps DR assumes nodes are cattle—stateful sets with local PV require separate DR playbook section. Document which apps violate pure GitOps recovery and need Velero volume restore or database PITR outside Kubernetes.

## Cross-functional drill participants

Include security (verify break-glass access works), finance (verify billing during DR account), legal (data residency when rebuilding region)—tech-only drill misses blockers appearing hour six of real event.

## Documentation location

Runbook URL in PagerDuty service default—on-call at 3am opens phone browser not Confluence search. Offline PDF export for total network loss scenario exercise annually.

DR readiness is measured in last successful rebuild date—not confidence expressed in roadmap slides.
""",

    "devops-gitops-drift-detection": r"""

## HPA and Git replica fields

Standard pattern: remove replicas from Git Deployment manifest entirely when HPA enabled—Git no longer declares replicas, HPA owns field, drift on replicas impossible. Alternatively ignoreDifferences on replicas with documented choice—pick one org-wide.

## Terraform vs GitOps boundary

Terraform manages cloud LB; GitOps manages in-cluster Deployment—drift in Terraform not visible to Argo CD. Joint drift review monthly combining cloud audit and Argo OutOfSync list.

## Training kubectl users

Engineers taught kubectl scale during onboarding must learn suspend annotation same day—habit without GitOps context creates drift whack-a-mole.

Effective drift strategy aligns human break-glass, automated heal, and alert visibility—any leg missing teaches wrong lesson.
""",

    "devops-gitops-helm-kustomize-hybrid": r"""

## Review ownership

CODEOWNERS: platform owns base helmCharts version bumps; app team owns overlay patches—PR requires both approvals when bump affects resource limits touching app SLO. Prevents platform upgrading Redis major without app acknowledgment.

## Render diff in PR

CI posts rendered manifest diff comment on helmCharts version bump PR—reviewers see CRD changes before merge. CRD upgrades need sequential apply waves documented in PR checklist.

## Local IDE support

VS Code kustomize plugin with helm enabled reduces "works on my laptop"—pin plugin docs to kustomize version matching CI 5.3.x etc.

Hybrid pattern longevity depends on disciplined pin and review—not on kustomize being magic glue avoiding Helm fork.
""",

    "devops-gitops-multi-cluster": r"""

## Blast radius of ApplicationSet template bug

One template error propagates to N clusters—canary ApplicationSet rollout: apply template change to `canary-clusters` generator label first, soak 24h, expand to prod generator. Same progressive delivery as apps.

## Cluster lifecycle

Cluster decommission: remove from generator list, verify Applications pruned, delete cluster registration secret, archive Git path—checklist prevents orphan Applications pointing at dead API servers spamming sync errors forever.

## Uniformity vs snowflake clusters

Some regions require data residency helm values—parameterize overlay path don't fork ApplicationSet template per region unless necessary. Snowflake count should shrink over time not grow with each acquisition.

Fleet GitOps at scale is change management discipline—generators multiply reach so template quality bar is higher not lower than single-cluster GitOps.
""",
}


def expand_all():
    results = []
    for slug, extra in EXPANSIONS.items():
        path = BLOG / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"Bad frontmatter: {slug}")
        body = parts[2]
        if extra.strip() in body:
            continue
        new_body = body.rstrip() + extra
        path.write_text("---".join([parts[0], parts[1], new_body]) + "\n", encoding="utf-8")
        wc = len(WORD_PAT.findall(new_body))
        results.append((slug, wc, wc >= 1200))
    return results


if __name__ == "__main__":
    results = expand_all()
    ok = sum(1 for _, _, g in results if g)
    print(f"Expanded {len(results)} posts; {ok} >= 1200 words")
    for slug, wc, good in sorted(results):
        print(f"  [{'OK' if good else 'SHORT'}] {slug}: {wc}")

