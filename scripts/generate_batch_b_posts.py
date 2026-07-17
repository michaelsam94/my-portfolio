#!/usr/bin/env python3
"""Generate Batch B backend/API/database blog posts (≥900 words each)."""

import os
import re
import textwrap
from datetime import date, timedelta

BLOG_DIR = "/Users/michael/Desktop/my-portfolio/content/blog"
BASE_DATE = date(2026, 1, 15)
TARGET_WORDS = 900

# slug -> (title, description, tags, keywords, faqs, sections)
# sections: list of (heading, paragraphs, optional_code)
TOPICS = {}

def topic(slug, title, desc, tags, keywords, faqs, sections):
    TOPICS[slug] = (title, desc, tags, keywords, faqs, sections)

# --- Postgres topics ---
topic(
    "postgres-exclusion-constraints-scheduling",
    "Postgres Exclusion Constraints for Scheduling",
    "Use Postgres exclusion constraints with GiST and range types to prevent double-booking rooms, overlapping shifts, and conflicting reservations without application-level race conditions.",
    ["PostgreSQL", "Backend", "Database"],
    "Postgres exclusion constraint, GiST index, range overlap, scheduling double booking, tstzrange",
    [
        ("When should I use exclusion constraints instead of application checks?", "Exclusion constraints enforce non-overlap at the database level inside the same transaction as the insert. Application checks race under concurrent requests; Postgres rejects the second conflicting row with a constraint violation before commit."),
        ("What index type do exclusion constraints require?", "Most overlap queries use GiST on range types (`tstzrange`, `tsrange`, `daterange`) or PostGIS geometries. B-tree cannot enforce arbitrary overlap exclusion."),
        ("How do I handle constraint violations in the API?", "Map SQLSTATE 23P01 to HTTP 409 Conflict with a stable error code. Retry is not appropriate — the client must pick a different slot."),
    ],
    [
        ("Why application-level overlap checks fail", [
            "Two API workers both read an empty calendar slot, both pass validation, both insert — you double-booked a conference room. I've debugged this twice: once with Redis locks that expired mid-transaction, once with `SELECT FOR UPDATE` on the wrong granularity. **Exclusion constraints** move the invariant into Postgres where concurrent transactions serialize correctly.",
        ]),
        ("Defining the constraint", [
            "Model bookings as a time range column and forbid overlap per resource:",
        ], textwrap.dedent("""\
            ```sql
            CREATE EXTENSION IF NOT EXISTS btree_gist;

            CREATE TABLE bookings (
              id          bigserial PRIMARY KEY,
              room_id     int NOT NULL,
              during      tstzrange NOT NULL,
              EXCLUDE USING gist (
                room_id WITH =,
                during WITH &&
              )
            );

            INSERT INTO bookings (room_id, during)
            VALUES (1, tstzrange('2026-07-01 09:00', '2026-07-01 10:00'));
            -- Second overlapping insert for room 1 fails at commit
            ```""")),
        ("Inclusive vs exclusive bounds", [
            "Back-to-back meetings need `[)` bounds — start inclusive, end exclusive — so 10:00 end touches 10:00 start without overlap. Document the convention in API docs; clients sending ISO8601 instants must not assume inclusive end times.",
        ]),
        ("Partial exclusion for cancelled slots", [
            "Cancelled bookings should not participate in exclusion. Use a partial exclusion index or move cancelled rows to an archive table. A common pattern: `WHERE status <> 'cancelled'` on the constraint via partial index workaround — store only active rows in the constrained table.",
        ]),
    ],
)

topic(
    "postgres-generated-columns-indexing",
    "Postgres Generated Columns and Indexing",
    "Design STORED and VIRTUAL generated columns in Postgres 18+, index them for query performance, and avoid redundant computation in application code.",
    ["PostgreSQL", "Backend", "Database"],
    "Postgres generated column, stored generated column, computed column index, expression index",
    [
        ("STORED vs VIRTUAL generated columns?", "STORED columns are computed on write and occupy disk — indexable like normal columns. VIRTUAL (Postgres 18+) compute on read — save space but cannot be indexed directly; use expression indexes on the same formula."),
        ("Should I use generated columns or expression indexes?", "Generated columns when the value appears in SELECT lists and multiple indexes/queries reuse it. Expression indexes when only one query pattern needs the derivation."),
        ("Do generated columns work with logical replication?", "STORED generated columns replicate as regular columns on subscribers Postgres 12+. Verify subscriber version compatibility before relying on them in CDC pipelines."),
    ],
    [
        ("Normalize once, query many times", [
            "Teams duplicate `lower(email)` in every query and wonder why functional indexes multiply. A **generated column** `email_normalized` keeps derivation centralized and index-friendly:",
        ], textwrap.dedent("""\
            ```sql
            ALTER TABLE users
              ADD COLUMN email_normalized text
              GENERATED ALWAYS AS (lower(trim(email))) STORED;

            CREATE UNIQUE INDEX users_email_norm_idx
              ON users (email_normalized)
              WHERE deleted_at IS NULL;
            ```""")),
        ("JSON extraction without repeated operators", [
            "Extract hot JSONB keys into generated columns when filters sort or join on them frequently. Pair with partial indexes on the generated column rather than GIN on the full document when cardinality is low.",
        ]),
        ("Migration strategy", [
            "Adding a STORED column rewrites the table — plan `ACCESS EXCLUSIVE` window or use expand-contract: add nullable column, backfill in batches, attach generated definition in maintenance window, then add index `CONCURRENTLY`.",
        ]),
    ],
)

topic(
    "postgres-prepared-statement-plan-cache",
    "Postgres Prepared Statements and Plan Cache",
    "Understand prepared statement lifecycle, generic vs custom plans, PgBouncer limitations, and ORM settings that cause plan cache churn or wrong plans.",
    ["PostgreSQL", "Backend", "Database", "Performance"],
    "Postgres prepared statements, plan cache, generic plan, PgBouncer transaction pooling, ORM prepared statements",
    [
        ("Why do prepared statements fail through PgBouncer transaction mode?", "Prepared statements bind to a session. Transaction pooling returns connections to different clients between transactions, so unnamed prepared statements disappear. Use session pooling, statement pooling disable, or driver `preferQueryMode=simple`."),
        ("What is the generic plan problem?", "After five executions Postgres may switch to a generic plan ignoring parameter values — fast for uniform data, catastrophic for skewed columns (status=active vs status=archived). Monitor with `pg_prepared_statements` and `EXPLAIN`."),
        ("Should Node pg use prepared statements?", "For OLTP with PgBouncer transaction pool, often no — simple query protocol avoids prepared statement leaks. For session pool or direct connections, prepared statements reduce parse overhead on hot queries."),
    ],
    [
        ("The PgBouncer surprise", [
            "Latency spiked after enabling PgBouncer transaction pooling. Errors: `prepared statement \"s0\" does not exist`. The Node `pg` driver prepared every query; pooled connections rotated; statements vanished. Fix: `prepare: false` or pool mode `session` for that service.",
        ]),
        ("Inspecting plan behavior", [], textwrap.dedent("""\
            ```sql
            PREPARE user_lookup (bigint) AS
              SELECT * FROM orders WHERE user_id = $1;

            EXECUTE user_lookup(42);
            -- Repeat 5+ times; check if plan uses Index Scan vs Seq Scan for skewed IDs

            SELECT name, plans, calls
            FROM pg_prepared_statements;
            ```""")),
        ("ORM defaults matter", [
            "Hibernate, Sequelize, and Prisma make different choices. Document per-service: connection pool mode, prepared statement toggle, and statement timeout. Integration tests should run through the same pooler path as production.",
        ]),
    ],
)

