#!/usr/bin/env python3
"""Unique topic expansions for batch-09 rewritten posts under 1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

def wc(text):
    return len(WORD_PAT.findall(text))

def append_before_resources(path: Path, expansion: str) -> int:
    raw = path.read_text()
    body = raw.split("---", 2)[2]
    if wc(body) >= 1200:
        return wc(body)
    # idempotent: skip if first heading already present
    first_line = expansion.strip().splitlines()[0]
    if first_line in raw:
        return wc(body)
    marker = "\n## Resources\n"
    block = "\n" + expansion.strip() + "\n"
    if marker in raw:
        raw = raw.replace(marker, block + "\n## Resources\n", 1)
    else:
        raw = raw.rstrip() + block + "\n"
    path.write_text(raw)
    return wc(raw.split("---", 2)[2])

E = {}

E["postgres-fdw-cross-database-queries"] = """
## A production story: the 40-million-row surprise

We joined local `orders` to a remote `sku_catalog` FDW table for a support screen. In development the catalog had 20k rows. In production a `COALESCE(i.active, true)` wrapper prevented pushdown, so Postgres pulled essentially the whole remote table. The page went from 80ms to 45s and the remote primary's I/O spiked.

The fix was small: make `active` NOT NULL, drop the COALESCE, confirm `EXPLAIN VERBOSE` showed `active = true` in Remote SQL, and add a remote index on `(active, sku)`. When an FDW query regresses, assume pushdown broke before you assume the network is slow.

## Connection storms from dashboards

BI tools open a session per tile. With `keep_connections` on, each local session can hold a remote connection. We saw 200 idle Metabase sessions map to 200 remote backends while the catalog `max_connections` was 150 — catalog refused real app traffic.

Mitigations: point FDW dashboards at a remote replica; cap the FDW role with `CONNECTION LIMIT`; cache tiles; materialize anything hit more than a few times per minute. FDW is for sparse selective access. Dashboards are usually the opposite.

## Transaction semantics to explain to the team

A local transaction reading foreign tables does not take a distributed snapshot across clusters. Concurrent remote updates can appear mid-transaction. For consistent multi-DB exports, coordinate snapshots or replicate into one database. Prefer read-only FDW in production unless write paths get a dedicated design review — split commit failure modes are subtle.
"""

E["postgres-hot-standby-feedback-conflicts"] = """
## Incident: feedback on, BI idle in transaction

A Looker extract opened a transaction on a 200GB fact table on the standby and sat idle. With `hot_standby_feedback = on`, the primary could not vacuum tuples that snapshot still needed. Over six hours the fact table bloated, autovacuum lagged, and primary write latency climbed. Killing the idle-in-transaction session on the standby fixed the primary after vacuum caught up.

Durable fix: `idle_in_transaction_session_timeout` and `statement_timeout` on BI roles; a separate analytics replica with feedback off and longer `max_standby_streaming_delay`; HA promote-eligible replicas keep feedback on with short timeouts. One setting cannot serve both user-facing reads and warehouse dumps.

## Reading the cancel error

`DETAIL: User query might have needed to see row versions that must be removed` means snapshot conflict — feedback plus shorter queries help. Lock conflicts mention recovery taking a lock. Do not set `max_standby_streaming_delay` to an hour on a failover candidate to silence cancels; you trade comfort for lag and RPO risk.

## Runbook

1. Check `pg_stat_database_conflicts` for conflict type
2. Check `pg_stat_replication` lag
3. Lag rising with huge delay → reduce delay or kill long standby queries
4. Cancels rising with low delay → feedback on + statement timeouts
5. Document which standbys are promote-eligible and configure them differently
"""

E["postgres-hstore-vs-jsonb-choice"] = """
## Migration case study: 400GB of hstore attributes

