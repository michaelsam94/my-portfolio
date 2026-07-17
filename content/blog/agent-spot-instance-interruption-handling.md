---
title: "AI Agents: Spot Instance Interruption Handling"
slug: "agent-spot-instance-interruption-handling"
description: "Gracefully drain agent workers on AWS Spot termination — IMDS notice, checkpointed tool jobs, and mixing on-demand baseline for streaming sessions."
datePublished: "2025-11-04"
dateModified: "2026-07-17"
tags: ["AI", "Agent", "Infrastructure", "AWS"]
keywords: "spot instance interruption, EC2 rebalance recommendation, agent worker drain, checkpoint, Karpenter"
faq:
  - q: "Which agent workloads are safe on spot instances?"
    a: "Batch eval jobs, embedding index rebuilds, offline fine-tuning data prep, log aggregation — fault-tolerant with checkpoints. Not safe without redundancy: real-time tool executor, streaming chat orchestrator, single-replica retrieval index serving live traffic."
  - q: "How much notice before spot termination?"
    a: "AWS typically 2 minutes via instance metadata and EventBridge. GCP preemptible ~30s. Design agent batch workers to checkpoint every 60–90 seconds and respect SIGTERM immediately."
  - q: "Spot vs on-demand mix for agent platforms?"
    a: "80/20 spot/on-demand for batch queues is common. Maintain on-demand baseline for queue depth SLA — when spot capacity evaporates, on-demand absorbs backlog. Never 100% spot on single-AZ critical path."
  - q: "Kubernetes spot for agent namespaces?"
    a: "Use node pools with taints agent-batch=spot:NoSchedule, PodDisruptionBudgets, and Karpenter capacity-type spot with on-demand fallback. Label agent realtime pods to require on-demand nodes."
---
Nightly agent eval suite processed 40,000 tool-calling scenarios on spot GPU instances. AWS reclaimed capacity at 3:12 AM — job died at 67% with no checkpoint. Morning release gate blocked on missing eval report. Re-run cost three hours and delayed ship. Checkpoint every 90 seconds plus spot interruption handler fixed the next week — interruptions became four-minute delays, not failed nights.

Spot and preemptible instances cut agent infrastructure cost 60–90% for fault-tolerant batch work: eval harnesses, embedding regeneration, corpus reindexing, synthetic data generation. Interruptions are expected weather — code must handle them.

## Interruption signal flow (AWS)

```
Spot reclaim decision
  → IMDS /metadata/spot/instance-action (2 min notice)
  → EventBridge EC2 Spot Instance Interruption Warning
  → SIGTERM to instance → SIGKILL after grace
```

Poll metadata from agent worker:

```python
import requests

def spot_interruption_pending() -> bool:
    try:
        r = requests.get(
            "http://169.254.169.254/latest/meta-data/spot/instance-action",
            timeout=1,
        )
        return r.status_code == 200
    except requests.RequestException:
        return False
```

Run aws-node-termination-handler as DaemonSet on spot pools — cordons node and triggers drain before SIGTERM. Wire handler to flush checkpoints or send SIGUSR1 to batch worker.

## Checkpoint loop

```python
def run_eval_shard(shard_id: int, cases: list):
    start = load_checkpoint(shard_id) or 0
    for i, case in enumerate(cases[start:], start=start):
        result = evaluate(case)
        write_result(result)
        if i % 10 == 0 or spot_interruption_pending():
            save_checkpoint(shard_id, i + 1)
        if spot_interruption_pending():
            graceful_exit(shard_id, i + 1)
            return
    mark_shard_complete(shard_id)
```

Checkpoint to S3/DynamoDB — not local disk alone. Use conditional writes so concurrent resume does not regress progress.

## SIGTERM and Karpenter consolidation

```python
signal.signal(signal.SIGTERM, handle_term)
```

Kubernetes terminationGracePeriodSeconds ≥ 120. Karpenter consolidation may SIGTERM without spot warning — treat every SIGTERM as capacity loss and checkpoint immediately.

## Queue-based batch architecture

```
SQS/Kafka queue → spot worker pool → results store
                      ↓ interrupt
                 checkpoint + requeue invisible messages
```

| Component | Spot-safe? |
|---|---|
| Eval worker | Yes with checkpoint |
| Embedding batch | Yes, idempotent chunks |
| Live retrieval API | No — on-demand min 2 |
| Tool executor | No |
| Index builder | Yes; swap alias atomically at end |

Set SQS visibility timeout to 2x p99 chunk duration. Heartbeat change_message_visibility every 60s during long embed batches.

## Karpenter mixed capacity

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: agent-batch-spot
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
      taints:
        - key: agent-batch
          value: spot
          effect: NoSchedule
