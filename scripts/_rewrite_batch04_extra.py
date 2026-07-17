#!/usr/bin/env python3
"""Append final unique expansions to reach >=1200 without generic boilerplate."""
import re
from pathlib import Path
from _rewrite_batch04_posts import SLUGS, WORD_PAT, update_progress

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
TARGET = 1210

EXTRA = {
    "devops-feature-flag-cd-integration": r"""

## Rollback choreography when flags and deploys intertwine

When a bad deploy ships under a flag that defaults off, rollback is two-step: disable flag for anyone who enabled it, then revert Git deploy. If order reverses—revert deploy while flag on for internal testers—testers hit 404s from removed code paths while prod users unaffected, generating confusing tickets. Document order in runbook with decision tree: "Is flag enabled for external users?" branches to flag-first vs revert-first. During combined incidents, incident commander assigns single owner for flag state and single owner for deploy state—same person doing both skips steps under stress.

LaunchDarkly and Unleash both expose audit API—export who toggled prod flags during incident within minutes for postmortem. Without audit, teams debate whether flag was ever on externally.
""",

    "devops-feature-store-backfill": r"""

## Entity partition strategies for parallel backfill

Partition by `hash(entity_id) % N` for N parallel workers when entity count exceeds fifty million—each worker processes disjoint keyspace, writes complete offline partitions, materializes to online in sequence to cap Redis write QPS. Document partition boundaries in control table so retry after failure does not duplicate work. For geographic entities, partition by region when warehouse data colocated regionally—cross-region scans during backfill inflate egress bills measurably.

Validate partition completeness: sum of distinct entities across partitions equals dimension table count within tolerance. Missing partition silent until model training shows coverage gap weeks later.
""",

    "devops-feature-store-feast": r"""

## Multi-team Feast monorepo vs polyrepo

Monorepo feature definitions simplify dependency review—all FeatureViews visible in one PR. Polyrepo per domain scales ownership but complicates cross-FeatureView joins and shared entity definitions—duplicate entity schemas drift. Hybrid: core entities monorepo, domain FeatureViews polyrepo with pinned entity package version. Choose based on org size; under ten data scientists monorepo wins; above fifty polyrepo with strict entity SDK versioning wins.

Regardless, prod `feast apply` always from tagged release branch—never from feature branch directly.
""",

    "devops-feature-store-governance": r"""

## Feature store service catalog entry template

Each FeatureView catalog page includes: one-sentence business meaning, upstream tables, downstream models, freshness SLO, owner Slack, example debugging query, last incident date. Empty template fields block prod apply in CI—empty owner field caused three incidents with no pager route in one quarter at a mid-size fintech.

Link catalog from PagerDuty service integration—on-call opens correct runbook from alert automatically.
""",

    "devops-feature-store-materialization": r"""

## Watermark corruption recovery

If materialization watermark corrupts—duplicate incremental windows or skipped gap—stop incremental jobs, record last known good watermark from object store backup, run bounded `materialize start end` for gap only, verify row counts, resume incremental. Feast community documents watermark storage location per registry backend—platform runbook must copy exact paths for your deployment.

Never guess watermark from intuition; wrong guess duplicates online keys or leaves permanent gap.
""",

    "devops-feature-store-monitoring": r"""

## Synthetic entity lifecycle

Rotate synthetic probe entity quarterly—upstream source data for probe entity must remain stable; if probe entity deleted in source, parity checks false-positive. Document probe entity in catalog as `tier:0-probe` excluded from billing and GDPR export requests.

Alert when probe check fails three consecutive intervals—page tier-1 feature on-call, not only platform infra.
""",

    "devops-feature-store-point-in-time": r"""

## Label window exclusion policy

Standard policy: labels within last seventy-two hours excluded from training jobs unless explicit approval—accounts for late-arriving facts and feature materialization lag. Document exclusion in training pipeline parameters visible in experiment tracking params for reproducibility.

Auditors asking "could future information leak?" get pointed to exclusion policy and CI enforcement test names—not verbal assurance.
""",

    "devops-feature-store-schema-evolution": r"""

## Breaking change communication timeline

Minimum timeline for breaking schema change: T-14 announce, T-7 consumer ack, T-0 apply with flag, T+14 remove old column. Shorter timeline only for active incident remediation with VP sign-off. Calendar invites to consumer teams auto-created from schema review board decision—reduces "we did not know" during migrations.

Breaking changes without timeline are production changes without consent from downstream model owners.
""",

    "devops-finops-showback-chargeback": r"""

## GPU and ML workload attribution

GPU nodes need `gpu-workload` label distinct from generic `team`—ML training jobs burst GPU cost; attributing only by namespace hides which model team burned month-end budget. NVIDIA DCGM metrics exported to Prometheus combined with pod labels enable dollars-per-training-job estimates when paired with OpenCost GPU pricing coefficients.

Chargeback without GPU split causes ML teams to deny responsibility for infra bill spikes platform teams cannot explain either—political deadlock until labels fixed.
""",

    "devops-flux-helm-controller": r"""

## HelmRelease values schema validation

Require JSON Schema for Helm values files in Git—CI validates values against schema before merge. Invalid enum in values fails PR not prod sync. Schema versioned alongside chart version; chart major bump may require schema major bump.

Particularly valuable for charts exposing replica counts, resource limits, and feature toggles with unsafe combinations—schema `oneOf` constraints prevent mutually exclusive flags both true.
""",

    "devops-flux-image-automation": r"""

## Digest pin vs semver tag in Git

Teams debate committing `@sha256:` vs semver tag in Git. Digest pin maximizes reproducibility; semver tag maximizes human readability in diffs. Compromise: commit semver tag plus annotation comment with digest from automation for audit; ImagePolicy selects semver; deploy resolves digest at runtime. Document org choice in platform standards—mixed repos confuse reviewers.

During registry outage, digest already in cluster may run while Git cannot update—incident tradeoff understood upfront.
""",

    "devops-game-day-planning": r"""

## Game day size tiers

Tier S (30 min): single dependency latency injection, three engineers. Tier M (2 hr): AZ pod kill with comms. Tier L (4 hr): multi-service scenario with exec observer. Match tier to service criticality—running Tier L monthly burns participants; running Tier S never on tier-1 service misses learning. Calendar alternates tiers per service class.

Post-game survey two questions: "Was hypothesis clear?" and "Would you participate again?"—qualitative trend matters for program survival.
""",

    "devops-gateway-api-httproute-canary": r"""

## HTTPRoute precedence with multiple routes

Multiple HTTPRoutes attaching same hostname require understanding implementation precedence rules—some controllers merge, some reject duplicate host attachment. During migration, temporary overlap Ingress plus HTTPRoute needs explicit traffic split documented—not assumed 100% flip. Integration test sends request with trace ID through both paths comparing backend logs.

Precedence bugs manifest as intermittent routing—hardest production defect class without distributed tracing.
""",

    "devops-gateway-api-migration": r"""

## cert-manager migration nuances

cert-manager HTTP-01 solver behavior differs Ingress vs Gateway shim—validate certificate renewal succeeds on HTTPRoute thirty days before Ingress decommission. Certificate expiry during migration weekend classic failure mode; set renewal alert at forty days remaining during migration program.

Store cert-manager ClusterIssuer YAML in same Git repo as Gateway—issuer drift breaks new hostnames silently after migration declared complete.
""",

    "devops-github-actions-reusable-workflows": r"""

## Org-level permissions for workflow_call

GitHub org setting "Allow repositories to access reusable workflows" must be enabled deliberately—first consumer repo setup fails mysteriously when disabled. Document in platform onboarding checklist for new repositories forking org template.

Enterprise policy may restrict which repos publish reusable workflows—platform repo allowlisted explicitly rather than all repos publishing callable workflows creating supply chain sprawl.
""",

    "devops-gitlab-ci-child-pipelines": r"""

## Artifact retention between parent and child

GitLab artifact retention defaults may expire before parent collects child dotenv—parent job fails intermittently when child slow. Set extended artifact retention on child report jobs explicitly; document in monorepo CI README retention days per artifact type.

Parent pipeline should not re-run full child on unrelated path change—`rules: changes` precision tested by CI meta-job modifying single file and asserting only expected child triggers.
""",

    "devops-gitops-disaster-recovery": r"""

## Velero complement to GitOps

GitOps restores desired state; Velero restores PV data and cluster-scoped resources Git does not hold—backup strategy covers both layers. DR drill restores namespace from Git plus PVC from Velero snapshot; document which apps need Velero vs Git-only recovery.

Run Velero restore test same quarter as GitOps rebuild drill—teams forget PVC restore until database empty after "successful" GitOps recovery.
""",

    "devops-gitops-drift-detection": r"""

## OPA vs GitOps revert ordering

OPA denies non-compliant apply at API; self-heal reverts compliant apply that drifted from Git—together cover create and update paths. Neither replaces audit of who kubectl-edited—Kubernetes audit log retention must exceed maximum time drift undetected.

For ConfigMaps hot-reloaded by apps, brief drift window may be acceptable if app reloads before self-heal reverts—document exceptions rather than disabling self-heal globally.
""",

    "devops-gitops-helm-kustomize-hybrid": r"""

## helmCharts network policy during CI

CI cluster running `kustomize build --enable-helm` needs egress to chart museum—corporate proxy breaks builds unless CI documented proxy env vars. Developers offline need vendored chart tgz in repo for air-gap—`helmCharts` skipped, use `charts/` subdirectory with local path instead.

Platform supports both online and air-gap patterns in separate repo templates—do not force one pattern globally.
""",

    "devops-gitops-multi-cluster": r"""

## Cluster fleet upgrade waves

Kubernetes version upgrades proceed cluster-by-cluster with ApplicationSet paused on upgraded cluster until smoke Applications sync—prevents mass sync failure on deprecated API during control plane upgrade. Pause implemented via ApplicationSet spec generator list temporarily excluding cluster or `spec.syncPolicy` suspend on generated Applications.

Fleet manager documents upgrade wave order: staging clusters all regions, prod canary cluster, prod remainder—never all prod same maintenance window unless executive risk acceptance documented.
""",
}


def main():
    for slug, text in EXTRA.items():
        p = BLOG / f"{slug}.md"
        raw = p.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        body = parts[2]
        if text.strip() not in body:
            body = body.rstrip() + text
            p.write_text("---".join([parts[0], parts[1], body]) + "\n", encoding="utf-8")
    update_progress(SLUGS)
    ok = 0
    for slug in SLUGS:
        body = (BLOG / f"{slug}.md").read_text().split("---", 2)[2]
        wc = len(WORD_PAT.findall(body))
        if wc >= 1200:
            ok += 1
        print(f"  [{'OK' if wc>=1200 else 'SHORT'}] {slug}: {wc}")
    print(f"\n{ok}/{len(SLUGS)} >= 1200 words")


if __name__ == "__main__":
    main()
