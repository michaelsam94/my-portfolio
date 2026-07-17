#!/usr/bin/env python3
"""Topic-specific second-pass expansion for posts under 1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD = re.compile(r"\b[\w'-]+\b")

EXTRA = {
    "devops-gitops-observability-metrics": """
## Incident timeline: six hours of false green

Reconstructing a real sync stall helps prioritize metrics. T0: merge to main. T+2m: CI green. T+5m: Argo CD reports Synced—controller fetched Git at commit A. T+15m: manual `kubectl set image` hotfix on cluster (outside Git). T+20m: engineer reverts hotfix in cluster; Application still Synced to commit A which still references broken tag. T+6h: customer reports stale feature; on-call sees Synced/Healthy; only repo-server logs show repeated manifest generate errors from invalid Helm values skipped by `ignoreMissingValueFiles`.

Fix checklist: alert on manifest generation error rate; compare deployed image digest annotation to CI-published digest; page when `Healthy` but deployment generation lag > 2 behind Git. Flux equivalent: watch `Ready=False` on Kustomization with message containing `build failed`.
""",
    "devops-gitops-policy-enforcement": """
## Emergency merge lane without disabling policy

Break-glass should not mean `ClusterPolicy` deleted. Pattern: dedicated `break-glass` namespace excluded from enforce policies **only** via time-boxed PolicyException approved in ticket system, with automatic Kyverno cleanup Job removing exception after TTL. All break-glass Deployments require annotation `break-glass/ticket: INC-1234` validated by admission. Post-incident: conftest replay on merged YAML proves normal path would have caught issue—feeds back into policy rule additions.

For OPA, use `dryrun` enforcement mode on new Constraint for one sprint—collect denials as metrics before flipping to deny. Teams see PolicyViolation events in Grafana before merge blocked—reduces surprise and shadow IT kubectl applies.
""",
    "devops-gitops-preview-environments": """
## Staging shared dependencies safely

When preview API calls real payment sandbox, rotate sandbox keys per preview namespace via ExternalSecret template keyed by PR number—prevents cross-preview idempotency key collisions on Stripe test mode. Document which dependencies are mocked (email, SMS) vs real (auth OIDC test realm shared). Load tests against preview should rate-limit—one PR load test must not DDoS shared staging IdP.

ApplicationSet generator requeue interval trades freshness for API rate limits—GitHub App installations hitting abuse detection during heavy PR days need backoff jitter and conditional generation on label `preview/wanted`.
""",
    "devops-gitops-promotion-environments": """
## Binary promotion vs config promotion metrics

Track separately: `deploy_promotion_image` (digest changed) and `deploy_promotion_config` (ConfigMap/Helm values only). Config-only promotions skip container build CI but still need staging soak—feature flag enabled in staging Monday, prod Wednesday, incident Thursday when flag assumes API field exists in old binary. Pair config promotion with minimum app version annotation in ConfigMap validated by admission webhook.

Monorepo promotion: only promote packages affected by diff—Argo CD ApplicationSet git generator path filter prevents promoting unchanged services when sibling team merges docs.
""",
    "devops-gitops-rollback-strategies": """
## Revision ledger automation

CI job on every prod sync posts to internal deploy API:

```json
{"app":"checkout","revision":42,"git_sha":"abc","digest":"sha256:...","chart":"api-2.3.0","timestamp":"..."}
```

Rollback UI queries API for last three `verified=true` entries—on-call clicks rollback target; bot opens Git PR with exact file restores. Eliminates guessing Helm revision numbers under stress. For database coupled releases, ledger includes `schema_version` from migration Job logs—rollback button disabled when schema incompatible unless runbook override with DBA ack.
""",
    "devops-gitops-sealed-secrets": """
## SealedSecrets rotation day runbook

Hour 0: announce maintenance. Hour 1: deploy controller with new key alongside old (multi-key supported). Hour 2–4: CI re-seals all SealedSecrets; merge PRs per cluster. Hour 5: validate sample Secret checksum in app. Hour 6: remove old key from controller; archive old private key in vault with expiry. Hour 7: verify Argo CD sync still green. Rollback: keep old key until all SealedSecrets re-sealed successfully—do not delete old key first.

For SOPS, `sops updatekeys` on all files; developers must pull before edit—conflicts on MAC lines resolved by re-downloading from main, never hand-merging ciphertext.
""",
    "devops-global-load-balancer-health": """
## Readiness contract with product

Product defines `/ready` SLA: which features must work for traffic (checkout yes, recommendations no). Document in OpenAPI `x-readiness-tier`. LB health check matches tier—prevents draining pod because optional recommendation model cold-starting. During partial outage, app can expose `/ready/degraded` internally while LB still uses stricter `/ready`—two endpoints avoid gaming health while enabling graceful degradation inside mesh.

Regional failover runbook: mark region unhealthy manually when control plane blind—automated health may lag during AWS API impairment; runbook includes health check disable steps with executive comms template.
""",
    "devops-gpu-node-scheduling": """
