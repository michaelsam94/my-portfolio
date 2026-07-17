---
title: "AI Agents: Failover Automation Patroni"
slug: "agent-failover-automation-patroni"
description: "Failover Automation Patroni: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-12-12"
dateModified: "2024-12-12"
tags: ["AI", "Agent", "Failover"]
keywords: "agent, failover, automation, patroni, ai, production, engineering, architecture"
faq:
  - q: "Why is Patroni a better fit than manual failover for agent PostgreSQL clusters?"
    a: "Agent workloads write continuously — conversation turns, tool audit rows, embedding metadata — and sessions span minutes to hours. Manual promotion after a primary failure loses uncommitted writes, leaves replicas in ambiguous states, and burns incident time while agents retry into a dead endpoint. Patroni automates leader election via DCS (etcd, Consul, or Kubernetes), promotes the most advanced replica, and reconfigures streaming replication without human SSH."
  - q: "What DCS settings matter most for Patroni with agent traffic?"
    a: "Tune ttl, loop_wait, and retry_timeout so failover completes before agent connection pools exhaust retries — typically ttl 30s, loop_wait 10s for small clusters. Use synchronous replication (synchronous_mode: true with at least one sync standby) when you cannot tolerate lost commits on tool-result writes. Never run Patroni without a stable DCS; agent platforms treat Postgres as the system of record for session state."
  - q: "How do you test Patroni failover without corrupting live agent sessions?"
    a: "Run game days in staging with production-shaped connection pool settings and long-running mock sessions. Kill the primary with SIGKILL, measure time-to-new-leader, and verify PgBouncer or application pools reconnect to the new primary. In production, schedule failovers during low-traffic windows first, then inject chaos during business hours once runbooks are proven."
  - q: "What is the most common Patroni misconfiguration in AI stacks?"
    a: "Applications connect directly to the primary DNS name instead of Patroni's REST API or a proxy like HAProxy/PgBouncer that watches cluster state. After promotion, apps keep hammering the dead node until pool timeout. Fix with patronictl-aware service discovery, health-checked VIPs, or Kubernetes endpoints that Patroni updates on role change."
---
The primary PostgreSQL node hosting agent conversation history died at 2:14 AM. On-call ran `pg_ctl promote` on a replica that was thirty seconds behind on WAL replay. Agents that had just persisted tool results read stale thread state on the new primary; duplicate tool calls fired because idempotency keys lived on the old leader. Patroni would have picked the replica with the highest timeline, fenced the old primary, and updated the cluster endpoint — but the team had installed Patroni without wiring applications to its discovery layer.

Agent platforms treat PostgreSQL as durable memory: sessions, RAG cursors, human-in-the-loop approvals, and eval traces all land in relational storage. Failover is not a quarterly DR exercise — it is a weekly operational concern when you run multi-AZ clusters under continuous write load. Patroni automates high availability for PostgreSQL by combining streaming replication with distributed consensus for leader election. This piece covers how to deploy, configure, and operate Patroni specifically for AI agent workloads where connection churn, long transactions, and write-heavy audit tables change the failure calculus.

## Why agent stacks need automated failover

Stateless inference APIs can retry against any healthy pod. Agent orchestrators cannot — they assume **read-your-writes** on session rows and **serializable tool side effects** backed by database constraints. A thirty-second promotion gap means:

- In-flight agent runs lose the latest turn and restart from an older checkpoint.
- Tool idempotency keys written on the dead primary never replicate; retries double-charge external APIs.
- Embedding metadata pointers reference rows that exist only on the fenced primary.

Manual runbooks fail under sleep-deprived incident response. Patroni encodes promotion logic: detect primary failure via DCS lease expiry, elect a candidate replica, run `pg_promote()`, reconfigure remaining standbys, and expose role changes through a REST API every node runs locally.

## Patroni architecture for production

```
                    ┌─────────────┐
   Agent workers ──►│  PgBouncer  │──► current PRIMARY (Patroni member)
                    │  or HAProxy │
                    └──────┬──────┘
                           │ health checks patroni REST :8008
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         [node A]     [node B]     [node C]
         leader       replica      replica
              └────────────┬────────────┘
                           ▼
                    etcd / Consul / K8s
                    (Distributed Config Store)
```

