#!/usr/bin/env python3
"""Boost 11 Helm posts to >=1200 words with topic-specific sections."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
M = "\n## Resources\n"
WORD = re.compile(r"\b[\w'-]+\b")

SLUGS = [
    "devops-helm-chart-signing-provenance",
    "devops-helm-chart-testing-ct-lint",
    "devops-helm-dependency-management",
    "devops-helm-diff-pre-deploy",
    "devops-helm-governance-standards",
    "devops-helm-hooks-weight-order",
    "devops-helm-library-chart-patterns",
    "devops-helm-rollback-strategies",
    "devops-helm-secrets-sops",
    "devops-helm-values-schema-validation",
    "devops-helmfile-multi-env",
]

# Unique marker per slug to avoid double-insert
MARKERS = {
    "devops-helm-chart-signing-provenance": "## Registry mirror and verify chain",
    "devops-helm-chart-testing-ct-lint": "## Upgrade-from-N-1 CI matrix",
    "devops-helm-dependency-management": "## Transitive CVE and Renovate hygiene",
    "devops-helm-diff-pre-deploy": "## Post-renderer diff parity",
    "devops-helm-governance-standards": "## Tier-1 launch gate integration",
    "devops-helm-hooks-weight-order": "## Hook failure observability",
    "devops-helm-library-chart-patterns": "## Consumer semver contract",
    "devops-helm-rollback-strategies": "## Revision ledger automation",
    "devops-helm-secrets-sops": "## KMS condition keys and rotation",
    "devops-helm-values-schema-validation": "## Nested subchart schema composition",
    "devops-helmfile-multi-env": "## Terraform boundary and DR",
}

BLOCKS = {
    "devops-helm-chart-signing-provenance": """
## Registry mirror and verify chain

Primary and disaster-recovery OCI registries replicate chart blobs asynchronously. Consumers must verify cosign signatures on the artifact they actually pull—whether from primary or DR—not assume replication preserved signature metadata. Quarterly failover drill: block primary registry, deploy from DR, confirm `cosign verify` succeeds with same certificate identity policy. Document emergency unsigned install procedure with dual-control approval; audit log retention seven years if regulated.

Supply-chain tabletop: red team publishes unsigned chart to test registry; blue team detects via verify failure in CI and blocks GitOps sync. Measure detection time; close gaps where only CI verifies but Argo CD repo-server pulls without verify. Integrate Sigstore policy-controller ClusterImagePolicy for clusters that install charts outside GitOps path.

Partner charts under contract may require in-region signing keys—map cluster region to trusted cosign public key set. Export-controlled artifacts need attestation predicate documenting build jurisdiction. Trivy scan remains mandatory; signature proves publisher identity, not absence of CVEs.

Dual-control for prod signing: two platform engineers required for KMS-backed cosign sign in release pipeline—no single actor publishes tier-1 chart. Key ceremony minutes stored for SOC2—cosign.pub in Git alone insufficient evidence of key handling discipline.
""",
    "devops-helm-chart-testing-ct-lint": """
## Upgrade-from-N-1 CI matrix

Fresh `ct install` misses upgrade-order bugs. Maintain CI job: install chart revision N-1 from OCI, upgrade to PR version with all `ci/*.yaml` fixtures, assert hooks and migrations succeed. Pin N-1 version in `ci/upgrade-from-version.txt` updated by release bot on tag—upgrade test never drifts from reality.

Kind cluster version may lag prod by at most one minor Kubernetes version—upgrade Kind quarterly. API drift between CI and prod manifests as chart passes CI but fails server-side apply in prod—document supported K8s window in chart README.

Parallelize ct across chart directories in monorepos—matrix from `ct list-changed` output—wall clock under fifteen minutes or developers bypass gate. Cache `helm dependency build` keyed on Chart.lock hash.

Track ct flake rate; above two percent triggers infrastructure fix—not disabling ct. Trivy CRITICAL on packaged tgz fails unless documented exception with expiry. NetworkPolicy tests require Kind CNI that enforces policies—otherwise false confidence.
""",
    "devops-helm-dependency-management": """
## Transitive CVE and Renovate hygiene

