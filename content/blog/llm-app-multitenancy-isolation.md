---
title: "Multi-Tenancy and Isolation for LLM Apps"
slug: "llm-app-multitenancy-isolation"
description: "Isolation patterns for multi-tenant LLM apps: data boundaries, vector index separation, rate limits, cost quotas, and the failure modes that leak one customer's data to another."
datePublished: "2024-10-16"
dateModified: "2024-10-16"
tags: ["AI", "LLM", "Architecture", "Security"]
keywords: "multi-tenant LLM, tenant isolation AI, SaaS LLM architecture, vector database multi-tenancy, LLM data separation"
faq:
  - q: "Should each tenant get a separate vector index?"
    a: "Depends on scale. Shared index with strict metadata filtering works up to thousands of tenants and millions of vectors if your vector DB enforces filters at query time. Dedicated indexes per enterprise tenant simplify compliance and noisy-neighbor isolation but increase ops cost. Hybrid models — shared pool for SMB, dedicated for enterprise — are common."
  - q: "How do I prevent cross-tenant data leaks in RAG?"
    a: "Enforce tenant_id as a required filter on every retrieval query — in application code and ideally as a database row-level policy. Never pass tenant_id from client input without auth validation. Log and alert on queries that return chunks from a different tenant (should be impossible if filters work)."
  - q: "What isolation do LLM API calls need?"
    a: "Provider APIs don't isolate tenants for you — your gateway must attach tenant context to logs and rate limits. Use separate API keys per tenant tier only if billing isolation requires it; otherwise one provider key with application-level quotas is simpler. Never include Tenant A's retrieved docs in Tenant B's prompt."
---

The bug report was calm, which made it worse: "Your AI quoted our competitor's internal pricing sheet." One missing `WHERE tenant_id = ?` on a vector search. Multi-tenancy in LLM apps isn't just database schemas — it's every layer that touches context: retrieval, memory, tool results, cached responses, and logs.

## Isolation layers

Think in concentric rings:

```
┌─────────────────────────────────────┐
│  Auth & tenant resolution (JWT)     │
├─────────────────────────────────────┤
│  Rate limits & cost quotas          │
├─────────────────────────────────────┤
│  Data plane: DB, vectors, files    │
├─────────────────────────────────────┤
│  Context assembly (prompt building) │
├─────────────────────────────────────┤
│  Observability (logs, traces)       │
└─────────────────────────────────────┘
```

A breach at any ring leaks data. Most incidents happen at context assembly — retrieval returns the right chunks but the wrong tenant's chunks.

## Tenant resolution

Resolve tenant once at the edge, propagate as trusted context:

```python
async def handle_chat(request: Request) -> Response:
    tenant = await auth.resolve_tenant(request.headers["Authorization"])
    # tenant.id is server-side truth — never from request body
    return await orchestrator.run(
        tenant_id=tenant.id,
        user_id=tenant.user_id,
        message=request.body.message,
    )
```

Pass `tenant_id` as an explicit parameter through every function — retrieval, memory, tools, cache keys. Thread-local or context vars work; implicit globals don't.

## Vector store strategies

**Shared index + metadata filter** (Pinecone namespaces, pgvector WHERE clause):

```python
results = await index.query(
    vector=embedding,
    filter={"tenant_id": {"$eq": tenant_id}},
    top_k=10,
)
```

Pros: simple ops, efficient resource use. Cons: filter bugs are catastrophic; noisy neighbors on shared hardware.

**Namespace per tenant** (Pinecone namespace, Qdrant collection):

Pros: hard boundary, easy per-tenant delete. Cons: management overhead at 10k+ tenants.

**Dedicated index per tenant** (enterprise):

Pros: compliance, custom embedding models, isolated scaling. Cons: cost, provisioning automation required.

Pick based on contract requirements, not premature optimization. SOC2 auditors care about provable boundaries, not your feelings about Pinecone namespaces.

## Row-level security in Postgres

Don't trust application code alone:

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Set `app.tenant_id` at connection start from your pool:

```python
async with pool.acquire() as conn:
    await conn.execute("SET app.tenant_id = $1", tenant_id)
    rows = await conn.fetch("SELECT * FROM documents WHERE ...")
```

Even if a developer forgets the WHERE clause, RLS blocks cross-tenant reads.

## Rate limits and cost quotas

Per-tenant fairness prevents one customer from starving others:

```python
class TenantQuota:
    requests_per_minute: int
    tokens_per_day: int
    max_concurrent: int
    max_storage_mb: int

async def enforce_quota(tenant_id: str, estimated_tokens: int) -> None:
    usage = await redis.hgetall(f"quota:{tenant_id}:{today}")
    if int(usage.get("tokens", 0)) + estimated_tokens > quota.tokens_per_day:
        raise QuotaExceeded(tenant_id)
```

Return 429 with `Retry-After`, not a generic error. Enterprise tenants expect quota dashboards showing burn rate.

## Cache isolation

Semantic caches are leak vectors. Key by tenant:

```python
cache_key = hash(tenant_id, normalized_prompt, model_version)
```

A cache hit from another tenant's similar question is a privacy incident. Include tenant_id in the key even if it hurts hit rate.

## Tool and API access

Tools often call third-party APIs with tenant-scoped credentials:

```python
@tool
async def search_crm(query: str, ctx: ToolContext) -> list[Contact]:
    client = crm_clients[ctx.tenant_id]  # per-tenant OAuth token
    return await client.search(query)
```

Never share OAuth tokens across tenants. Store them encrypted with tenant-scoped KMS keys.

## Testing isolation

Automated tests that actually matter:

```python
async def test_retrieval_never_crosses_tenants():
    await ingest("tenant_a", doc="Secret A")
    await ingest("tenant_b", doc="Secret B")
    results = await retrieve("Secret", tenant_id="tenant_a")
    assert all(r.tenant_id == "tenant_a" for r in results)
    assert not any("Secret B" in r.text for r in results)
```

Run on every deploy. Add chaos tests that pass wrong tenant_id and assert hard failures.

## Row-level security as defense in depth

Application-level tenant filters fail when someone writes raw SQL or a bug omits the `WHERE` clause. PostgreSQL RLS enforces isolation at the database:

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON documents
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Application sets per-request:
SET LOCAL app.tenant_id = '550e8400-e29b-41d4-a716-446655440000';
```

RLS is not optional for multi-tenant SaaS storing customer data in shared tables. Pair with integration tests that connect as the app role and verify cross-tenant SELECT returns zero rows.

Vector databases vary: Pinecone namespaces, Weaviate multi-tenancy collections, pgvector with RLS on embedding tables. Match the isolation model to your threat model — namespace typos have caused production leaks.

## Noisy neighbor and fair scheduling

One tenant's batch embedding job shouldn't starve others:

```python
async def schedule_request(tenant_id: str, priority: int) -> None:
    queue = f"llm:{tenant_id}"
    await fair_scheduler.enqueue(queue, weight=tenant_weights[tenant_id])
```

Per-tenant concurrency limits, token buckets, and separate worker pools for enterprise vs free tiers prevent cascade failures. Monitor p95 latency **per tenant** — aggregate metrics hide one tenant blocking others on shared GPU inference.

## Audit and compliance

Enterprise customers ask for:

- **Access logs** — who queried what document, when, from which IP
- **Data residency** — tenant pinned to EU index / EU model endpoint
- **Deletion certificates** — prove embeddings removed within SLA after account termination

Implement deletion as a workflow, not a single `DELETE`:

1. Mark tenant `pending_deletion`
2. Purge vector index entries by tenant_id
3. Purge object storage prefixes
4. Purge cache layers (exact + semantic)
5. Emit audit event with counts deleted
6. Block re-ingestion until cooling period ends

SOC 2 auditors will trace from contract to code path — document the isolation architecture in your security whitepaper with diagrams, not bullet points.

## Production checklist

- [ ] Row-level security enabled on all tenant-scoped tables
- [ ] Vector index filtered by tenant_id on every query
- [ ] Per-tenant quota dashboards visible to enterprise admins
- [ ] Deletion workflow purges embeddings, cache, and object storage
- [ ] Cross-tenant isolation tests run on every deploy

## Resources

- [OWASP Multi-Tenancy Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Security_Cheat_Sheet.html)
- [Pinecone multi-tenancy guide](https://docs.pinecone.io/guides/indexes/implement-multitenancy)
- [PostgreSQL row-level security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [WorkOS multi-tenant architecture guide](https://workos.com/blog/what-is-multi-tenancy)
- [NIST SP 800-210 tenant isolation considerations](https://csrc.nist.gov/publications/detail/sp/800-210/final)