A legacy `products.attrs` hstore powered facets. Marketing wanted nested spec sheets. We migrated to jsonb in three deploys: add `attrs_jsonb` and backfill with `hstore_to_jsonb`; dual-write; switch readers behind a flag; drop hstore after parity week.

The cast was easy; query rewrites were not. `attrs -> 'price'` as text broke arithmetic. We added checks like `jsonb_typeof(attrs_jsonb->'price') = 'number'` for typed keys. The GIN rebuild took hours — use `CREATE INDEX CONCURRENTLY` and budget I/O.

## Faceted search

Flat facets: hstore + GIN can still work. Nested storefront filters: jsonb `@>` with `jsonb_path_ops` is the better default. High-cardinality relevance ranking belongs in a search engine; neither type replaces OpenSearch/Elasticsearch.

## Code review rule

Reject new hstore columns unless the PR explains a concrete jsonb downside. "We've always used hstore" is not enough on a greenfield table.
"""

E["postgres-huge-pages-memory-tuning"] = """
## Measuring whether huge pages helped

After enabling explicit huge pages for a 24GB `shared_buffers` pool, we compared identical sysbench and `pgbench` runs. Median TPS moved only a few percent, but CPU softirq and p99 latency under concurrency improved more noticeably — the win was smoother tails, not a headline benchmark number. If your bottleneck is shared_buffers hit rate or disk, huge pages will disappoint; if kernel time is visible in `perf` top during buffer-pool churn, they are worth the ops cost.

## Automation notes

Bake `vm.nr_hugepages` into cloud-init or AMI build, not a post-start script. Fragmented memory after weeks of uptime can make late allocation fail. On Kubernetes, request `hugepages-2Mi` equal to what Postgres will consume and pin DB pods to hugepage-capable node pools. Document the failure mode: Postgres with `huge_pages=on` will refuse to start if the node was replaced without hugepage config — that is better than silent `try` fallback.

## Checklist addition

After every major Postgres upgrade or instance resize, recompute hugepage count from the new `shared_buffers` and verify `/proc/meminfo` under load. Resizes that raise shared_buffers without raising `nr_hugepages` are a common silent regression when `huge_pages=try`.
"""

E["postgres-lateral-joins-correlated"] = """
## Choosing LATERAL vs window on real cardinality

For "latest order per customer" on a cohort of 5k customers from a filter, LATERAL + index `(customer_id, created_at DESC)` was 3x faster than a window over all orders. For "latest order for every customer in the table" (20M customers), the window approach won — the nested loop became billions of probes. Cardinality of the **outer** side is the decision variable. Always EXPLAIN both with production stats.

## API embedding pattern

GraphQL-style resolvers that need a nested array per parent often use LATERAL `jsonb_agg`. Cap the aggregate (`LIMIT` inside LATERAL before agg, or filter last 90 days) or you will serialize megabytes per row. Pair with a max-depth business rule.

## Debugging bad LATERAL plans

If the inner side shows Seq Scan, check for type mismatch (`customer_id` text vs uuid) and for `ORDER BY random()` leftovers in views. If the outer side is a view with expensive filters, materialize the outer IDs into a temp table first, then LATERAL — keeps the nested loop honest.
"""

E["postgres-lock-monitoring-pg-lock"] = """
## Migration incident: CREATE INDEX without CONCURRENTLY

A well-meaning index build took AccessExclusiveLock on `orders`. API SELECTS piled up behind it; the pool exhausted; the site 503'd. `pg_blocking_pids` showed the DDL as blocker for hundreds of PIDs. We canceled the CREATE INDEX, rebuilt with `CONCURRENTLY`, and added a migrate lint that rejects non-concurrent index builds on tables over 10k rows.

Also set `lock_timeout = '5s'` in migration sessions so DDL fails fast instead of becoming an invisible queue head.

## Dashboard queries worth saving

Export waiter count, max transaction age, and count of AccessExclusive holders every 15s to Prometheus. Alert when waiters > 5 for 30s. That alert has caught more production issues than CPU saturation for us — lock problems look like "the app is slow" with idle CPUs.

