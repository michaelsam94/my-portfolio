---
title: "Database Access from Serverless"
slug: "serverless-database-access-patterns"
description: "Connect serverless functions to databases safely: RDS Proxy, connection pooling, IAM auth, and patterns that avoid exhausting max connections."
datePublished: "2025-07-18"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "serverless database access, RDS Proxy Lambda, connection pooling serverless, Lambda PostgreSQL connections, DynamoDB serverless, IAM database authentication"
faq:
  - q: "Connection pooling?"
    a: "Use RDS Proxy or external pooler — pools cannot live inside ephemeral functions alone."
  - q: "DynamoDB vs RDS from Lambda?"
    a: "DynamoDB is connectionless; RDS needs proxy and minimal pool per function."
  - q: "Aurora Data API?"
    a: "HTTP SQL for low-QPS workloads avoids persistent connections."
---

CloudWatch showed `FATAL: too many connections for role "app"` seconds after the marketing email dropped. Five hundred Lambdas each opened a Postgres connection because the code copied a Flask SQLAlchemy snippet. Serverless compute scales horizontally by default; relational databases scale connections vertically with hard limits. The fix is not "lower Lambda concurrency"—it is architecture that matches ephemeral workers to durable connection budgets.

## RDS Proxy pattern

```
Lambda → RDS Proxy → Aurora/RDS
         (pools ~1000 clients → ~50 DB conns)
```

```python
import psycopg2

def handler(event, context):
    conn = psycopg2.connect(
        host=os.environ["PROXY_ENDPOINT"],
        user=os.environ["DB_USER"],
        password=get_secret(),
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        conn.close()  # returns to proxy pool quickly
```

Enable IAM authentication to avoid static passwords in env vars. Set Proxy max connections percent below database limit.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Reuse connections across invocations

Lambda may reuse execution environment:

```python
conn = None

def handler(event, context):
    global conn
    if conn is None or conn.closed:
        conn = psycopg2.connect(...)
    ...
```

Reuse helps warm invocations but is insufficient alone at high concurrency—still need Proxy.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## HTTP data APIs

Aurora Serverless v2 with RDS Data API or PostgREST layer exposes HTTP SQL without persistent connections from Lambda. Trade latency and feature limits for connection simplicity.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## DynamoDB and serverless-native stores

```python
table.put_item(Item={"pk": f"USER#{user_id}", "sk": "PROFILE", ...})
```

No connection pool; on-demand billing matches spiky traffic. Design access patterns upfront—GSIs for alternate queries.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Read replicas and timeouts

Set statement_timeout and connect_timeout low so stuck queries release proxy slots. Route read-only analytics to replica endpoint via separate Lambda or connection string.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Secrets and rotation

Fetch credentials from Secrets Manager with caching in global scope; rotate via dual-user pattern without redeploying all functions. IAM DB auth tokens expire—refresh before 15-minute boundary.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

- Opening connection per query inside loop
- Running migrations from Lambda on every cold start
- max_connections = 1000 on tiny instance instead of pooling

IAM DB auth tokens expire—refresh before 15-minute boundary in long-running handlers though Lambda lifetime usually shorter.

Statement_timeout and connect_timeout low so stuck queries release proxy slots. Read replica routing for analytics Lambdas separate from OLTP connection strings.

Anti-pattern: migrations on every cold start—run migrations from CI deploy job, not invocation path.

 with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.



## Resources

- [Amazon RDS Proxy documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy.html)
- [AWS Lambda database access best practices](https://docs.aws.amazon.com/lambda/latest/dg/services-rds.html)
- [RDS IAM database authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)
- [PgBouncer documentation](https://www.pgbouncer.org/)
- [DynamoDB best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## serverless database access patterns rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## Connection strategy beats bigger memory

Serverless functions and classic connection pools fight each other. Each warm instance opening its own pool will exhaust Postgres `max_connections` during a scale-out. Prefer a connection proxy (RDS Proxy, PgBouncer, Cloudflare Hyperdrive) or an HTTP-era data API that multiplexes safely.

Set pool size to 1–2 per instance when you must connect directly, and fail fast on acquire. Separate read replicas for bursty read paths. Cache entity reads in the platform KV/edge cache when consistency allows.

## Transactions and timeouts

Keep transactions shorter than the function timeout with margin. Do not hold a transaction open across an external HTTP call. Idempotency keys belong in the data layer for webhook-driven writes. Watch `remainingTime` / deadline APIs and abort work before the platform kills the isolate mid-write.

Instrument checkout of connections, wait time, and downstream query p99. When p99 climbs with concurrency, you have pool starvation — not an application CPU problem.
