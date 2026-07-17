#!/usr/bin/env python3
"""Final pass: unique closing sections to reach >=1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD = re.compile(r"\b[\w'-]+\b")
M = "\n## Resources\n"

FINAL = {
"devops-gitops-promotion-environments": """
## Closing the loop with deployment notifications

Wire Argo CD notifications to post promotion PR links when prod Application sync completes—Slack message includes prior staging digest, prod digest, and diff summary. Engineers correlate user reports with exact promotion within minutes. When notification shows unexpected digest, freeze further promotions until drift investigation completes—often reveals manual sync or wrong overlay path merged without review.
""",
"devops-gitops-rollback-strategies": """
## Training rollbacks in calm weather

New on-call engineers perform staged rollback in training cluster quarterly—timed exercise with rubric: identify good revision, execute Git restore, verify metrics recovery, write incident timeline draft. Untrained rollback during real incident adds 30+ minutes of Helm revision archaeology—cheaper to practice with synthetic bad deploy on staging labeled `rollback-drill`.
""",
"devops-gitops-sealed-secrets": """
## Vault vs Git encryption decision record

Document ADR: why SealedSecrets chosen over Vault ESO for bootstrap tokens only, with review date. ADR stale after two years triggers reevaluation—org may have adopted Vault HA since original decision—migrate without big-bang by moving high-churn secrets first. Audit asks for ADR link during SOC2—keep in repo adjacent to sealing scripts.
""",
"devops-global-load-balancer-health": """
## Edge cases with sidecars and mTLS

Service mesh sidecars may expose admin port healthy while app container wedged—target health check at app port directly, not sidecar inbound unless mesh documents app health delegated correctly. mTLS between LB and pod requires health check client cert rotation same as data plane—expired cert marks all backends unhealthy simultaneously—monitor cert expiry independently of app certs.
""",
"devops-gpu-node-scheduling": """
## Scheduling latency SLO

Track time from pod create to GPU allocated—long queue indicates need more nodes or better quota policy, not user error. Publish P95 scheduling latency to ML platform dashboard—when P95 exceeds 10 minutes, auto-page platform even if jobs eventually schedule—user experience degraded before pending forever.
""",
"devops-gpu-scheduling-ml-workloads": """
## Cold start and model load time

Inference HPA must account for model load duration on new pod—readiness probe should fail until model weights loaded from object storage—otherwise HPA scales out pods that pass TCP health but serve 503 until load completes—users see errors during scale event. Pre-warm minReplicas during known traffic; use init container downloading weights before marking ready.
""",
"devops-grafana-dashboard-as-code": """
## Accessibility and on-call stress

Dashboard JSON includes human-readable panel descriptions for screen readers where Grafana supports—during incident, panel titles must state unit and threshold explicitly (`p99 latency seconds`) not cryptic `query A`—grafonnet helper enforces title format in CI lint. Dark mode consistent via theme in provisioning—on-call at 3am benefits from contrast standards not cosmetic preference.
""",
"devops-headroom-policy-enforcement": """
## Seasonal capacity planning

Retail peaks need temporary headroom bump via documented change ticket—raise cluster quota and lower alert thresholds 30 days before event—revert after postmortem. Automate seasonal profile in Git for alert thresholds—PR merged by platform each October—reduces manual dashboard edits forgotten until mid-peak.
""",
"devops-helm-chart-signing-provenance": """
## Supply chain tabletop exercise

Annual exercise: red team publishes unsigned chart to test registry—blue team detects via verify failure alerts and blocks deploy pipeline—measure detection time. Findings update verify coverage gaps—e.g., GitOps path not verifying OCI digest pin—close loop with engineering ticket same sprint.
""",
"devops-helm-chart-testing-ct-lint": """
## Parallel ct for monorepos

Shard chart directories across CI matrix jobs—ct list-changed output fed to matrix strategy—total wall clock under 15 minutes for 100 chart repo—developers do not bypass CI waiting for serial Kind installs. Cache helm dependency build between jobs keyed on Chart.lock hash—speed without stale vendor risk if lock committed.
""",
"devops-helm-dependency-management": """
## Air-gap dependency vendoring

Air-gapped cluster cannot reach bitnami repo—CI vendors tgz into Git; air-gap transfer bundle includes charts/ directory verified by digest against Chart.lock—manual step checklist on USB transfer—simulate quarterly. Missing subchart in bundle fails closed at helm dependency build in air-gap CI before any apply attempt—prevents half-deployed umbrella.
""",
"devops-helm-diff-pre-deploy": """
## Diff noise reduction for operators

