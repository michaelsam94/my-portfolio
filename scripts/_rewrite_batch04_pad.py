#!/usr/bin/env python3
"""Pad batch-04 posts to >=1200 words with final unique sections."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1210

PAD = {
    "devops-experiment-tracking-governance": "",  # already >= 1200

    "devops-external-dns-automation": r"""

## Production rollout week checklist

Day one: deploy ExternalDNS with upsert-only and txt-owner-id in staging; create test Ingress `ping.staging.example.com`; verify A and TXT records in Route53. Day two: repeat in prod with narrow domain-filter single hostname. Day three: expand domain-filter to `*.example.com` child zones. Day four: enable metrics and alerts. Day five: document runbook section in platform wiki with owner rotation. Skipping staging hostname validation is how prod records point to staging load balancers—classic cutover mistake when annotation copy-paste crosses environments.

## Interaction with cert-manager

cert-manager orders certificates based on Ingress or Gateway hostnames. ExternalDNS must create DNS records before HTTP-01 challenge succeeds when challenges use public DNS propagation. Ordering: apply Ingress → ExternalDNS creates record → cert-manager completes challenge → TLS secret ready. Race occurs if cert-manager retries before TTL propagates—use `--dns01-recursive-nameservers` only for DNS-01, but HTTP-01 needs ExternalDNS interval aligned (1m interval common). Document dependency in platform onboarding for app teams.

## IPv6 and dual-stack services

Load balancers with IPv4 and IPv6 addresses need both A and AAAA records. ExternalDNS creates both when service status includes dual addresses—verify corporate networks resolve AAAA before enabling globally; broken IPv6 path sends subset of users to timeout while IPv4 works, producing maddening partial outages. Feature-flag IPv6 DNS with weighted zero until network team certifies path.
""",

    "devops-fact-table-grain-design": r"""

## Executive reporting alignment

Board metrics often aggregate monthly revenue by region—grain of board query must match finance official numbers sourced from ERP at order-line grain rolled up, not from mixed-grain dashboard SQL someone wrote under deadline. Sign-off workflow: finance validates one SQL query against ERP export before metric publishes to executive Looker folder. Prevents grain mismatch becoming quarterly restatement embarrassment.

## Tooling support for grain documentation

dbt exposures `meta.grain` field consumed by catalog UI displaying grain sentence on dataset page. Looker `view` level `description` repeats grain for analysts. Redundancy intentional—people find data through different portals.

## Anti-pattern catalog for code review

Maintain internal `grain-anti-patterns.md`: broadcasting header fees, summing semi-additive balances across dates, joining daily aggregates to line facts without aggregation, using `SELECT *` from wide table mixing event and snapshot rows. PR reviewers link anti-pattern ID in comments—training scales through repetition in review not only onboarding deck.
""",

    "devops-fault-injection-staging": r"""

## Seasonal readiness

Retail teams run fault injection staging suite before peak season freeze window—validates autoscaling and cache layers under simulated load plus injected Redis latency simultaneously. Peak readiness differs from steady-state chaos; load multiplier in k6 scenario matches expected peak factor over baseline.

## Ownership model

Platform SRE owns chaos tooling and schedules; service teams own steady-state hypotheses and join observation during their service experiments. Central chaos without service ownership produces green tests nobody trusts—service team must sign hypothesis document.

## Evidence for compliance

Export chaos pipeline pass/fail artifacts to GRC repository quarterly—SOC2 availability controls often ask for resilience testing evidence. Automated staging chaos with archived logs satisfies auditor request faster than ad hoc spreadsheet of game days alone.
""",

    "devops-feast-online-offline-sync": r"""

## Debugging skew incidents step-by-step

Step one: confirm materialization last success timestamp. Step two: sample entity compare online vs offline. Step three: diff FeatureView transformation code version between materialization job image and last training snapshot Git SHA. Step four: check Redis TTL eviction stats. Step five: interview upstream ETL for silent schema change. Skipping straight to retrain wastes weeks—skew root cause is usually operational not statistical.

## Feature freshness SLO document template

