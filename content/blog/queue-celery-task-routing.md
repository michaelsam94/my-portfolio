---
title: "Celery Task Routing Queues"
slug: "queue-celery-task-routing"
description: "Route tasks by name to dedicated workers — priority and rate limits per queue."
datePublished: "2026-03-14"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "celery task routing, celery queues, worker concurrency, task_routes"
faq:
  - q: "How does Celery decide which queue receives a task?"
    a: "The producer sends to an exchange/routing key (Redis/RabbitMQ backend dependent). task_routes maps task names or patterns to queue names. Workers subscribe only to queues listed in -Q flag or worker_queues config. A task routed to 'pdf' never runs on a worker that only consumes 'default'."
  - q: "Can one Celery worker consume multiple queues?"
    a: "Yes: celery -A proj worker -Q critical,default,low. Order in -Q can imply priority in some broker setups, but true priority requires separate workers or broker priority features. Mixing heavy and light tasks on one worker still risks head-of-line blocking unless concurrency and prefetch are tuned."
  - q: "What is the difference between task_routes and task_default_queue?"
    a: "task_default_queue is the fallback when no route matches — usually 'celery'. task_routes is the explicit routing table. Set default to a low-priority queue intentionally so new tasks without routes do not starve critical work."
---

Email confirmation tasks sat behind a three-hour PDF export backlog because every `@shared_task` landed on the default `celery` queue and one worker pool handled everything. Splitting routes — `critical`, `default`, `batch` — and deploying workers with `-Q critical -c 4` vs `-Q batch -c 1` dropped confirmation latency from minutes to seconds without adding Redis memory. Celery routing is boring infrastructure until the wrong task shares a queue with the wrong neighbor.

## Celery routing topology

```
Producer (Django/FastAPI)
        │
        ▼
   Router (task_routes)
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
critical   default     batch
   │         │          │
   ▼         ▼          ▼
Worker A   Worker B   Worker C
```

## Defining task_routes

```python
# celeryconfig.py
task_routes = {
    'billing.tasks.charge_invoice': {'queue': 'critical'},
    'billing.tasks.send_receipt': {'queue': 'critical'},
    'reports.tasks.generate_pdf': {'queue': 'batch'},
    'reports.tasks.*': {'queue': 'batch'},
    'analytics.tasks.*': {'queue': 'low'},
}

task_default_queue = 'default'
task_create_missing_queues = True
```

Task definition override:

```python
@shared_task(queue='critical')
def charge_invoice(invoice_id: str):
    ...
```

Inline `queue=` beats `task_routes` for that task — use sparingly to keep routing centralized.

## Worker deployment patterns

```yaml
# critical-worker
command: ["celery", "-A", "proj", "worker", "-Q", "critical", "-c", "8"]

# batch-worker
command: ["celery", "-A", "proj", "worker", "-Q", "batch", "-c", "1", "--prefetch-multiplier=1"]
```

**Batch queue:** low concurrency, prefetch 1 — prevents one worker from hoarding hundred PDF jobs.

**Critical queue:** higher concurrency, aggressive autoscaling on queue depth metric.

## Rate limits per task

```python
@shared_task(rate_limit='10/m', queue='default')
def sync_crm_contact(contact_id: str):
    ...
```

Rate limit is per worker instance, not global — ten workers each at `10/m` equals 100/min fleet-wide.

## Priorities on RabbitMQ vs Redis

**RabbitMQ:** supports `x-max-priority` on queues; Celery can publish with priority 0–9.

**Redis broker:** priority support is limited — **separate queues + dedicated workers** is the reliable pattern for SLA tiers on Redis.

## Kombu exchanges with RabbitMQ backend

```python
from kombu import Exchange, Queue

task_queues = (
    Queue('critical', Exchange('critical', type='direct'), routing_key='critical'),
    Queue('batch', Exchange('batch', type='direct'), routing_key='batch'),
)
```

Redis broker ignores exchange topology — routes map directly to list names.

## Beat scheduler separation

Celery Beat enqueues periodic tasks — run Beat as **single instance**. Scheduled tasks still honor `task_routes`:

```python
app.conf.beat_schedule = {
    'nightly-report': {
        'task': 'reports.tasks.generate_all',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'batch'},
    },
}
```

Do not run Beat on worker pods that scale horizontally — duplicate schedules duplicate charges.

## Autoscaling on queue depth

Kubernetes HPA custom metric from Redis:

```
celery_queue_length{queue="critical"} → scale critical-worker deployment
```

Separate HPAs per queue — scaling batch workers when critical depth rises wastes money.

## Monitoring routed workloads

Flower shows per-queue depth. Prometheus exporter labels metrics by queue. Alert when `critical` depth > 0 for > 60 seconds during business hours.

## Chord and chain routing implications

```python
from celery import chord
chord([fetch.s(i) for i in ids], aggregate.s()).apply_async(queue='batch')
```

Header tasks inherit group queue; callback may land on default — set `link` queue explicitly.

