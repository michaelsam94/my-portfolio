#!/usr/bin/env python3
"""Generate Batch C DevOps blog posts (devops-* slugs)."""

import os
import textwrap
from datetime import date, timedelta

BLOG_DIR = "/Users/michael/Desktop/my-portfolio/content/blog"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATE = date(2026, 3, 1)
TARGET_WORDS = 900

FOOTER = textwrap.dedent("""\

## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.

## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.

## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.

## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.

## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.
""")


RAW_TOPICS = [
    ('Kubernetes', 'pod-disruption-budgets', 'Pod Disruption Budgets for Safe Cluster Upgrades', 'Design PodDisruptionBudgets that protect quorum during node drains, cluster upgrades, and Karpenter consolidation.', 'DevOps|Kubernetes|SRE', 'PodDisruptionBudget, PDB, node drain', 'At 2 a.m. during a node pool upgrade, Redis Sentinel lost quorum because three pods were evicted simultaneously.', 'PodDisruptionBudget', 'Before enabling cluster autoscaler consolidation or your first production node drain.', 'Setting minAvailable to 100% on stateless Deployments blocks all voluntary evictions.'),
    ('Kubernetes', 'vertical-pod-autoscaler', 'Vertical Pod Autoscaler: Recommendations vs Auto Mode', 'Operate VPA in recommendation or auto mode: right-size requests, avoid OOM loops, and coordinate with HPA.', 'DevOps|Kubernetes|Cost Optimization', 'VPA, vertical pod autoscaler, right-sizing', 'Finance flagged 40% over-provisioned CPU requests while pods averaged a fraction of allocated resources.', 'Vertical Pod Autoscaler', 'Enable VPA recommendations first on batch tiers before auto mode.', 'Running VPA auto on the same Deployment as HPA on CPU causes scaling fight loops.'),
    ('Kubernetes', 'horizontal-pod-autoscaler-custom-metrics', 'HPA with Custom and External Metrics', 'Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2.', 'DevOps|Kubernetes|Observability', 'HPA, custom metrics, KEDA', 'Checkout latency breached SLO while CPU sat flat—queue depth existed but HPA watched CPU only.', 'HPA v2', 'When CPU/memory do not correlate with user-visible latency or backlog.', 'Scaling on CPU alone during I/O-bound spikes never adds pods.'),
    ('Kubernetes', 'network-policies-default-deny', 'Kubernetes Network Policies: Default Deny Baseline', 'Implement default-deny network policies with explicit egress and ingress allowlists.', 'DevOps|Kubernetes|Security', 'network policy, default deny', 'Compliance demanded default-deny; the first policy broke DNS because kube-dns egress was missing.', 'NetworkPolicy', 'Roll out namespace by namespace after inventorying flows.', 'Applying deny-all without DNS egress breaks every pod overnight.'),
    ('Kubernetes', 'resource-quota-limitrange', 'ResourceQuota and LimitRange for Multi-Tenant Namespaces', 'Govern namespace consumption with ResourceQuota and LimitRange defaults.', 'DevOps|Kubernetes|Platform', 'ResourceQuota, LimitRange', 'Notebooks requested 8 CPU each with no limits and starved production scheduling.', 'ResourceQuota', 'When onboarding tenant namespaces or opening self-service namespace creation.', 'Quotas without LimitRange let pods with missing requests bypass fairness.'),
    ('Kubernetes', 'ingress-nginx-rate-limiting', 'Ingress-NGINX Rate Limiting and Edge Protection', 'Configure NGINX Ingress rate limits, connection limits, and edge throttling.', 'DevOps|Kubernetes|Security', 'ingress-nginx, rate limiting', 'A scraping bot hammered search at 2k RPS before application-level limits existed.', 'Ingress-NGINX', 'Before public launch or after abuse on unauthenticated endpoints.', 'Global limits that throttle health checks flip synthetic monitors.'),
    ('Kubernetes', 'etcd-backup-restore-ops', 'etcd Backup and Restore Operations', 'Automate etcd snapshots, validate restore drills, and document RTO.', 'DevOps|Kubernetes|SRE', 'etcd backup, snapshot, restore', 'Restored etcd from a snapshot taken mid-compaction—it was unusable.', 'etcd snapshots', 'For every self-managed control plane before declaring DR complete.', 'Backups without tested restore are wishful thinking.'),
    ('Kubernetes', 'karpenter-nodepool-tuning', 'Karpenter NodePool Tuning for Cost and Speed', 'Configure Karpenter NodePools: instance families, consolidation, limits.', 'DevOps|Kubernetes|Cost Optimization', 'Karpenter, NodePool, consolidation', 'Spot reclamation spiked; batch jobs restarted because consolidation was too aggressive.', 'Karpenter NodePool', 'When moving from Cluster Autoscaler or when spot interruptions spike.', 'Allowing all instance types picks wrong shapes for workloads.'),
    ('Kubernetes', 'secrets-store-csi-driver', 'Secrets Store CSI Driver with External Secrets', 'Mount cloud secrets via CSI and sync rotation with External Secrets Operator.', 'DevOps|Kubernetes|Security', 'Secrets Store CSI, External Secrets', 'Weekly DB password rotation required rolling restarts across twelve services.', 'Secrets Store CSI', 'When eliminating secret env vars or meeting short-lived credential compliance.', 'Mounts without rotation polling leave pods on stale credentials.'),
    ('Kubernetes', 'topology-spread-constraints', 'Topology Spread Constraints for Zone Balance', 'Spread pods across zones and nodes with topologySpreadConstraints.', 'DevOps|Kubernetes|SRE', 'topologySpreadConstraints, multi-AZ', 'An AZ power event took 80% of API pods because replicas piled into one zone.', 'topologySpreadConstraints', 'For tier-1 services before declaring multi-AZ HA complete.', 'DoNotSchedule with skew 1 and too few replicas blocks scheduling.'),
    ('Kubernetes', 'cluster-autoscaler-overprovision', 'Cluster Autoscaler Over-Provisioning Patterns', 'Use overprovision deployments and priority classes to reduce scale-up latency.', 'DevOps|Kubernetes|Capacity', 'cluster autoscaler, overprovision', 'Black Friday traffic spiked; new nodes took eight minutes while pending pods queued.', 'Cluster Autoscaler', 'When pending pod duration during scale-up breaches SLO.', 'Overprovision without priority classes wastes budget 24/7.'),
    ('Kubernetes', 'gpu-node-scheduling', 'GPU Node Scheduling and Fractional GPUs', 'Schedule ML workloads on GPU nodes with device plugins, taints, and MIG.', 'DevOps|Kubernetes|MLOps', 'GPU scheduling, device plugin', 'Training jobs pending-scheduled for hours because GPU nodes ran default workloads.', 'GPU device plugin', 'Before production ML training or inference on Kubernetes.', 'Missing taints let non-GPU workloads consume expensive GPU nodes.'),
    ('Kubernetes', 'priority-classes-preemption', 'PriorityClasses and Preemption for Critical Workloads', 'Define PriorityClasses so critical pods preempt lower-priority batch work safely.', 'DevOps|Kubernetes|SRE', 'PriorityClass, preemption', 'Critical payment pods pending while batch analytics consumed the entire node pool.', 'PriorityClass', 'When batch and latency-sensitive workloads share clusters.', 'Overusing system-cluster-critical devalues the entire priority model.'),
    ('Kubernetes', 'init-containers-migration', 'Init Containers for Migration and Bootstrap', 'Use init containers for schema migration, config fetch, and dependency wait logic.', 'DevOps|Kubernetes|Platform', 'init containers, bootstrap', 'App containers started before Flyway finished—500 errors until manual restart.', 'init containers', 'When apps need ordered startup beyond simple probes.', 'Heavy migration logic in init without timeout leaves pods stuck Init:0/1.'),
    ('Kubernetes', 'sidecar-containers-native', 'Native Sidecar Containers in Kubernetes 1.29+', 'Adopt native sidecar containers for logging, mesh, and proxy lifecycle ordering.', 'DevOps|Kubernetes|Platform', 'sidecar containers, lifecycle', 'Istio sidecar terminated before app flushed buffers during rollout.', 'native sidecar containers', 'When upgrading to Kubernetes 1.29+ with service mesh or log agents.', 'Mixing classic and native sidecars without restartPolicy causes confusion.'),
    ('Kubernetes', 'cronjob-timezone-dst', 'CronJob Timezone and DST-Safe Scheduling', 'Run CronJobs with correct timezones and avoid DST duplicate/skipped runs.', 'DevOps|Kubernetes|SRE', 'CronJob, timezone, DST', 'Billing CronJob ran twice on DST fall-back—double charges until rollback.', 'CronJob timeZone', 'For finance, billing, or compliance jobs tied to local midnight.', 'UTC-only CronJobs that ignore business timezone requirements.'),
    ('Kubernetes', 'job-backoff-limits-parallelism', 'Job Backoff Limits and Parallelism Tuning', 'Configure Job backoffLimit, parallelism, and completions for batch reliability.', 'DevOps|Kubernetes|Data Engineering', 'Kubernetes Job, backoffLimit', 'A poison message retried 10k times before backoff—cluster API throttled.', 'Kubernetes Job', 'Before production batch pipelines on native Jobs.', 'Unbounded parallelism overwhelming downstream databases.'),
    ('Kubernetes', 'statefulset-rolling-update', 'StatefulSet Rolling Update Strategies', 'Manage StatefulSet partition updates, OnDelete strategy, and PVC retention.', 'DevOps|Kubernetes|SRE', 'StatefulSet, rolling update', 'Rolling update restarted all Kafka brokers simultaneously despite partition setting.', 'StatefulSet', 'For stateful tiers before first in-place version upgrade.', 'Deleting StatefulSet with wrong PVC retention policy loses data.'),
    ('Kubernetes', 'daemonset-upgrade-strategy', 'DaemonSet Upgrade and Surge Patterns', 'Upgrade DaemonSet agents with maxUnavailable tuning.', 'DevOps|Kubernetes|Platform', 'DaemonSet, rolling update', 'Log agent upgrade left 30% of nodes on old version—blind spot during incident.', 'DaemonSet', 'Before upgrading CNI, log, or security DaemonSets fleet-wide.', 'maxUnavailable 100% on single-replica-per-node DaemonSets.'),
    ('Kubernetes', 'configmap-hot-reload', 'ConfigMap Hot Reload Without Pod Restart', 'Reload configuration from ConfigMaps using watchers, sidecars, or Reloader.', 'DevOps|Kubernetes|Platform', 'ConfigMap, hot reload', 'Feature flag change required full Deployment restart for one boolean.', 'ConfigMap reload', 'When config changes are frequent and restarts are costly.', 'Assuming kubelet sync instantly updates in-memory app config.'),
    ('Kubernetes', 'downward-api-metadata', 'Downward API for Pod Metadata Injection', 'Expose labels, annotations, and resource limits to containers via Downward API.', 'DevOps|Kubernetes|Platform', 'Downward API, metadata', 'Observability agent could not tag metrics with pod version—hardcoded in env.', 'Downward API', 'When apps need self-aware metadata without hardcoding.', 'Projecting sensitive annotations into env visible to all containers.'),
    ('Kubernetes', 'ephemeral-storage-limits', 'Ephemeral Storage Limits and Eviction', 'Set ephemeral-storage requests/limits and monitor emptyDir pressure.', 'DevOps|Kubernetes|SRE', 'ephemeral storage, eviction', 'Log-heavy pod filled node disk; kubelet evicted unrelated production pods.', 'ephemeral-storage', 'For workloads writing logs, caches, or temp files to emptyDir.', 'Missing ephemeral limits on log or download workloads.'),
    ('Kubernetes', 'taints-tolerations-nodepools', 'Taints, Tolerations, and Dedicated Node Pools', 'Isolate workloads with taints, tolerations, and dedicated node pools.', 'DevOps|Kubernetes|Platform', 'taints, tolerations', 'GPU and batch workloads competed on same nodes—p99 latency collapsed.', 'taints and tolerations', 'When mixing latency-sensitive and batch/GPU tiers in one cluster.', 'NoEffect tolerations that do not match node taints.'),
    ('Kubernetes', 'custom-scheduler-plugins', 'Custom Scheduler Plugins and Scheduling Profiles', 'Extend kube-scheduler with plugins for topology, cost, or compliance scoring.', 'DevOps|Kubernetes|Platform', 'scheduler plugins', 'Compliance required EU-only nodes; default scheduler ignored region labels.', 'scheduler plugins', 'When default scoring cannot express cost, compliance, or affinity rules.', 'Custom scheduler without fallback profile blocks all scheduling.'),
    ('Kubernetes', 'api-server-audit-logging', 'API Server Audit Logging for Security and Forensics', 'Configure audit policies, log backends, and retention for API forensics.', 'DevOps|Kubernetes|Security', 'audit logging, API server', 'Post-incident: no record of who applied cluster-admin RoleBinding.', 'API audit policy', 'Before SOC2 audit or after suspicious RBAC change.', 'Logging RequestResponse for all resources—etcd-sized log volumes.'),
    ('Kubernetes', 'rbac-least-privilege', 'RBAC Least Privilege for Platform Teams', 'Design Role bindings with least privilege and break-glass paths.', 'DevOps|Kubernetes|Security', 'RBAC, least privilege', 'Contractor retained cluster-admin six months after offboarding.', 'Kubernetes RBAC', 'During tenant onboarding and quarterly access reviews.', 'ClusterRole aggregates that grant wildcard verbs silently.'),
    ('Kubernetes', 'service-account-iam-roles', 'IRSA and Workload Identity for Service Accounts', 'Bind service accounts to cloud IAM roles without static keys.', 'DevOps|Kubernetes|Security', 'IRSA, workload identity', 'Long-lived AWS keys in Secrets leaked via compromised pod.', 'IRSA', 'When pods call cloud APIs—S3, SQS, Secrets Manager.', 'Annotating wrong IAM role ARN—silent permission failures.'),
    ('Kubernetes', 'cert-manager-letsencrypt-dns01', "cert-manager DNS-01 with Let's Encrypt", 'Automate TLS with cert-manager, DNS-01 challenges, and wildcard certificates.', 'DevOps|Kubernetes|Security', 'cert-manager, DNS-01', 'HTTP-01 failed for internal services; wildcard cert manual renewal expired.', 'cert-manager', 'When services are not publicly reachable for HTTP-01 validation.', 'DNS-01 without restricted IAM on Route53.'),
    ('Helm', 'helm-chart-testing-ct-lint', 'Helm Chart Testing with chart-testing and helm-unittest', 'Validate Helm charts before release with ct lint/install and helm-unittest.', 'DevOps|Kubernetes|Helm', 'chart-testing, helm-unittest', 'Chart bump removed securityContext; Argo synced valid YAML but pods failed admission.', 'chart-testing', 'Before publishing charts to OCI.', 'ct without helm-unittest misses template logic regressions.'),
    ('Helm', 'helm-dependency-management', 'Helm Dependency Management and Subchart Patterns', 'Manage Helm dependencies: conditions, aliases, OCI registries, Chart.lock.', 'DevOps|Kubernetes|Helm', 'Helm dependencies, Chart.lock', 'Umbrella chart floating redis range changed persistence defaults.', 'Helm dependencies', 'When composing platform charts with stateful subcharts.', 'Floating dependency ranges on stateful subcharts.'),
    ('Helm', 'helm-oci-registry-migration', 'Migrating Helm Charts to OCI Registries', 'Publish and consume Helm charts from OCI instead of HTTP chart repos.', 'DevOps|Helm|Supply Chain', 'Helm OCI, chart registry', 'HTTP chart repo outage blocked all deploys for four hours.', 'Helm OCI registry', 'During chart repo consolidation.', 'OCI push without immutability—tags overwritten.'),
    ('Helm', 'helmfile-multi-env', 'Helmfile for Multi-Environment Deployments', 'Orchestrate multi-env Helm releases with helmfile and gotmpl.', 'DevOps|Helm|GitOps', 'helmfile, multi-environment', 'Twelve near-identical helm upgrade scripts drifted within a month.', 'helmfile', 'When managing more than three environment-specific releases.', 'helmfile without version pinning on remote repos.'),
    ('Helm', 'helm-hooks-weight-order', 'Helm Hooks: Weights, Ordering, and Cleanup', 'Configure pre/post install hooks with correct weights and delete policies.', 'DevOps|Kubernetes|Helm', 'Helm hooks, hook-weight', 'DB migration hook ran after app pods—schema mismatch outage.', 'Helm hooks', 'When charts run migrations via hooks.', 'hook-delete-policy without idempotent hooks.'),
    ('Helm', 'helm-values-schema-validation', 'Helm Values Schema Validation', 'Enforce values.schema.json on charts to reject invalid input early.', 'DevOps|Kubernetes|Helm', 'Helm values schema', 'Typo set replicas to string—HPA ignored it.', 'values.schema.json', 'When platform charts are consumed by many teams.', 'Schema too permissive—allows dangerous requests.'),
    ('Helm', 'helm-secrets-sops', 'Helm Secrets with SOPS', 'Encrypt Helm values with SOPS; decrypt in CI and GitOps.', 'DevOps|Helm|Security', 'Helm secrets, SOPS', 'Plaintext DB passwords in values.yaml in Git history.', 'SOPS', 'When secrets must live in Git for GitOps.', 'SOPS keys in same repo as encrypted files.'),
    ('Helm', 'helm-diff-pre-deploy', 'Helm Diff Before Deploy in CI', 'Run helm diff in CI to show manifest changes before upgrade.', 'DevOps|Helm|CI/CD', 'helm diff, CI', 'Blind upgrade changed ClusterIP to LoadBalancer.', 'helm diff', 'On every production chart upgrade PR.', 'Diff against wrong release name.'),
    ('Helm', 'helm-rollback-strategies', 'Helm Rollback Strategies and Release History', 'Plan Helm rollback, history limits, and atomic upgrades.', 'DevOps|Kubernetes|Helm', 'Helm rollback, atomic', 'Rollback to revision 3 restored broken config.', 'Helm rollback', 'Before first production Helm upgrade on tier-1.', '--atomic without adequate probe timeouts.'),
    ('Helm', 'helm-library-chart-patterns', 'Helm Library Chart Patterns for DRY Templates', 'Extract shared templates into library charts.', 'DevOps|Kubernetes|Helm', 'Helm library chart', 'Four teams copied identical label helpers—drift broke selectors.', 'library charts', 'When three or more charts duplicate helpers.', 'Library chart version not pinned.'),
    ('Helm', 'helm-post-renderer-kustomize', 'Helm Post-Renderers with Kustomize', 'Patch Helm output with kustomize post-renderer.', 'DevOps|Helm|GitOps', 'Helm post-renderer, kustomize', 'Vendor chart could not add required pod labels.', 'Helm post-renderer', 'When upstream charts cannot be modified.', 'Post-renderer patches not tested in CI.'),
    ('Helm', 'helm-release-health-checks', 'Helm Release Health Checks and Wait Logic', 'Configure --wait, --timeout, and resource readiness.', 'DevOps|Kubernetes|Helm', 'Helm wait, readiness', 'Helm reported deployed while pods CrashLoopBackOff.', 'Helm --wait', 'On all automated Helm upgrades.', 'Timeout too short for slow-start JVM.'),
    ('Helm', 'helm-chart-signing-provenance', 'Helm Chart Signing and Provenance', 'Sign charts with cosign and verify before install.', 'DevOps|Helm|Security', 'Helm signing, cosign', 'Compromised chart mirror served modified templates.', 'cosign chart signing', 'Before adopting third-party charts.', 'Verification in CI but not in GitOps controller.'),
    ('Helm', 'helm-governance-standards', 'Helm Chart Governance and Platform Standards', 'Establish org-wide Helm standards and review gates.', 'DevOps|Helm|Platform', 'Helm governance', 'Incident traced to chart missing probes.', 'Helm standards', 'When more than five teams publish internal charts.', 'Standards documented but not enforced in CI.'),
    ('Terraform', 'terraform-remote-state-locking', 'Terraform Remote State and Locking', 'Configure remote backends with state locking and encryption.', 'DevOps|Terraform|Platform', 'Terraform remote state, locking', 'Two engineers applied simultaneously—state corruption and duplicate VPCs.', 'Terraform remote state', 'Before team grows beyond one Terraform operator.', 'Local state files on laptops for shared infrastructure.'),
    ('Terraform', 'terraform-workspace-strategy', 'Terraform Workspace Strategy for Environments', 'Use workspaces vs separate state keys for dev/staging/prod isolation.', 'DevOps|Terraform|Platform', 'Terraform workspace, environments', 'Prod destroy targeted dev workspace due to wrong -workspace flag.', 'Terraform workspaces', 'When defining multi-environment Terraform layout.', 'Single workspace for all envs without naming guards.'),
    ('Terraform', 'terraform-module-versioning', 'Terraform Module Versioning and Semver', 'Pin module versions with semver ranges and changelog discipline.', 'DevOps|Terraform|Platform', 'Terraform modules, semver', 'Floating git ref module introduced breaking change on Friday deploy.', 'Terraform modules', 'When consuming internal or public Terraform modules.', 'Module sources without version pin—main branch breaks prod.'),
    ('Terraform', 'terraform-drift-detection', 'Terraform Drift Detection and Remediation', 'Detect and remediate infrastructure drift with scheduled plans.', 'DevOps|Terraform|SRE', 'Terraform drift, remediation', 'Console hotfix during incident never codified—drift hid for months.', 'Terraform drift detection', 'Weekly on production workspaces minimum.', 'Drift alerts without ownership—noise ignored until audit.'),
    ('Terraform', 'terraform-import-existing', 'Terraform Import for Existing Resources', 'Import brownfield resources without recreation.', 'DevOps|Terraform|Platform', 'Terraform import, brownfield', 'Import recreated RDS instance—brief outage during wrong resource address.', 'terraform import', 'When bringing existing cloud resources under IaC.', 'Import without plan review—unintended destroys in apply.'),
    ('Terraform', 'terraform-moved-blocks-refactor', 'Terraform moved Blocks for Safe Refactoring', 'Use moved blocks instead of state mv for module refactors.', 'DevOps|Terraform|Platform', 'Terraform moved blocks', 'Module refactor destroyed and recreated load balancer—DNS flap.', 'moved blocks', 'During module restructuring without resource replacement.', 'Manual state mv scripts not run in CI—drift between envs.'),
    ('Terraform', 'terraform-policy-as-code-sentinel', 'Terraform Policy as Code with Sentinel/OPA', 'Enforce guardrails on plans with Sentinel or OPA policies.', 'DevOps|Terraform|Security', 'Terraform policy, Sentinel, OPA', 'Public S3 bucket merged because no policy gate on plan.', 'Terraform policy', 'Before self-service Terraform for application teams.', 'Policies only on apply—not on speculative plans in PRs.'),
    ('Terraform', 'terraform-cloud-run-tasks', 'Terraform Cloud Run Tasks and Private Agents', 'Run Terraform in TFC/TFE with private agents and run tasks.', 'DevOps|Terraform|CI/CD', 'Terraform Cloud, run tasks', 'Sensitive plan output logged in shared CI artifact.', 'Terraform Cloud', 'When using HCP Terraform or self-hosted TFE.', 'Public agents reaching private endpoints without tunnel.'),
    ('Terraform', 'terraform-provider-pinning', 'Terraform Provider Version Pinning', 'Pin provider versions in required_providers and lock file.', 'DevOps|Terraform|Platform', 'Terraform providers, lock file', 'AWS provider upgrade changed default tags—unexpected bill allocation.', 'required_providers', 'On every Terraform root module from day one.', 'Missing dependency lock file—CI and laptop resolve different versions.'),
    ('Terraform', 'terraform-terragrunt-dry', 'Terragrunt for DRY Terraform at Scale', 'Use Terragrunt for remote state, dependencies, and DRY configs.', 'DevOps|Terraform|Platform', 'Terragrunt, DRY Terraform', 'Copy-pasted backend config across forty root modules.', 'Terragrunt', 'When managing dozens of similar Terraform roots.', 'Terragrunt without explicit dependency blocks—race on apply.'),
    ('Terraform', 'terraform-k8s-provider-context', 'Terraform Kubernetes Provider Context Safety', 'Manage multiple cluster contexts safely in Terraform k8s provider.', 'DevOps|Terraform|Kubernetes', 'Terraform kubernetes provider', 'Terraform applied to prod cluster using stale kubeconfig context.', 'kubernetes provider', 'When Terraform manages in-cluster resources.', 'Provider alias omitted—wrong cluster targeted silently.'),
    ('Terraform', 'terraform-aws-eks-module', 'Terraform AWS EKS Module Operations', 'Operate the terraform-aws-modules/eks module: node groups, IRSA, addons.', 'DevOps|Terraform|Kubernetes', 'terraform-aws-modules eks', 'EKS upgrade skipped addon compatibility—CoreDNS pending.', 'terraform-aws-modules/eks', 'When provisioning or upgrading EKS with Terraform.', 'Managed node group max unavailable too aggressive during upgrade.'),
    ('Terraform', 'terraform-plan-comment-pr', 'Terraform Plan Comments on Pull Requests', 'Post speculative plans as PR comments with cost estimation.', 'DevOps|Terraform|CI/CD', 'Terraform plan, PR comments', 'Reviewer approved without reading plan—security group opened 0.0.0.0/0.', 'Terraform plan in PR', 'On every infrastructure pull request.', 'Plan from wrong working directory—misleading comment.'),
    ('Terraform', 'terraform-state-migration', 'Terraform State Migration Between Backends', 'Migrate state between S3, GCS, and Terraform Cloud safely.', 'DevOps|Terraform|Platform', 'Terraform state migration', 'State migration interrupted—partial write required manual recovery.', 'state migration', 'When changing backend or consolidating workspaces.', 'Migration without backup snapshot of state file.'),
    ('Terraform', 'terraform-destroy-guardrails', 'Terraform Destroy Guardrails', 'Prevent accidental terraform destroy with policies and workflow gates.', 'DevOps|Terraform|Security', 'Terraform destroy, guardrails', 'Intern ran destroy on wrong workspace—prod VPC gone.', 'terraform destroy', 'Before granting Terraform access beyond platform team.', 'Destroy allowed from local laptops without approval.'),
    ('Terraform', 'terraform-dynamic-blocks', 'Terraform Dynamic Blocks for Scalable Config', 'Use dynamic blocks for repeated nested config without copy-paste.', 'DevOps|Terraform|Platform', 'Terraform dynamic blocks', 'Forty copy-pasted ingress rules—one typo opened wrong port.', 'dynamic blocks', 'When nested blocks repeat per tenant or region.', 'Dynamic block key errors—silent omission of rules.'),
    ('Terraform', 'terraform-test-framework', 'Terraform Test Framework for Module Validation', 'Write terraform test blocks for module regression testing.', 'DevOps|Terraform|Testing', 'Terraform test, module testing', 'Module change broke output—consumers failed without module CI.', 'terraform test', 'When publishing modules to internal registry.', 'Tests run only locally—never in module publish pipeline.'),
    ('Terraform', 'terraform-backstage-integration', 'Terraform Backstage Software Templates', 'Integrate Terraform provisioning with Backstage scaffolder templates.', 'DevOps|Terraform|Platform', 'Backstage, Terraform templates', 'Self-service infra requests via Slack—no audit trail or standards.', 'Backstage scaffolder', 'When enabling developer self-service infrastructure.', 'Templates without policy checks—everyone provisions oversized RDS.'),
    ('CI/CD', 'github-actions-reusable-workflows', 'GitHub Actions Reusable Workflows for Platform CI', 'Extract reusable workflow patterns for build, test, and deploy across repos.', 'DevOps|CI/CD|Platform', 'GitHub Actions, reusable workflows', 'Twelve repos copied identical deploy YAML—security patch required twelve PRs.', 'GitHub Actions reusable workflows', 'When more than five repos share identical pipeline stages.', 'Reusable workflows without version pinning—@main breaks consumers.'),
    ('CI/CD', 'gitlab-ci-child-pipelines', 'GitLab CI Child Pipelines and DAG Orchestration', 'Split monorepo CI with child pipelines, needs, and artifact passing.', 'DevOps|CI/CD|Platform', 'GitLab CI, child pipelines', 'Monorepo pipeline ran 4 hours on every doc change—no path rules.', 'GitLab child pipelines', 'For monorepos with independent service deploy cycles.', 'Child pipeline without needs—race on shared staging deploy.'),
    ('CI/CD', 'tekton-pipeline-caching', 'Tekton Pipeline Caching and Workspace Optimization', 'Optimize Tekton workspaces, volume caches, and task runtimes.', 'DevOps|CI/CD|Kubernetes', 'Tekton, pipeline caching', 'Container builds re-downloaded 2GB base image every commit.', 'Tekton pipelines', 'When running CI on Kubernetes with Tekton.', 'EmptyDir workspaces without size limits—node disk pressure.'),
    ('CI/CD', 'argo-workflows-data-pipelines', 'Argo Workflows for Data and ML Pipelines', 'Run batch and ML pipelines with Argo Workflows on Kubernetes.', 'DevOps|CI/CD|MLOps', 'Argo Workflows, data pipelines', 'Cron-based ML training on Jenkins agent ran out of disk silently.', 'Argo Workflows', 'When migrating batch/ML jobs to Kubernetes-native orchestration.', 'Workflow templates without retry limits—runaway pod creation.'),
    ('CI/CD', 'jenkins-shared-libraries', 'Jenkins Shared Libraries and Pipeline Governance', 'Centralize Jenkins pipeline logic in versioned shared libraries.', 'DevOps|CI/CD|Platform', 'Jenkins shared libraries', 'Copy-pasted Groovy deploy scripts diverged—prod deploy used stale credentials ID.', 'Jenkins shared libraries', 'When Jenkins remains primary CI for legacy or regulated workloads.', 'Shared library @Library without version—breaking change on main.'),
    ('CI/CD', 'circleci-orb-patterns', 'CircleCI Orbs and Config Reuse', 'Publish and consume CircleCI orbs for standardized jobs.', 'DevOps|CI/CD|Platform', 'CircleCI orbs', 'Orb update changed Docker login step—every project pipeline failed Monday.', 'CircleCI orbs', 'For CircleCI shops standardizing deploy and scan jobs.', 'Unpinned orb versions in config—silent breaking changes.'),
    ('CI/CD', 'pipeline-oidc-aws-gcp', 'CI/CD OIDC Federation for Cloud Deploy', 'Replace long-lived cloud keys in CI with OIDC workload identity.', 'DevOps|CI/CD|Security', 'CI OIDC, workload identity', 'Leaked GitHub Actions AWS key in fork PR—read access to prod S3.', 'CI OIDC federation', 'When any CI pipeline assumes cloud IAM roles.', 'OIDC trust policy too broad—any repo in org can assume prod role.'),
    ('CI/CD', 'dind-rootless-buildkit', 'Rootless BuildKit and Docker-in-Docker Alternatives', 'Build container images in CI without privileged DinD where possible.', 'DevOps|CI/CD|Security', 'BuildKit, rootless, DinD', 'Privileged DinD container escape CVE forced emergency CI lockdown.', 'rootless BuildKit', 'When hardening CI runners or migrating from docker.sock mounts.', 'Kaniko without cache—build times 10x, teams bypass with DinD.'),
    ('CI/CD', 'container-image-signing-cosign', 'Container Image Signing with Cosign in CI', 'Sign and verify container images in CI/CD with cosign and policy controllers.', 'DevOps|CI/CD|Security', 'cosign, image signing, supply chain', 'Compromised base image replaced in registry—deploy pulled malicious layer.', 'cosign', 'Before enforcing admission policies on image signatures.', 'Sign in CI but no cluster-side verification—signatures ignored.'),
    ('CI/CD', 'sbom-generation-syft', 'SBOM Generation with Syft and Grype in CI', 'Generate SBOMs on build and scan for CVEs before deploy gates.', 'DevOps|CI/CD|Security', 'SBOM, Syft, Grype, supply chain', 'Log4j-style CVE in transitive dep—no inventory until auditor asked.', 'Syft SBOM', 'For regulated industries or SLSA-oriented supply chain programs.', 'SBOM generated but never stored—cannot diff between releases.'),
    ('CI/CD', 'deployment-gates-smoke-tests', 'Deployment Gates and Post-Deploy Smoke Tests', 'Block promotion until smoke tests pass against canary or staging.', 'DevOps|CI/CD|SRE', 'deployment gates, smoke tests', 'Pipeline green but prod 500s—health check only hit /health not /api/v1/orders.', 'deployment gates', 'On every automated production promotion path.', 'Smoke tests hitting mocks—not real downstream dependencies.'),
    ('CI/CD', 'blue-green-cd-implementation', 'Blue-Green CD Implementation on Kubernetes', 'Implement blue-green deploys with Service selectors, Ingress weights, or Argo Rollouts.', 'DevOps|CI/CD|Kubernetes', 'blue-green, CD, Kubernetes', 'Blue-green switch flipped before DB migration finished—split-brain writes.', 'blue-green deployment', 'When zero-downtime cutover is required for stateless tiers.', 'Both colors sharing write DB without migration coordination.'),
    ('CI/CD', 'canary-cd-analysis', 'Canary CD with Automated Analysis', 'Run canary deploys with metric-based promotion and rollback.', 'DevOps|CI/CD|SRE', 'canary deployment, Flagger, Argo Rollouts', 'Manual canary promotion at 50% traffic—error rate doubled before anyone noticed.', 'canary analysis', 'When progressive delivery replaces big-bang deploys.', 'Canary without error budget guardrails—promote on gut feel.'),
    ('CI/CD', 'feature-flag-cd-integration', 'Feature Flag Integration in CD Pipelines', 'Decouple deploy from release using feature flags in CD workflows.', 'DevOps|CI/CD|Platform', 'feature flags, CD', 'Deploy rollback for dark-launched feature—unnecessary full revert.', 'feature flags in CD', 'When shipping code daily but releasing features weekly.', 'Flags without cleanup—dead code paths accumulate security debt.'),
    ('CI/CD', 'pipeline-secret-scanning', 'Secret Scanning in CI Pipelines', 'Block merges when gitleaks or trufflehog detect secrets in diffs.', 'DevOps|CI/CD|Security', 'secret scanning, gitleaks', 'API key committed in test fixture—rotated after GitHub alert 48 hours later.', 'secret scanning', 'On every repository before granting CI cloud credentials.', 'Scan only main branch—secrets merge via PR then deleted.'),
    ('CI/CD', 'monorepo-path-filters', 'Monorepo Path Filters and Affected Targets', 'Run CI only for changed paths in monorepos with path filters and bazel/gazelle.', 'DevOps|CI/CD|Platform', 'monorepo, path filters', 'Every commit ran full 90-minute test suite for typo in README.', 'path filters', 'When monorepo CI exceeds 30 minutes without code changes.', 'Path filter too aggressive—missed shared library change impact.'),
    ('GitOps', 'argocd-app-of-apps', 'Argo CD App of Apps Bootstrap Pattern', 'Bootstrap cluster add-ons and tenant apps with Argo CD app-of-apps.', 'DevOps|GitOps|Kubernetes', 'Argo CD, app of apps', 'Manual kubectl apply for platform addons—drift from Git within a week.', 'Argo CD app of apps', 'When bootstrapping new clusters from Git.', 'App of apps repo without RBAC—any dev syncs cluster-wide resources.'),
    ('GitOps', 'argocd-sync-waves-hooks', 'Argo CD Sync Waves and Resource Hooks', 'Order deployments with sync waves, hooks, and Replace sync options.', 'DevOps|GitOps|Kubernetes', 'Argo CD sync waves', 'CRD applied after CustomResource—controller crash loop until manual reorder.', 'Argo CD sync waves', 'When GitOps repos mix CRDs, operators, and app manifests.', 'Sync wave annotations undocumented—new resources race on every sync.'),
    ('GitOps', 'flux-helm-controller', 'Flux Helm Controller and HelmRelease Ops', 'Manage Helm releases with Flux HelmRelease and HelmRepository sources.', 'DevOps|GitOps|Helm', 'Flux, HelmRelease', 'Helm upgrade outside Flux—GitOps controller reverted hotfix on next reconcile.', 'Flux HelmRelease', 'When standardizing on Flux over Argo for Helm-heavy shops.', 'HelmRelease without rollback test—failed upgrade stuck in Failed state.'),
    ('GitOps', 'flux-image-automation', 'Flux Image Automation and Policy', 'Automate image tag updates with Flux image automation controllers.', 'DevOps|GitOps|CI/CD', 'Flux image automation', 'Manual image tag bumps in Git—deploy lagged registry by three days.', 'Flux image automation', 'When teams want continuous deploy from CI-built images.', 'ImagePolicy allowing latest tag—non-reproducible prod deploys.'),
    ('GitOps', 'gitops-promotion-environments', 'GitOps Promotion Across Environments', 'Promote manifests dev→staging→prod with Kustomize overlays and PR gates.', 'DevOps|GitOps|Platform', 'GitOps promotion, environments', 'Prod hotfix applied directly to prod overlay—never backported to dev.', 'GitOps promotion', 'When more than two environments sync from Git.', 'Direct prod commits bypassing staging PR review.'),
    ('GitOps', 'gitops-drift-detection', 'GitOps Drift Detection and Self-Heal', 'Configure self-heal, diff alerts, and ignore differences for secrets.', 'DevOps|GitOps|SRE', 'GitOps drift, self-heal', 'On-call kubectl patched Deployment—self-heal reverted fix during incident.', 'GitOps drift detection', 'Always—self-heal without diff alerts hides intentional break-glass edits.', 'Ignoring all diffs on Secrets—plaintext drift undetected.'),
    ('GitOps', 'gitops-sealed-secrets', 'Sealed Secrets and SOPS in GitOps', 'Encrypt secrets in Git with Sealed Secrets or SOPS for GitOps repos.', 'DevOps|GitOps|Security', 'Sealed Secrets, SOPS, GitOps', 'Plaintext Secret committed—history scrub required audit finding.', 'Sealed Secrets', 'When GitOps repos must contain Kubernetes Secret manifests.', 'Sealed secret key loss—cannot rotate or unseal during disaster.'),
    ('GitOps', 'gitops-rollback-strategies', 'GitOps Rollback Strategies', 'Rollback by Git revert vs Argo/Flux history vs Helm rollback.', 'DevOps|GitOps|SRE', 'GitOps rollback', 'Git revert of merge commit reintroduced old bug—rollback made things worse.', 'GitOps rollback', 'Before first production GitOps incident response drill.', 'Rollback without pinning previous image digest—registry garbage collected tag.'),
    ('GitOps', 'gitops-multi-cluster', 'GitOps for Multi-Cluster Fleet Management', 'Manage fleet of clusters with ApplicationSet or Flux multi-tenancy.', 'DevOps|GitOps|Platform', 'GitOps multi-cluster, ApplicationSet', 'Four clusters manually synced—config skew caused region-specific outage.', 'ApplicationSet', 'When operating more than three Kubernetes clusters.', 'Single branch to all clusters—staging change synced to prod.'),
    ('GitOps', 'gitops-preview-environments', 'GitOps Preview Environments per Pull Request', 'Spin ephemeral preview envs with Argo CD ApplicationSet or Flux preview.', 'DevOps|GitOps|CI/CD', 'GitOps preview environments', 'PR merged without preview test—integration bug hit prod.', 'preview environments', 'When frontend/backend integration needs per-PR validation.', 'Preview envs without TTL—zombie namespaces exhaust IP space.'),
    ('GitOps', 'gitops-policy-enforcement', 'GitOps Policy Enforcement with Kyverno/OPA', 'Validate manifests at admission and in CI before GitOps sync.', 'DevOps|GitOps|Security', 'GitOps policy, Kyverno', 'Privileged pod synced from Git—policy added after incident.', 'Kyverno in GitOps', 'Before opening GitOps to application team repos.', 'Policy only at admission—invalid YAML merged to main repeatedly.'),
    ('GitOps', 'gitops-observability-metrics', 'GitOps Controller Observability', 'Monitor Argo CD/Flux sync status, reconciliation lag, and errors.', 'DevOps|GitOps|Observability', 'GitOps metrics, Argo CD', 'Silent sync failures for 6 hours—users hit stale deployment.', 'GitOps observability', 'From day one of GitOps adoption.', 'Metrics without alerts on sync Failed phase.'),
    ('GitOps', 'gitops-disaster-recovery', 'GitOps Disaster Recovery Runbooks', 'Recover clusters from Git when control plane or registry is lost.', 'DevOps|GitOps|SRE', 'GitOps disaster recovery', 'Registry outage—clusters could not pull images; GitOps could not help without cache.', 'GitOps DR', 'Before declaring GitOps the sole source of truth.', 'Git repo without offline mirror—GitHub outage blocks recovery.'),
    ('GitOps', 'gitops-helm-kustomize-hybrid', 'GitOps with Helm and Kustomize Hybrid Repos', 'Combine Helm charts with Kustomize overlays in unified GitOps repos.', 'DevOps|GitOps|Helm', 'Helm Kustomize GitOps', 'Kustomize patch targeted wrong Helm release name—labels missing in prod.', 'Helm + Kustomize', 'When platform team ships Helm and app team needs overlays.', 'helmCharts in Kustomize without version pin—upstream chart drift.'),
    ('Observability', 'prometheus-operator-setup', 'Prometheus Operator Setup and ServiceMonitor Patterns', 'Deploy kube-prometheus-stack and scrape with ServiceMonitor/PodMonitor CRDs.', 'DevOps|Observability|Kubernetes', 'Prometheus Operator, ServiceMonitor', 'Metrics blind spot after upgrade—ServiceMonitor selector typo missed new pods.', 'Prometheus Operator', 'When running Prometheus on Kubernetes beyond static scrape configs.', 'ServiceMonitor namespaceSelector too broad—cardinality explosion.'),
    ('Observability', 'prometheus-recording-rules', 'Prometheus Recording Rules for Dashboard Performance', 'Pre-aggregate expensive PromQL with recording rules for dashboards and alerts.', 'DevOps|Observability|SRE', 'Prometheus recording rules', 'Dashboard timeout on raw high-cardinality query—on-call flew blind during incident.', 'recording rules', 'When dashboard queries exceed 5s or alerts evaluate heavy PromQL.', 'Recording rules without unit tests—wrong aggregation silently.'),
    ('Observability', 'prometheus-federation-hierarchy', 'Prometheus Federation and Hierarchical Scraping', 'Federate metrics from regional Prometheus to global without single point overload.', 'DevOps|Observability|Platform', 'Prometheus federation', 'Global Prometheus OOM from scraping all targets directly.', 'Prometheus federation', 'When multi-region or multi-cluster metrics need global view.', 'Federation without drop rules—duplicate series and cost blowup.'),
    ('Observability', 'thanos-long-term-storage', 'Thanos for Long-Term Metrics Storage', 'Use Thanos sidecar, query, and store gateway for durable Prometheus metrics.', 'DevOps|Observability|Platform', 'Thanos, long-term metrics', '30-day retention insufficient for quarterly capacity review—data gone.', 'Thanos', 'When Prometheus retention exceeds local disk or compliance needs years.', 'Thanos compact without downsample—query cost untenable.'),
    ('Observability', 'grafana-dashboard-as-code', 'Grafana Dashboards as Code with Jsonnet or Terraform', 'Version control Grafana dashboards and provision via GitOps.', 'DevOps|Observability|GitOps', 'Grafana as code, dashboards', 'Critical dashboard edited in UI—lost on Grafana pod restart.', 'Grafana as code', 'When more than ten engineers edit the same Grafana instance.', 'Dashboard UID churn—Terraform recreates panels every apply.'),
    ('Observability', 'otel-collector-pipelines', 'OpenTelemetry Collector Pipeline Design', 'Route traces, metrics, and logs through OTel collectors with processors and exporters.', 'DevOps|Observability|Platform', 'OpenTelemetry Collector, pipelines', 'App agents exported directly to vendor—egress cost and no tail sampling.', 'OpenTelemetry Collector', 'When standardizing observability on OpenTelemetry.', 'Single collector deployment—no HA during node drain.'),
    ('Observability', 'otel-auto-instrumentation', 'OpenTelemetry Auto-Instrumentation on Kubernetes', 'Deploy OTel operator auto-instrumentation for Java, Python, and Node.', 'DevOps|Observability|Kubernetes', 'OTel auto-instrumentation', 'Manual tracing annotations missed async paths—broken trace trees.', 'OTel auto-instrumentation', 'When adopting tracing without rewriting every service.', 'Auto-instrumentation overhead unmeasured—CPU regression in prod.'),
    ('Observability', 'jaeger-sampling-strategies', 'Jaeger Head and Tail Sampling Strategies', 'Configure trace sampling to balance cost and debuggability.', 'DevOps|Observability|SRE', 'Jaeger sampling, tracing', 'Trace storage bill 5x budget—100% sampling on high-QPS service.', 'trace sampling', 'Before enabling tracing on tier-1 high-traffic services.', 'Head sampling only—missed rare errors in tail.'),
    ('Observability', 'loki-label-cardinality', 'Loki Label Cardinality and Log Query Performance', 'Design Loki labels to avoid cardinality explosions and slow queries.', 'DevOps|Observability|Platform', 'Loki, label cardinality', 'user_id as label—Loki ingester OOM and query timeouts.', 'Loki labels', 'When deploying Loki for Kubernetes log aggregation.', 'High-cardinality labels in structured metadata—same as bad labels.'),
    ('Observability', 'tempo-trace-backend', 'Grafana Tempo as Trace Backend Operations', 'Operate Tempo with object storage, compactor, and trace query patterns.', 'DevOps|Observability|Platform', 'Grafana Tempo, tracing', 'Jaeger all-in-one hit retention wall—traces gone after 48 hours.', 'Grafana Tempo', 'When trace volume exceeds single-node Jaeger capacity.', 'Tempo without blocklist—malicious trace payloads fill storage.'),
    ('Observability', 'alertmanager-inhibition-routes', 'Alertmanager Inhibition and Routing Trees', 'Design Alertmanager routes, receivers, and inhibition to reduce noise.', 'DevOps|Observability|SRE', 'Alertmanager, inhibition', 'Disk alert paged 40 times for one host—no inhibition between related alerts.', 'Alertmanager routing', 'When alert volume causes on-call fatigue or ignored pages.', 'Inhibition rules too aggressive—suppress real root cause pages.'),
    ('Observability', 'slo-burn-rate-alerts', 'SLO Burn Rate Alerts with Prometheus', 'Implement multi-window burn rate alerts from SLI recording rules.', 'DevOps|Observability|SRE', 'SLO burn rate, error budget', 'Static error rate alert fired on low traffic noise—missed real SLO breach Friday peak.', 'SLO burn rate alerts', 'When services have defined SLOs and error budgets.', 'Single-window burn rate—false positives on traffic dips.'),
    ('Observability', 'metrics-cardinality-control', 'Metrics Cardinality Control and Relabeling', 'Drop high-cardinality labels via relabel configs and naming standards.', 'DevOps|Observability|Cost Optimization', 'metrics cardinality, relabel', 'Prometheus TSDB 2TB from unbounded path label on HTTP metrics.', 'cardinality control', 'When Prometheus storage growth exceeds 20% month-over-month.', 'Relabel drop in scrape only—metrics already exported from apps.'),
    ('Observability', 'log-aggregation-pipeline', 'Log Aggregation Pipeline: Fluent Bit to OpenSearch', 'Ship Kubernetes logs with Fluent Bit, parse JSON, and index in OpenSearch.', 'DevOps|Observability|Data Engineering', 'Fluent Bit, log aggregation', 'Unparsed multiline stack traces—grep useless during outage.', 'Fluent Bit pipeline', 'When centralizing logs beyond kubectl logs.', 'Fluent Bit without backpressure—lost logs during spike.'),
    ('Observability', 'apm-service-map-ops', 'APM Service Map Operations and Dependency Health', 'Maintain service maps from traces and metrics for dependency incident response.', 'DevOps|Observability|SRE', 'APM service map', 'Unknown downstream caused cascade—service map stale after microservice split.', 'APM service map', 'When microservice count exceeds manual dependency docs.', 'Service map from sampled traces only—missing critical edges.'),
    ('Observability', 'ebpf-observability-cilium', 'eBPF Observability with Cilium Hubble', 'Use Hubble for L3/L7 flow visibility and policy verification.', 'DevOps|Observability|Security', 'Cilium Hubble, eBPF', 'NetworkPolicy looked correct—Hubble showed DNS bypass via hostNetwork pod.', 'Cilium Hubble', 'When running Cilium CNI and debugging network policy.', 'Hubble metrics without retention plan—short debug window only.'),
    ('Observability', 'opentelemetry-logs-bridge', 'OpenTelemetry Logs Bridge and Correlation', 'Correlate logs with trace_id via OTel logs bridge and structured logging.', 'DevOps|Observability|Platform', 'OpenTelemetry logs, correlation', 'Logs and traces searched separately—MTTR doubled finding failing span.', 'OTel logs bridge', 'When migrating to unified OTel for traces and logs.', 'trace_id injected only in some services—partial correlation.'),
    ('Observability', 'prometheus-remote-write', 'Prometheus Remote Write and HA Pairs', 'Configure remote_write to Cortex/Mimir/VictoriaMetrics with HA deduplication.', 'DevOps|Observability|Platform', 'Prometheus remote write, HA', 'Dual Prometheus remote_write duplicate samples—query double counts.', 'remote_write', 'When scaling Prometheus beyond single replica.', 'Remote write without queue config—data loss on backend blip.'),
    ('Observability', 'observability-cost-control', 'Observability Stack Cost Control', 'Control metrics, log, and trace ingest costs with sampling and retention tiers.', 'DevOps|Observability|Cost Optimization', 'observability cost', 'Observability bill exceeded compute—100% trace sampling on batch jobs.', 'observability cost control', 'When observability spend exceeds 15% of infra budget.', 'Cost cuts by dropping all debug logs—incidents undiagnosable.'),
    ('Observability', 'oncall-runbook-automation', 'On-Call Runbook Automation from Alerts', 'Link Alertmanager alerts to runbooks and automated remediation playbooks.', 'DevOps|Observability|SRE', 'on-call runbooks, automation', 'Page fired with no runbook link—engineer grep-archaeology for 45 minutes.', 'runbook automation', 'When mean time to remediate exceeds SLO targets.', 'Runbooks in wiki never updated—automated links point to wrong steps.'),
    ('Chaos Engineering', 'litmus-chaos-experiments', 'Litmus Chaos Experiments on Kubernetes', 'Run Litmus ChaosEngine experiments for pod, network, and IO faults.', 'DevOps|Chaos Engineering|Kubernetes', 'Litmus, chaos experiments', 'First prod outage from untested dependency timeout—no chaos coverage.', 'Litmus', 'Before peak season or after major architecture change.', 'Chaos in prod without blast radius limits—customer-facing blast.'),
    ('Chaos Engineering', 'chaos-mesh-network-faults', 'Chaos Mesh Network Fault Injection', 'Inject delay, loss, and partition with Chaos Mesh NetworkChaos.', 'DevOps|Chaos Engineering|Kubernetes', 'Chaos Mesh, network chaos', 'Retry storm amplified outage—never tested partial network partition.', 'Chaos Mesh', 'When services rely on retries and circuit breakers.', 'NetworkChaos targeting all namespaces—staging took down prod mesh.'),
    ('Chaos Engineering', 'game-day-planning', 'Game Day Planning and Steady-State Hypotheses', 'Plan game days with hypotheses, observers, and rollback criteria.', 'DevOps|Chaos Engineering|SRE', 'game day, steady state', 'Game day became real outage—no rollback criteria defined upfront.', 'game days', 'Quarterly for tier-1 services minimum.', 'Game days without executive communication—confused status pages.'),
    ('Chaos Engineering', 'fault-injection-staging', 'Fault Injection in Staging Environments', 'Run continuous fault injection in staging with production-shaped traffic.', 'DevOps|Chaos Engineering|Testing', 'fault injection, staging', 'Staging always green—prod failed on first Redis blip.', 'fault injection', 'When staging exists but rarely sees failure modes.', 'Staging without traffic—fault injection proves nothing.'),
    ('Chaos Engineering', 'pod-kill-resilience-test', 'Pod Kill Resilience Testing', 'Validate recovery from random pod termination with kube-monkey or Litmus.', 'DevOps|Chaos Engineering|Kubernetes', 'pod kill, resilience', 'Single replica Deployment survived pod kill test—false confidence.', 'pod kill tests', 'For every Deployment claiming HA with replicas >= 2.', 'Pod kill during DB migration—data corruption not tested.'),
    ('Chaos Engineering', 'network-partition-simulation', 'Network Partition Simulation Between Services', 'Simulate split-brain and partition between microservices and databases.', 'DevOps|Chaos Engineering|SRE', 'network partition', 'Split-brain writes after AZ partition—consistency model never validated.', 'network partition tests', 'For distributed systems with async replication.', 'Partition test only one direction—missed asymmetric failures.'),
    ('Chaos Engineering', 'dns-failure-injection', 'DNS Failure Injection and Resolver Fallback', 'Test behavior when CoreDNS or external DNS fails mid-request.', 'DevOps|Chaos Engineering|Networking', 'DNS failure injection', 'CoreDNS overload during rollout—cascading timeouts undetected.', 'DNS chaos', 'When services cache DNS or use hardcoded resolvers.', 'DNS chaos in prod without rate limits—amplified outage.'),
    ('Chaos Engineering', 'dependency-latency-injection', 'Dependency Latency Injection for Timeout Tuning', 'Inject latency to validate timeouts, bulkheads, and circuit breakers.', 'DevOps|Chaos Engineering|SRE', 'latency injection', '30s default timeout held threads—latency injection would have found it.', 'latency injection', 'Before tuning Hystrix/resilience4j or service mesh timeouts.', 'Injected latency without monitoring—cannot prove breaker opened.'),
    ('Chaos Engineering', 'steady-state-hypothesis', 'Steady-State Hypotheses for Chaos Experiments', 'Define measurable steady-state before and during chaos experiments.', 'DevOps|Chaos Engineering|SRE', 'steady-state hypothesis', 'Chaos experiment stopped early—no baseline metric defined.', 'steady-state metrics', 'Every chaos experiment design phase.', 'Hypothesis uses vanity metrics—not user-visible SLIs.'),
    ('Chaos Engineering', 'blast-radius-containment', 'Blast Radius Containment for Chaos Tests', 'Limit chaos experiments with namespaces, service selectors, and time windows.', 'DevOps|Chaos Engineering|Security', 'blast radius, chaos', 'Chaos test leaked to prod namespace via misconfigured selector.', 'blast radius controls', 'Before any chaos in shared clusters.', 'No automated stop when error budget burns during experiment.'),
    ('Chaos Engineering', 'chaos-experiment-automation', 'Automating Chaos Experiments in CI/CD', 'Schedule chaos in staging pipelines after deploy with pass/fail gates.', 'DevOps|Chaos Engineering|CI/CD', 'chaos automation', 'Manual chaos quarterly—regression shipped between game days.', 'chaos in CI', 'When continuous resilience validation replaces annual game days.', 'Chaos in CI without artifact capture—flaky failures ignored.'),
    ('Capacity Planning', 'capacity-forecasting-models', 'Capacity Forecasting Models for Platform Teams', 'Forecast CPU, memory, and QPS growth with time-series models and headroom policies.', 'DevOps|Capacity Planning|SRE', 'capacity forecasting', 'Launch week CPU pegged at 100%—forecast used linear extrapolation from quiet month.', 'capacity forecasting', 'Before major launches and quarterly budget planning.', 'Forecast without seasonality—Black Friday surprise every year.'),
    ('Capacity Planning', 'node-pool-rightsizing', 'Node Pool Rightsizing and Instance Family Selection', 'Right-size node pools by workload profile: compute, memory, GPU, burstable.', 'DevOps|Capacity Planning|Kubernetes', 'node pool rightsizing', 'Memory-bound Java on compute-optimized nodes—constant GC and OOM.', 'node pool sizing', 'When node utilization skews CPU vs memory beyond 40%.', 'Single instance family for all workloads—cost and perf penalty.'),
    ('Capacity Planning', 'overcommit-ratio-tuning', 'Overcommit Ratios and Scheduler Utilization', 'Tune request/limit ratios and overcommit for batch vs latency tiers.', 'DevOps|Capacity Planning|Kubernetes', 'overcommit ratio', 'Batch jobs OOMKilled after platform raised overcommit to save cost.', 'overcommit tuning', 'When cluster utilization below 40% but scheduling pressure high.', 'Limits omitted entirely—noisy neighbor on shared nodes.'),
    ('Capacity Planning', 'queue-depth-capacity', 'Queue Depth Capacity Planning for Async Systems', 'Size workers and brokers from queue depth growth and processing rates.', 'DevOps|Capacity Planning|Data Engineering', 'queue depth capacity', 'Kafka lag hit 6 hours during sale—consumer count never sized for peak.', 'queue capacity', 'For any async pipeline with SLAs on processing time.', 'Autoscale on queue depth without max consumer cap—DB overwhelmed.'),
    ('Capacity Planning', 'database-connection-pools', 'Database Connection Pool Capacity Planning', 'Size PgBouncer and app pools from pod count and query concurrency.', 'DevOps|Capacity Planning|Platform', 'connection pool sizing', 'Deploy doubled pods—Postgres max_connections exhausted instantly.', 'connection pools', 'Before horizontal scale of stateless app tiers.', 'Pool size per pod too high—few pods exhaust DB connections.'),
    ('Capacity Planning', 'traffic-forecasting-seasonality', 'Traffic Forecasting with Seasonality and Events', 'Model traffic seasonality, marketing events, and geographic peaks.', 'DevOps|Capacity Planning|SRE', 'traffic forecasting', 'Super Bowl ad traffic 8x forecast—autoscale max too low.', 'traffic forecasting', 'Before marketing events and retail peak seasons.', 'Forecast from averages—misses tail events entirely.'),
    ('Capacity Planning', 'headroom-policy-enforcement', 'Headroom Policy Enforcement for Production', 'Enforce minimum headroom (CPU, memory, connections) via policy and alerts.', 'DevOps|Capacity Planning|SRE', 'headroom policy', 'Cluster ran at 95% CPU for weeks—no alert until scheduling failures.', 'headroom enforcement', 'Continuously in production—not just pre-launch.', 'Headroom defined but not monitored—policy paper only.'),
    ('Capacity Planning', 'load-test-production-shadow', 'Shadow Load Testing Against Production Paths', 'Shadow or replay production traffic in staging for capacity validation.', 'DevOps|Capacity Planning|Testing', 'shadow load testing', 'Load test used synthetic payload—prod choked on large JSON bodies.', 'shadow load testing', 'Before doubling traffic or major architecture migrations.', 'Shadow traffic mutating data—production corruption incident.'),
    ('Capacity Planning', 'saturation-alerting', 'Saturation Alerting Before Hard Limits', 'Alert on saturation signals: CPU throttling, disk IO wait, connection pools.', 'DevOps|Capacity Planning|Observability', 'saturation alerting', 'Alert only on OOM—no warning as memory climbed 90→99%.', 'saturation alerts', 'When hard limits cause user-visible failures without warning.', 'Saturation alerts on averages—miss hot pods and nodes.'),
    ('Capacity Planning', 'autoscaler-limits-governance', 'Autoscaler Max Limits and Governance', 'Govern HPA max replicas and cluster max nodes with approval workflows.', 'DevOps|Capacity Planning|Platform', 'autoscaler limits', 'Runaway HPA scaled to 500 pods—invoice shock and DB meltdown.', 'autoscaler governance', 'Before enabling autoscale on new services.', 'No max replicas—misconfig scales cost unbounded.'),
    ('Capacity Planning', 'multi-region-capacity', 'Multi-Region Capacity and Failover Headroom', 'Plan capacity for regional failover when one region absorbs full traffic.', 'DevOps|Capacity Planning|SRE', 'multi-region capacity', 'Failover to secondary region overloaded it—each region sized for 60% only.', 'multi-region capacity', 'When running active-active or active-passive multi-region.', 'Failover drill never run—capacity math untested.'),
    ('MLOps', 'mlflow-model-registry', 'MLflow Model Registry and Stage Transitions', 'Govern model lifecycle with MLflow registry stages, tags, and approval gates.', 'DevOps|MLOps|Platform', 'MLflow, model registry', 'Production served Staging-tagged model after manual URI override.', 'MLflow model registry', 'When more than one data scientist deploys models.', 'Registry without RBAC—anyone promotes to Production stage.'),
    ('MLOps', 'kubeflow-pipelines-ops', 'Kubeflow Pipelines Operations on Kubernetes', 'Operate Kubeflow Pipelines: SDK, artifacts, caching, and multi-user isolation.', 'DevOps|MLOps|Kubernetes', 'Kubeflow Pipelines', 'Pipeline pod OOM on feature engineering—no resource templates.', 'Kubeflow Pipelines', 'When ML training pipelines run on Kubernetes.', "Shared namespace—one team's run deletes another's artifacts."),
    ('MLOps', 'feature-store-feast', 'Feast Feature Store Deployment and Operations', 'Deploy Feast online/offline stores with materialization jobs and monitoring.', 'DevOps|MLOps|Data Engineering', 'Feast feature store', 'Training-serving skew—online store stale by 24 hours vs offline.', 'Feast', 'When features shared across training and real-time inference.', 'Materialization job failures silent—stale features in prod.'),
    ('MLOps', 'model-serving-kserve', 'KServe Model Serving on Kubernetes', 'Deploy models with KServe InferenceService, autoscaling, and canaries.', 'DevOps|MLOps|Kubernetes', 'KServe, model serving', 'Raw Deployment for models—no scale-to-zero, GPU idle 80% of day.', 'KServe', 'When standardizing model inference on Kubernetes.', 'KServe without timeout—slow model blocks worker queue.'),
    ('MLOps', 'model-serving-triton', 'NVIDIA Triton Inference Server Operations', 'Operate Triton for multi-model GPU serving, dynamic batching, and ensembles.', 'DevOps|MLOps|Platform', 'Triton inference server', 'Three models on three GPU nodes—Triton ensemble would have fit one.', 'Triton', 'For GPU-consolidated multi-model inference.', 'Dynamic batching max delay too high—latency SLO breach.'),
    ('MLOps', 'model-monitoring-drift', 'Model Monitoring: Data and Concept Drift', 'Monitor feature drift, prediction drift, and performance decay in production.', 'DevOps|MLOps|Observability', 'model drift monitoring', 'Model accuracy collapsed after market shift—no drift alerts configured.', 'model monitoring', 'From day one of production model serving.', 'Monitoring only infrastructure CPU—not model quality metrics.'),
    ('MLOps', 'experiment-tracking-governance', 'Experiment Tracking Governance and Retention', 'Govern ML experiments: naming, artifact retention, and PII in metadata.', 'DevOps|MLOps|Platform', 'experiment tracking', 'Disk full from million-run experiment spam—no retention policy.', 'experiment tracking', 'When MLflow/W&B adoption goes team-wide.', 'PII in experiment params—compliance violation on audit.'),
    ('MLOps', 'gpu-scheduling-ml-workloads', 'GPU Scheduling for ML Training and Inference', 'Schedule GPU jobs with quotas, fractions, and priority for training vs inference.', 'DevOps|MLOps|Kubernetes', 'GPU scheduling ML', 'Training job starved inference GPUs—no separate NodePool or quota.', 'GPU scheduling', 'When GPU capacity is shared across teams.', 'Time-slicing without isolation—noisy neighbor on shared GPU.'),
    ('MLOps', 'batch-inference-pipelines', 'Batch Inference Pipelines at Scale', 'Run large batch inference with Spark, Argo, or cloud batch with checkpointing.', 'DevOps|MLOps|Data Engineering', 'batch inference', 'Batch scoring restarted from zero after 18-hour failure—no checkpoint.', 'batch inference', 'For nightly or hourly large-scale scoring jobs.', 'Batch output overwrite without versioning—downstream consumed wrong partition.'),
    ('MLOps', 'model-rollout-canary', 'Model Rollout Canary and Shadow Deployment', 'Roll out new models with traffic split, shadow mode, and metric comparison.', 'DevOps|MLOps|SRE', 'model canary rollout', 'New model deployed 100%—latency regression hit all users.', 'model canary', 'Before replacing production model serving endpoint.', 'Canary compares accuracy offline only—prod traffic distribution differs.'),
    ('MLOps', 'ml-pipeline-airflow', 'Airflow for ML Pipeline Orchestration', 'Orchestrate ML pipelines in Airflow with sensors, XComs, and KubernetesPodOperator.', 'DevOps|MLOps|Data Engineering', 'Airflow ML pipelines', 'Sensor deadlock blocked retraining for a week—no SLA alert.', 'Airflow for ML', 'When ML steps mix SQL, Spark, and K8s jobs.', 'XCom passing large dataframes—metadata DB bloat and failure.'),
    ('MLOps', 'model-artifact-versioning', 'Model Artifact Versioning and Immutable Stores', 'Store model artifacts in versioned object storage with immutability and lineage.', 'DevOps|MLOps|Platform', 'model artifact versioning', 'Production pulled latest tag—artifact overwritten by retrains.', 'model artifacts', 'For every production model deployment path.', 'Mutable latest tag in registry—non-reproducible inference.'),
    ('MLOps', 'inference-autoscaling-custom', 'Inference Autoscaling on Custom Metrics', 'Scale inference Deployments on queue depth, GPU util, or p99 latency metrics.', 'DevOps|MLOps|Kubernetes', 'inference autoscaling', 'CPU-based HPA on GPU inference—never scaled during batch spike.', 'inference autoscaling', 'When model serving has non-CPU-bound scaling signals.', 'Scale to zero without warm pool—cold start broke latency SLO.'),
    ('MLOps', 'data-versioning-dvc', 'Data Versioning with DVC and Pipeline Reproducibility', 'Version datasets and pipelines with DVC remotes and reproducible training runs.', 'DevOps|MLOps|Data Engineering', 'DVC, data versioning', 'Could not reproduce champion model—training data moved on S3.', 'DVC', 'When models must be reproducible for audit or debugging.', 'DVC remote credentials in repo—security and rotation pain.'),
    ('MLOps', 'ml-ci-cd-github-actions', 'ML CI/CD with GitHub Actions and Model Tests', 'Gate model deploys with unit tests, data validation, and eval thresholds in CI.', 'DevOps|MLOps|CI/CD', 'ML CI/CD', 'Broken preprocessing shipped—CI only tested model pickle load.', 'ML CI/CD', 'Before automating model promotion to production.', 'Eval on static holdout only—does not catch serving skew.'),
    ('MLOps', 'model-governance-audit', 'Model Governance Audit Trails and Approval', 'Maintain audit trails for model approvals, inputs, and bias evaluations.', 'DevOps|MLOps|Security', 'model governance', 'Regulator asked who approved model v3—only Slack thread existed.', 'model governance', 'For regulated or customer-impacting ML systems.', 'Governance checklist after deploy—not blocking gate.'),
    ('Feature Stores', 'feast-online-offline-sync', 'Feast Online and Offline Store Synchronization', 'Keep Feast online Redis and offline warehouse features consistent with SLAs.', 'DevOps|Feature Stores|MLOps', 'Feast online offline sync', 'Point-in-time join wrong—offline training used future data.', 'Feast sync', 'When using Feast for training-serving consistency.', 'Online store TTL shorter than materialization interval.'),
    ('Feature Stores', 'feature-store-materialization', 'Feature Store Materialization Job Operations', 'Schedule, monitor, and backfill Feast materialization jobs reliably.', 'DevOps|Feature Stores|Data Engineering', 'feature materialization', 'Materialization lagged 6 hours—fraud model used stale velocity features.', 'materialization jobs', 'For any online feature store with freshness SLAs.', 'Backfill without idempotency—duplicate feature rows.'),
    ('Feature Stores', 'feature-store-point-in-time', 'Point-in-Time Correct Joins in Feature Stores', 'Enforce point-in-time correctness for training datasets from feature stores.', 'DevOps|Feature Stores|MLOps', 'point-in-time joins', 'Offline eval inflated—leakage from future feature timestamps.', 'point-in-time correctness', 'During training pipeline design reviews.', 'As-of joins without timezone normalization—midnight bugs.'),
    ('Feature Stores', 'feature-store-monitoring', 'Feature Store Freshness and Quality Monitoring', 'Alert on stale features, null rates, and schema drift in feature stores.', 'DevOps|Feature Stores|Observability', 'feature store monitoring', 'Null rate spike in embedding feature—no alert until model degraded.', 'feature monitoring', 'Production feature stores from launch day.', 'Monitoring batch stats only—online serving drift undetected.'),
    ('Feature Stores', 'feature-store-governance', 'Feature Store Governance and Feature Ownership', 'Assign feature owners, documentation, and deprecation policies in registries.', 'DevOps|Feature Stores|Platform', 'feature governance', 'Nobody owned deprecated feature—three teams still queried it.', 'feature governance', 'When feature count exceeds informal tribal knowledge.', 'Shared features without SLAs—consumers blame model team.'),
    ('Feature Stores', 'redis-feature-store-ops', 'Redis Feature Store Operations at Scale', 'Operate Redis as online feature store: memory, clustering, and hot keys.', 'DevOps|Feature Stores|Platform', 'Redis feature store', 'Hot user_id key saturated single Redis shard—p99 feature fetch 2s.', 'Redis feature store', 'When Feast or custom store uses Redis online.', 'Redis without persistence plan—cold restart empty store.'),
    ('Feature Stores', 'dynamodb-feature-serving', 'DynamoDB for Low-Latency Feature Serving', 'Design DynamoDB tables for feature serving with GSIs and on-demand capacity.', 'DevOps|Feature Stores|Platform', 'DynamoDB feature serving', 'Throttled reads during launch—on-demand not enabled for feature table.', 'DynamoDB features', 'For millisecond feature lookups at high QPS.', 'GSI hot partition on popular entity keys.'),
    ('Feature Stores', 'feature-store-backfill', 'Feature Store Backfill Strategies Without Downtime', 'Backfill historical features without breaking online serving or training.', 'DevOps|Feature Stores|Data Engineering', 'feature backfill', 'Backfill locked table—online serving timed out for an hour.', 'feature backfill', 'When adding new features to existing entities at scale.', 'Backfill writing to online store without rate limits.'),
    ('Feature Stores', 'feature-store-schema-evolution', 'Feature Schema Evolution and Compatibility', 'Evolve feature schemas with additive changes and consumer contracts.', 'DevOps|Feature Stores|Platform', 'feature schema evolution', 'Renamed column broke three training pipelines silently.', 'schema evolution', 'Before any breaking feature definition change.', 'Breaking change without version bump in feature view.'),
    ('RAG Ops', 'rag-index-versioning', 'RAG Index Versioning and Zero-Downtime Reindex', 'Version vector indexes and swap aliases for zero-downtime RAG reindexing.', 'DevOps|RAG Ops|MLOps', 'RAG index versioning', 'Reindex deleted production alias—RAG returned empty for 20 minutes.', 'RAG index versioning', 'When document corpus updates daily or hourly.', 'In-place reindex without alias swap—query downtime.'),
    ('RAG Ops', 'rag-embedding-pipeline-ops', 'RAG Embedding Pipeline Operations', 'Operate batch and streaming embedding pipelines with retry and deduplication.', 'DevOps|RAG Ops|Data Engineering', 'RAG embedding pipeline', 'Duplicate chunks embedded 3x—index size and cost tripled.', 'embedding pipeline', 'Before production RAG at scale.', 'Embedding pipeline without content hash dedup—wasted compute.'),
    ('RAG Ops', 'rag-chunking-strategy-production', 'Production Chunking Strategy for RAG Indexes', 'Tune chunk size, overlap, and structure-aware splitting for retrieval quality.', 'DevOps|RAG Ops|MLOps', 'RAG chunking', 'Tables split mid-row—retrieval returned nonsense numbers to LLM.', 'chunking strategy', 'When eval shows low recall on structured documents.', 'Fixed token chunking on markdown code blocks—broken syntax in context.'),
    ('RAG Ops', 'rag-hybrid-search-ops', 'Hybrid Search Operations: BM25 plus Vector', 'Operate hybrid retrieval with weight tuning, fusion, and index consistency.', 'DevOps|RAG Ops|Platform', 'hybrid search RAG', 'Vector-only search missed exact SKU match—hybrid would have ranked it first.', 'hybrid search', 'When keyword and semantic recall both matter.', 'Hybrid weights tuned offline only—prod query mix differs.'),
    ('RAG Ops', 'rag-eval-automation', 'RAG Evaluation Automation in CI/CD', 'Automate RAG evals: faithfulness, recall@k, and latency gates in CI.', 'DevOps|RAG Ops|CI/CD', 'RAG evaluation CI', 'Prompt change shipped—faithfulness dropped 15% with no eval gate.', 'RAG eval automation', 'Before every RAG config or model change merges.', 'Eval set of 10 questions—does not represent prod query distribution.'),
    ('RAG Ops', 'rag-cache-invalidation', 'RAG Cache Invalidation on Corpus Updates', 'Invalidate query and embedding caches when source documents change.', 'DevOps|RAG Ops|Platform', 'RAG cache invalidation', 'Stale policy doc cached—LLM cited outdated compliance language.', 'RAG cache', 'When caching RAG responses or retrieval results.', 'TTL-only invalidation—doc update invisible until expiry.'),
    ('RAG Ops', 'rag-rate-limiting-serving', 'RAG Serving Rate Limits and Cost Controls', 'Rate limit RAG endpoints by tenant, token budget, and retrieval depth.', 'DevOps|RAG Ops|Security', 'RAG rate limiting', 'Bot scraped RAG API—embedding cost 10x daily budget in an hour.', 'RAG rate limits', 'Before public or partner-facing RAG APIs.', 'Rate limit on HTTP only—not embedding batch abuse.'),
    ('RAG Ops', 'rag-observability-latency', 'RAG Observability: Retrieval vs Generation Latency', 'Break down RAG latency into retrieve, rerank, and LLM spans with tracing.', 'DevOps|RAG Ops|Observability', 'RAG observability', 'Users complained slow chat—team optimized LLM while retrieval was 80% of latency.', 'RAG tracing', 'From first production RAG deployment.', 'Single latency metric—cannot tell retrieve vs generation regression.'),
    ('RAG Ops', 'rag-security-prompt-injection', 'RAG Security: Prompt Injection and Document Trust', 'Harden RAG against poisoned documents and indirect prompt injection.', 'DevOps|RAG Ops|Security', 'RAG prompt injection', 'User uploaded doc with hidden instruction—model leaked system prompt fragment.', 'RAG security', 'When RAG ingests user-provided or web-fetched content.', 'Trusting all retrieved chunks equally—no source scoring or filtering.'),
    ('Model Serving', 'model-serving-batching', 'Dynamic Batching for Model Inference', 'Configure dynamic batching windows and max batch size for throughput vs latency.', 'DevOps|Model Serving|MLOps', 'dynamic batching inference', 'GPU at 20% util with batch size 1—dynamic batching fixed throughput 4x.', 'dynamic batching', 'When inference GPU/CPU underutilized at low QPS.', 'Batch window too long—p99 latency unacceptable for realtime.'),
    ('Model Serving', 'model-serving-ensemble', 'Model Ensemble Serving Patterns', 'Serve ensembles with Triton/KServe pipeline parallelism and fallback models.', 'DevOps|Model Serving|MLOps', 'model ensemble serving', 'Single model wrong on edge case—ensemble reduced error rate 30%.', 'ensemble serving', 'When multiple models vote or cascade for quality.', 'Ensemble without timeout per stage—one slow model blocks all.'),
    ('Model Serving', 'model-serving-a-b-testing', 'A/B Testing Model Versions in Production', 'Split traffic between model versions with consistent user hashing and metrics.', 'DevOps|Model Serving|SRE', 'model A/B testing', 'Manual 50/50 split broke when pods restarted—sticky sessions lost.', 'model A/B testing', 'Before promoting challenger model to champion.', 'A/B without statistical power calc—premature winner declaration.'),
    ('Model Serving', 'model-serving-circuit-breakers', 'Circuit Breakers for Model Dependencies', 'Wrap model calls with circuit breakers when dependencies or GPU paths fail.', 'DevOps|Model Serving|SRE', 'model circuit breakers', 'Embedding service outage cascaded—no breaker on retrieval path.', 'circuit breakers', 'When inference chains multiple model or feature calls.', 'Breaker opens permanently—no half-open retry policy.'),
    ('Model Serving', 'model-serving-multi-model', 'Multi-Model Single GPU Multiplexing', 'Multiplex multiple small models on one GPU with memory profiling and MPS.', 'DevOps|Model Serving|Cost Optimization', 'multi-model GPU', 'Ten GPU nodes for ten tiny models—multiplexing fit all on two.', 'multi-model serving', 'When many small models each underutilize GPU.', 'Models without memory isolation—OOM takes down neighbor models.'),
    ('Model Serving', 'model-serving-edge-deployment', 'Edge Model Deployment and OTA Updates', 'Deploy and update models on edge with OTA rollback and bandwidth limits.', 'DevOps|Model Serving|IoT', 'edge model deployment', 'OTA bricked 200 devices—no rollback image on device.', 'edge model OTA', 'For inference on edge or IoT fleets.', 'Full model push every update—cellular cost unsustainable.'),
    ('Model Serving', 'model-serving-warm-pools', 'Warm Pools and Cold Start Mitigation', 'Keep warm inference replicas or preloaded models to meet cold start SLOs.', 'DevOps|Model Serving|Kubernetes', 'warm pools inference', 'Scale-from-zero added 45s load time—SLO missed on first requests.', 'warm pools', 'When using Knative/KServe scale-to-zero.', 'Warm pool sized for peak—idle cost equals always-on.'),
    ('Model Serving', 'model-serving-quantization', 'Model Quantization for Production Inference', 'Apply INT8/FP16 quantization with accuracy validation before deploy.', 'DevOps|Model Serving|MLOps', 'model quantization', 'FP32 model too slow—quantization cut latency 2x with 0.5% accuracy loss.', 'quantization', 'When latency or cost requires smaller model footprint.', 'Quantize without eval on prod-representative set—silent quality drop.'),
    ('Model Serving', 'model-serving-fallback-models', 'Fallback Models When Primary Fails', 'Route to smaller fallback model when primary times out or errors.', 'DevOps|Model Serving|SRE', 'fallback models', 'Primary LLM timeout returned 500—fallback would have answered safely.', 'fallback models', 'For customer-facing inference with strict availability SLO.', 'Fallback model not tested in load— fails under same traffic.'),
    ('Data Pipelines', 'airflow-dag-best-practices', 'Airflow DAG Best Practices for Production', 'Design idempotent Airflow DAGs with retries, SLAs, and clear ownership.', 'DevOps|Data Pipelines|Data Engineering', 'Airflow DAG best practices', 'Retry loop on bad data reprocessed terabytes—bill and downstream corruption.', 'Airflow DAGs', 'Before scheduling business-critical ETL in Airflow.', 'catchup=True on backfill—surprise historical run storm.'),
    ('Data Pipelines', 'airflow-kubernetes-executor', 'Airflow Kubernetes Executor Operations', 'Run Airflow workers as pods with resource limits and image pinning.', 'DevOps|Data Pipelines|Kubernetes', 'Airflow Kubernetes executor', 'Worker pod OOM on wide dataframe—no limit on KubernetesPodOperator.', 'Kubernetes executor', 'When Celery executor does not isolate task resources.', 'Shared worker image tag latest—non-reproducible task env.'),
    ('Data Pipelines', 'airflow-backfill-strategies', 'Airflow Backfill Strategies and Safety', 'Backfill historical partitions with max_active_runs and data validation gates.', 'DevOps|Data Pipelines|Data Engineering', 'Airflow backfill', 'Backfill doubled rows in warehouse—idempotency key missing on insert.', 'Airflow backfill', 'When fixing upstream gaps or late-arriving data.', 'Unbounded backfill date range—accidental full history replay.'),
    ('Data Pipelines', 'dag-dependency-management', 'Cross-DAG Dependencies and Data Contracts', 'Manage cross-DAG deps with datasets, external sensors, and contracts.', 'DevOps|Data Pipelines|Platform', 'DAG dependencies', 'ExternalTaskSensor deadlock—upstream rename broke silent dependency.', 'DAG dependencies', 'When pipeline count exceeds manual coordination.', 'Sensors polling every minute—DB load from orchestrator.'),
    ('Data Pipelines', 'pipeline-data-quality-great-expectations', 'Data Quality Gates with Great Expectations', 'Block pipeline promote on Great Expectations suites and data docs.', 'DevOps|Data Pipelines|Data Engineering', 'Great Expectations, data quality', 'Null primary keys loaded to prod—GE suite existed but not in critical path.', 'Great Expectations', 'On pipelines feeding ML or finance tables.', 'Expectations on sample only—full partition violations missed.'),
    ('Data Pipelines', 'pipeline-lineage-openlineage', 'Pipeline Lineage with OpenLineage and Marquez', 'Emit OpenLineage events for column-level lineage and impact analysis.', 'DevOps|Data Pipelines|Platform', 'OpenLineage, Marquez', 'Breaking column rename—no downstream impact analysis, five dashboards broke.', 'OpenLineage', 'When data mesh or many consumers depend on shared tables.', 'Lineage without ownership tags—cannot notify affected teams.'),
    ('Data Pipelines', 'pipeline-idempotency-patterns', 'Idempotency Patterns for Data Pipelines', 'Design merges, upserts, and partition swaps for rerunnable pipelines.', 'DevOps|Data Pipelines|Data Engineering', 'pipeline idempotency', 'Pipeline rerun after failure duplicated revenue facts—no merge key.', 'idempotent pipelines', 'For every scheduled pipeline from day one.', 'Delete-insert window—readers see empty partition mid-run.'),
    ('Data Pipelines', 'pipeline-sla-monitoring', 'Pipeline SLA Monitoring and Alerting', 'Alert on DAG duration, landing time, and freshness SLAs with ownership.', 'DevOps|Data Pipelines|SRE', 'pipeline SLA monitoring', 'Exec dashboard stale 4 hours—freshness SLA existed but unwired alert.', 'pipeline SLAs', 'When downstream products depend on pipeline landing times.', 'SLA on scheduler start not data landing—false green.'),
    ('Data Pipelines', 'pipeline-dead-letter-handling', 'Dead Letter Queues for Failed Pipeline Records', 'Route poison records to DLQ with replay tooling and metrics.', 'DevOps|Data Pipelines|Data Engineering', 'pipeline DLQ', 'One bad JSON line failed entire batch job for 6 hours.', 'pipeline DLQ', 'Streaming or batch ingest with untrusted sources.', 'DLQ without replay runbook—manual SQL fixes forever.'),
    ('Data Pipelines', 'pipeline-schema-registry', 'Schema Registry for Streaming and Batch', 'Enforce Avro/Protobuf schemas with Confluent Schema Registry compatibility.', 'DevOps|Data Pipelines|Platform', 'schema registry', 'Backward incompatible schema broke consumers—FULL compatibility not enforced.', 'schema registry', 'Kafka or event-driven pipelines with evolving schemas.', 'Schema registered manually—producer bypasses registry.'),
    ('Data Pipelines', 'pipeline-orchestration-dagster', 'Dagster Orchestration for Data Assets', 'Model pipelines as software-defined assets with Dagster ops and sensors.', 'DevOps|Data Pipelines|Platform', 'Dagster, data assets', 'Task-based Airflow could not express asset lineage—Dagster clarified deps.', 'Dagster', 'Greenfield data platforms preferring asset-centric orchestration.', 'Assets without partitions—backfills recompute entire graph.'),
    ('Data Pipelines', 'pipeline-event-driven-triggers', 'Event-Driven Pipeline Triggers', 'Trigger pipelines from S3 events, Kafka messages, or webhooks not cron.', 'DevOps|Data Pipelines|Platform', 'event-driven pipelines', 'Hourly cron lagged 55 minutes behind file landing—event trigger needed.', 'event triggers', 'When data arrival is irregular not clock-aligned.', 'Duplicate events without dedup—double processing downstream.'),
    ('Data Pipelines', 'pipeline-cost-allocation', 'Pipeline Cost Allocation and FinOps Tags', 'Tag pipeline runs with team, product, and job cost for chargeback.', 'DevOps|Data Pipelines|Cost Optimization', 'pipeline cost allocation', 'Snowflake bill spike—no tag on which DAG caused warehouse burn.', 'pipeline cost tags', 'When data platform cost exceeds visibility threshold.', 'Tags on cluster not query—cannot allocate Spark job cost.'),
    ('Data Pipelines', 'pipeline-disaster-recovery', 'Data Pipeline Disaster Recovery Runbooks', 'Recover orchestrator metadata, replay queues, and restore warehouse from backup.', 'DevOps|Data Pipelines|SRE', 'pipeline disaster recovery', 'Airflow metadata DB lost—no backup, DAG history gone.', 'pipeline DR', 'Before declaring orchestrator critical infrastructure.', 'DR plan ignores warehouse—replay without idempotency corrupts data.'),
    ('Spark/dbt', 'spark-k8s-operator', 'Spark on Kubernetes Operator Operations', 'Submit and monitor Spark jobs with Spark Operator and dynamic allocation.', 'DevOps|Spark|Kubernetes', 'Spark Kubernetes operator', 'Driver OOM on collect()—job killed after 3 hours of compute wasted.', 'Spark on K8s', 'When migrating Spark from YARN to Kubernetes.', 'Static executor count—no dynamic allocation on variable jobs.'),
    ('Spark/dbt', 'spark-dynamic-allocation', 'Spark Dynamic Allocation and Shuffle Tuning', 'Tune dynamic allocation, shuffle partitions, and adaptive query execution.', 'DevOps|Spark|Data Engineering', 'Spark dynamic allocation', '200 default shuffle partitions on 1GB job—scheduler overhead dominated.', 'Spark AQE', 'For Spark jobs with variable input sizes.', 'Dynamic allocation min executors 0—cold start every job.'),
    ('Spark/dbt', 'spark-shuffle-service', 'Spark External Shuffle Service Operations', 'Deploy external shuffle service for safer executor scale-down on K8s/YARN.', 'DevOps|Spark|Platform', 'Spark shuffle service', 'Executor scale-in lost shuffle blocks—job failed stage 7.', 'shuffle service', 'Long Spark jobs with dynamic executors.', 'Shuffle service disk full—no monitoring on shuffle PVCs.'),
    ('Spark/dbt', 'dbt-cicd-testing', 'dbt CI/CD: Slim CI and State Comparison', 'Run dbt slim CI with defer and state:modified+ on pull requests.', 'DevOps|dbt|CI/CD', 'dbt CI/CD, slim CI', 'Full dbt run 2 hours on typo in docs—slim CI would run 4 models.', 'dbt slim CI', 'When dbt project exceeds 15 minute PR feedback budget.', 'Slim CI without prod manifest artifact—defer broken.'),
    ('Spark/dbt', 'dbt-incremental-models', 'dbt Incremental Model Strategies', 'Choose merge, delete+insert, and micro-batch incremental strategies correctly.', 'DevOps|dbt|Data Engineering', 'dbt incremental models', 'Full table scan nightly on 10TB table—incremental misconfigured as table materialization.', 'dbt incremental', 'Tables over 100GB or hourly refresh requirements.', 'Incremental without unique_key—duplicate rows on retry.'),
    ('Spark/dbt', 'dbt-snapshot-strategies', 'dbt Snapshots for Slowly Changing Dimensions', 'Implement Type 2 history with dbt snapshots and timestamp strategies.', 'DevOps|dbt|Data Engineering', 'dbt snapshots, SCD2', 'Manual history table errors—snapshot strategy timestamp wrong column.', 'dbt snapshots', 'When dimension history required for analytics or compliance.', 'check strategy on mutable source—history corrupted silently.'),
    ('Spark/dbt', 'dbt-exposures-lineage', 'dbt Exposures and Downstream Lineage', 'Document dashboards and apps as dbt exposures for impact analysis.', 'DevOps|dbt|Platform', 'dbt exposures, lineage', 'Dropped column used by Looker tile—exposure would have flagged PR.', 'dbt exposures', 'When many BI tools consume dbt models.', 'Exposures stale—never updated after dashboard migration.'),
    ('Spark/dbt', 'dbt-semantic-layer', 'dbt Semantic Layer Operations', 'Publish metrics via dbt Semantic Layer with governance and caching.', 'DevOps|dbt|Platform', 'dbt semantic layer', 'Marketing and finance reported different ARR—metric defined twice.', 'semantic layer', 'When metric definitions proliferate across BI tools.', 'Semantic layer cache stale—dashboard disagrees with warehouse.'),
    ('Spark/dbt', 'spark-delta-lake-ops', 'Delta Lake Operations: OPTIMIZE and VACUUM', 'Maintain Delta tables with optimize, vacuum, and retention safety windows.', 'DevOps|Spark|Data Engineering', 'Delta Lake OPTIMIZE VACUUM', 'Small files problem—query 10x slower until OPTIMIZE scheduled.', 'Delta Lake ops', 'Production Delta tables over 1TB or streaming ingest.', 'VACUUM retention too aggressive—time travel broken for audit.'),
    ('Spark/dbt', 'spark-executor-tuning', 'Spark Executor Memory and Core Tuning', 'Right-size executor memory, overhead, and cores for skew and spill.', 'DevOps|Spark|Data Engineering', 'Spark executor tuning', 'Massive spill to disk—executor memory 4g for 200g shuffle partition.', 'Spark executors', 'When Spark jobs spill or OOM regularly.', 'Equal executors on skewed key—one task runs hours.'),
    ('Spark/dbt', 'dbt-run-hooks-ops', 'dbt Run Hooks and On-Run-End Operations', 'Use run hooks for grants, notifications, and post-run validation safely.', 'DevOps|dbt|Data Engineering', 'dbt run hooks', 'on-run-end grant failed silently—BI could not query new models until manual fix.', 'dbt hooks', 'When post-run automation must accompany every dbt job.', 'Hooks with side effects not idempotent—double grant errors.'),
    ('Warehouse Modeling', 'snowflake-warehouse-sizing', 'Snowflake Warehouse Sizing and Auto-Suspend', 'Size warehouses, auto-suspend policies, and multi-cluster for query concurrency.', 'DevOps|Warehouse|Cost Optimization', 'Snowflake warehouse sizing', 'XS warehouse queue during month-end—reports late to executives.', 'Snowflake warehouses', 'When Snowflake credit burn or queue time spikes.', 'Auto-suspend disabled on dev warehouses—credits burn overnight.'),
    ('Warehouse Modeling', 'bigquery-slot-management', 'BigQuery Slot Management and Reservations', 'Manage on-demand vs flat-rate slots and reservations for predictable cost.', 'DevOps|Warehouse|Cost Optimization', 'BigQuery slots', 'Ad hoc query scan 5TB—slot cap would have queued not surprise bill.', 'BigQuery slots', 'When BigQuery spend unpredictable on on-demand.', 'Reservation without autoscale—queries queue at cap.'),
    ('Warehouse Modeling', 'redshift-distribution-keys', 'Redshift Distribution Keys and Sort Keys', 'Choose DISTKEY and SORTKEY to minimize redistribution and zone maps.', 'DevOps|Warehouse|Data Engineering', 'Redshift distribution keys', 'Full table scan every join—DISTKEY wrong on 50TB fact.', 'Redshift tuning', 'Redshift performance degradation on fact joins.', 'EVEN distribution on large fact—massive redistribute.'),
    ('Warehouse Modeling', 'dbt-star-schema-design', 'Star Schema Design for Analytics Warehouses', 'Design fact and dimension tables with conformed dimensions and grain discipline.', 'DevOps|Warehouse|Data Engineering', 'star schema design', 'Revenue double-counted—fact grain included partial shipments twice.', 'star schema', 'Greenfield analytics marts before ten conflicting definitions.', 'Factless fact tables misused—join explosion in BI.'),
    ('Warehouse Modeling', 'data-mesh-domain-ownership', 'Data Mesh Domain Ownership and Product Thinking', 'Assign domain teams ownership of data products with SLAs and contracts.', 'DevOps|Warehouse|Platform', 'data mesh ownership', 'Central team bottleneck—domain could not ship features waiting on ETL.', 'data mesh', 'When data org exceeds ~15 engineers without domain split.', 'Mesh without federated governance—incompatible schemas everywhere.'),
    ('Warehouse Modeling', 'slowly-changing-dimensions', 'Slowly Changing Dimensions Type 1 vs Type 2', 'Implement SCD patterns with effective dating and surrogate keys.', 'DevOps|Warehouse|Data Engineering', 'SCD Type 2', 'Customer address history lost—Type 1 overwrite on dimension.', 'SCD patterns', 'Dimensions where history matters for reporting or compliance.', 'Type 2 without end-date maintenance—multiple current rows.'),
    ('Warehouse Modeling', 'fact-table-grain-design', 'Fact Table Grain Design and Additivity', 'Define fact grain explicitly and validate measure additivity across dimensions.', 'DevOps|Warehouse|Data Engineering', 'fact table grain', 'Summed snapshot balance as additive—totals nonsense in pivot.', 'fact grain', 'Every new fact table design review.', 'Grain includes timestamp to minute—unqueryable row explosion.'),
    ('Warehouse Modeling', 'dimensional-modeling-pitfalls', 'Dimensional Modeling Pitfalls in Modern Stacks', 'Avoid snowflaking, junk dimensions, and bridge table abuse in cloud warehouses.', 'DevOps|Warehouse|Data Engineering', 'dimensional modeling pitfalls', 'Over-normalized dimensions—BI queries 12-way join timeout.', 'dimensional modeling', 'When migrating from OLTP thinking to analytics modeling.', 'Bridge tables without weighting—duplicate measure sums.'),
    ('Warehouse Modeling', 'warehouse-query-governance', 'Warehouse Query Governance and Cost Guards', 'Enforce query timeouts, result limits, and approved access paths.', 'DevOps|Warehouse|Security', 'warehouse query governance', 'Analyst SELECT * on raw events—$12k scan single afternoon.', 'query governance', 'Self-serve warehouse access for more than data team.', 'Governance only on BI tool—direct SQL bypasses limits.'),
    ('Cost Optimization', 'k8s-cost-allocation-kubecost', 'Kubernetes Cost Allocation with Kubecost/OpenCost', 'Allocate cluster cost by namespace, label, and shared overhead fairly.', 'DevOps|Cost Optimization|Kubernetes', 'Kubecost, OpenCost, K8s cost', 'One namespace 60% of bill—no labels until finance escalated.', 'K8s cost allocation', 'When Kubernetes exceeds 25% of cloud spend.', 'Allocation without shared cost split—GPU nodes blamed on wrong team.'),
    ('Cost Optimization', 'spot-instance-strategy', 'Spot Instance Strategy for Fault-Tolerant Workloads', 'Mix spot and on-demand with interruption handling and diversified pools.', 'DevOps|Cost Optimization|Kubernetes', 'spot instances, interruption', 'All spot same instance type—capacity crunch took out entire batch fleet.', 'spot strategy', 'Batch, stateless, and fault-tolerant tiers.', 'Spot for stateful databases—data loss on reclaim.'),
    ('Cost Optimization', 'rightsizing-automation', 'Automated Rightsizing Recommendations', 'Act on rightsizing reports for VMs, RDS, and K8s requests weekly.', 'DevOps|Cost Optimization|Platform', 'rightsizing automation', '200 idle RDS instances sized for peak 2019 traffic.', 'rightsizing', 'Monthly FinOps review cadence minimum.', 'Rightsizing report ignored—no owner assigned per resource.'),
    ('Cost Optimization', 'idle-resource-reclamation', 'Idle Resource Reclamation Policies', 'Detect and reclaim unattached EBS, old snapshots, and unused LB IPs.', 'DevOps|Cost Optimization|Platform', 'idle resource reclamation', '$40k/year orphaned EBS volumes from deleted test clusters.', 'idle reclamation', 'Quarterly cost optimization sprints.', 'Aggressive reclamation without tag grace period—prod volume deleted.'),
    ('Cost Optimization', 's3-lifecycle-tiering', 'S3 Lifecycle Tiering and Intelligent-Tiering', 'Tier logs and backups to IA/Glacier with lifecycle rules and retrieval planning.', 'DevOps|Cost Optimization|Platform', 'S3 lifecycle, tiering', 'All logs in STANDARD—storage bill 3x after retention policy missing.', 'S3 lifecycle', 'Any bucket over 10TB without lifecycle policy.', 'Glacier retrieval during incident—hours delay unacceptable.'),
    ('Cost Optimization', 'cloud-reserved-capacity-planning', 'Reserved Capacity and Savings Plans Planning', 'Model RI/SP commitment from utilization baselines with conservative buffers.', 'DevOps|Cost Optimization|Platform', 'reserved instances, savings plans', '1-year RI for dev workload cancelled project month 2.', 'reserved capacity', 'Stable baseline workload over 70% utilization 90 days.', 'SP covering all usage—no room for architecture change.'),
    ('Cost Optimization', 'finops-showback-chargeback', 'FinOps Showback and Chargeback Models', 'Implement showback reports and optional chargeback to engineering teams.', 'DevOps|Cost Optimization|Platform', 'FinOps showback chargeback', 'Teams oversize resources—no visibility until central budget cut.', 'FinOps showback', 'When eng headcount exceeds 50 with cloud autonomy.', 'Chargeback without benchmarks—teams game labels only.'),
    ('Cost Optimization', 'multi-cloud-cost-benchmark', 'Multi-Cloud Cost Benchmarking Methodology', 'Compare equivalent workloads across clouds with normalized unit economics.', 'DevOps|Cost Optimization|Platform', 'multi-cloud cost benchmark', 'Lift-shift quote wrong—egress between clouds omitted from TCO.', 'cloud TCO benchmark', 'Multi-cloud strategy or vendor negotiation prep.', 'Benchmark on list price not negotiated enterprise discount.'),
    ('Cost Optimization', 'egress-cost-optimization', 'Cloud Egress Cost Optimization', 'Reduce cross-AZ, cross-region, and internet egress with topology and CDN.', 'DevOps|Cost Optimization|Networking', 'egress cost optimization', 'Cross-AZ traffic 30% of AWS bill—microservices chatty by default.', 'egress optimization', 'When network transfer line item grows month over month.', 'CDN for dynamic API—cache miss still expensive, wrong tool.'),
    ('Cost Optimization', 'storage-cost-monitoring', 'Storage Cost Monitoring and Anomaly Alerts', 'Alert on storage growth anomalies and per-team bucket budgets.', 'DevOps|Cost Optimization|Observability', 'storage cost monitoring', 'Log bucket doubled size in week—no alert until invoice.', 'storage monitoring', 'All object storage from day one.', 'Monitoring total only—not per-prefix attribution.'),
    ('Cost Optimization', 'serverless-cost-controls', 'Serverless Cost Controls and Concurrency Limits', 'Cap Lambda/Cloud Run concurrency and set per-function budgets.', 'DevOps|Cost Optimization|Platform', 'serverless cost controls', 'Recursive Lambda triggered 2M invocations—bill shock same hour.', 'serverless limits', 'Before exposing serverless to untrusted event sources.', 'No DLQ on async Lambda—retry loop billing explosion.'),
    ('Networking', 'external-dns-automation', 'External DNS Automation for Kubernetes Ingress', 'Sync Ingress/Gateway hostnames to Route53/Cloud DNS with ExternalDNS.', 'DevOps|Networking|Kubernetes', 'ExternalDNS, Route53', 'Manual DNS typo during cutover—hour of partial outage.', 'ExternalDNS', 'Kubernetes clusters exposing public hostnames.', 'ExternalDNS full zone access—can delete unrelated records.'),
    ('Networking', 'cert-manager-wildcard-certs', 'Wildcard TLS with cert-manager and DNS Providers', 'Automate wildcard cert renewal with DNS-01 and limited IAM scope.', 'DevOps|Networking|Security', 'wildcard TLS, cert-manager', 'Wildcard cert expired—HTTP challenge impossible for internal-only hosts.', 'wildcard certificates', 'Many subdomains under one service mesh or ingress.', 'Wildcard cert shared across prod and dev—compromise blast radius.'),
    ('Networking', 'service-mesh-mtls-ops', 'Service Mesh mTLS Operations and Rotation', 'Operate Istio/Linkerd mTLS: rotation, permissive vs strict, and debugging.', 'DevOps|Networking|Security', 'service mesh mTLS', 'Permissive mode left plaintext path—compliance audit failed.', 'mesh mTLS', 'Zero-trust service-to-service requirements.', 'Strict mTLS without debug tooling—on-call cannot tcpdump plaintext.'),
    ('Networking', 'cdn-cache-purge-strategies', 'CDN Cache Purge Strategies and Surrogate Keys', 'Purge CDN cache surgically with surrogate keys not full zone flush.', 'DevOps|Networking|CDN', 'CDN cache purge', 'Full CDN flush during incident—origin hammered, outage extended.', 'CDN purge', 'Content or API responses cached at edge.', 'Long TTL without purge path—stale assets for days.'),
    ('Networking', 'anycast-dns-failover', 'Anycast DNS and Health-Checked Failover', 'Configure health-checked DNS failover and anycast for global entry points.', 'DevOps|Networking|SRE', 'anycast DNS failover', 'Primary region down—DNS still routed dead IPs TTL 3600.', 'DNS failover', 'Global user-facing properties with RTO under 5 minutes.', 'Health check too shallow—passes while app broken.'),
    ('Networking', 'gateway-api-migration', 'Migrating from Ingress to Gateway API', 'Plan Gateway API migration with shared gateways and HTTPRoute splitting.', 'DevOps|Networking|Kubernetes', 'Gateway API migration', 'Ingress annotation limit hit—could not add canary weight rule.', 'Gateway API', 'New clusters or ingress feature wall on NGINX annotations.', 'Big-bang cutover—rollback required full DNS revert.'),
    ('Networking', 'ip-reputation-scoring', 'IP Reputation and Egress IP Warmup', 'Manage shared egress IP reputation and warmup for email/API integrations.', 'DevOps|Networking|Security', 'IP reputation, egress', 'New NAT IP blocked by partner API—reputation not warmed.', 'IP reputation', 'Outbound integrations with IP allowlists or spam filters.', 'Shared NAT with abusive tenant—whole IP blocklisted.'),
    ('Networking', 'egress-filtering-dns', 'Egress Filtering and DNS Logging for Compliance', 'Filter egress with firewall rules and log DNS for exfil detection.', 'DevOps|Networking|Security', 'egress filtering DNS', 'Unknown nightly DNS tunnel to suspicious domain—no egress log.', 'egress filtering', 'Regulated workloads requiring egress allowlists.', 'Allow-all egress with log only—no automated block on anomaly.'),
    ('Networking', 'global-load-balancer-health', 'Global Load Balancer Health Check Design', 'Design LB health checks that reflect user-visible failures not just TCP open.', 'DevOps|Networking|SRE', 'load balancer health checks', 'Healthy backend returning 500—HTTP check on /health only not /ready.', 'LB health checks', 'Any multi-region active-active setup.', 'Aggressive check interval—flapping removes good backends.'),
    ('Networking', 'tcp-connect-timeout-tuning', 'TCP and Connect Timeout Tuning at Edge', 'Tune connect/read timeouts at LB, mesh, and app layers consistently.', 'DevOps|Networking|SRE', 'TCP timeout tuning', 'Cascading hang—LB 300s timeout while app waited 600s.', 'timeout tuning', 'Latency incidents with thread or connection pool exhaustion.', 'Timeout zero meaning infinite—hidden default in library.'),
    ('Networking', 'private-link-hybrid-cloud', 'PrivateLink and Hybrid Cloud Connectivity Ops', 'Operate PrivateLink, VPN, and Direct Connect with redundancy and monitoring.', 'DevOps|Networking|Platform', 'PrivateLink hybrid cloud', 'Single VPN tunnel maintenance took down hybrid batch jobs.', 'PrivateLink', 'Hybrid cloud data paths with compliance requirements.', 'PrivateLink without DNS private zone—wrong endpoint resolved.'),
    ('Security', 'pod-security-standards', 'Pod Security Standards Enforcement', 'Enforce restricted/baseline PSS via admission labels and namespace defaults.', 'DevOps|Security|Kubernetes', 'Pod Security Standards', 'Privileged pod deployed in app namespace—PSS not enforced.', 'Pod Security Standards', 'All multi-tenant Kubernetes clusters.', 'Warn mode forever—never upgraded to enforce.'),
    ('Security', 'network-policy-audit', 'Network Policy Audit and Compliance Reporting', 'Continuously audit NetworkPolicy coverage and generate compliance reports.', 'DevOps|Security|Kubernetes', 'network policy audit', '30% namespaces without deny policy—audit found before pentest.', 'network policy audit', 'SOC2/Kubernetes compliance programs.', 'Audit snapshot only—drift after deploy not detected.'),
    ('Security', 'secrets-rotation-automation', 'Secrets Rotation Automation Without Outages', 'Rotate DB and API secrets with dual-credential windows and sync controllers.', 'DevOps|Security|Platform', 'secrets rotation', 'Emergency rotation restarted all pods simultaneously—brief outage.', 'secrets rotation', 'Any secret older than 90 days in production.', 'Single-slot secret—no overlap during rotation.'),
    ('Security', 'iam-policy-simulator', 'IAM Policy Simulator Before Production Changes', 'Validate IAM policy changes with simulator and access analyzer before apply.', 'DevOps|Security|Platform', 'IAM policy simulator', 'New policy looked minimal—simulator showed s3:* on all buckets.', 'IAM simulator', 'Before every production IAM change.', 'Simulator only on single action—missed condition key bug.'),
    ('Security', 'container-image-scanning-gate', 'Container Image Scanning Gates in CI/CD', 'Block deploy on critical CVE with Trivy/Grype and exception workflow.', 'DevOps|Security|CI/CD', 'container scanning, Trivy', 'Critical CVE in base image shipped—scan existed but warn-only.', 'image scanning gate', 'All container builds in CI.', 'Scan only latest tag in registry—missed pinned digest in manifest.'),
    ('Security', 'admission-webhook-security', 'Kubernetes Admission Webhook Security and HA', 'Run validating/mutating webhooks with HA, timeout budgets, and fail-closed policy.', 'DevOps|Security|Kubernetes', 'admission webhooks', 'Webhook timeout 1s—API server rejected all creates during webhook lag.', 'admission webhooks', 'Policy enforcement via Kyverno, OPA, or custom webhooks.', 'failurePolicy Ignore on security webhook—bypass during outage.'),
    ('Security', 'rbac-audit-automation', 'RBAC Audit Automation and Unused Binding Cleanup', 'Automate RBAC reviews: unused bindings, wildcard roles, and stale accounts.', 'DevOps|Security|Kubernetes', 'RBAC audit', '500 RoleBindings—40 referenced deleted ServiceAccounts.', 'RBAC audit', 'Quarterly access review minimum.', 'Audit report without remediation ticket—findings accumulate.'),
    ('Security', 'kubernetes-rbac-break-glass', 'Kubernetes Break-Glass RBAC for Incidents', 'Design emergency cluster-admin access with MFA, logging, and time bounds.', 'DevOps|Security|Kubernetes', 'break-glass RBAC', 'On-call shared static kubeconfig cluster-admin—no audit trail.', 'break-glass access', 'Before first production Kubernetes incident.', 'Break-glass without auto-expire—emergency access becomes permanent.'),
    ('Security', 'terraform-security-scanning', 'Terraform Security Scanning with Checkov/tfsec', 'Scan Terraform plans for misconfigurations before apply in CI.', 'DevOps|Security|Terraform', 'Checkov, tfsec, Terraform security', 'Public RDS snapshot flag in module—tfsec would have blocked merge.', 'Terraform scanning', 'All Terraform repos with production workspaces.', 'Scan main only—not PR plan files.'),
    ('Security', 'supply-chain-slsa', 'SLSA and Supply Chain Security for Artifacts', 'Implement SLSA provenance, signed commits, and verified builds.', 'DevOps|Security|Supply Chain', 'SLSA, supply chain security', 'Dependency confusion package almost merged—provenance check missing.', 'SLSA provenance', 'Software supply chain compliance initiatives.', 'Provenance generated in same pipeline it attests—weak trust.'),
    ('Security', 'zero-trust-workload-identity', 'Zero Trust Workload Identity Across Cloud and K8s', 'Unify workload identity: SPIFFE, IRSA, and federated credentials.', 'DevOps|Security|Platform', 'workload identity, SPIFFE', 'Long-lived kubeconfig on CI runner—should be OIDC federated role.', 'workload identity', 'Hybrid multi-cloud workload authentication.', 'SPIFFE without rotation—SVID expiry outage.'),
    ('Security', 'audit-log-immutable-trail', 'Immutable Audit Logs for Infrastructure Actions', 'Ship CloudTrail/K8s audit logs to immutable WORM storage with integrity monitoring.', 'DevOps|Security|Compliance', 'immutable audit logs', 'Attacker deleted CloudTrail—no WORM bucket configured.', 'immutable audit trail', 'Regulated or SOC2 infrastructure.', 'Logs mutable S3 bucket—tampering undetectable.'),
    ('Security', 'pci-dss-scope-reduction', 'PCI DSS Scope Reduction for Infrastructure', 'Segment cardholder data environments with network and RBAC boundaries.', 'DevOps|Security|Compliance', 'PCI DSS scope', 'Whole cluster in PCI scope—single shared namespace mistake.', 'PCI scope reduction', 'Any payment-adjacent workload on shared platform.', 'Scope doc outdated—new service connected to CDE unnoticed.'),
    ('Security', 'kill-switch-incident-response', 'Infrastructure Kill Switches for Incident Response', 'Pre-build kill switches: disable ingress, revoke tokens, scale to zero safely.', 'DevOps|Security|SRE', 'kill switch incident response', 'Ransomware spreading—no pre-tested way to isolate namespace fast.', 'kill switches', 'Incident response playbooks for tier-1 services.', 'Kill switch untested—removed wrong namespace during panic.'),
    ('Kubernetes', 'gateway-api-httproute-canary', 'Gateway API HTTPRoute Canary Traffic Splitting', 'Split traffic with Gateway API weight rules and GAMMA-compatible controllers.', 'DevOps|Kubernetes|Networking', 'Gateway API, HTTPRoute canary', 'Ingress annotation canary limit blocked fine-grained 5% test.', 'Gateway API', 'When Ingress annotations insufficient for traffic split.', 'Weights not summing to 100—controller rejected entire route.'),
    ('Helm', 'helm-starter-chart-scaffolding', 'Helm Starter Charts and Scaffolding Standards', 'Publish internal starter charts with security and observability baked in.', 'DevOps|Helm|Platform', 'Helm starter chart', 'New service chart missing PodDisruptionBudget—copied from empty template.', 'Helm starters', 'Onboarding new services to Kubernetes weekly.', 'Starter chart outdated—new hires scaffold insecure defaults.'),
    ('Observability', 'victoria-metrics-cluster-ops', 'VictoriaMetrics Cluster Operations', 'Operate VictoriaMetrics cluster: vminsert, vmselect, vmstorage scaling.', 'DevOps|Observability|Platform', 'VictoriaMetrics cluster', 'Prometheus single node ceiling—VM cluster horizontal scale fixed ingest.', 'VictoriaMetrics', 'Prometheus horizontal scaling or long retention needs.', 'vmstorage without replication—node loss loses history.'),
    ('MLOps', 'vector-db-ops-production', 'Vector Database Operations in Production', 'Operate Pinecone/Weaviate/pgvector: capacity, backup, and query SLAs.', 'DevOps|MLOps|RAG Ops', 'vector database ops', 'Vector index rebuild locked queries—no read replica during maintenance.', 'vector database', 'Production RAG or similarity search at scale.', 'Shared vector index dev/prod—bad embed test wiped prod.'),
    ('Data Pipelines', 'cdc-debezium-postgres-ops', 'CDC with Debezium and PostgreSQL Operations', 'Operate Debezium CDC: slots, heartbeats, schema changes, and Kafka connect.', 'DevOps|Data Pipelines|Data Engineering', 'Debezium CDC PostgreSQL', 'Replication slot bloat crashed Postgres—monitoring missing on pg_replication_slots.', 'Debezium CDC', 'Real-time analytics from OLTP PostgreSQL.', 'CDC without schema evolution plan—connector crash on ALTER.'),
]


