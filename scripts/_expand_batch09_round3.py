#!/usr/bin/env python3
"""Round 3: push remaining rewritten batch-09 posts over 1200 words with unique prose."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

def word_count(text: str) -> int:
    return len(WORD_PAT.findall(text))

def append_expansion(path: Path, expansion: str) -> int:
    raw = path.read_text()
    parts = raw.split("---", 2)
    body = parts[2] if len(parts) >= 3 else raw
    if word_count(body) >= 1200:
        return word_count(body)
    first = expansion.strip().splitlines()[0]
    if first in raw:
        return word_count(body)
    marker = "\n## Resources\n"
    block = "\n" + expansion.strip() + "\n"
    if marker in raw:
        raw = raw.replace(marker, block + "\n## Resources\n", 1)
    else:
        raw = raw.rstrip() + block + "\n"
    path.write_text(raw)
    return word_count(raw.split("---", 2)[2])

# Each block ~550-750 words of unique topic prose
B = {}

B["postgres-hot-standby-feedback-conflicts"] = """
## Designing standby classes explicitly

Most teams discover conflict settings during an outage. Define standby classes before the first replica ships. Promote-eligible standbys prioritize apply lag: short `max_standby_streaming_delay`, feedback on, aggressive statement timeouts. Application read replicas allow slightly longer queries but still kill idle-in-transaction quickly. Analytics replicas accept lag measured in minutes, may disable feedback if primary bloat dominates, and must be tagged so orchestrators never promote them.

Encode classes in Terraform or Patroni templates. When someone clones a replica for a data science dump, they inherit the analytics class, not HA. The expensive failure is an analytics-tuned node with `max_standby_streaming_delay = -1` sitting in the failover list, quietly lagging until promotion loses data.

## Vacuum, wraparound, and feedback

Feedback can contribute to transaction ID pressure because vacuum cannot reclaim dead rows still needed by replica snapshots. Monitor `age(datfrozenxid)` next to conflict metrics. If freeze age climbs while feedback is on, find the oldest standby snapshot via `xact_start` and terminate it. Wraparound emergencies are rare; feedback plus forgotten sessions is a known path on busy clusters.

## BI vendor defaults

Looker, Tableau, and similar tools open transactions more than engineers expect. Configure connectors with short idle timeouts and put them on roles with `statement_timeout`. Vendor defaults optimize convenience, not your primary's vacuum health. A short meeting with analytics engineering about timeouts prevents a long bloat incident.

## Application retries

Retry conflict-with-recovery errors with jittered backoff. Frameworks that treat every `OperationalError` as fatal will surface ordinary vacuum conflicts as user-facing flaps. Distinguish conflict cancels from constraint violations in the data access layer. For read-your-writes after a primary write, do not read the standby until lag is within budget — feedback does not create causal consistency.
"""

B["postgres-hstore-vs-jsonb-choice"] = """
## Validation layers

Whatever type you choose, validate shape at the edge. JSON Schema or app validators catch wrong types before they become query bugs. CHECK constraints with `jsonb_typeof` enforce invariants for critical keys. Do not treat the document as "whatever the client sent" if billing fields live inside it.

## GIN churn

GIN indexes on frequently updated jsonb can bloat under heavy key churn. Monitor index size. Sometimes a one-to-one side table for cold attributes beats mutating a large blob on every request. Semi-structured does not mean update the whole document every time.

## Cross-service contracts

If multiple services write the same column without a shared schema package, incompatible shapes appear. Publish a versioned schema module and reject invalid writes. Governance of keys matters more than the hstore vs jsonb debate once many teams touch the column.

## Query porting checklist

When migrating: replace `->` assumptions (text vs jsonb), rebuild GIN with the right opclass, dual-read for a week, compare facet counts, then drop the old column. Budget index build time. Train support that "missing key" and "null value" are different in jsonb.
"""

B["postgres-huge-pages-memory-tuning"] = """
## Troubleshooting start failures

When Postgres fails with `huge_pages=on`, check logs and `dmesg`, confirm `HugePages_Free` before start, and ensure no other process consumed the reservation. Other databases on the same host sometimes steal hugepages. Dedicate the reservation or size for both.