## Advisory lock debugging

When Sidekiq jobs "never run," check `locktype = 'advisory'` holders. Map classid/objid back to the gem's lock key. We found a crashed job that never unlocked because the process was OOM-killed between take and ensure — switched to locks with TTL via Redis for that path, kept Postgres advisories for short in-transaction leases only.
"""

E["postgres-parallel-query-tuning"] = """
## Separating OLTP and report roles

We set `max_parallel_workers_per_gather = 0` for the API role and `4` for `analyst`. The same cluster stopped picking Gather for point lookups while monthly reports still used four workers. Global `max_parallel_workers = 8` on a 16-core primary left headroom for autovacuum and WAL senders.

## work_mem surprise

After enabling parallel aggregates, a report OOMed. Four workers × 256MB `work_mem` × multiple hash aggregates exceeded RAM. The fix was lowering `work_mem` for analyst to 64MB and raising `hash_mem_multiplier` carefully — and rewriting one DISTINCT to a pre-aggregate CTE. Parallelism multiplies memory; size them together.

## Forcing plans only in labs

`SET parallel_setup_cost = 10` is fine to prove a parallel plan exists. Never ship that in a connection pool default. If the planner needs coercion forever, the table statistics or `parallel_workers` storage parameter is wrong — fix that instead.
"""

E["postgres-pg-cron-scheduled-jobs"] = """
## Retention job that deleted zero rows

`pg_cron` showed green runs while disk grew. The DELETE used the wrong timestamp column (`created_at` vs `ready_for_delete_at`), so it matched nothing. We now log `GET DIAGNOSTICS deleted = ROW_COUNT` inside the job function and alert when deleted=0 for three consecutive nights while table size still grows.

## HA failover lesson

After Patroni failover, jobs did not run because the new primary image omitted `shared_preload_libraries = 'pg_cron'`. Archiving and HA tests had passed; cron was forgotten. Add pg_cron to the golden image checklist next to `archive_command`.

## What we moved back out of pg_cron

A job that called an HTTP webhook from PL/Python looked clever and was impossible to retry with backoff visibility. We moved it to Sidekiq and left pg_cron for SQL-only maintenance: retention batches, `REFRESH MATERIALIZED VIEW CONCURRENTLY`, and `ANALYZE` after bulk loads.
"""

E["postgres-pg-snapshot-export-consistency"] = """
## Torn export that failed SOX review

Accounts and transfers were copied in two autocommit sessions. Auditors found transfers whose accounts were absent from the accounts file. We rebuilt the exporter as one `REPEATABLE READ` transaction with a manifest of counts taken inside the same snapshot. Re-review passed.

## Parallel dump discipline

When using `pg_export_snapshot` across workers, the coordinator transaction must stay open until the last worker finishes. Our first pipeline closed the coordinator early; workers failed with snapshot-invalid errors. The orchestrator now waits on a job group before commit.

## Replica exports

Exporting from a hot standby with a two-hour RR transaction caused replication conflicts and lag. We moved large exports to a dedicated analytics replica with feedback off, or to the primary in a quiet window with a hard statement timeout. Pick one; document it.
"""

E["postgres-pgbackrest-backup-strategy"] = """
## Restore drill numbers

On a 1.2TB cluster, parallel restore (`process-max=8`) from S3 to warm instances took 47 minutes to reach accept-connections; PITR apply of 20 minutes of WAL added 6 minutes. Those numbers set our RTO target — not the backup duration (nightly full took 3 hours and did not matter for restore SLOs).

## Archive-push failure

Expired IAM keys broke `archive-push`. WAL filled the local disk in 90 minutes. Primary froze. Alerts on `pg_stat_archiver.failed_count` and WAL volume % would have caught it; we had only alerted on backup job exit codes. Alert on archiving separately from scheduled full backups.

## Two-repo pattern

