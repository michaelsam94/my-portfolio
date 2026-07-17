---
title: "AI Agents: Write Through Cache Consistency"
slug: "agent-write-through-cache-consistency"
description: "Keep agent session state and tool caches consistent with write-through patterns: Redis + Postgres dual writes, read-your-writes guarantees, and invalidation when agents mutate shared knowledge."
datePublished: "2026-05-11"
dateModified: "2026-07-17"
tags: ["AI Agents", "Cache", "Consistency", "Architecture"]
keywords: "write through cache agent session, agent state consistency Redis, read your writes agent, cache invalidation RAG"
faq:
  - q: "Write-through vs write-behind for agent session state?"
    a: "Write-through: update cache and DB synchronously on every agent turn — simpler read-your-writes for multi-tab UX. Write-behind: higher write throughput but stale reads if user switches device before flush — poor fit for conversational agents."
  - q: "What agent data belongs in cache vs authoritative store?"
    a: "Cache: hot session context, tool result memoization, embedding lookup for recent chunks. Authoritative: billing events, audit logs, KB document versions — never cache-only."
  - q: "How do you invalidate RAG cache when documents update?"
    a: "Versioned keys: `chunk:{doc_id}:{content_hash}`. On ingest publish, bump doc version — old cache entries miss naturally. Broadcast invalidation event for eager purge on large reindex."
  - q: "Does prompt caching change write-through design?"
    a: "Provider prompt caches are read-only from your side. Your write-through layer still owns session facts and tool memo keys locally — don't conflate OpenAI prefix cache with application cache consistency."
---

User asks the agent to update a CRM record, then immediately asks "what did we just set the status to?" If session state went to Redis async while Postgres lagged — or worse, edge cache served another pod's stale view — the agent confidently lies. **Write-through caching** synchronizes cache and authoritative store on every mutation so agent reads see what writes committed, at the cost of write latency you must budget in p95 turn time.

## Cache patterns compared for agents

| Pattern | Read latency | Write latency | Consistency | Agent fit |
|---------|--------------|---------------|-------------|-----------|
| Cache-aside | Low | Low | Eventual | OK for RAG chunks |
| Write-through | Low | Higher | Strong | Session state |
| Write-behind | Low | Lowest | Eventual | Risky for chat |
| Read-through | Low | N/A | Depends | Tool memo reads |

Agent **session memory** and **post-tool state** → write-through. Immutable **retrieved chunks** → cache-aside with version keys.

## Write-through session store

```python
class AgentSessionStore:
    def __init__(self, redis, pg):
        self.redis = redis
        self.pg = pg

    def append_turn(self, session_id: str, turn: Turn) -> None:
        key = f"session:{session_id}"
        with self.pg.transaction():
            self.pg.execute(
                "INSERT INTO session_turns (session_id, seq, role, content) VALUES (%s, %s, %s, %s)",
                (session_id, turn.seq, turn.role, turn.content),
            )
            self.redis.rpush(key, turn.to_json())
            self.redis.expire(key, 86400 * 7)
            # Invalidate derived summary cache
            self.redis.delete(f"session:{session_id}:summary")
```

Both succeed or transaction rolls back — no orphaned Redis state.

## Read-your-writes across pods

Sticky sessions are fragile on K8s. Options:

1. **Redis as primary read path** after write-through (Postgres for recovery).
2. **Version token** returned to client, sent on next request:

```python
def get_session(session_id: str, min_version: int | None) -> Session:
    data = redis.lrange(f"session:{session_id}", 0, -1)
    version = pg.get_version(session_id)
    if min_version and version < min_version:
        raise StaleReadError()  # client retries 100ms
    return Session.from_turns(data, version=version)
```

Client includes `If-Match: session-version-42` header.

## Tool result memoization

Expensive idempotent tools (market data fetch) memo with write-through to avoid stale **external** truth:

```python
def cached_tool_call(tool: str, args_hash: str, ttl: int, fn):
    key = f"toolmemo:{tool}:{args_hash}"
    hit = redis.get(key)
    if hit:
        return json.loads(hit)

    result = fn()
    with pg.transaction():
        pg.log_tool_result(tool, args_hash, result)
        redis.setex(key, ttl, json.dumps(result))
    return result
```

TTL short (60–300s) for semi-fresh data; invalidate on known market close events.

## RAG chunk cache — cache-aside with versioning

Don't write-through megabyte embeddings every ingest:

```python
def get_chunk_embedding(chunk_id: str, content_hash: str) -> vector:
    key = f"emb:{chunk_id}:{content_hash}"
    cached = redis.get(key)
    if cached:
        return deserialize(cached)

    vec = embed_service.encode(chunk_id)
    redis.setex(key, 86400, serialize(vec))  # no PG write — PG has chunks table
    return vec
```

Document update → new `content_hash` → automatic miss. Old keys expire via TTL.

## Invalidation broadcast on KB reindex

Large reindex flips collection version:

```python
def on_reindex_complete(tenant_id: str, new_version: int):
    pg.set_kb_version(tenant_id, new_version)
    redis.publish(f"kb_invalidate:{tenant_id}", new_version)
    # Workers subscribe and purge local Caffeine caches
```

Agent retrieval checks `kb_version` in session — mismatch triggers re-fetch even if chunk cache hit.

## Consistency vs agent latency budget

Write-through adds ~2–8ms Redis + PG on hot path. Measure:

```python
with metrics.timer("session_append_ms"):
    store.append_turn(session_id, turn)
```

If p95 exceeds SLO, consider:

- Async summary compression (write-through turns only, not derived artifacts)
- Partitioned Redis cluster by tenant
- Cockroach/Spanner for single-node SQL latency

Don't revert to write-behind without UX acceptance of stale reads.

## Failure handling

| Failure | Behavior |
|---------|----------|
| Redis down | Fall back to PG read (degraded latency) |
| PG down | Fail turn append — don't write Redis alone |
| Partial dual-write bug | Reconciliation job compares counts |

Nightly:

```sql
SELECT session_id FROM session_turns
GROUP BY session_id
HAVING count(*) != redis_turn_count(session_id);  -- pseudo
```

## Testing

Integration test two concurrent pods:

```python
def test_read_your_writes_cross_pod(store_a, store_b):
    store_a.append_turn("s1", turn1)
    session = store_b.get_session("s1", min_version=1)
    assert len(session.turns) == 1
```

## Resources

- [Redis — Cache consistency patterns](https://redis.io/docs/manual/patterns/)
- [Martin Kleppmann — Designing Data-Intensive Applications (cache chapter)](https://dataintensive.net/)
- [AWS — Caching best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Strategies.html)
- [Jepsen — distributed cache consistency analyses](https://jepsen.io/analyses)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

