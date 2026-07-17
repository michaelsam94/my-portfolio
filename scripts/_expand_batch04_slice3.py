#!/usr/bin/env python3
"""Third-pass: push remaining slice posts to >=1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD = re.compile(r"\b[\w'-]+\b")
MARKER = "\n## Resources\n"

BLOCKS = {
    "devops-gitops-policy-enforcement": """
## Measuring policy program maturity

Track weekly: deny rate by policy rule, mean time to fix denied PR, count of active PolicyExceptions, and percentage of namespaces under enforce vs audit mode. A rising deny rate after new rule rollout is healthy; a flat zero deny rate with audit mode forever suggests policies never graduated to enforce. Pair Kyverno PolicyReport with Grafana Loki queries on admission webhook audit logs for usernames bypassing CI—cluster-admin kubectl remains the unstoppable path; reduce through break-glass auditing and periodic access reviews.

When policies block legitimate urgent work twice in one quarter, fix the policy or the paved-road template—not the exception rate. Exceptions should decay to zero before rule sunset; automate PolicyException expiry alerts 7 days ahead so owners renew deliberately rather than by accident.
""",
    "devops-gitops-preview-environments": """
## Observability for preview fleets

Preview namespaces need lighter SLO dashboards—not full prod paging. Track: count active previews, mean time-to-healthy after PR open, cleanup failures (namespace Terminating > 1h), and percentage of PRs with preview URL commented. Spikes in time-to-healthy often indicate image pull or ExternalSecret sync issues on first PR of the day when caches cold.

Log aggregation costs balloon if preview apps log at debug—set preview overlay log level info and shorter retention (48h) via Loki tenant or index TTL. Chargeback preview CPU to team label `preview/owner` for quarterly FinOps review; teams over budget must use label-gated preview generation.
""",
    "devops-gitops-promotion-environments": """
## Audit and compliance hooks

Regulated environments require evidence that prod change passed staging: store promotion PR URL, approver identities, staging test artifact digests, and Argo CD sync timestamp in immutable audit store (CloudTrail for API, or append-only S3 with object lock). Git history alone insufficient if someone with admin merges without PR—branch protection and signed commits strengthen chain.

For SOC2 change management, automate ticket creation on prod overlay merge linking diff summary and rollback commit SHA pre-computed by CI. Auditors ask "show me July 14 prod deploy"—single query returns promotion PR, tests, approvers, deployed digest, and rollback path file path in repo.
""",
    "devops-gitops-rollback-strategies": """
## Communication during GitOps rollback

Status page messaging differs for rollback vs forward-fix: rollback implies customer-visible regression risk (old bug returns); forward-fix implies continued exposure to new bug until fix lands. Template comms in runbook. Engineering manager approves rollback customer comm when rollback crosses business hours in multiple regions.

After alignment PR merges post-emergency rollback, run automated diff: cluster manifest hash vs Git render hash—must match before incident closed. Argo CD `OutOfSync` allowed duration after rollback zero tolerance for tier-1 beyond 15 minutes—page platform if Git/cluster still divergent.
""",
    "devops-gitops-sealed-secrets": """
## Comparison workshop for architects

Run 90-minute decision session documenting: number of secrets, rotation frequency, multi-cluster count, air-gap requirements, developer offline need, and audit requirements. Matrix score Sealed Secrets vs SOPS vs ESO—no silver bullet. Hybrid common: ESO for dynamic DB creds, SOPS for static API keys in Helm values, SealedSecrets for bootstrap tokens only.

Operational cost: SealedSecrets per-cluster key ceremony; SOPS KMS CloudTrail audit; ESO Vault HA operational burden. Revisit decision annually—starting with SOPS does not preclude migrating high-churn secrets to ESO without re-architecting entire GitOps repo.
""",
    "devops-global-load-balancer-health": """
## Load test validation of health thresholds

Before production launch, load test while artificially delaying `/ready` response 500ms—verify LB does not flap if delay within timeout budget. Then delay 5s beyond timeout—verify backends drain without connection reset storm on clients using keep-alive. Document client retry behavior—mobile apps with aggressive retry amplify partial drain failures.

HTTP/2 and gRPC health: some L7 load balancers use HTTP/1.1 probes only—gRPC health on different port requires TCP or dedicated HTTP health port—architecture review item for new services choosing gRPC-only serving.
""",
    "devops-gpu-node-scheduling": """
## Hardware lifecycle integration

GPU node failures show XID errors in dmesg before total loss—DCGM alert → cordon → drain ML jobs → replace node. Keep spare GPU node capacity 1–2 nodes in pool for rolling replacement without queue stall. RMA process with cloud provider requires checkpoint-friendly training jobs—platform policy mandates checkpoint interval max 30 minutes on spot/preemptible tiers.

