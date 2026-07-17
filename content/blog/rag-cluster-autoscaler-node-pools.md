---
title: "RAG: Cluster Autoscaler Node Pools"
slug: "rag-cluster-autoscaler-node-pools"
description: "Separate Kubernetes node pools for RAG embedding GPU workloads, retrieval CPU services, and ingestion batch jobs—cluster autoscaler scales each pool independently based on pod resource requests."
datePublished: "2026-02-20"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cluster"]
keywords: "cluster autoscaler, node pools, Kubernetes, RAG scaling, GPU nodes, EKS node groups, GKE node pools, taints tolerations, embedding workloads"
faq:
  - q: "Why separate node pools for RAG workloads?"
    a: "Embedding inference needs GPUs; retrieval services need CPU-optimized instances; batch ingestion needs memory-heavy nodes with spot tolerance. Mixing them in one pool causes GPU pods to block on CPU node scale-up, or expensive GPU nodes running CPU-only retrieval pods. Separate pools let cluster autoscaler scale each dimension independently."
  - q: "How does cluster autoscaler decide to add nodes to a pool?"
    a: "When pods are unschedulable due to insufficient CPU, memory, or GPU resources on existing nodes, cluster autoscaler adds a node to the matching node pool—if the pool's max size allows and the pod's nodeSelector/taints match. Pods must have resource requests defined; autoscaler ignores pods without requests."
  - q: "Should RAG embedding pods use spot/preemptible GPU nodes?"
    a: "Batch reindex embedding jobs tolerate spot interruption well with checkpoint/resume. Real-time query embedding serving needs on-demand GPU nodes for availability. Split into two pools: embedding-serving (on-demand GPU) and embedding-batch (spot GPU with taints)."
---
Bulk reindex jobs queued 400 embedding pods requesting `nvidia.com/gpu: 1` each. The cluster autoscaler added nodes—but from the general-purpose pool because no GPU node pool existed. CPU nodes appeared with no GPU, pods stayed Pending for two hours, and someone manually scaled a static GPU node group. The fix was three dedicated node pools with taints, cluster autoscaler per pool, and pod resource requests that matched actual workload profiles.

RAG platforms run heterogeneous workloads on Kubernetes: GPU embedding inference, CPU-heavy hybrid retrieval, memory-bound rerankers, and bursty batch ingestion. A single node pool with cluster autoscaler cannot optimize cost and scheduling for all of them.

## RAG workload profiles and instance types

| Pool name | Workload | Instance type (AWS) | Resources |
|-----------|----------|---------------------|-----------|
| gpu-serving | Query embedding | g5.xlarge | 1 GPU, 4 vCPU, 16 GB |
| gpu-batch | Bulk reindex | g5.xlarge (spot) | 1 GPU, checkpoint tolerant |
| retrieval | Hybrid search API | c6i.2xlarge | 8 vCPU, 16 GB, no GPU |
| reranker | Cross-encoder | c6i.4xlarge | 16 vCPU, 32 GB |
| ingestion | Chunk + embed pipeline | r6i.xlarge | 4 vCPU, 32 GB RAM |
| system | Redis, Kafka, monitoring | m6i.large | 2 vCPU, 8 GB |

Right-size from production metrics—do not guess resource requests.

## Node pool configuration with taints

Isolate pools so retrieval pods never land on GPU nodes:

```yaml
# gpu-serving pool (EKS managed node group)
# Terraform excerpt
resource "aws_eks_node_group" "gpu_serving" {
  cluster_name    = aws_eks_cluster.rag.name
  node_group_name = "gpu-serving"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = 2
    min_size     = 1
    max_size     = 10
  }

  instance_types = ["g5.xlarge"]
  capacity_type  = "ON_DEMAND"

  labels = {
    workload = "gpu-serving"
    node-pool = "gpu-serving"
  }

  taint {
    key    = "nvidia.com/gpu"
    value  = "serving"
    effect = "NO_SCHEDULE"
  }
}
```

Retrieval deployment tolerates only CPU pools:

```yaml
# deployments/retrieval.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-retrieval
spec:
  template:
    spec:
      nodeSelector:
        node-pool: retrieval
      containers:
        - name: retrieval
          resources:
            requests:
              cpu: "2"
              memory: "4Gi"
            limits:
              cpu: "4"
              memory: "8Gi"
```

Embedding serving requires GPU toleration:

```yaml
# deployments/embedding-serving.yaml
spec:
  template:
    spec:
      nodeSelector:
        node-pool: gpu-serving
      tolerations:
        - key: nvidia.com/gpu
          value: serving
          effect: NoSchedule
      containers:
        - name: embedding
          resources:
            requests:
              cpu: "2"
              memory: "8Gi"
              nvidia.com/gpu: "1"
            limits:
              nvidia.com/gpu: "1"
```

## Cluster autoscaler configuration

Install cluster autoscaler with multiple node group support:

```yaml
# cluster-autoscaler deployment flags
- --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/rag-prod
- --balance-similar-node-groups=true
- --expander=priority
- --scale-down-unneeded-time=10m
- --scale-down-delay-after-add=10m
```

Priority expander for cost optimization:

```yaml
# cluster-autoscaler-priority-expander.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-priority-expander
  namespace: kube-system
data:
  priorities: |-
    10:
      - gpu-serving-.*
    20:
      - retrieval-.*
      - reranker-.*
    30:
      - ingestion-.*-spot-.*
    40:
      - ingestion-.*-ondemand-.*
```

Lower number = higher priority for scale-up. GPU serving scales first when embedding pods pending.

## Pod resource requests drive autoscaling

Cluster autoscaler simulates scheduling: if pending pod fits on new node type, scale that pool.

Common mistakes:

**Requests too low.** Retrieval pod requests 100m CPU but uses 2 cores—node fills incorrectly, no scale-up, throttling.

**Requests too high.** Embedding pod requests 4 GPU—only one pod per g5.xlarge but autoscaler thinks node full after one pod.

**Missing GPU request.** Pod uses GPU but doesn't request `nvidia.com/gpu`—schedules on CPU node, crashes, no GPU scale-up.

Validate with kubectl:

```bash
kubectl describe pod <pending-pod> | grep -A5 Events
# "0/12 nodes are available: 12 Insufficient nvidia.com/gpu"
```

## Horizontal Pod Autoscaler + Cluster Autoscaler interaction

HPA scales pods; cluster autoscaler scales nodes. They must cooperate:

```yaml
# hpa/embedding-serving.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: embedding-serving
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: embedding-serving
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: embedding_queue_depth
        target:
          type: AverageValue
          averageValue: "10"
```

Sequence: QPS spike → HPA adds pods → pods Pending → cluster autoscaler adds GPU nodes → pods schedule.

Set `--scale-down-delay-after-add` ≥ HPA stabilization window to prevent node flapping.

## Spot instances for batch embedding

Batch reindex tolerates interruption:

```yaml
# gpu-batch pool
capacity_type = "SPOT"

taint {
  key    = "nvidia.com/gpu"
  value  = "batch"
  effect = "NO_SCHEDULE"
}

taint {
  key    = "spot"
  value  = "true"
  effect = "NO_SCHEDULE"
}
```

Batch job with checkpoint:

```yaml
spec:
  template:
    spec:
      tolerations:
        - key: nvidia.com/gpu
          value: batch
          effect: NoSchedule
        - key: spot
          value: "true"
          effect: NoSchedule
      containers:
        - name: batch-embed
          env:
            - name: CHECKPOINT_S3_BUCKET
              value: rag-embed-checkpoints
```

On spot interruption, job resumes from checkpoint on new node.

## Monitoring autoscaler behavior

Key metrics:

- `cluster_autoscaler_unschedulable_pods_count` — pending pods waiting for nodes
- `cluster_autoscaler_nodes_count` — per node group
- `cluster_autoscaler_scale_up_events_total` — scale-up frequency
- Node pool utilization vs requests

Alert when unschedulable pods >0 for >5 minutes—autoscaler may be at max node count or misconfigured.

## Cost optimization patterns

- **Scale-to-zero batch pool** — min_size=0 for gpu-batch; accept cold start on reindex
- **Consolidation** — cluster autoscaler removes underutilized nodes after scale-down-delay
- **Right-size requests** — over-requested pods waste node capacity
- **Separate spot/on-demand** — never run serving on spot without fallback pool

## Troubleshooting pending pods

1. Check pod events for resource type missing
2. Verify nodeSelector matches pool labels
3. Verify tolerations match pool taints
4. Check node group max_size not reached
5. Check cluster autoscaler logs for scale-up failures (IAM, ASG limits)
6. Verify GPU device plugin running on GPU nodes

RAG scaling is multi-dimensional. Separate node pools with cluster autoscaler per pool turn "everything Pending" incidents into predictable, cost-aware scaling per workload type.

## Pre-warming GPU pools before known events

Scheduled product launches with predictable traffic spikes benefit from pre-warming GPU node pools—temporarily raise min_size 24 hours before launch, restore after traffic normalizes. cluster-autoscaler cold-start for GPU nodes (AMI pull, device plugin ready) takes 3–8 minutes; pre-warming eliminates Pending pods during launch window. Coordinate with HPA minReplicas bump for embedding service Deployment.

## Node pool upgrade and AMI rotation

GPU AMI updates (CUDA driver, device plugin compatibility) require cordoned node replacement. cluster-autoscaler adds new nodes with updated AMI while old nodes drain—ensure PodDisruptionBudgets on embedding service allow minimum one replica during rotation. Test AMI updates in staging with full embedding inference workload before production. Document GPU driver version compatibility matrix with embedding model serving framework (Triton, TorchServe, vLLM).


## Production rollout notes

Cluster Autoscaler priority expander configuration should be version-controlled in git alongside node pool Terraform. Drift between autoscaler config and actual node group tags causes pods to stay Pending indefinitely—tags k8s.io/cluster-autoscaler/node-template/label/node-pool must match pod nodeSelector exactly including spelling.


Document node pool capacity limits in runbooks: max GPU nodes, max retrieval CPU nodes, current utilization baseline. On-call engineers scale max_size during incidents without finding Terraform repo. Autoscaler events log to dedicated Loki stream for post-incident timeline: which pool scaled, when, trigger pod count.


FinOps tags on node pools (cost-center, workload-type) enable chargeback for RAG infrastructure per product line. GPU pool costs often dominate—separate tagging proves embedding cost attribution to leadership reviewing RAG platform budget requests.

Validate cluster autoscaler IAM permissions after EKS cluster upgrades—control plane updates occasionally reset node group tags autoscaler depends on for discovery.

## Integration notes for cluster autoscaler node pools

This rarely lives alone. Map upstream dependencies (auth, data stores, queues) and downstream consumers before you harden the happy path. Sequence the rollout: observability first, then flags, then the risky behavior change. That order turns rollback into a flag flip instead of a reverse migration under pressure. Keep the integration diagram in the same repo as the code so it cannot rot in a slide deck.


Also for rag cluster autoscaler node pools: change one variable at a time when tuning, keep a rollback path tested quarterly, and verify consumer or replica behavior — not only the primary signal you expected to move.

## Resources

- Kubernetes cluster autoscaler documentation
- AWS EKS managed node groups
- GKE node auto-provisioning
- NVIDIA device plugin for Kubernetes