`helm dependency list` exposes transitive bumps invisible in parent Chart.yaml diff—CI comment on Renovate PR shows tree. Subchart disabled in prod values still vendored in tgz—scan for CVE exposure; remove unused deps.

HTTP chart museum sunset: batch migrate repository fields to OCI in single integration-tested PR—stragglers on deprecated index miss security patches. Chart.lock digest must match vendored tgz after update—CI fails on mismatch.

Change freeze before major sales events: disable Renovate auto-merge for helm deps—manual CVE triage only—communicate resume date in platform calendar. Air-gap: commit vendored charts/ with lock digests verified on USB transfer into isolated CI.

Document pin rationale in Chart.yaml comments—why postgresql 15.2.4 not 16.x—prevents reckless major Renovate merge breaking app compatibility.
""",
    "devops-helm-diff-pre-deploy": """
## Post-renderer diff parity

When kustomize post-renderer mutates Helm output, `helm diff` must use identical wrapper—diff without renderer shows false negative. Platform script `helm-diff-safe` injects `POST_RENDERER_PATH` from environment—CI fails if unset.

Summarize large diffs: count changes by kind before human reads four thousand lines—Deployment +2 ~1, ClusterRole +1 flags platform review. Store diff artifacts ninety days; hash retained longer for audit.

Fork PRs without cluster access: diff rendered manifest against last-deployed artifact in S3—not live cluster—security isolation without skipping review. Hotfix still runs diff or requires break-glass ticket with CISO approval.

On-call shell alias includes kubecontext guard—prompt shows context name—prevents diffing prod while believing staging. Teach diff literacy in onboarding week two—fresh eyes catch ClusterRole changes veterans skim.
""",
    "devops-helm-governance-standards": """
## Tier-1 launch gate integration

Non-compliant tier-1 charts block feature launch in release management tool—PM sees actionable platform message not mysterious infra denial. Compliance score weighted by customer traffic—low-traffic internal tools lower priority than checkout chart gaps.

Security champions in each division review chart PRs within twenty-four hours—trained on conftest rules not ad hoc opinions. Random quarterly audit of five production Deployments against rubric—gaps are platform debt not team shame.

Contractors: read-only catalog, publish requires staff sponsor merge—offboard same-day cosign key access removal. Forked upstream charts require FORK.md divergence doc—quarterly upstream merge evaluation—Renovate tracks upstream tags.

Sunset non-compliant catalog versions after six-month grandfather—no CVE patches for ancient versions—forces migration. Executive scoreboard by org unit—transparency beats nag email.
""",
    "devops-helm-hooks-weight-order": """
## Hook failure observability

PrometheusRule pages on Job failure with label `helm.sh/hook` for tier-1 releases—distinct from app pod crash runbooks. Loki label `component=helm-hook` retains logs before hook-delete-policy removes pods.

Hook Job resource requests must match worst-case migration memory measured in staging—OOM mid-migration leaves schema half-applied. Chart README includes hook order diagram—PR checklist verifies diagram matches annotations.

Pre-upgrade migration while old pods serve traffic can lock tables—prefer expand-contract migrations allowing parallel old/new code. Hook ServiceAccount with cluster-admin blocked unless ADR attached—scoped Role for migration Job.

Test `helm uninstall` in ct—not only install/upgrade—pre-delete hooks for backup export often forgotten. Uninstall `--timeout` must exceed longest backup hook duration in runbook for decommissioning checklist.
""",
    "devops-helm-library-chart-patterns": """
## Consumer semver contract

platform-lib breaking changes require major semver, migration guide, and example consumer re-render diff in release notes. CI matrix renders representative consumers against library N, N-1, N+1 beta—catch accidental breaking minor before publish.

Monorepo: batch library bump weekly release train—thirty charts do not each get independent Renovate noise—emergency CVE excepted. `.Capabilities.KubeVersion` gates API versions—Kind matrix 1.27 and 1.29 in parallel CI—document supported K8s window in README.

Library templates must not use `lookup` without documenting non-deterministic GitOps render—prefer explicit values. Quarterly survey: missing helpers, wrong defaults, persistent copy-paste—prioritize roadmap from answers not guesses.

Platform office hours demo library bump with three consumer renders recorded for async zones—visual confidence before merge.
""",
    "devops-helm-rollback-strategies": """