```

Agent eval pods tolerate taint; orchestrator pods require on-demand nodeSelector. Enforce in CI with policy-as-code — mislabeled Deployments schedule chat gateway on spot.

## Diversification and GPU batches

Spread across m6i, m5, m5a and three AZs. capacity-optimized-pool reduces reclaim vs lowest-price-only. GPU embedding jobs reclaim frequently — checkpoint parquet partition offset; use on-demand floor for final 10% when SLA deadline near.

## Idempotent work units

```sql
INSERT INTO eval_results (case_id, score, run_id)
VALUES ($1, $2, $3)
ON CONFLICT (case_id, run_id) DO NOTHING;
```

## On-demand surge policy

SQS depth threshold triggers on-demand scale-up when spot interruption rate exceeds 5/minute in a region. Maintain minimum two on-demand workers during release week when eval gate blocks deploy.

## Monitoring and game day

Metrics: spot_interruption_total, eval_shard_resume_count, batch_job_wall_time, effective_cost including retry overhead. Alert when interruption rate >30%/hour or nightly eval coverage <100% at 06:00 UTC.

Quarterly game day: terminate 30% of spot nodes during active eval. Success: zero unrecoverable failures, resume within 2x chunk duration, no duplicate billable side effects.

## EventBridge-driven orchestration

Wire `EC2 Spot Instance Interruption Warning` to Step Functions or Lambda that: marks shard `paused` in DynamoDB, publishes requeue message to SQS with same `run_id`, and increments CloudWatch `spot_interruption_total`. Orchestrator picks paused shards on on-demand pool without human intervention — critical when interruption happens at 3 AM during release-week eval gate.

```python
def on_interruption_event(event, context):
    instance_id = event["detail"]["instance-id"]
    for shard in shards_on_instance(instance_id):
        save_checkpoint(shard.id, shard.progress)
        sqs.send_message(QueueUrl=REQUEUE_URL, MessageBody=shard.to_json())
        mark_paused(shard.id)
```

## Comparison: spot vs on-demand for agent batches

| Factor | Spot | On-demand |
|---|---|---|
| Cost | 60–90% lower | Baseline |
| Interruption | Expected | Rare |
| Agent eval fit | Excellent | Fallback queue |
| Live chat gateway | Never | Always |

## Release gate integration

Block promote to production if nightly eval shard coverage <100% at 06:00 UTC. Checkpoint metadata in S3 proves percentage complete — partial eval from spot interrupt without resume must fail CI, not ship with missing tool safety cases. Product and security sign release checklist only when eval artifact hash matches expected full-run fingerprint.

## Retry overhead math

```
effective_cost = spot_cost + (retry_overhead_hours * hourly_rate)
```

If retry overhead exceeds 15% of spot savings, increase checkpoint frequency from 90s to 45s or raise on-demand floor from 2 to 4 workers during business days. FinOps review monthly — spot without checkpoint discipline costs more than on-demand through duplicated GPU hours.

Real-time tool executor and streaming chat belong on on-demand — spot is for batch agent work with checkpoints.

## EventBridge-driven checkpoint flush

Subscribe Lambda or SQS worker to EC2 Spot Instance Interruption Warning. On event, publish `pause_shard` message keyed by instance ID so eval workers stop dequeuing new cases within seconds — before IMDS poll loop wakes up. Pair with DynamoDB conditional update marking instance `draining=true` so autoscaler does not schedule duplicate shard work on replacement node until checkpoint confirms last_case_index persisted. This pattern cut duplicate eval case execution from 3% to zero during spot storms in us-east-1 spring capacity crunches.

## Release gate integration

CI promote pipeline should query eval coverage table: `SELECT COUNT(DISTINCT case_id) FROM eval_results WHERE run_id=$1` compared against expected corpus size. Partial spot interrupt without resume must fail gate loudly — not silently ship with 94% coverage. Document expected spot interrupt rate in SRE handbook so on-call does not page for normal 2 AM reclaim during cost-optimized batch windows.

## Regional capacity planning

Maintain spot pool diversification across us-east-1a/b/c and secondary region DR batch queue. When entire AZ empties of spot GPU, cross-AZ shard reassignment via Step Functions avoids single-region release blockage. Finance model includes on-demand surge ceiling dollars per release week — pre-approved spend avoids 4 AM finance pager when ops scales on-demand eval workers during Black Friday prep.

## Comparison with reserved instances

Reserved instances suit flat baseline embedding clusters running 24/7. Spot plus checkpoint suits bursty nightly eval and reindex. Hybrid: reserved baseline for minimum daily embed throughput, spot burst for catch-up after corpus import spikes. Agent platform cost reviews should segment batch vs realtime — consolidating both into one ASG drives wrong capacity type choices.
## Operational checklist before production cutover

Document owners, rollback steps, and metric dashboards before enabling changes for enterprise tenants. Run staged rollout at five percent traffic for one business week when touching authentication, billing, or batch infrastructure — agent platforms amplify partial failures across every tenant workflow simultaneously. Keep runbook section updated after each game day or incident retrospective so the next engineer does not rediscover the same spot reclaim or SAML metadata gap under pager pressure.


## Resources

- [AWS Spot Instance best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
- [Spot Instance interruption notice](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler)
- [Karpenter disruption controls](https://karpenter.sh/docs/concepts/disruption/)
- [GCP preemptible VM documentation](https://cloud.google.com/compute/docs/instances/preemptible)
