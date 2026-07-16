---
title: "Multi-Tenancy Data Isolation Models"
slug: "backend-multi-tenancy-data-isolation"
description: "Compare pooled, siloed, and hybrid multi-tenant data models: row-level tenant_id, schema-per-tenant, database-per-tenant, and the isolation mistakes that leak data."
datePublished: "2024-11-24"
dateModified: "2024-11-24"
tags: ["Backend", "Architecture", "Databases", "Security"]
keywords: "multi-tenancy, tenant isolation, row-level security, schema per tenant, database per tenant, SaaS data model"
faq:
  - q: "What's the difference between pooled and siloed tenancy?"
    a: "Pooled means many tenants share tables (usually with a tenant_id column) or a shared database. Siloed means each tenant gets a schema or database. Pooled is cheaper and easier to operate at scale; siloed simplifies noisy-neighbor and compliance isolation at higher ops cost."
  - q: "Is a tenant_id column enough?"
    a: "Only if every query path enforces it — preferably via row-level security, a query filter middleware you can't bypass, or both. One raw SQL admin path or a missing WHERE clause is a cross-tenant incident. Defense in depth: RLS + app-level tenant context required on every connection."
  - q: "When do enterprises demand database-per-tenant?"
    a: "When contracts require data residency, dedicated encryption keys, or hard isolation for regulated workloads. Also when a single tenant's size would dominate a shared DB. Offer it as a tier; don't start there for every customer."
---

Multi-tenancy fails loudly: one missing `WHERE tenant_id = ?` and Customer A sees Customer B's invoices. The data model you pick — pooled rows, schema-per-tenant, or database-per-tenant — sets your default blast radius and your ops bill. Choose deliberately; migrating later is a rewrite.

## Three models

| Model | Isolation | Cost | Ops complexity |
|---|---|---|---|
| Shared tables + `tenant_id` | Logical | Lowest | Lowest at scale |
| Schema per tenant | Stronger logical | Medium | Migrations × N |
| Database per tenant | Strongest | Highest | Provisioning, backups × N |

Most B2B SaaS should start pooled with ruthless enforcement, and offer silo as an enterprise SKU.

## Pooled done right

```sql
-- Postgres RLS sketch
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- On each request connection:
SET app.tenant_id = '…';
```

Application code still sets tenant context from the auth token — RLS is the backstop for bugs and confused-deputy queries. Never trust a client-supplied tenant id without verifying membership.

```typescript
async function withTenant<T>(tenantId: string, fn: () => Promise<T>) {
  return db.transaction(async (tx) => {
    await tx.query(`SELECT set_config('app.tenant_id', $1, true)`, [tenantId]);
    return fn();
  });
}
```

## Noisy neighbors and limits

Pooled tenants share buffer pools and connection limits. Per-tenant rate limits, statement timeouts, and optional separate read replicas for huge tenants keep one analytics user from starving others. Watch for unbounded `SELECT` without tenant-scoped indexes — `(tenant_id, created_at)` is table stakes.

## Hybrid reality

I've run pooled for everyone and dedicated DBs for a handful of enterprise logos. Same application code, different connection routing based on tenant config. Keep the domain model identical; only the storage topology changes.

## Checklist before you ship

- Tenant context derived from auth, not request body alone
- RLS or equivalent on every tenant-owned table
- Automated tests that attempt cross-tenant reads and expect denial
- Backups/exports that can't accidentally include all tenants in one file without authz
- Unique constraints scoped correctly (`UNIQUE (tenant_id, external_id)`)

Isolation is a security boundary, not a column you remember to add. Design the model for your compliance tier, then make forgetting `tenant_id` structurally hard.

## How cross-tenant leaks actually happen

Most incidents aren't dramatic SQL injection — they're boring engineering mistakes:

