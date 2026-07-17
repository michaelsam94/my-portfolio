#!/usr/bin/env python3
"""Second unique expansion pass for batch-09 posts still under 1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

def wc(t): return len(WORD_PAT.findall(t))

def append(path: Path, expansion: str) -> int:
    raw = path.read_text()
    body = raw.split("---", 2)[2]
    if wc(body) >= 1200:
        return wc(body)
    key = expansion.strip().splitlines()[0]
    if key in raw:
        return wc(body)
    marker = "\n## Resources\n"
    block = "\n" + expansion.strip() + "\n"
    raw = raw.replace(marker, block + "\n## Resources\n", 1) if marker in raw else raw.rstrip() + block + "\n"
    path.write_text(raw)
    return wc(raw.split("---", 2)[2])

# Large unique blocks (~450-700 words each) keyed by slug
R2 = {}

R2["postgres-fdw-cross-database-queries"] = """
## Indexing and statistics on both sides

Remote indexes only help if the planner pushes the predicate. After fixing pushdown, run `ANALYZE` on the foreign table with `use_remote_estimate` so join order is not a guess. Local `orders` needed its usual indexes; remote `sku` needed `(active, sku)` and a covering include for the columns we select. FDW does not invent indexes — you still design them twice.

When remote estimates are wrong, the local planner may choose a nested loop that executes thousands of remote round trips. Force a materialization of the remote side into a temp table for the rare reporting query if join order stays pathological — ugly, explicit, and sometimes faster than fighting the FDW planner for an hour.

## Security review items

Store user mappings in a secrets manager and rotate the remote password. Prefer SCRAM. Never create a mapping for `PUBLIC`. Grant the remote role `SELECT` on specific tables only — not `SELECT` on schema public. If the remote DB has RLS, test as the mapped user; FDW does not bypass RLS.

Audit who can `CREATE USER MAPPING` — it is a privilege escalation path to whatever the remote role can read.
"""

R2["postgres-hot-standby-feedback-conflicts"] = """
## Application retry strategy

Drivers should retry conflict-with-recovery errors with jittered backoff a few times. Frameworks that treat all `OperationalError` as fatal will surface flaps to users during ordinary vacuum on the primary. Distinguish conflict cancels from unique violations in the data access layer.

For read-your-writes after a write to the primary, do not read from the standby until lag is within budget — feedback and delay settings do not create causal consistency. Use primary reads for that path or session-sticky causal tokens.

## Capacity planning

If cancel rates are high even with feedback and 30s delay, the workload does not belong on an HA standby. Budget a third node class: promote-eligible (strict), app-read (feedback on, timeouts), analytics (lag OK). Three configs beat one compromise config.
"""

R2["postgres-hstore-vs-jsonb-choice"] = """
## Operator cheat sheet we keep in the wiki

hstore `?` / `?&` / `?|` map cleanly to jsonb. hstore `->` returns text; jsonb `->` returns jsonb and `->>` returns text — this is the #1 porting bug. Containment `@>` is jsonb-only and is why GIN shines for document queries. Slice updates with `||` work on both for flat keys; nested jsonb patches need `jsonb_set`.

## When to extract columns

If a jsonb/hstore key is in every WHERE clause, promote it to a real column with a default and backfill. Semi-structured storage is for semi-structured access. The hybrid model — typed columns for hot paths, jsonb for the long tail — beats a single infinite document every time we have measured it.
"""

R2["postgres-huge-pages-memory-tuning"] = """
## Interaction with cgroups and containers

If Postgres runs in a cgroup with a memory limit, huge pages still count against the limit. Set the container memory request/limit above `shared_buffers + huge page overhead + connection memory + OS`. Under-limit OOM kills look mysterious when `free` on the node shows available RAM outside the cgroup.

## THP compaction latency

We saw multi-millisecond stalls with THP `always`. Setting THP to `madvise` and relying on explicit huge pages for shared_buffers removed those stalls. Track `compact_stall` in vmstat when chasing unexplained p99 spikes on DB hosts.
"""

R2["postgres-lateral-joins-correlated"] = """
## DISTINCT ON vs LATERAL for top-1