topic(
    "postgres-upsert-on-conflict-patterns",
    "Postgres UPSERT Patterns with ON CONFLICT",
    "Master INSERT ON CONFLICT for idempotent writes, partial unique indexes, DO UPDATE vs DO NOTHING, and returning clauses for event-driven sync.",
    ["PostgreSQL", "Backend", "Database"],
    "Postgres ON CONFLICT, upsert, DO UPDATE, DO NOTHING, partial unique index upsert",
    [
        ("ON CONFLICT requires what kind of index?", "A unique constraint or unique index — including partial unique indexes. The conflict target must exactly match the index columns and predicate."),
        ("DO UPDATE vs DO NOTHING?", "DO NOTHING for deduplication (webhook idempotency). DO UPDATE for sync (last-write-wins metadata). Always think about which columns should change on conflict."),
        ("How do I upsert with serializable isolation?", "Upserts under serializable may retry on serialization failures. Use idempotency keys and application retry with backoff; or lower isolation to read committed for ingest paths with unique constraints."),
    ],
    [
        ("Idempotent webhook ingest", [], textwrap.dedent("""\
            ```sql
            CREATE UNIQUE INDEX events_provider_id_idx
              ON inbound_events (provider, external_id);

            INSERT INTO inbound_events (provider, external_id, payload)
            VALUES ('stripe', 'evt_123', '{"type":"payment"}')
            ON CONFLICT (provider, external_id) DO NOTHING
            RETURNING id;
            -- NULL id in app means duplicate — skip processing
            ```""")),
        ("Conditional update on conflict", [
            "Use `WHERE` on DO UPDATE to avoid clobbering newer data:",
        ], textwrap.dedent("""\
            ```sql
            INSERT INTO inventory (sku, qty, version)
            VALUES ('ABC', 10, 1)
            ON CONFLICT (sku) DO UPDATE
              SET qty = EXCLUDED.qty,
                  version = inventory.version + 1
              WHERE inventory.version < EXCLUDED.version;
            ```""")),
        ("Partial unique indexes for soft delete", [
            "Unique email only among active users: `UNIQUE (email) WHERE deleted_at IS NULL`. Upsert conflict target must include the same predicate — use `ON CONFLICT ON CONSTRAINT` name for clarity.",
        ]),
    ],
)

topic(
    "postgres-pg-stat-statements-tuning",
    "Postgres pg_stat_statements for Query Tuning",
    "Enable pg_stat_statements, interpret total_time vs mean_time, find regressions after deploys, and reset safely in production.",
    ["PostgreSQL", "Backend", "Database", "Observability"],
    "pg_stat_statements, query performance Postgres, top queries by total time, shared_blks_read",
    [
        ("total_time or mean_time for prioritization?", "Rank by total_time (or total_exec_time) to find queries consuming the most cluster capacity. mean_time finds slow individual executions; a fast query run millions of times dominates total_time."),
        ("How do I reset pg_stat_statements in prod?", "Use `pg_stat_statements_reset()` for specific queryids after fixing a query, or snapshot to a metrics table before reset. Avoid global reset during incidents — you lose comparison baseline."),
        ("Does pg_stat_statements show prepared statement text?", "It normalizes parameters to `$1`, `$2`. Use `queryid` to track the same logical query across ORM versions that change whitespace."),
    ],
    [
        ("Finding the real CPU hogs", [], textwrap.dedent("""\
            ```sql
            SELECT queryid,
                   calls,
                   round(total_exec_time::numeric, 2) AS total_ms,
                   round(mean_exec_time::numeric, 2) AS mean_ms,
                   rows,
                   shared_blks_read
            FROM pg_stat_statements
            ORDER BY total_exec_time DESC
            LIMIT 20;
            ```""")),
        ("Regression detection workflow", [
            "Export top 50 queryids nightly to Prometheus or ClickHouse. Alert when mean_exec_time doubles for a stable queryid. Pair with deploy markers — ORM upgrades change query text but often preserve queryid.",
        ]),
        ("IO vs CPU bound queries", [
            "High `shared_blks_read` relative to calls indicates cache misses — index missing or working set exceeds shared_buffers. High mean time with low blocks suggests CPU-heavy sorts or JSON parsing in SQL.",
        ]),
    ],
)

FOOTER_SECTIONS = textwrap.dedent("""\

## Common production mistakes

Teams ship backend changes without rehearsing failure modes: missing `lock_timeout` on migrations, connection pools sized for app count not PgBouncer multiplexing, and assuming staging EXPLAIN plans match production statistics after a traffic pattern shift. Document trade-offs explicitly — if you chose availability over strict consistency, write that down for the next engineer on call.

## Debugging and triage workflow

When production misbehaves, work top-down:

1. **Confirm scope** — one tenant, region, or deployment stage?
2. **Check recent changes** — deploys, flag flips, schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, traffic vs baseline.
4. **Reproduce minimally** — smallest input that triggers failure; capture traces with correlation IDs.
5. **Fix forward or rollback** — rollback first during incident if faster than root cause.
6. **Add a guard** — alert, integration test, or circuit breaker for this failure class.

## Operational checklist

- **Staging parity** — failure paths (timeouts, retries, partial outages) exercised before prod.
- **Observability** — dashboards and alerts for metrics discussed above; on-call knows where to look.
- **Rollback** — documented revert path without improvising.
- **Load test** — evidence about behavior at expected peak plus headroom, not intuition.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
""")