Teach helm diff `--suppress-secrets` default in wrapper script; separate `--show-secrets` break-glass for security reviewers only—reduces accidental secret leak in Slack diff bot. For 5000 line diffs, generate summary count by kind changed—Deployment +2 -0 ~1—human reads summary first, full diff on demand—incident speed without missing ClusterRole +1.
""",
"devops-helm-governance-standards": """
## Executive reporting without vanity metrics

Report percent compliant charts weighted by customer traffic—100% compliant low-traffic internal tool matters less than tier-1 checkout chart compliance—prioritize platform reviews accordingly. Non-compliant tier-1 chart blocks feature launches in release process—product management understands governance as launch gate not bureaucracy.
""",
"devops-helm-hooks-weight-order": """
## Hook resource limits

Migration hook Job without resource requests can land on overloaded node—hook timeout—failed upgrade—set hook Job requests equal to worst-case migration memory profile measured in staging. CPU limit optional for Java migrations—avoid OOMKill mid-migration leaving schema half-applied—use activeDeadlineSeconds on Job as backstop with alert.
""",
"devops-helm-library-chart-patterns": """
## Backward compatibility testing matrix

CI matrix renders consumer charts against platform-lib N, N-1, N+1 beta—detect accidental breaking change in minor release before publish—semver discipline enforced mechanically not by honor system. Consumers pin but Renovate bumps quickly—minor breaking hurts many teams—matrix prevents.
""",
"devops-helm-rollback-strategies": """
## Customer communication template library

Rollback triggers comms template selection: data loss risk, feature unavailable, performance degraded—legal pre-approved sentences—on-call picks template not freehand writing during stress—reduce accidental over-promising recovery time—link templates from runbook next to helm rollback commands.
""",
"devops-helm-secrets-sops": """
## Secret scanning in encrypted repos

Gitleaks on decrypted output in CI only—never commit decrypt to persistent artifact—ephemeral workspace destroyed post-job—detects accidental plaintext commit in values file adjacent to enc file—common mistake copying example to wrong filename—block merge on `password:` pattern in non-enc yaml paths.
""",
"devops-helm-values-schema-validation": """
## Consumer wrapper charts

Team wraps platform chart with thin wrapper adding team-specific required values in wrapper schema—composition via JSON Schema allOf merging platform schema URL with local extensions—platform publishes schema artifact per chart version—wrapper references immutable URL—upgrade platform chart requires wrapper schema revalidation in same PR—prevents silent incompat.
""",
"devops-helmfile-multi-env": """
## helmfile and Terraform boundary

Document when helmfile ends and Terraform begins—Terraform owns cluster, helmfile owns in-cluster releases—overlap causes double VPC CNI config fights—architecture diagram in README mandatory for new platform hires—helmfile not used to install Terraform-managed add-ons without explicit handoff doc—reduces circular dependencies during incidents.
""",
"devops-horizontal-pod-autoscaler-custom-metrics": """
## Testing scale-down behavior

Load test followed by idle period—verify scale-down removes pods without killing in-flight requests—PodDisruptionBudget minAvailable interacts with HPA scale-down—document maxUnavailable during scale-down for stateful connections—WebSocket services may set minReplicas equal to peak always—accept cost over flappy scale-down—metric documented in service SLO doc.
""",
"devops-iam-policy-simulator": """
## Privilege boundary for CI simulation role

CI role running simulator needs iam:SimulatePrincipalPolicy but not iam:*—tight policy on CI role itself—ironic broad CI role undermines simulation program—review CI role quarterly same as production roles—simulation pipeline compromise equals policy exfiltration risk—run in isolated AWS account for policy testing if possible.
""",
}


def wc(path):
    return len(WORD.findall(path.read_text().split("---", 2)[2]))


def main():
    for slug, block in FINAL.items():
        p = BLOG / f"{slug}.md"
        if wc(p) >= 1200:
            print(f"skip {slug} {wc(p)}")
            continue
        c = p.read_text()
        if block.strip()[:50] in c:
            print(f"dup {slug}")
            continue
        p.write_text(c.replace(M, block + M))
        print(f"ok {slug} -> {wc(p)}")


if __name__ == "__main__":
    main()
