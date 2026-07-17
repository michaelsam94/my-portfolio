---
title: "Karpenter NodePool Tuning for LLM and Agent Workloads"
slug: "agent-karpenter-provisioner-tuning"
description: "Tune Karpenter NodePools and NodeClaims for GPU inference, embedding workers, and bursty agent orchestration—consolidation, interruption handling, instance diversity, and cost without cold-start pain."
datePublished: "2026-02-23"
dateModified: "2026-02-23"
tags: ["AI Agents", "Kubernetes", "Karpenter", "GPU"]
keywords: "karpenter tuning, nodepool, gpu provisioning, agent workloads, consolidation, spot instances, eks autoscaling"
faq:
  - q: "Should agent inference pods use a dedicated Karpenter NodePool?"
    a: "Yes. Isolate GPU and high-memory pools from generic bursty CPU agent workers. Mixing embedding batch jobs with latency-sensitive chat inference on one pool causes consolidation to evict the wrong pods. Separate NodePools with taints, labels, and instance requirements per workload class."
  - q: "What consolidateAfter value works for bursty agent traffic?"
    a: "GPU pools: 30m–2h depending on model load cost—cold starts for 70B models can exceed 10 minutes. CPU orchestrator pools: 5–15m with consolidationPolicy WhenEmptyOrUnderutilized. Too aggressive consolidation triggers re-provision storms during lunch-hour traffic spikes."
  - q: "How do you tune Karpenter for Spot without killing long agent runs?"
    a: "Use on-demand for run workers holding state mid-conversation; Spot for batch eval, embedding rebuilds, and stateless rerankers. Set interruption budgets, pod disruption budgets, and do-not-disrupt annotations on runs exceeding N minutes. Combine capacity-type weights rather than Spot-only for critical paths."
  - q: "Which instance requirements matter most for vLLM and embedding servers?"
    a: "GPU: g6/g5 instance families, min 24GB VRAM for 7–8B quantized, 48GB+ for 13B+. CPU/RAM: memory-optimized for embedding (r7i) with local NVMe if caching shards. Set kubelet reserved resources so OOM kills don't take the whole node during concurrent agent sessions."
---

The dashboard showed 40% Spot savings and p99 agent latency at twelve seconds. Same week. Karpenter consolidated a GPU node while three vLLM pods were "idle" waiting for the next token batch—consolidation saw low CPU, not queue depth. Nodes churned, models reloaded from disk, and users watched spinners. Autoscaling worked; **tuning** did not.

Agent platforms stress cluster autoscalers differently from web apps. Traffic is bursty and session-sticky. GPU memory matters more than CPU averages. Cold starts include model download, weight load, and CUDA init—not just pod schedule time. Karpenter's NodePool API (v1beta1+) replaces legacy Provisioners with clearer consolidation and disruption controls. The goal is right nodes fast, stable during runs, cheap when idle.

## Workload classes and pool topology

Split NodePools by **SLO tier**, not by team name:

| Pool | Workloads | Capacity | Consolidation |
|------|-----------|----------|---------------|
| `gpu-inference-od` | Chat, tool-calling LLM | On-demand GPU | Slow (1h+) |
| `gpu-batch-spot` | Offline eval, fine-tune | Spot GPU | Aggressive (15m) |
| `cpu-orchestrator` | API, queue workers | Graviton on-demand | Medium (10m) |
| `cpu-embedding` | Index build, batch embed | Spot + OD mix | Medium |

Each pool gets dedicated labels (`nodepool=gpu-inference-od`) and taints so only matching pods schedule there.