def _code_block(category, suffix, tool):
    """Category-specific example manifests and commands."""
    name = suffix.replace("-", "_")
    if category == "Kubernetes":
        return textwrap.dedent(f"""\
            ```yaml
            # devops-{suffix}
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: {name}
              labels:
                app.kubernetes.io/part-of: devops-{suffix}
            spec:
              replicas: 3
              selector:
                matchLabels:
                  app: {name}
              template:
                metadata:
                  labels:
                    app: {name}
                spec:
                  containers:
                    - name: app
                      image: app:1.0.0
                      resources:
                        requests:
                          cpu: 100m
                          memory: 128Mi
            ```""")
    if category == "Helm":
        return textwrap.dedent(f"""\
            ```yaml
            # values fragment for {tool}
            replicaCount: 3
            resources:
              requests:
                cpu: 100m
                memory: 128Mi
            podDisruptionBudget:
              enabled: true
              minAvailable: 2
            ```""")
    if category == "Terraform":
        return textwrap.dedent(f"""\
            ```hcl
            # devops-{suffix}
            resource "aws_s3_bucket" "{name}" {{
              bucket = "org-{suffix}-logs"
              tags = {{
                ManagedBy = "terraform"
                Topic     = "devops-{suffix}"
              }}
            }}
            ```""")
    if category in ("CI/CD", "GitOps"):
        return textwrap.dedent(f"""\
            ```yaml
            # pipeline / GitOps snippet for devops-{suffix}
            name: {suffix}
            on:
              pull_request:
                paths: ["infra/{suffix}/**"]
            jobs:
              validate:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                  - run: make validate-{suffix}
            ```""")
    if category in ("Observability", "Chaos Engineering"):
        return textwrap.dedent(f"""\
            ```yaml
            # PrometheusRule / experiment hook for devops-{suffix}
            groups:
              - name: {name}
                rules:
                  - alert: {name.title()}HighErrorRate
                    expr: rate(http_errors_total{{job="{name}"}}[5m]) > 0.05
                    for: 10m
                    labels:
                      severity: page
            ```""")
    if category in ("MLOps", "Feature Stores", "RAG Ops", "Model Serving"):
        return textwrap.dedent(f"""\
            ```yaml
            apiVersion: serving.kserve.io/v1beta1
            kind: InferenceService
            metadata:
              name: {name}
            spec:
              predictor:
                model:
                  modelFormat:
                    name: sklearn
                  storageUri: s3://models/{suffix}/v1
            ```""")
    if category in ("Data Pipelines", "Spark/dbt"):
        return textwrap.dedent(f"""\
            ```python
            # Airflow / dbt task pattern for devops-{suffix}
            @task(retries=3, retry_delay=timedelta(minutes=5))
            def run_{name}():
                validate_schema("{suffix}")
                execute_transform("{suffix}")
            ```""")
    if category in ("Warehouse Modeling", "Cost Optimization"):
        return textwrap.dedent(f"""\
            ```sql
            -- warehouse / cost guard for devops-{suffix}
            CREATE TABLE analytics.{name}_fact (
              event_id VARCHAR PRIMARY KEY,
              event_ts TIMESTAMP NOT NULL,
              team_id VARCHAR
            );
            ```""")
    if category in ("Networking", "Security"):
        return textwrap.dedent(f"""\
            ```bash
            # ops check for devops-{suffix}
            kubectl get networkpolicy -A | grep -v "kube-system"
            aws iam simulate-principal-policy \\
              --policy-source-arn "$ROLE_ARN" \\
              --action-names s3:GetObject \\
              --resource-arns "arn:aws:s3:::prod-data/*"
            ```""")
    return textwrap.dedent(f"""\
        ```bash
        # operational command for devops-{suffix}
        kubectl apply -f manifests/{suffix}/
        helm upgrade --install {name} ./charts/{name} -f values/prod.yaml
        ```""")