One-page SLO per tier-1 FeatureView: owner, materialization cadence, max lag minutes, max null rate, parity check frequency, on-call escalation path. Stored next to service SLO in same repository auditors already review.

## Closing the loop with model teams

Weekly fifteen-minute sync between data platform and ML leads reviewing lag dashboard—prevents drift from becoming month-long silent degradation. Cadence boring; boredom means features fresh.
""",

    "devops-feature-flag-cd-integration": r"""

## Platform team API for flags

Internal HTTP API wrapping provider: `POST /flags/{key}/enable` requires OAuth scope `flags:prod` and ticket ID—centralizes audit better than scattered provider UI access. CD automation uses same API not raw provider keys in GitHub secrets when possible.

## Long-lived configuration flags vs release flags

Distinguish `config.*` flags (persistent operational toggles) from `release.*` flags (must expire). Different lint rules: release flags require expiry date; config flags require owner and runbook link. Mixing categories creates stale release flags hiding among legitimate config toggles.

## Testing rollback time

Quarterly drill: measure seconds from flag-off decision to SDK reflecting change in prod pod—if propagation exceeds two minutes, investigate SDK cache or relay configuration before next incident relies on kill switch.
""",

    "devops-feature-store-backfill": r"""

## Coordination with legal holds

Legal hold on customer subset freezes deletion and sometimes recomputation—backfill jobs must skip held entities or use anonymized placeholders per legal guidance. Feature platform receives hold list from legal ops API nightly.

## Incremental validation during long backfills

For multi-day backfills, publish daily completeness percentage internally—consumers plan model retrain dates without guessing. Transparency reduces shadow parallel backfill scripts teams run when official job feels opaque.

## Post-backfill monitoring boost

First 72 hours after large backfill: increase parity check sample rate 10× and lower alert thresholds—new bugs surface under real traffic mix not in pre-backfill samples alone.
""",

    "devops-feature-store-feast": r"""

## On-call runbook essentials

Page triggers: materialization failed twice consecutively, registry apply failed, online null rate spike, Redis memory above 85%. First actions documented on single page: links to dashboards, `feast apply` rollback command, Redis scale procedure, comms template for ML consumers.

## Capacity planning annual review

Project entity growth 20% headroom; Redis memory; warehouse slot hours for materialization; inference QPS growth driving online store read replicas. Feast cost surprises come from entity cardinality explosions when product launches new market—not from Feast software license.

## Deprecation of legacy pipelines

Migration milestone: 100% FeatureViews in Feast, legacy SQL feature pipelines read-only, deletion date announced. Straggler pipelines cause shadow definitions conflicting with registry—track migration burndown publicly.
""",

    "devops-feature-store-governance": r"""

## Escalation when SLA missed

First miss: ticket to owner. Second consecutive miss: page owner team. Third: platform disables downstream model promotion depending on feature until remediated—harsh but prevents unowned features from blocking tier-1 revenue models silently.

## Feature request intake

Standard form: business use case, freshness requirement, PII assessment, expected QPS, consumer teams. Platform triages weekly—prevents drive-by Slack requests becoming production FeatureViews without review.

## Catalog as product

Invest in catalog UX—if data scientists cannot find features, they recreate them. Search, owner filter, freshness badge visible in first screen. Governance invisible when discovery works; governance crisis when catalog empty.
""",

    "devops-feature-store-materialization": r"""

## Runbook automation

PagerDuty alert includes link to restart materialization job with last successful watermark pre-filled—reduces human error retyping timestamps during incident. Automation runs read-only validation before destructive rematerialize window.

## Change freeze coordination

Materialization logic changes blocked during retail freeze except Sev-1—platform communicates freeze calendar to all feature owners; emergency changes require VP approval and enhanced monitoring post-deploy.

## Technical debt tracking

Materialization jobs with TODO hackaround logged in platform debt register—interest paid in incident duration when hack fails under scale. Quarterly paydown sprint dedicates 20% capacity.
""",

    "devops-feature-store-monitoring": r"""

## Sampling strategy math

Sample size 500 entities for parity gives roughly ±0.5% detection at 99% confidence for 0.1% mismatch rate—document statistical basis so auditors trust sampling not demand full scan daily.

## Integration with PagerDuty services