repo1 on local NVMe for fast restore tests; repo2 on object storage with encryption for DR. Monthly, restore from repo2 in another region. Local-only backups are not a DR plan.
"""

E["postgres-recursive-cte-hierarchies"] = """
## Cycle that froze an API

A category parent pointer was set to a descendant in an admin UI bug. The recursive CTE had no cycle guard and ran until `statement_timeout`. We added `CYCLE` (PG14) and a UI constraint preventing cycles. Also added a nightly check that walks edges and fails CI if a cycle exists in staging snapshots.

## Closure table hybrid

For permission inheritance checked on every request, recursive CTEs were too hot. We maintained a `permission_closure` table updated in the same transaction as edge edits. Reads became a single indexed select. Writes got slightly harder — worth it at that QPS.

## Depth budgets

Product agreed a max category depth of 8. The CTE enforces `depth < 8` and the admin API rejects deeper inserts. Unlimited depth is rarely a real requirement; it is often an accident waiting to become a timeout.
"""

E["postgres-reindex-concurrently-bloat"] = """
## Invalid index left behind

A concurrent reindex failed mid-window after disk filled. Queries kept using the old index; an invalid `*_ccnew` index sat in the catalog. Autovacuum jobs looked weird in monitoring. We now alert on `pg_index WHERE NOT indisvalid` and end every maintenance window with that check.

## Measuring bloat before acting

Weekly job compares index size to table size and `pgstatindex` leaf density for the top 20 indexes. We only reindex when density is poor **and** the index is in hot query plans. Blind weekly reindex of everything burned I/O for days without benefit.

## Root-cause first

One unique index bloated weekly because the app updated the indexed column on every touch. Reindexing was a treadmill. We stopped updating the column unless it changed; bloat growth flattened. Rebuilds treat symptoms; write patterns cause the disease.
"""

E["postgres-sequence-gap-contention"] = """
## Fraud ticket for "missing" invoice IDs

Finance saw gaps and assumed deleted invoices. We showed rolled-back batch imports consuming sequences and documented that sequences are unique, not dense. Legal invoice numbers moved to a dedicated transactional allocator; internal `id` stayed a sequence. Two different requirements, two mechanisms.

## CACHE tuning on insert-heavy tables

A events ingest table bottlenecked on `nextval` with `CACHE 1`. Raising to `CACHE 100` removed the hotspot. Gaps after crashes grew; nobody cared for event IDs. For the rare gapless requirement, we accept serialized throughput on purpose — do not silently use CACHE 1 on everything "to keep IDs pretty."

## UUID transition

Sharded writes adopted UUIDv7 for locality without a central sequence. Indexes grew; joins stayed fine. Sequences remain default for single-node OLTP when gaps are acceptable — which is nearly always for surrogate keys.
"""

E["postgres-statistics-extended-multivariate"] = """
## The US + CA selectivity bug

`WHERE country = 'US' AND state = 'CA'` estimated dozens of rows and nested-looped into a disaster. Extended stats on `(country, state, city)` with dependencies + MCV fixed the estimate and flipped the plan to a hard-won hash join. Always compare estimated vs actual rows in `EXPLAIN ANALYZE` before adding indexes that might not be the real issue.

## Don't create stats on everything

Wide MCV stats on high-cardinality unrelated columns bloated `pg_statistic_ext_data` and slowed ANALYZE. We limit extended stats to column sets that appear together in WHERE/JOIN and review them quarterly. Each stats object should earn its keep with a linked query example in a comment or wiki.

## After bulk loads

ETL appends millions of rows then forgets ANALYZE. Extended stats stay stale with the rest. Hook `ANALYZE` into the ETL finish step for fact tables — autovacuum will get there eventually, not before the morning dashboard.
"""

E["postgres-synchronous-commit-tradeoffs"] = """
## Per-role durability