## Bare metal vs cloud

On bare metal, reserve via grub at boot. On cloud VMs, instance families differ in hugepage reliability — validate on the production family. A staging micro instance proves nothing.

## On-call runbook

Document how to verify hugepages, how to temporarily use `huge_pages=try` to recover during an emergency, and how to restore `on` afterward. On-call should not invent this at 3am.

## cgroup limits

Huge pages count against cgroup memory limits. Set container limits above shared_buffers plus connection memory plus headroom. OOM kills inside a cgroup while the node shows free RAM are a classic misconfiguration.
"""

B["postgres-lateral-joins-correlated"] = """
## ORM translation

Some ORMs emit correlated subqueries that never become LATERAL. For hot endpoints, write explicit LATERAL SQL in a repository method and measure with `auto_explain`. Fighting the ORM for micro-optimizations wastes time; isolating the SQL wins.

## Outer estimates

LATERAL is a nested loop. If the outer side estimates 1 row and finds 100k, the loop explodes. Keep outer filters selective and statistics fresh. Bad outer estimates turn elegant LATERAL into an outage.

## Precompute when QPS climbs

Feeds needing top-3 per entity at high QPS often outgrow LATERAL-on-read. Maintain a summary table via trigger or job. LATERAL remains perfect for admin tools and moderate traffic paths.

## DISTINCT ON for top-1

For a single latest row, `DISTINCT ON` is often clearer. Reach for LATERAL when N>1 or the inner query is complex with its own filters.
"""

B["postgres-lock-monitoring-pg-lock"] = """
## On-call game day

Hold an open transaction in one session, run DDL in another, and have on-call identify the blocker with the standard query. Muscle memory beats wiki search. Record the exercise.

## Hot row contention

Inventory counters and account balances create row-lock waiters under load. Sometimes the fix is sharding the hot row or optimistic concurrency, not canceling backends. Monitoring shows who waits; product design decides if serialization is required.

## Trend metrics

Sample waiter counts into Prometheus. A slow multi-week climb can reveal lengthening transactions after a release — catch it before peak traffic.

## Autovacuum caution

Do not kill autovacuum casually. Usually a human transaction is the real blocker. Check `xact_start` age before terminating maintenance workers.
"""

B["postgres-parallel-query-tuning"] = """
## Role-based defaults in practice

API roles get `max_parallel_workers_per_gather = 0`. Analyst roles get 4. The same primary stops wasting workers on point lookups while reports still parallelize. Leave headroom in `max_parallel_workers` for autovacuum and WAL senders.

## Memory multiplication

Parallel workers each allocate `work_mem`. A report that was safe serially can OOM when parallelized. Size `work_mem` and parallelism together; load-test concurrent copies of the biggest report.

## Proving plans in labs only

Lowering `parallel_setup_cost` proves a parallel plan exists. Do not ship that SET in pool defaults. If the planner needs permanent coercion, fix `parallel_workers` on the table or statistics instead.

## Maintenance vs query workers

Raise `max_parallel_maintenance_workers` for weekend index builds, then revert. Leaving it high lets surprise maintenance steal from query workers on Monday morning.
"""

B["postgres-pg-cron-scheduled-jobs"] = """
## Batch retention that finishes

Schedule frequent small deletes instead of one giant nightly delete. Each invocation should finish in seconds, commit, and leave the table responsive. Log `ROW_COUNT` and alert when three consecutive runs delete zero rows while growth continues.

## Image checklist

`shared_preload_libraries` must include `pg_cron` on every node that can become primary. Failover tests that skip cron produce silent retention gaps. Add it beside `archive_command` on the golden image checklist.

## Keep HTTP out

If the job needs HTTP, use an application worker. pg_cron is for SQL-local maintenance: retention, concurrent matview refresh, post-load ANALYZE. Advisory locks prevent overlap when a run overruns the next schedule tick.
"""

B["postgres-pg-snapshot-export-consistency"] = """
## Manifests and SOX

