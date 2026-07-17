---
title: "AI Agents: Preemptible Workload Checkpoint"
slug: "agent-preemptible-workload-checkpoint"
description: "Checkpointing long-running agent batch jobs on spot and preemptible VMs — notice windows, idempotent resume, and storage patterns that turn 70% cost savings into reliable throughput."
datePublished: "2026-02-28"
dateModified: "2026-02-28"
tags: ["AI", "Agent", "Preemptible"]
keywords: "preemptible instances, spot instances, checkpoint resume, agent batch jobs, GPU spot training, interruption notice, idempotent workers"
faq:
  - q: "How often should agent batch jobs checkpoint on preemptible nodes?"
    a: "Interval should be less than notice window minus drain time minus upload latency. On GCP preemptible VMs you get ~30 seconds notice; AWS Spot Instance interruption notices are typically two minutes. If checkpoint upload takes 45 seconds, checkpoint at least every 60–90 seconds on AWS and every 15–20 seconds on GCP for long jobs."
  - q: "What state must a checkpoint include for agent pipelines?"
    a: "Cursor into the work queue (offset or shard ID), completed item IDs for idempotency, partial aggregation results, model or embedding version, and prompt template hash. Omit ephemeral caches that can be rebuilt — keep checkpoints small to upload before the node dies."
  - q: "Can online agent serving run on preemptible capacity?"
    a: "Only with warm standby on on-demand nodes and sub-second failover. Batch embedding, evaluation sweeps, and offline tool replay are the sweet spot. Interactive chat agents belong on stable capacity unless you accept session drops and replay from conversation state stored externally."
  - q: "How do you avoid duplicate side effects after resume?"
    a: "Make every unit of work idempotent with a deterministic idempotency key. On resume, skip items whose keys appear in the checkpoint's completed set. For writes to external systems, use upserts or compare-and-set rather than blind inserts."
---
Spot savings looked great on the spreadsheet until a reclaim erased eleven hours of embedding generation. The job restarted from item zero because the only "checkpoint" was a log line saying "processed 840,000 rows."

Preemptible and spot instances cut compute bills 60–80% for agent batch workloads — if checkpointing is a first-class design constraint, not a post-incident patch.

## The economics only work with resume semantics

Agent batch jobs — bulk embedding, eval harness runs, document ingestion into RAG corpora, synthetic conversation generation — are embarrassingly parallel and tolerate minutes of pause. That profile maps cleanly to preemptible VMs, Google Cloud Spot VMs, and AWS Spot Fleet.

The break-even math is simple. Suppose on-demand GPU time costs $3.20/hour and spot averages $0.85/hour. A 24-hour embedding job saves roughly $56 per run. If preemptible reclaim happens twice and you lose four hours of progress each time because you cannot resume, you paid $6.80 in extra on-demand rework and burned engineer time on top.

Checkpointing converts spot volatility from a project risk into a line-item discount. Without it, finance eventually mandates on-demand "for reliability" and the FinOps win evaporates.

## Interruption mechanics you must design around

Each cloud signals differently. Treat documentation as approximate — always measure in your region and instance type.

**AWS EC2 Spot** sends an two-minute interruption notice via instance metadata and EventBridge. Some instance types and capacity crunches shorten the window. IMDS path: `GET /latest/meta-data/spot/instance-action`.

**GCP preemptible/Spot VMs** provide roughly 30 seconds after the preemption notice. The metadata server sets `instance/preempted` to TRUE.

**Azure Spot VMs** offer evictions with 30 seconds to two minutes depending on policy and capacity.

Your checkpoint pipeline must complete: flush in-memory buffers, serialize state, upload to durable storage, and acknowledge — inside that window. If upload takes 90 seconds, you need asynchronous checkpointing with bounded staleness, not synchronous checkpoint-on-every-item.

## Checkpoint design for agent workloads

Divide job state into three tiers:

**Tier 1 — Resume-critical.** Work cursor, completed idempotency keys, checksum of aggregate outputs. Must reach object storage before process exit.

**Tier 2 — Rebuildable.** Local embedding cache, retrieved chunks, intermediate token counts. Recompute on resume if lost; do not block shutdown uploading megabytes of discardable data.

**Tier 3 — Debug-only.** Sample outputs, per-item latency histograms. Nice for postmortems; optional during interruption drain.

For a RAG ingestion pipeline processing PDF shards, Tier 1 might be `{shard_index: 412, completed_doc_ids: [...], chunk_count: 1840000}`. On resume, skip doc IDs in the set and continue from shard 412.

## Implementation: notice handler plus async checkpoint loop

Python sketch using AWS metadata and S3 checkpoint store:

