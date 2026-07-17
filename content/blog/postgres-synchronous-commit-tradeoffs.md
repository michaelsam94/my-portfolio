---
title: "Postgres Synchronous Commit Tradeoffs"
slug: "postgres-synchronous-commit-tradeoffs"
description: "Balance durability and latency with synchronous_commit modes, group commit, and when async commits are safe for your RPO."
datePublished: "2026-03-05"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "synchronous_commit, postgres durability, fsync, group commit, RPO latency tradeoff"
faq:
  - q: "What does synchronous_commit control in Postgres?"
    a: "It defines how strictly COMMIT waits for durability before returning to the client. With synchronous_commit=on (default), commit waits until WAL is flushed to disk or acknowledged by synchronous standby if configured. Lighter modes defer flush for lower latency at crash risk."
  - q: "When is synchronous_commit=off acceptable?"
    a: "When you explicitly accept losing recent commits on single-node crash—session analytics, idempotent event buffering, staging imports—not financial ledger finalization. Document RPO. Pair with application replay or upsert idempotency."
  - q: "How does synchronous_commit interact with synchronous replication?"
    a: "synchronous_commit=on waits for local flush AND configured remote standbys when synchronous_standby_names is set. remote_write and remote_apply relax or tighten remote durability. Slow replicas can block commits—monitor replication lag."
  - q: "Does turning off synchronous_commit disable WAL entirely?"
    a: "No. WAL is still written; commits may return before fsync completes locally. Crash can lose recent unflushed transactions."
---

Every **`COMMIT`** is a promise about durability. Postgres defaults to **`synchronous_commit = on`**: wait until WAL reaches durable storage before telling the client success. That promise costs latency—especially on remote storage with high fsync times.

Understanding **`synchronous_commit`** modes, **group commit**, and **streaming replication** interaction lets you tune per transaction instead of gambling on a global default.

## WAL flush path on COMMIT

1. Transaction commits; WAL records buffered
2. **`XLogFlush`** writes and **`fsync`s** WAL (unless deferred)
3. Client receives success

**`synchronous_commit`** controls step 2's strictness—not whether WAL exists in memory.

## Mode reference

| Value | Client waits for | Crash may lose |
| --- | --- | --- |
| **on** (default) | Local WAL flush (+ sync rep if configured) | Acknowledged commits |
| **off** | WAL in kernel buffer, not necessarily fsync | Recent unflushed commits |
| **local** | Local flush only | Async rep lag on standby |
| **remote_write** | Standby received WAL to OS buffer | If standby dies before flush |
| **remote_apply** | Standby applied changes | Least loss on failover; highest latency |
| **full** | Local flush of all prior commits | Slowest; rare in production |

Per transaction:

```sql
BEGIN;
SET LOCAL synchronous_commit = off;
INSERT INTO click_stream VALUES (...);
COMMIT;
```

Per role:

```sql
ALTER ROLE batch_loader SET synchronous_commit = off;
```

## Measuring commit latency

```sql
\timing on
BEGIN; INSERT INTO t SELECT generate_series(1,1000); COMMIT;
```

Compare **`on`** vs **`SET LOCAL synchronous_commit=off`**. Monitor **`pg_stat_wal`**.

## Group commit

Postgres batches concurrent commits into single **`fsync`** when many sessions commit simultaneously—amortizes disk round-trip. Does not change **`off`** semantics—it batches **`fsync`**, not eliminate durability wait when **`on`**.

## Synchronous replication coupling

```sql
synchronous_standby_names = 'FIRST 1 (pg-replica-1, pg-replica-2)'
```

Slow or dead standby blocks commits with **`on`**. Mitigations: **`ANY 1 (...)`**, temporarily **`SET synchronous_commit = local`** during replica maintenance.

**`remote_apply`** waits until standby queries could read committed data—strongest consistency for read-from-replica; slowest commits.

## RPO framing

Document:

- **Single instance crash with `off`:** recent unflushed commits may vanish despite client success
- **Failover with async replica:** unreplicated WAL lost regardless of local setting

Financial **`COMMIT`** paths stay **`on`** + sync rep; clickstream batch **`off`** with idempotent **`INSERT`**.

## Safe patterns for relaxed commits

```sql
BEGIN;
SET LOCAL synchronous_commit = off;
INSERT INTO raw_events (id, payload) VALUES ($1, $2)
ON CONFLICT (id) DO NOTHING;
COMMIT;
```

Bulk ETL: one **`on`** commit at promotion beats per-row during COPY.

## Unsafe patterns

- Global **`synchronous_commit=off`** for "speed"
- **`off`** on wallet balances read from replica immediately after write without **`remote_apply`**
- Assuming **`off`** means no WAL IO

## Latency budget worksheet

| Layer | Typical added ms (NVMe) | With sync replica |
| --- | --- | --- |
| **on** | 0.5–3 | +1–10 |
| **off** | ~0.1 | replica lag unbounded |
| **remote_apply** | +local | +10–100+ |

Present **`off`** savings only with explicit "rows at risk" from crash drill.

## Connection pooler interaction

PgBouncer transaction pooling: **`SET LOCAL synchronous_commit`** applies per server transaction—safe. Use **`SET LOCAL`**, not session-global leaks.

## Crash recovery expectations