- **Missing WHERE clause** — new endpoint copies a query from an admin tool that runs cross-tenant by design.
- **Cache key without tenant** — Redis key `user:123:profile` when user 123 exists in two tenants; tenant A gets tenant B's cached data.
- **Background job without context** — nightly report job iterates all rows because the cron worker doesn't set `app.tenant_id`.
- **Search index shared** — Elasticsearch document missing `tenant_id` filter in every query template.
- **File storage paths** — S3 key `uploads/{fileId}` instead of `uploads/{tenantId}/{fileId}`; guessable IDs become cross-tenant reads.
- **Webhook forwarding** — integration sends event to URL registered by wrong tenant because lookup skipped tenant scope.

Each vector needs its own defense. RLS catches SQL bugs; it doesn't catch cache keys.

## Schema-per-tenant and database-per-tenant operations

Siloed models shift complexity from application bugs to operational multiplication:

**Schema-per-tenant (Postgres):** One migration runs N times — automate with a migration runner that iterates tenant schemas. Connection pooling gets painful (PgBouncer with `search_path` per tenant, or separate pools). Backups are single-database but restore-one-tenant requires schema-level export.

**Database-per-tenant:** Provisioning becomes a product feature — create DB, run migrations, configure connection string, register in tenant router. Connection limits explode; use a proxy layer (Citus, RDS proxy) or cap enterprise tier count. GDPR deletion is `DROP DATABASE` — genuinely clean, which is why regulated buyers pay for it.

```typescript
// Connection routing — keep domain code tenant-agnostic
function getDbForTenant(tenant: TenantConfig): Database {
  if (tenant.isolation === 'dedicated') {
    return dedicatedPools.get(tenant.dbConnectionString);
  }
  return sharedPool; // RLS enforced
}
```

## Tenant context propagation

Every request path must establish tenant context before any data access:

```typescript
// Middleware: derive tenant from JWT, never from body alone
async function tenantMiddleware(req, res, next) {
  const tenantId = req.auth.organizationId; // from verified token
  if (req.body.tenantId && req.body.tenantId !== tenantId) {
    return res.status(403).json({ error: 'Tenant mismatch' });
  }
  req.tenantId = tenantId;
  next();
}
```

For async work, pass tenant ID explicitly into job payloads and re-establish context in the worker — `AsyncLocalStorage` in Node, `ThreadLocal` in Java, or explicit parameter threading. "Implicit global tenant" breaks the moment you add a second concurrent job.

## Testing isolation

Automated tests should attempt cross-tenant access and expect failure:

```typescript
test('tenant A cannot read tenant B invoice', async () => {
  const invoiceB = await createInvoice({ tenantId: tenantB.id });
  await expect(
    getInvoice({ tenantId: tenantA.id, invoiceId: invoiceB.id })
  ).rejects.toThrow(NotFoundError); // 404, not 403 — don't confirm existence
});
```

Return 404 instead of 403 for cross-tenant resource access — don't leak whether the resource exists in another tenant. Run these tests in CI on every migration that touches tenant-scoped tables.

## Migration between models

Moving a tenant from pooled to dedicated is a product event, not a Friday deploy:

1. Freeze writes for tenant (maintenance window or dual-write period)
2. Copy data to dedicated DB with verified row counts
3. Switch connection routing in tenant config
4. Verify reads/writes against dedicated
5. Delete pooled rows after retention period

Expect a week of planning for a large tenant. Build the routing abstraction on day one even if all tenants start pooled — retrofitting connection routing into a codebase that assumes one DSN is painful.

## Production checklist

- Tenant ID from authenticated session, validated against membership
- RLS enabled on every tenant-owned table in pooled model
- Cache keys, file paths, and search queries include tenant scope
- Background jobs carry and restore tenant context
- Cross-tenant access tests in CI
- Admin cross-tenant tools require separate authz with audit logging
- Export/backup flows scoped per tenant
- Unique constraints include `tenant_id`: `UNIQUE (tenant_id, slug)`

## Resources

- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Microsoft — Multi-tenant SaaS patterns](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/overview)
- [AWS — SaaS storage strategies](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/introduction.html)
---