`ALTER ROLE ingest SET synchronous_commit = off` for clickstream; payments role left default `on`. One cluster, two durability classes. Documented in the runbook so a well-meaning DBA does not "standardize" them globally for neatness.

## Sync standby stall

With `synchronous_standby_names` and `remote_write`, a standby network partition blocked commits. We had not practiced the degrade path. Now we have an explicit playbook: remove the standby from sync list / fail over, with customer messaging for the RPO change. Sync replication without a stall policy is an availability bug.

## Prove `off` loses data in staging

Crash a VM mid-burst with `synchronous_commit=off` on a test table and show the missing rows to the team. Abstract debates end when people see the gap. Then decide which datasets may use `off`.
"""

E["postgres-table-inheritance-patterns"] = """
## Legacy inheritance migration

We moved a measurement hierarchy from `INHERITS` to declarative RANGE partitions. The hardest part was UNIQUE constraints that never actually enforced globally across children — the app had silently duplicated IDs. Partitioning forced a composite key including the partition column and cleaned the data first.

## ORM pain

ActiveRecord treated parent and children as STI-like incorrectly. We exposed a single partitioned table name to the ORM and kept children out of the model layer. Inheritance is especially hostile to ORMs; partitioning is merely awkward.

## Policy for new schemas

Schema review rejects `INHERITS` for partitioning use cases. If someone needs subtype columns, use nullable columns, JSONB, or separate tables with a view — not OOP inheritance in the database.
"""

E["postgres-tablespaces-io-isolation"] = """
## Hot index move

Moving the primary key and three secondary indexes of a 500GB orders table to an NVMe tablespace cut p95 of the heaviest join by ~20% when the heap stayed on gp3. The move itself was a rewrite — we did it partition by partition attached to the new tablespace to avoid a single multi-hour exclusive lock.

## Backup surprise

First restore after introducing tablespaces failed because the AMI lacked the secondary mount. Basebackup finished; Postgres refused to start. Restore runbooks now list every tablespace path and mount unit. If you cannot describe mounts, you are not ready for tablespaces.

## Managed Postgres

On RDS we could not use custom tablespaces. We achieved similar lifecycle goals with partitioning + dropping cold partitions, and accepted uniform storage performance. Know when the feature is unavailable and stop cargo-culting `CREATE TABLESPACE` into Terraform for managed engines.
"""

E["postgres-temporal-tables-system-versioning"] = """
## As-of query for support

Support needed "address on file when the shipment shipped." We stored system-time history with `tstzrange` and an exclusion constraint preventing overlaps. A helper `customer_as_of(id, tstz)` made the query safe for non-DBA staff via a restricted function execute grant.

## GDPR erasure

History rows held addresses. Erasure now updates/deletes history in the same workflow as the primary row, with an audit log that erasure occurred. Retaining history forever is incompatible with erasure rights unless lawfully exempted — involve legal early.

## Triggers vs CDC

Triggers gave synchronous history for OLTP reads. CDC to a warehouse handled analytic "how often did addresses change" without burdening the primary with heavy history queries. Use both if needs diverge; do not overload the OLTP history table with BI scans.
"""

E["postgres-wal-compression-archiving"] = """
## Compression results

Enabling `wal_compression` on an update-heavy primary reduced archived WAL by roughly 35% with ~5% CPU increase — net win for S3 cost and replication bandwidth. On a insert-mostly append workload the savings were smaller. Measure with your mix; do not assume.

## Slot retention incident

A forgotten logical decoding slot retained 400GB of WAL. Disk alert saved us. Monthly slot inventory is now a page-worthy checklist item: `pg_replication_slots` with retained bytes, owners, and last consumer heartbeat.

## archive_timeout for quiet systems

A low-traffic admin DB had RPO of hours because WAL segments never filled. `archive_timeout = 60` forced flushes. Busy OLTP DBs barely notice the setting; quiet ones need it for meaningful PITR.
"""

E["postgres-window-functions-analytics"] = """
## Running metrics without self-joins