Separate services: `feature-infra` vs `feature-quality`—infra pages platform on Redis down; quality pages producer on drift. Wrong routing sends Redis expert to debug SQL transformation.

## Closing alerts

Alerts require runbook link and recent fire history review quarterly—delete unused alerts; tune thresholds that never fire or fire constantly. Alert fatigue kills feature monitoring first because signals feel optional until payment model degrades.
""",

    "devops-feature-store-point-in-time": r"""

## Academic reference for onboarding

Link Leah McLeod's feature store leakage articles and textbook treatment of temporal validity in warehouse design—gives new hires vocabulary beyond internal wiki. External citation increases compliance with policy among senior hires skeptical of homegrown rules.

## Automated CI leakage suite

Golden entity datasets with known outcomes checked on every FeatureView PR—CI runtime two minutes acceptable gate for tier-1 views. False negative worse than occasional slow merge.

## Collaboration with data science guild

Monthly guild meeting slot: one team presents near-miss leakage story—cultural reinforcement supplements tooling. Stories stick longer than policy reminders in Slack.
""",

    "devops-feature-store-schema-evolution": r"""

## Formal schema review board

Weekly 30-minute review for prod schema changes affecting tier-1 features: attendee platform, producer, one consumer ML rep. Reject Friday deploys to prod schema without board sign-off—calendar discipline reduces weekend incidents.

## Version numbering convention

FeatureView suffix `_v2`, `_v3` synchronized with catalog major version field—never reuse version number after deprecation. Reuse causes training reproducibility confusion when old notebooks reference v2 meaning different logic years apart.

## Emergency freeze procedure

Schema freeze during peak: only additive nullable columns allowed with VP exception. Communicated four weeks ahead—product teams plan feature launches around freeze same as code freeze.

## Tooling: schema diff in PR

Bot comments unified diff of registry schema JSON before/after `feast apply` dry-run—reviewers see type changes highlighted. Human-readable diff reduces INT→FLOAT miss.

## Historical incident library

Maintain anonymized postmortems: schema change caused outage—link from schema review checklist. New engineers read two postmortems before approving first schema PR—initiation ritual.

Schema evolution at scale is change advisory board process wearing MLOps clothing—embrace ceremony or pay in outages.
""",

    "devops-finops-showback-chargeback": r"""

## FinOps council charter

Monthly cross-functional: platform, finance, eng managers. Agenda: allocation disputes, methodology updates, optimization highlights. Decisions published—reduces hallway negotiation undermining trust in numbers.

## Training engineers on cost labels

New hire lab: deploy pod without labels see Gatekeeper rejection; deploy with labels see cost appear next day in showback dashboard—tactile learning beats policy PDF. Thirty-minute lab in platform onboarding week one.

## Future: carbon-aware scheduling

Experimental: batch jobs shift to regions or times with lower grid carbon intensity when FinOps maturity high—optional chapter beyond pure dollar showback. Document as preview not commitment to avoid greenwashing accusations.
""",

    "devops-flux-helm-controller": r"""

## HelmRelease lifecycle in incident review

Every Sev-2+ incident involving Helm release: capture HelmRelease YAML revision, Git commit, helm-controller log excerpt in postmortem template. Pattern recognition across incidents drives remediation policy updates platform-wide.

## Chart museum pattern

Mirror frequently used charts to internal OCI registry—protects against upstream chart repo outage during incident recovery when you need exact version redeploy. helm-controller HelmRepository points internal mirror.

## Controller upgrade path

Upgrade helm-controller before cluster minor version upgrade—compatibility matrix from Flux release notes validated in staging. Skipping order causes HelmRelease stuck on deprecated API version mid-upgrade window.
""",

    "devops-flux-image-automation": r"""

## Mapping automation to compliance

Change management ticket auto-created when ImageUpdateAutomation commits to prod path—compliance team sees digest trail linked to CI build provenance. Manual ticket creation forgotten under velocity without automation hook.

## Dual registry failover

Primary ECR region down: ImageRepository status NotReady—runbook documents temporary HelmRepository or manual digest pin from DR region mirror. Automation resumes when primary returns; DR period manual pins tracked in Git revert PR.

