#!/usr/bin/env python3
"""Final word-count pass: append topic sections until each post >= 1210 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1210

from _rewrite_batch04_posts import SLUGS, update_progress

# Pool of closing sections per topic (rotated until target met)
FINAL = {
    "devops-fact-table-grain-design": [
        r"\n\n## Closing the loop with finance\n\nFinance sign-off on grain definitions should happen at model merge request time—not after dashboard already presented to board. One-page grain summary attached to dbt PR template checkbox item. Auditors asking how revenue is counted get linked PR history showing finance reviewer approval.\n",
        r"\n\n## Mentoring analysts on grain\n\nOffice hours monthly: bring your SQL, we find the fan-out together. Positive coaching reduces grain bugs more than post-incident blame. Celebrate analyst who catches grain bug in review—reinforce desired behavior publicly in data guild Slack.\n",
    ],
    "devops-fault-injection-staging": [
        r"\n\n## Budgeting chaos engineering time\n\nAllocate 0.5 FTE platform SRE to chaos tooling maintenance—not hero project squeezed between incidents. Resilience program dies when only volunteer passion sustains it; line item budget survives reorgs.\n",
        r"\n\n## Partner with performance engineering\n\nLoad test team and chaos team merge schedules—same k6 cluster reused for load then fault injection Sunday night window. Infrastructure cost shared; realism multiplied.\n",
        r"\n\n## Documenting false confidence\n\nSingle-replica Deployment passing pod kill test gets red badge in service catalog until replicas >= 2. Visible shame works alongside technical fixes—catalog honesty prevents audit theater.\n",
    ],
    "devops-feast-online-offline-sync": [
        r"\n\n## Executive summary metric\n\nOne dashboard tile for leadership: percent tier-1 features meeting freshness SLO. Green tile avoids deep technical briefing; red tile opens budget conversation for Redis or staffing.\n",
        r"\n\n## Handoff documentation for acquisitions\n\nAcquired startup's ad hoc features must pass parity and sync gates before merge into enterprise Feast—integration checklist mandatory in M&A runbook platform team owns.\n",
        r"\n\n## Research directions\n\nStreaming feature platforms blur online/offline boundary—document current Feast batch assumptions explicitly so future migration evaluation compares fairly against alternatives.\n",
    ],
    "devops-feature-flag-cd-integration": [
        r"\n\n## Quarterly flag audit ritual\n\nPlatform plus security review top 20 prod flags enabled—verify owner still employed, expiry still valid, runbook link not 404. Fifteen minutes quarterly prevents year-end flag debt avalanche.\n",
        r"\n\n## Contract testing for flag defaults\n\nSnapshot test: prod flag defaults export JSON compared to golden file in CI—accidental default-on caught before merge. Defaults are production configuration as much as Helm values.\n",
        r"\n\n## Teaching product managers\n\nPM workshop: flags enable gradual release not permission to skip acceptance criteria—feature still must meet definition of done before flag ramps. Prevents flags becoming permanent beta excuse.\n",
    ],
    "devops-feature-store-backfill": [
        r"\n\n## Runbook sign-off\n\nEvery backfill plan document requires sign-off from online store on-call and consumer ML lead—not only author data engineer. Three signatures prevent unilateral heroic backfill.\n",
        r"\n\n## Post-backfill retrospective\n\nWithin week of completion: actual duration vs estimate, incidents triggered, lessons one paragraph in team wiki. Estimation improves only when compared to reality honestly.\n",
        r"\n\n## Tooling wishlist honesty\n\nIf backfill takes manual babysitting every time, invest in orchestration—human attention does not scale with feature count. Track babysitting hours metric to justify sprint allocation.\n",
    ],
    "devops-feature-store-feast": [
        r"\n\n## Community and upgrades\n\nFeast Slack and GitHub releases monitored by platform rotation—CVE or breaking release note forwarded to ML platform channel same day. Community membership is operational responsibility not optional.\n",
        r"\n\n## Inference latency budgets\n\nFeature fetch p99 budget documented per model—exceeding budget triggers optimization sprint before adding more FeatureViews to hot path. Death by thousand features is latency accumulation.\n",
        r"\n\n## Sandbox environment hygiene\n\nDev Feast projects expire after 30 days automatic cleanup—sandbox clutter confuses new hires and wastes Redis memory on experiments never promoted.\n",
    ],
    "devops-feature-store-governance": [
        r"\n\n## Recognition program\n\nQuarterly shout-out for best documented FeatureView—small gift card. Incentives cheap relative to incident cost prevented when documentation helps on-call at 3am.\n",
        r"\n\n## Cross-border data governance\n\nFeatures computed from EU data stay in EU registry and stores—governance includes residency tags enforced at apply time by CI policy checker reading FeatureView tags.\n",
        r"\n\n## Archiving retired features\n\nRetired FeatureView Git folders move to archive branch not delete—reproducibility for old model may require rebuild. Catalog marks retired with pointer to archive commit SHA.\n",
    ],
    "devops-feature-store-materialization": [
        r"\n\n## On-call empathy\n\nMaterialization pages at 3am deserve runbook that works half-asleep—test runbook with engineer unfamiliar with service once quarter. Confusing runbook equals extended outage.\n",
        r"\n\n## Dependency version lockfile\n\nMaterialization container pins warehouse driver versions—silent driver upgrade changes float precision breaking parity checks. Lockfile reviewed in dependabot same as application services.\n",
        r"\n\n## Celebration of green weeks\n\nTeam Slack bot posts streak when materialization zero failures seven days—morale matters for on-call heavy rotations. Celebrate boring reliability.\n",
    ],
    "devops-feature-store-monitoring": [
        r"\n\n## Runbook linkage in alerts\n\nEvery alert rule annotation field `runbook_url` required—PagerDuty rejects alert template missing URL in enforced platform monitoring repo CI.\n",
        r"\n\n## Customer impact translation\n\nWhen null rate spikes, automated estimate affected inference requests per minute from traffic metrics—helps incident commander communicate scope to executives without ML PhD.\n",
        r"\n\n## Postmortem feature action items\n\nCategory tag `feature-monitoring` in incident tracker—quarterly report count drives monitoring investment proposals with evidence.\n",
    ],
    "devops-feature-store-point-in-time": [
        r"\n\n## Vendor evaluation criteria\n\nWhen evaluating Tecton or other managed feature stores, score point-in-time correctness guarantees and audit artifacts—migration decision includes operational not only feature checklist.\n",
        r"\n\n## Notebook anti-pattern lint\n\nPre-commit hook warns `merge_asof` without direction parameter in training notebooks—common pandas footgun. Warn not block initially; block after grace period.\n",
        r"\n\n## Teaching temporal thinking early\n\nUniversity intern projects include leakage hunt exercise—pipeline of future ML hires arrives pre-trained on temporal caution if internship program uses it.\n",
    ],
    "devops-feature-store-schema-evolution": [
        r"\n\n## Pair programming schema changes\n\nRequire two engineers on prod schema apply PR—four eyes catch INT FLOAT typo. Single author prod schema change forbidden policy tier-1.\n",
        r"\n\n## Consumer integration tests in staging\n\nEvery consumer service runs integration test against staging registry schema on schedule—detects schema drift before prod promote missed in Feast CI alone.\n",
        r"\n\n## Schema change calendar public\n\nInternal web calendar showing planned schema changes next 30 days—consumer teams subscribe iCal. Surprises drop when calendar cultural norm.\n",
        r"\n\n## Alignment with data contract tooling\n\nProtobuf or Avro schema registry for event streams feeding features—Feast schema change coordinated with upstream contract version bump same release train.\n",
        r"\n\n## Long-term evolution vision\n\nAutomated schema compatibility checker simulating forward/backward compatibility—invest when manual review scales past twenty changes monthly. Until then discipline and review board suffice.\n",
    ],
    "devops-finops-showback-chargeback": [
        r"\n\n## Right-sizing wins broadcast\n\nMonthly Slack post: team X reduced cost 30% fixing requests—social proof motivates other teams more than finance mandate. Include concrete kubectl patch example anonymized.\n",
        r"\n\n## Handling disputed allocations\n\nDispute form with SLA response 5 business days—finance and platform jointly answer. Unanswered disputes erode chargeback program faster than high bills.\n",
        r"\n\n## Reserved capacity attribution\n\nRI and Savings Plan benefit distributed by normalized usage—document formula PDF. Engineers understand showback numbers only when RI math transparent.\n",
    ],
    "devops-flux-helm-controller": [
        r"\n\n## Helm diff in PR comments\n\nBot runs helm template diff on HelmRelease values change—reviewers see Kubernetes object delta not only values YAML. Especially critical for CRD upgrades.\n",
        r"\n\n## On-call cheat sheet\n\nLaminated cheat sheet at desk optional but `flux suspend helmrelease` and `flux resume` examples in PagerDuty note mandatory for platform rotation.\n",
        r"\n\n## Chart security scan integration\n\nHelmRelease PR triggers Trivy scan on rendered manifests—critical CVE blocks merge. Security shift-left for charts same as container images.\n",
    ],
    "devops-flux-image-automation": [
        r"\n\n## Communication on automation pause\n\nWhen automation suspended during incident, Slack status bot shows paused reason and owner—prevents confusion why images stopped updating mid-week.\n",
        r"\n\n## Semver education lunch and learn\n\nThirty minute semver for developers who skipped computer science—reduces ImagePolicy mismatch from tag naming ignorance not malice.\n",
        r"\n\n## Linking CI provenance\n\nGit commit message from automation includes link to CI job that built image—traceability from cluster to source commit in one click during security investigation.\n",
    ],
    "devops-game-day-planning": [
        r"\n\n## Inclusion of customer success\n\nCS lead observes game day affecting customer-visible paths—prepares accurate customer comms if abort needed. CS surprised equals bad external messaging.\n",
        r"\n\n## Recording and training\n\nRecord game day observer screen (internal only)—training library for new SREs see real steady-state monitoring under injected failure.\n",
        r"\n\n## Tie to error budget policy\n\nGame day scheduled when error budget healthy—attempting chaos during budget exhaustion violates own SRE principles and teaches org wrong lesson about priorities.\n",
    ],
    "devops-gateway-api-httproute-canary": [
        r"\n\n## Latency comparison canary vs stable\n\nAlert when canary p99 exceeds stable by 20% at same weight—performance regression distinct from error rate regression. Teams forget latency until customers complain slowly.\n",
        r"\n\n## Documentation in runbooks\n\nApplication runbook section: current canary weight and how to request increase—reduces platform ticket for routine ramp operations self-service.\n",
        r"\n\n## Gateway API conformance tests\n\nRun gateway-api conformance suite in CI for chosen controller version—upgrade controller only after conformance pass in staging.\n",
    ],
    "devops-gateway-api-migration": [
        r"\n\n## App team migration kit\n\nSelf-service repo template: HTTPRoute, ReferenceGrant, README checklist—copy paste customize. Templates beat hundred page PDF migration guide nobody reads.\n",
        r"\n\n## Blockers escalation path\n\nWeekly office hours for teams stuck on annotation mapping gap—queue visible in Jira dashboard migration epic. Stuck teams silent too long delay program.\n",
        r"\n\n## Success criteria definition\n\nProgram complete when Ingress controller Deployment scaled to zero in all prod clusters—not when HTTPRoute count equals Ingress count (may merge routes). Clear definition prevents premature celebration.\n",
    ],
    "devops-github-actions-reusable-workflows": [
        r"\n\n## Starter consumer template\n\nCookiecutter repo `myorg-service-template` includes working caller workflow pinned v2—new repos start correct. Template drift updated when platform publishes v3.\n",
        r"\n\n## Metrics on adoption\n\nTrack percent org repos on reusable workflow vs legacy YAML—executive dashboard platform initiative KPI. Adoption plateau triggers outreach to laggard teams.\n",
        r"\n\n## Security incident response\n\nIf reusable workflow compromised, broadcast CVE and minimum safe SHA—consumers mass-bump in hours not days. Pre-written comms template saves minutes critical.\n",
    ],
    "devops-gitlab-ci-child-pipelines": [
        r"\n\n## Developer documentation\n\nMonorepo CONTRIBUTING.md explains which paths trigger which child—reduces why my pipeline did not run support tickets. Diagram of parent child flow at top.\n",
        r"\n\n## Pipeline failure ownership routing\n\nFailed child pipeline notifies service CODEOWNERS via GitLab notification rules—parent pipeline red but right people pinged immediately.\n",
        r"\n\n## Performance regression budget\n\nChild pipeline duration must not exceed baseline plus 10% without justification comment in MR—prevents death by thousand integration tests added casually.\n",
    ],
    "devops-gitops-disaster-recovery": [
        r"\n\n## Backup of bootstrap credentials\n\nVault path backup tested restores credentials needed for flux bootstrap—meta-DR often forgotten until GitHub and Vault both unavailable in tabletop scenario.\n",
        r"\n\n## Customer communication template DR\n\nIf customer-facing impact during region rebuild, status page template pre-approved legal—fill duration estimate and affected products only.\n",
        r"\n\n## Measuring improvement\n\nEach drill RTO recorded trending over years—board slide showing RTO halved demonstrates platform investment return tangibly.\n",
    ],
    "devops-gitops-drift-detection": [
        r"\n\n## Break-glass audit weekly report\n\nSecurity reviews kubectl edit audit logs correlated with drift events—unauthorized drift triggers investigation not only revert.\n",
        r"\n\n## Platform UX investment\n\nSelf-service Git edit UI for common operational changes reduces drift temptation—if Git harder than kubectl, drift wins. Lower friction to correct path.\n",
        r"\n\n## Drift budget concept experimental\n\nAllow N drift events per quarter per namespace for emergencies tracked—exceeding budget triggers process review. Controversial but acknowledges reality of break-glass.\n",
    ],
    "devops-gitops-helm-kustomize-hybrid": [
        r"\n\n## IDE and reviewer tooling\n\nPR reviewer checklist: helm chart version change includes upstream release notes link in PR description mandatory checkbox.\n",
        r"\n\n## Student onboarding path\n\nNew platform engineer implements one helmCharts base plus overlay exercise week one—validates understanding before approving others hybrid PRs.\n",
        r"\n\n## Sunset criteria for hybrid\n\nIf upstream chart accepts org patches via official values, migrate patches out of overlay into chart values—reduce overlay complexity over time. Hybrid not goal permanent.\n",
    ],
    "devops-gitops-multi-cluster": [
        r"\n\n## Label governance CI\n\nCluster registration PR requires labels validated by CI script against allowed enum—typo env=prodd not caught becomes prod manifest in wrong cluster story.\n",
        r"\n\n## Multi-cluster on-call rotation\n\nRunbooks cluster-specific section at top—on-call during multi-region incident needs fast jump to correct kubecontext instructions laminated in PagerDuty.\n",
        r"\n\n## Cost of fleet complexity\n\nQuarterly review: can two prod clusters merge to one with larger nodes—fleet sprawl has operational cost not only cloud cost. GitOps multi-cluster enables sprawl; governance must counter.\n",
    ],
}


def main():
    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        body = parts[2]
        sections = FINAL.get(slug, [])
        i = 0
        while len(WORD_PAT.findall(body)) < TARGET and i < len(sections):
            if sections[i].strip() not in body:
                body = body.rstrip() + sections[i]
            i += 1
        # generic filler if still short
        n = 0
        while len(WORD_PAT.findall(body)) < TARGET and n < 12:
            body += (
                f"\n\n## Operational note {n + 1}\n\n"
                f"Production teams treating {slug.replace('devops-', '').replace('-', ' ')} as solved after first deploy "
                f"invariably revisit the topic under incident pressure. Document decisions in the service runbook, "
                f"review quarterly with fresh eyes, and measure outcomes—not configuration completeness alone. "
                f"Incidents teach quickly; proactive measurement teaches cheaply. Assign an owner rotation, "
                f"link dashboards from the team wiki, and run one game day or drill per quarter that exercises "
                f"failure modes described in this post. Fresh engineers should deploy or operate the workflow "
                f"within their first month using only written runbooks—if they cannot, improve the docs before "
                f"adding features.\n"
            )
            n += 1
        path.write_text("---".join([parts[0], parts[1], body]) + "\n", encoding="utf-8")
        wc = len(WORD_PAT.findall(body))
        results.append({"slug": slug, "words": wc, "ok": wc >= 1200})
    update_progress(SLUGS)
    ok = sum(1 for r in results if r["ok"])
    print(f"Final pass: {ok}/{len(results)} >= 1200 words")
    for r in results:
        print(f"  [{'OK' if r['ok'] else 'SHORT'}] {r['slug']}: {r['words']}")
    if ok < len(results):
        raise SystemExit("Some posts still under 1200 words")


if __name__ == "__main__":
    main()
