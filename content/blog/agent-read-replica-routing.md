---
title: "AI Agents: Read Replica Routing"
slug: "agent-read-replica-routing"
description: "Route agent read traffic to replicas without breaking session consistency: lag-aware routing for RAG retrieval, sticky primary for tool writes, and failover patterns when replicas fall behind."
datePublished: "2024-12-17"
dateModified: "2024-12-17"
tags: ["AI", "Agent", "Read"]
keywords: "read replica routing agents, PostgreSQL replica lag routing, RAG stale retrieval, session consistency agent DB, primary replica failover"
faq:
  - q: "How much replication lag is acceptable for agent RAG retrieval?"
    a: "For document search over published content, 1–5 seconds is usually fine if agents never answer 'did my upload succeed?' from a replica. For session memory or permission checks, route to primary or use lag ceiling under 500ms. Measure per replica — lag is not uniform."
  - q: "Should vector similarity search run on replicas?"
    a: "Yes, when queries are read-only and documents are eventually consistent. pgvector HNSW indexes replicate like any index; heavy ANN queries belong off the primary. Invalidate or warm caches when embeddings bulk-update."
  - q: "What breaks when an agent reads its own write from a replica?"
    a: "Classic failure: user uploads a file, agent immediately searches, replica hasn't received the row yet, agent says 'I can't find that document.' Route post-write reads to primary for a short session window or block until replication catches up."
  - q: "How do you test replica routing without production traffic?"
    a: "Inject artificial lag with pg_sleep on replica apply, or use delayed standbys in staging. Run agent evals that upload-then-query in one session and assert document visibility. Chaos-test replica promotion during active sessions."
---

The agent answered confidently that the policy document didn't exist. The user had uploaded it thirty seconds earlier. Primary had the row; the replica serving RAG retrieval was four seconds behind after a bulk re-embedding job saturated replication bandwidth. Nothing was "wrong" with the model — we routed **read-your-own-write** traffic to a lagging replica and called it scale.

Read replica routing for agent platforms is a consistency problem dressed up as infrastructure.

## Read patterns in agent workloads

Agent systems generate unusual read traffic:

| Pattern | Consistency need | Replica OK? |
|---------|------------------|-------------|
| RAG chunk retrieval | Eventual (seconds) | Yes, with lag guard |
| Tool SQL analytics | Eventual | Yes, prefer OLAP |
| Session memory fetch | Read-your-writes | Primary or fresh replica |
| Permission / tenancy check | Strong | Primary or sync replica |
| Idempotency key lookup | Strong | Primary |
| Conversation history | Read-your-writes | Primary for recent turns |

Most teams enable replica routing globally, save 40% primary CPU, and ship a week of "the agent forgot" tickets. The fix is **intent-aware routing**, not turning replicas off.

## Lag-aware router core

Track replication lag per replica from `pg_stat_replication` or your cloud provider's metric. Route only when lag is below threshold:

```typescript
type ReplicaTarget = {
  id: string;
  dsn: string;
  lagMs: number;
  healthy: boolean;
  weight: number;
};

type ReadIntent =
  | "rag_search"
  | "session_memory"
  | "authz_check"
  | "analytics";

interface RoutingPolicy {
  maxLagMs: number;
  requirePrimary: boolean;
}

const POLICIES: Record<ReadIntent, RoutingPolicy> = {
  rag_search: { maxLagMs: 5000, requirePrimary: false },
  session_memory: { maxLagMs: 500, requirePrimary: false },
  authz_check: { maxLagMs: 0, requirePrimary: true },
  analytics: { maxLagMs: 60_000, requirePrimary: false },
};

function pickReplica(
  replicas: ReplicaTarget[],
  intent: ReadIntent
): ReplicaTarget | "primary" {
  const policy = POLICIES[intent];

  if (policy.requirePrimary) return "primary";

  const eligible = replicas.filter(
    (r) => r.healthy && r.lagMs <= policy.maxLagMs
  );

  if (eligible.length === 0) return "primary";

  // weighted random among eligible
  return weightedPick(eligible);
}
```

Refresh lag every 1–2 seconds; do not query `pg_stat_replication` per request.

## Read-your-own-write session stickiness

After a write, pin subsequent reads for that session to primary for a short window:

```typescript
class SessionRouter {
  private primaryUntil = new Map<string, number>(); // sessionId → epoch ms

  markWrite(sessionId: string, pinMs = 3000) {
    this.primaryUntil.set(sessionId, Date.now() + pinMs);
  }

  route(sessionId: string, intent: ReadIntent): "primary" | ReplicaTarget {
    const until = this.primaryUntil.get(sessionId) ?? 0;
    if (Date.now() < until) return "primary";
    return pickReplica(replicas, intent);
  }
}
```

For upload flows, stronger guarantee: poll replication position until caught up.

```sql
-- On primary after INSERT
SELECT pg_current_wal_lsn() AS write_lsn;

-- On candidate replica before RAG query
SELECT pg_last_wal_replay_lsn() >= $1 AS caught_up;
```

Expose `caught_up` as a routing gate for "search what I just uploaded" intents.

## Connection pool layout

Separate pools prevent analytics from starving retrieval:

