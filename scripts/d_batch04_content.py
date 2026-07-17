"""Topic-specific bodies and FAQs for batch-04 D posts."""
CONTENT = {
    "devops-custom-scheduler-plugins": (
        [
            ('When should you write a custom scheduler plugin instead of nodeSelector or affinity?', 'Use plugins when placement logic must apply cluster-wide with consistent scoring—cost weighting across hundreds of node pools, compliance gates that reject ineligible nodes before binding, or topology spread that interacts with other filters. Labels and affinity work for per-workload rules; plugins encode platform policy once.'),
            ('What happens if a custom Filter plugin rejects every node?', 'The pod stays Pending with a scheduling failure event. Unlike a misconfigured nodeSelector, the scheduler may retry on every sync loop, flooding events. Always test plugins against empty node pools in staging, expose rejection reasons via scheduler framework events, and keep a default profile without the custom plugin for break-glass workloads.'),
            ('Can you run multiple scheduling profiles in one kube-scheduler?', 'Yes. Kubernetes 1.19+ supports KubeSchedulerConfiguration with multiple profiles, each with its own plugin set. Pods select a profile via schedulerName on the Pod spec. This lets you offer a compliance-hardened profile for regulated workloads and a latency-optimized profile for batch jobs without maintaining separate scheduler deployments.'),
            ('How do you safely roll out a new Score plugin?', "Deploy in Score-only mode first with weight 0 or on a staging cluster mirroring production node labels. Compare scheduling decisions via the scheduling framework's PodSchedulingProfile audit logs or a shadow scheduler that records would-have-bound nodes without binding. Promote weight gradually and watch Pending pod duration and placement skew metrics."),
        ],
        """A GDPR audit found twelve production pods on US-East worker nodes processing EU citizen data. The manifests looked compliant: every Deployment had `nodeSelector: region: eu-west`. Platform had missed the catch—three CronJobs and a Helm subchart spawned pods without that selector, and the default scheduler happily placed them wherever CPU was free. Compliance did not fail because someone forgot labels on one service; it failed because **placement policy lived in hundreds of scattered YAML files** instead of one enforceable scheduling contract.

Custom scheduler plugins fix that class of problem. Since Kubernetes 1.19, the scheduling framework exposes extension points—Filter, Score, PreFilter, Reserve, Permit—where you inject logic that runs for every schedulable pod. Combined with **scheduling profiles**, you can ship a `eu-compliant` profile that hard-rejects non-EU nodes before binding, while keeping a default profile for internal tooling.

## How the scheduling framework actually runs

When a pod enters the scheduling queue, kube-scheduler executes a pipeline:

```
Pod → PreFilter → Filter (per node) → PreScore → Score (per node) → Normalize → SelectHost → Reserve → Permit → Bind
```

**Filter plugins** remove nodes from consideration entirely—think taint-like logic without mutating nodes. **Score plugins** rank remaining nodes; weights in KubeSchedulerConfiguration multiply each plugin's 0–100 score. **Reserve** holds resources on the chosen node; **Permit** can delay binding for gang scheduling or quota gates.

The critical operational detail: Filter failures are binary. A buggy Filter that returns Unschedulable for valid nodes creates Pending pods that no amount of cluster autoscaling fixes. Score bugs skew placement—expensive nodes get all the traffic— but pods still land somewhere.

## Scheduling profiles: one binary, many policies

Before plugins, teams ran **multiple scheduler deployments**—`kube-scheduler-eu`, `kube-scheduler-gpu`—each a separate Deployment with duplicated leader election and upgrade risk. Profiles collapse that:

```yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
profiles:
  - schedulerName: default-scheduler
    plugins:
      score:
        enabled:
          - name: NodeResourcesBalancedAllocation
          - name: PodTopologySpread
  - schedulerName: eu-compliant
    plugins:
      filter:
        enabled:
          - name: NodeRegionFilter
      score:
        disabled:
          - name: NodeResourcesBalancedAllocation
        enabled:
          - name: NodeResourcesFit
            weight: 1
```

Pods opt in with `spec.schedulerName: eu-compliant`. Platform teams document which profiles exist, who may use them, and whether admission webhooks enforce profile selection for regulated namespaces.

## Building a region-compliance Filter plugin

The EU placement plugin is a textbook Filter: read pod labels or namespace annotations, read node labels, return Success or Unschedulable with a clear reason string.

```go
func (pl *NodeRegionFilter) Filter(ctx context.Context, state *framework.CycleState,
    pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
    required, ok := pod.Annotations["compliance.example/required-region"]
    if !ok {
        return framework.NewStatus(framework.Success, "")
    }
    nodeRegion := nodeInfo.Node().Labels["topology.kubernetes.io/region"]
    if nodeRegion != required {
        return framework.NewStatus(framework.Unschedulable,
            fmt.Sprintf("node region %q != required %q", nodeRegion, required))
    }
    return framework.NewStatus(framework.Success, "")
}
```

Register the plugin in the scheduler's registry, enable it only in the `eu-compliant` profile, and add a **fallback**: break-glass namespaces use `default-scheduler` with an audit alert if someone promotes workloads without the compliance profile.

## Cost-aware Score plugins

FinOps teams often want cheaper spot/preemptible nodes when latency SLO allows. A Score plugin reads node labels like `node.kubernetes.io/capacity-type: spot` and adds points for spot nodes when the pod carries `workload-tier: batch`. Weight it below topology spread plugins so HA workloads still respect zone balance.

Watch for **score normalization**: after all Score plugins run, the framework normalizes scores to 0–100. Document effective weights in runbooks—"spot preference weight 40" means little if PodTopologySpread runs at weight 200.

## The failure mode that blocks all scheduling

The audit hook from the opening: a team deployed a custom scheduler Deployment with only their compliance plugins enabled but **forgot to enable NodeResourcesFit and inter-pod affinity plugins** from the default profile. Every pod Pending. Events showed `0/84 nodes available: 84 node(s) didn't satisfy plugin NodeRegionFilter` even for pods that should use the default profile—because those pods still pointed at the custom schedulerName.

Rules that prevent this:

1. **Never replace the default profile**—add profiles alongside it.
2. Integration test: submit a vanilla nginx pod to each profile; assert Bound within 60s.
3. CI renders KubeSchedulerConfiguration and fails if required default plugins are disabled in any profile intended for general use.
4. Keep a documented break-glass Helm value to revert schedulerName cluster-wide.

## Observability and debugging Pending pods

Generic `kubectl describe pod` output rarely explains custom plugin rejections. Enable **scheduler framework event recording** and export metrics:

- `scheduler_plugin_execution_duration_seconds` per plugin stage
- Count of Unschedulable results by plugin name and reason prefix
- Histogram of Score spread per profile (detect "always picks same node pool")

For on-call, maintain a script that lists nodes with labels relevant to your plugins and cross-checks against a Pending pod's requirements—faster than reading plugin source during an incident.

Log at verbosity 4 during rollout only; permanent V(4) on production schedulers fills disks.

## Rollout checklist

Test on a cluster whose node labels mirror production skew—including edge cases like nodes missing optional labels your plugin assumes present. Run **descheduler** or workload migration drills: when you add a new Filter, existing pods do not reschedule; only new pods get the policy. Plan cordoned node drains if retroactive compliance matters.

Upgrade kube-scheduler with the control plane; plugin APIs evolve between minor versions. Pin `k8s.io/kubernetes` module versions in your plugin build to the cluster version minus one minor.

## Managed control planes and plugin gaps

EKS, GKE, and AKS expose varying levels of scheduler customization. GKE's custom schedulers often mean **separate scheduler deployments** rather than in-tree plugin registration on the managed control plane component. Before investing in a Go plugin, confirm whether your provider lets you patch `KubeSchedulerConfiguration` at all. When they do not, options narrow to:

- **Scheduling Gates** (1.27+) to hold pods until external controllers approve placement
- **Mutating admission** that sets nodeSelector/affinity from central policy—less elegant but portable
- **Secondary schedulers** for specific workload classes only

The EU compliance story at the top often lands here: a Filter plugin is ideal, but a ValidatingWebhook that rejects pods missing `schedulerName: eu-compliant` in regulated namespaces achieves most of the audit benefit without forking the managed scheduler.

## Performance and the PreFilter extension

Heavy PreFilter work blocks the entire scheduling cycle for one pod. If your plugin calls external APIs—pricing feeds, carbon intensity services, live compliance databases—you can starve the scheduling queue. Cache results with short TTL per node pool, fail open with a metric increment when the cache is stale, or move expensive lookups to asynchronous controllers that annotate nodes before the scheduler runs.

Benchmark with `scheduler_perf` or load-test by creating thousands of Pending pods in a KWOK cluster. Watch scheduling rate (`scheduler_schedule_attempts_total`) drop after enabling a new plugin—that regression is how you discover accidental O(n²) loops over node lists.

## Multi-scheduler operations at scale

Large fleets sometimes run a **shadow scheduler**—same configuration, `--leader-elect=false` on a deployment that never binds, only logs which node it would pick. Compare shadow decisions to production for a week before raising Score plugin weights. Shadow schedulers catch normalization bugs that unit tests miss because they never simulate full node lists with real taints and resource fragmentation.

Document plugin ownership in the platform catalog: repo link, on-call rotation, Kubernetes version compatibility matrix, and last game-day date. Custom scheduling code is control-plane-adjacent software; treat upgrades with the same rigor as etcd backups.

## Closing perspective

Custom scheduler plugins move placement policy from scattered manifest fields into auditable, versioned configuration. They are not free complexity—you own testing, upgrades, and the terrifying failure mode where nothing schedules. Used with profiles, fallback schedulers, and metrics on rejection reasons, they turn "we hope every team remembered the nodeSelector" into "the platform enforces placement once, correctly."""",
    ),

    "devops-daemonset-upgrade-strategy": (
        [
            ('What is the difference between DaemonSet RollingUpdate and OnDelete?', 'RollingUpdate replaces pods automatically when the pod template changes, respecting maxUnavailable. OnDelete waits until you manually delete each pod—slower but gives per-node control. Use OnDelete for agents where simultaneous restarts cause observable blind spots (log pipelines, security sensors); use RollingUpdate with tuned maxUnavailable when the agent tolerates brief overlap.'),
            ('How should maxUnavailable be set for a one-pod-per-node DaemonSet?', 'Never 100% on clusters where every node depends on the agent for observability or policy enforcement. Start with maxUnavailable: 10% or an absolute value like 1 on small clusters, so at most one node per hundred lacks the agent during rollout. For CNI or kube-proxy-class agents, some teams use maxUnavailable: 0 with maxSurge semantics via temporary second pods—verify your Kubernetes version supports surge on DaemonSets (1.22+).'),
            ('Why did 30% of nodes stay on an old log agent version after upgrade?', 'Common causes: rollout paused by maxUnavailable budget while unhealthy nodes block progress; selector or toleration mismatch so new pods CannotSchedule on tainted nodes; imagePullBackOff on subset of nodes; or OnDelete strategy with no follow-up deletion. Check DaemonSet status.desiredNumberScheduled vs updatedNumberScheduled and kubectl get pods -l app=agent -o wide for stragglers.'),
            ('Can you canary a DaemonSet upgrade on specific nodes?', 'Native DaemonSets lack Deployment-style canary controllers. Patterns: temporary second DaemonSet with nodeSelector matching canary nodes; use OnDelete and manually upgrade canary nodes first; or run a Helm hook Job that validates new agent on labeled nodes before widening the nodeSelector on the primary DaemonSet.'),
        ],
        """During a Sev-2, the on-call engineer opened the log search UI and got results from only seventy percent of the fleet. A DaemonSet upgrade for the log forwarder had rolled out three days earlier—green in CI, green in Argo CD sync status. Nobody noticed that **thirty percent of nodes still ran the previous image** until an incident needed full-fleet correlation. The upgrade strategy, not the agent code, created the blind spot.

DaemonSets exist to run exactly one pod per matching node—CNI plugins, kube-proxy, node exporters, EDR agents. Upgrading them is unlike Deployment rollouts: you cannot simply "surge" replicas on the same node without coordination, and taking too many agents offline at once removes telemetry or networking from a slice of the cluster simultaneously.

## DaemonSet update strategies in practice

Kubernetes supports two update types on DaemonSet spec:

| Strategy | Behavior | Best for |
|----------|----------|----------|
| `RollingUpdate` | Controller deletes/creates pods automatically | Agents that restart in seconds, tolerate brief gaps |
| `OnDelete` | New spec applies only after manual pod delete | CNI, storage drivers, anything where simultaneous restart hurts |

Since 1.22, RollingUpdate also supports **maxSurge** on DaemonSets—briefly run two pods on a node during handoff. That matters for agents that must bind a host port or maintain continuous packet capture.

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-forwarder
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 0
  selector:
    matchLabels:
      app: log-forwarder
  template:
    spec:
      tolerations:
        - operator: Exists
      containers:
        - name: forwarder
          image: registry.example/log-forwarder:2.4.1
```

`maxUnavailable: 1` on a hundred-node cluster means at most one node lacks a healthy forwarder at any moment—assuming the controller can place replacements.

## The math platform teams skip

For node-critical agents, compute **minimum observable fleet fraction** during rollout:

```
observable_nodes ≥ total_nodes - maxUnavailable_budget - unhealthy_nodes
```

If `maxUnavailable` is ten percent on a thousand-node cluster, one hundred nodes may lack the agent concurrently. If your SLO assumes ninety-nine percent log coverage, you fail your own SLO during every upgrade.

Tighten maxUnavailable, accept slower rollouts, or split agents into critical (OnDelete, manual waves) and non-critical tiers.

## Rolling CNI and security agents safely

CNI DaemonSet upgrades reorder network plumbing. A pattern that works:

1. **Canary nodes**: label `network-agent-canary=true`, deploy DaemonSet with nodeSelector limited to canary, validate pod networking and DNS for 48 hours.
2. Widen nodeSelector in waves—ten percent of node pools per day.
3. Keep previous image tag in OCI registry for instant revert; OnDelete old pods on failed nodes only.

Security EDR agents often cannot tolerate two agents fighting for the same kernel hooks—**maxSurge: 0** mandatory. Serialize restarts with maxUnavailable: 1 and maintenance windows per failure domain (one AZ at a time via node labels).

## Detecting straggler nodes

Argo CD "Synced" does not mean every node runs the new pod template. Monitor:

```promql
kube_daemonset_status_number_unavailable{daemonset="log-forwarder"}
  /
kube_daemonset_status_desired_number_scheduled{daemonset="log-forwarder"}
```

Alert when `updatedNumberScheduled != desiredNumberScheduled` for more than one hour.

Run a weekly controller script:

```bash
kubectl get daemonset log-forwarder -o jsonpath='{.status.updatedNumberScheduled}/{.status.desiredNumberScheduled}'
kubectl get pods -l app=log-forwarder -o jsonpath='{range .items[*]}{.spec.nodeName}{"\t"}{.spec.containers[0].image}{"\n"}{end}' \
  | sort -k2 | uniq -c -f1
```

The second command surfaces nodes still on old image digests even when counts look equal—useful when two ReplicaSets briefly overlap.

## Interaction with cluster upgrades

Node drains and DaemonSet upgrades race. When a node cordons for kernel patch, the DaemonSet pod evicts; when it uncordons, the controller schedules the current template. If the cluster-wide DaemonSet rollout paused mid-way, new nodes joining the pool may get **new** version while straggler old nodes persist elsewhere—widening version skew without a single deployment event.

Document: after node pool rotation, re-run straggler detection. Tie cluster-autoscaler scale-up events to DaemonSet sync checks.

## Rollback under pressure

RollingUpdate rollback = revert DaemonSet manifest to previous image, let controller roll forward again—**slow** if maxUnavailable is tight. Faster emergency path:

1. Revert Git/Helm revision.
2. If OnDelete: delete pods on nodes where new agent misbehaves (label selector).
3. If new agent crashes loop: old image pull plus forced delete restores service per node.

Keep previous DaemonSet manifest in release artifacts, not just image tags in values.yaml comments.

## Testing before fleet-wide promotion

In staging, use a node pool mirroring production taints and OS mix. Simulate:

- Agent pod crashLoop during rollout—does maxUnavailable stall entire DaemonSet?
- Image pull failure on one AZ—does skew concentrate on one region?
- Node NotReady during rollout—controller should not count it toward updated budget incorrectly (check Kubernetes version behavior).

Game day: disable log ingestion for nodes running old agent version deliberately; confirm monitoring fires before production upgrade.

## Helm, GitOps, and coordinated multi-agent upgrades

Real nodes run stacked DaemonSets—CNI, CSI node driver, log agent, metrics exporter. GitOps sync order matters when two agents share hostPath volumes or iptables rules. Use Argo CD sync waves: wave 0 CNI, wave 1 CSI, wave 2 observability. Within one DaemonSet chart, embed a **pre-upgrade Job** on a labeled canary node that validates host connectivity before the chart bumps image tags fleet-wide.

Helm `--wait` on DaemonSet releases returns success when the controller marks the rollout complete—not when every node reported healthy logs from the new version. Add post-sync verification as a CI step calling your straggler detection script; fail the pipeline if updated < desired.

## Node lifecycle and serverless add-ons

Managed node groups that recycle instances inherit whatever DaemonSet template was current at join time—good for convergence, bad if a paused rollout left the cluster in mixed state. For Fargate or virtual-kubelet nodes that **skip** DaemonSets entirely, document explicit exceptions: "log coverage SLO excludes Fargate profiles" or ship sidecar agents instead. Incidents fail when runbooks assume DaemonSet equals universal but the fleet is heterogeneous.

## Capacity during surge-enabled handoffs

When `maxSurge: 1` briefly runs two agent pods per node, CPU and memory requests sum on that node. A log forwarder requesting 200m CPU × 2 during handoff plus existing workload can push a node into CPU pressure, evicting unrelated app pods. Size surge headroom on node allocatable or set Guaranteed QoS on critical DaemonSets so they survive pressure events.

Document expected rollout duration in the change ticket: `(node_count / maxUnavailable) × (pod_restart_seconds + image_pull_seconds)` gives order-of-magnitude ETA. A three-thousand-node cluster at maxUnavailable 1 and ninety-second restarts needs days, not minutes—set stakeholder expectations before clicking sync.

When incidents require pausing rollout, use `kubectl rollout pause daemonset/log-forwarder` (Kubernetes 1.30+ supports pause on DaemonSet) or pin image digest in Git and stop sync—do not leave half-updated fleets untracked for weeks. Resume only after straggler report hits one hundred percent updated or you explicitly accept documented risk.

## Takeaway

DaemonSet upgrades fail quietly. Sync status and green pipelines hide partial fleet updates until an incident demands full coverage. Treat maxUnavailable as an **observability budget**, measure updated vs desired continuously, and prefer slow correct rollouts over fast blind ones—especially for the agents you only notice when they disappear.

## Coordination with cluster autoscaler

When autoscaler adds nodes during a rolling DaemonSet upgrade, new nodes immediately receive the **current** template while older nodes may still run the previous image if rollout paused. Autoscaler does not wait for DaemonSet sync completion. After scale-out events, always verify version homogeneity before declaring upgrade complete—especially for security agents where version skew creates audit findings.

## Privileged vs non-privileged agents

Privileged DaemonSets (CAP_SYS_ADMIN, hostPID, hostNetwork) face stricter change windows. Some orgs require change advisory board approval when maxUnavailable exceeds one on networking agents. Document blast radius in the ticket: which observability signals degrade when N percent of nodes lack the agent, and for how long.""",
    ),

    "devops-data-versioning-dvc": (
        [
            ('What does DVC track that Git cannot?', 'Large artifacts in remote storage with .dvc pointer files in Git for reproducible dvc repro runs.'),
            ('How manage DVC credentials in CI?', 'OIDC/IRSA short-lived roles—never commit keys in .dvc/config.'),
            ('Why champion model unreproducible?', 'Data moved or overwritten without dvc push; manual paths not hashed.'),
            ('DVC vs warehouse time travel?', 'DVC for file/ML artifacts; Delta/Iceberg snapshots for in-warehouse features.'),
        ],
        """Regulators requested March 3 fraud model training data; Git commit existed but S3 objects were lifecycle-deleted.

## dvc add and push workflow

Pointer files commit to Git; bytes live in remote. Immutability or versioning on bucket prevents silent hash breaks.

In practice, dvc add and push workflow for data versioning dvc requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dvc add and push workflow. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, dvc add and push workflow for data versioning dvc requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dvc add and push workflow. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, dvc add and push workflow for data versioning dvc requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dvc add and push workflow. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, dvc add and push workflow for data versioning dvc requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dvc add and push workflow. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## dvc.yaml pipelines

Stages with deps and outs; repro invalidates downstream only. Pair with container digest and requirements lock.

In practice, dvc.yaml pipelines for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing dvc.yaml pipelines. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dvc.yaml pipelines for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing dvc.yaml pipelines. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dvc.yaml pipelines for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing dvc.yaml pipelines. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dvc.yaml pipelines for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing dvc.yaml pipelines. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## CI repro pattern

PR pulls prod state manifest equivalent; repro changed stages; metrics gate on merge.

In practice, ci repro pattern for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci repro pattern. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci repro pattern for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci repro pattern. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci repro pattern for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci repro pattern. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci repro pattern for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci repro pattern. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Remote hygiene

Separate dev/prod prefixes; scan for credentials; alert on pull 404 spikes.

In practice, remote hygiene for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing remote hygiene. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, remote hygiene for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing remote hygiene. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, remote hygiene for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing remote hygiene. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, remote hygiene for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing remote hygiene. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Quarterly game day

Random historical tag reproduce on clean VM; compare inference epsilon tolerance.

In practice, quarterly game day for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing quarterly game day. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, quarterly game day for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing quarterly game day. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, quarterly game day for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing quarterly game day. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, quarterly game day for data versioning dvc requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing quarterly game day. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-database-connection-pools": (
        [
            ('Why pods exhaust max_connections?', 'pod_count × pool_max exceeds Postgres limit without PgBouncer multiplexing.'),
            ('Size pools from what metric?', 'Concurrent in-flight queries via pool wait metrics—not thread count defaults.'),
            ('Transaction vs session pooling?', 'Transaction mode multiplexes many clients; breaks prepared statements without ORM tweaks.'),
            ('Validate before scale events?', 'Load test at target pod count; watch pg_stat_activity and acquire latency.'),
        ],
        """Autoscaler added forty pods; Postgres logged too many clients already within ninety seconds.

## Sizing inequality

Document formula pods times pool_max less than max_connections. PgBouncer reduces backend count.

In practice, sizing inequality for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing sizing inequality. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, sizing inequality for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing sizing inequality. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, sizing inequality for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing sizing inequality. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, sizing inequality for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing sizing inequality. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Per-pod defaults

HTTP services often 5-10 connections; measure pool waits under peak before raising.

In practice, per-pod defaults for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing per-pod defaults. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, per-pod defaults for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing per-pod defaults. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, per-pod defaults for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing per-pod defaults. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, per-pod defaults for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing per-pod defaults. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## PgBouncer caveats

prepareThreshold zero; session features incompatible with transaction mode.

In practice, pgbouncer caveats for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pgbouncer caveats. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pgbouncer caveats for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pgbouncer caveats. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pgbouncer caveats for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pgbouncer caveats. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pgbouncer caveats for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pgbouncer caveats. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## K8s rollouts

Surge doubles pods briefly; include CronJob pools in totals; separate read replica pools.

In practice, k8s rollouts for database connection pools requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing k8s rollouts. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, k8s rollouts for database connection pools requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing k8s rollouts. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, k8s rollouts for database connection pools requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing k8s rollouts. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, k8s rollouts for database connection pools requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing k8s rollouts. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Observability table

pg_stat_activity, cl_waiting, Hikari active, acquire p99 alerts.

In practice, observability table for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability table. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability table for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability table. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability table for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability table. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability table for database connection pools requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability table. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-cicd-testing": (
        [
            ('What is slim CI?', 'state:modified+ runs changed models and downstream only using prod manifest comparison.'),
            ('Why defer fails?', 'Missing or stale prod manifest or dbt version skew vs artifact.'),
            ('Publish manifests how?', 'Upload target/manifest.json after every prod run to object storage manifest-latest.'),
            ('What slim CI still runs?', 'parse, lint, tests on modified+; nightly full runs catch drift slim PRs miss.'),
        ],
        """README typo triggered two-hour full dbt run on four hundred models; zero SQL changed.

## State comparison

dbt ls --select state:modified+ --state prod-state. Plus suffix includes downstream dependents.

In practice, state comparison for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing state comparison. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, state comparison for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing state comparison. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, state comparison for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing state comparison. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, state comparison for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing state comparison. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Defer in CI

Unresolved refs bind to prod relations for unchanged upstream—scratch schema only builds subgraph.

In practice, defer in ci for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
defer in ci. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, defer in ci for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
defer in ci. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, defer in ci for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
defer in ci. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, defer in ci for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
defer in ci. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## CI target schemas

Ephemeral CI_PR_NUMBER dropped after merge; pin dbt version to manifest producer.

In practice, ci target schemas for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci target schemas. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci target schemas for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci target schemas. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci target schemas for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci target schemas. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ci target schemas for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ci target schemas. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Merge queue freshness

Refresh manifest from main after each merge queue completion to avoid stale state.

In practice, merge queue freshness for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing merge queue freshness. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, merge queue freshness for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing merge queue freshness. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, merge queue freshness for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing merge queue freshness. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, merge queue freshness for dbt cicd testing requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing merge queue freshness. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Metrics

PR duration, selected model count, defer failures—alert when selection hits root models.

In practice, metrics for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
metrics. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, metrics for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
metrics. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, metrics for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
metrics. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, metrics for dbt cicd testing requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
metrics. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-exposures-lineage": (
        [
            ('What is a dbt exposure?', 'YAML documenting downstream dashboard or app depending on models for impact analysis.'),
            ('Why exposures stale hurt?', 'Column drops merge without knowing Looker tile still references field.'),
            ('CI enforcement?', 'Fail PR dropping columns referenced in exposures; require exposure updates with dashboard migrations.'),
            ('Exposures vs catalog?', 'dbt exposures version with models; export to DataHub for enterprise search.'),
        ],
        """Merged column drop broke Looker tile; exposure in repo still listed old field name from migration never updated.

## Exposure YAML

type dashboard, depends_on refs, owner, url. Lives beside models in git reviewed in PR.

In practice, exposure yaml for dbt exposures lineage requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing exposure yaml. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, exposure yaml for dbt exposures lineage requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing exposure yaml. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, exposure yaml for dbt exposures lineage requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing exposure yaml. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, exposure yaml for dbt exposures lineage requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing exposure yaml. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Impact analysis in CI

dbt ls --select exposure:*+ or custom script diff column sets vs exposure dependency graph.

In practice, impact analysis in ci for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing impact analysis in ci. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, impact analysis in ci for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing impact analysis in ci. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, impact analysis in ci for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing impact analysis in ci. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, impact analysis in ci for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing impact analysis in ci. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Ownership rotation

Exposure owner field maps to on-call; stale owner blocks merge via lint.

In practice, ownership rotation for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing ownership rotation. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ownership rotation for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing ownership rotation. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ownership rotation for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing ownership rotation. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ownership rotation for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing ownership rotation. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Migration workflow

Dashboard migration PR must update exposures same release; dual-write columns one sprint if needed.

In practice, migration workflow for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration workflow. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration workflow for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration workflow. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration workflow for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration workflow. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration workflow for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration workflow. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Lineage completeness

Connect BI tools via exposures even when native lineage exists—git review beats UI-only docs.

In practice, lineage completeness for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing lineage completeness. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, lineage completeness for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing lineage completeness. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, lineage completeness for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing lineage completeness. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, lineage completeness for dbt exposures lineage requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing lineage completeness. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-incremental-models": (
        [
            ('When incremental vs table?', 'Tables over ~100GB or hourly refresh where full scan cost prohibitive.'),
            ('incremental_strategy merge vs delete+insert?', 'Merge for upsert grain; delete+insert when partition replace cheaper on warehouse.'),
            ('unique_key requirement?', 'Required for merge dedup on retry—without it duplicates silently on failure replay.'),
            ('Micro-batch incremental?', 'High frequency small batches reduce latency; watch warehouse small file problem.'),
        ],
        """Nightly full scan on ten TB fact table because materialization stayed table not incremental merge.

## Strategy selection matrix

Append-only events append strategy; slowly changing dimensions merge with unique_key; partitions delete+insert.

In practice, strategy selection matrix for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection matrix. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, strategy selection matrix for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection matrix. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, strategy selection matrix for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection matrix. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, strategy selection matrix for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection matrix. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## is_incremental branch

Full refresh on --full-refresh; incremental filter on updated_at or event_time watermark.

In practice, is_incremental branch for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing is_incremental branch. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, is_incremental branch for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing is_incremental branch. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, is_incremental branch for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing is_incremental branch. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, is_incremental branch for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing is_incremental branch. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Late-arriving facts

Lookback window in incremental predicate; merge handles duplicates within window.

In practice, late-arriving facts for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing late-arriving facts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, late-arriving facts for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing late-arriving facts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, late-arriving facts for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing late-arriving facts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, late-arriving facts for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing late-arriving facts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Testing incrementals

Unit test SQL generation for is_incremental true/false; integration test retry idempotency.

In practice, testing incrementals for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing testing incrementals. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, testing incrementals for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing testing incrementals. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, testing incrementals for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing testing incrementals. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, testing incrementals for dbt incremental models requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing testing incrementals. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Ops monitoring

Row count deltas, runtime trend, merge bytes processed—alert 10x baseline.

In practice, ops monitoring for dbt incremental models requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ops monitoring. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ops monitoring for dbt incremental models requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ops monitoring. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ops monitoring for dbt incremental models requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ops monitoring. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, ops monitoring for dbt incremental models requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing ops monitoring. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-run-hooks-ops": (
        [
            ('on-run-end vs on-run-start?', 'Start grants session setup; end post-run grants notifications validation after models exist.'),
            ('Why hooks must be idempotent?', 'Retry runs double-apply grants or duplicate Slack posts without IF NOT EXISTS patterns.'),
            ('Hooks failing should fail run?', 'Yes for security grants; optional for notifications—document which hooks are hard vs soft.'),
            ('Macro vs hook?', 'Macros called explicitly; hooks run every invocation—keep hooks minimal and fast.'),
        ],
        """on-run-end GRANT failed silently in logs; BI could not query new models until manual DBA fix Monday.

## Grant automation

Generate GRANT SELECT from meta roles; warehouse-specific SQL in adapter macros.

In practice, grant automation for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing grant automation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, grant automation for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing grant automation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, grant automation for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing grant automation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, grant automation for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing grant automation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Notification hooks

Post to Slack with run results summary; rate limit to avoid spam on dev targets.

In practice, notification hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing notification hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, notification hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing notification hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, notification hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing notification hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, notification hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing notification hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Validation hooks

Assert row counts >0 for critical marts; fail run before consumers schedule queries.

In practice, validation hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing validation hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, validation hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing validation hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, validation hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing validation hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, validation hooks for dbt run hooks ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing validation hooks. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Idempotent SQL

CREATE SCHEMA IF NOT EXISTS; GRANT idempotent patterns per warehouse docs.

In practice, idempotent sql for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
idempotent sql. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, idempotent sql for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
idempotent sql. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, idempotent sql for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
idempotent sql. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, idempotent sql for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
idempotent sql. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## Observability

Log hook duration; alert slow hooks blocking job SLA.

In practice, observability for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
observability. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, observability for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
observability. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, observability for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
observability. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, observability for dbt run hooks ops requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
observability. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-semantic-layer": (
        [
            ('What problem does semantic layer solve?', 'Single metric definitions consumed by multiple BI tools—one ARR not three.'),
            ('Cache stale symptoms?', 'Dashboard disagrees with ad hoc SQL until cache TTL expires or invalidation missed.'),
            ('Governance?', 'Metric owners approve changes; breaking metric version bumps require consumer ack.'),
            ('Semantic layer vs dbt metrics?', 'dbt MetricFlow exposes metrics via API; operational concerns include cache, auth, SLA.'),
        ],
        """Marketing and finance ARR differed four percent—same name, different filters in Looker vs Tableau.

## Metric definitions as code

Version in git; CI tests metric SQL against known fixtures.

In practice, metric definitions as code for dbt semantic layer requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing metric definitions as code. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, metric definitions as code for dbt semantic layer requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing metric definitions as code. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, metric definitions as code for dbt semantic layer requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing metric definitions as code. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, metric definitions as code for dbt semantic layer requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing metric definitions as code. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Cache invalidation

Invalidate on prod dbt run completion webhook; monitor stale read rate.

In practice, cache invalidation for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache invalidation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache invalidation for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache invalidation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache invalidation for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache invalidation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache invalidation for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache invalidation. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Consumer onboarding

Document approved metrics list; block rogue calculated fields in BI via governance policy.

In practice, consumer onboarding for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing consumer onboarding. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, consumer onboarding for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing consumer onboarding. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, consumer onboarding for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing consumer onboarding. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, consumer onboarding for dbt semantic layer requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing consumer onboarding. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Performance

Push aggregations to warehouse; semantic layer not second database of full tables.

In practice, performance for dbt semantic layer requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
performance. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, performance for dbt semantic layer requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
performance. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, performance for dbt semantic layer requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
performance. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, performance for dbt semantic layer requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
performance. Document who approves production changes and the one-step rollback validated in the
last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## Rollout

Pilot one domain metrics; expand after cache and auth patterns proven.

In practice, rollout for dbt semantic layer requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
rollout. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, rollout for dbt semantic layer requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
rollout. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, rollout for dbt semantic layer requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
rollout. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, rollout for dbt semantic layer requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
rollout. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-snapshot-strategies": (
        [
            ('timestamp vs check strategy?', 'Timestamp when source has reliable updated_at; check when only full row hash detects change.'),
            ('Why check on mutable source corrupts?', 'Hard deletes invisible to check—history wrong without delete tracking.'),
            ('Snapshot frequency?', 'Balance storage vs analytics need; weekly snapshots may miss intra-week compliance questions.'),
            ('Invalid snapshot hard refresh?', 'Full refresh snapshot rebuilds history—plan storage and downstream impact.'),
        ],
        """Manual SCD2 table had effective dates wrong; snapshot used check strategy on source that hard-deleted rows.

## Type 2 with snapshots

dbt_valid_from/to columns; analytics join as-of date for point-in-time.

In practice, type 2 with snapshots for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing type 2 with snapshots. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, type 2 with snapshots for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing type 2 with snapshots. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, type 2 with snapshots for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing type 2 with snapshots. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, type 2 with snapshots for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing type 2 with snapshots. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Strategy selection

Audit source columns before choosing; document assumption in model description.

In practice, strategy selection for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, strategy selection for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, strategy selection for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, strategy selection for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing strategy selection. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Storage growth

Archive old snapshot partitions; monitor table size month over month.

In practice, storage growth for dbt snapshot strategies requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing storage growth. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, storage growth for dbt snapshot strategies requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing storage growth. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, storage growth for dbt snapshot strategies requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing storage growth. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, storage growth for dbt snapshot strategies requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing storage growth. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Downstream contracts

Consumers must filter dbt_valid_to is null for current row unless temporal join.

In practice, downstream contracts for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing downstream contracts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, downstream contracts for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing downstream contracts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, downstream contracts for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing downstream contracts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, downstream contracts for dbt snapshot strategies requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing downstream contracts. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Testing

Seed fixture with update delete sequences; assert snapshot rows match expected timeline.

In practice, testing for dbt snapshot strategies requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for dbt snapshot strategies requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for dbt snapshot strategies requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for dbt snapshot strategies requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dbt-star-schema-design": (
        [
            ('What is grain of a fact table?', 'One row means one business event at stated granularity—never ambiguous partial shipments.'),
            ('Conformed dimensions?', 'Shared dim_date dim_customer across marts enable consistent joins.'),
            ('Factless fact tables?', 'Bridge events without measures—easy to misuse causing join explosions.'),
            ('Surrogate keys?', 'Warehouse integer keys decouple from source id changes; natural keys documented.'),
        ],
        """Revenue double-counted because fact grain included partial shipment lines twice per order.

## Declare grain in YAML

meta grain field reviewed in PR; tests assert uniqueness of grain columns.

In practice, declare grain in yaml for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing declare grain in yaml. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, declare grain in yaml for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing declare grain in yaml. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, declare grain in yaml for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing declare grain in yaml. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, declare grain in yaml for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing declare grain in yaml. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Dimension design

Avoid snowflake unless storage cost demands; conformed dims maintained centrally in mesh.

In practice, dimension design for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dimension design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dimension design for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dimension design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dimension design for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dimension design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, dimension design for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dimension design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Measure additivity

Revenue additive; ratios non-additive—store components not pre-averaged rates in facts.

In practice, measure additivity for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing measure additivity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, measure additivity for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing measure additivity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, measure additivity for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing measure additivity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, measure additivity for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing measure additivity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Slowly changing dims

Type 1 overwrite vs Type 2 history—explicit choice per attribute.

In practice, slowly changing dims for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing slowly changing dims. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, slowly changing dims for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing slowly changing dims. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, slowly changing dims for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing slowly changing dims. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, slowly changing dims for dbt star schema design requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing slowly changing dims. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## BI performance

Align clustering keys on fact date and high filter columns.

In practice, bi performance for dbt star schema design requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing bi performance. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bi performance for dbt star schema design requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing bi performance. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bi performance for dbt star schema design requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing bi performance. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bi performance for dbt star schema design requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing bi performance. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dependency-latency-injection": (
        [
            ('What is latency injection for?', 'Validate timeouts bulkheads circuit breakers before production dependency slowdown.'),
            ('Chaos Mesh vs app-level?', 'Mesh injects without code change; app fault injection tests library behavior directly.'),
            ('Steady-state hypothesis?', 'Define SLI expected during injection—breaker open rate latency p99 error budget.'),
            ('Without monitoring injection is useless?', 'Prove breaker opened via metrics not assume from config alone.'),
        ],
        """Thirty second default HTTP timeout held four hundred threads during embedding outage—latency injection would have found it.

## Injection targets

Dependency client stub mesh VirtualService delay Chaos Mesh HTTPFault.

In practice, injection targets for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing injection targets. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, injection targets for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing injection targets. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, injection targets for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing injection targets. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, injection targets for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing injection targets. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Timeout tuning loop

Inject 200ms 500ms 2s; find knee where errors rise; set timeout just above p99 dependency latency.

In practice, timeout tuning loop for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing timeout tuning loop. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, timeout tuning loop for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing timeout tuning loop. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, timeout tuning loop for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing timeout tuning loop. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, timeout tuning loop for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing timeout tuning loop. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Bulkhead validation

Saturate one pool; verify other pools serve traffic.

In practice, bulkhead validation for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bulkhead validation. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, bulkhead validation for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bulkhead validation. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, bulkhead validation for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bulkhead validation. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, bulkhead validation for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bulkhead validation. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Game day script

Run injection in staging weekly automation; capture dashboard screenshots for runbook.

In practice, game day script for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing game day script. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, game day script for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing game day script. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, game day script for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing game day script. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, game day script for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing game day script. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Blast radius

Limit to namespace and service selectors; auto abort on SLO burn.

In practice, blast radius for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing blast radius. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, blast radius for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing blast radius. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, blast radius for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing blast radius. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, blast radius for dependency latency injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing blast radius. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-deployment-gates-smoke-tests": (
        [
            ('Deployment gate vs CI test?', 'Gate runs against deployed artifact in prod-like env after build succeeds.'),
            ('Smoke vs integration?', 'Smoke is fast critical path; integration broader—gates need sub-five-minute smoke for CD velocity.'),
            ('Mock smoke false confidence?', 'Hitting /health only misses DB misconfig; smoke must touch real read-only dependency.'),
            ('Canary promotion gate?', 'Compare error rate canary vs baseline before full promotion—automated not manual checkbox.'),
        ],
        """Pipeline green; production 500 on /api/v1/orders because smoke tested /health only.

## Smoke test design

Three to five requests representing revenue auth read paths with synthetic tenant.

In practice, smoke test design for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing smoke test design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, smoke test design for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing smoke test design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, smoke test design for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing smoke test design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, smoke test design for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing smoke test design. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Gate in CD

Block promote until smoke pass against canary URL; rollback on fail automatic.

In practice, gate in cd for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gate in cd. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gate in cd for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gate in cd. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gate in cd for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gate in cd. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gate in cd for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gate in cd. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Environment parity

Smoke uses same secrets resolver and network path as prod—not localhost mocks.

In practice, environment parity for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing environment parity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, environment parity for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing environment parity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, environment parity for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing environment parity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, environment parity for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing environment parity. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Flake control

Retry once with jitter; quarantine flaky smoke as Sev-2 tech debt.

In practice, flake control for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing flake control. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, flake control for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing flake control. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, flake control for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing flake control. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, flake control for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing flake control. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Observability

Smoke duration and fail rate dashboard; alert on skipped gate manual override.

In practice, observability for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, observability for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, observability for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, observability for deployment gates smoke tests requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dimensional-modeling-pitfalls": (
        [
            ('Snowflaking dimensions when bad?', 'When BI generates 12-way joins timeout; flatten unless storage critical.'),
            ('Junk dimensions?', 'Low-cardinality flags belong in fact row not separate dim with fanout.'),
            ('Bridge tables without weight?', 'Many-to-many bridges duplicate measures if weight not applied in aggregation.'),
            ('Role-playing dimensions?', 'Multiple date keys need aliases or BI confusion on which dim_date join.'),
        ],
        """Over-normalized product hierarchy caused twelve-way join timeout in Looker on cloud warehouse.

## Pitfall catalog

Document anti-patterns in modeling guide; PR checklist references guide.

In practice, pitfall catalog for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pitfall catalog. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pitfall catalog for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pitfall catalog. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pitfall catalog for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pitfall catalog. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, pitfall catalog for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing pitfall catalog. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Bridge weighting

Allocate fraction per bridge row; test sum equals fact measure on sample.

In practice, bridge weighting for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bridge weighting. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bridge weighting for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bridge weighting. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bridge weighting for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bridge weighting. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, bridge weighting for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing bridge weighting. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Degenerate dimensions

Order id on fact row OK at grain; do not join wide varchar dim unnecessarily.

In practice, degenerate dimensions for dimensional modeling pitfalls requires aligning platform
and application teams on failure modes. Staging must reproduce production traffic shape—not
uniform load—before changing degenerate dimensions. Document who approves production changes and
the one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, degenerate dimensions for dimensional modeling pitfalls requires aligning platform
and application teams on failure modes. Staging must reproduce production traffic shape—not
uniform load—before changing degenerate dimensions. Document who approves production changes and
the one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, degenerate dimensions for dimensional modeling pitfalls requires aligning platform
and application teams on failure modes. Staging must reproduce production traffic shape—not
uniform load—before changing degenerate dimensions. Document who approves production changes and
the one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, degenerate dimensions for dimensional modeling pitfalls requires aligning platform
and application teams on failure modes. Staging must reproduce production traffic shape—not
uniform load—before changing degenerate dimensions. Document who approves production changes and
the one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Cloud warehouse realities

Columnar storage reduces snowflake storage benefit; favor wide dims within reason.

In practice, cloud warehouse realities for dimensional modeling pitfalls requires aligning
platform and application teams on failure modes. Staging must reproduce production traffic
shape—not uniform load—before changing cloud warehouse realities. Document who approves production
changes and the one-step rollback validated in the last game day. Pair technical controls with
metrics tied to user-visible outcomes: latency, errors, freshness, cost.

In practice, cloud warehouse realities for dimensional modeling pitfalls requires aligning
platform and application teams on failure modes. Staging must reproduce production traffic
shape—not uniform load—before changing cloud warehouse realities. Document who approves production
changes and the one-step rollback validated in the last game day. Pair technical controls with
metrics tied to user-visible outcomes: latency, errors, freshness, cost.

In practice, cloud warehouse realities for dimensional modeling pitfalls requires aligning
platform and application teams on failure modes. Staging must reproduce production traffic
shape—not uniform load—before changing cloud warehouse realities. Document who approves production
changes and the one-step rollback validated in the last game day. Pair technical controls with
metrics tied to user-visible outcomes: latency, errors, freshness, cost.

In practice, cloud warehouse realities for dimensional modeling pitfalls requires aligning
platform and application teams on failure modes. Staging must reproduce production traffic
shape—not uniform load—before changing cloud warehouse realities. Document who approves production
changes and the one-step rollback validated in the last game day. Pair technical controls with
metrics tied to user-visible outcomes: latency, errors, freshness, cost.

## Review ritual

Model review office hours for new facts before merge to main.

In practice, review ritual for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing review ritual. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, review ritual for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing review ritual. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, review ritual for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing review ritual. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, review ritual for dimensional modeling pitfalls requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing review ritual. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dind-rootless-buildkit": (
        [
            ('Why avoid privileged DinD?', 'docker.sock and privileged pods expand escape surface—CVE history forced CI lockdowns.'),
            ('BuildKit vs Kaniko?', 'BuildKit faster with cache; Kaniko daemonless but cache misconfig causes 10x builds teams bypass with DinD.'),
            ('Rootless BuildKit limits?', 'Some Dockerfile tricks need fuse-overlayfs or skip chown—document allowed patterns.'),
            ('Cache in CI?', 'Registry cache importers or local cache mounts—invalidate on Dockerfile base change.'),
        ],
        """Privileged DinD escape CVE forced emergency CI lockdown; all builds stopped two days.

## Rootless pod spec

runAsUser 1000, no privileged, BuildKit daemon sidecar or kubectl buildx.

In practice, rootless pod spec for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing rootless pod spec. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, rootless pod spec for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing rootless pod spec. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, rootless pod spec for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing rootless pod spec. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, rootless pod spec for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing rootless pod spec. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## GitLab/Kaniko migration

Replace docker build with buildctl/buildkitd socket mount unprivileged.

In practice, gitlab/kaniko migration for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitlab/kaniko migration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitlab/kaniko migration for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitlab/kaniko migration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitlab/kaniko migration for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitlab/kaniko migration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitlab/kaniko migration for dind rootless buildkit requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitlab/kaniko migration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Cache strategy

type=registry cache-to/cache-from; measure build duration weekly.

In practice, cache strategy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache strategy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache strategy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache strategy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache strategy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache strategy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, cache strategy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing cache strategy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Supply chain

Pin base images by digest; scan in pipeline; deny latest tags in prod builds.

In practice, supply chain for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing supply chain. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, supply chain for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing supply chain. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, supply chain for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing supply chain. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, supply chain for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing supply chain. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Fallback policy

Break-glass privileged only isolated runner pool with audit log.

In practice, fallback policy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing fallback policy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, fallback policy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing fallback policy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, fallback policy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing fallback policy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, fallback policy for dind rootless buildkit requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing fallback policy. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dns-failure-injection": (
        [
            ('Why DNS chaos?', 'CoreDNS overload or upstream failure cascades to every dependency using hostnames.'),
            ('CoreDNS vs external DNS?', 'Test both; apps caching DNS behave differently on TTL expiry during outage.'),
            ('Resolver fallback?', 'nscd/CoreDNS NodeLocal cache—document expected behavior when authoritative fails.'),
            ('Prod DNS chaos?', 'Only with blast limits and error budget stop—staging continuous preferred.'),
        ],
        """CoreDNS CPU spiked during rollout; cascading timeouts undetected until customer reports.

## Failure modes

SERVFAIL slow responses NXDOMAIN poisoned cache negative TTL storms.

In practice, failure modes for dns failure injection requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing failure modes. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, failure modes for dns failure injection requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing failure modes. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, failure modes for dns failure injection requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing failure modes. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, failure modes for dns failure injection requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing failure modes. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Litmus/Chaos Mesh DNS

DNSChaos patterns; scope by label not cluster-wide.

In practice, litmus/chaos mesh dns for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing litmus/chaos mesh dns. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, litmus/chaos mesh dns for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing litmus/chaos mesh dns. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, litmus/chaos mesh dns for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing litmus/chaos mesh dns. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, litmus/chaos mesh dns for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing litmus/chaos mesh dns. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Application resilience

Retry with jitter on DNS errors; avoid infinite tight loops amplifying QPS.

In practice, application resilience for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing application resilience. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, application resilience for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing application resilience. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, application resilience for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing application resilience. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, application resilience for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing application resilience. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## NodeLocal DNSCache

Reduce CoreDNS load; test chaos with cache enabled production-like.

In practice, nodelocal dnscache for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nodelocal dnscache. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, nodelocal dnscache for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nodelocal dnscache. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, nodelocal dnscache for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nodelocal dnscache. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, nodelocal dnscache for dns failure injection requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nodelocal dnscache. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Runbook

Scale CoreDNS; check upstream forwarder; rollback deployment if version correlated.

In practice, runbook for dns failure injection requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
runbook. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, runbook for dns failure injection requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
runbook. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, runbook for dns failure injection requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
runbook. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, runbook for dns failure injection requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
runbook. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-downward-api-metadata": (
        [
            ('What can Downward API expose?', 'labels annotations name namespace uid resource limits via env or volume files.'),
            ('Why env vs volume?', 'Volumes update on label change without pod restart for some fields; env fixed at start.'),
            ('Security pitfall?', 'Projecting sensitive annotations into env visible to all containers and process list.'),
            ('Use cases?', 'Telemetry agent tags traces with pod version; autoscaler hints; quota-aware batch sizing.'),
        ],
        """Metrics agent tagged all spans with hardcoded service version—rollouts invisible in traces.

## fieldRef label example

Expose app.kubernetes.io/version from pod labels into OTEL_RESOURCE_ATTRIBUTES.

In practice, fieldref label example for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing fieldref label example. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, fieldref label example for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing fieldref label example. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, fieldref label example for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing fieldref label example. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, fieldref label example for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing fieldref label example. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## resourceFieldRef limits

Container aware of memory limit for self-throttling batch buffers.

In practice, resourcefieldref limits for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing resourcefieldref limits. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, resourcefieldref limits for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing resourcefieldref limits. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, resourcefieldref limits for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing resourcefieldref limits. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, resourcefieldref limits for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing resourcefieldref limits. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Avoid secret annotations

Never mount registry tokens via Downward API; use projected volumes separately.

In practice, avoid secret annotations for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing avoid secret annotations. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, avoid secret annotations for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing avoid secret annotations. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, avoid secret annotations for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing avoid secret annotations. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, avoid secret annotations for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing avoid secret annotations. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## GitOps label consistency

Helm chart sets version label; Downward API picks up automatically each deploy.

In practice, gitops label consistency for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitops label consistency. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitops label consistency for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitops label consistency. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitops label consistency for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitops label consistency. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, gitops label consistency for downward api metadata requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing gitops label consistency. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Testing

Roll label change; verify agent picks up volume refresh or restart policy documented.

In practice, testing for downward api metadata requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for downward api metadata requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for downward api metadata requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for downward api metadata requires aligning platform and application teams on
failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dynamodb-feature-serving": (
        [
            ('Why DynamoDB for features?', 'Single-digit ms at high QPS with on-demand scaling for spiky launch traffic.'),
            ('GSI hot partition?', 'Popular entity keys concentrate on one partition—shuffle suffix or write sharding.'),
            ('On-demand vs provisioned?', 'On-demand for unknown launch spikes; provisioned with auto scaling when steady.'),
            ('Feature freshness SLA?', 'TTL attributes and stream Lambda updates; stale features worse than missing defaults.'),
        ],
        """Launch day throttled reads on feature table—provisioned capacity not switched to on-demand.

## Key design

Composite pk/sk entity_id feature_group; avoid monotonic hot keys.

In practice, key design for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing key design. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, key design for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing key design. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, key design for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing key design. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, key design for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing key design. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## GSI patterns

Lookup by secondary access pattern; monitor ConsumedReadCapacityUnits per key.

In practice, gsi patterns for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing gsi patterns. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gsi patterns for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing gsi patterns. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gsi patterns for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing gsi patterns. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, gsi patterns for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing gsi patterns. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## BatchGet pipeline

ML inference batch features; respect 16MB and 100 item limits split batches.

In practice, batchget pipeline for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing batchget pipeline. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, batchget pipeline for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing batchget pipeline. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, batchget pipeline for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing batchget pipeline. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, batchget pipeline for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing batchget pipeline. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Streams to online store

Materialize offline warehouse to Dynamo via stream processor idempotent upsert.

In practice, streams to online store for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing streams to online store. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, streams to online store for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing streams to online store. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, streams to online store for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing streams to online store. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, streams to online store for dynamodb feature serving requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing streams to online store. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Monitoring

Throttling metrics SystemErrors p99 latency alarms on hot partitions.

In practice, monitoring for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for dynamodb feature serving requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-ebpf-observability-cilium": (
        [
            ('Hubble vs tcpdump?', 'Hubble aggregates L3/L7 flows with policy verdict labels across cluster—not single interface.'),
            ('Policy verification?', 'Flow marked forwarded despite NetworkPolicy deny indicates mislabel or hostNetwork bypass.'),
            ('Metrics retention?', 'Hubble metrics without retention plan too short for trend; export to Prometheus Mimir.'),
            ('Performance impact?', 'eBPF overhead low but monitor drop counters on high PPS nodes.'),
        ],
        """NetworkPolicy YAML looked correct; Hubble showed DNS bypass via hostNetwork pod.

## Enable Hubble UI relay

Relay aggregates flows; UI for incident search by pod label.

In practice, enable hubble ui relay for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing enable hubble ui relay. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, enable hubble ui relay for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing enable hubble ui relay. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, enable hubble ui relay for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing enable hubble ui relay. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, enable hubble ui relay for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing enable hubble ui relay. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Policy troubleshooting

Compare Policy verdict DROPPED vs FORWARDED on same label selector.

In practice, policy troubleshooting for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing policy troubleshooting. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, policy troubleshooting for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing policy troubleshooting. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, policy troubleshooting for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing policy troubleshooting. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, policy troubleshooting for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing policy troubleshooting. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## L7 HTTP visibility

Requires visibility annotation on pod; balance cardinality vs debug need.

In practice, l7 http visibility for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing l7 http visibility. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, l7 http visibility for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing l7 http visibility. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, l7 http visibility for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing l7 http visibility. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, l7 http visibility for ebpf observability cilium requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing l7 http visibility. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Alerting

Unexpected egress to CIDR outside allowlist from tier-1 namespaces.

In practice, alerting for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alerting. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, alerting for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alerting. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, alerting for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alerting. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, alerting for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alerting. Document who approves production changes and the one-step rollback validated in
the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## Integration

Export flows to SIEM for compliance; sample at edge to control cost.

In practice, integration for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing integration. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, integration for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing integration. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, integration for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing integration. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, integration for ebpf observability cilium requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing integration. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-egress-cost-optimization": (
        [
            ('Why cross-AZ expensive?', 'Cloud charges per GB between AZs; chatty microservices multiply cost silently.'),
            ('Topology spread cost?', 'HA spread across AZ necessary—reduce chatter via locality-aware clients or caching.'),
            ('CDN wrong for APIs?', 'Dynamic API cache miss still pays egress; CDN for static assets primarily.'),
            ('Measure how?', 'VPC flow logs cost allocation tags per service mesh telemetry bytes by destination AZ.'),
        ],
        """Cross-AZ traffic thirty percent of AWS bill—default microservice placement ignored locality.

## Service mesh locality

Prefer same AZ endpoint when healthy; fallback cross-AZ on failure only.

In practice, service mesh locality for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing service mesh locality. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, service mesh locality for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing service mesh locality. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, service mesh locality for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing service mesh locality. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, service mesh locality for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing service mesh locality. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Data placement

Colocate compute with data store AZ; avoid cross-region replication for non-DR paths.

In practice, data placement for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data placement. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data placement for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data placement. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data placement for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data placement. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data placement for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data placement. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Compression and protobuf

Reduce bytes per RPC; audit verbose JSON internal APIs.

In practice, compression and protobuf for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compression and protobuf. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, compression and protobuf for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compression and protobuf. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, compression and protobuf for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compression and protobuf. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, compression and protobuf for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compression and protobuf. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## NAT gateway concentration

Single NAT multiplies cross-AZ hairpin; per-AZ NAT or VPC endpoints.

In practice, nat gateway concentration for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nat gateway concentration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, nat gateway concentration for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nat gateway concentration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, nat gateway concentration for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nat gateway concentration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, nat gateway concentration for egress cost optimization requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing nat gateway concentration. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## FinOps review

Monthly top talkers dashboard; assign owner per service team chargeback.

In practice, finops review for egress cost optimization requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing finops review. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, finops review for egress cost optimization requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing finops review. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, finops review for egress cost optimization requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing finops review. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, finops review for egress cost optimization requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing finops review. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-egress-filtering-dns": (
        [
            ('Egress allowlist vs log-only?', 'Log-only fails compliance; allowlist with alert on deny for exfil detection.'),
            ('DNS logging for security?', 'Query logs reveal C2 domains before TCP connect; correlate with proxy denies.'),
            ('Default deny rollout?', 'Start monitor mode inventory domains; then tighten allowlist with break-glass.'),
            ('Egress from pods?', 'NetworkPolicy plus egress gateway or firewall appliance; hostNetwork exceptions documented.'),
        ],
        """Unknown nightly DNS queries to suspicious TLD—no egress log existed to correlate.

## Domain allowlist tiers

Tier1 production strict; tier2 staging relaxed with anomaly detection.

In practice, domain allowlist tiers for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing domain allowlist tiers. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, domain allowlist tiers for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing domain allowlist tiers. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, domain allowlist tiers for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing domain allowlist tiers. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, domain allowlist tiers for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing domain allowlist tiers. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## DNS logging pipeline

CoreDNS log plugin or NodeLocal forward to SIEM; retain per policy.

In practice, dns logging pipeline for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dns logging pipeline. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, dns logging pipeline for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dns logging pipeline. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, dns logging pipeline for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dns logging pipeline. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, dns logging pipeline for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing dns logging pipeline. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Automated block

SOAR playbook on high entropy domain score auto ticket not auto block first week.

In practice, automated block for egress filtering dns requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing automated block. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, automated block for egress filtering dns requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing automated block. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, automated block for egress filtering dns requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing automated block. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, automated block for egress filtering dns requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing automated block. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Compliance mapping

PCI requires egress restriction evidence; store 90 day DNS logs immutable.

In practice, compliance mapping for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compliance mapping. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, compliance mapping for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compliance mapping. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, compliance mapping for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compliance mapping. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, compliance mapping for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing compliance mapping. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## False positive handling

Domain ticket workflow for developers; SLA to unblock legitimate SaaS.

In practice, false positive handling for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing false positive handling. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, false positive handling for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing false positive handling. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, false positive handling for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing false positive handling. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, false positive handling for egress filtering dns requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing false positive handling. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-ephemeral-storage-limits": (
        [
            ('emptyDir without limits?', 'Pod can fill node disk; kubelet evicts others unpredictably.'),
            ('requests vs limits ephemeral-storage?', 'Both matter for scheduling and eviction ordering; set both for log-heavy pods.'),
            ('Monitoring?', 'kubelet stats summary container_fs_usage_bytes; alert before node pressure.'),
            ('Sidecar logs?', 'Shared emptyDir between app and log shipper counts toward same pod quota.'),
        ],
        """Log-heavy pod filled node disk; kubelet evicted unrelated production pods on same node.

## Set limits example

ephemeral-storage requests 1Gi limits 2Gi on download or log workloads.

In practice, set limits example for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing set limits example. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, set limits example for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing set limits example. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, set limits example for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing set limits example. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, set limits example for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing set limits example. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Eviction behavior

Node pressure evicts best-effort pods over guaranteed; size Guaranteed for critical.

In practice, eviction behavior for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing eviction behavior. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, eviction behavior for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing eviction behavior. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, eviction behavior for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing eviction behavior. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, eviction behavior for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing eviction behavior. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Alternatives

Stream logs stdout only; avoid large emptyDir caches use PVC with size limit.

In practice, alternatives for ephemeral storage limits requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alternatives. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, alternatives for ephemeral storage limits requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alternatives. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, alternatives for ephemeral storage limits requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alternatives. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, alternatives for ephemeral storage limits requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing alternatives. Document who approves production changes and the one-step rollback
validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Cluster autoscaling

Disk pressure should trigger node replacement not endless evictions.

In practice, cluster autoscaling for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing cluster autoscaling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, cluster autoscaling for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing cluster autoscaling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, cluster autoscaling for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing cluster autoscaling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, cluster autoscaling for ephemeral storage limits requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing cluster autoscaling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Testing

Load test write to emptyDir until limit; verify OOMKilled vs evicted behavior documented.

In practice, testing for ephemeral storage limits requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for ephemeral storage limits requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for ephemeral storage limits requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

In practice, testing for ephemeral storage limits requires aligning platform and application teams
on failure modes. Staging must reproduce production traffic shape—not uniform load—before changing
testing. Document who approves production changes and the one-step rollback validated in the last
game day. Pair technical controls with metrics tied to user-visible outcomes: latency, errors,
freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-etcd-backup-restore-ops": (
        [
            ('Why restore failed mid-compaction?', 'Snapshot taken during compaction window inconsistent; use consistent snapshot API.'),
            ('How often backup etcd?', 'Hourly snapshots with retention; RPO documented; off-cluster storage immutable.'),
            ('Restore drill frequency?', 'Quarterly full restore to isolated control plane validates RTO not wishful.'),
            ('Managed K8s etcd?', 'Provider backs up but verify restore procedure and RTO in contract—not assume.'),
        ],
        """Restored etcd snapshot taken mid-compaction—cluster unusable until rebuild from older backup.

## etcdctl snapshot save

Run from authorized endpoint; verify sha256; upload to object storage versioning enabled.

In practice, etcdctl snapshot save for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing etcdctl snapshot save. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, etcdctl snapshot save for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing etcdctl snapshot save. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, etcdctl snapshot save for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing etcdctl snapshot save. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, etcdctl snapshot save for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing etcdctl snapshot save. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Restore procedure

Stop apiserver; restore snapshot; member list consistency; documented RTO steps.

In practice, restore procedure for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing restore procedure. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, restore procedure for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing restore procedure. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, restore procedure for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing restore procedure. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, restore procedure for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing restore procedure. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Encryption at rest

Backup files encrypted KMS; access audit for break-glass restores.

In practice, encryption at rest for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing encryption at rest. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, encryption at rest for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing encryption at rest. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, encryption at rest for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing encryption at rest. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, encryption at rest for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing encryption at rest. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Monitoring

Backup job success lag_seconds since last success alert Sev-2.

In practice, monitoring for etcd backup restore ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for etcd backup restore ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for etcd backup restore ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, monitoring for etcd backup restore ops requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing monitoring. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## Disaster runbook

When restore invalid rebuild cluster restore apps from GitOps not only etcd.

In practice, disaster runbook for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing disaster runbook. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, disaster runbook for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing disaster runbook. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, disaster runbook for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing disaster runbook. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, disaster runbook for etcd backup restore ops requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing disaster runbook. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-dag-dependency-management": (
        [
            ('When replace ExternalTaskSensor with Datasets?', 'When upstream completion is the signal—not task_id strings.'),
            ('Why sensors overload metastore?', 'Poke queries multiply with sensor count competing with scheduler.'),
            ('What is a cross-DAG data contract?', 'Schema version partition SLA owner breaking-change policy in CI.'),
            ('How detect deadlocks?', 'Cycle detection in CI; alert long up_for_retry sensors.'),
        ],
        """Finance mart never scheduled—upstream task rename broke ExternalTaskSensor strings.

## ExternalTaskSensor costs

Rename fragility poke DB load execution_date alignment.

In practice, externaltasksensor costs for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing externaltasksensor costs. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, externaltasksensor costs for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing externaltasksensor costs. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, externaltasksensor costs for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing externaltasksensor costs. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, externaltasksensor costs for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing externaltasksensor costs. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Datasets decoupling

Outlet URI consumer schedule lineage native in Airflow 2.4+.

In practice, datasets decoupling for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing datasets decoupling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, datasets decoupling for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing datasets decoupling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, datasets decoupling for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing datasets decoupling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, datasets decoupling for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing datasets decoupling. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Contracts between teams

Semver schema compat shims on rename one release.

In practice, contracts between teams for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing contracts between teams. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, contracts between teams for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing contracts between teams. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, contracts between teams for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing contracts between teams. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

In practice, contracts between teams for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing contracts between teams. Document who approves production changes and the
one-step rollback validated in the last game day. Pair technical controls with metrics tied to
user-visible outcomes: latency, errors, freshness, cost.

## Observability edges

Dataset freshness sensors retry dashboard lineage export.

In practice, observability edges for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability edges. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability edges for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability edges. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability edges for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability edges. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, observability edges for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing observability edges. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Migration steps

Rank sensors dual-write delete sensor watch CPU drop.

In practice, migration steps for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration steps. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration steps for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration steps. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration steps for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration steps. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration steps for dag dependency management requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration steps. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

    "devops-data-mesh-domain-ownership": (
        [
            ('Domain ownership in mesh?', 'Team owns pipelines quality SLAs for published data products.'),
            ('Mesh vs decentralized ETL?', 'Federated governance on keys PII—not only scattered pipelines.'),
            ('When central still?', 'Small org may not justify mesh coordination overhead yet.'),
            ('Without governance?', 'Incompatible schemas duplicate metrics no accountability.'),
        ],
        """Central queue fourteen-day SLA blocked subscriptions feature eleven weeks.

## Data products

Consumers interface SLA lifecycle on-call on domain.

In practice, data products for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data products. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data products for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data products. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data products for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data products. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, data products for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing data products. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## Federated governance

Central spine keys domains map business meaning.

In practice, federated governance for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing federated governance. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, federated governance for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing federated governance. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, federated governance for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing federated governance. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

In practice, federated governance for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing federated governance. Document who approves production changes and the one-
step rollback validated in the last game day. Pair technical controls with metrics tied to user-
visible outcomes: latency, errors, freshness, cost.

## Embedded engineers

Platform paved roads not every mart PR approval.

In practice, embedded engineers for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing embedded engineers. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, embedded engineers for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing embedded engineers. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, embedded engineers for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing embedded engineers. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, embedded engineers for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing embedded engineers. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

## SLA metrics

Freshness error budgets downstream stale flags.

In practice, sla metrics for data mesh domain ownership requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing sla metrics. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, sla metrics for data mesh domain ownership requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing sla metrics. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, sla metrics for data mesh domain ownership requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing sla metrics. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

In practice, sla metrics for data mesh domain ownership requires aligning platform and application
teams on failure modes. Staging must reproduce production traffic shape—not uniform load—before
changing sla metrics. Document who approves production changes and the one-step rollback validated
in the last game day. Pair technical controls with metrics tied to user-visible outcomes: latency,
errors, freshness, cost.

## Migration pilot

One domain conformed dims expand quarterly measure lead time.

In practice, migration pilot for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration pilot. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration pilot for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration pilot. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration pilot for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration pilot. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

In practice, migration pilot for data mesh domain ownership requires aligning platform and
application teams on failure modes. Staging must reproduce production traffic shape—not uniform
load—before changing migration pilot. Document who approves production changes and the one-step
rollback validated in the last game day. Pair technical controls with metrics tied to user-visible
outcomes: latency, errors, freshness, cost.

Day-two ownership matters as much as initial rollout: assign on-call, review alerts quarterly, and
update internal runbooks with lessons from every incident—even minor ones—so the next engineer
inherits context not only configuration snippets.""",
    ),

}
