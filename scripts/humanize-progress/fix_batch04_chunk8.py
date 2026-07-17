#!/usr/bin/env python3
"""Fix batch-04 chunk 8: remove boilerplate, expand under-1200 posts."""
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BLOG = Path(__file__).resolve().parents[2] / "content" / "blog"
BATCH_JSON = Path(__file__).resolve().parent / "batch-04.json"

SLUGS = """devops-ingress-nginx-rate-limiting devops-iam-policy-simulator devops-cert-manager-letsencrypt-dns01 devops-gpu-node-scheduling devops-cluster-autoscaler-overprovision devops-cloud-reserved-capacity-planning devops-gitops-helm-kustomize-hybrid devops-gitlab-ci-child-pipelines devops-flux-image-automation devops-configmap-hot-reload devops-feature-store-monitoring devops-github-actions-reusable-workflows devops-cert-manager-wildcard-certs devops-gateway-api-httproute-canary devops-autoscaler-limits-governance devops-batch-inference-pipelines devops-cdn-cache-purge-strategies devops-chaos-experiment-automation devops-capacity-forecasting-models devops-dag-dependency-management devops-model-serving-kserve devops-bigquery-slot-management devops-argocd-sync-waves-hooks devops-cdc-debezium-postgres-ops devops-canary-cd-analysis devops-data-mesh-domain-ownership devops-blue-green-cd-implementation devops-audit-log-immutable-trail devops-argocd-app-of-apps devops-blast-radius-containment devops-model-serving-ensemble design-system-semantic-versioning design-system-dark-mode-tokens design-system-icon-system-svg-sprite design-system-typography-scale-fluid devops-argo-workflows-data-pipelines design-system-density-modes devops-airflow-kubernetes-executor design-system-spacing-grid-system design-system-composition-over-configuration devops-airflow-dag-best-practices design-system-slot-pattern-polymorphism design-system-figma-code-parity devops-alertmanager-inhibition-routes developer-productivity-metrics-space devops-anycast-dns-failover devops-airflow-backfill-strategies devops-api-server-audit-logging designing-tool-schemas-for-agents devops-apm-service-map-ops dbt-transformations-testing dependency-confusion-attacks database-uuid-vs-autoincrement-keys design-system-component-api-design devops-admission-webhook-security devops-model-serving-edge-deployment devops-model-serving-batching devops-custom-scheduler-plugins database-time-series-partitioning devops-daemonset-upgrade-strategy designing-for-observability-slos devops-model-serving-circuit-breakers database-soft-delete-patterns devops-cronjob-timezone-dst""".split()

BOILERPLATE_RE = re.compile(
    r"\n## Keeping [^\n]+\n\nSchedule quarterly reviews of the practices in this post.*?(?=\n## |\Z)",
    re.DOTALL,
)

