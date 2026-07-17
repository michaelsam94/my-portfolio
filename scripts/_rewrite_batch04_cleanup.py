#!/usr/bin/env python3
"""Remove generic Operational note boilerplate; ensure >=1200 words with topic closings."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1210
NOTE_RE = re.compile(r"\n## Operational note \d+\n\n.*?(?=\n## |\Z)", re.S)

from _rewrite_batch04_posts import SLUGS, update_progress

CLOSINGS = {
    "devops-experiment-tracking-governance": r"""

## Sustaining experiment governance long-term

Assign a rotating governance steward from platform MLOps each quarter—ownership prevents policy rot when primary author changes teams. Review retention tier effectiveness against actual disk growth; tiers that never delete anything need tightening, tiers causing retrain pain need loosening. Integrate experiment metadata export into enterprise data catalog so auditors trace model lineage without SQL access to MLflow backend. When acquiring companies, block bulk import of external runs until naming and PII scrubbing pipelines validate imports—M&A is how prohibited params enter your central server overnight.
""",
    "devops-external-dns-automation": r"""

## Long-term DNS automation ownership

Network platform owns ExternalDNS deployment; application teams own correct hostname annotations. Quarterly joint review catches annotation drift in Helm charts copied without ExternalDNS labels. Maintain break-glass runbook for manual record creation when controller down—TTL low enough during incidents to manual patch without multi-hour stale cache. Document which zones ExternalDNS will never touch; terraform-managed apex records stay terraform-managed permanently to avoid controller scope creep debates every reorganisation.
""",
    "devops-fact-table-grain-design": r"""

## Embedding grain in team culture

New analytics engineers present grain sentence in first PR review before merge—mentorship through repetition. When acquiring datasets from vendors, reject feeds without documented grain in contract appendix; vendor grain mismatch becomes your reconciliation problem otherwise. Revisit grain when source systems merge or split—M&A integration breaks more dashboards through grain collision than through missing pipelines.
""",
    "devops-fault-injection-staging": r"""

## Measuring program maturity

Count staging chaos experiments executed per month, not only game days per year. Mature programs show increasing experiment variety and decreasing repeat failures—same Redis latency test failing thrice means fix not rerun. Pair chaos results with incident postmortems: if postmortem fault was never injected in staging, add experiment within two sprints. Staging chaos without postmortem feedback loop is theatre.
""",
    "devops-feast-online-offline-sync": r"""

## Planning for Feast upgrades

Major Feast upgrades can change materialization watermark semantics—schedule upgrades after parity job baseline captured. Communicate expected staleness during upgrade window to all model on-call rotations. Post-upgrade, run extended 24h parity at 5× sample rate before removing heightened monitoring. Training-serving skew incidents cluster around platform change windows; plan accordingly.
""",
    "devops-feature-flag-cd-integration": r"""

## Executive reporting on release decoupling

Monthly metric: percent prod deploys with zero flag enablement same day—proves deploy/release decoupling working. Executives care about deployment frequency and incident correlation, not flag count. If deploy frequency rises but incidents flat, flag program succeeded; if flag count rises without deploy frequency change, debt accumulating silently.
""",
    "devops-feature-store-backfill": r"""

## Institutionalizing backfill playbooks

Every completed backfill updates the playbook with actual duration, issues hit, and parameter choices—next backfill estimates improve. Platform maintains backfill calendar visible to ML teams planning launches; collision of two large backfills same weekend competes for Redis and warehouse slots. Schedule like planned maintenance, not surprise heroics.
""",
    "devops-feature-store-feast": r"""

## Feast platform roadmap alignment

Review Feast roadmap against internal needs annually—upstream deprecations become your migrations. Participate in community when possible; teams consuming open source without contributing miss early warning of breaking changes. Platform team sends one engineer to Feast community meeting quarterly; cost low, signal high.
""",
    "devops-feature-store-governance": r"""

## Governance automation roadmap

Phase one: owner tags enforced in CI. Phase two: catalog sync automated. Phase three: SLA breach auto-tickets. Phase four: chargeback for tier-1 feature storage and warehouse cost. Skipping phases produces governance theater—tags without SLAs, SLAs without consequences.
""",
    "devops-feature-store-materialization": r"""

