---
title: "Cron Jobs, Timezones, and DST Bugs"
slug: "rag-cron-timezone-dst-bugs"
description: "Fix cron and scheduled agent jobs across timezones and DST — ambiguous local times, skipped hours, duplicate runs, and why UTC-only cron fails global agent fleets."
datePublished: "2026-04-27"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cron"]
keywords: "cron timezone DST, daylight saving time bugs, scheduled agent jobs, Temporal cron, Kubernetes CronJob timezone, skipped hour"
faq:
  - q: "Should agent cron jobs run in UTC or local timezone?"
    a: "Store and compute next-run instants in UTC internally; accept schedule definitions in the user's IANA timezone (America/New_York) when the job must fire at local wall-clock time — 'every day at 9am EST for this tenant.' Never use fixed UTC offsets (UTC-5) — they break twice yearly at DST transitions."
  - q: "What happens to cron jobs scheduled at 2:30 AM during US spring DST?"
    a: "On spring-forward day, 2:00–2:59 AM local time does not exist. Cron implementations either skip the run, run once at 3:00 AM, or throw — behavior varies by scheduler. Document your platform's choice and avoid scheduling critical agent batch jobs in the 2–3 AM window for US timezones."
  - q: "Why did our agent digest run twice on DST fall-back day?"
    a: "Fall-back repeats the 1:00–1:59 AM hour. Cron expressions like '0 * * * *' or '30 1 * * *' match twice unless the scheduler tracks UTC instants or deduplicates by monotonic run ID. Use idempotency keys on agent job execution — duplicate cron fires must not double-charge or double-email."
---
The weekly agent digest email arrived twice for Chicago tenants on November 3rd and never fired for Sydney tenants on October 6th. Both incidents traced to the same root cause: cron expressions evaluated in **UTC** against product copy promising "Monday 9 AM your local time." Spring DST made 2:30 AM jobs vanish; fall-back made hourly jobs duplicate. The scheduler was technically correct; the **timezone contract** was undefined.

Agent platforms schedule heavily — report generation, embedding refresh, billing aggregation, proactive outreach, eval harnesses. Each tenant expects local wall-clock semantics. This post covers IANA timezone handling, DST edge cases, idempotent execution, and scheduler patterns that survive global fleets.

## Three failure modes at DST boundaries

| Transition | Local clock behavior | Cron risk |
|------------|---------------------|-----------|
| Spring forward | Hour skipped (2→3 AM) | Missed run |
| Fall back | Hour repeated (1 AM twice) | Duplicate run |
| Zone rule change | Government moves DST date | Wrong instant forever until tzdata update |

Fixed-offset timezones (`UTC+10`) do not observe DST — until they do (see Samoa 2011). Always use IANA identifiers: `Australia/Sydney`, not `AEST`.

```
Spring forward (US): 2026-03-08 02:30 America/New_York
  ──► local time 02:30 does not exist
  ──► valid next: 03:00 EDT (instant jumps forward)

Fall back (US): 2026-11-01 01:30 America/New_York  
  ──► 01:30 occurs twice (EDT then EST)
  ──► same cron match, two UTC instants 1 hour apart
```

## Anti-pattern: server-local cron

Kubernetes CronJob default uses controller manager timezone — usually UTC. A manifest `schedule: "0 9 * * 1"` runs Monday 09:00 UTC, not user local.

```yaml
# WRONG for "Monday 9am per tenant"
apiVersion: batch/v1
kind: CronJob
metadata:
  name: agent-weekly-digest
spec:
  schedule: "0 9 * * 1"  # UTC unless timezone field set (K8s 1.27+)
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: digest
              image: agent-worker:latest
```

Kubernetes 1.27+ adds `spec.timeZone` on CronJob — still one timezone per job, not per tenant. Multi-tenant agent platforms need an application scheduler.

## Pattern: next-run computation with zoneinfo

Compute next fire time in Python 3.9+ with `zoneinfo`:

```python
# scheduler/next_run.py
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

def next_local_wall_time(
    after_utc: datetime,
    local_time: time,
    tz_name: str,
    weekdays: set[int] | None = None,  # 0=Monday
) -> datetime:
    """Return next UTC instant when local clock hits local_time in tz_name."""
    if after_utc.tzinfo is None:
        raise ValueError("after_utc must be timezone-aware UTC")

    tz = ZoneInfo(tz_name)
    local = after_utc.astimezone(tz)
    candidate_date = local.date()

    for _ in range(370):  # max scan ~1 year
        try:
            candidate_local = datetime.combine(candidate_date, local_time, tzinfo=tz)
        except Exception:
            # Non-existent time (spring forward) — skip forward
            candidate_date += timedelta(days=1)
            continue

        if candidate_local <= local:
            candidate_date += timedelta(days=1)
            continue

        if weekdays and candidate_local.weekday() not in weekdays:
            candidate_date += timedelta(days=1)
            continue

        return candidate_local.astimezone(ZoneInfo("UTC"))

    raise RuntimeError(f"No valid next run in range for {tz_name} {local_time}")
```

Spring-forward nonexistent times raise or skip depending on `combine` behavior — catch and advance to next valid day explicitly.

## Deduplication and idempotency

Fall-back duplicates require **run keys**:

```python
def build_run_key(schedule_id: str, scheduled_utc: datetime) -> str:
    # Use UTC instant, not local string — distinguishes repeated local hours
    return f"{schedule_id}:{scheduled_utc.isoformat()}"

async def execute_scheduled_job(schedule_id: str, scheduled_utc: datetime):
    key = build_run_key(schedule_id, scheduled_utc)
    if await redis.set(key, "1", nx=True, ex=86400 * 7):
        await run_agent_digest(schedule_id)
    else:
        logger.info("duplicate cron suppressed", extra={"key": key})
```