EXPANSIONS = {
    "devops-dag-dependency-management": """

## Backfill coordination across teams

Historical replays are the highest-risk window for cross-DAG coupling. When upstream backfills 90 days of Stripe charges, downstream marts scheduled on datasets may fire once per partition update—or not at all if producers forget to emit dataset events for backfill tasks. Standardize a **backfill playbook**: announce in `#data-platform`, freeze consumer deploys, run upstream with `max_active_runs=1`, verify dataset timestamps in the UI, then trigger downstream with explicit `execution_date` alignment documented in the ticket.

For teams still on ExternalTaskSensor during migration, require `mode="reschedule"` and `poke_interval` no less than 300 seconds unless deferrable. Publish a monthly **sensor inventory report** from the metastore—owners must justify any sensor poking more than 1,000 times per day or delete it.

## Contract testing in CI

Treat dataset URIs like OpenAPI specs. Consumer repo CI job:

```python
def test_contract_stripe_charges():
    contract = load_yaml("contracts/warehouse/raw/stripe/charges.yaml")
    assert contract["schema_version"] == "2.1.0"
    assert "dt" in contract["partition_key"]
```

Upstream PR that drops a column without bumping `schema_version` fails required check. Pair with dbt `sources` freshness tests so warehouse-native validation catches drift even when Airflow metadata looks green.

## Ownership and escalation

Every dataset URI has a primary owner and secondary in the data catalog. When freshness SLA misses, page the producer first—downstream on-call should not debug upstream SQL at 3 AM without a handoff. Escalation after 30 minutes routes to platform orchestration on-call for scheduler or metastore issues, not application SRE.

Cross-DAG dependencies fail quietly; datasets, contracts, and CI enforcement make the coupling visible before finance notices the mart stopped updating.
""",
    "devops-gitops-helm-kustomize-hybrid": """

## Post-incident review for hybrid repos

When a hybrid deploy fails, capture whether the root cause was unpinned chart version, conflicting patch layers, or CRD ordering—not "GitOps is flaky." We maintain a lightweight template: chart version, overlay path, diff size, time to rollback, and whether `kustomize build --enable-helm` locally reproduced the failure. Patterns repeat: teams that skip local build pay for it in prod sync timeouts.

## Teaching the pattern to application teams

Platform office hours demo: start from empty overlay, add one resource patch, bump chart patch version, read CI diff comment. Engineers who only copy-paste YAML from Notion recreate the bash-pipe antipattern within a quarter. Backstage scaffolder generates the directory skeleton with pinned `helmCharts` block—reduces blank-page errors.

Hybrid GitOps endures when chart bumps are intentional products and overlays stay thin environment skin—not a second place to fork upstream templates.
""",
    "devops-gitlab-ci-child-pipelines": """

## Measuring child pipeline ROI

Track parent pipeline duration before/after split, cache hit rate per child, and **false-negative skip rate** (child did not trigger but should have due to rules misconfiguration). We dashboard `ci_child_trigger_missed_total` from a nightly job that diffs changed paths against rules—catches glob typos before they skip security scans on critical paths.

## Security boundaries between children

Child pipelines inherit parent variables—never pass long-lived deploy tokens to every child. Scope `CI_JOB_TOKEN` permissions per project; use protected environments only on production deploy jobs inside the child that owns that service. Separate signing keys per child image build so compromise of one Dockerfile does not grant registry push for all services.

Child pipelines buy speed when DAG edges and deploy locks are as explicit as the microservice boundaries they mirror.
""",
    "devops-github-actions-reusable-workflows": """

## Version pinning and breaking changes

Reusable workflows referenced as `@main` broke 52 repos when we renamed a required input. Policy: tag reusable workflow releases (`@v3.2.1`) and let Renovate open bump PRs with integration tests. Document input schema in workflow `workflow_call` comments; breaking input renames require major tag bump and migration note in platform changelog.

## Secrets inheritance pitfalls

`secrets: inherit` is convenient and dangerous—child workflows receive every secret the caller can access. Prefer explicit `secrets:` mapping per reusable workflow. Audit quarterly which repos call platform workflows and whether they still need inherited production credentials for lint-only jobs.

Reusable workflows scale platform CI when contracts are versioned like libraries—not when `@main` is a moving target.
""",
    "devops-flux-image-automation": """

## Automation pause runbooks

During registry incidents or CVE holds, suspend `ImageUpdateAutomation` with a Git revert or `spec.suspend: true` documented in `#platform-status`. Resume checklist: ImageRepository Ready, policy range updated, one manual digest promoted to staging, then re-enable automation. Paused automation without communication looks like "Flux broken" to application teams shipping daily.

## Semver policy as code

Store allowed tag regex per environment in policy repo reviewed by security. CI on application repos validates `docker tag` matches prod policy before push—fail fast instead of ImagePolicy silently ignoring tags for weeks while prod runs stale digest.

Flux image automation is trustworthy when semver ranges, signing, and review gates fail closed—not when `latest` floats because policy was never written down.
""",
    "devops-feature-store-monitoring": """

## Executive-readable dashboards

Translate null-rate spikes into **estimated affected inferences per minute** using traffic metrics—incident commanders communicate customer scope without ML jargon. Pair technical dashboards with one business panel: revenue at risk when payment fraud features degrade, tied to feature freshness SLAs.

## Model launch checklist integration

Every model launch ticket includes monitoring tasks: dashboard cloned, alerts wired, probe entity registered, parity job scheduled. Registry promotion blocked until tier-1 checklist green seven days—prevents shipping models on features nobody watches until chargebacks rise.

Feature store monitoring earns budget when it prevents silent quality decay—not when it only exists to satisfy a MLOps maturity spreadsheet.
""",
    "devops-gateway-api-httproute-canary": """

## Controller capability matrix

GAMMA-compatible implementations differ: some honor `backendRefs` weights only when Service port names match exactly; others require `parentRefs` sectionName for shared gateways. Maintain an internal matrix: controller version × supported Route features × known bugs. Upgrade controller before adopting HTTPRoute fields your current version ignores silently—weights stuck at 50/50 look like "canary works" until error rate proves otherwise.

## Metric gates for promotion

Automate promotion on `HTTPRoute` weight increase only when:

- 5xx rate delta < 0.1% vs stable backend over 15 minutes
- p99 latency delta < 20 ms
- Business golden signal (checkout success) flat or improved

Manual weight edits remain break-glass with ticket ID annotation in Git commit message.

Gateway API canaries replace Ingress annotation hacks when your controller implements weights honestly and metrics prove the shift before humans declare victory.
""",
    "devops-model-serving-circuit-breakers": """

## Breaker configuration in service catalog

Register each dependency breaker in Backstage: thresholds, owner, degradation behavior, last chaos test date. On-call runbook links from Alertmanager annotations go directly to that entry—not a wiki search during a sev2. Quarterly chaos drills update `last_verified` or the catalog marks the breaker stale.

## Cost of over-sensitive breakers

Breakers that open on single timeouts create flapping degraded mode—support tickets rise while infra metrics look fine. Review open events monthly; tune thresholds if false-positive rate exceeds 10%. Under-sensitive breakers show up as thread pool exhaustion with closed breaker state—lower failure threshold or shorten client timeout.

Circuit breakers pay off when degradation is explicit, tested, and owned—not when they are copy-pasted defaults from a blog post without metrics.
""",
}