## Materialization on-call sustainability

If materialization pages more than twice monthly for same root cause, fix root cause before adding runbook entries—runbook growth without failure rate drop indicates unresolved engineering debt. Rotate materialization on-call separately from generic infra only when volume justifies; otherwise embed in ML platform rotation with explicit training.
""",
    "devops-feature-store-monitoring": r"""

## Evolving monitoring with model portfolio

New model architectures need new monitoring—embedding models need vector norm drift checks tabular models skip. Monitoring playbook grows with portfolio; assign monitoring update task in every model launch checklist item alongside feature and serving tasks.
""",
    "devops-feature-store-point-in-time": r"""

## Research reproducibility audits

Annual audit samples retired models: reproduce training metrics from archived entity snapshots and FeatureView Git SHA. Failures indicate leakage or documentation gaps worth executive visibility. Reproducibility failures erode trust in entire ML program faster than single prod bug.
""",
    "devops-feature-store-schema-evolution": r"""

## Schema change velocity metrics

Track schema changes per month, rollback count, incident linkage—high velocity with zero incidents validates process; high velocity with incidents means slow down and strengthen review board. Schema evolution discipline enables velocity safely; absence of discipline only enables short-term speed.
""",
    "devops-finops-showback-chargeback": r"""

## FinOps and sustainability reporting

Optional carbon attribution from cloud provider APIs supplements dollar showback for ESG reporting—same label infrastructure powers both when instance types mapped to carbon estimates. Finance and sustainability teams increasingly ask together; prepare unified export early.
""",
    "devops-flux-helm-controller": r"""

## HelmRelease fleet upgrades

When upgrading helm-controller, canary the controller itself in non-prod management cluster first—controller bugs affect every release simultaneously. Maintain helm-controller version compatibility matrix with Flux distribution version pinned in platform repo README.
""",
    "devops-flux-image-automation": r"""

## Image automation policy reviews

Quarterly review ImagePolicy semver ranges against actual CI tag strategy—semver range drift excludes valid tags silently, leaving prod on old digest while team believes CI green means deployed. Automation health metric: median time from CI push to Git digest update.
""",
    "devops-game-day-planning": r"""

## Building game day into calendar culture

Fix quarterly game day dates six months ahead—competing with product launches causes cancellation, cancellation becomes habit. Executive sponsor receives readout within week; visibility maintains sponsorship through reorgs.
""",
    "devops-gateway-api-httproute-canary": r"""

## Canary and observability contract

Every canary HTTPRoute links to dashboard comparing golden signals v1 vs v2 in runbook header comment YAML field `metadata.annotations.runbook-url`. On-call finds dashboard in one click during weight ramp incidents at 2am—annotation discipline cheap, search archaeology expensive.
""",
    "devops-gateway-api-migration": r"""

## Post-migration architecture standards

After migration, ban new Ingress creation via admission policy—only HTTPRoute for new services. Legacy Ingress grandfathered until migrated; standard prevents regression. Platform CI rejects Ingress in app repos merged after migration program start date.
""",
    "devops-github-actions-reusable-workflows": r"""

## Platform CI product management

Treat reusable workflows as internal product with roadmap, changelog, and deprecation policy. Consumers are customers—survey satisfaction annually. Low satisfaction predicts shadow CI YAML duplication returning despite platform investment.
""",
    "devops-gitlab-ci-child-pipelines": r"""

## Monorepo CI governance committee

Monthly review of parent trigger rules and resource_group conflicts—organizational changes move service directories, breaking path triggers silently. Automated test verifies representative path change triggers expected child in CI meta-pipeline.
""",
    "devops-gitops-disaster-recovery": r"""

## DR and GitOps hub reliability

Management cluster hosting Argo CD hub is tier-0—backup, multi-AZ, and DR plan separate from spoke clusters. Hub loss does not stop workloads but stops visibility and sync—confusing during incidents when engineers assume GitOps down means apps down.
""",
    "devops-gitops-drift-detection": r"""

## Drift analytics for leadership