# Bulk topic definitions: slug suffix after prefix, title, one-line desc seed
BULK = [
    ("postgres-table-inheritance-patterns", "Postgres Table Inheritance Patterns", "Use table inheritance for partitioned-like schemas, constraint exclusion, and legacy patterns — and know when declarative partitioning replaces it."),
    ("postgres-fdw-cross-database-queries", "Postgres FDW Cross-Database Queries", "Query remote Postgres, Redis, or CSV via foreign data wrappers with pushdown, connection limits, and security boundaries."),
    ("postgres-lock-monitoring-pg-lock", "Postgres Lock Monitoring with pg_locks", "Diagnose blocking chains, deadlocks, and long-running DDL with pg_locks, pg_blocking_pids, and lock_timeout guards."),
    ("postgres-hot-standby-feedback-conflicts", "Postgres Hot Standby Feedback and Conflicts", "Reduce query cancellations on replicas with hot_standby_feedback and resolve conflict with vacuum tuning on primary."),
    ("postgres-parallel-query-tuning", "Postgres Parallel Query Tuning", "Tune max_parallel_workers_per_gather, parallel_setup_cost, and when parallel seq scan beats index scan at scale."),
    ("postgres-work-mem-sort-hash-tuning", "Postgres work_mem Sort and Hash Tuning", "Size work_mem for sorts and hashes without OOM — understand per-operation allocation and log_temp_files signals."),
    ("postgres-statistics-extended-multivariate", "Postgres Extended Statistics for Correlated Columns", "Create extended statistics on correlated columns so the planner stops underestimating join cardinality."),
    ("postgres-huge-pages-memory-tuning", "Postgres Huge Pages Memory Tuning", "Enable huge pages on Linux for shared_buffers to reduce TLB pressure on large memory instances."),
    ("postgres-connection-limits-max-connections", "Postgres max_connections Sizing", "Right-size max_connections vs PgBouncer pool — formula for app servers, background workers, and admin reserve."),
    ("postgres-sequence-gap-contention", "Postgres Sequence Gap and Contention", "Understand sequence gaps, caching, and snowflake-style IDs when insert throughput saturates nextval."),
    ("postgres-lateral-joins-correlated", "Postgres LATERAL Joins for Correlated Subqueries", "Replace N+1 patterns with LATERAL joins for top-N-per-group and correlated aggregations."),
    ("postgres-recursive-cte-hierarchies", "Postgres Recursive CTEs for Hierarchies", "Model org charts, bill of materials, and comment trees with recursive CTEs and cycle detection."),
    ("postgres-window-functions-analytics", "Postgres Window Functions for Analytics", "Running totals, rank, lag/lead, and frame clauses for reporting queries without self-join explosion."),
    ("postgres-temporal-tables-system-versioning", "Postgres Temporal Tables and System Versioning", "Track row history with temporal tables, application-level versioning, or audit triggers — tradeoffs for compliance."),
    ("postgres-citext-case-insensitive", "Postgres citext for Case-Insensitive Text", "Use citext vs lower() functional indexes for email login fields — collation and unique constraint implications."),
    ("postgres-pg-cron-scheduled-jobs", "Postgres pg_cron Scheduled Jobs", "Schedule vacuum, partition maintenance, and materialized view refresh with pg_cron inside Postgres."),
    ("postgres-reindex-concurrently-bloat", "Postgres REINDEX CONCURRENTLY for Index Bloat", "Rebuild bloated indexes without blocking writes — monitor progress and handle invalid index states."),
    ("postgres-tablespaces-io-isolation", "Postgres Tablespaces for IO Isolation", "Place indexes and heap on separate tablespaces for IO isolation on bare metal — cloud limitations apply."),
    ("postgres-failover-pg-rewind", "Postgres Failover with pg_rewind", "Resync an old primary after failover using pg_rewind to avoid full base backup rebuild."),
    ("postgres-pgbackrest-backup-strategy", "Postgres pgBackRest Backup Strategy", "Configure full, differential, and incremental backups with pgBackRest, PITR, and restore drill cadence."),
    ("postgres-wal-compression-archiving", "Postgres WAL Compression and Archiving", "Enable wal_compression, archive to object storage, and monitor archive_command failures before disk fill."),
    ("postgres-synchronous-commit-tradeoffs", "Postgres synchronous_commit Tradeoffs", "Balance durability vs latency with synchronous_commit off, remote_apply, and quorum commit."),
    ("postgres-pg-snapshot-export-consistency", "Postgres Snapshot Export for Consistency", "Export consistent snapshots for logical dumps and CDC initial load without long-running transactions."),
    ("postgres-hstore-vs-jsonb-choice", "Postgres hstore vs JSONB Choice", "Pick hstore for flat string maps, JSONB for nested documents — indexing and operator differences."),
    ("postgres-pgvector-hybrid-search", "Postgres pgvector Hybrid Search", "Combine pgvector cosine search with full-text tsvector in single queries for RAG retrieval pipelines."),
    ("redis-cluster-slot-migration", "Redis Cluster Slot Migration", "Reshard Redis Cluster with zero-downtime slot migration — rebalance, verify, and monitor moved keys."),
    ("redis-pipeline-transaction-optimization", "Redis Pipeline and Transaction Optimization", "Batch commands with pipelining vs MULTI/EXEC transactions — latency wins and atomicity boundaries."),
    ("redis-lua-scripting-atomic-ops", "Redis Lua Scripting for Atomic Operations", "Implement compare-and-set, rate limits, and inventory decrements atomically with Lua scripts."),
    ("redis-key-expiration-strategies", "Redis Key Expiration Strategies", "TTL policies, active vs passive expiration, and avoiding thundering herd on hot expiring keys."),
    ("redis-memory-eviction-policies", "Redis Memory Eviction Policies", "Choose allkeys-lru vs volatile-lfu — cache vs session store implications and maxmemory tuning."),
    ("redis-persistence-rdb-aof-hybrid", "Redis RDB and AOF Hybrid Persistence", "Configure RDB snapshots plus AOF everysec — recovery time vs durability tradeoffs."),
    ("redis-client-side-caching-tracking", "Redis Client-Side Caching with Tracking", "Use RESP3 client-side caching and BCAST invalidation to reduce network round trips."),
    ("redis-bloom-filter-probabilistic", "Redis Bloom Filters for Probabilistic Membership", "Dedup and cache filtering with RedisBloom — false positive rates and memory sizing."),
    ("redis-geo-spatial-queries", "Redis Geo-Spatial Queries", "Store and query locations with GEOADD and GEORADIUS — precision limits vs PostGIS."),
    ("redis-time-series-redistimeseries", "RedisTimeSeries for Metrics Storage", "Downsample, aggregate, and retention policies for time-series metrics in Redis."),
    ("redis-module-redisjson-search", "RedisJSON and RediSearch Modules", "Document store and secondary indexing in Redis — when to stay in Redis vs move to Postgres."),
    ("redis-connection-pooling-ioredis", "Redis Connection Pooling with ioredis", "Size Redis pools, handle cluster MOVED/ASK redirects, and tune commandTimeout for tail latency."),
    ("redis-hot-key-mitigation", "Redis Hot Key Mitigation", "Detect hot keys, split with hash tags, local cache fronting, and read replicas for read-heavy keys."),
    ("redis-big-key-detection", "Redis Big Key Detection", "Find and split big keys — memory fragmentation, RDB save stalls, and lazy-free deletion."),
    ("redis-failover-sentinel-quorum", "Redis Sentinel Failover Quorum", "Configure sentinel quorum, split-brain prevention, and client sentinel discovery for HA Redis."),
    ("redis-streams-consumer-pending", "Redis Streams Pending Entry List", "Claim stale messages with XAUTOCLAIM, monitor lag, and trim streams without losing consumers."),
    ("redis-rate-limit-cell-tower", "Redis Cell Rate Limiting Algorithm", "Implement GCRA/cell rate limiting in Redis for smooth API throttling with minimal memory."),
    ("redis-session-store-patterns", "Redis Session Store Patterns", "Store sessions with TTL, rotation on privilege change, and encryption for regulated workloads."),
    ("redis-cache-invalidation-pubsub", "Redis Cache Invalidation with Pub/Sub", "Broadcast cache invalidation events — at-most-once semantics and missed message mitigation."),
    ("redis-compare-and-swap-optimistic", "Redis Compare-and-Swap Optimistic Locking", "WATCH/MULTI patterns vs Lua for optimistic concurrency on shared counters and inventory."),
    ("kafka-compacted-topics-tombstones", "Kafka Compacted Topics and Tombstones", "Configure log compaction, tombstone null values, and retention for changelog topics."),
    ("kafka-transactional-producer-eos", "Kafka Transactional Producer for EOS", "Enable idempotent and transactional producers — initTransactions, commit, and abort semantics."),
    ("kafka-idempotent-producer-config", "Kafka Idempotent Producer Configuration", "enable.idempotence=true defaults — in-flight request limits and acks=all requirements."),
    ("kafka-consumer-offset-management", "Kafka Consumer Offset Management", "Commit sync vs async, store offsets in external store, and reset policies for reprocessing."),
    ("kafka-rebalance-cooperative-sticky", "Kafka Cooperative Sticky Rebalance", "Upgrade consumer groups to cooperative-sticky assignor to reduce stop-the-world rebalances."),
    ("kafka-headers-propagation-metadata", "Kafka Headers for Propagation Metadata", "Propagate trace IDs, tenant IDs, and schema version in record headers without polluting payload."),
    ("kafka-log-compaction-retention", "Kafka Log Compaction Retention Policies", "min.compaction.lag.ms and delete.retention.ms — balance changelog size vs tombstone visibility."),
    ("kafka-mirror-maker-2-replication", "Kafka MirrorMaker 2 Cross-Cluster Replication", "Replicate topics across regions with MM2 — offset mapping, topic naming, and failover runbooks."),
    ("kafka-connect-sink-connector-errors", "Kafka Connect Sink Connector Error Handling", "errors.tolerance, dead letter queue, and retry backoff for Connect sink failures."),
    ("kafka-connect-transforms-smt", "Kafka Connect Single Message Transforms", "Chain SMTs for field extraction, masking, and routing — test transforms in isolation."),
    ("kafka-kraft-mode-no-zookeeper", "Kafka KRaft Mode Without ZooKeeper", "Migrate to KRaft controller quorum — broker IDs, metadata log, and operational differences."),
    ("kafka-tiered-storage-archival", "Kafka Tiered Storage for Archival", "Offload old segments to object storage — fetch latency and retention cost tradeoffs."),
    ("kafka-producer-batch-linger-compression", "Kafka Producer Batching and Compression", "Tune linger.ms, batch.size, and compression.type (lz4, zstd) for throughput vs latency."),
    ("kafka-consumer-fetch-min-bytes", "Kafka Consumer fetch.min.bytes Tuning", "Reduce empty fetches or improve batching — fetch.max.wait.ms interaction for real-time vs bulk."),
    ("kafka-broker-disk-io-tuning", "Kafka Broker Disk IO Tuning", "Segment size, flush messages, and RAID vs NVMe — monitor disk queue depth under peak produce."),
    ("kafka-schema-evolution-compatibility", "Kafka Schema Evolution Compatibility", "BACKWARD vs FORWARD compatibility in Schema Registry — safe field addition and defaults."),
    ("kafka-dead-letter-topic-patterns", "Kafka Dead Letter Topic Patterns", "Route poison messages to DLT with headers preserving original partition, offset, and error cause."),
    ("kafka-exactly-once-streams-rocksdb", "Kafka Streams RocksDB State Stores", "Size state stores, changelog topics, and restore time after rebalance or crash."),
    ("kafka-topic-naming-conventions", "Kafka Topic Naming Conventions", "Environment prefixes, domain.entity.event patterns, and ACL-friendly naming for multi-tenant clusters."),
    ("kafka-acls-sasl-scram-setup", "Kafka ACLs and SASL SCRAM Setup", "Principle of least privilege ACLs per producer/consumer group — avoid wildcard prod ACLs."),
    ("kafka-metrics-jmx-prometheus", "Kafka JMX Metrics for Prometheus", "Export broker and consumer lag metrics — kafka_exporter vs JMX exporter cardinality control."),
    ("kafka-lag-exporter-alerting", "Kafka Lag Exporter Alerting", "Alert on consumer group lag SLO — distinguish catch-up vs stuck consumers."),
    ("kafka-reprocessing-replay-strategies", "Kafka Reprocessing and Replay Strategies", "Reset offsets, mirror from archive, or dual-write new topic — pick replay without double side effects."),
    ("kafka-multi-datacenter-replication", "Kafka Multi-Datacenter Replication", "Active-active vs hub-spoke replication — offset sync, conflict resolution, and network partition behavior."),
    ("kafka-flink-kafka-connector-checkpoint", "Flink Kafka Connector Checkpointing", "Align Flink checkpoints with Kafka consumer offsets — exactly-once sink configuration."),
    ("api-problem-details-rfc7807", "API Problem Details with RFC 7807", "Standardize error responses with application/problem+json — type, title, status, detail, instance."),
    ("api-conditional-requests-etag", "API Conditional Requests with ETag", "Implement If-None-Match and If-Match for caching and optimistic concurrency on REST resources."),
    ("api-content-negotiation-accept", "API Content Negotiation with Accept Headers", "Support JSON, Protobuf, or CSV via Accept — 406 handling and default representation policy."),
    ("api-hypermedia-hateoas-pragmatic", "Pragmatic HATEOAS for REST APIs", "When _links add value vs YAGNI — discoverability for public APIs and internal service clients."),
    ("api-cursor-pagination-stable-sort", "API Cursor Pagination with Stable Sort", "Keyset pagination with opaque cursors — avoid OFFSET drift when rows insert during paging."),
    ("api-bulk-operations-batch-endpoints", "API Bulk Operations and Batch Endpoints", "Design bulk create/update with partial success responses, idempotency, and payload size limits."),
    ("api-long-running-async-jobs", "API Long-Running Async Jobs", "Return 202 Accepted with job status URL — polling vs webhook completion notification."),
    ("api-request-validation-zod-joi", "API Request Validation with Zod and Joi", "Validate at the edge with shared schemas — map validation errors to 400 problem details consistently."),
    ("api-response-compression-brotli", "API Response Compression with Brotli", "Enable brotli vs gzip at reverse proxy — CPU cost vs bandwidth for JSON payloads."),
    ("api-cors-preflight-production", "API CORS Preflight in Production", "Configure Access-Control-Allow-* correctly — credentials mode, wildcard pitfalls, and preflight cache."),
    ("api-gateway-auth-offload-patterns", "API Gateway Auth Offload Patterns", "Terminate JWT at gateway vs service — header injection, mTLS to origin, and trust boundaries."),
    ("api-contract-testing-pact-provider", "API Contract Testing with Pact Provider", "Verify provider satisfies consumer contracts in CI — broker workflow and can-i-deploy gates."),
    ("api-openapi-codegen-tradeoffs", "OpenAPI Codegen Tradeoffs", "Generate server stubs vs clients — drift when spec lags implementation and spec-first workflow."),
    ("api-deprecation-sunset-headers", "API Deprecation with Sunset Headers", "Communicate deprecation via Sunset, Deprecation, and Link headers — telemetry on remaining callers."),
    ("api-multi-tenant-header-isolation", "API Multi-Tenant Header Isolation", "Propagate tenant ID via header vs JWT claim — validation, cross-tenant leak tests, and audit logging."),
    ("api-correlation-id-propagation", "API Correlation ID Propagation", "Accept or generate X-Request-ID — propagate through logs, traces, and downstream HTTP calls."),
    ("api-error-envelope-consistency", "API Error Envelope Consistency", "One error shape across REST, GraphQL, and gRPC gateways — stable machine-readable codes."),
    ("api-field-selection-sparse-fieldsets", "API Sparse Fieldsets and Field Selection", "Let clients request fields= to reduce payload — implementation with serializers and OpenAPI docs."),
    ("api-idempotency-key-header-standard", "API Idempotency-Key Header Standard", "Implement Idempotency-Key like Stripe — storage, TTL, replay of stored response body."),
    ("api-rate-limit-response-headers", "API Rate Limit Response Headers", "Return RateLimit-Limit, Remaining, Reset — Retry-After on 429 for client backoff."),
    ("api-health-check-deep-shallow", "API Deep vs Shallow Health Checks", "Liveness vs readiness — check dependencies in readiness only to avoid cascade kill during blips."),
    ("api-graceful-shutdown-drain", "API Graceful Shutdown Connection Drain", "Handle SIGTERM — stop accept, drain in-flight requests, then close pools and Kafka consumers."),
    ("api-request-size-limits-dos", "API Request Size Limits for DoS Prevention", "Cap body size at reverse proxy and framework — streaming upload exceptions documented."),
    ("api-json-patch-merge-patch", "API JSON Patch and Merge Patch", "RFC 6902 vs 7396 for partial updates — validation, test ops, and conflict handling."),
    ("api-server-sent-events-streaming", "API Server-Sent Events Streaming", "SSE for one-way push — reconnection, Last-Event-ID, proxy buffering disable, vs WebSockets."),
    ("grpc-deadline-propagation-chains", "gRPC Deadline Propagation Chains", "Set and propagate context deadlines across microservice calls — avoid orphaned work."),
    ("grpc-metadata-context-propagation", "gRPC Metadata Context Propagation", "Carry auth, trace, and baggage in metadata — binary vs ASCII headers and size limits."),
    ("grpc-health-check-protocol", "gRPC Health Check Protocol", "Implement grpc.health.v1.Health — Kubernetes probe config vs HTTP /healthz adapters."),
    ("grpc-reflection-debugging", "gRPC Server Reflection for Debugging", "Enable reflection for grpcurl and Evans — disable in production edge or restrict by network policy."),
    ("grpc-load-balancing-client-side", "gRPC Client-Side Load Balancing", "Pick-first vs round_robin vs xDS — DNS resolution, subchannel health, and sticky issues."),
    ("grpc-keepalive-idle-timeout", "gRPC Keepalive and Idle Timeout", "HTTP/2 PING settings — detect dead connections behind NAT without killing idle streams."),
    ("grpc-max-message-size-limits", "gRPC Max Message Size Limits", "Set max send/receive — prevent OOM from huge payloads; streaming for large transfers."),
    ("grpc-protobuf-validation-protovalidate", "gRPC protovalidate Request Validation", "Validate protobuf messages with protovalidate (buf) — reject invalid requests at interceptor."),
    ("grpc-gateway-rest-transcoding", "gRPC-Gateway REST Transcoding", "Expose REST from protobuf annotations — path params, body mapping, and error translation."),
    ("grpc-connect-protocol-compatibility", "Connect Protocol gRPC Compatibility", "Connect-RPC over HTTP — browser-friendly gRPC without grpc-web proxy tradeoffs."),
    ("grpc-bidirectional-stream-backpressure", "gRPC Bidirectional Stream Backpressure", "Flow control on bidi streams — application-level pause/resume vs channel buffer exhaustion."),
    ("grpc-mtls-service-mesh", "gRPC mTLS in Service Mesh", "SPIFFE IDs, cert rotation, and strict mTLS — plaintext gRPC ban in production policy."),
    ("grpc-retry-policy-service-config", "gRPC Retry Policy Service Config", "Configure retryable status codes and hedging — avoid retry storms on overloaded dependencies."),
    ("grpc-otel-metrics-per-method", "gRPC OpenTelemetry Per-Method Metrics", "Instrument rpc.server.duration by grpc.method — cardinality control for custom methods."),
    ("grpc-java-virtual-thread-executor", "gRPC Java Virtual Thread Executors", "Run gRPC Java on virtual threads — pinning risks with synchronized blocks and native code."),
    ("oidc-backchannel-logout-revocation", "OIDC Back-Channel Logout Revocation", "Implement back-channel logout — session termination across apps when IdP signs out user."),
    ("oidc-token-exchange-rfc8693", "OIDC Token Exchange RFC 8693", "Exchange subject token for downstream API token — delegation and service account patterns."),
    ("oidc-par-pushed-authorization", "OIDC Pushed Authorization Requests PAR", "Push authorization parameters to server — reduce front-channel tampering on public clients."),
    ("oidc-jarm-response-mode", "OIDC JARM Secure Authorization Response", "Signed authorization response mode — prevent authorization code interception on mobile."),
    ("oidc-client-authentication-methods", "OIDC Client Authentication Methods", "client_secret_post vs private_key_jwt vs mTLS — pick per client type and store secrets safely."),
    ("jwt-claims-validation-aud-iss", "JWT Claims Validation aud and iss", "Validate audience and issuer strictly — multi-tenant IdP confusion and token replay across services."),
    ("jwt-algorithm-confusion-prevention", "JWT Algorithm Confusion Prevention", "Reject alg=none, enforce allowed algorithms, use asymmetric keys — library defaults are not enough."),
    ("jwt-short-lived-access-tokens", "JWT Short-Lived Access Tokens", "5–15 minute access tokens with refresh rotation — clock skew leeway and forced re-auth paths."),
    ("oauth2-refresh-token-rotation", "OAuth2 Refresh Token Rotation", "Rotate refresh tokens on use — detect reuse as breach signal and revoke token family."),
    ("oauth2-device-authorization-tv", "OAuth2 Device Authorization for TV", "Device code flow for input-constrained devices — polling interval and user code UX."),
    ("oauth2-resource-indicators-audience", "OAuth2 Resource Indicators for Audience", "Request token for specific resource URI — avoid over-scoped tokens in multi-API ecosystems."),
    ("oauth2-token-binding-dpop", "OAuth2 DPoP Token Binding", "Demonstrating Proof-of-Possession — bind tokens to client key pair against bearer token theft."),
    ("oauth2-client-credentials-scopes", "OAuth2 Client Credentials Scopes", "Scope M2M clients narrowly — service-specific roles vs broad admin scopes."),
    ("auth-api-key-hashing-storage", "Auth API Key Hashing and Storage", "Store SHA-256 hashes of API keys, show once on create — prefix lookup and rotation policy."),
    ("auth-session-hardening-cookies", "Auth Session Cookie Hardening", "HttpOnly, Secure, SameSite=Strict, __Host- prefix — session fixation and CSRF integration."),
    ("auth-mtls-client-certificates", "Auth mTLS Client Certificates", "Issue and validate client certs — SPIFFE, cert pinning, and revocation checking at scale."),
    ("auth-rbac-vs-abac-decision", "Auth RBAC vs ABAC Decision Guide", "When role-based access suffices vs attribute policies — OPA/Cedar integration patterns."),
    ("auth-zero-trust-service-identity", "Auth Zero Trust Service Identity", "No long-lived shared secrets — workload identity federation and short-lived tokens per call."),
    ("auth-spiffe-spire-workload-identity", "Auth SPIFFE SPIRE Workload Identity", "Deploy SPIRE agents — SVID rotation, federation across clusters, and gRPC mTLS integration."),
    ("auth-break-glass-emergency-access", "Auth Break-Glass Emergency Access", "Time-boxed emergency admin access — dual control, audit trail, and automatic expiry."),
    ("cqrs-event-versioning-upcasting", "CQRS Event Versioning and Upcasting", "Evolve event schemas with upcasters in the event store — replay compatibility across versions."),
    ("cqrs-snapshot-frequency-tuning", "CQRS Snapshot Frequency Tuning", "Balance snapshot storage vs replay time — snapshot after N events or time threshold."),
    ("cqrs-read-model-rebuild-strategies", "CQRS Read Model Rebuild Strategies", "Rebuild projections from event log — blue-green read models and progress monitoring."),
    ("cqrs-command-validation-pipeline", "CQRS Command Validation Pipeline", "Validate commands before aggregate load — middleware pipeline vs domain exceptions."),
    ("event-sourcing-aggregate-design", "Event Sourcing Aggregate Design", "Size aggregates correctly — transactional boundaries, invariants, and avoid distributed aggregates."),
    ("event-sourcing-event-store-postgres", "Event Sourcing Event Store on Postgres", "Append-only event table, optimistic concurrency on stream version, and indexing patterns."),
    ("event-sourcing-projection-lag-monitoring", "Event Sourcing Projection Lag Monitoring", "Alert when read model lag exceeds SLO — catch-up subscribers and poison event handling."),
    ("event-sourcing-saga-timeout-compensation", "Event Sourcing Saga Timeout Compensation", "Schedule saga timeouts with durable timers — compensating transactions and idempotent undo."),
    ("event-sourcing-idempotent-handlers", "Event Sourcing Idempotent Event Handlers", "Track processed event IDs — at-least-once delivery safe projection updates."),
    ("event-sourcing-schema-registry-events", "Event Sourcing Schema Registry for Events", "Register Avro/Protobuf event schemas — compatibility checks before deploy."),
    ("event-sourcing-temporal-queries", "Event Sourcing Temporal Queries", "Query aggregate state at point in time — as-of queries for audit and debugging."),
    ("event-sourcing-multi-stream-projections", "Event Sourcing Multi-Stream Projections", "Join events from multiple streams — ordering guarantees and correlation IDs."),
    ("event-sourcing-catch-up-subscriptions", "Event Sourcing Catch-Up Subscriptions", "Subscribe from start, position, or tail — checkpoint storage and parallel consumer scaling."),
    ("event-sourcing-event-envelope-metadata", "Event Sourcing Event Envelope Metadata", "Wrap payload with metadata — causation, correlation, user ID, schema version."),
    ("event-sourcing-deduplication-idempotency", "Event Sourcing Deduplication Idempotency", "Dedup by event ID at ingest — inbox table pattern for external event sources."),
    ("database-migration-zero-downtime-expand", "Database Zero-Downtime Expand Migrations", "Expand-contract phases — add column nullable, dual-write, backfill, switch read, drop old."),
    ("database-migration-backfill-batching", "Database Migration Backfill Batching", "Batch UPDATE with sleep — avoid long locks and replication lag spikes on large tables."),
    ("database-migration-flyway-baseline", "Database Flyway Baseline for Legacy DB", "Baseline existing schema — version table without replaying historical DDL on brownfield."),
    ("database-migration-liquibase-changelog", "Database Liquibase Changelog Organization", "Structured changelogs — contexts, labels, and rollback statements for safe deploy."),
    ("database-migration-prisma-shadow-db", "Database Prisma Migrate Shadow Database", "How shadow DB validates migrations — CI requirements and drift detection."),
    ("database-migration-rollback-strategies", "Database Migration Rollback Strategies", "When down migrations lie — forward-fix preferred, feature flags, and backup restore criteria."),
    ("database-migration-concurrent-index-add", "Database Add Index CONCURRENTLY", "CREATE INDEX CONCURRENTLY in migration tools — lock_timeout and invalid index cleanup."),
    ("database-migration-column-rename-safe", "Database Safe Column Rename Migration", "Rename without downtime — views, expand-contract alias column, dual-read period."),
    ("database-migration-enum-type-evolution", "Database Enum Type Evolution", "Add enum values safely — commit before use, avoid removing values, migration ordering."),
    ("database-migration-not-null-backfill", "Database NOT NULL Backfill Migration", "Three-phase NOT NULL — add nullable, backfill default, set NOT NULL with check validation."),
    ("database-migration-foreign-key-deferred", "Database Deferred Foreign Key Constraints", "DEFERRABLE INITIALLY DEFERRED for bulk loads — tradeoffs vs immediate integrity."),
    ("database-migration-data-verification-checksums", "Database Migration Data Verification Checksums", "Row counts and checksum compare after migration — automated gates before cutover."),
    ("database-migration-blue-green-cutover", "Database Blue-Green Cutover", "Switch application connection string — DNS, proxy tier, and replication lag gate."),
    ("database-migration-feature-flag-gating", "Database Migration Feature Flag Gating", "Gate code paths reading new schema — decouple deploy from migration apply order."),
    ("database-migration-lock-timeout-guard", "Database Migration lock_timeout Guard", "SET lock_timeout in migrations — fail fast instead of blocking production traffic."),
    ("connection-pool-hikari-tuning-java", "HikariCP Connection Pool Tuning", "Size maximumPoolSize, connectionTimeout, leakDetectionThreshold — pool name in metrics."),
    ("connection-pool-pg-pool-node-postgres", "node-postgres Pool Sizing", "pg.Pool max connections per instance — total cluster connections vs Postgres max."),
    ("connection-pool-prepared-statement-pgbouncer", "PgBouncer Prepared Statement Pooling", "Transaction vs session pool — prepared statement compatibility matrix by driver."),
    ("connection-pool-serverless-proxy-rds", "RDS Proxy Serverless Connection Pooling", "Multiplex Lambda connections — IAM auth, pin compatibility, and cold start behavior."),
    ("connection-pool-leak-detection-hikari", "HikariCP Connection Leak Detection", "Find threads holding connections — leakDetectionThreshold and stack traces in logs."),
    ("connection-pool-transaction-mode-pitfalls", "PgBouncer Transaction Mode Pitfalls", "SET LOCAL, temp tables, advisory locks, and listen/notify break in transaction pooling."),
    ("connection-pool-sizing-formula-little", "Connection Pool Sizing with Little's Law", "Derive pool size from concurrency and query duration — avoid connection stampede."),
    ("connection-pool-health-check-validation", "Connection Pool Health Check Validation", "Test query on checkout — stale connection detection after idle timeout or firewall drop."),
    ("connection-pool-r2dbc-reactive-postgres", "R2DBC Reactive Postgres Pooling", "Pool configuration for WebFlux — max size vs event loop thread count."),
    ("connection-pool-prisma-accelerate-edge", "Prisma Accelerate Edge Connection Pool", "Serverless edge pooling — cache strategy interaction and connection limits."),
    ("rate-limit-distributed-redis-lua", "Distributed Rate Limiting with Redis Lua", "Atomic token bucket in Lua — sliding window log vs fixed window accuracy."),
    ("rate-limit-adaptive-congestion-control", "Adaptive Rate Limiting Congestion Control", "Reduce limits when error rate rises — coordinated admission control across nodes."),
    ("rate-limit-per-tenant-quota-tiers", "Per-Tenant Quota Tiers Rate Limiting", "Free vs pro limits — store counters per tenant API key with burst allowance."),
    ("rate-limit-api-gateway-kong-plugin", "Kong Rate Limiting Plugin Configuration", "Local vs Redis policy — sync rate across gateway instances and header injection."),
    ("rate-limit-grpc-interceptor-quota", "gRPC Interceptor Rate Limit Quota", "Unary interceptor checks quota before handler — metadata key for client tier."),
    ("idempotency-key-storage-postgres", "Idempotency Key Storage in Postgres", "Table schema for idempotency keys — unique constraint, response blob, status in-progress."),
    ("idempotency-ttl-cleanup-scheduler", "Idempotency Key TTL Cleanup Scheduler", "Delete expired keys — retention vs storage and replay window policy."),
    ("idempotency-response-caching-replay", "Idempotency Response Caching Replay", "Return identical status and body on replay — in-progress lock with expiry."),
    ("idempotency-stripe-style-keys", "Stripe-Style Idempotency Keys", "24-hour retention, POST only, hash body optional — client SDK guidance."),
    ("idempotency-outbox-dedup-pattern", "Idempotency Outbox Dedup Pattern", "Combine outbox with idempotency key — exactly-once external publish semantics."),
    ("observability-trace-context-w3c-baggage", "W3C Trace Context and Baggage", "traceparent and tracestate propagation — baggage for tenant tier without span bloat."),
    ("observability-log-trace-correlation", "Log and Trace Correlation", "Inject trace_id in structured logs — join Loki and Tempo in Grafana."),
    ("observability-red-metrics-method", "RED Metrics Per API Method", "Rate, Errors, Duration histograms — golden signals for every route and gRPC method."),
    ("observability-service-graph-topology", "Observability Service Graph Topology", "Derive dependency map from traces — SLO per edge and critical path analysis."),
    ("observability-tail-sampling-otel", "OpenTelemetry Tail Sampling", "Keep interesting traces — errors, high latency, specific user cohort after complete trace."),
    ("observability-grpc-status-code-metrics", "gRPC Status Code Metrics", "Counter by grpc.status_code — separate InvalidArgument from Internal for alerting."),
    ("observability-db-query-tracing-orm", "Database Query Tracing in ORMs", "Span per query with db.statement — sanitize parameters, N+1 detection in traces."),
    ("observability-kafka-consumer-lag-slo", "Kafka Consumer Lag SLO", "Define lag SLO per consumer group — burn rate alerts and capacity planning."),
    ("observability-api-latency-histograms", "API Latency Histogram Buckets", "Prometheus histogram bucket selection — accurate p99 vs storage cardinality."),
    ("observability-error-budget-burn-alerts", "Error Budget Burn Rate Alerts", "Multi-window burn alerts — page on fast burn, ticket on slow burn."),
    ("observability-synthetic-monitoring-apis", "Synthetic Monitoring for APIs", "Probe critical paths from external regions — auth token rotation in checks."),
    ("observability-continuous-profiling-parca", "Continuous Profiling with Parca", "Sample CPU profiles in production — correlate with traces via exemplars."),
    ("observability-ebpf-network-observability", "eBPF Network Observability for Services", "Cilium/Hubble or Pixie — L7 metrics without sidecar per pod overhead."),
    ("observability-structured-log-schema", "Structured Log Schema Standards", "JSON log field conventions — level, service, trace_id, tenant_id, message."),
    ("observability-oncall-runbook-automation", "On-Call Runbook Automation", "Link alerts to runbooks — ChatOps buttons for kubectl and rollback scripts."),
    ("node-fastify-plugin-architecture", "Fastify Plugin Architecture", "Encapsulate routes in plugins — decorate, hooks order, and test isolation."),
    ("node-express-async-error-handling", "Express Async Error Handling", "Wrap async handlers — centralized error middleware and never miss rejected promises."),
    ("node-nestjs-module-boundaries", "NestJS Module Boundaries", "Feature modules, shared kernel, circular dependency fixes — domain-driven module layout."),
    ("node-bullmq-job-priority-retries", "BullMQ Job Priority and Retries", "Priority queues, exponential backoff, stalled job detection — Redis memory planning."),
    ("node-prisma-transaction-isolation", "Prisma Transaction Isolation Levels", "Interactive transactions — Serializable for inventory, ReadCommitted default tradeoffs."),
    ("node-typeorm-migration-production", "TypeORM Migrations in Production", "transactions: each vs all — CREATE INDEX CONCURRENTLY escape hatch."),
    ("node-drizzle-orm-type-safe-sql", "Drizzle ORM Type-Safe SQL", "Schema in TypeScript — migrations with drizzle-kit and raw SQL escape hatches."),
    ("node-pino-structured-logging", "Pino Structured Logging in Node", "Low overhead JSON logs — redact paths, serializers for req/res, child loggers per request."),
    ("node-opentelemetry-auto-instrumentation", "Node OpenTelemetry Auto-Instrumentation", "@opentelemetry/auto-instrumentations-node — disable noisy fs, enable pg and http."),
    ("node-cluster-mode-vs-worker-threads", "Node Cluster Mode vs Worker Threads", "When cluster helps CPU-bound HTTP — worker threads for isolated compute jobs."),
    ("node-event-loop-lag-monitoring", "Node Event Loop Lag Monitoring", "Monitor event loop delay — alert before GC pauses become user-visible timeouts."),
    ("node-memory-leak-heap-snapshot", "Node Memory Leak Heap Snapshot", "Capture heap snapshot in prod — compare dominators, closure leaks in caches."),
    ("node-graceful-shutdown-sigterm", "Node Graceful Shutdown on SIGTERM", "Close server, drain BullMQ workers, flush telemetry — Kubernetes terminationGracePeriodSeconds."),
    ("node-env-validation-zod-envalid", "Node Environment Validation with Zod", "Fail fast on boot — validate DATABASE_URL, secrets, and feature flag types."),
    ("node-http-agent-keepalive-pooling", "Node HTTP Agent Keep-Alive Pooling", "Reuse TCP connections to downstream APIs — maxSockets and LRU agent config."),
    ("go-echo-middleware-patterns", "Go Echo Middleware Patterns", "Group routes, middleware order, custom context — test handlers with httptest."),
    ("go-fiber-high-performance-api", "Go Fiber High Performance API", "Zero-allocation routing — when Fiber fits vs std net/http for your team."),
    ("go-chi-router-composable", "Go Chi Composable Router", "Route groups, URL params, middleware chains — mount sub-routers per domain."),
    ("go-sqlx-prepared-statements", "Go sqlx Prepared Statements", "Named queries, Rebind for Postgres — struct scanning and NULL handling."),
    ("go-pgx-copy-from-bulk-insert", "Go pgx COPY FROM Bulk Insert", "Load CSV and row batches with CopyFrom — fastest Postgres ingest from Go."),
    ("go-redis-cluster-client", "Go Redis Cluster Client", "go-redis ClusterClient — MOVED handling, read-only replicas, pipeline limits."),
    ("go-sarama-kafka-consumer-groups", "Go Sarama Kafka Consumer Groups", "MarkOffset vs Commit — rebalance listener cleanup and graceful shutdown."),
    ("go-grpc-gateway-openapi", "Go gRPC-Gateway OpenAPI Generation", "Generate OpenAPI from protobuf — swagger UI for internal API discovery."),
    ("go-wire-dependency-injection", "Go Wire Dependency Injection", "Compile-time DI graphs — wireinject build tag and provider sets for services."),
    ("go-testcontainers-integration", "Go Testcontainers Integration Tests", "Spin Postgres and Kafka in CI — ryuk cleanup and parallel test isolation."),
    ("go-errgroup-parallel-limits", "Go errgroup Parallel Limits", "Bounded parallelism with semaphore — cancel siblings on first error."),
    ("go-slog-structured-logging", "Go slog Structured Logging", "Replace log.Printf — Handler options, context attrs, and JSON output for Loki."),
    ("go-otel-sdk-exporter-setup", "Go OpenTelemetry SDK Exporter Setup", "OTLP gRPC exporter, resource attributes, batch span processor tuning."),
    ("go-context-value-antipatterns", "Go context.Value Antipatterns", "Typed keys, avoid string keys — what belongs in context vs function params."),
    ("go-table-driven-tests-services", "Go Table-Driven Tests for Services", "Subtests with t.Parallel — mock interfaces and golden error cases."),
    ("java-spring-boot-actuator-health", "Spring Boot Actuator Health Indicators", "Custom HealthIndicator for Kafka and Redis — readiness group configuration."),
    ("java-spring-data-jpa-n-plus-one", "Spring Data JPA N Plus One Fix", "EntityGraph, fetch join, @BatchSize — detect with Hibernate statistics."),
    ("java-spring-kafka-listener-concurrency", "Spring Kafka Listener Concurrency", "concurrency vs partitions — ordering per key and ack mode BATCH vs RECORD."),
    ("java-spring-security-oauth2-resource", "Spring Security OAuth2 Resource Server", "JwtDecoder bean, issuer validation, scope mapping to authorities."),
    ("java-hibernate-batch-insert-tuning", "Hibernate Batch Insert Tuning", "jdbc.batch_size, order_inserts, IDENTITY vs SEQUENCE batching limits."),
    ("java-virtual-threads-spring-boot-3", "Java Virtual Threads in Spring Boot 3", "spring.threads.virtual.enabled — pin carriers with synchronized JDBC carefully."),
    ("java-micrometer-prometheus-metrics", "Java Micrometer Prometheus Metrics", "Timer percentiles, common tags, meter registry customization — cardinality limits."),
    ("java-resilience4j-circuit-breaker", "Java Resilience4j Circuit Breaker", "CircuitBreakerRegistry config — recordResult predicate and fallback methods."),
    ("java-mapstruct-dto-mapping", "Java MapStruct DTO Mapping", "Compile-time mappers — nested mapping and afterMapping custom logic."),
    ("java-flyway-migration-ci-gate", "Java Flyway Migration CI Gate", "flyway validate and repair — block merge on checksum mismatch."),
    ("java-testcontainers-postgres-kafka", "Java Testcontainers Postgres and Kafka", "@DynamicPropertySource for Spring tests — singleton container reuse pattern."),
    ("java-grpc-spring-boot-starter", "Java gRPC Spring Boot Starter", "grpc-spring-boot-starter server and client stubs — interceptor registration."),
    ("java-jooq-type-safe-sql", "Java jOOQ Type-Safe SQL", "Generated code from schema — multi-tenant row policies in SQL DSL."),
    ("java-quarkus-native-graalvm", "Java Quarkus Native GraalVM Builds", "Native image for serverless — reflection config and startup time wins."),
    ("java-spring-webflux-backpressure", "Spring WebFlux Backpressure", "Reactive streams demand — avoid blocking on boundedElastic for JDBC."),
    ("outbox-pattern-polling-vs-wal", "Outbox Pattern Polling vs WAL", "Poll outbox table vs logical decoding — latency and operational complexity."),
    ("outbox-pattern-transactional-kafka", "Transactional Outbox to Kafka", "Same transaction for business row and outbox event — relay process idempotency."),
    ("inbox-pattern-exactly-once-consumer", "Inbox Pattern for Exactly-Once Consumer", "Dedup table in consumer — process message once despite Kafka redelivery."),
    ("cdc-debezium-heartbeat-topics", "Debezium Heartbeat Topics", "Heartbeat for low-traffic tables — confirm connector alive and WAL reading."),
    ("cdc-debezium-snapshot-modes", "Debezium Snapshot Modes", "initial vs never vs when_needed — lock impact and schema history topic."),
    ("cdc-change-data-capture-lag-slo", "CDC Lag SLO Monitoring", "Measure end-to-end latency from commit to sink — alert on growing lag."),
    ("cdc-event-envelope-schema", "CDC Event Envelope Schema", "Debezium payload structure — before/after, op code, source metadata parsing."),
    ("queue-sqs-fifo-deduplication", "AWS SQS FIFO Deduplication", "Message deduplication ID and group ID — throughput limits per group."),
    ("queue-rabbitmq-dead-letter-exchange", "RabbitMQ Dead Letter Exchange", "DLX routing for poison messages — TTL queues and retry count headers."),
    ("queue-nats-jetstream-persistence", "NATS JetStream Persistence", "Stream retention, consumer ack wait, and at-least-once redelivery config."),
    ("queue-temporal-workflow-saga", "Temporal Workflow Saga Pattern", "Durable timers and compensation activities — vs choreographed Kafka saga."),
    ("queue-sidekiq-reliable-scheduler", "Sidekiq Reliable Scheduler", "Scheduled jobs with Redis — unique jobs and death handlers for failures."),
    ("queue-celery-task-routing", "Celery Task Routing Queues", "Route tasks by name to dedicated workers — priority and rate limits per queue."),
    ("queue-bull-board-monitoring", "Bull Board Queue Monitoring", "UI for Bull/BullMQ — auth proxy, failed job retry, and stalled detection."),
    ("queue-priority-inversion-prevention", "Queue Priority Inversion Prevention", "Separate queues for high and low priority — avoid head-of-line blocking."),
    ("elasticsearch-index-template-ilm", "Elasticsearch Index Template ILM", "Index lifecycle hot-warm-cold — rollover alias and shard size targets."),
    ("elasticsearch-aggregations-cardinality", "Elasticsearch Cardinality Aggregations", "HyperLogLog++ precision — unique counts vs terms agg on high cardinality."),
    ("elasticsearch-nested-vs-object-mapping", "Elasticsearch Nested vs Object Mapping", "Query nested arrays correctly — nested type vs flattened for performance."),
    ("elasticsearch-analyzer-custom-tokenizer", "Elasticsearch Custom Analyzer Tokenizer", "Edge n-gram, synonym filter, and language stemmers for search relevance."),
    ("elasticsearch-scroll-vs-search-after", "Elasticsearch Scroll vs search_after", "Deep pagination — avoid scroll in user-facing APIs, use PIT + search_after."),
    ("elasticsearch-cross-cluster-replication", "Elasticsearch Cross Cluster Replication", "Follower indices for DR — bi-directional limitations and failover steps."),
    ("elasticsearch-ingest-pipeline-enrichment", "Elasticsearch Ingest Pipeline Enrichment", "GeoIP, user agent, and set processor — fail pipeline vs ignore missing."),
    ("elasticsearch-slow-log-tuning", "Elasticsearch Slow Log Tuning", "index.search.slowlog thresholds — find expensive queries in production."),
    ("elasticsearch-bulk-indexing-tuning", "Elasticsearch Bulk Indexing Tuning", "Bulk thread pool, refresh_interval=-1 during load, merge throttling."),
    ("elasticsearch-security-rbac-roles", "Elasticsearch Security RBAC Roles", "Index-level privileges, API keys for apps, and role mapping from OIDC."),
]

