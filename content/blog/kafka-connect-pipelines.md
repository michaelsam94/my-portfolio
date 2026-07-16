---
title: "Data Pipelines with Kafka Connect"
slug: "kafka-connect-pipelines"
description: "Build reliable data pipelines with Kafka Connect: source and sink connectors, SMTs, error handling, and operational patterns for moving data without custom consumers."
datePublished: "2025-10-16"
dateModified: "2025-10-16"
tags: ["Backend", "Kafka", "Data Engineering"]
keywords: "Kafka Connect, source connector, sink connector, SMT, Debezium, data pipeline, CDC, Kafka Connect REST API"
faq:
  - q: "When should I use Kafka Connect instead of a custom consumer?"
    a: "Use Connect when you need to move data between Kafka and an external system with well-defined schemas and minimal transformation logic. Connectors handle offset management, retries, and partitioning for you. Custom consumers make sense when you need complex business logic, joins across many sources, or tight control over batching and backpressure that no existing connector provides."
  - q: "How do Single Message Transforms fit into a Connect pipeline?"
    a: "SMTs are lightweight, per-record transformations applied inside the connector worker before records reach the sink or after they leave the source. They are ideal for field renames, routing to different topics, or masking PII. They are not a replacement for Kafka Streams or ksqlDB when you need stateful joins, aggregations, or windowed processing."
  - q: "What is the most common production failure mode in Connect clusters?"
    a: "Connector tasks stall because of misconfigured converter settings, schema incompatibility, or a sink that cannot keep up with source throughput. Dead letter queues and the errors.tolerance setting help isolate bad records without stopping the entire pipeline. Monitor task status, consumer lag on internal Connect topics, and rebalance frequency on the worker group."
---

A team I worked with spent three weeks building a custom Python consumer to copy Postgres rows into Kafka. It worked on staging, then fell over in production when a VARCHAR column widened and their JSON serializer threw. They rewrote the whole thing as a Debezium source connector plus a JDBC sink in two days. Kafka Connect did not make the pipeline smarter—it made it boring, which is exactly what you want for data movement.

Connect sits between your databases, SaaS APIs, and object stores on one side and Kafka topics on the other. You configure connectors; workers handle partitioning, offset commits, and restarts. The mental model is a fleet of specialized importers and exporters, not a pile of one-off scripts.

## Connectors, workers, and the REST API

A **Connect cluster** is a set of worker processes (standalone for dev, distributed for production) that run connector plugins. Each connector spawns one or more **tasks** that actually produce or consume records. Tasks map to Kafka partitions when possible, so scaling often means raising `tasks.max`.

Deploy and manage connectors through the REST API:

```bash
curl -X POST http://connect:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-orders-source",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "database.hostname": "db.internal",
      "database.dbname": "orders",
      "topic.prefix": "cdc",
      "table.include.list": "public.orders",
      "tasks.max": "4",
      "key.converter": "org.apache.kafka.connect.storage.StringConverter",
      "value.converter": "io.confluent.connect.avro.AvroConverter",
      "value.converter.schema.registry.url": "http://schema-registry:8081"
    }
  }'
```

Check health with `GET /connectors/postgres-orders-source/status`. If a task is FAILED, the status payload includes the stack trace—fix the config and POST to `/connectors/{name}/restart?includeTasks=true`.

## Source vs sink patterns

**Source connectors** pull data in: Debezium for CDC, JDBC for polling, S3 for files. **Sink connectors** push data out: Elasticsearch, BigQuery, another JDBC database. The same topic can fan out to multiple sinks without touching the source.

For CDC, prefer log-based capture (Debezium) over timestamp polling. Polling misses deletes, struggles with high-churn tables, and hammers the database. Debezium reads the WAL, emits create/update/delete events with before/after images, and stores offsets in a Kafka topic (`connect-offsets` by default).

Sink connectors need idempotency awareness. A JDBC sink with `insert.mode=upsert` and a primary key in the record key handles at-least-once delivery. Without upsert semantics, retries duplicate rows.

## Single Message Transforms and routing

SMTs chain on the connector config:

```json
"transforms": "route,mask",
"transforms.route.type": "org.apache.kafka.connect.transforms.RegexRouter",
"transforms.route.regex": "cdc.public.(.*)",
"transforms.route.replacement": "orders.$1",
"transforms.mask.type": "org.apache.kafka.connect.transforms.MaskField$Value",
"transforms.mask.fields": "email"
```

This renames topics and masks email before records hit downstream consumers. Keep SMTs pure and fast—they run on every record in the task thread.

When transforms grow beyond field tweaks, move logic to Kafka Streams or a stream processor. Connect moves bytes; Streams computes.

## Error handling and dead letter queues

Production pipelines need a plan for poison records. Set `errors.tolerance=all` and configure a dead letter topic:

```json
"errors.tolerance": "all",
"errors.deadletterqueue.topic.name": "connect-dlq.orders",
"errors.deadletterqueue.context.headers.enable": "true"
```

Bad records land in the DLQ with headers describing the connector, task, and exception. Alert on DLQ growth rate, not just absolute count—a steady trickle of bad UUIDs is different from a schema explosion.

For sinks, also tune `max.retries` and `retry.backoff.ms`. Transient network blips should retry; permanent schema mismatches should fail fast into the DLQ.

## Operating Connect in production

Run at least three workers for fault tolerance. Connect uses Kafka consumer groups internally; losing a worker triggers rebalance and task reassignment. Keep worker heap modest—Connect is I/O bound, not compute bound.

Monitor:

- **Task state** — anything not RUNNING needs attention
- **Lag on source topics** — sinks falling behind
- **Rebalances** — frequent rebalances mean unstable workers or overly aggressive session timeouts
- **Converter errors** — almost always schema registry or JSON parsing

Version connector plugins independently of Kafka broker version, but test upgrades on a staging cluster first. Debezium major bumps often change event envelope fields.

## When Connect is the wrong tool

Skip Connect when you need multi-table joins before writing, complex enrichment from external APIs per record, or sub-millisecond latency. Those belong in application code or Kafka Streams. Connect shines when the job is "keep this table synchronized with that topic" and the transformations fit in a handful of SMTs.

## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Resources

- [Kafka Connect documentation](https://kafka.apache.org/documentation/#connect) — official guide to concepts, configs, and REST endpoints
- [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html) — CDC setup, WAL prerequisites, and event format
- [Confluent Kafka Connect deep dive](https://docs.confluent.io/platform/current/connect/index.html) — distributed worker deployment and connector hub
- [Kafka Connect production FAQ](https://cwiki.apache.org/confluence/display/KAFKA/Kafka+Connect+Production+FAQ) — community-run operational notes