For a single latest row, `DISTINCT ON (customer_id)` with matching `ORDER BY` is often clearer and just as fast. LATERAL wins when you need top-N (N>1) or multiple columns from a complex inner query with its own filters. Prefer the boring tool when N=1.

## Parameterized depth

Expose `limit_n` as a query parameter capped at 20 in the API so LATERAL cannot be abused into `LIMIT 100000`. Windows can be abused too — caps belong at the API boundary either way.
"""

R2["postgres-lock-monitoring-pg-lock"] = """
## Autovacuum vs user queries

Autovacuum takes mild locks that still show up in wait graphs. Do not terminate autovacuum casually during an incident unless you know it is stuck on a wraparound emergency path — usually the blocker is a human transaction. Check `xact_start` age first.

## Prepared statements and lock confusion

A session sitting `idle in transaction` after a failed migration still holds locks. ORMs that leave transactions open on exceptions are frequent offenders. Combine lock monitoring with exception-path audits in the app.
"""

R2["postgres-parallel-query-tuning"] = """
## Parallel index scans

Parallel index scans help some range queries but less often than parallel seq scans on unindexed analytics filters. If EXPLAIN never shows Parallel Index Scan, that may be fine — focus on the big sequential readers. Use `min_parallel_index_scan_size` deliberately so tiny index lookups stay serial.

## Maintenance windows

Temporarily raise `max_parallel_maintenance_workers` during CREATE INDEX weekends, then put it back. Leaving it high forever lets a surprise REINDEX steal workers from query parallelism during business hours.
"""

R2["postgres-pg-cron-scheduled-jobs"] = """
## Batched delete pattern details

Delete in `LIMIT` chunks inside a loop in a PL/pgSQL function, `COMMIT` between batches if you use procedures with transaction control, or schedule every five minutes with a single batch per invocation. Long single-transaction deletes bloat and hold locks. Aim for batches that finish in seconds.

## Observability table

Copy job run details into a long-retention history table if your pg_cron version rotates `job_run_details` aggressively. Ops needs weeks of history for "did retention run during the incident?" questions.
"""

R2["postgres-pg-snapshot-export-consistency"] = """
## COPY options for safer files

Use `CSV HEADER`, explicit column lists (never `SELECT *` for contractual exports), and force encoding UTF8. Compress outside the transaction when possible — `COPY TO PROGRAM 'gzip > ...'` holds the snapshot while gzip runs. Prefer `COPY TO STDOUT` streamed by a client that compresses as it reads.

## Clock and time zones

Timestamp predicates in exports should use timestamptz boundaries. A `date` filter in a local zone has caused off-by-one-day audit files more than once.
"""

R2["postgres-pgbackrest-backup-strategy"] = """
## Encryption and key custody

repo cipher pass lives in a secret manager; access is audited. Losing the key loses the backups — escrow the key material with the same seriousness as disk encryption keys. Test restore including key retrieval, not only `pgbackrest restore` with a pre-exported env var.

## After major version upgrade

Take a fresh full backup immediately after `pg_upgrade`. Old backup chains may not restore cleanly across major versions depending on tooling. Update stanza checks in CI against the new binaries.
"""

R2["postgres-recursive-cte-hierarchies"] = """
## Graphviz for debugging

Export parent/child edges to Graphviz when a hierarchy bug is reported. Humans find cycles faster in a picture than in a recursive result set. Ship a small admin-only endpoint that returns the DOT file for a subtree.

## Pagination of trees

Do not return entire trees to mobile clients. Return one level + children counts, or a materialized path breadcrumb. Recursive CTEs belong behind carefully bounded APIs.
"""

R2["postgres-reindex-concurrently-bloat"] = """
## Concurrent reindex and replicas

The extra I/O from reindex hits replication too. Schedule on the primary during low traffic; watch apply lag. On large indexes, consider reindexing on a promoted clone and switching — usually more complex than concurrent reindex, reserved for pathological cases.

## When to use pg_repack instead

If the heap is bloated too, `pg_repack` rewrites table and indexes online. It is another extension to operate. We use it when `VACUUM FULL` is unacceptable and reindex alone cannot reclaim enough disk.
"""

R2["postgres-sequence-gap-contention"] = """
## `ON CONFLICT` and burned IDs