def _build_sections(row):
    cat, suffix, title, desc, tags, keywords, hook, tool, when, mistake = row
    topic_label = title.split(":")[0]
    sections = [
        {
            "h": f"Problem framing: {topic_label}",
            "p1": hook,
            "p2": (
                f"Platform teams treat **{tool}** as solved after the first successful deploy. "
                f"Production disagrees: edge cases around {suffix.replace('-', ' ')}, dependency failures, "
                f"and human process gaps show up under real load. The sections below capture patterns "
                f"that survive review, incident response, and gradual traffic growth—not just a green CI badge."
            ),
        },
        {
            "h": f"Design principles for {tool}",
            "p1": (
                f"Explicit contracts beat tribal knowledge. Document who owns {tool} configuration, "
                f"which environments may change it, and how rollback works when a change misbehaves. "
                f"Prefer defaults that **fail closed**—deny, queue, or degrade safely rather than "
                f"return partial wrong answers."
            ),
            "p2": (
                f"A common failure mode: {mistake} "
                f"Bake guards into CI, admission control, or plan-time policy so the mistake is caught "
                f"before merge—not discovered by customers or auditors."
            ),
            "code": _code_block(cat, suffix, tool),
        },
        {
            "h": f"Implementation walkthrough",
            "p1": (
                f"Start with the smallest production-safe slice of **{title}**. "
                f"Ship observability first: structured logs, metrics with low-cardinality labels, and "
                f"traces where requests cross team boundaries. Without telemetry, you cannot prove "
                f"the change helped or hurt after rollout."
            ),
            "p2": (
                f"Automate repetitive steps—CLI scripts, GitOps repos, or pipeline jobs—so on-call "
                f"engineers do not hand-edit production during incidents. Keep runbooks next to dashboards "
                f"with the three golden signals: latency, errors, and saturation for {tool}."
            ),
        },
        {
            "h": f"Operational concerns in production",
            "p1": (
                f"Day-two operations for {cat.lower()} work is mostly guardrails: capacity headroom, "
                f"alert routing, and ownership rotation. Define SLOs tied to user-visible outcomes—not "
                f"vanity metrics like pod count alone. Page on symptom-based alerts (error budget burn, "
                f"queue age, failed reconciliation) and ticket on causes."
            ),
            "p2": (
                f"Run game days or fault injection in staging quarterly for {suffix.replace('-', ' ')}. "
                f"Inject latency, credential expiry, and partial outages. Update this runbook with what "
                f"broke—not generic advice copied from vendor docs."
            ),
        },
        {
            "h": f"Security and compliance angles",
            "p1": (
                f"Even when {topic_label} is not labeled security software, it participates in your "
                f"trust boundary. Apply least privilege to service accounts and CI roles. Rotate secrets "
                f"on a schedule with overlap windows. Validate inputs at the perimeter—especially when "
                f"{tool} accepts configuration from multiple teams."
            ),
            "p2": (
                f"For regulated workloads, maintain an immutable audit trail: who changed {tool} settings, "
                f"when, and from which pipeline or break-glass session. Prefer short-lived credentials and "
                f"OIDC federation over long-lived keys in environment variables."
            ),
        },
        {
            "h": f"Integration with platform standards",
            "p1": (
                f"Align {tool} with org-wide pod security, network policy, and secret management baselines. "
                f"If External Secrets Operator syncs credentials, verify rotation does not require "
                f"chart upgrades. If service mesh mTLS is mandatory, confirm sidecar injection labels "
                f"in rendered manifests before merge."
            ),
            "p2": (
                f"Capacity planning should precede rollout: estimate peak QPS, bytes per second, or "
                f"concurrent jobs; multiply by headroom (typically 1.5–2×); compare against quotas and "
                f"cloud limits. File increase requests before launch week, not during an incident."
            ),
        },
    ]
    return sections


