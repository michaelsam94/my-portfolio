---
title: "Bull Board Queue Monitoring"
slug: "queue-bull-board-monitoring"
description: "UI for Bull/BullMQ — auth proxy, failed job retry, and stalled detection."
datePublished: "2026-03-13"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "bull board, bullmq monitoring, redis queue dashboard, stalled jobs"
faq:
  - q: "Does Bull Board work with both Bull and BullMQ?"
    a: "Yes, via separate adapters (@bull-board/api with @bull-board/bull or @bull-board/bullmq). BullMQ is the maintained successor; new projects should use BullMQ adapter. Queue names and Redis key prefixes must match your worker configuration or the dashboard shows empty queues."
  - q: "Why must Bull Board never be exposed publicly without authentication?"
    a: "The UI can retry failed jobs, promote delayed jobs, clean queues, and inspect payloads that may contain PII or secrets. Treat it like admin API access — mount behind SSO reverse proxy, VPN, or IP allowlist with session auth."
  - q: "What causes stalled jobs in Bull/BullMQ and how does Bull Board help?"
    a: "Stalled jobs occur when a worker stops heartbeating — process crash, long GC pause, or blocking synchronous work exceeding lockDuration. Bull Board highlights stalled counts; workers should log stall events. Fix root cause in worker code; use Bull Board to retry after deploy, not as permanent remediation."
---

Operations deleted the wrong Redis keys trying to "clear a stuck queue" because nobody could see what Bull was doing. After mounting Bull Board behind the internal OAuth proxy, on-call could inspect failed payloads, retry poison messages after a fix, and watch stalled counts drop after a worker memory leak patch — without SSH or raw `redis-cli`. A queue UI is not luxury; it is how you avoid becoming the person who `FLUSHDB`'d production.

## What Bull Board renders

Bull Board is an Express/Fastify middleware that reads Bull's Redis structures and serves a React UI:

```
Browser ──► nginx (SSO) ──► Express + Bull Board ──► Redis
                                    ▲
Worker processes ───────────────────┘ (same Redis)
```

Install for BullMQ:

```bash
npm install @bull-board/api @bull-board/express @bull-board/bullmq bullmq
```

```typescript
import express from 'express';
import { createBullBoard } from '@bull-board/api';
import { BullMQAdapter } from '@bull-board/bullmq';
import { ExpressAdapter } from '@bull-board/express';
import { Queue } from 'bullmq';

const serverAdapter = new ExpressAdapter();
serverAdapter.setBasePath('/admin/queues');

const emailQueue = new Queue('email', { connection: { host: 'redis.internal' } });
const webhookQueue = new Queue('webhook', { connection: { host: 'redis.internal' } });

createBullBoard({
  queues: [
    new BullMQAdapter(emailQueue),
    new BullMQAdapter(webhookQueue),
  ],
  serverAdapter,
});

const app = express();
app.use('/admin/queues', serverAdapter.getRouter());
app.listen(3001);
```

Queue instances must share the same Redis connection options and prefix as workers.

## Authentication and network placement

Never expose port 3001 to the internet. Patterns that work:

**OAuth2 reverse proxy (recommended).** nginx `auth_request` to Okta/Authelia; upstream to Bull Board only after 200 from auth subrequest.

**Separate admin deployment.** Bull Board runs as internal-only Kubernetes service with NetworkPolicy allowing ingress from VPN CIDR.

**Read-only mode.** Some teams wrap Bull Board routes and disable POST actions in production, forcing retries through audited CLI scripts.

Also restrict CORS and disable public DNS records for the admin host.

## Mapping Redis reality to the UI

Bull stores jobs in keys like `bull:email:wait`, `bull:email:active`, `bull:email:failed`. If Bull Board shows zero jobs but workers process work, check prefix mismatch, DB index mismatch, or missing TLS on ElastiCache.

```typescript
const connection = {
  host: process.env.REDIS_HOST,
  port: 6379,
  password: process.env.REDIS_PASSWORD,
  tls: process.env.REDIS_TLS === 'true' ? {} : undefined,
};
```

Document connection parity in the worker and board README.

## Stalled job detection

Bull marks jobs stalled when workers fail to renew locks — default `lockDuration` 30s.

```typescript
const worker = new Worker('webhook', processor, {
  connection,
  lockDuration: 60000,
  stalledInterval: 30000,
  maxStalledCount: 2,
});

worker.on('stalled', (jobId) => {
  metrics.increment('bull.job.stalled', { queue: 'webhook' });
});
```

Root causes: CPU-bound synchronous code in async handler, unhandled promise hang, pod SIGSTOP during node drain, Redis latency preventing lock renewal.

## Failed job triage workflow

1. Filter failed queue in Bull Board — sort by timestamp.
2. Inspect `failedReason` stack.
3. Check `attemptsMade` vs `opts.attempts`.
4. Retry individually first — confirm fix on one job.
5. Bulk retry via board or script after deploy.

Scripted retry:

```typescript
const failed = await q.getFailed(0, 100);
for (const job of failed) {
  if (job.failedReason.includes('ECONNRESET')) {
    await job.retry();
  }
}
```

