---
title: "AI Agents: Logical Replication Conflicts"
slug: "agent-logical-replication-conflicts"
description: "Logical Replication Conflicts: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-12-15"
dateModified: "2024-12-15"
tags: ["AI", "Agent", "Logical"]
keywords: "agent, logical, replication, conflicts, ai, production, engineering, architecture"
faq:
  - q: "When do PostgreSQL logical replication conflicts occur?"
    a: "Conflicts arise when a change applied on the subscriber cannot be replayed — typically duplicate primary keys, updated rows missing on the subscriber, or DELETE/UPDATE on rows that do not exist. They appear in multi-master setups, after subscriber lag with divergent writes, or when agents and batch jobs write to both sides."
  - q: "Should agent conversation state use logical replication?"
    a: "Only if you accept conflict resolution rules upfront. High-churn agent session tables with concurrent writes on multiple regions need primary keys scoped per region, last-write-wins policies, or a single writer with read replicas — not naive bidirectional replication."
  - q: "What is the difference between pglogical conflict handlers and PostgreSQL 16+ built-in?"
    a: "PostgreSQL 16 improved logical replication with conflict logging and options on subscribers. Extensions like pglogical historically offered custom conflict handlers. Prefer native logical replication on supported versions; verify your handler policy matches product semantics before enabling multi-master."
  - q: "How do you detect replication conflicts before users notice?"
    a: "Monitor pg_stat_subscription_conflicts, replication lag, and subscriber error logs. Alert on any conflict count increase — do not wait for missing agent messages. Run periodic row-count checksums between publisher and subscriber on critical tables."
---
Your agent platform replicates conversation history to a read region using PostgreSQL logical replication. A user switches devices mid-session; both clients append messages. The publisher and subscriber diverge. Replication halts with `duplicate key value violates unique constraint` on `messages_pkey`, and the EU read path serves stale threads until someone manually skips the transaction.

Logical replication conflicts are not exotic edge cases — they are the predictable outcome of applying row changes on a subscriber that already mutated the same keys. Agent stacks amplify the risk: high insert rates on session tables, tool-call audit rows keyed by request ID, embedding metadata updated in place, and multi-region failover drills that briefly create two writers.

This article explains conflict mechanics in PostgreSQL logical replication, patterns that prevent them in agent data models, detection and remediation, and when to choose unidirectional replication instead.

## How logical replication applies changes

Unlike physical streaming replication (byte-for-byte WAL), **logical replication** decodes WAL into row-level changes and applies INSERT/UPDATE/DELETE on subscribers via apply workers.

```
Publisher (primary)                    Subscriber (standby / region)
     │                                        │
     │  INSERT message id=42                  │
     ├───────────────────────────────────────►│ apply OK
     │                                        │
     │  (lag: subscriber offline)             │ local INSERT id=42 (conflict path)
     │                                        │
     │  INSERT message id=42 (replay)         │
     ├───────────────────────────────────────►│ ERROR: duplicate key
```

Default behavior on conflict: the apply worker **errors and stops** the subscription until an operator intervenes. Agent products feel this as frozen conversation sync and growing replication lag.

Common conflict types:

| Conflict | Scenario |
|----------|----------|
| **insert_exists** | Same primary key inserted on subscriber during lag |
| **update_missing** | UPDATE on publisher for row deleted on subscriber |
| **update_conflict** | Concurrent updates to same row with different values |
| **delete_missing** | DELETE on publisher for row already absent on subscriber |

## Schema design that reduces agent-table conflicts

### Single writer, many readers

The default safe pattern for agent state:

- One **publisher** region accepts writes.
- Subscribers are read-only; application routing sends writes only to publisher.
- Failover promotes a subscriber to publisher; brief read-only window during cutover.

No concurrent writes on subscribers means no insert/update conflicts from application logic — only replay ordering issues during failover if old publisher still accepts writes (split brain).

### Partition keys by region or tenant

If you must write locally for latency, partition so keys never collide:

```sql
CREATE TABLE agent_messages (
  region_code   text NOT NULL,
  message_id    uuid NOT NULL,
  session_id    uuid NOT NULL,
  content       jsonb NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (region_code, message_id)
);
```

Each region generates `message_id` locally; replication merges disjoint keyspaces without primary key clashes. Cross-region session reads aggregate via federated queries or sync jobs — not bidirectional row replay on the same PK.

### Use natural keys with idempotency

Agent tool calls should use client-supplied idempotency keys:

```sql
CREATE TABLE agent_tool_invocations (
  idempotency_key text PRIMARY KEY,
  session_id      uuid NOT NULL,
  tool_name       text NOT NULL,
  payload         jsonb,
  result          jsonb,
  created_at      timestamptz NOT NULL DEFAULT now()
);
```

Retries and duplicate agent steps become `INSERT ... ON CONFLICT DO NOTHING` on publisher — subscribers replay identical upserts without conflict if apply order matches.

## Monitoring conflicts and lag

PostgreSQL exposes conflict counters:

```sql
SELECT subname, confl_insert_exists, confl_update_missing,
       confl_update_conflict, confl_delete_missing
FROM pg_stat_subscription_stats;
```

Alert when any counter increases:

```yaml
# prometheus postgres_exporter custom query alert
- alert: LogicalReplicationConflict
  expr: increase(pg_stat_subscription_conflicts_total[5m]) > 0
  labels:
    severity: critical
  annotations:
    summary: "Logical replication conflict on {{ $labels.subname }}"
```

Track **replication lag** in bytes and seconds:

```sql
SELECT slot_name,
       pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes
FROM pg_replication_slots
WHERE slot_type = 'logical';
```

Agent session tables lagging minutes mean users see stale tool results in read regions — conflict risk rises if any write path touches subscribers.