def _enrich(row):
    cat, suffix, title, desc, tags, keywords, hook, tool, when, mistake = row
    title_short = title.split(":")[0].split(" with")[0]
    tags_list = [t.strip() for t in tags.split("|")]
    faqs = [
        (
            f"What is {title_short}?",
            f"{title_short} covers operational practices for {tool} in production {cat.lower()} environments: "
            f"design, rollout, observability, failure modes, and day-two maintenance—not a one-time setup task.",
        ),
        (f"When should teams prioritize {title_short}?", when),
        (f"What mistakes break {title_short}?", mistake),
    ]
    return {
        "category": cat,
        "suffix": suffix,
        "title": title,
        "desc": desc,
        "tags": tags_list,
        "keywords": keywords,
        "hook": hook,
        "tool": tool,
        "faqs": faqs,
        "sections": _build_sections(row),
    }


def _resources(category, tool):
    links = {
        "Kubernetes": [
            "https://kubernetes.io/docs/home/",
            "https://github.com/kubernetes/community/tree/master/contributors/devel/sig-architecture",
        ],
        "Helm": ["https://helm.sh/docs/", "https://github.com/helm/chart-testing"],
        "Terraform": ["https://developer.hashicorp.com/terraform/docs", "https://www.terraform.io/cloud-docs"],
        "CI/CD": ["https://docs.github.com/en/actions", "https://docs.gitlab.com/ee/ci/"],
        "GitOps": ["https://argo-cd.readthedocs.io/", "https://fluxcd.io/docs/"],
        "Observability": ["https://prometheus.io/docs/", "https://opentelemetry.io/docs/"],
        "Chaos Engineering": ["https://litmuschaos.io/docs/", "https://chaos-mesh.org/docs/"],
        "MLOps": ["https://mlflow.org/docs/latest/", "https://www.kubeflow.org/docs/"],
        "Data Pipelines": ["https://airflow.apache.org/docs/", "https://docs.getdbt.com/"],
    }
    default = [
        "https://kubernetes.io/docs/home/",
        "https://opentelemetry.io/docs/",
        "https://developer.hashicorp.com/terraform/docs",
    ]
    for key, urls in links.items():
        if category.startswith(key) or key in category:
            return urls
    return default


