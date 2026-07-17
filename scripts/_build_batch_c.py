#!/usr/bin/env python3
"""One-shot builder: writes generate_batch_c_posts.py with 250 topics."""
from pathlib import Path

OUT = Path(__file__).parent / "generate_batch_c_posts.py"

# (slug_suffix, title, description, tags_csv, keywords, hook, tool, mistake, when, s1h, s1p, s2h, s2code, s3h, s3p, s4h, s4p, s5h, s5p)
# tags_csv like "DevOps|Kubernetes|SRE"

def cat(name, items):
    return [(name, *row) for row in items]

TOPIC_ROWS = []

def add(category, rows):
    TOPIC_ROWS.extend(cat(category, rows))

# --- KUBERNETES (28) ---
add("Kubernetes", [
("pod-disruption-budgets","Pod Disruption Budgets for Safe Cluster Upgrades","Design PodDisruptionBudgets that protect quorum during node drains, cluster upgrades, and Karpenter consolidation without blocking maintenance.","DevOps|Kubernetes|SRE","PodDisruptionBudget, PDB, node drain, cluster upgrade","At 2 a.m. during a node pool upgrade, Redis Sentinel lost quorum because three pods were evicted simultaneously—no PDB existed on the StatefulSet.","kubectl drain","Setting minAvailable to 100% on stateless Deployments blocks all voluntary evictions and stalls upgrades for days.","Before enabling cluster autoscaler consolidation or your first production node drain.","Why PDBs exist","Voluntary disruptions—drains, upgrades, Karpenter consolidation—can remove multiple pods at once. PodDisruptionBudgets cap simultaneous evictions so quorum services survive. Involuntary disruptions (node failure, OOMKill) still need replication and anti-affinity—not PDB alone.","PDB spec patterns","""```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: api
```""","Interaction with autoscaler","Cluster Autoscaler and Karpenter respect PDBs when consolidating nodes. Overly strict PDBs prevent bin-packing savings; overly loose PDBs risk outages during maintenance windows.","Testing drains in staging","Run kubectl drain against staging nodes with production-shaped replica counts. Measure time-to-drain and whether PDB blocks appear in events. Document max concurrent drains per service tier.","Observability for PDBs","Alert on kube_poddisruptionbudget_status_current_healthy approaching limits during maintenance. Track eviction failures in audit logs for postmortems."),
("vertical-pod-autoscaler","Vertical Pod Autoscaler: Recommendations vs Auto Mode","Operate VPA in recommendation or auto mode: right-size requests, avoid OOM loops, and coordinate with HPA.","DevOps|Kubernetes|Cost Optimization","VPA, vertical pod autoscaler, resource requests, right-sizing","Finance flagged a 40% over-provisioned namespace. VPA recommendations showed requests at 200m CPU while pods averaged 45m—yet nobody trusted auto mode after a prior OOM incident.","VPA","Running VPA auto mode on the same Deployment as HPA on CPU causes fight loops—one scales pods, the other scales requests.","Enable VPA recommendations first on batch tiers; move to auto only after validating HPA metrics do not overlap.","VPA modes explained","Off stores recommendations only. Initial sets requests on pod creation. Auto updates requests and recreates pods. Auto saves money but causes churn; Initial is safer for latency-sensitive APIs.","Installing the recommender","""```bash
helm install vpa fairwinds-stable/vpa \\
  --set recommender.enabled=true --set updater.enabled=false
kubectl get vpa -A
```""","Reading recommendations","Compare VPA status.recommendation against current requests weekly. Batch apply changes during maintenance windows rather than enabling auto on everything at once.","HPA coordination","Use VPA on memory, HPA on custom metrics—not both on CPU for the same workload. Document the split in your platform runbook.","Rollout checklist","Start with updateMode Off for two weeks. Export recommendations to Grafana. Pilot Initial on internal tools before customer-facing tiers."),
("horizontal-pod-autoscaler-custom-metrics","HPA with Custom and External Metrics","Scale Deployments on Prometheus, KEDA, or cloud queue depth using HorizontalPodAutoscaler v2 metric sources.","DevOps|Kubernetes|Observability","HPA, custom metrics, KEDA, Prometheus adapter","Checkout latency breached SLO for an hour while CPU sat at 30%. Queue depth existed in Prometheus but HPA still watched CPU only.","HPA v2","Scaling on CPU alone while latency SLOs burn during I/O-bound spikes—HPA never adds pods because CPU stays flat.","Adopt custom metrics when CPU/memory do not correlate with user-visible latency or queue backlog.","Metrics API prerequisites","Install metrics-server for resource metrics. For custom metrics, deploy prometheus-adapter or use KEDA ScaledObjects referencing Prometheus, Kafka lag, or SQS depth.","HPA v2 manifest","""```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker
  minReplicas: 2
  maxReplicas: 50
  metrics:
    - type: External
      external:
        metric:
          name: sqs_queue_depth
        target:
          type: AverageValue
          averageValue: "30"
```""","Adapter configuration","Map Prometheus queries to custom.metrics.k8s.io names in adapter config. Validate with kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1.","Scaling behavior tuning","Tune behavior.scaleDown.stabilizationWindowSeconds to prevent flapping. Scale-up aggressively; scale-down slowly for batch workers.","Validation load tests","Load-test with synthetic queue depth. Confirm HPA events show metric values and replica changes within one stabilization window."),
("network-policies-default-deny","Kubernetes Network Policies: Default Deny Baseline","Implement default-deny network policies with explicit egress and ingress allowlists for zero-trust pod networking.","DevOps|Kubernetes|Security","network policy, default deny, zero trust, CNI","A compliance audit demanded default-deny. The first blanket policy broke all pods because kube-dns egress was missing from the allowlist.","NetworkPolicy","Applying deny-all without documenting required DNS and API server egress—every pod loses DNS resolution overnight.","Roll out default-deny namespace by namespace after inventorying required flows with a network policy viewer.","Zero-trust pod networking","Without NetworkPolicy, any compromised pod can reach any Service in the cluster. Default-deny forces explicit documentation of every required flow.","Deny-all template","""```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
```""","Allow DNS egress","Add explicit egress to kube-dns on UDP 53 in kube-system. Without it, every pod fails name resolution silently after deny-all applies.","Progressive rollout","Use Cilium Hubble or Calico flow logs to discover traffic before enforcing deny. Stage policies in audit mode if your CNI supports it.","Operations discipline","Version policies in Git. Review diffs in PRs like application code. Alert on policy sync failures from your GitOps controller."),
("resource-quota-limitrange","ResourceQuota and LimitRange for Multi-Tenant Namespaces","Govern namespace consumption with ResourceQuota and LimitRange defaults so one team cannot exhaust cluster capacity.","DevOps|Kubernetes|Platform","ResourceQuota, LimitRange, multi-tenancy, namespace governance","One team's notebooks requested 8 CPU each with no limits. They consumed an entire node pool while production APIs pending-scheduled for hours.","ResourceQuota","Setting quotas without LimitRange—pods with missing requests bypass scheduling fairness and starve neighbors.","Apply quotas when onboarding tenant namespaces or before opening self-service namespace creation.","Quota vs LimitRange","ResourceQuota caps total namespace consumption. LimitRange sets per-pod defaults and maxima. Use both: quota for budget, LimitRange for pod shape.","Example manifests","""```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tenant-quota
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
---
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
spec:
  limits:
    - type: Container
      defaultRequest:
        cpu: 100m
        memory: 128Mi
```""","Monitoring quota pressure","Export kube_resourcequota metrics. Alert at 80% of hard limits so teams resize before hard failures at deploy time.","Self-service UX","Expose quota headroom in internal developer portals. Rejection messages should link to docs for requesting increases.","Governance reviews","Review quota increases quarterly. Tie increases to cost allocation tags and business justification."),
])

print(f"Partial builder has {len(TOPIC_ROWS)} rows - use full generator instead")