Agent side effects — emails, LLM batch spend, Stripe usage records — must check idempotency before work starts.

## Per-tenant timezone registry

```sql
CREATE TABLE agent_schedules (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  cron_expr TEXT,              -- optional legacy
  local_time TIME NOT NULL,    -- 09:00:00
  local_tz TEXT NOT NULL,      -- IANA name
  weekdays SMALLINT[] NOT NULL DEFAULT '{1}',  -- Mon=1..Sun=7
  next_run_at TIMESTAMPTZ NOT NULL,
  last_run_at TIMESTAMPTZ
);

CREATE INDEX idx_schedules_next ON agent_schedules (next_run_at)
  WHERE enabled = true;
```

A polling worker claims due rows with `FOR UPDATE SKIP LOCKED`, executes, recomputes `next_run_at` via `next_local_wall_time`, commits. Avoid cron entirely for tenant-local semantics — store absolute next instant.

## Testing DST transitions

Property tests beat manual calendar watching:

```python
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

@pytest.mark.parametrize("tz, spring_date", [
    ("America/New_York", "2026-03-08"),
    ("Europe/London", "2026-03-29"),
    ("Australia/Sydney", "2026-10-04"),
])
def test_spring_forward_no_crash(tz, spring_date):
    after = datetime.fromisoformat(f"{spring_date}T06:00:00+00:00")
    nxt = next_local_wall_time(
        after, time(2, 30), tz, weekdays={6}  # Sunday
    )
    assert nxt > after

def test_fall_back_idempotent_keys():
    tz = ZoneInfo("America/New_York")
    # Two UTC instants map to repeated 1:30 AM local
    t1 = datetime(2026, 11, 1, 5, 30, tzinfo=ZoneInfo("UTC"))  # 1:30 EDT
    t2 = datetime(2026, 11, 1, 6, 30, tzinfo=ZoneInfo("UTC"))  # 1:30 EST
    k1 = build_run_key("sched-1", t1)
    k2 = build_run_key("sched-1", t2)
    assert k1 != k2
```

CI should run against latest `tzdata` package; pin version in Docker images and upgrade on schedule — Argentina and Morocco change rules with minimal notice.

## Managed schedulers and agents

**Temporal** — use calendar schedules with timezone in workflow code; replay-safe timers handle DST if specified via SDK timezone-aware APIs.

**AWS EventBridge Scheduler** — supports `ScheduleExpressionTimezone`; still verify spring/fall behavior for `cron()` expressions.

**Cloud Scheduler (GCP)** — `timeZone` field on job; document duplicate behavior on fall-back.

For LLM agent **cron tools** exposed to users ("remind me every weekday at 8am"), parse natural language into `{local_time, tz_name}` via structured output — never free-text cron from the model without validation.

```typescript
const ScheduleSchema = z.object({
  localTime: z.string().regex(/^\d{2}:\d{2}$/),
  timezone: z.string().refine(isValidIanaTimezone, "Invalid IANA timezone"),
  weekdays: z.array(z.number().min(0).max(6)).min(1),
});
```

Reject `EST`/`PST` abbreviations — ambiguous.

## Observability

Metrics:

- `scheduler.runs.scheduled` vs `scheduler.runs.executed` — gap indicates misses
- `scheduler.runs.duplicate_suppressed`
- `scheduler.next_run_lag_seconds` — worker backlog

Alert when any tenant's `next_run_at` is more than 2× interval in the past — stuck lock or tz computation bug.

Log `{schedule_id, tenant_id, scheduled_utc, local_wall, tz_name}` on every execution for postmortems spanning DST weekends.

## Product communication

When users configure schedules, show **next three run times** in their timezone including DST-adjusted dates — preview catches "your job will skip March 8" before save.

Document platform behavior for ambiguous hours in help center; link from agent UI when user picks 2:00–3:00 AM local.

## Migration from legacy UTC cron

Teams often inherit `0 14 * * *` UTC jobs that "worked" until EU tenants onboarded. Migration path:

1. Inventory all CronJob manifests and database schedules with owner and user-facing description.
2. Classify each as **instant** (run at fixed UTC) vs **wall-clock** (run at local time per tenant).
3. For wall-clock jobs, backfill `local_tz` from tenant profile — default `America/New_York` is wrong for half your base.
4. Run shadow mode for two weeks: compute new `next_run_at` alongside legacy cron, log divergence without executing twice.
5. Cut over on a non-DST weekend in the dominant timezone; keep idempotency keys for two release cycles.

Agent eval cron jobs that refresh golden datasets should stay UTC-aligned to CI — only customer-visible schedules need local semantics.

## The takeaway

Cron timezone bugs hit agent fleets twice a year unless you treat local wall-clock schedules as first-class: IANA zones, UTC storage, explicit next-run computation, idempotent execution keys, and DST test fixtures in CI. UTC-only cron is fine for internal infra; customer-facing agent schedules need per-tenant timezone registry and duplicate suppression on fall-back nights. The email that sends twice destroys trust faster than any model hallucination.

## Resources

- [IANA Time Zone Database](https://www.iana.org/time-zones)
- [Python zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html)
- [Kubernetes CronJob timezone (v1.27+)](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Temporal schedules guide](https://docs.temporal.io/workflows#schedule)
- [Falsehoods programmers believe about time](https://inventivehq.com/blog/falsehoods-programmers-believe-about-time)