## Revision ledger automation

CI posts deploy record on prod sync: app, Helm revision, git SHA, image digest, chart version, timestamp, schema_version from migration logs. Rollback UI offers last three verified entries—on-call selects target; bot opens Git PR restoring exact files—eliminates revision roulette under stress.

SEV1 runbook: customer mitigation (traffic shift, feature flag) may precede helm rollback when faster—rollback still required to align Git. Post-incident document if forward-fix chosen without rollback—consistent precedent matters.

Export `helm get manifest` nightly for tier-1 to versioned S3—disaster recovery if etcd history lost—test restore in staging annually. Windows chart rollback needs longer `--timeout`—separate runbook section linked from main header.

Rollback drill metrics in engineering all-hands—MTTR trend justifies platform investment—quarterly timed exercise includes GitOps re-alignment step not helm alone.
""",
    "devops-helm-secrets-sops": """
## KMS condition keys and rotation

Restrict SOPS KMS decrypt to CI OIDC role and break-glass role ARNs—developers use workflow dispatch for decrypt audit trail not laptop KMS access. Dual-key overlap during rotation—`sops updatekeys` on all files before removing old key—stagger repo-server and CI rollout.

Pre-commit rejects `secrets.yaml` without `.enc` suffix except `.example` templates. Gitleaks on ephemeral decrypt in CI only—never persist plaintext artifacts. New hire lab: encrypt/decrypt dummy secret before prod repo access granted.

Break-glass decrypt requires manager ticket approval—security Slack notification—seven-day usage review—remove unused break-glass paths from runbook. Rotation calendar for static API keys—fourteen-day automated reminder before SOPS file stale.

Compare ESO for high-churn creds vs SOPS for static bootstrap—hybrid common—document ADR with review date for auditors asking why ciphertext in Git.
""",
    "devops-helm-values-schema-validation": """
## Nested subchart schema composition

Parent schema documents subchart keys matching Chart.yaml dependency aliases—typo `postgress` fails fast. `additionalProperties: false` on known subchart sections catches typos; allow extension at root via team-specific wrapper schema merging platform schema URL with `allOf`.

Helm dry-run validates types not business rules—conftest checks `replicaCount * cpu_request` against namespace quota on rendered manifests—schema plus policy layers together.

Schema changelog auto-generated in release pipeline—required fields added/removed/types changed—consumers scan before Renovate merge. Example values per environment validate against schema in CI—examples rot slower than prose.

IDE integration: publish schema `$id` to internal HTTPS—VS Code yaml.schemas auto-validates values on edit—reduces Slack questions to platform team.
""",
    "devops-helmfile-multi-env": """
## Terraform boundary and DR

Document handoff: Terraform owns cluster and VPC; helmfile owns in-cluster releases—overlap causes double CNI install fights—architecture diagram mandatory for new hires. Emergency `helmfile apply -l name=X` in runbook limits blast radius during multi-release incidents.

`missingFileHandler: Error` prevents silent skip when `environments/prod.yaml` typo—Warn caused prod deploy with dev-sized replicas historically. helmfile validate in pre-commit for platform engineers—cheap YAML typo catch.

Scheduled prod vs staging resource count parity job—flags missing release after prod-only hotfix—exclusions config for intentional replica differences. DR: clone repo, restore kubecontext secrets, `helmfile -e prod apply` idempotent—secrets SOPS keys in vault recovery step documented.

Gotmpl must not render plaintext secrets to disk—vals refs only—CI scans gotmpl output for password patterns. Pin `helmBinary` path in CI image—mac vs linux template drift resolved by devcontainer matching CI.
""",
}


def wc_body(text: str) -> int:
    parts = text.split("---", 2)
    return len(WORD.findall(parts[2] if len(parts) >= 3 else ""))


def main():
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        raw = path.read_text()
        marker = MARKERS[slug]
        if marker in raw:
            print(f"skip {slug} (already boosted)")
            continue
        if M not in raw:
            print(f"error {slug}: no Resources")
            continue
        before = wc_body(raw)
        path.write_text(raw.replace(M, BLOCKS[slug] + M))
        after = wc_body(path.read_text())
        print(f"{slug}: {before} -> {after}")


if __name__ == "__main__":
    main()