def render_post(idx, topic):
    slug = f"devops-{topic['suffix']}"
    pub = BASE_DATE + timedelta(days=idx)
    tags_yaml = "\n".join(f'  - "{t}"' for t in topic["tags"])
    faq_yaml = "\n".join(
        f'  - q: "{q}"\n    a: "{a}"' for q, a in topic["faqs"]
    )

    intro = (
        f"{topic['hook']}\n\n"
        f"This post walks through **{topic['title']}** for platform and SRE teams shipping "
        f"reliable infrastructure. {topic['desc']} You will get concrete configuration patterns, "
        f"operational guardrails, and review questions that catch mistakes before production—not "
        f"after an incident writes the requirements doc."
    )

    body_parts = [intro + "\n"]
    for sec in topic["sections"]:
        body_parts.append(f"## {sec['h']}\n\n{sec['p1']}\n")
        if sec.get("p2"):
            body_parts.append(f"\n{sec['p2']}\n")
        if sec.get("code"):
            body_parts.append(f"\n{sec['code']}\n")

    resources = _resources(topic["category"], topic["tool"])
    resource_lines = "\n".join(f"- {u}" for u in resources)
    body_parts.append(FOOTER)
    body_parts.append(f"\n## Resources\n\n{resource_lines}\n")

    body = "\n".join(body_parts)
    frontmatter = f"""---
title: "{topic['title']}"
slug: "{slug}"
description: "{topic['desc']}"
datePublished: "{pub.isoformat()}"
dateModified: "{pub.isoformat()}"
tags:
{tags_yaml}
keywords: "{topic['keywords']}"
faq:
{faq_yaml}
---

"""
    return slug, frontmatter + body