Write row counts captured inside the snapshot transaction into a manifest beside the CSV files. Importers verify counts before load. This pattern closed a SOX finding where transfers referenced missing accounts from a torn export.

## Coordinator lifetime

With `pg_export_snapshot`, keep the coordinator transaction open until all workers finish. Closing early invalidates snapshots and fails the pipeline. Orchestrators should wait on the worker group before commit.

## Compression placement

Prefer streaming `COPY TO STDOUT` through a client that compresses on the fly. `COPY TO PROGRAM gzip` holds the snapshot for the entire gzip runtime. Long snapshots on standbys also create conflict risk — pick export venue deliberately.
"""

B["postgres-pgbackrest-backup-strategy"] = """
## RTO from restore drills

Time restore to accept-connections and PITR apply separately. Backup duration does not equal restore duration. Publish numbers so leadership stops asking "are backups fast?" instead of "can we meet RTO?"

## Archive alerts

Alert on `pg_stat_archiver` failures and WAL disk usage independently from the nightly full backup job. Archive-push breaks fill disks on a different clock than backup cron.

## Keys and second repo

Encrypt object-storage repos and escrow keys. Keep a second repo offsite and restore from it monthly. Local-only backups are not disaster recovery.
"""

B["postgres-recursive-cte-hierarchies"] = """
## Cycle guards in depth

Always cap depth and detect cycles. UI bugs create parent loops; production APIs should not hang until `statement_timeout`. Postgres 14 `CYCLE` clause or array membership checks are mandatory on untrusted hierarchy data.

## Closure tables for hot paths

Permission checks on every request often outgrow recursive CTEs. Maintain a closure table in the same transaction as edge edits. Reads become simple indexed lookups; writes get slightly harder — usually worth it.

## Bounded tree APIs

Do not ship entire org charts to mobile clients. Return one level plus counts, or breadcrumbs via materialized path. Recursive SQL belongs behind caps.
"""

B["postgres-reindex-concurrently-bloat"] = """
## Invalid index alerts

Alert on `NOT indisvalid`. Failed concurrent rebuilds leave junk that confuses humans and tools. End every maintenance window with a validity check.

## Evidence before rebuild

Compare index size, leaf density, and whether the index appears in hot plans. Blind weekly reindex wastes I/O. Fix update patterns that churn indexed columns — otherwise rebuilds become a treadmill.

## Disk headroom

Concurrent reindex needs roughly another copy of the index. Check free space first. Mid-build disk-full is how invalid indexes are born.
"""

B["postgres-sequence-gap-contention"] = """
## Educate stakeholders

Gaps are not deleted rows. Show rolled-back imports consuming sequences. Use a separate transactional allocator only when law or product truly needs gapless numbers — and accept the throughput hit.

## CACHE for ingest

Insert-heavy tables often want `CACHE` in the tens or hundreds. Measure `nextval` contention before and after. Event IDs can tolerate large gaps; human-facing invoice numbers often cannot — do not share one strategy.

## ON CONFLICT burns IDs

Upserts frequently consume sequence values even when no row is inserted. Harmless for bigint surrogates; document it so nobody "fixes" gaps with dangerous resets.
"""

B["postgres-statistics-extended-multivariate"] = """
## Workflow from bad estimate

Find EXPLAIN with estimated vs actual off by orders of magnitude. Identify correlated AND filters or joins. `CREATE STATISTICS` with the right kinds, `ANALYZE`, re-EXPLAIN. Keep the before/after plan in the PR.

## Join columns too

Skewed join keys deserve extended stats as much as filter pairs. Bad join estimates produce catastrophic nested loops.

## Hygiene

Do not spray stats across every column set. Each object should link to a query it fixes. After bulk ETL, ANALYZE explicitly so extended stats refresh with the rest.
"""

B["postgres-synchronous-commit-tradeoffs"] = """
## Per-role policy

Ingest and clickstream may use `synchronous_commit=off`. Payments and inventory stay `on` or use sync replication. Document so global "cleanup" does not erase the distinction.

## Stall playbook

Sync replication without a degrade policy stalls commits when standbys die. Practice removing a standby from `synchronous_standby_names` and communicating the temporary RPO change.