After **`kill -9`** on postmaster, transactions with **`off`** not flushed vanish—clients may have received success. Application must tolerate idempotent replay.

## Observability

Log **`synchronous_commit`** mode in slow transaction traces. Dashboard commit latency with **`pg_stat_replication`** lag when sync rep enabled.

## Practical recommendation tier

1. Default **`on`** until measured pain
2. Per-transaction **`off`** for named idempotent pipelines
3. Sync rep **`ANY n`** for HA without single-replica fragility
4. **`remote_apply`** only when app reads from replica immediately after write

**`synchronous_commit`** is a durability dial, not a performance cheat code.



## C synchronous_commit and drivers

Some drivers autocommit each statement—**`SET LOCAL synchronous_commit`** must run inside explicit transaction before DML. JDBC: verify **`setAutoCommit(false)`** before tuning. Rust **`tokio-postgres`**: same. Misconfigured autocommit makes **`SET LOCAL`** ineffective or error.

## Aurora and cloud durability semantics

Managed Aurora often describes durability at storage layer replication—customer-visible **`synchronous_commit`** still affects client ack timing but underlying durability model differs from self-managed EBS. Read provider docs before copying self-managed tuning guides verbatim.

## Benchmark anti-pattern: fsync=off in dev

Developers disable fsync globally in docker compose "for speed" then ship **`synchronous_commit=off`** habit to staging—both compound data loss risk. Keep production-like durability in staging for integration tests that assert crash recovery; use separate perf lab for fsync-off benchmarks with explicit banner.

## Quorum commit mathematics

**`ANY 2 (a,b,c)`** survives one replica loss while waiting for two acks—latency equals second-fastest replica. Model expected commit latency as **`max(local_fsyn, second_replica_rtt)`** not average replica lag.




## wal_compression interaction

**`wal_compression=on`** reduces WAL bytes; **`synchronous_commit`** still waits for flush of compressed WAL. Compression saves IO bandwidth—not fsync count. Do not disable sync commit assuming compression replaces durability.

## Read-your-writes from async replica

Application reading from async replica after write to primary may not see commit until replay catches up—**`synchronous_commit=remote_apply`** on critical read-after-write paths only, or route those reads to primary. Session stickiness to primary after mutation simpler than global remote_apply.




## Document per-role defaults in IaC

Store **`ALTER ROLE ... SET synchronous_commit`** in Terraform-managed SQL or migration files—not manual prod clicks. Review quarterly when batch roles added. Unexpected **`off`** on application role discovered during audit is compliance incident.

## Latency SLO and sync commit

If API SLO 200ms p99 and commit fsync 5ms, sync commit not dominant—optimize elsewhere first. If fsync 40ms on saturated EBS, fix storage tier before **`off`**. Measure subcomponents before durability tradeoffs.




## Patroni synchronous_mode vs synchronous_commit

Patroni **`synchronous_mode`** influences leader replica ack behavior—coordinate with Postgres **`synchronous_standby_names`**. Dual misconfiguration causes mysterious commit stalls; document both in HA runbook single section to avoid split-brain documentation.




## Testing synchronous_commit off in staging only

Create dedicated staging role **`batch_writer_staging`** with **`synchronous_commit=off`**; production role remains **`on`**. Prevents configuration drift copied via **`pg_dumpall --globals`** accidentally promoting off to prod roles during refresh.

## WAL writer and off mode interaction

**`wal_writer_delay`** and **`wal_writer_flush_after`** still eventually flush WAL—even with **`off`**, crash window size bounded by these GUCs plus uncommitted buffer—not zero risk immediately after commit return. Quantify window in staging crash tests.



## Change management for sync commit toggles

Any ALTER ROLE SET synchronous_commit requires change ticket citing RPO impact, rollback ALTER ROLE RESET, and crash test evidence for off modes. On-call runbook lists which batch jobs use off—incident response checks batch overlap with finance close windows before blaming storage.

## EBS io2 vs gp3 commit latency

Self-managed Postgres on AWS: measure commit latency when moving gp3 to io2 with same synchronous_commit=on—often eliminates need for off on ledger tables. Document storage baseline in architecture decision record before application-level durability weakening.


## Incident retro template for data loss scares

When stakeholders fear lost commits after crash, capture synchronous_commit settings, replication mode, WAL flush metrics, and rows recovered vs expected. Facts calm panic better than asserting Postgres durable by default.



## Synchronous standby priority

Postgres synchronous_standby_names FIRST vs ANY semantics changed across versions—verify docs for installed major during HA design review. Wrong assumption pages on-call during replica maintenance thinking ANY configured when FIRST still blocks.

## Batch job isolation

Run batch ETL roles on separate connection pool with synchronous_commit off; OLTP pool stays on—prevents global GUC change affecting checkout path. Connection pooler user mapping enforces separation cleaner than session GUC in shared pool.

Load tests must use production durability settings — benchmarking with synchronous_commit=off and shipping on invents release-day latency surprises.

Write the failure mode you accept for postgres synchronous commit tradeoffs into the runbook next to the config that enforces it — configuration without narrative decays into cargo cult.

## Resources

- [Runtime config: WAL](https://www.postgresql.org/docs/current/runtime-config-wal.html)
- [Synchronous replication](https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION)