## Conflict resolution policies

PostgreSQL 16+ subscribers can log conflicts and continue depending on configuration — verify exact settings for your version in official docs. Conceptually, policies include:

**error (default)** — stop replication; safest for financial agent audit tables where silent overwrite is unacceptable.

**skip** — discard conflicting change; dangerous for agent messages unless paired with compensating sync.

**last-update-wins** — compare commit timestamps or `updated_at`; acceptable for ephemeral session metadata, not for billing events.

Example subscriber-side handling concept (extension or custom apply):

```sql
-- Illustrative: prefer publisher version on update_conflict
-- Production: use version-native settings or pglogical handlers
ALTER SUBSCRIPTION agent_events_sub
  SET (binary = false);
-- Enable conflict logging to table for audit
CREATE TABLE replication_conflicts (
  id bigserial PRIMARY KEY,
  conflict_time timestamptz DEFAULT now(),
  table_name text,
  conflict_type text,
  row_data jsonb,
  resolution text
);
```

Every resolution should land in `replication_conflicts` for agent compliance review — "why did message 42 disappear in EU?"

## Failover without split brain

Agent platforms drill regional failover. Logical replication breaks when **two publishers** accept writes:

1. Enable **write fence** — revoke app credentials on old primary via consensus (etcd, Patroni, RDS promotion).
2. Wait until subscriber catches up or explicitly resync.
3. Promote subscriber; re-point DNS and connection pools.
4. Recreate subscription from new publisher to old region (now subscriber) if bidirectional.

Patroni + logical replication pattern:

```yaml
# patroni.yml excerpt — tag for logical slots
postgresql:
  parameters:
    wal_level: logical
    max_replication_slots: 10
    max_wal_senders: 10
```

After promotion, verify slot health:

```sql
SELECT * FROM pg_replication_slots WHERE active IS FALSE;
-- inactive slots accumulate WAL — drop or restart carefully
```

## Resync after conflict stop

When apply worker halts on duplicate key:

1. Identify offending LSN from subscriber logs.
2. Compare row on publisher vs subscriber:

```sql
-- on publisher
SELECT * FROM agent_messages WHERE message_id = '42';

-- on subscriber
SELECT * FROM agent_messages WHERE message_id = '42';
```

3. Choose remediation:
   - **Delete subscriber row**, restart replication (publisher wins).
   - **Skip transaction** with pg_replication_origin or advanced slot advance (risky — document LSN).
   - **Full table resync** for small agent config tables: `COPY` + truncate subscriber partition.

For large conversation history, prefer **per-partition resync** by `session_id` range rather than full truncate.

```bash
# pg_dump data-only for one partition, restore to subscriber
pg_dump --data-only --table=agent_messages_2024_12 \
  -h publisher.internal -U repl agent_db \
  | psql -h subscriber.internal -U repl agent_db
```

## Agent-specific tables and replication fit

| Table | Replication pattern | Conflict risk |
|-------|---------------------|---------------|
| `sessions` | Unidirectional | Low if single writer |
| `messages` | Append-only on publisher | Medium during failover |
| `tool_invocations` | Idempotent PK | Low with idempotency keys |
| `embedding_metadata` | UPDATE heavy | High — avoid multi-master |
| `user_settings` | LWW on `updated_at` | Medium — explicit policy |

Vector index tables often live outside Postgres (Pinecone, pgvector on separate sync). Replicate **metadata** only; rebuild indexes from snapshot after major conflict recovery.

## Testing conflict scenarios

**Integration test** with two write paths in staging (never prod):

```python
def test_insert_exists_conflict(subscriber_conn, publisher_conn):
    publisher_conn.execute(
        "INSERT INTO agent_messages (region_code, message_id, session_id, content) "
        "VALUES ('eu', 'test-uuid', 'sess-1', '{}')"
    )
    subscriber_conn.execute(
        "INSERT INTO agent_messages (region_code, message_id, session_id, content) "
        "VALUES ('eu', 'test-uuid', 'sess-1', '{\"local\": true}')"
    )
    # advance replication; assert conflict logged and policy applied
```

**Failover game-day** — promote subscriber, write 100 agent messages, verify old primary read-only, no duplicate PK in unified read.

**Checksum job** nightly:

```sql
SELECT count(*), sum(hashtext(content::text)) FROM agent_messages;
```

Compare publisher vs subscriber; drift triggers resync before conflicts stop replication.

## When not to use logical replication for agents

- **Strong cross-region consistency** for every message — use single region + CDN edge cache or CRDT-backed store.
- **High-frequency counter updates** (token usage meters) — use Redis or dedicated metering with async aggregate to Postgres.
- **Bidirectional editing** of same session — product-level merge, not database replay.

Logical replication excels at **read scaling** and **analytics copy** of agent audit data to warehouse subscribers — not as implicit multi-master without conflict design.

## The takeaway

Logical replication conflicts surface when subscribers apply changes that collide with local row state — common during lag, failover, or mistaken multi-writer setups. Agent platforms should default to single-writer schemas, idempotent keys on tool tables, partition strategies that isolate regions, and alerting on `pg_stat_subscription_conflicts` before users see stale chat. When conflicts occur, treat resolution as a audited operational act with explicit publisher-wins or LWW semantics — not a silent skip that erases agent history.

## Resources

- [PostgreSQL logical replication documentation](https://www.postgresql.org/docs/current/logical-replication.html) — publications, subscriptions, conflicts
- [pg_stat_subscription_stats](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-SUBSCRIPTION-STATS) — conflict counters
- [Patroni high availability](https://patroni.readthedocs.io/) — failover coordination for Postgres
- [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html) — CDC alternative for analytics paths
- [CRDTs and collaborative state](https://crdt.tech/) — when application-level merge beats row replay