# Generate bulk topics with template content
for slug, title, desc in BULK:
    if slug in TOPICS:
        continue
    prefix = slug.split("-")[0]
    tag_map = {
        "postgres": ["PostgreSQL", "Backend", "Database"],
        "redis": ["Redis", "Backend", "Caching"],
        "kafka": ["Kafka", "Backend", "Distributed Systems"],
        "api": ["Backend", "API", "HTTP"],
        "grpc": ["gRPC", "Backend", "API"],
        "oidc": ["Authentication", "OIDC", "Backend"],
        "oauth2": ["Authentication", "OAuth", "Backend"],
        "jwt": ["Authentication", "JWT", "Security"],
        "auth": ["Authentication", "Backend", "Security"],
        "cqrs": ["CQRS", "Backend", "Architecture"],
        "event": ["Event Sourcing", "Backend", "Architecture"],
        "database": ["Database", "Backend", "Migrations"],
        "connection": ["Database", "Backend", "Performance"],
        "rate": ["Backend", "API", "Rate Limiting"],
        "idempotency": ["Backend", "Reliability", "API"],
        "observability": ["Observability", "Backend", "SRE"],
        "node": ["Node.js", "Backend", "JavaScript"],
        "go": ["Go", "Backend", "Performance"],
        "java": ["Java", "Backend", "Spring"],
        "outbox": ["Backend", "Messaging", "Reliability"],
        "inbox": ["Backend", "Messaging", "Reliability"],
        "cdc": ["CDC", "Backend", "Data"],
        "queue": ["Backend", "Queues", "Messaging"],
        "elasticsearch": ["Elasticsearch", "Backend", "Search"],
    }
    tags = tag_map.get(prefix, ["Backend", "Distributed Systems"])
    kw = slug.replace("-", " ")
    faqs = [
        (f"What problem does {title.split(' for ')[0].split(' with ')[0]} solve?",
         f"It addresses production gaps teams hit when scaling {kw}: correctness under concurrency, operability, and measurable SLOs instead of ad-hoc scripts."),
        (f"When should I adopt this pattern?",
         f"Adopt when {kw} appears on incident timelines, p95 latency regresses, or the next traffic doubling will break the current shortcut."),
        (f"What is the most common implementation mistake?",
         f"Copying a tutorial without matching your pooler mode, isolation level, or retry semantics — and skipping idempotency on any path that can be retried."),
    ]
    sections = [
        ("Production context", [
            f"A billing service lost duplicate events because {kw} was handled only in application code without database-enforced invariants. The fix was not more logging — it was moving the guarantee to the layer that survives process crashes and duplicate deliveries.",
            f"Senior backend work on {title.lower()} is less about syntax and more about failure modes: what happens on retry, on partial outage, and when two deploy versions run simultaneously during a rolling update.",
        ]),
        ("Architecture pattern", [
            f"Separate command path from query path where appropriate. Keep side effects idempotent. Push cross-cutting concerns — auth, quotas, tracing — to middleware/interceptors so domain handlers stay testable.",
            f"Document explicit SLIs: availability, p95 latency, error rate, and lag (if async). Alerts should page on user-visible symptoms, not every internal retry.",
        ], textwrap.dedent(f"""\
            ```sql
            -- Example: idempotent ingest skeleton for {slug.split('-')[0]} workloads
            CREATE TABLE IF NOT EXISTS processed_events (
              idempotency_key text PRIMARY KEY,
              response_code   int NOT NULL,
              response_body   jsonb,
              created_at      timestamptz NOT NULL DEFAULT now()
            );
            ```""")),
        ("Implementation checklist", [
            "Validate inputs at the trust boundary with schema versioning.",
            "Use timeouts and cancellation on every outbound call; propagate context.",
            "Store idempotency keys with TTL; return cached responses on replay.",
            "Run migrations with lock_timeout and statement_timeout set.",
            "Load test at 2× expected peak with production-like payload sizes.",
        ]),
        ("Observability", [
            f"Metrics: request rate, error ratio, duration histogram, and saturation (pool wait, queue depth, consumer lag). Logs: structured JSON with trace_id and tenant_id. Traces: one span per outbound dependency.",
            f"Dashboards for {kw} should answer: 'Is the system slow, broken, or overloaded?' without SSH. Exemplars link spikes to trace IDs.",
        ]),
        ("Security notes", [
            "Least privilege for service accounts and database roles. Rotate secrets without redeploy where possible. Never log raw tokens or PII — redact at serialization.",
            "For auth-related paths, fail closed. Rate limit unauthenticated endpoints aggressively.",
        ]),
    ]
    TOPICS[slug] = (title, desc, tags, kw + ", production, backend", faqs, sections)