## Node image and driver pinning

GPU node AMI: pin NVIDIA driver 535.x + container toolkit 1.14.x tested against ML base image matrix. Automated weekly job runs `nvidia-smi` + sample CUDA matmul on new AMI candidate before rolling node pool. MIG reconfiguration requires node cordon—schedule maintenance window; training jobs checkpoint before drain.

Spot GPU nodes: label `lifecycle=spot`; training jobs tolerate spot with checkpoint; inference on on-demand pool only unless SLO allows cold start. Cluster autoscaler priority expander prefers spot pool for batch Job, on-demand for Deployment.
""",
    "devops-gpu-scheduling-ml-workloads": """
## Inference SLO during training season

Black Friday: inference tier gets temporary quota borrow from training pool via Kueue `cohort` configuration—training preemptible entire week, revert Monday automation. Communicate via internal status page. Metrics dashboard: `gpu_hours_by_class` stacked area chart—finance and SRE share single view.

Multi-model inference server: one GPU serves three models with dynamic batching—HPA on `batch_queue_depth` not per-model CPU. Model A latency regression may need model-specific metric adapter rule—document in model card which PromQL drives its scale.
""",
    "devops-grafana-dashboard-as-code": """
## Panel query review in PR

Require PR screenshot from ephemeral Grafana for any panel query change—visual diff catches unit mistakes (`milliseconds` vs `seconds` in PromQL). `grafonnet` unit tests render JSON; human review catches "chart looks empty." For Terraform-managed dashboards, `terraform plan` JSON diff noisy—use `grafana/dashboard-json-diff` tooling or OPA on panel count limits preventing accidental deletion.

Disaster recovery: export all dashboards nightly to S3 via Grafana API—Git is primary, S3 backup if repo corruption. RTO target: restore dashboards in 15m without hand-clicking UI.
""",
    "devops-headroom-policy-enforcement": """
## Executive narrative for idle capacity

Finance asks why CPUs at 35% idle—translate headroom policy into incident cost: last year one scheduling failure during launch cost $X revenue; headroom target 25% costs $Y annual idle. Data wins budget when quantified. Include spot/dev pool rightsizing separately—do not cut prod headroom to fund dev waste.

Automated rightsizing (VPA recommendations) feeds back into quota requests—team whose VPA suggests 2x over-requested CPU gets quota review before increase approved. Headroom policy is dynamic negotiation, not static cap.
""",
    "devops-helm-chart-signing-provenance": """
## Registry mirror verification chain

Primary Harbor → DR mirror async replication. Consumers verify cosign on pull from DR—signatures replicate with artifact. If DR serves unsigned copy during failover, install blocked—document emergency unsigned procedure with dual-control approval. Quarterly drill: fail primary, deploy from DR, measure RTO including verify latency.

Helm classic repo users migrating to OCI: re-sign all active chart versions on OCI before decommissioning HTTP index—clients on old helm versions may not verify—track client upgrade metric before cutoff.
""",
    "devops-helm-chart-testing-ct-lint": """
## Performance regression in chart CI

Measure `ct install` duration trend—chart complexity creep slows every PR. Threshold: install test > 8 minutes triggers chart refactor ticket (subchart split, reduce hooks). Kind cluster reuse vs fresh cluster tradeoff: reuse faster but state leak between tests—namespace per test with finalizers check.

Security scan gate: Trivy on packaged chart must fail CRITICAL unless documented exception CVE with expiry. Exceptions live in `.trivyignore` with comment linking ticket—reviewed monthly.
""",
    "devops-helm-dependency-management": """
## Subchart CVE response play

Trivy alerts CVE in embedded postgresql subchart: assess runtime exposure (subchart disabled in prod?), upgrade path via dependency bump PR, emergency patch if exploit active. If upstream no fix, NetworkPolicy restrict postgres Service to app namespace only—document compensating control until bump merges.

Dependency graph visualization in CI comment on Renovate PR—shows transitive depth; depth > 3 triggers architecture review for new umbrella chart proposals.
""",
    "devops-helm-diff-pre-deploy": """
## Diff ownership in CODEOWNERS

`values/prod.yaml` changes require service owner + platform review when diff touches ClusterRole, PersistentVolume, or Ingress host. GitHub CODEOWNERS + automated diff keyword match assigns reviewers—reduces `$` eyes on 4000-line prometheus diff missing one ClusterRole rule change.

Store diff artifacts 90 days in object storage for compliance—link from change ticket. Redact Secret values but retain key names changed—auditors verify intentional credential rotation vs accidental deletion.
""",
    "devops-helm-governance-standards": """
## Onboarding new team to paved road

Day 1: fork helm-starter, run CI, deploy to dev namespace via GitOps. Platform office hours review first chart PR against rubric—not blocking but educational. Within 30 days team must own dashboard and on-call for their chart—governance includes operability not just YAML style.

Violation trend report to engineering leadership monthly: top policy denials by rule—if `missing-readiness-probe` dominates, improve starter template; if `privileged` denials spike, security training targeted at one division.
""",
    "devops-helm-hooks-weight-order": """