Scrub payloads before screenshotting jobs for Slack.

## Metrics beyond the UI

| Metric | Alert threshold |
|--------|-----------------|
| `queue_waiting` | Sustained growth > 30 min |
| `queue_failed` rate | > baseline × 3 |
| `queue_stalled` | Any increment in 5 min window |
| Job age p95 (waiting) | Exceeds SLA |

Correlate Redis memory with delayed job ZSET size — huge delayed sets slow Bull Board pagination.

## Bull vs BullMQ adapter differences

| Concern | Bull (legacy) | BullMQ |
|---------|---------------|--------|
| Adapter import | `@bull-board/bull` | `@bull-board/bullmq` |
| Maintenance | Limited | Active |
| Flows / parent-child | No | Yes |

When migrating Bull → BullMQ, run board against both Redis namespaces during cutover.

## Graceful shutdown and active job visibility

During Kubernetes rolling deploy, workers receive SIGTERM; Bull waits `lockDuration` before marking jobs stalled. Set `terminationGracePeriodSeconds` greater than longest job runtime plus lock renewal interval.

## Integration with OpenTelemetry

Wrap processors to propagate trace context stored in job data:

```typescript
async function processor(job: Job) {
  const ctx = propagation.extract(context.active(), job.data.traceContext ?? {});
  return context.with(ctx, async () => {
    return span('process', job.name, async () => { ... });
  });
}
```

## Rate limiting admin actions

Bulk retry in Bull Board can overwhelm downstream APIs — wrap production board with rate limits on POST routes or require confirmation for actions affecting >100 jobs.

## Comparing Bull Board to Arena

Arena is an alternative Redis queue UI. Bull Board wins when you already use Bull/BullMQ adapters officially maintained. Grafana dashboards remain authoritative for paging; board is incident triage.

## Production hardening checklist

- [ ] Board behind SSO, no public route
- [ ] Same Redis prefix/DB/TLS as workers
- [ ] Role separation: read-only prod board vs full dev
- [ ] Alerts on stalled/failed independent of UI
- [ ] Job data schema avoids secrets (reference IDs only)

Bull Board closes the observability gap between "Redis is a black box" and actionable queue operations. Mount it safely, wire stall alerts, and treat retry buttons as sharp tools — useful after fixes, dangerous before root cause.

## Running Bull Board on Fastify

Teams standardizing on Fastify use `@bull-board/fastify` with identical adapter setup — mount path and auth proxy rules mirror Express. Ensure `setBasePath` matches reverse proxy strip prefix or static assets 404 silently.

## Job data redaction in board views

Wrap Bull Board with middleware that scrubs `job.data` fields matching `/password|token|ssn/i` before render — defense in depth when engineers accidentally enqueue secrets. Redaction middleware logs scrub events for security audit without blocking legitimate debugging on non-sensitive fields.

## Multi-environment board federation

Platform teams expose one board per environment (`board.prod.internal`, `board.staging.internal`) with color-coded titles — prevents retrying staging job against prod Redis because engineer bookmarked wrong URL. Never federate prod and staging queues in single board instance — one mis-click retries prod failed jobs.

## Board timeout on million-job queues

Completed job retention without cleanup fills Redis and makes Bull Board pagination timeout. Set `removeOnComplete: { count: 1000 }` and `removeOnFail: { count: 5000 }` at queue level — board stays responsive; metrics remain in Prometheus for historical depth.

## Incident runbook: stalled job spike

1. Check worker pod restarts and CPU throttling. 2. Check Redis latency (`INFO latency`). 3. Sample stalled job IDs — same job class? 4. Deploy fix; use board to retry failed only, not bulk active. 5. Post-incident: add stall alert if missing.

## Board behind Cloudflare Access

Zero-trust access policies gate `/admin/queues` by identity — audit log of who retried which job ID satisfies SOC2 change management without building custom auth middleware. Pair with IP allowlist for defense in depth.

## Custom job filters in Bull Board 5.x

Filter UI by queue state and job name substring — train on-call to filter `failedReason: ECONNREFUSED` before bulk retry after network fix. Reduces accidental retry of genuinely bad payloads mixed in failed set.

## Redis Cluster and Bull Board

Cluster mode requires hash tag in prefix `{bull:prod}` so related keys colocate — board and workers must use identical tagged prefix or jobs appear missing. Document hash tag in infrastructure terraform next to Redis cluster module.

## Docker Compose local board setup

Developers run Bull Board against local Redis with docker-compose service — same `REDIS_HOST=redis` as worker service prevents "works locally, empty board in CI" when CI uses different hostname. Commit compose file to repo as canonical dev topology.

## Audit log for board actions

Proxy logs POST body job ID and authenticated user email to SIEM — compliance asks who retried payment webhook job ID 8842 during incident. Read-only board for most engineers; retry role limited to platform on-call group.
Treat Board access like production DB access: SSO, audit logs, and no public ingress. Job payloads are a PII surface even when the UI feels like an internal toy.