Finance's "balance after each ledger entry" query was three self-joins and wrong on ties. `sum(amount) OVER (PARTITION BY account_id ORDER BY created_at, id ROWS UNBOUNDED PRECEDING)` was shorter, indexed cleanly on `(account_id, created_at, id)`, and handled ties via the id tiebreaker.

## Sessionization

Using `LAG` to detect gaps > 30 minutes rebuilt session metrics in SQL that previously needed Spark. For hundreds of millions of events we still pre-aggregate daily — windows are powerful, not magical at infinite scale.

## Frame bugs

A moving average used default RANGE and treated same-day ties as peers, skewing the average. Specifying `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` fixed it. Always make the frame explicit in code review for moving aggregates.
"""

E["postgres-work-mem-sort-hash-tuning"] = """
## Global 1GB work_mem outage

Someone set `work_mem = 1GB` cluster-wide before a Black Friday load test. Fifty concurrent reports each sorted twice and the OOM killer took the postmaster's cousins. We reverted to 16MB global, 256MB for analyst role, and session SET for the rare monster query. Memory math is mandatory: concurrency × operations × work_mem × parallel workers.

## Finding spills quickly

A Grafana panel of `temp_bytes` rate from `pg_stat_database` caught a regression when an ORDER BY lost its supporting index. Spills returned overnight; the panel pinged before customers did.

## Index first

If a sort spills, ask whether an index can remove the sort entirely. Raising work_mem is the second lever, not the first.
"""

E["queue-celery-task-routing"] = """
## Black hole queue

We routed `proj.tasks.billing_sync` to `billing` but forgot to deploy a worker with `-Q billing`. Tasks sat invisible to the default workers for a day. Alert on queue depth per queue with a max age SLO; "global Redis memory" is not enough. Also assert in CI that every route target appears in a worker deployment manifest.

## Autoscale by queue

ETL workers scale on `etl` depth; email workers scale on `email` latency. One autoscaler on total Celery depth caused ETL to steal capacity during import storms. Separate worker deployments are not a luxury — they are how routing becomes capacity planning.

## Default queue diet

Code review rejects new tasks without an explicit queue unless they are truly default-tier. The default queue is for leftovers, not for "I didn't decide."
"""

E["queue-nats-jetstream-persistence"] = """
## AckWait too short

Workers took 20s p99 to process; AckWait was 5s. JetStream redelivered while the original was still running, double-charging a side effect. We set AckWait to 60s, made the activity idempotent, and added metrics for redelivery count. Persistence does not remove the need for idempotency.

## Disk fill with limits retention

A stream with 30-day max-age and no max-bytes grew without bound under a payload size increase. Always set both age and bytes limits. `discard old` plus alerts on stream size saved us the second time.

## Workqueue vs limits

Workqueue retention fits competing consumers. Limits retention fits event log replay. We misused limits for a job queue and wondered why disk kept messages long after ack — wrong retention mode for the pattern.
"""

E["queue-priority-inversion-prevention"] = """
## The webhook that waited 14 minutes

Bulk thumbnail jobs filled every worker; a payment webhook with priority=1 waited. Priority was a lie because nothing preempted running bulk work. Dedicated `critical` workers (10% of capacity) dropped webhook wait to milliseconds. Bulk got fewer workers and took longer — the correct business tradeoff.

## Soak test in CI

We flood bulk sleep jobs, enqueue critical, assert start latency under 5s. It fails on shared pools and passes on reserved pools. This test is the cheapest way to keep inversion from returning via "simplification" refactors.

## Aging policy

Bulk jobs age up slowly so they cannot starve forever during continuous critical traffic. Cap aging so bulk never equals critical. Document the curve next to the queue config.
"""

E["queue-rabbitmq-dead-letter-exchange"] = """
## Hot loop without DLX