Mixed precision training may not saturate GPU compute—monitor `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE` not just GPU util—low tensor active with high memory suggests batch size tuning before buying more GPUs.
""",
    "devops-gpu-scheduling-ml-workloads": """
## Platform API quotas and self-service

Expose quota dashboard to data science: remaining GPU-hours this month, queue position, estimated start time for pending Workload. Reduces Slack asks to platform. Quota increase requests require SLO impact review—inference SLO holder veto on training quota borrow during freeze windows (Black Friday, year-end close).

Ethical and legal review workloads (PII fine-tuning) get dedicated node pool with encryption at rest and no spot—scheduling label `compliance=hipaa` routes only to hardened pool; Kueue ClusterQueue separate from general training.
""",
    "devops-grafana-dashboard-as-code": """
## Unified alerting ownership

Dashboard panel thresholds do not auto-sync to PrometheusRule—require linked PR or annotation `alert_rule: checkout-latency-burn` on dashboard JSON reviewed by same owner. Quarterly audit finds orphan panels with dashed red lines nobody pages on—delete or wire to Unified Alerting export in Git.

For multi-tenant Grafana, folder-per-team RBAC in Terraform prevents team A editing team B dashboards—drift detection via nightly `terraform plan` in CI on observability repo; non-empty plan opens automated ticket to folder owner.
""",
    "devops-headroom-policy-enforcement": """
## Bridging FinOps and SRE headroom targets

Monthly meeting agenda: compare Kubecost idle cost vs incident count from capacity exhaustion. If idle cost down but incidents up, raise headroom target. If idle cost up with zero incidents quarter, cautiously lower target 5% and watch one month—data-driven negotiation beats static 30% wiki policy.

Node pool headroom separate from pod request headroom—cluster may show CPU requests at 60% while one hot node at 95% due to bad bin packing—monitor `kube_node_status_allocatable` minus requests per node p99; cluster autoscaler may need second pool shape if single pool skewed.
""",
    "devops-helm-chart-signing-provenance": """
## Developer UX for verify failures

When cosign verify fails in CI, error message must include: expected signer identity, actual signature absence, and link to internal doc "how to sign charts." Opaque "verify failed" sends engineers to Slack—structured errors reduce MTTR for legitimate new chart publishes.

Cache verified chart digests in local Helm cache mirror—air-gapped clusters pull once through secure transfer, verify at air-gap boundary, distribute internally signed again with org key—double-sign chain documented for auditors.
""",
    "devops-helm-chart-testing-ct-lint": """
## Chart test data realism