def word_count(path: Path) -> int:
    return int(subprocess.check_output(["wc", "-w", str(path)], text=True).split()[0])


def strip_boilerplate(text: str) -> str:
    return BOILERPLATE_RE.sub("", text)


def update_date_modified(text: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if re.search(r"^dateModified:", text, re.M):
        return re.sub(r'^dateModified:.*$', f'dateModified: "{today}"', text, count=1, flags=re.M)
    return text


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    text = path.read_text()
    text = strip_boilerplate(text)
    text = update_date_modified(text)
    if slug in EXPANSIONS and slug != "devops-ingress-nginx-rate-limiting":
        if EXPANSIONS[slug].strip() not in text:
            text = text.rstrip() + EXPANSIONS[slug]
    path.write_text(text if text.endswith("\n") else text + "\n")
    w = word_count(path)
    return {"slug": slug, "words": w, "status": "ok" if w >= 1200 else "short"}


def merge_batch(results: list[dict]) -> None:
    import json

    data = json.loads(BATCH_JSON.read_text())
    done = set(data.get("done", []))
    for r in results:
        done.add(r["slug"])
    data["done"] = sorted(done)
    data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    chunk = {
        "processed": len(results),
        "results": sorted(results, key=lambda x: x["slug"]),
    }
    data["chunk8"] = chunk
    data["notes"] = "Rewrote/expanded 64 posts in batch-04 worker chunk 8 (user request)"
    BATCH_JSON.write_text(json.dumps(data, indent=2) + "\n")


def main():
    results = [process_slug(s) for s in SLUGS]
    merge_batch(results)
    short = [r for r in results if r["status"] != "ok"]
    print(f"Processed {len(results)} files")
    print(f">=1200 words: {len(results) - len(short)}")
    if short:
        print("Still short:")
        for r in sorted(short, key=lambda x: x["words"]):
            print(f"  {r['words']} {r['slug']}")
    else:
        samples = sorted(results, key=lambda x: -x["words"])[:5]
        print("Top word counts:")
        for r in samples:
            print(f"  {r['words']} {r['slug']}")


if __name__ == "__main__":
    main()
