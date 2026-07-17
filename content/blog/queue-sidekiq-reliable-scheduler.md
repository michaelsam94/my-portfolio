---
title: "Sidekiq Reliable Scheduler"
slug: "queue-sidekiq-reliable-scheduler"
description: "Scheduled jobs with Redis — unique jobs and death handlers for failures."
datePublished: "2026-03-18"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "sidekiq scheduler, sidekiq-cron, reliable scheduling, sidekiq unique jobs"
faq:
  - q: "How does Sidekiq schedule jobs for the future?"
    a: "Sidekiq stores scheduled jobs in a Redis sorted set (schedule) scored by Unix timestamp. The Sidekiq scheduler process polls due scores and pushes jobs to the appropriate queue lists. If scheduler process is down, jobs run late but remain in Redis — they are not lost unless Redis loses data."
  - q: "What is the difference between sidekiq-scheduler, sidekiq-cron, and Sidekiq Enterprise periodic jobs?"
    a: "sidekiq-cron loads cron YAML into Redis and enqueues on schedule. sidekiq-scheduler adds dynamic rescheduling from worker code. Sidekiq Enterprise provides Periodic Jobs with leader election built in. All require exactly one scheduler leader per Redis to avoid duplicate enqueues unless unique jobs guard duplicates."
  - q: "How do Sidekiq death handlers relate to scheduled jobs?"
    a: "Death handlers run when a job exhausts retries and lands in the Dead set. For scheduled/recurring jobs, a death handler prevents silent failure — log, alert, or re-enqueue next interval. Without handlers, nightly billing may fail for weeks before anyone notices empty invoices."
---

Subscription renewals stopped shipping on March 3rd because the Sidekiq scheduler pod had been OOMKilled for eleven days — and nobody noticed the empty `schedule` poll metric. Jobs were still in Redis, waiting for a process to call `enqueue` on due timestamps. Sidekiq scheduling is reliable against process crashes **if** Redis persists and **if** you run a singleton scheduler with monitoring.

## Redis data structures behind scheduling

Sidekiq keys (simplified):

```
schedule          ZSET  score=timestamp, member=job payload
retry             ZSET  backoff retries
dead              SET   exhausted failures
queue:default     LIST  ready jobs
```

If poller stops, `schedule` ZSET grows with due scores in the past — backlog executes in burst when scheduler returns.

Monitor:

```ruby
Sidekiq::ScheduledSet.new.size
Sidekiq::Stats.new.scheduled_size
```

Alert when oldest due job age > 5 minutes.

## sidekiq-cron setup

```yaml
# config/schedule.yml
billing_daily:
  cron: "0 2 * * *"
  class: BillingDailyJob
  queue: critical
```

```ruby
Sidekiq.configure_server do |config|
  config.on(:startup) do
    schedule = YAML.load_file(Rails.root.join('config/schedule.yml'))
    Sidekiq::Cron::Job.load_from_hash(schedule)
  end
end
```

Cron jobs re-register on Sidekiq **server** startup — not on web pods.

## Dynamic scheduling from workers

```ruby
class TrialReminderJob
  include Sidekiq::Job

  def perform(user_id, day)
    send_reminder(user_id, day)
    TrialReminderJob.perform_in(3.days, user_id, day + 1) if day < 7
  end
end
```

Use UTC consistently: `Time.zone = 'UTC'`.

## Unique jobs to prevent duplicate schedules

```ruby
class BillingDailyJob
  include Sidekiq::Job
  sidekiq_options lock: :until_executed, on_conflict: :log

  def perform
    InvoiceGenerator.run!
  end
end
```

Ensure lock Redis keys use same Redis as Sidekiq.

## Death handlers for recurring failures

```ruby
Sidekiq.configure_server do |config|
  config.death_handlers << ->(job, ex) do
    Sentry.capture_exception(ex, extra: { jid: job['jid'], class: job['class'] })
    PagerDuty.trigger('billing daily failed', job) if job['class'] == 'BillingDailyJob'
  end
end
```

## Singleton scheduler and leader election

**Anti-pattern:** Sidekiq server with cron enabled on every worker replica → duplicate enqueues at 2:00 AM.

Run one `sidekiq` deployment with cron, separate high-memory workers for batch without cron enabled.

## Clock skew and DST

```yaml
billing_daily:
  cron: "0 2 * * * America/New_York"
```

Test DST boundaries. Use UTC for storage, local for display.

## Redis persistence implications

Scheduled jobs survive Sidekiq restart only if Redis persists (AOF everysec typical). Ephemeral Redis in dev → false "scheduler unreliable" diagnosis.

## Sidekiq Web and operational visibility

Mount Sidekiq::Web behind auth. Tabs that matter: Scheduled, Retries, Dead, Cron (last enqueue time).

## Catch-up behavior after long outage

Document business decision: skip vs burst catch-up missed cron runs when scheduler down > 24h.

## Metrics export with Yabeda or Prometheus

Wire Grafana alert: `sidekiq_scheduled_latency_seconds` p99 > 300 during business hours.

## Argument serialization and schedule size

Keep args as IDs referencing database rows — multi-megabyte JSON in scheduled job slows Redis poll loop.

