---
title: "Row-Level Security for Multi-Tenancy"
slug: "postgres-row-level-security-multitenant"
description: "Implement multi-tenant isolation with PostgreSQL RLS: policies, session variables, bypass pitfalls, performance, and comparison with schema-per-tenant."
datePublished: "2026-04-02"
dateModified: "2026-07-17"
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


## RLS policy pattern

ALTER TABLE orders ENABLE ROW LEVEL SECURITY; policy tenant_isolation USING tenant_id = current_setting app.tenant_id. Set app.tenant_id per request in middleware.

## Bypass roles

Migration role and admin BI user need BYPASSRLS sparingly — audit log every connection using bypass role. Application role never bypasses.

## Performance with RLS

Planner injects policy qual into every query — index on tenant_id mandatory. Policy calling subquery per row kills performance.

## Testing RLS in CI

Integration test sets tenant A, inserts row, switches tenant B, asserts SELECT returns empty.

## Connection pool and SET tenant

PgBouncer transaction mode resets session state between transactions — SET LOCAL app.tenant_id inside transaction or pass tenant in every query predicate from application without session variable. Middleware setting session var must run on same connection as query — poolers break naive SET at connection acquire.

## Supabase-style RLS patterns

auth.uid() in policy for user-owned rows; service role bypasses for admin API. Map to your JWT claims in policy USING clause — document claim name in platform auth guide.

## FORCE ROW LEVEL SECURITY

Table owner bypasses RLS unless FORCE ROW LEVEL SECURITY — enable on tables accessed by migration superuser role accidentally in app code path. Integration test connects as app role not superuser — catches missing FORCE in staging.

## Policy for INSERT WITH CHECK

USING filters SELECT/UPDATE/DELETE; INSERT needs WITH CHECK same predicate — INSERT with wrong tenant_id silently blocked or error depending on policy. Test INSERT path separately from SELECT in RLS test suite.

## Performance: subquery in policy

Policy referencing EXISTS subquery on large table runs per row — materialize tenant membership in JWT claim or session table indexed by user_id instead of correlated subquery per row on orders table.

## SECURITY INVOKER views on RLS tables

View owner bypass nuance — PG15 security_invoker views evaluate RLS as querying user. Without invoker, view owner bypass exposes tenant data through view — audit all views joining tenant tables.

## Supabase realtime and RLS

Realtime channel respects RLS — subscription only receives rows visible under policy. Custom websocket server must replicate same tenant filter manually or leak cross-tenant events; audit push code path separately from REST API RLS tests.

## Closing notes

Pen test annually attempts cross-tenant SELECT with forged tenant header — RLS test suite complements external validation; missing FORCE ROW LEVEL SECURITY on new table caught before pen test when CI covers INSERT and SELECT paths.

## Additional guidance

Application middleware sets app.tenant_id using JWT claim validated by auth service — never trust client header alone without signature verification. Integration tests include tampered tenant claim expecting zero rows or 403 from API gateway before request reaches database layer where RLS provides defense in depth not primary authorization for cross-tenant access attempts.

Row security policy audit log via pgAudit logs when BYPASSRLS role queries tenant table — quarterly access review samples pgAudit entries for compliance evidence that break-glass database access remained rare and ticket-linked not routine developer convenience bypassing RLS during feature development laziness.

Annual pen test includes forged tenant_id header attempt — expect zero rows; complements automated RLS integration tests on every schema migration touching tenant tables.

## Resources

- [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL CREATE POLICY](https://www.postgresql.org/docs/current/sql-createpolicy.html)
- [OWASP multi-tenancy cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Security_Cheat_Sheet.html)
- [Citus multi-tenant RLS patterns](https://docs.citusdata.com/en/stable/use_cases/multi_tenant.html)
- [PostgreSQL SET LOCAL documentation](https://www.postgresql.org/docs/current/sql-set.html)
