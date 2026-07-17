---
title: "AI Agents: Cluster Autoscaler Node Pools"
slug: "agent-cluster-autoscaler-node-pools"
description: "Right-sizing Kubernetes for LLM agent fleets — GPU inference pools, CPU retrieval workers, spot preemption handling, and cluster autoscaler settings that scale without bankrupting you."
datePublished: "2026-02-21"
dateModified: "2026-02-21"
tags: ["AI", "Agent", "Cluster"]
keywords: "cluster autoscaler node pools, Kubernetes agent scaling, GPU node pool LLM, Karpenter vs cluster autoscaler, agent inference autoscaling"
faq:
  - q: "Should agent inference and retrieval run on separate node pools?"
    a: "Yes, in almost every production setup. Inference pods need GPU or high-memory instances with strict taints; retrieval and orchestration pods are CPU-bound and benefit from cheaper general-purpose nodes. Mixing them causes GPU waste when retrieval scales and inference starvation when batch jobs land on the wrong pool."
  - q: "How do you prevent cluster autoscaler from thrashing during agent traffic spikes?"
    a: "Set scale-down delays (scale-down-unneeded-time ≥ 10m for GPU pools), use PodDisruptionBudgets on agent orchestrators, configure expander priorities so spot pools scale before on-demand, and add horizontal pod autoscaler cooldowns aligned with node provisioning latency (GPU nodes often need 3–5 minutes)."
  - q: "Cluster Autoscaler or Karpenter for agent workloads?"
    a: "Cluster Autoscaler works well with fixed node group definitions and predictable instance types — common for regulated environments. Karpenter excels when agent traffic is spiky and heterogeneous (mix of g5.xlarge and inf2.xlarge). Many teams run Karpenter for CPU pools and managed GPU node groups with CA for compliance boundaries."
  - q: "What instance types fit typical agent node pools?"
    a: "Orchestrator/API: c6i/c7g 4–8 vCPU. Retrieval/embeddings CPU: r6i 16–32 GB RAM. GPU inference: g5.xlarge (A10G) or inf2 for AWS Inferentia. Batch eval/reindex: spot m6i with checkpointing. Size pools from p95 concurrent sessions × per-pod CPU/GPU request, not peak marketing email spikes."
---
Your agent platform hits steady state at 40 pods until a product launch doubles concurrent sessions, the cluster autoscaler provisions twelve `g5.2xlarge` nodes, and finance asks why the GPU bill tripled while p95 latency still missed SLO. The autoscaler did its job — it saw unschedulable pods and added capacity. The failure was **node pool design**: one undifferentiated pool, wrong instance family, spot preemption during long inference, and scale-down that evicted warm model servers every quiet hour.

Running LLM agents on Kubernetes requires node pools shaped around **workload physics** — GPU memory for model weights, CPU RAM for retrieval fan-out, fast network for tool calls — and autoscaler tuning that respects provisioning latency and cost guardrails.

## Workload topology for agent fleets

Decompose agent infrastructure into schedulable tiers:

```
                    ┌─────────────────────────────────┐
  Ingress/API       │  pool: agent-api (c7g, on-demand) │
                    └───────────────┬─────────────────┘
                                    │
                    ┌───────────────▼─────────────────┐
  Orchestration     │  pool: agent-worker (m6i, spot OK) │
                    └───────────────┬─────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
     │ pool: retrieval│   │ pool: inference│   │ pool: batch    │
     │ r6i, CPU-heavy │   │ g5/inf2, GPU   │   │ spot m6i, jobs │
     └────────────────┘   └────────────────┘   └────────────────┘
```

Each pool carries **taints and tolerations** so a runaway retrieval HPA cannot land on GPU nodes:

```yaml
# node-pools/inference-gpu.yaml
apiVersion: v1
kind: Node
metadata:
  labels:
    workload: agent-inference
    nvidia.com/gpu.present: "true"
  taints:
    - key: nvidia.com/gpu
      value: "true"
      effect: NoSchedule
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-agent-gateway
spec:
  template:
    spec:
      tolerations:
        - key: nvidia.com/gpu
          operator: Equal
          value: "true"
          effect: NoSchedule
      nodeSelector:
        workload: agent-inference
      containers:
        - name: vllm
          resources:
            requests:
              nvidia.com/gpu: "1"
              memory: "24Gi"
            limits:
              nvidia.com/gpu: "1"
              memory: "28Gi"
```

Orchestrator pods tolerate `workload=agent-worker` only — never GPU taints.

## Sizing node pools from agent metrics

Start from session concurrency, not pod count:

| Metric | Source | Pool impact |
|--------|--------|-------------|
| Concurrent active sessions | Redis / app gauge | orchestrator replicas |
| Tokens/sec aggregate | Prometheus | inference GPU count |
| Retrieval QPS × chunks/query | RAG metrics | retrieval CPU/RAM |
| Batch reindex backlog | queue depth | batch spot pool |

Translate to resource requests:

```python
# capacity/agent_pool_sizer.py
def inference_nodes_needed(
    concurrent_sessions: int,
    sessions_per_gpu: float = 8.0,
    headroom: float = 1.25,
) -> int:
    """g5.xlarge with 24GB fits ~8 concurrent 7B-quant sessions (varies by model)."""
    import math
    gpus = math.ceil(concurrent_sessions / sessions_per_gpu * headroom)
    return gpus  # one GPU per node for simplicity; pack only with MIG/time-slicing

def retrieval_nodes_needed(
    qps: float,
    cpu_per_query: float = 0.3,
    vcpu_per_node: int = 16,
) -> int:
    import math
    cpu = qps * cpu_per_query
    return max(1, math.ceil(cpu / vcpu_per_node * 1.3))
```

Feed these as **cluster autoscaler node group min/max** bounds, not static node counts. Min > 0 for inference only if cold-start latency is unacceptable — otherwise accept 2–3 minute scale-up.

## Cluster Autoscaler configuration

Key flags for agent platforms on EKS/GKE:

```yaml
# cluster-autoscaler deployment excerpt
args:
  - --balance-similar-node-groups=true
  - --expander=priority,least-waste
  - --scale-down-enabled=true
  - --scale-down-unneeded-time=10m
  - --scale-down-delay-after-add=5m
  - --skip-nodes-with-local-storage=false
  - --max-node-provision-time=15m
```

**scale-down-unneeded-time**: GPU pools need longer values (10–15m) because model load into GPU memory takes minutes; premature scale-down causes thrashing reloads.

**expander=priority**: Define priority ConfigMap so on-demand GPU pools win only when spot GPU is unavailable:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-priority
data:
  priorities: |
    10:
      - agent-inference-spot-g5
    20:
      - agent-inference-ondemand-g5
    30:
      - agent-worker-spot
    40:
      - agent-worker-ondemand
```

**PodDisruptionBudgets** on orchestrators prevent CA from draining nodes during scale-down while sessions are active:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: agent-orchestrator-pdb
spec:
  minAvailable: 80%
  selector:
    matchLabels:
      app: agent-orchestrator
```

## Spot and preemption for agent workloads

Spot saves 60–70% on retrieval and batch pools; inference spot is viable only with checkpointing and client retry semantics.

Patterns that work:

1. **Retrieval/embeddings on spot** — stateless, HPA scales replicas, retry on `SIGTERM`
2. **Inference on spot with fallback** — run spot + on-demand node groups; scheduler prefers spot via priority expander; on-demand absorbs preemption surge
3. **Batch eval exclusively on spot** — checkpoint to S3 every N documents

Handle preemption gracefully:

```python
# agent_runtime/preemption_handler.py
import signal
import sys

draining = False

def handle_sigterm(signum, frame):
    global draining
    draining = True
    # Stop accepting new sessions; finish in-flight with deadline
    orchestrator.begin_graceful_shutdown(timeout_sec=90)

signal.signal(signal.SIGTERM, handle_sigterm)
```