## Reliable scheduler checklist

- [ ] Redis AOF/RDB persistence enabled
- [ ] Single cron registration path (one server role)
- [ ] Unique locks on financial periodic jobs
- [ ] Death handlers alert on billing/settlement jobs
- [ ] Monitor `scheduled_size` and overdue job age
- [ ] DST and timezone documented in schedule.yml

Sidekiq's scheduler is durable because Redis is durable — not because polling is magic. Run one leader, lock duplicates, alert on death and overdue schedules, and rehearse what happens when eleven days of renewals enqueue in one minute.

## sidekiq-scheduler vs perform_at load

High-volume `perform_at` from user actions (remind me later) fills schedule ZSET — distinct from cron. Monitor schedule size separately from cron job count. Archive old scheduled jobs or use Redis TTL patterns for canceled reminders to prevent unbounded ZSET growth.

## Redis memory fragmentation

Sidekiq schedule entries serialize job args — memory fragmentation after burst schedule causes Redis OOM before `maxmemory` apparent full. Enable active defrag in Redis 4+ during maintenance window if schedule-heavy app shows RSS >> used_memory.

## Sidekiq Enterprise periodic vs cron

Enterprise periodic jobs integrate leader election — worth license when sidekiq-cron duplicate enqueue causes financial incident. Evaluate after first duplicate billing cron incident cost exceeds license.

## Graceful quiet before deploy

Run `sidekiqctl quiet` before deploy stops new job fetch; scheduler may still enqueue — quiet workers only. For zero duplicate cron during deploy, pause cron jobs in Sidekiq Web before pod termination if deploy spans cron minute boundary.

## Scheduled job idempotency

Cron enqueues even when previous run still active unless unique lock — long-running nightly job overlapping next cron creates duplicate parallel runs. Extend unique lock duration or use `lock: :while_executing` on job class.

## Kubernetes CronJob vs Sidekiq cron

Some teams run K8s CronJob that enqueues Sidekiq job instead of sidekiq-cron — duplicates scheduler responsibility. Pick one: Sidekiq-native cron for job args in Ruby ecosystem, K8s CronJob only when Sidekiq unavailable. Dual cron double-charges customers.

## Redis ACL and Sidekiq scheduler

Redis 6 ACL limits keys Sidekiq uses — scheduler role needs access to `schedule`, `queues`, and queue lists. Overly restrictive ACL causes silent schedule poll failures with generic connection errors — test ACL in staging with exact production prefix.

## Daylight saving and cron drift

Sidekiq-cron uses Fugit parser — invalid cron strings fail at load with error in logs during deploy. Add CI validation of schedule.yml schema and cron parse before merge.

## Horizontal scaling Sidekiq without cron

Worker replicas scale horizontally; only scheduler pod loads cron — HPA on worker deployment must exclude scheduler deployment from same manifest template. Template mistake duplicates cron on every HPA scale event before unique lock catches duplicate.

## Sidekiq Pro super_fetch reliability

Sidekiq Pro super_fetch reduces job loss on process crash — scheduler reliability separate from fetch reliability. Enterprise customers combine reliable scheduler with super_fetch so cron enqueue and worker fetch both survive Redis hiccups; evaluate bundle for financial cron paths.

## Monitoring Redis schedule key memory

`MEMORY USAGE` on schedule key during growth incident — identifies runaway perform_at from bug looping schedule without delete. Fix bug then ZREM orphaned entries or restart from known good backup if schedule corrupted.

## Runbook: scheduler pod not running

Step 1: verify Sidekiq process up. Step 2: check Redis schedule ZSET size and oldest score. Step 3: check sidekiq-cron last enqueue. Step 4: manual `Sidekiq::Cron::Job.find(name).enque!` for missed critical cron once after fix. Step 5: postmortem why alert did not fire.

## Billing cron idempotency audit

Before enabling new billing cron, QA verifies duplicate enqueue produces single charge — Stripe idempotency keys plus Sidekiq unique lock plus death handler page on any duplicate invoice ID in database unique constraint violation log.

## Closing principle

Scheduled money movement without scheduler monitoring is a liability. One Redis, one cron leader, unique jobs on financial tasks, death handlers that page, and alerts on overdue schedule entries — minimum bar before calling Sidekiq scheduling production-ready.

## Read next when cron misfires

Compare Sidekiq Web cron last enqueue timestamp with expected cron — if stale, scheduler process is down while workers healthy. If enqueue fresh but job not running, queue routing or worker `-Q` subscription mismatch is next check before blaming cron expression typo.

Document tier ownership, DLX bindings, cron schedules, and FIFO group-key schema in the same repository as application code — operational knowledge drift causes repeat incidents when runbooks live only in wiki software nobody updates after reorganizations.

Include scheduler pod health in the same PagerDuty service as payment workers — siloed alerts let scheduler die quietly while workers process backlog that never replenishes from cron.

Verify cron timezone in staging by enqueuing test job one minute ahead — catches UTC versus local misconfiguration before billing window.
Run cron enqueue from a single scheduler role and prove in staging with two pods that duplicate fires cannot happen; pair with uniqueness locks on the worker.