**Distributed Configuration Store (DCS).** Patroni stores cluster state — who is leader, replication slots, custom tags — in etcd, Consul, ZooKeeper, or Kubernetes API. Pick one DCS and run it in odd-numbered quorum across failure domains. Agent teams on Kubernetes often use the native backend; bare-metal shops prefer a dedicated etcd cluster isolated from the database nodes.

**Patroni REST API.** Each PostgreSQL host runs a Patroni sidecar on port 8008 exposing `/master`, `/replica`, `/health`, and `/patroni`. Load balancers and connection poolers poll these endpoints instead of guessing which IP is primary.

**Replication topology.** Use asynchronous replication for cross-region DR; use synchronous replication within the primary region when losing the last committed tool result is unacceptable. Patroni supports `synchronous_mode` and `synchronous_mode_strict` — the latter blocks writes if no sync standby is available, which protects correctness at the cost of availability during partial outages.

## Configuration that survives agent write bursts

A starter `patroni.yml` tuned for agent session storage:

```yaml
scope: agent-platform
namespace: /service/
name: pg-node-1

restapi:
  listen: 0.0.0.0:8008
  connect_address: 10.0.1.11:8008

etcd3:
  hosts: 10.0.0.1:2379,10.0.0.2:2379,10.0.0.3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576  # 1MB WAL — tighten for sync workloads
    synchronous_mode: true
    synchronous_mode_strict: false
    postgresql:
      use_pg_rewind: true
      parameters:
        max_connections: 300
        shared_buffers: 8GB
        wal_level: replica
        hot_standby: on
        max_wal_senders: 10
        max_replication_slots: 10

postgresql:
  listen: 0.0.0.0:5432
  connect_address: 10.0.1.11:5432
  data_dir: /var/lib/postgresql/16/main
  authentication:
    replication:
      username: replicator
      password: "${REPL_PASSWORD}"
    superuser:
      username: postgres
      password: "${PG_SUPERUSER_PASSWORD}"
  parameters:
    archive_mode: on
    archive_command: 'wal-g wal-push %p'

tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false
```

Key knobs for agent platforms:

| Parameter | Agent workload guidance |
|-----------|-------------------------|
| `maximum_lag_on_failover` | Lower (256KB–1MB) when sessions must not resume on stale state |
| `synchronous_mode` | Enable for tool-audit and billing tables |
| `use_pg_rewind` | Essential when old primary rejoins as replica after split-brain |
| `max_connections` | Size for agent worker pools × pods + admin overhead |

## Application integration: the part teams skip

Patroni automates database promotion; it does **not** automatically retarget your application connection strings. Three production patterns:

**PgBouncer with Patroni-aware checks.** HAProxy or Consul Template watches `/master` and points the write pool at the current leader. Agent workers connect to `agent-db-write.internal:6432` — never to a node IP.

**Kubernetes Endpoints.** The Zalando Postgres Operator and Crunchy PGO both wrap Patroni; Services named `*-primary` and `*-replica` update on failover. Agent deployments should use the primary Service for writes and replica Service for analytics queries only.

**Application-level retry.** Even with perfect routing, failovers cause brief connection resets. Wrap database access with retry on `57P01` (admin shutdown) and `08006` (connection failure):

```typescript
import { Pool } from "pg";

const WRITE_POOL = new Pool({
  host: process.env.AGENT_DB_WRITE_HOST, // Patroni-managed VIP
  port: 6432,
  database: "agent_platform",
  max: 20,
  connectionTimeoutMillis: 5000,
  idleTimeoutMillis: 30000,
});

export async function withDbRetry<T>(
  fn: (client: Pool) => Promise<T>,
  maxAttempts = 5,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn(WRITE_POOL);
    } catch (err: unknown) {
      lastError = err;
      const code = (err as { code?: string }).code;
      if (code === "57P01" || code === "08006" || code === "08001") {
        await sleep(Math.min(1000 * 2 ** attempt, 8000));
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

export async function persistAgentTurn(
  sessionId: string,
  turn: AgentTurn,
): Promise<void> {
  await withDbRetry(async (pool) => {
    await pool.query(
      `INSERT INTO agent_turns (session_id, seq, role, content, tool_calls)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (session_id, seq) DO NOTHING`,
      [sessionId, turn.seq, turn.role, turn.content, JSON.stringify(turn.toolCalls)],
    );
  });
}
```