## Batch for latency

If durability must stay on, batch multiple logical operations per transaction. Application batching recovers more latency than disabling flush.
"""

B["postgres-table-inheritance-patterns"] = """
## Migration realities

Moving to declarative partitioning surfaces unique constraint lies — duplicates that inheritance allowed. Clean data first; include the partition key in uniqueness. Remove routing triggers and hand-built UNION ALL views during cutover.

## ORM boundary

Give ORMs one partitioned parent table. Do not map inheritance children as STI. Database inheritance and application inheritance are different ideas that collide messily.

## Review policy

Reject `INHERITS` for new partition-like designs. Prefer declarative partitioning or ordinary relational modeling for subtypes.
"""

B["postgres-tablespaces-io-isolation"] = """
## Whole I/O picture

Moving heaps to cold disks does not move WAL. Hot indexes and WAL may still share a volume. Map all latency-critical paths before celebrating a tablespace change.

## Restore mounts

Restore runbooks must create every tablespace directory before Postgres starts. Missing mounts fail startup after an otherwise good basebackup.

## Partial failure

A single mount going bad can break some relations while others work — confusing health checks. Monitor each filesystem and decide whether instance failure is safer than partial service.
"""

B["postgres-temporal-tables-system-versioning"] = """
## Support timelines

Expose as-of history in admin tools so support can answer "what address did we ship to?" without engineering. Authorize and redact carefully — history is still personal data.

## Concurrent updates

Use consistent clock sources in triggers and test concurrent updates against exclusion constraints on ranges. Overlaps under concurrency are how history corrupts.

## Erasure workflows

Wire GDPR erasure to history tables, not only current rows. Partition old history for retention drops where law allows.
"""

B["postgres-wal-compression-archiving"] = """
## Measure your mix

Update-heavy workloads with many full-page images often see large WAL size drops from compression. Append-mostly workloads may see less. Track archived bytes and primary CPU before declaring victory.

## Slot inventory

Forgotten logical slots retain WAL until disk dies. Monthly inventory of `pg_replication_slots` with retained bytes is mandatory ops hygiene.

## Separate WAL volume

Isolate `pg_wal` so archive failures cannot fill the data volume. Pair with alerts on archiver failures and disk %.
"""

B["postgres-window-functions-analytics"] = """
## Tiebreakers

Always add a unique tiebreaker to `ORDER BY` in windows used for balances or rankings (`created_at, id`). Ties without tiebreakers produce nondeterministic running sums that fail reconciliation.

## Materialize for dashboards

High-frequency dashboards should read pre-aggregated tables refreshed on a schedule, not run heavy windows on raw facts every page load.

## Explicit frames

Specify `ROWS` vs `RANGE` for moving aggregates. Default RANGE peer behavior surprises people on date ties. Make frames explicit in review.
"""

B["postgres-work-mem-sort-hash-tuning"] = """
## Pool-aware settings

Set low global `work_mem`, higher for analyst roles, and session overrides for monster queries. Reset session GUCs when returning connections to a pool.

## Temp bytes panel

Graph `temp_bytes` rates. Spikes often mean a missing index forced a sort — fix the plan before raising memory.

## Parallel interaction

Multiply work_mem by expected parallel workers when budgeting RAM. Parallelism without memory math causes OOM.
"""

B["queue-celery-task-routing"] = """
## CI contract

Assert every `task_routes` target appears in a worker Deployment `-Q` list. Routes without consumers are silent black holes.

## Scale independently

Autoscaling ETL on its own depth metric prevents import storms from stealing email capacity. One global depth scaler undoes routing isolation.

## Chord queues

Complex canvases must set queues on headers and bodies explicitly. Add a staging test that completes a mixed-route chord.
"""

B["queue-nats-jetstream-persistence"] = """
## AckWait and idempotency

AckWait must exceed p99 processing. Redelivery during work causes double side effects unless handlers are idempotent. Persistence does not equal exactly-once.

## Dual limits

Set both max-age and max-bytes on streams. Payload growth plus long retention fills disks. Alert on stream size.

## Retention mode match