`INSERT ... ON CONFLICT DO NOTHING` still consumes a sequence value for the attempted insert in many patterns. Bulk upserts can burn millions of IDs. Harmless for bigint; surprising for people watching sequences. Document it next to the upsert helper.

## Multi-database ID spaces

If you merge databases, colliding serials hurt. Prefer UUIDs or allocated ranges per shard when a merge is foreseeable. Sequences are local by nature.
"""

R2["postgres-statistics-extended-multivariate"] = """
## Join selectivity

Correlated join keys (`customer_id` pairs with skewed `region`) also benefit from extended stats. Bad join estimates cause nested loops over millions of rows — the same class of bug as filter selectivity. Include join column sets in your stats review when EXPLAIN join rows are fiction.

## Tracking plan flips

After creating stats, save EXPLAIN plans for the top five queries in the PR. If a plan flips negative (rare but possible), drop or narrow the stats object. Treat extended stats like indexes: measured, not hoped.
"""

R2["postgres-synchronous-commit-tradeoffs"] = """
## Disk flush reality

On cloud disks with weak fsync behavior, `synchronous_commit=on` still only as durable as the hypervisor promises. Know your volume's power-loss guarantees. Some teams pair sync commit with sync replication because local flush alone is not enough under their threat model.

## Batching to regain latency

If sync commit is required, batch work: one transaction per 100 events beats 100 sync commits. Application batching recovers more latency than turning durability off.
"""

R2["postgres-table-inheritance-patterns"] = """
## Trigger routing leftovers

Legacy designs used `BEFORE INSERT` on the parent to redirect to children. Those triggers fight declarative partitioning. Kill them during migration. Also kill views that `UNION ALL` children manually — the partitioned parent already does that.

## Documentation debt

If inheritance remains, put a WARNING at the top of the schema README: uniques are per-child, FKs are weird, prefer partition attach for new chunks. Future you will thank present you.
"""

R2["postgres-tablespaces-io-isolation"] = """
## WAL and tablespaces

WAL stays in `pg_wal` regardless of tablespaces. Putting heaps on cold storage does not move WAL. If WAL and hot indexes share a disk while heaps are elsewhere, you still need that disk to be fast. Map the whole I/O picture before celebrating a tablespace move.

## Filesystem failure domains

A tablespace mount going read-only takes down relations on it while other tables might still work — partial outages confuse health checks. Monitor each mount; fail the instance if any required tablespace is unhealthy if your app cannot degrade gracefully.
"""

R2["postgres-temporal-tables-system-versioning"] = """
## UI for history

Expose a simple timeline in admin: who changed what field when. Built on history tables, it reduces "can you check the logs" tickets. Redact sensitive fields in the UI even if history stores them — authorization still applies.

## Clock skew

`valid_from` should use `clock_timestamp()` or transaction timestamps consistently. Mixing `now()` in different contexts across triggers can create overlapping ranges that violate exclusion constraints under concurrency. Test concurrent updates hard.
"""

R2["postgres-wal-compression-archiving"] = """
## Replication and compression

Standbys receive compressed WAL records and decompress as needed — CPU appears on both sides. During catch-up after a standby outage, compression reduces network time-to-catch-up, which often matters more than the CPU tax. Watch catch-up duration before/after enabling.

## Separating WAL volume

Put `pg_wal` on its own volume so archive lag cannot fill the data volume. This single isolation has prevented more full-disk outages than compression alone.
"""

R2["postgres-window-functions-analytics"] = """
## FILTER clause

`count(*) FILTER (WHERE status = 'ok') OVER (PARTITION BY day)` keeps window queries readable without nested CASE forests. Combine with FILTER aggregates in the same SELECT carefully — readability beats cleverness.

## Materialized windows

For dashboards hit every few seconds, materialize daily window results into a summary table refreshed by pg_cron. Fresh enough, cheap forever. Not every window query should run against raw facts.
"""

R2["postgres-work-mem-sort-hash-tuning"] = """
## Per-query budgets in the app

The analytics service sets `work_mem` on checkout of a connection from the pool based on query class tags. OLTP pool never raises it. This pattern beats a single compromised global default. Reset on connection return if the pool reuses sessions.

## Hash batching

