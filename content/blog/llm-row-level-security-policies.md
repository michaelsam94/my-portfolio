---
title: "Row Level Security Policies"
slug: "llm-row-level-security-policies"
description: "Row-level security for AI agent database access — PostgreSQL RLS policies, session context, SQL generation guardrails, and tests that prove tenants cannot leak through agent tool calls for teams running LLM features in production."
datePublished: "2025-01-02"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "row level security, RLS, PostgreSQL policies, multi-tenant AI, agent SQL access, tenant isolation, SET LOCAL, database security"
faq:
  - q: "Why is application-level filtering not enough for agent SQL access?"
    a: "Agents generate dynamic SQL. A forgotten WHERE clause in one tool call exposes rows. RLS enforces tenant boundaries inside the database regardless of how the query was composed — buggy prompt, hallucinated table join, or compromised middleware."
  - q: "How do you pass tenant context to PostgreSQL for RLS?"
    a: "Set session variables at connection checkout: SET LOCAL app.current_tenant = 'uuid'. Policies reference current_setting('app.current_tenant', true). Never trust tenant IDs embedded in agent-generated SQL — bind them from authenticated session context only."
  - q: "Does RLS break agent performance?"
    a: "Poorly written policies can. Index columns used in policy expressions, avoid per-row subqueries to unrelated tables, and test EXPLAIN plans under representative agent queries. RLS adds predicate overhead; proper indexing usually keeps P95 acceptable."
  - q: "How do you test RLS for agent workloads?"
    a: "Automated tests that SET ROLE to each tenant session, run agent tool query templates, and assert row counts match fixtures. Include negative tests: tenant A must never see tenant B rows even with UNION tricks or OR 1=1 injection in generated filters."
---
The ticket was labeled "agent returns wrong customer's invoice." Engineering assumed prompt drift. Three hours later we found the real bug: the SQL tool connected as a shared `app_readonly` role with SELECT on the entire `invoices` table. The agent's generated query had a typo in the tenant filter. PostgreSQL happily returned another customer's rows.

Application code "always adds tenant_id" until it does not — especially when an LLM writes the WHERE clause. Row-level security (RLS) moves isolation from hope to enforcement.

## RLS in the agent threat model

Agents with database tools sit in a awkward place:

- They need **flexible read access** to answer varied questions
- They must **never exceed** the requesting user's authorization
- They will occasionally produce **malformed or overbroad SQL**

Your defenses stack:

1. **Tool allowlist** — read-only, specific schemas, statement timeouts
2. **Query validation** — parse SQL, reject DDL/DML, multi-statement
3. **RLS** — database enforces row visibility per session tenant
4. **Audit logging** — every query tied to user + agent trace ID

RLS is layer 3. Without it, layers 1–2 eventually fail.

## PostgreSQL RLS fundamentals

RLS attaches policies to tables. When enabled, rows must pass policy expressions for SELECT/INSERT/UPDATE/DELETE.

```sql
-- Enable RLS on tenant-scoped tables
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

-- Application role cannot bypass
REVOKE ALL ON invoices FROM app_agent_role;
GRANT SELECT ON invoices TO app_agent_role;
```

Define tenant isolation policy:

```sql
CREATE POLICY invoices_tenant_isolation ON invoices
  FOR SELECT
  TO app_agent_role
  USING (
    tenant_id = current_setting('app.current_tenant', true)::uuid
  );
```

`FORCE ROW LEVEL SECURITY` ensures even table owners respect policies — important when DBAs and migration roles exist.

For multi-tenant SaaS with hierarchical access (org → workspace → user), compose policies with helper functions:

```sql
CREATE OR REPLACE FUNCTION app.user_can_access_tenant(t uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM app.user_tenant_memberships m
    WHERE m.user_id = current_setting('app.current_user', true)::uuid
      AND m.tenant_id = t
      AND m.revoked_at IS NULL
  );
$$;

CREATE POLICY invoices_membership ON invoices
  FOR SELECT TO app_agent_role
  USING (app.user_can_access_tenant(tenant_id));
```

Mark helper functions `STABLE` and index `user_tenant_memberships(user_id, tenant_id)` — policy evaluation runs per row.

## Session context: wiring the agent pool

Never embed tenant UUIDs from the model into SQL strings. Set context when checking out a connection from the pool:

```python
from contextlib import contextmanager
import psycopg

@contextmanager
def agent_db_session(tenant_id: str, user_id: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # SET LOCAL scopes to transaction — safe with pooled connections
            cur.execute("SET LOCAL app.current_tenant = %s", (tenant_id,))
            cur.execute("SET LOCAL app.current_user = %s", (user_id,))
            cur.execute("SET LOCAL statement_timeout = '8000ms'")
            cur.execute("SET LOCAL transaction_read_only = on")
        yield conn
```

Critical details:

- **`SET LOCAL`** — resets at transaction end; prevents tenant bleed in PgBouncer transaction pooling
- **`transaction_read_only`** — blocks agent-generated UPDATE slips
- **`statement_timeout`** — caps runaway scans from bad joins

The agent tool receives only the connection with context already bound:

```python
def run_readonly_query(conn, sql: str, params: dict) -> list[dict]:
    validate_select_only(sql)  # sqlparse / sqlglot
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
```

## SQL generation guardrails that complement RLS

RLS is not an excuse to run raw agent SQL unsupervised. Parse and constrain:

```python
import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"invoices", "invoice_lines", "customers"}

def validate_select_only(sql: str) -> None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    if not isinstance(parsed, exp.Select):
        raise ValueError("only SELECT allowed")
    for table in parsed.find_all(exp.Table):
        if table.name not in ALLOWED_TABLES:
            raise ValueError(f"table not allowed: {table.name}")
    if parsed.find(exp.Insert, exp.Update, exp.Delete, exp.Drop):
        raise ValueError("DML/DDL not allowed")
```

Agents should prefer **parameterized query templates** over free-form SQL for high-risk domains:

```sql
-- tools/invoice_lookup.sql (template, not generated)
SELECT id, amount_cents, status, issued_at
FROM invoices
WHERE customer_id = %(customer_id)s
ORDER BY issued_at DESC
LIMIT 20;
```

RLS still applies — templates reduce attack surface and make evals reproducible.

## Column-level exposure

RLS controls rows, not columns. Agents that SELECT * on tables with `ssn_last_four` or internal cost fields leak horizontally.

Options:

- **`GRANT SELECT (col1, col2)`** on views, not base tables
- **Security-barrier views** exposing agent-safe projections
- Separate **`agent_read` schema** synced from canonical tables

```sql
CREATE VIEW agent_safe.invoices AS
SELECT id, tenant_id, customer_id, amount_cents, status, issued_at
FROM public.invoices;

GRANT SELECT ON agent_safe.invoices TO app_agent_role;
-- no grant on public.invoices
```

Point agent tools at `agent_safe` only. RLS policies duplicate on views or apply on underlying tables depending on your Postgres version and view definition — test both.

## Testing RLS with agent query patterns

Unit tests without a real database lie about RLS. Use pytest with template SQL the agent issues:

```python
def test_tenant_a_cannot_see_tenant_b_invoices(db, tenant_a, tenant_b):
    db.seed_invoice(tenant_a, amount=100)
    db.seed_invoice(tenant_b, amount=999)

    with agent_db_session(tenant_id=tenant_a, user_id="user-1") as conn:
        rows = run_readonly_query(
            conn,
            "SELECT amount_cents FROM agent_safe.invoices",
            {},
        )
    assert len(rows) == 1
    assert rows[0]["amount_cents"] == 100

def test_injected_or_does_not_bypass_rls(db, tenant_a, tenant_b):
    db.seed_invoice(tenant_b, amount=999)
    malicious = "SELECT amount_cents FROM agent_safe.invoices WHERE 1=0 OR tenant_id = %s"
    with agent_db_session(tenant_id=tenant_a, user_id="user-1") as conn:
        rows = run_readonly_query(conn, malicious, {"tenant_id": tenant_b})
    assert rows == []  # RLS still filters; parameter cannot override session
```

Add fuzz tests that mutate WHERE clauses — RLS should keep result sets within tenant boundary regardless.

## Performance tuning under agent load

Agents generate unpredictable joins. Watch for:

- **Sequential scans** on large tables when policy expressions disable index use
- **InitPlans** that re-evaluate subqueries per row

Run EXPLAIN (ANALYZE, BUFFERS) with session vars set:

```sql
BEGIN;
SET LOCAL app.current_tenant = '550e8400-e29b-41d4-a716-446655440000';
SET LOCAL app.current_user = '660e8400-e29b-41d4-a716-446655440001';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM agent_safe.invoices i
JOIN agent_safe.customers c ON c.id = i.customer_id
WHERE c.status = 'active';
ROLLBACK;
```

Index `invoices(tenant_id, customer_id)` and `customers(tenant_id, id, status)` together. Partial indexes help when agents always filter `status = 'active'`.

## Bypass paths that undo RLS

Even perfect policies fail when something connects as a superuser or table owner without `FORCE ROW LEVEL SECURITY`. Audit these bypass paths quarterly:

- **Migration roles** — Flyway/Liquibase often use superuser; never point agent tools at migration credentials
- **BI read replicas** — analysts connecting with roles that bypass RLS for "convenience"
- **Connection pool misconfiguration** — PgBouncer session pooling reusing connections without resetting session vars
- **`SECURITY DEFINER` functions** — helper functions that forget to validate tenant inside the function body

Add a CI check that fails if any new table in agent-accessible schemas lacks RLS enabled:

```sql
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('public', 'agent_safe')
  AND c.relkind = 'r'
  AND NOT c.relrowsecurity;
```

Any row returned is a merge blocker.

## Operational monitoring

Log `current_setting('app.current_tenant')` with each query in pg_audit or application logs. Alert on:

- Queries returning row counts >> baseline for tenant size
- Session context missing errors (`current_setting` returns NULL — fail closed)
- Agent tool errors spike after schema migration

Schema migrations must include RLS policy updates. A new `invoices_archive` table without policies is a launch-day leak.

## Policy change management

RLS policies are code. Store them in migrations, review in PRs, version alongside agent tool definitions.

Checklist for policy changes:

- [ ] EXPLAIN on representative agent queries before/after
- [ ] Negative tenant isolation tests pass
- [ ] Rollback migration ready
- [ ] Agent eval suite re-run — some answers may legitimately shrink when holes close

## The bottom line

Agents plus shared database roles are a data breach waiting for a bad prompt. RLS makes the breach bounded: worst case, the agent wastes tokens on empty result sets — not competitor invoices.

Invest in session context discipline, agent-safe views, and tests that assume the model will eventually generate terrible SQL. The database should remain the adult in the room.

## Resources

- [PostgreSQL documentation: Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL SET LOCAL session variables](https://www.postgresql.org/docs/current/sql-set.html)
- [OWASP Query Parameterization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html)
- [sqlglot SQL parser](https://github.com/tobymao/sqlglot)
- [PgBouncer transaction pooling considerations](https://www.pgbouncer.org/features.html)