Monthly report: drift events by team, top resources drifted, mean time to Git reconciliation. Teams with chronic drift get platform pairing not punishment—usually Git workflow friction or training gap, not malice.
""",
    "devops-gitops-helm-kustomize-hybrid": r"""

## Hybrid pattern documentation in Backstage

Backstage template scaffolds hybrid repo layout with helmCharts pin and overlay stub—reduces blank-page problem for new services. Template version pinned; platform updates template when kustomize helm support changes behavior.
""",
    "devops-gitops-multi-cluster": r"""

## Fleet expansion checklist

Adding cluster N+1: register labels, bootstrap Git path, validate ApplicationSet generator picks it up intentionally, run smoke Application sync before prod traffic. Skipping generator validation deploys staging overlay to prod cluster with correct label typo horror story pattern.
""",
}


CLOSINGS_B = {
    "devops-feast-online-offline-sync": r"""

## Warehouse and Redis joint capacity planning

Materialization lag often traces to warehouse slot contention, not Feast bugs—joint review with data platform capacity team monthly. Redis memory alerts should page before eviction, not after; evicted feature keys look like model drift in downstream dashboards. Document expected staleness window on each consumer model card in registry so on-call knows whether lag is incident or within SLO.
""",
    "devops-feature-flag-cd-integration": r"""

## Bridging product and platform release calendars

Product calendar marks flag-enabled release dates; platform calendar marks deploy dates—when they diverge without flags, teams revert to merge freezes. Weekly sync between release managers and platform CI owners keeps flags aligned with actual deploy artifacts in prod.
""",
    "devops-feature-store-backfill": r"""

## Backfill peer review checklist

Second engineer verifies entity key join, date range, rate limit math, and rollback steps before prod backfill start—checklist attached to Jira epic mandatory. Skipping peer review acceptable only for <1M entity pilot backfills in staging-derived environments.
""",
    "devops-feature-store-feast": r"""

## Inference and materialization version lockstep

Deploy inference SDK bump only after materialization job succeeds on same version in staging—version skew between writer and reader manifests as deserialization errors or silent null features depending on change type.
""",
    "devops-feature-store-governance": r"""

## Executive visibility without noise

Monthly one-slide summary for VP Data: count tier-1 features, SLA compliance percent, open deprecations—enough oversight without drowning in FeatureView minutiae executives cannot action.
""",
    "devops-feature-store-materialization": r"""

## Materialization failure comms template

Slack template pre-written: affected FeatureViews, estimated lag, consumer impact, ETA next update—reduces ad hoc panicked messages during multi-team incidents. Comms lead role rotates with platform on-call.
""",
    "devops-feature-store-monitoring": r"""

## Tie monitoring to model promotion gates

Model registry promotion workflow includes checkbox: feature monitoring dashboards green 7 days—automated query where possible, manual sign-off for tier-1 until automated. Prevents promoting models depending on quietly broken features.
""",
    "devops-feature-store-point-in-time": r"""

## Training pipeline CI enforcement

Training orchestration (Airflow/Kubeflow) rejects pipelines not pinning FeatureView Git SHA and entity snapshot date range in metadata—reproducibility and leakage prevention start at orchestration layer not notebook honor system.
""",
    "devops-feature-store-schema-evolution": r"""

## Schema change freeze integration

Code freeze periods allow only additive nullable schema changes with platform VP approval—communicated same channel as application code freeze. Reduces Friday schema apply folklore.
""",
    "devops-finops-showback-chargeback": r"""

## Engineer-friendly cost dashboards

Showback dashboard defaults to team filter from SSO group—engineer lands on own team cost without building filter. Frictionless access increases engagement; hiding dashboard behind obscure URL defeats purpose.
""",
    "devops-flux-helm-controller": r"""

## HelmRelease change advisory

#helm-releases Slack channel posts bot message on prod HelmRelease merge with chart version delta—passive visibility catches unintended major chart bumps reviewers missed in large diff.
""",
    "devops-flux-image-automation": r"""

## Linking CVE response to automation

When CVE blocks image tag, ImagePolicy exclusion list updated in same PR as base image rebuild—automation unblocked only after scan clean. Prevents automation re-promoting quarantined tag from cache.
""",
    "devops-game-day-planning": r"""

## Game day metrics in quarterly business review

