---
title: "Row-Level Security for Multi-Tenancy"
slug: "postgres-row-level-security-multitenant"
description: "Implement multi-tenant isolation with PostgreSQL RLS: policies, session variables, bypass pitfalls, performance, and comparison with schema-per-tenant."
datePublished: "2026-04-02"
dateModified: "2026-04-02"
tags: ["PostgreSQL", "Backend", "Security", "Multi-Tenancy"]
keywords: "PostgreSQL row level security, RLS multi-tenant, tenant isolation Postgres, RLS policy, BYPASSRLS security"
faq:
  - q: "How does PostgreSQL row-level security enforce tenant isolation?"
    a: "RLS policies append implicit WHERE clauses to every query on a table. A policy like tenant_id = current_setting('app.tenant_id')::uuid ensures users only see rows matching their tenant — even if application code forgets a filter."
  - q: "Can RLS be bypassed?"
    a: "Superusers and roles with BYPASSRLS attribute skip policies. Table owners bypass RLS unless FORCE ROW LEVEL SECURITY is enabled. Application must connect with non-superuser roles and never expose connection strings with elevated privileges."
  - q: "Is RLS slower than application-level filtering?"
    a: "Minimal overhead when tenant_id is indexed — the planner applies policy as filter condition. Poor performance comes from missing indexes on policy columns or complex subquery policies, not RLS itself."
---

A missing `WHERE tenant_id = ?` in one API endpoint leaked another customer's invoices. Code review catches most; RLS catches what review misses — at the database layer. Postgres row-level security adds mandatory filters Postgres enforces regardless of ORM bugs. It's not magic — superuser bypass and connection pool tenant leakage still kill you — but it's defense in depth that paid for itself in our first pen test.

## Enabling RLS

```sql
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;  -- applies to table owner too

CREATE POLICY tenant_isolation ON invoices
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

Every SELECT, UPDATE, DELETE on `invoices` implicitly filters by `tenant_id`. INSERT needs WITH CHECK:

```sql
CREATE POLICY tenant_insert ON invoices
  FOR INSERT
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

## Setting tenant context per request

```python
def with_tenant(conn, tenant_id: str):
    conn.execute("SET LOCAL app.tenant_id = %s", (tenant_id,))
    # SET LOCAL scopes to current transaction — safe with pooling if transaction-bound
```

**Critical:** use `SET LOCAL` inside transaction, not session-level `SET` — PgBouncer returns connection to pool with stale tenant if session-level.

Pattern with middleware:

```python
@app.middleware("http")
async def tenant_middleware(request, call_next):
    tenant_id = extract_tenant_from_jwt(request)
    async with db.begin():
        await db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        response = await call_next(request)
    return response
```

## Role design

```sql
CREATE ROLE app_user NOINHERIT;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;

-- app_user is NOT superuser, NO BYPASSRLS
CREATE USER api_service PASSWORD '...' IN ROLE app_user;
```

Migration role separate with elevated privileges — migrations run outside app connection.

Audit:
```sql
SELECT rolname, rolbypassrls FROM pg_roles WHERE rolcanlogin;
```

Any `rolbypassrls = true` on app-facing roles — fix immediately.

## Multi-tenant models compared

| Model | Isolation | Ops complexity |
|-------|-----------|----------------|
| Shared table + RLS | Policy enforced | Lowest infra |
| Schema per tenant | Namespace separation | Migration × N |
| Database per tenant | Strongest | Highest cost |

RLS fits SaaS with thousands of tenants and shared schema. Enterprise customers demanding dedicated DB — separate database, RLS redundant.

## Performance

Index tenant_id on every RLS-protected table:

```sql
CREATE INDEX invoices_tenant_id_idx ON invoices (tenant_id);
-- Composite for common queries:
CREATE INDEX invoices_tenant_created_idx ON invoices (tenant_id, created_at DESC);
```

Policy as simple equality — avoid subqueries in policies when possible:

```sql
-- Slower: policy calls function per row
USING (tenant_id IN (SELECT tenant_id FROM user_tenants WHERE user_id = current_user_id()))
-- Better: set tenant in session, direct equality
```

## Testing RLS

```sql
SET app.tenant_id = 'tenant-a-uuid';
SELECT count(*) FROM invoices;  -- only tenant A

SET app.tenant_id = 'tenant-b-uuid';
SELECT count(*) FROM invoices;  -- only tenant B
```

Automated tests:
```python
def test_rls_isolation(db):
    set_tenant(db, TENANT_A)
    create_invoice(db, tenant_id=TENANT_A)
    set_tenant(db, TENANT_B)
    assert list_invoices(db) == []
```

Test INSERT WITH CHECK — tenant A cannot insert row with tenant B id.

## Common pitfalls

- **Superuser app connection** — RLS disabled effectively
- **Session SET without LOCAL** — tenant bleed via connection pool
- **SECURITY DEFINER functions** — run as owner, may bypass RLS unless coded carefully
- **Replication / logical decoding** — replicates rows, not policies; subscribers need own RLS
- **Forgotten tables** — enable RLS on all tenant-scoped tables consistently

## Penetration testing RLS

Include RLS bypass attempts in annual pen test scope: connect as app role, attempt cross-tenant IDOR, attempt session variable manipulation via SQL injection. RLS fails open if app uses string concatenation for `SET LOCAL` — always parameterize.

## Operational notes

Integration tests should include attempt to SET `app.tenant_id` to another tenant UUID — verify zero rows returned, not error leaking existence. Error messages should be identical for missing and forbidden rows.

Audit BYPASSRLS roles quarterly — contractor accounts and break-glass credentials accumulate; remove bypass when no longer justified.

Run RLS policies through SQL formatter in CI — policies with implicit casts on `tenant_id` types can fail open when session variable format does not match column type exactly.

Export RLS policy definitions to Git via pg_dump or custom script — policies changed only in production drift from documented tenant model without version control trail.

Document which database roles bypass RLS in your service catalog — auditors and new engineers both need a single source of truth for effective tenant isolation scope.

## Common production mistakes

Teams get row level security multitenant wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on row level security multitenant causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When row level security multitenant misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL CREATE POLICY](https://www.postgresql.org/docs/current/sql-createpolicy.html)
- [OWASP multi-tenancy cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Security_Cheat_Sheet.html)
- [Citus multi-tenant RLS patterns](https://docs.citusdata.com/en/stable/use_cases/multi_tenant.html)
- [PostgreSQL SET LOCAL documentation](https://www.postgresql.org/docs/current/sql-set.html)