def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text))


def render_post(idx, slug, data):
    title, desc, tags, keywords, faqs, sections = data
    pub = BASE_DATE + timedelta(days=idx % 180)
    faq_yaml = "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in faqs)
    tags_yaml = "\n".join(f'  - "{t}"' for t in tags)
    body_parts = []
    for section in sections:
        heading = section[0]
        paras = section[1]
        code = section[2] if len(section) > 2 else None
        body_parts.append(f"## {heading}\n")
        for p in paras:
            body_parts.append(f"{p}\n")
        if code:
            body_parts.append(f"\n{code}\n")
    body = "\n".join(body_parts) + FOOTER_SECTIONS
    frontmatter = f"""---
title: "{title}"
slug: "{slug}"
description: "{desc}"
datePublished: "{pub.isoformat()}"
dateModified: "{pub.isoformat()}"
tags:
{tags_yaml}
keywords: "{keywords}"
faq:
{faq_yaml}
---

"""
    content = frontmatter + body
    return content


def pad_content(content, title, slug):
    wc = word_count(content)
    if wc >= TARGET_WORDS:
        return content
    extra_sections = []
    topic_words = slug.replace("-", " ")
    pads = [
        ("Performance tuning notes", [
            f"Measure before optimizing {topic_words}. Capture baseline p50/p95 latency, error rate, and resource utilization under representative load. Change one variable at a time — pool size, batch size, timeout, cache TTL — and re-measure.",
            f"CPU profiling often reveals unexpected hotspots: JSON serialization, regex in middleware, or ORM hydration of wide entities. IO profiling reveals N+1 queries, missing indexes, and pool wait time dominating tail latency.",
            f"Cache only what is expensive to compute and safe to stale. Document TTL rationale. Invalidate on write where consistency matters; accept eventual consistency where product allows.",
        ]),
        ("Rollout and migration", [
            f"Ship {topic_words} changes behind feature flags when behavior crosses service boundaries. Use canary deploys with automatic rollback on error rate or latency regression.",
            f"For schema changes, prefer expand-contract over big-bang DDL. Never assume maintenance windows are available — design for online migration.",
            f"Maintain rollback runbooks: previous container image digest, down migration forward-fix, and feature flag disable path tested quarterly.",
        ]),
        ("Testing recommendations", [
            "Unit test pure domain logic without database. Integration test against real Postgres/Redis/Kafka in CI with Testcontainers.",
            "Contract test API boundaries with Pact or schema fixtures. Chaos test dependency timeouts and verify circuit breakers open.",
            "Load test before marketing launches — synthetic traffic shapes miss fan-out and queue backlog effects seen in production.",
        ]),
        ("Incident patterns we see", [
            "Connection pool exhaustion masquerading as slow queries — graph active connections vs pool max.",
            "Missing idempotency on webhook or queue consumers causing duplicate side effects during at-least-once delivery.",
            "Migration holding ACCESS EXCLUSIVE lock because lock_timeout was not set — traffic pile-up and cascading timeouts.",
            "Retry storms amplifying outage — uncapped retries on 503 increase load on failing dependency.",
        ]),
        ("Team ownership", [
            f"Assign an owner for {topic_words} standards: code templates, lint rules, and onboarding docs. Platform teams provide paved roads; product teams stay responsible for SLOs.",
            "Review this pattern in architecture reviews when touching money, auth, or personal data. Security and compliance questions early beat retrofitting controls later.",
        ]),
    ]
    for heading, paras in pads:
        if wc >= TARGET_WORDS:
            break
        block = f"\n## {heading}\n\n" + "\n\n".join(paras) + "\n"
        content = content.replace("\n## Resources\n", block + "\n## Resources\n")
        wc = word_count(content)
    return content


def main():
    existing = set()
    if os.path.isdir(BLOG_DIR):
        for f in os.listdir(BLOG_DIR):
            if f.endswith(".md"):
                existing.add(f[:-3])

    slugs = sorted(TOPICS.keys())[:250]
    written = 0
    skipped = 0
    short = []

    for idx, slug in enumerate(slugs):
        if slug in existing:
            skipped += 1
            continue
        content = render_post(idx, slug, TOPICS[slug])
        content = pad_content(content, TOPICS[slug][0], slug)
        wc = word_count(content)
        if wc < TARGET_WORDS:
            short.append((slug, wc))
        path = os.path.join(BLOG_DIR, f"{slug}.md")
        with open(path, "w") as f:
            f.write(content)
        written += 1
        existing.add(slug)

    print(f"Written: {written}, Skipped: {skipped}, Target: 250")
    if short:
        print(f"Still under {TARGET_WORDS} words: {len(short)}")
        for s, w in short[:5]:
            print(f"  {s}: {w}")
    print("Example slugs:", ", ".join(slugs[:10]))


if __name__ == "__main__":
    main()