```python
import json
import signal
import threading
import time
import urllib.request
from dataclasses import dataclass, asdict

CHECKPOINT_INTERVAL_SEC = 90
CHECKPOINT_URI = "s3://agent-batch/checkpoints/job-7f3a/state.json"

@dataclass
class JobState:
    job_id: str
    next_offset: int
    completed_ids: list[str]
    model_version: str

class PreemptibleWorker:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.state = JobState(job_id, 0, [], "text-embedding-3-large-v1")
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def run(self):
        threading.Thread(target=self._spot_watchdog, daemon=True).start()
        threading.Thread(target=self._checkpoint_loop, daemon=True).start()
        for item in self._work_queue():
            if self._stop.is_set():
                break
            self._process(item)
            with self._lock:
                self.state.completed_ids.append(item.id)
                self.state.next_offset = item.offset + 1

    def _spot_watchdog(self):
        while not self._stop.is_set():
            if self._spot_interruption_pending():
                self._stop.set()
                self._flush_checkpoint(final=True)
                return
            time.sleep(5)

    def _spot_interruption_pending(self) -> bool:
        try:
            req = urllib.request.Request(
                "http://169.254.169.254/latest/meta-data/spot/instance-action",
                headers={"X-aws-ec2-metadata-token": self._imds_token()},
            )
            urllib.request.urlopen(req, timeout=1)
            return True
        except urllib.error.HTTPError as e:
            return e.code != 404

    def _checkpoint_loop(self):
        while not self._stop.is_set():
            time.sleep(CHECKPOINT_INTERVAL_SEC)
            self._flush_checkpoint(final=False)

    def _flush_checkpoint(self, final: bool):
        with self._lock:
            payload = asdict(self.state)
        payload["final"] = final
        payload["ts"] = time.time()
        upload_json(CHECKPOINT_URI, payload)  # multipart upload, retry with backoff
```

On startup, load the checkpoint if present:

```python
def resume_or_create(job_id: str) -> PreemptibleWorker:
    raw = download_json(CHECKPOINT_URI)
    worker = PreemptibleWorker(job_id)
    if raw:
        worker.state = JobState(**{k: raw[k] for k in JobState.__dataclass_fields__})
        worker._work_queue = lambda: queue_from_offset(raw["next_offset"])
    return worker
```

Pair with idempotent writes in `_process`:

```python
def _process(self, item):
    if item.id in self.state.completed_ids:
        return  # duplicate delivery after partial crash
    chunks = embed(item.text)
    upsert_vectors(item.id, chunks)  # idempotent upsert, not blind insert
```

## Kubernetes and queue integration

Running on EKS or GKE, use a `PriorityClass` or dedicated node pool for spot workloads. Taint spot nodes; tolerate only batch job pods. Never schedule stateful interactive agents there without external session stores.

The job controller — Kueue, Argo Workflows, or a simple SQS consumer — must distinguish **retry** from **resume**. Retry re-enqueues the whole job; resume passes checkpoint URI in the job spec. After preemption, the controller should immediately requeue the same job ID with `resume_from=CHECKPOINT_URI`, not increment attempt count toward DLQ.

Set `terminationGracePeriodSeconds` on batch pods to at least your worst-case checkpoint flush plus 15 seconds buffer. A 30-second default kills the process mid-upload.

For GPU jobs, checkpoint model weights only if you are fine-tuning. Inference-only embedding jobs reference a fixed model version string — reloading weights on resume is wasteful. Re-pull from model registry on new pod start.

## Storage and consistency choices

Object storage (S3, GCS) fits large checkpoints. Use versioned keys or etags to detect concurrent writers if multiple workers mistakenly claim the same shard. Redis or DynamoDB fits small, frequent cursor updates when upload latency to S3 is too high — sync to S3 every N minutes for disaster recovery.

Encrypt checkpoints at rest if they contain customer text snippets from ingestion jobs. Lifecycle rules expire checkpoints seven days after job completion — orphaned state should not linger.

## Monitoring preemptible batch health

Track these metrics per job type:

- `checkpoint_age_seconds` — time since last successful flush; alert if > 2× interval during active processing
- `preemption_events_total` — count by region and instance type
- `resume_success_rate` — jobs that continue vs. restart from zero
- `wasted_compute_seconds` — estimated work redone after failed checkpoint
- `spot_savings_usd` — on-demand equivalent minus actual spend

Dashboard that compares wasted compute to savings keeps finance aligned when spot looks "flaky" in a bad week.

## When not to checkpoint

Ultra-short jobs where checkpoint overhead exceeds run time — skip spot or accept occasional full retry. Jobs with non-idempotent external side effects (sending emails, charging cards) need outbox pattern or external idempotency keys before spot is safe at all.

Interactive agent sessions are a poor fit unless conversation state lives in Redis and any pod can resume — that is a different architecture than batch checkpointing.

## Cost allocation and FinOps reporting

Tag every checkpoint file and job metric with `cost_center`, `team`, and `workload_type`. Finance wants proof spot savings exceed rework — export weekly reports:

```
spot_savings = on_demand_equivalent_hours × on_demand_rate − actual_spot_spend
rework_cost = duplicate_items_processed × avg_cost_per_item
net_savings = spot_savings − rework_cost − checkpoint_storage_usd
```

When net savings turns negative for a job type, either tighten checkpoint interval, shrink Tier 1 payload, or move that workload back to on-demand until the pipeline is fixed. Without this accounting, preemptible programs die after one visible failure in an executive demo.

Mixed-instance fleets help: run the last 10% of shards on on-demand as a "completion buffer" while spot workers chew through the long tail. Checkpointing plus buffer nodes beats pure spot for deadline-sensitive eval runs before a product launch.

Load-test preemption in staging by voluntarily terminating spot nodes during a batch run — chaos beats assuming metadata notices always arrive. Record whether checkpoint upload completes inside the measured window; adjust interval and payload size until success rate exceeds 99% across ten forced kills.

## Resources

- [AWS Spot Instance Interruption Notices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)
- [GCP Spot VM preemption documentation](https://cloud.google.com/compute/docs/instances/spot)
- [Kubernetes Pod termination graceful shutdown](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)
- [Argo Workflows retry and exit handlers](https://argo-workflows.readthedocs.io/en/latest/walk-through/retries/)
- [Dask distributed worker preemptible best practices](https://docs.dask.org/en/stable/adaptive.html)
