---
title: "Database Access from Serverless"
slug: "serverless-database-access-patterns"
description: "Connect serverless functions to databases safely: RDS Proxy, connection pooling, IAM auth, and patterns that avoid exhausting max connections."
datePublished: "2025-07-18"
dateModified: "2025-07-18"
tags: ["Serverless", "Database", "AWS Lambda", "Architecture"]
keywords: "serverless database access, RDS Proxy Lambda, connection pooling serverless, Lambda PostgreSQL connections, DynamoDB serverless, IAM database authentication"
faq:
  - q: "Why do Lambda functions exhaust database connections?"
    a: "Each concurrent invocation may open its own TCP connection to Postgres or MySQL. Lambda scales concurrency quickly—500 invocations can mean 500 connections against a db.t3.medium with max_connections around 100. Traditional app-server pools assume long-lived processes; Lambda's ephemeral model needs pooling at a shared layer or a connectionless datastore."
  - q: "When should I use RDS Proxy versus PgBouncer?"
    a: "RDS Proxy integrates with IAM auth, Secrets Manager rotation, and Aurora failover for AWS-native stacks. PgBouncer on ECU or ECS suits multi-cloud or self-managed Postgres with mature pool tuning. Both multiplex many client connections onto fewer database connections; pick based on ops model and auth requirements."
  - q: "Is DynamoDB always better for serverless?"
    a: "DynamoDB eliminates connection management and scales with pay-per-request, ideal for key-value and simple access patterns. Relational queries, complex joins, and existing ORM investments may justify RDS with Proxy. Hybrid architectures use Dynamo for hot paths and RDS for reporting via streams."
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## HTTP data APIs

Aurora Serverless v2 with RDS Data API or PostgREST layer exposes HTTP SQL without persistent connections from Lambda. Trade latency and feature limits for connection simplicity.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## DynamoDB and serverless-native stores

```python
table.put_item(Item={"pk": f"USER#{user_id}", "sk": "PROFILE", ...})
```

No connection pool; on-demand billing matches spiky traffic. Design access patterns upfront—GSIs for alternate queries.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Read replicas and timeouts

Set statement_timeout and connect_timeout low so stuck queries release proxy slots. Route read-only analytics to replica endpoint via separate Lambda or connection string.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Secrets and rotation

Fetch credentials from Secrets Manager with caching in global scope; rotate via dual-user pattern without redeploying all functions. IAM DB auth tokens expire—refresh before 15-minute boundary.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


- Opening connection per query inside loop
- Running migrations from Lambda on every cold start
- max_connections = 1000 on tiny instance instead of pooling

IAM DB auth tokens expire—refresh before 15-minute boundary in long-running handlers though Lambda lifetime usually shorter.

Statement_timeout and connect_timeout low so stuck queries release proxy slots. Read replica routing for analytics Lambdas separate from OLTP connection strings.

Anti-pattern: migrations on every cold start—run migrations from CI deploy job, not invocation path.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Amazon RDS Proxy documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-proxy.html)
- [AWS Lambda database access best practices](https://docs.aws.amazon.com/lambda/latest/dg/services-rds.html)
- [RDS IAM database authentication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html)
- [PgBouncer documentation](https://www.pgbouncer.org/)
- [DynamoDB best practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