```
                    ┌──────────────┐
  Agent gateway ──► │ Router       │
                    └───┬──────┬───┘
                        │      │
              ┌─────────▼      ▼─────────┐
              │ primary pool (small)     │
              │ replica pool RAG (large) │
              │ replica pool analytics   │
              └──────────────────────────┘
```

Primary pool stays small — only strong reads and all writes. RAG pool scales wide on replicas. Never share one pool with round-robin DNS; ORMs will happily send session reads to random nodes.

Prisma / TypeORM pattern: explicit `readClient` and `writeClient`, not `@Transaction` magic on a single datasource.

```typescript
async function searchDocuments(
  session: Session,
  query: VectorQuery
): Promise<Chunk[]> {
  const target = sessionRouter.route(session.id, "rag_search");
  const db = target === "primary" ? writePool : readPool;

  return db.query(
    `SELECT id, chunk_text FROM document_chunks
     WHERE tenant_id = $1
     ORDER BY embedding <=> $2
     LIMIT 20`,
    [session.tenantId, query.vector]
  );
}
```

## RAG-specific staleness UX

When replica lag exceeds policy but you still serve the request (degraded mode), surface it internally:

- Log `replica_id`, `lag_ms`, `intent` on every retrieval span
- Optionally append system context: "Document index may be up to N seconds stale"
- Do not silently fail — missing docs with high lag should trigger primary retry once

```typescript
async function retrieveWithFallback(
  session: Session,
  query: VectorQuery
): Promise<Chunk[]> {
  const replica = sessionRouter.route(session.id, "rag_search");
  let chunks = await searchDocuments(replica, query);

  if (chunks.length === 0 && replica !== "primary") {
    const lag = getLag(replica);
    if (lag > 1000) {
      chunks = await searchDocuments("primary", query);
      metrics.increment("rag_primary_fallback");
    }
  }
  return chunks;
}
```

Cap fallbacks — primary overload from zero-result retries is worse than staleness.

## Failover and replica promotion

When a replica dies, remove it from the eligible set within one health-check interval. When **primary** fails:

1. Promote most caught-up replica
2. Rewind connection strings in config service
3. Invalidate pools — stale connections kill agents silently
4. Expect brief window where agents see conflicting data; pause mutating tools if promotion is in progress

Run game days: promote replica during load, measure agent error rate and p99 retrieval latency.

## Metrics that matter

- `db_replica_lag_ms{replica_id}` — gauge
- `db_route_total{intent, target}` — counter
- `db_primary_fallback_total{reason}` — counter
- `db_pool_waiting_connections{pool}` — saturation

SLO example: 99% of `authz_check` reads hit primary; 95% of `rag_search` served from replica with lag < 2s.

## Anti-patterns

- **Global round-robin** without intent — simplest way to break uploads
- **Ignoring hot standby conflicts** on long replica queries — cancel queries exceeding `max_standby_streaming_delay`
- **Same schema migrations on replicas lagging hours** — agent retrieval against old schema + new app code = empty results
- **Caching embeddings only on primary** — cache invalidation must propagate or replicas return different neighbors than primary

Read replica routing is how agent platforms absorb retrieval load without sacrificing the moments users test hardest: right after they change something and ask the agent to use it.

## Caching layer between agents and replicas

Even well-routed replica traffic repeats identical retrieval queries within seconds — multiple users asking the same FAQ, or one agent loop retrying search with minor paraphrase. Add a read-through cache **after** routing decision, keyed by normalized query fingerprint:

```typescript
async function cachedRagSearch(
  session: Session,
  query: VectorQuery
): Promise<Chunk[]> {
  const target = sessionRouter.route(session.id, "rag_search");
  const cacheKey = `rag:v3:${session.tenantId}:${hash(query.vector)}:${query.filtersHash}`;

  const cached = await redis.get(cacheKey);
  if (cached) {
    metrics.increment("rag_cache_hit", { target: String(target) });
    return JSON.parse(cached);
  }

  const chunks = await searchDocuments(target, query);

  // Short TTL when served from replica; longer when primary confirmed fresh
  const ttl = target === "primary" ? 60 : 15;
  await redis.setex(cacheKey, ttl, JSON.stringify(chunks));
  return chunks;
}
```

Invalidate on write paths: `redis.del` matching `rag:v3:${tenantId}:*` when documents in that tenant change. Stale cache on replica is worse than stale replica — you doubled your consistency lag.

For embedding queries, cache **chunk IDs and scores**, not full text, and hydrate text from replica in one batch `WHERE id = ANY($1)`. Text blobs bloat Redis; IDs stay small.

## Long-running analytical tool calls

When agents run "generate quarterly report" tools that scan millions of rows, route to a **dedicated analytics replica** with `hot_standby_feedback` disabled and `max_standby_streaming_delay` set high — long queries should not cancel replication on the RAG replica.

Tag these connections in application name: `SET application_name = 'agent_analytics'`. Postgres logs and `pg_stat_activity` then separate retrieval from reporting. Mixing both on one replica pool guarantees mutual interference.

## Resources

- [PostgreSQL Hot Standby documentation](https://www.postgresql.org/docs/current/hot-standby.html)
- [Monitoring replication lag (pg_stat_replication)](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-REPLICATION-VIEW)
- [AWS RDS Read Replica lag metrics](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [PgBouncer connection pooling](https://www.pgbouncer.org/usage.html)
- [Jepsen consistency analysis (background reading)](https://jepsen.io/analyses)