## Hook timeout vs migration duration

Flyway migration exceeding Helm `--timeout` leaves release pending-upgrade—document expected migration duration in chart README; CI enforces migration completes in < 5m on fixture DB or split migrations across releases. Long migrations run as separate Kubernetes Job outside Helm hook with manual gate—Helm hook only for fast idempotent schema steps.

Observability: hook Job duration histogram by chart version—detect migration slowdown before prod upgrade (DB lock contention visible in staging hook duration trend).
""",
    "devops-helm-library-chart-patterns": """
## Consumer upgrade communication

platform-lib 1.5.0 release notes auto-post to Slack #platform-changes with diff of rendered `helm template` for reference consumer chart—teams preview impact before Renovate PR merges. Breaking change office hours scheduled for major bumps—recorded for async zones.

Count consumers via CI inventory scanning Chart.yaml dependencies across org GitHub—orphan consumers on ancient library version flagged for deprecation sunset.
""",
    "devops-helm-rollback-strategies": """
## Game day: rollback under load

Quarterly: production-like staging with continuous load generator; deploy bad chart version; measure MTTR for atomic rollback vs manual Git revert while error budget burns. Document winner per service tier—tier-1 may mandate atomic for all Helm upgrades.

Post-rollback verification script: smoke test + compare ConfigMap hash to expected from revision ledger—human clicks "rollback complete" only after script green—prevents premature incident close.
""",
    "devops-helm-secrets-sops": """
## Developer ergonomics without plaintext leaks

`direnv` loads SOPS_AGE_KEY_FILE only in approved directories—leaving repo unsets env. VS Code task `sops edit secrets.prod.enc.yaml` wraps editor—no plaintext file on disk after save. Git pre-commit rejects files matching `secrets.*.yaml` without `.enc` suffix except `.example` templates.

Onboarding: new engineer generates age key, security adds to KMS/team keyring, never commits private key—first exercise decrypt and re-encrypt dummy secret in training sandbox repo.
""",
    "devops-helm-values-schema-validation": """
## Schema evolution without breaking consumers

Adding required field `team` in schema major bump—CI on consumer repos pins parent chart `<2.0` until they add field. Gradual: schema marks field required in chart 2.0 but template defaults `team: unknown` with Prometheus metric counting Deployments using default—sunset default in 3.0.

Document every values key in README table generated from schema descriptions—single source via `helm schema --help` custom tool or redocly on exported JSON Schema for internal portal search.
""",
    "devops-helmfile-multi-env": """
## Partial apply during incidents

During ingress controller emergency, `helmfile -l name=ingress-nginx -e prod apply` limits blast radius—document label conventions on every release in helmfile. Without labels, teams grep helmfile during incident—error prone.

helmfile `missingFileHandler: Error` prevents silent skip when environment values file path typo—default Warn caused prod deploy with dev-sized replicas when `environments/prod.yaml` missing from typo `environments/prod.yml`.
""",
    "devops-horizontal-pod-autoscaler-custom-metrics": """
## Fallback when metrics disappear

HPA v2 with multiple metrics uses max desired replica count across metrics—pair external queue metric with CPU floor so metric outage does not scale to min while CPU pegged. Document fallback behavior in runbook: if Prometheus adapter down, manually raise `minReplicas` via emergency values PR—do not rely on HPA alone.

KEDA ScaledObject plus HPA on same Deployment forbidden—pick one scaler; if migrating Prometheus HPA to KEDA, delete HPA first in same PR as ScaledObject add to avoid dual controllers fighting.
""",
    "devops-iam-policy-simulator": """
## Terraform plan peer review cues

Reviewers scan plan for `aws_iam_role_policy_attachment` adding managed policies—always simulate effective policy after attachment. Red flag strings in JSON policy: `"Action": "*", "Resource": "*"` even in Deny—Deny * on * breaks unexpectedly with service-linked roles.

Joiner onboarding: new engineer runs simulator lab—three exercises allow/deny S3 paths with MFA condition—before prod IAM PR approval privileges granted. Reduces "helpful" broad policy additions from inexperienced contributors.
""",
}


def wc(path):
    p = path.read_text().split("---", 2)
    return len(WORD.findall(p[2] if len(p) >= 3 else ""))


def main():
    for slug, text in EXTRA.items():
        path = BLOG / f"{slug}.md"
        if wc(path) >= 1200:
            print(f"skip {slug} {wc(path)}")
            continue
        content = path.read_text()
        marker = "\n## Resources\n"
        if "## Incident timeline:" in content or "## Emergency merge lane" in content or text.strip()[:30] in content:
            # idempotent check on first line of extra
            key = text.strip().split("\n")[1][:20]
            if key in content:
                print(f"dup {slug}")
                continue
        path.write_text(content.replace(marker, text + marker))
        print(f"ok {slug} {wc(path)} -> {wc(path)}")


if __name__ == "__main__":
    main()