CI values should enable every template branch used in prod at least once across ci/*.yaml files—coverage tool on `helm template` output paths vs prod render paths highlights dead branches never tested. Add ci/prod-parity-values.yaml in PR when prod enables new ingress annotation—mandatory reviewer checklist item from incident postmortem.

Flaky hook tests: retry hook Job once in CI only if documented upstream race—otherwise fix chart; flakiness erodes trust in ct gate and teams skip waiting for CI green.
""",
    "devops-helm-dependency-management": """
## License compliance on subcharts

Dependency update PR includes license scan of vendored subchart—GPL subchart in Apache-licensed umbrella triggers legal review. Automate with FOSSA/Snyk on extracted tgz. Some enterprises ban copyleft in production charts—policy blocks merge before legal ticket.

Document subchart pin rationale in Chart.yaml comment block—future maintainer understands why postgresql pinned 15.2.4 not 16.x (app compatibility)—reduces reckless Renovate merge on major bumps.
""",
    "devops-helm-diff-pre-deploy": """
## Teaching diff literacy in platform onboarding

New platform engineers complete lab: given synthetic diff, identify which change causes outage (ClusterRole vs label change). Diff literacy reduces approval rubber-stamping on large platform upgrades. Include exercise on `--reset-values` accidental wipe—diff shows everything changed red—recognize pattern instantly in real PR.

For Argo CD users, compare helm diff output to Argo CD UI diff side-by-side in training—sources differ when post-renderers or kustomize overlays involved—explain which diff is authoritative for each pipeline architecture.
""",
    "devops-helm-governance-standards": """
## Sunset non-compliant charts

Policy: charts failing governance CI cannot publish new versions to internal catalog—existing versions grandfathered with expiry date. Grandfather without expiry becomes permanent debt—6 month sunset max. Teams migrate or accept no CVE patches from catalog—motivation strong enough to adopt platform-lib.

Publish monthly "standards score" per engineering group—gamification optional but visibility drives VP-level prioritization of tech debt sprints for chart compliance without security scare tactics alone.
""",
    "devops-helm-hooks-weight-order": """
## Uninstall hook ordering

`pre-delete` hooks for final backup or audit export run before resources removed—weight more negative than app deletion. Teams forget uninstall hooks—orphaned cloud resources when Helm release deleted but S3 bucket hook failed silently. Test `helm uninstall` in ct pipeline—not only install/upgrade path.

Helm 3 wait on uninstall hooks—timeout applies; long backup hook needs `--timeout` on uninstall automation matching backup duration—document in runbook for service decommissioning checklist.
""",
    "devops-helm-library-chart-patterns": """
## Documenting template function API

Each `define` in platform-lib gets godoc-style comment block: parameters via Values keys, example invocation, semver introduced, semver deprecated. Auto-generate docs from comments in CI published to internal portal—consumers search "platform.probes" before guessing Values shape.

Load test library render: 100 concurrent `helm template` runs in CI—detect race in shared temp files if library uses disk in helper—should be pure; performance regression on large monorepo chart releases.
""",
    "devops-helm-rollback-strategies": """
## Insurance: revision export cron

Nightly CronJob exports `helm get manifest` for tier-1 releases to S3 versioned bucket—disaster when etcd corrupted and Helm history lost—rare but cheap insurance. Restore procedure documented: reinstall from exported manifest with same release name—test in staging annually.

Coordinate with GitOps: exported manifest must match Git desired state—drift between export and Git triggers investigation—either Git wrong or manual cluster edit—both need remediation before next deploy.
""",
    "devops-helm-secrets-sops": """
## Cross-border and residency

SOPS KMS keys per region—EU prod secrets decrypt only with eu-west-1 KMS key—developers in US cannot decrypt EU secrets on laptop—policy enforcement via IAM on KMS key policy. Residency audits ask where plaintext ever exists—decrypt only in CI runner in-region, never on developer machine for prod paths.

Rotation table: secret name, last rotated, next due, owner team—automated issue 14 days before due—SOPS files updated in PR with security reviewer—same process as certificate renewal.
""",
    "devops-helm-values-schema-validation": """
## Teaching teams to read schema errors

CI comment on schema failure translates JSON Schema path to Values YAML line—custom wrapper around helm install error parsing `on path replicaCount` → link to values.yaml line via yq. Reduces platform support load from cryptic `Invalid type` messages.

Schema review in chart PR: required fields justified—every required key is one more footgun for consumers—prefer sensible defaults in templates with optional schema fields—required only for security/compliance labels cannot default.

## Aligning schema with CRD OpenAPI

When chart installs CRDs with OpenAPI validation, values.schema should not contradict CRD schema—conflicting max length on field causes Helm pass, API server reject on apply—test with server-side dry-run in CI on rendered CR manifests. Single team owns alignment between chart values and CRD schema generation if using kubebuilder.
""",
    "devops-helmfile-multi-env": """
## Disaster recovery for helmfile operations

Document rebuild from scratch: clone repo, restore kubeconfig contexts, `helmfile -e prod apply` idempotent if releases already exist—Helm upgrades in place. If cluster total loss, helmfile apply order via `needs` rebuilds dependency order—verify CRD chart first in separate helmfile wave—platform wave 0 CRDs, wave 1 platform, wave 2 apps.

Secrets in helmfile repos use SOPS—DR runbook includes decrypt key recovery from vault—without key, helmfile apply renders incomplete—DR drill includes secrets key availability not just Git clone.
""",
    "devops-horizontal-pod-autoscaler-custom-metrics": """
## Capacity planning with custom metrics

Before enabling HPA on queue metric, math: at maxReplicas, can workers drain max observed queue depth within SLO? If not, maxReplicas insufficient—fix before enabling autoscaling false confidence. Load test saturates queue producer while watching scale-up lag—scale-up too slow increases stabilizationWindow or pre-warm minReplicas during known peaks.

Document metric ownership—who fixes Prometheus adapter rule when service renames metric? Metric rename without adapter update freezes HPA at min—alert on `hpa_metric_missing` custom rule when metrics API returns 404 for configured metric name.
""",
    "devops-iam-policy-simulator": """
## Continuous verification in production

Weekly batch job simulates critical deny/allow cases against production role ARNs read-only—detect policy drift from Terraform state if someone attached policy manually in console—simulation result mismatch opens sev2 ticket. IAM Access Analyzer new findings feed same queue—external S3 access finding plus failed deny simulation on DeleteObject equals urgent review.

Integrate simulator into service catalog—scaffolding new microservice generates IAM policy JSON + test matrix PR template—author fills actions list, CI runs simulation before human review—shift-left for new services not only policy changes.
""",
}


def body_words(path):
    return len(WORD.findall(path.read_text().split("---", 2)[2]))


def main():
    for slug, block in BLOCKS.items():
        path = BLOG / f"{slug}.md"
        if body_words(path) >= 1200:
            print(f"skip {slug}")
            continue
        content = path.read_text()
        if block.strip()[:40] in content:
            print(f"dup {slug}")
            continue
        if MARKER not in content:
            print(f"no marker {slug}")
            continue
        path.write_text(content.replace(MARKER, block + MARKER))
        print(f"ok {slug} -> {body_words(path)}")


if __name__ == "__main__":
    main()