def _pad_content(content, topic):
    """Add topic-specific depth if under word target."""
    words = len(content.split())
    if words >= TARGET_WORDS:
        return content
    title_short = topic["title"].split(":")[0]
    extra = textwrap.dedent(f"""

## Operational deep dive

Production teams running **{title_short}** at scale should instrument three layers: control plane health (API latency, reconciliation errors), data plane throughput (request rates, queue depth), and cost signals (CPU/memory per unit of work). Dashboards that only chart infrastructure CPU miss user-visible regressions until error budgets burn.

Treat **{topic['tool']}** configuration as versioned artifacts. Store manifests in Git, review diffs like application code, and tag releases that match deployed versions. When incidents occur, the first question is "what changed?"—Git history and pipeline logs should answer that in under five minutes without SSH archaeology.

Schedule quarterly drills for {topic['category'].lower()} failure modes: dependency outage, credential expiry, regional failover, and traffic spike. Capture timelines during drills. Future on-call engineers inherit playbooks with real timestamps and thresholds—not generic bullet lists copied from vendor marketing.

## Debugging workflow when things go wrong

When {title_short} misbehaves in production, work top-down: confirm blast radius (one tenant, region, or cluster), check changes in the last 24 hours (deploys, flag flips, Terraform applies, config pushes), compare golden signals to baseline, reproduce with minimal input while capturing trace IDs, then fix forward or rollback before deep root-cause during an active incident.

Document what you measured—not just what you fixed. Add one integration test or alert per real incident so the same class of failure pages earlier next time. {topic['tool']} changes that cannot be observed are changes you cannot operate safely at 3 a.m.
""")
    return content.replace("\n## Resources\n", extra + "\n## Resources\n")


def main():
    raw = RAW_TOPICS
    if len(raw) != 250:
        raise SystemExit(f"Expected 250 topics, got {len(raw)}")

    existing = set()
    if os.path.isdir(BLOG_DIR):
        for f in os.listdir(BLOG_DIR):
            if f.endswith(".md"):
                existing.add(f[:-3])

    written = 0
    skipped = 0
    topics = [_enrich(r) for r in raw]
    examples = [f"devops-{t['suffix']}" for t in topics[:10]]

    for idx, topic in enumerate(topics):
        slug, content = render_post(idx, topic)
        if slug in existing:
            skipped += 1
            continue
        content = _pad_content(content, topic)
        path = os.path.join(BLOG_DIR, f"{slug}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written += 1
        existing.add(slug)

    print(f"Written: {written}")
    print(f"Skipped (already exist): {skipped}")
    print(f"Total defined: {len(topics)}")
    print("Example slugs:")
    for s in examples:
        print(f"  - {s}")


if __name__ == "__main__":
    main()