## Common routing mistakes

1. **Workers not subscribed to new queue** — tasks accumulate invisible to default workers.
2. **Heavy task on default** — new `@shared_task` without route goes to `task_default_queue`.
3. **Same queue for beat and interactive** — nightly job floods `default`.
4. **Prefetch too high on long tasks** — set `--prefetch-multiplier=1` for batch queues.
5. **Ignoring task_acks_late** — killed worker redelivers; idempotent tasks required on critical queue.

## Staging parity for task_routes

Copy production `task_routes` to staging exactly — drift causes "works in staging on default queue" surprises. CI test that asserts every registered task name appears in routing table.

Celery routing is configuration-as-architecture: task names map to SLA tiers, workers map to capacity pools, and the broker holds the contract between them. Get the tables right once; on-call spends fewer nights wondering why signup emails wait behind tax PDFs.

## Django integration and task discovery

Django autodiscovers tasks from `tasks.py` in installed apps — routing config must load before worker starts:

```python
# proj/celery.py
app = Celery('proj')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

`CELERY_TASK_ROUTES` in Django settings mirrors `task_routes` dict. Forgetting to restart workers after settings change leaves old routes active — document worker restart in deploy checklist alongside migrations.

## Multi-tenant routing by header

SaaS platforms route tenant bulk jobs to isolated queues:

```python
def route_for_task(name, args, kwargs, options, task=None, **kw):
    tenant_tier = kwargs.get('tenant_tier', 'default')
    if tenant_tier == 'enterprise':
        return {'queue': 'critical'}
    return {'queue': 'default'}

app.conf.task_router = (route_for_task,)
```

Dynamic routers beat static dict for tenant-specific SLAs — test router unit tests with kwargs fixtures.

## Celery 5.x and quorum queues (RabbitMQ)

RabbitMQ 3.8+ quorum queues for durability pair with Celery when broker URL uses quorum declaration in `task_queues`. Routing keys unchanged; worker prefetch must stay low on quorum due to delivery semantics — consult Celery + RabbitMQ quorum docs for your version combo.

## Flower auth and queue isolation

Flower displays same queue topology as workers — mount behind same SSO as admin tools. Read-only Flower for developers prevents accidental revoke without blocking queue visibility for debugging.

## Migration playbook: monolith queue split

Week 1: add routes, deploy workers subscribed to new queues, keep default workers on old queue. Week 2: migrate task names batch by batch; monitor depth on both. Week 3: remove default worker subscription to migrated tasks. Never big-bang route change without dual-subscribe period — tasks in flight during deploy land on old queue otherwise.

## Celery canvas routing for chains

Task chains pass results sequentially — each link inherits queue of chain head unless overridden per signature:

```python
(chain(process.s(i).set(queue='batch') for i in ids) | aggregate.s()).apply_async()
```

Misconfigured chain sends million map tasks to default while reduce lands on batch — verify chain queue propagation in staging load test.

## Eventlet/gevent pool and I/O bound routing

Gevent workers handle many I/O bound tasks on one process — routing webhooks to gevent pool and CPU PDF generation to prefork pool separates concerns better than single pool concurrency tuning. `-P gevent` worker only consumes `io` queue; CPU queue on prefork `-c 2`.

## Broker connection pool size

Each worker opens broker connections per process — scaling critical workers 10→50 increases RabbitMQ connection count. Route consolidation reduces connections but increases blast radius — monitor broker `connection_count` alert alongside queue depth.

## SQS as Celery broker routing

When using SQS broker via kombu, queue names map to SQS queue URLs in `task_queues` — IAM policy must allow `sqs:SendMessage` per queue ARN. Routing mistake sends tasks to nonexistent URL — tasks lost without Redis-style visibility; monitor SQS ApproximateNumberOfMessagesSent anomaly detection.

## Priority inversion in Celery chord

Chord callback runs after all header tasks complete — slowest header task blocks callback regardless of queue priority. Split chord headers to batch queue and promote callback to critical only if callback itself is SLA-sensitive; headers still gate completion.

## Instrumentation with task_prerun signal

Log queue and routing key on every task execution for traceability:

```python
from celery.signals import task_prerun

@task_prerun.connect
def log_routing(task_id, task, **kwargs):
    delivery = task.request.delivery_info or {}
    logger.info('task_start', extra={
        'task': task.name,
        'queue': delivery.get('routing_key'),
        'exchange': delivery.get('exchange'),
    })
```

Ship logs to structured aggregator — dashboard top tasks by queue catches routing regressions within hour of deploy instead of after customer complaint.

## Rolling deploy and in-flight task routing

Tasks published before deploy land on queue configured at publish time; workers after deploy may subscribe different set — in-flight tasks on removed queue stall until old worker drains. Blue-green worker deploy: keep old worker pool subscribed old+new queues until depth zero before decommission.
CI should fail if task_routes targets a queue absent from any worker Deployment -Q list — routes without consumers are silent black holes.