Use `ON CONFLICT DO NOTHING` or explicit idempotency keys so agent retries during failover do not duplicate turns.

## Operational runbook

**Planned switchover** (patching the primary host):

```bash
# Verify cluster health
patronictl -c /etc/patroni/patroni.yml list

# Graceful switchover — demote current leader, promote chosen standby
patronictl -c /etc/patroni/patroni.yml switchover --master pg-node-1 --candidate pg-node-2 --force

# Confirm new leader
patronictl -c /etc/patroni/patroni.yml list
curl -s http://pg-node-2:8008/patroni | jq .role
```

**Unplanned failover validation:**

1. Alert fires on primary `/health` failure or replication lag SLO burn.
2. Patroni promotes standby within `ttl + loop_wait` seconds (~40s default).
3. PgBouncer drains dead connections and routes to new primary.
4. Agent error rate may spike briefly — watch `agent_turn_write_errors` not just HTTP 5xx.
5. Post-incident: run `pg_rewind` on old primary if it survived; rejoin as replica.

**Metrics to dashboard:**

- `patroni_postgres_running` per node
- Replication lag bytes and seconds (`pg_stat_replication`)
- Failover count and duration (custom alert on DCS leader change)
- Agent session write latency p95 during failover windows

## Split-brain and fencing

Network partitions can leave two nodes believing they are primary. Patroni prevents this by requiring DCS lease renewal — only one leader holds the key. Still, configure **STONITH** semantics: old primary must stop accepting writes when it loses the lease. On cloud VMs, combine Patroni with metadata-tag-aware shutdown scripts or rely on `pg_rewind` after partition heals.

Never set `nofailover: true` on your only synchronous standby. Never run agents against a read replica for session writes "temporarily" during an incident — you will merge divergent histories.

## Testing and game days

Quarterly failover drills are minimum. Script:

1. Start synthetic agent sessions writing turns every 2s for 10 minutes.
2. `kill -9` postgres on the primary.
3. Measure: time to new leader, count of failed writes, duplicate turns after recovery.
4. Repeat during peak simulated traffic with connection pools at production `max`.

Automate checks in CI with a docker-compose stack: Patroni + etcd + three PostgreSQL containers. Run `patronictl failover` in integration tests before every platform release.

## Security and compliance

Patroni REST API exposes cluster control — restrict `:8008` to admin networks. Rotate replication and superuser passwords through Vault; Patroni supports dynamic credential templates. Encrypt replication traffic with `sslmode=verify-full` between nodes. Audit logs for `patronictl` operations satisfy change-control requirements in regulated agent deployments (financial advice bots, healthcare triage assistants).

## The takeaway

Patroni removes manual promotion from the critical path, but agent platforms only benefit when connection routing, application retries, and idempotent writes are designed together with the HA layer. Treat failover as a product feature with measured RTO/RPO targets — not as infrastructure someone else handles. Wire discovery, run game days, tighten `maximum_lag_on_failover` to match your session consistency needs, and document the exact commands on-call runs when the primary disappears.

## Resources

- [Patroni documentation — GitHub](https://github.com/zalando/patroni)
- [Patroni REST API reference](https://patroni.readthedocs.io/en/latest/rest_api.html)
- [Zalando Postgres Operator (Patroni on Kubernetes)](https://postgres-operator.readthedocs.io/)
- [Crunchy PostgreSQL for Kubernetes (PGO)](https://access.crunchydata.com/documentation/postgres-operator/latest/)
- [PgBouncer connection pooling guide](https://www.pgbouncer.org/usage.html)
- [PostgreSQL synchronous replication](https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION)