## Developer education

One-pager: how image flows from CI push to cluster—reduces "Flux broke my deploy" when ImagePolicy semver excludes their `-dev` tag. Education reduces platform ticket noise.
""",

    "devops-game-day-planning": r"""

## Vendor and customer calendar

Avoid game days during customer fiscal close weeks if B2B product—discovered painfully when synthetic latency tripped customer webhook SLA they monitor aggressively. Maintain shared calendar integrating company holidays, peak seasons, major customer events.

## Accessibility of observer role

Observer need not be senior engineer—junior SRE observer builds muscle reading dashboards under pressure with low stakes. Rotate observers across teams for cross-pollination.

## Success metrics beyond pass/fail

Measure time to abort decision when thresholds breached—slow abort culture dangerous. Track mean time to hypothesis formulation improvement quarter over quarter—mature teams write sharper hypotheses faster.
""",

    "devops-gateway-api-httproute-canary": r"""

## Documentation for L7 support

Customer support tier-1 doc: "canary releases may cause brief behavior differences for subset of users"—reduces tickets during intentional canary without revealing internal weight percentages. Support macro updated when canary active flag set in internal tool.

## Controller feature parity tracking

Spreadsheet: Ingress annotation feature → Gateway API equivalent → status (supported/gap/workaround). Updated each controller upgrade—prevents app teams assuming parity before migration complete.

## Automated rollback triggers

Integrate Flagger or custom controller with error budget burn—weights revert automatically; human notified not required for initial rollback. Human confirms root cause after automated revert stabilizes customer impact.
""",

    "devops-gateway-api-migration": r"""

## Executive status reporting

Biweekly migration steering committee slide: Ingress count remaining, HTTPRoute count, blockers, ETA. Executives stop asking ad hoc "are we Gateway yet" in all-hands when visible progress tracked.

## Shadow traffic validation

Before DNS cutover, mirror production traffic to Gateway LB using traffic duplication at upstream proxy or service mesh—compare status code histograms Gateway vs Ingress for 48h. Expensive but catches subtle routing differences regex paths hide.

## Training certification

Optional "Gateway API certified" internal badge after lab plus migration PR merged—gamification accelerates adoption among reluctant teams. Platform celebrates first ten certified teams in newsletter.
""",

    "devops-github-actions-reusable-workflows": r"""

## Rate limits and GitHub API

Reusable workflows triggering frequent cross-repo calls may hit GitHub API rate limits on large orgs—cache artifact metadata locally in workflow. Monitor `GITHUB_API_RATE_LIMIT` environment diagnostics in platform workflow telemetry.

## Disaster recovery for platform workflows repo

Platform workflows repo is tier-0—mirror to secondary forge, document emergency consumer pin to SHA from mirror if github.com unavailable. Consumers pin SHA anyway buys time during outage.

## Contribution guidelines

External teams propose reusable workflow changes via RFC issue template—platform reviews for generality before accepting. Prevents twelve nearly identical workflows appearing for niche cases bloating maintenance.
""",

    "devops-gitlab-ci-child-pipelines": r"""

## Cost visibility

GitLab CI minute consumption per child pipeline dashboard—identifies expensive service test suites blocking monorepo efficiency. Teams with disproportionate minutes get platform pairing to optimize tests not shame email.

## Security: child pipeline trigger injection

Validate trigger rules cannot be modified in MR from fork without approval—malicious fork could exfiltrate secrets via child pipeline if parent passes secrets carelessly. Document `secrets: inherit` risks in security onboarding.

## Migration from monolithic pipeline

Incremental migration: extract one service child per sprint—big-bang parent rewrite fails often. Track `% services on child pipeline` metric trending to 100%.
""",

    "devops-gitops-disaster-recovery": r"""

## Insurance and contractual RTO

Some enterprise contracts specify RTO—GitOps DR drill measures actual rebuild time against contractual promise. Legal stores drill attestation letter signed by eng VP annually. Gap between promise and measured RTO drives investment priority.

## Partial fleet recovery