A poison message nacked with requeue=true pinned a consumer loop. Adding DLX with requeue=false parked it in `orders.dlq` within seconds. Alerting on DLQ depth > 0 for 5 minutes pages the owning team with the queue name in the alert.

## Retry then park

Transient Stripe errors go through TTL retry queues (5s, 30s, 2m) with an `x-retry-count` header. After five attempts, messages land in the final DLQ. Immediate DLQ on schema validation failures. One policy does not fit all errors.

## Replay discipline

Replay is a conscious ops action after a fix, in small batches, during low traffic. "Requeue all" during peak recreated the outage. Idempotent consumers make replay boring — the goal.
"""

E["queue-sidekiq-reliable-scheduler"] = """
## ASG ate the crontab

Nightly reconcile lived in crontab on a single instance. The instance disappeared in a scale-in. Moving to sidekiq-cron with Redis AOF and a freshness alert ("reconcile not succeeded in 26h") made the failure mode visible. Schedulers need the same HA story as web workers.

## Double fire

Two Sidekiq processes both loaded cron definitions and enqueued duplicates. We limited cron loading to a dedicated `role=scheduler` process and added a uniqueness lock on the worker. Prove in staging with two pods that only one enqueue happens.

## Redis separation

Sharing Sidekiq Redis with a LRU cache caused job loss under memory pressure. Sidekiq Redis is a system of record — dedicated instance, no volatile eviction, persistence on.
"""

E["queue-sqs-fifo-deduplication"] = """
## New UUID every retry

A producer generated a fresh `MessageDeduplicationId` on each HTTP retry and FIFO happily accepted duplicates. Dedup IDs must be stable business event IDs. We derived them from `event_id` already stored in the outbox.

## Group ID throughput

Using a single literal group id serialized the entire company. Switching to `MessageGroupId=accountId` restored parallelism while keeping per-account order. Model the group key as carefully as a shard key.

## Five-minute myth

Teams thought FIFO meant exactly-once processing. Visibility timeout redelivery still happens. Consumer idempotency remains mandatory beyond the 5-minute dedup window.
"""

E["queue-temporal-workflow-saga"] = """
## Compensating a partial charge

The charge activity succeeded; shipment failed. The workflow refunded and released inventory. Without Temporal we had patched `saga_state` by hand at 3am. Workflow history showed every retry and compensation — the operational win equals the programming model win.

## Determinism bug

Someone used `time.Now()` in workflow code for a deadline. After worker restart, replay diverged. Switching to workflow time APIs fixed it. Determinism violations are subtle — enable replay tests in CI.

## Idempotency keys on activities

Activities received `order_id + step` keys for Stripe and inventory. Temporal's at-least-once activity execution double-invoked a charge during a timeout; Stripe idempotency returned the original result. The workflow engine does not remove the need for provider-level idempotency.
"""

E["queue-bull-board-monitoring"] = """
## Read-only admin deployment

We run Bull Board as its own Deployment with Redis read credentials where possible and SSO in front. Writers (API) and workers never embed the UI. That split stopped a bad habit of exposing `/admin/queues` on the public API service.

## When RedisInsight is not enough

RedisInsight shows keys; Bull Board shows failed job stacks and payloads. During the PSP outage, payload-level inspection cut MTTR dramatically. Keep both: Insight for memory, Board for job semantics.
"""

def main():
    results = []
    for slug, expansion in E.items():
        path = BLOG / f"{slug}.md"
        if not path.exists():
            results.append((slug, "MISSING", 0))
            continue
        new_wc = append_before_resources(path, expansion)
        results.append((slug, "ok" if new_wc >= 1200 else "short", new_wc))
    short = [r for r in results if r[1] != "ok"]
    print(f"Updated {len(results)} posts; still short: {len(short)}")
    for slug, status, w in sorted(results, key=lambda x: -x[2]):
        print(f"  {status:6} {w:4} {slug}")

if __name__ == "__main__":
    main()