EXPLAIN showing many hash batches means work_mem is low for that hash join. Sometimes a better join order removes the hash entirely — check both levers.
"""

R2["queue-celery-task-routing"] = """
## Chord and routing

Chords and groups inherit queues carefully — a chord header landing on the wrong queue has caused silent stalls. Explicitly set queues on headers and bodies in complex canvases. Add a staging test that waits for a chord of mixed routed tasks to complete.

## Flower vs Prometheus

Flower is fine for humans; Prometheus metrics per queue drive alerts. Export depth, acknowledgment rate, and worker count per queue name. Routing without per-queue telemetry is flying blind.
"""

R2["queue-nats-jetstream-persistence"] = """
## Multi-replica streams

`replicas: 3` on a three-node NATS cluster survived a node loss without message loss in our game day. Quorum loss (two nodes down) pauses durability — know the difference between R3 and magic. Document the failure domain for the platform team.

## Subject design

`orders.> ` is easy; high cardinality subjects with unique IDs can create management pain. Prefer subjects by type and put IDs in payloads, using filters on consumers for interest. Stream design reviews should include subject taxonomy.
"""

R2["queue-priority-inversion-prevention"] = """
## Kubernetes fair sharing is not enough

Cluster autoscaling does not fix a Deployment where one pod type runs both critical and bulk consumers. Separate Deployments with separate thread pools. Resource requests prevent noisy neighbors at the CPU layer; they do not preempt a bulk job already running in-process.

## Product language

Teach PMs that "high priority" means reserved capacity, not a label. Capacity reservations have cost — make that explicit when prioritizing features that generate bulk work.
"""

R2["queue-rabbitmq-dead-letter-exchange"] = """
## Header preservation

On dead-letter, RabbitMQ adds `x-death` headers describing why and whence. Surface `x-death` in the DLQ inspector UI so ops see "expired in retry.5s" vs "rejected by consumer." Parsing `x-death` in alert payloads speeds triage.

## Quorum queue + TTL

Test TTL retry topologies on quorum queues in your exact RabbitMQ version — behaviors have evolved. Staging proof beats blog posts.
"""

R2["queue-sidekiq-reliable-scheduler"] = """
## Daylight saving and cron

Cron in Sidekiq uses a timezone — UTC everywhere avoids DST double-runs or skips. Document UTC in the schedule file. A billing job that double-ran on DST spring-forward was an expensive lesson.

## Manual trigger

Provide a secure admin button to enqueue `ReconcileWorker` with the same args as cron. When a run fails, humans should not SSH to redis-cli. Audit log the manual trigger.
"""

R2["queue-sqs-fifo-deduplication"] = """
## Batch send API

`SendMessageBatch` still needs per-message group and dedup ids. Partial batch failures require careful retry of only failed entries without regenerating dedup ids. Write a helper that retries with the same ids.

## Poison messages in FIFO

A poison message can block a message group. Detect max receive counts and move to DLQ quickly so the group unblocks. Per-group head-of-line blocking is the FIFO tax — design groups accordingly.
"""

R2["queue-temporal-workflow-saga"] = """
## Child workflows

Large sagas split into child workflows per line item with a parent waiting on all. Failure isolation improves, but compensation coordination gets harder. Start monolithic; split when history size or blast radius demands it.

## Search attributes

Index workflow status and order_id as search attributes so support can find workflows without knowing the workflow id. Operational discoverability is part of the saga design.
"""

R2["queue-bull-board-monitoring"] = """
## PII scrubbing

Job payloads in Bull Board are a GDPR surface. Redact emails and tokens at enqueue time; store pointers to DB ids instead of blobs. Add a quarterly access review for who can open the Board.
"""

def main():
    results = []
    for slug, exp in R2.items():
        p = BLOG / f"{slug}.md"
        if not p.exists():
            continue
        w = append(p, exp)
        results.append((slug, w, w >= 1200))
    ok = sum(1 for _,_,o in results if o)
    print(f"round2: {ok}/{len(results)} now >=1200")
    for slug,w,o in sorted(results, key=lambda x: x[1]):
        print(f"  {'OK' if o else '..'} {w:4} {slug}")

if __name__ == "__main__":
    main()