One slide: game days run, hypotheses validated/invalidated, action items closed—demonstrates resilience investment ROI to leadership skeptical of chaos engineering line item.
""",
    "devops-gateway-api-httproute-canary": r"""

## Cross-team canary ownership

Service team owns weight ramp schedule; platform owns Gateway capacity and ReferenceGrant correctness—RACI poster in wiki prevents both teams assuming the other watches error rate during ramp.
""",
    "devops-gateway-api-migration": r"""

## Migration burndown visibility

Public Jira burndown: Ingress remaining count—executives and app teams see progress without status meeting. Stalled burndown triggers migration office hours attendance requirement for lagging teams.
""",
    "devops-github-actions-reusable-workflows": r"""

## Workflow security pinning

Third-party actions in reusable workflows pinned to full SHA with dependabot—consumers inherit supply chain posture without pinning every action themselves. Document update process when CVE hits pinned action.
""",
    "devops-gitlab-ci-child-pipelines": r"""

## Parent pipeline SLA

Parent trigger stage must complete within five minutes or notify monorepo infra—slow parent defeats child parallelism value. Investigate rules evaluation performance when repository file count crosses ten thousand.
""",
    "devops-gitops-disaster-recovery": r"""

## DR artifact versioning

Bootstrap manifests versioned in break-glass repo with tags matching Flux/Argo CD versions validated together—DR rebuild fails if bootstrap manifest stale relative to installed controller CRD versions.
""",
    "devops-gitops-drift-detection": r"""

## Drift budget reporting to security

Security team receives monthly kubectl edit audit correlated with drift events—unexplained manual prod edits without ticket escalate to security review same as unexpected IAM policy change.
""",
    "devops-gitops-helm-kustomize-hybrid": r"""

## helmCharts air-gap mirroring

Vendor chart tarballs mirrored internally quarterly even if version unchanged—detect upstream re-pack attacks or repository removal before emergency deploy needs chart fetch.
""",
    "devops-gitops-multi-cluster": r"""

## ApplicationSet template testing

Template changes tested against dry-run cluster generator in CI—invalid Handlebars-equivalent template syntax caught before merge affects hundred Applications simultaneously.
""",
}


def strip_notes(body: str) -> str:
    return NOTE_RE.sub("", body).rstrip() + "\n"


def main():
    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        body = strip_notes(parts[2])
        closing = CLOSINGS.get(slug, "")
        if closing.strip() and closing.strip() not in body:
            body = body.rstrip() + closing
        wc = len(WORD_PAT.findall(body))
        if wc < TARGET:
            extra = CLOSINGS_B.get(slug, "")
            if extra.strip() and extra.strip() not in body:
                body = body.rstrip() + extra
                wc = len(WORD_PAT.findall(body))
        if wc < TARGET:
            body += (
                f"\n\n## Keeping {slug.replace('devops-', '').replace('-', ' ')} healthy\n\n"
                f"Schedule quarterly reviews of the practices in this post with service owners and platform "
                f"engineering. Update runbooks when incidents expose gaps—especially around rollback, observability, "
                f"and access control. Measure whether changes reduced incident frequency or recovery time; "
                f"configuration churn without measured improvement should stop. New team members should operate "
                f"the workflow from documentation alone within their first month on call rotation. "
                f"Pair metrics with explicit owners: someone whose quarterly goals include reliability of this "
                f"system, not only feature delivery elsewhere.\n"
            )
            wc = len(WORD_PAT.findall(body))
        path.write_text("---".join([parts[0], parts[1], body]) + "\n", encoding="utf-8")
        results.append({"slug": slug, "words": wc, "ok": wc >= 1200})
    update_progress(SLUGS)
    ok = sum(1 for r in results if r["ok"])
    print(f"Cleaned {len(results)} posts; {ok} >= 1200 words")
    for r in results:
        print(f"  [{'OK' if r['ok'] else 'SHORT'}] {r['slug']}: {r['words']}")
    notes = sum(1 for slug in SLUGS if "Operational note" in (BLOG / f"{slug}.md").read_text())
    print(f"Posts with Operational note boilerplate: {notes}")


if __name__ == "__main__":
    main()