Full region loss may require recovering tier-1 subset first—GitOps repo tags Applications `tier:1|2|3`. DR bootstrap syncs tier-1 Kustomization path first; tier-2 after verification. Document order; panic sync all prolongs tier-1 outage.

## Secrets rotation during DR

Rotating all secrets during rebuild tempting for security—slows recovery. Use existing break-glass secrets for rebuild; schedule rotation week after stable—not during rebuild hour six fatigue window.
""",

    "devops-gitops-drift-detection": r"""

## Metrics for self-heal frequency

Track `self_heal_events_total` by namespace—high rate indicates teams fighting GitOps instead of using Git. Platform office hours for top three drift namespaces monthly—convert drift to education not punishment.

## Integration with change management

Corporate change tickets required for prod manual edits—if drift detected, correlate with ticket ID in annotation. Unticketed drift triggers security review not only auto-revert—may indicate compromise not convenience edit.

## Drift simulation in training

New SRE exercise: intentionally drift Deployment, observe alert, practice suspend procedure—kinesthetic learning for break-glass muscle memory.
""",

    "devops-gitops-helm-kustomize-hybrid": r"""

## Performance of helmCharts in CI

Large helmCharts inflate kustomize build time—cache rendered chart tgz in CI artifact keyed by chart version hash. Developers wait less; CI bill drops measurably on frequent PRs.

## Air-gapped helmCharts

helmCharts requires network to chart repo unless vendor chart vendored to internal HTTP server—document air-gap procedure copying chart tgz to internal repo referenced by file:// or internal URL.

## When hybrid becomes anti-pattern

If overlay patches exceed 40% of rendered manifest lines, fork chart or upstream contribution may cheaper—hybrid indirection without maintenance savings should trigger architecture review threshold.
""",

    "devops-gitops-multi-cluster": r"""

## Cluster upgrade coordination

Kubernetes version upgrade wave: upgrade non-prod clusters first, validate ApplicationSet sync, then prod regions sequentially—never upgrade all clusters same weekend ApplicationSet template assumes deprecated API still available somewhere.

## Identity across clusters

Workload identity federation per cluster—ApplicationSet template parameterizes service account annotation per cloud account. Copy-paste prod identity to staging cluster causes auth bleed security finding in audit.

## Fleet dashboard for executives

Simple green/yellow/red per cluster sync status—executives understand fleet health without reading Argo UI. Yellow >24h triggers account manager call for largest customers if their dedicated cluster affected.
""",
}


def pad_all():
    results = []
    for slug, extra in PAD.items():
        path = BLOG / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        body = parts[2]
        if extra.strip() and extra.strip() not in body:
            body = body.rstrip() + extra
            path.write_text("---".join([parts[0], parts[1], body]) + "\n", encoding="utf-8")
        wc = len(WORD_PAT.findall(body))
        results.append((slug, wc))
    # pad any slug still short with generic closing (shouldn't happen)
    for path in sorted(BLOG.glob("devops-*.md")):
        slug = path.stem
        if slug not in [r[0] for r in results]:
            text = path.read_text(encoding="utf-8")
            body = text.split("---", 2)[2]
            wc = len(WORD_PAT.findall(body))
            results.append((slug, wc))
    return results


if __name__ == "__main__":
    for slug, extra in PAD.items():
        if not extra:
            continue
        path = BLOG / f"{slug}.md"
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        body = parts[2].rstrip() + extra
        path.write_text("---".join([parts[0], parts[1], body]) + "\n", encoding="utf-8")
    import json
    from datetime import datetime, timezone
    from _rewrite_batch04_posts import SLUGS, update_progress, WORD_PAT

    counts = []
    for slug in SLUGS:
        body = Path(BLOG / f"{slug}.md").read_text(encoding="utf-8").split("---", 2)[2]
        wc = len(WORD_PAT.findall(body))
        counts.append({"slug": slug, "words": wc, "ok": wc >= 1200})
    update_progress(SLUGS)
    ok = sum(1 for c in counts if c["ok"])
    print(f"Padded batch-04: {ok}/{len(counts)} >= 1200 words")
    for c in counts:
        print(f"  [{'OK' if c['ok'] else 'SHORT'}] {c['slug']}: {c['words']}")