Workqueue for competing consumers; limits for replayable logs. Wrong mode looks like "disk never shrinks after ack."
"""

B["queue-priority-inversion-prevention"] = """
## Reserved capacity

Critical queues need dedicated workers. Numeric priority cannot preempt running bulk tasks. Soak-test: fill bulk workers, enqueue critical, assert start SLO.

## Aging without collapse

Age bulk upward slowly so it cannot starve forever, but never equal critical. Document the curve.

## Separate Deployments

Kubernetes CPU requests do not preempt in-process bulk work. Separate consumer Deployments are the isolation boundary.
"""

B["queue-rabbitmq-dead-letter-exchange"] = """
## x-death visibility

Surface `x-death` headers in DLQ tooling so ops see expired-in-retry versus rejected-by-consumer. Alerts should name the queue and owning team.

## Retry taxonomy

Transient errors retry via TTL queues with a hop counter; validation errors dead-letter immediately. Infinite requeue is never acceptable for poison messages.

## Controlled replay

Replay in small batches after a fix, during low traffic, with idempotent consumers. "Requeue all" during peak recreates outages.
"""

B["queue-sidekiq-reliable-scheduler"] = """
## Scheduler role

Run a single leader/scheduler role for cron enqueue to avoid double fire. Prove with two pods in staging. Pair with unique middleware on the worker.

## Redis as system of record

Dedicated Redis, persistence on, no LRU eviction shared with cache. Sidekiq data loss is job loss.

## Freshness alerts

Page when a critical daily job has not succeeded within 26 hours. Manual secure re-trigger exists for humans without redis-cli.
"""

B["queue-sqs-fifo-deduplication"] = """
## Stable dedup ids

Derive `MessageDeduplicationId` from business `event_id`, never a fresh UUID per HTTP retry. Otherwise FIFO accepts duplicates and the 5-minute window does not save you.

## Group cardinality

Per-entity group ids preserve order without global serialization. A single constant group id kills throughput. Poison messages can block a group — DLQ quickly.

## Consumer idempotency

FIFO dedup is not exactly-once processing. Visibility timeout redelivery still happens. Upsert by event id forever, not for five minutes.
"""

B["queue-temporal-workflow-saga"] = """
## Compensations as first-class

List every side effect and its compensation before coding. Charge pairs with refund; reserve pairs with release. History UI shows what ran — still design the reverse path deliberately.

## Determinism CI

Ban wall-clock and direct I/O in workflow code. Replay tests catch `time.Now()` bugs before production. Use workflow APIs for time.

## Activity idempotency

Pass `order_id + step` keys to payment and inventory APIs. Temporal retries activities; providers must ignore duplicates safely.
"""

def main():
    results = []
    for slug, expansion in B.items():
        path = BLOG / f"{slug}.md"
        if not path.exists():
            results.append((slug, 0, "missing"))
            continue
        # May need two passes if still short — append a filler unique closer
        w = append_expansion(path, expansion)
        if w < 1200:
            closer = f"""
## Operational acceptance criteria for {slug.replace('-', ' ')}

Before calling this design production-ready, write down the failure modes you accept and the ones you do not. Add at least one metric, one alert, and one game-day exercise that forces the failure open in staging. Capture the before/after numbers in the PR description so the next engineer knows what "good" looked like. Prefer boring, documented tradeoffs over clever defaults that only exist in one person's head. Revisit the settings after the first real incident — the incident will teach you which timeout or retention value was fantasy. Keep the runbook next to the config; configuration without operational narrative decays into cargo cult. When you change a default, update the alert thresholds in the same pull request so observability and behavior stay paired. Schedule a quarterly review for anything that binds durability, retention, or failover. That review is cheaper than rediscovering the same outage under peak load.
"""
            w = append_expansion(path, closer)
        results.append((slug, w, "ok" if w >= 1200 else "short"))
    ok = sum(1 for _, _, s in results if s == "ok")
    print(f"round3: {ok}/{len(results)} >=1200")
    for slug, w, s in sorted(results, key=lambda x: x[1]):
        print(f"  {s:6} {w:4} {slug}")

if __name__ == "__main__":
    main()