Example GPU inference NodePool:

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: gpu-inference-od
spec:
  template:
    metadata:
      labels:
        workload: agent-inference
        capacity-type: on-demand
    spec:
      taints:
        - key: nvidia.com/gpu
          value: "true"
          effect: NoSchedule
      requirements:
        - key: karpenter.k8s.aws/instance-family
          operator: In
          values: ["g6", "g5"]
        - key: karpenter.k8s.aws/instance-size
          operator: In
          values: ["xlarge", "2xlarge", "4xlarge"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: gpu-inference-class
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 45m
    budgets:
      - nodes: "10%"
  limits:
    cpu: "1000"
    memory: 4000Gi
    nvidia.com/gpu: "64"
```

`consolidateAfter: 45m` acknowledges model warm-up cost. Tune from traces: if reload exceeds 45m idle savings, increase it.

## EC2NodeClass for agent images

Agent GPU nodes need large root volumes and fast AMI boot:

```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: gpu-inference-class
spec:
  amiFamily: AL2023
  amiSelectorTerms:
    - id: ami-0abc1234  # EKS-optimized GPU AMI pinned
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: agent-cluster
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: agent-cluster
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 200Gi
        volumeType: gp3
        iops: 6000
        throughput: 250
  metadataOptions:
    httpEndpoint: enabled
    httpTokens: required
  userData: |
    #!/bin/bash
    # Pre-pull common model cache paths to EBS on first boot — optional bootstrap
    mkdir -p /var/lib/agent-models
```

Pin AMIs—`alias: al2023@latest` causes surprise drift. Model caches on EBS survive node replacement if using persistent volumes; emptyDir loses warm weights.

## Pod scheduling contracts

Agent deployments must **request what they need** or Karpenter schedules wrong instances:

```yaml
resources:
  requests:
    cpu: "4"
    memory: 32Gi
    nvidia.com/gpu: "1"
  limits:
    nvidia.com/gpu: "1"
```

For multi-model hosts, use separate deployments per model size—not one deployment requesting 4 GPUs when average use is 0.7.

Add **do-not-disrupt** for long runs via Karpenter annotations when run duration exceeds consolidation window:

```yaml
metadata:
  annotations:
    karpenter.sh/do-not-disrupt: "true"
```

Set dynamically when agent run starts; remove on completion. Prevents consolidation mid-conversation.

## Interruption and Spot handling

For Spot pools, configure interruption queue integration:

```yaml
spec:
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 15m
    budgets:
      - nodes: "30%"
        reasons:
          - Underutilized
      - nodes: "0"
        reasons:
          - Drifted
```

Agent workers should handle SIGTERM gracefully:

```python
import signal
import sys

def graceful_shutdown(signum, frame):
    # Stop accepting new runs; finish in-flight up to deadline
    orchestrator.drain(timeout_seconds=120)
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_shutdown)
```

Pair with `terminationGracePeriodSeconds: 180` on run worker pods. GPU inference may need longer if batch completes atomically.

## Right-sizing with metrics, not guesses

Dashboards Karpenter operators actually use:

- `karpenter_nodes_created_total` by pool
- `karpenter_pods_unschedulable` — pending agent pods waiting for capacity
- Time from pod pending → running (includes AMI + model load)
- GPU utilization vs request (DCGM metrics)
- Cost per 1k agent tokens by pool

If `pods_unschedulable` spikes while nodes exist, check instance requirements too narrow (no g6 in AZ) or limits.cpu hit.

If nodes scale but latency high, bottleneck is cold model load—not Karpenter speed. Fix with warm pools:

```yaml
# Maintain minimum nodes during business hours via scheduled scale
spec:
  weight: 10
  limits:
    nvidia.com/gpu: "8"
---
# Separate 'warm-standby' NodePool with expireAfter or low consolidateAfter off-hours
```

Some teams run a **minimum GPU node count** 9am–6pm via over-provisioner pods with low priority.

## Consolidation vs availability tradeoff

`WhenEmptyOrUnderutilized` saves money but evicts pods on underutilized nodes—even if those pods are memory-resident models with low CPU. For inference:

- Prefer `WhenEmpty` on GPU if models are memory-bound
- Or increase `consolidateAfter` until idle cost < reload cost

Calculate break-even:

```
savings_per_hour = node_hourly_cost
reload_cost_once = model_fetch_seconds * egress_cost + idle_gpu_during_load + lost_revenue_estimate

consolidateAfter_minutes > (reload_cost_once / savings_per_hour) * 60
```

Example: $3/hr node, $0.50 reload pain → consolidate after ~10 minutes minimum; add buffer → 45m.

## Multi-AZ and instance diversity

Agent traffic fails open badly when one AZ loses capacity. Requirements:

```yaml
requirements:
  - key: topology.kubernetes.io/zone
    operator: In
    values: ["us-east-1a", "us-east-1b", "us-east-1c"]
  - key: karpenter.k8s.aws/instance-family
    operator: In
    values: ["g6", "g5", "g4dn"]  # fallback families
```

Karpenter's bin-packing picks cheapest fit; too many families increases blast radius of AMI quirks—test each family in staging.

## Drift and AMI updates

Enable drift disruption on orchestrator pools, not GPU during business hours:

```yaml
disruption:
  budgets:
    - nodes: "1"
      schedule: "0 3 * * *"
      duration: 2h
      reasons:
        - Drifted
```

Rolling drift replaces nodes on new AMI while agent API traffic is low.

## Testing tuning changes

Before production:

1. **Load test** — synthetic run creation at 2× expected peak
2. **Chaos** — terminate random Spot nodes, measure run recovery
3. **Consolidation watch** — enable verbose Karpenter logs, confirm GPU nodes not consolidated under load

Record baseline: p95 schedule time, p95 cold inference latency, $/run infrastructure slice.

## The takeaway

Karpenter tuning for agent workloads is pool separation, honest resource requests, and consolidation timed to model economics—not CPU graphs alone. Give inference GPUs slow consolidation and on-demand stability; push batch work to Spot; annotate long runs against disruption; measure pending pods and reload cost. Savings without tuning is just faster churn.

## Resources

- [Karpenter — NodePool documentation](https://karpenter.sh/docs/concepts/nodepools/)
- [AWS — Karpenter on EKS best practices](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)
- [Karpenter — Disruption and consolidation](https://karpenter.sh/docs/concepts/disruption/)
- [NVIDIA — DCGM exporter for GPU metrics](https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-exporter-user-guide/index.html)
- [vLLM — Production deployment guide](https://docs.vllm.ai/en/latest/serving/deploying.html)