Pair with **terminationGracePeriodSeconds: 120** on inference pods — longer than default 30s.

AWS Node Termination Handler or GKE spot preemption notices give ~2 minutes; agent gateways should drain HTTP connections and persist session state to Redis before exit.

## HPA and CA coordination

Misaligned HPA and cluster autoscaler causes flapping: HPA adds pods → unschedulable → CA adds nodes → HPA removes pods → CA removes nodes.

Align timing:

| Component | Setting | Rationale |
|-----------|---------|-----------|
| HPA scale-up stabilization | 0–60s | Respond fast to session spike |
| HPA scale-down stabilization | 300s | Wait for session completion |
| CA scale-down-unneeded | 600s+ | Match HPA scale-down |
| HPA metrics | custom `agent_active_sessions` | CPU alone lies for I/O-bound agents |

Custom metrics adapter example:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: agent-orchestrator
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: agent-orchestrator
  minReplicas: 3
  maxReplicas: 50
  metrics:
    - type: Pods
      pods:
        metric:
          name: agent_active_sessions
        target:
          type: AverageValue
          averageValue: "25"
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

Register `agent_active_sessions` from your orchestrator — one metric per pod exported via Prometheus adapter.

## Multi-pool scheduling pitfalls

**Cluster autoscaler ignores pods with unsatisfiable constraints.** If inference HPA scales but GPU pool is at max, pods stay Pending forever while CA logs "max node group size reached." Alert on `kube_pod_status_scheduled{condition="false"}` for agent namespaces.

**Resource overcommit on GPU nodes** — requesting 0.5 GPU without MIG leads to OOM kills when two pods land on one A10G. Prefer one inference pod per GPU unless using NVIDIA MIG or time-slicing with explicit limits.

**Zone imbalance** — agent tool calls to regional APIs suffer if all inference lands in `us-east-1a` and that AZ degrades. Use topology spread:

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: agent-inference
```

## Observability for autoscaler decisions

Dashboard panels on-call actually uses:

- `cluster_autoscaler_unneeded_nodes_count` by node group
- `cluster_autoscaler_failed_scale_ups_total` — quota, IAM, insufficient subnet IP
- Pending pods by `reason=Unschedulable` and `workload` label
- Cost per node group ( Kubecost / OpenCost ) overlaid with `agent_sessions_active`

Log CA events to CloudWatch or Loki at info level during incidents — "Scale-up: group agent-inference-spot-g5 needed +2 nodes" explains latency spikes faster than guessing.

## Karpenter alternative sketch

When node group proliferation becomes unmanageable, Karpenter provisions instances per pending pod:

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: agent-inference
spec:
  template:
    metadata:
      labels:
        workload: agent-inference
    spec:
      taints:
        - key: nvidia.com/gpu
          effect: NoSchedule
      requirements:
        - key: karpenter.k8s.aws/instance-gpu-count
          operator: Gt
          values: ["0"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["g", "p"]
      expireAfter: 720h
  limits:
    cpu: 1000
    memory: 4000Gi
```

Karpenter consolidates underutilized nodes aggressively — great for CPU retrieval, tune `disruption.consolidationPolicy` carefully for GPU inference to avoid reloading 40GB models hourly.

Cluster autoscaler node pools for agent platforms are a capacity contract between ML, platform, and finance. Split GPU inference, CPU retrieval, and orchestration into tainted pools; size max bounds from session metrics; align HPA stabilization with CA scale-down delays; handle spot preemption with graceful drain. The autoscaler is not magic — it scales what you tell it to, on the instance types you provision, at the speed your cloud quota allows. Design pools for those constraints and latency stops being a surprise.

## Resources

- [Kubernetes Cluster Autoscaler — FAQ and best practices](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler/FAQ.md)
- [AWS EKS — Best practices for cluster autoscaling](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-autoscaling.html)
- [Karpenter — NodePool configuration](https://karpenter.sh/docs/concepts/nodepools/)
- [NVIDIA GPU Operator — MIG partitioning](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html)
- [Kubernetes — Pod topology spread constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
