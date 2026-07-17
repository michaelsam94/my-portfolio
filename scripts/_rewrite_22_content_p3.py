# Part 3: Vitest + Timeseries (4)

POSTS = {}

POSTS["testing-vitest-react-testing-library"] = (
    {
        "title": "Testing React with Vitest",
        "description": "Vitest brings fast unit testing to React with native ESM support, Jest-compatible API, and instant HMR. Pair it with Testing Library for behavior-focused component tests.",
        "datePublished": "2026-01-26",
        "tags": ["Testing", "React", "Vitest", "Frontend"],
        "keywords": "Vitest React testing, React Testing Library, Vitest vs Jest, component testing React, Vitest configuration, userEvent testing",
        "faq": [
            {
                "q": "Should I use Vitest or Jest for a new React project?",
                "a": "Use Vitest if your project uses Vite (which most new React projects do). Vitest shares Vite's config, transform pipeline, and ESM support — tests start instantly with native TypeScript. Use Jest if you're on Create React App (Webpack), need specific Jest-only plugins, or have an existing Jest suite you don't want to migrate. Vitest's API is Jest-compatible, so migration is mostly config changes.",
            },
            {
                "q": "What should I test in a React component?",
                "a": "Test behavior users experience: does clicking Submit send the form? Does an error message appear on invalid input? Does loading state show while fetching? Don't test implementation details — state variable names, internal hook calls, component structure. If a refactor changes internal state management but the UI behavior is identical, tests should still pass.",
            },
            {
                "q": "How do I test components that fetch data?",
                "a": "Mock the fetch/API layer with MSW (Mock Service Worker) or vi.mock(). Render the component, let it fetch mocked data, assert on rendered output. Use findBy queries (async) for data that loads after render. Test three states: loading, success, and error. Don't mock React hooks — mock the data source the hooks call.",
            },
        ],
    },
    r"""Migrating our React test suite from Jest to Vitest cut cold start from fourteen seconds to about 1.2 seconds. Not because individual tests ran faster — assertion time is similar — but because Vitest reuses Vite's already-warm transform pipeline instead of booting a separate Babel config. With eight hundred component tests, twelve seconds is the difference between running on every save and skipping until CI. Vitest plus Testing Library is the default stack for Vite React apps in 2026; the setup is small, the patterns are stable.

## Configuration

```bash
npm install -D vitest @testing-library/react @testing-library/jest-dom \
  @testing-library/user-event jsdom @vitejs/plugin-react
```

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
    },
  },
});
```

```typescript
// src/test/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

One config for dev server and tests — no duplicate module resolution or alias definitions.

## Behavior-focused component tests

```tsx
// Counter.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Counter } from "./Counter";

test("increments on click", async () => {
  const user = userEvent.setup();
  render(<Counter />);
  await user.click(screen.getByRole("button", { name: /increment/i }));
  expect(screen.getByText(/count: 1/i)).toBeInTheDocument();
});
```

Query priority: **role → label → text → test id**. `getByRole("button", { name: "Save" })` mirrors accessibility.

## Async data with MSW

```typescript
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const server = setupServer(
  http.get("/api/profile", () => HttpResponse.json({ name: "Ada" }))
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("shows profile name", async () => {
  render(<ProfilePage />);
  expect(await screen.findByText("Ada")).toBeInTheDocument();
});
```

Use **`findBy`** for async appearance; **`waitFor`** for complex conditions.

## Mocking modules with vi.mock

```typescript
import { vi } from "vitest";

vi.mock("./analytics", () => ({
  track: vi.fn(),
}));

import { track } from "./analytics";

test("tracks checkout", async () => {
  // render and complete checkout
  expect(track).toHaveBeenCalledWith("checkout_complete");
});
```

Hoist mocks carefully — import mocked module after `vi.mock`. Prefer MSW over mocking fetch globally when testing components.

## Testing hooks

Use **`@testing-library/react`** `renderHook`:

```typescript
import { renderHook, act } from "@testing-library/react";
import { useCounter } from "./useCounter";

test("increments", () => {
  const { result } = renderHook(() => useCounter());
  act(() => result.current.increment());
  expect(result.current.count).toBe(1);
});
```

Extract hook logic worth unit testing; do not re-test every hook through full component tree.

## Vitest vs Jest migration notes

| Jest | Vitest |
|------|--------|
| `jest.fn()` | `vi.fn()` |
| `jest.mock` | `vi.mock` |
| `jest.spyOn` | `vi.spyOn` |
| `--watch` | `vitest` (default watch) |

Replace `@types/jest` with Vitest globals in tsconfig:

```json
{ "compilerOptions": { "types": ["vitest/globals"] } }
```

## CI

```json
{ "scripts": { "test": "vitest", "test:ci": "vitest run --coverage" } }
```

`vitest run` exits with code 1 on failure — suitable for CI. Shard large suites: `vitest run --shard=1/4`.

## Common pitfalls

- Using **`fireEvent`** instead of **`userEvent`** — prefer userEvent for realistic interaction.
- Not awaiting async updates — flaky tests.
- Testing CSS classes instead of visible outcomes.
- **`vi.mock` entire React** — never.

Vitest removes friction from running tests often. Testing Library keeps those tests aligned with what users do. Together they make component tests fast enough to be habitual, not ceremonial.""",
)

POSTS["timeseries-downsampling-retention"] = (
    {
        "title": "Downsampling and Retention Policies",
        "description": "Design downsampling and retention policies for time-series data: tiered rollups, continuous aggregates, storage math, and query patterns that keep historical telemetry fast and cheap.",
        "datePublished": "2026-02-01",
        "tags": ["Data", "Databases", "Time Series", "Architecture"],
        "keywords": "downsampling, retention policy, time series, continuous aggregates, TimescaleDB, Prometheus, telemetry storage",
        "faq": [
            {
                "q": "Why downsample time-series data instead of keeping full resolution forever?",
                "a": "Raw metrics at 15-second scrape intervals generate terabytes over years. Dashboards querying month-long ranges rarely need second-level precision. Downsampling rollups to hourly or daily aggregates cut storage 100–1000x while preserving trend analysis. Keep raw data for recent windows where incident debugging needs full resolution.",
            },
            {
                "q": "What retention tiers should most observability stacks use?",
                "a": "A common pattern: 15 days raw at full scrape interval, 90 days at 5-minute rollups, 1–2 years at hourly rollups, optional daily aggregates for capacity planning beyond that. Align tiers with on-call needs — engineers rarely zoom sub-minute on six-month-old graphs.",
            },
            {
                "q": "How do continuous aggregates differ from batch downsampling jobs?",
                "a": "Continuous aggregates (TimescaleDB, Materialize) incrementally maintain rollup tables as new data arrives. Batch jobs recompute windows on schedule — simpler but laggy and expensive at scale. Continuous aggregates trade setup complexity for fresher rollups and predictable ingest cost.",
            },
        ],
    },
    r"""The metrics cluster hit 94% disk at 3 AM because someone set `--storage.tsdb.retention.time=10y` on a 15-second scrape interval without doing storage math. Two million series × 4 bytes × 8640 samples/day × 3650 days is not a rounding error. Downsampling and retention policies are not archival nostalgia — they are the difference between querying last quarter in seconds and finance approving a petabyte budget.

## Storage math

Rough samples per series per day:

```
86400 seconds / scrape_interval_seconds = samples/day

Example: 15s scrape → 5,760 samples/day/series
1M series → 5.76B samples/day
```

With **2 bytes sample + overhead**, raw cost explodes. Rollups collapse time dimension:

| Tier | Resolution | Retention | Use case |
|------|------------|-----------|----------|
| Hot | 15s–1m | 7–15 days | Incident debugging |
| Warm | 5m | 30–90 days | Weekly SLO review |
| Cold | 1h | 1–2 years | Capacity trends |
| Archive | 1d | 5+ years | Finance, compliance |

## Prometheus native retention

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

storage:
  tsdb:
    retention.time: 15d
    retention.size: 50GB
```

Prometheus local TSDB is hot tier only — pair with remote write for warm/cold (see remote write post). Recording rules pre-aggregate before remote storage:

```yaml
groups:
  - name: rollups
    interval: 5m
    rules:
      - record: instance:node_cpu:rate5m
        expr: avg by (instance) (rate(node_cpu_seconds_total[5m]))
```

## TimescaleDB continuous aggregates

```sql
CREATE MATERIALIZED VIEW cpu_hourly
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', time) AS bucket,
  host,
  avg(cpu_pct) AS avg_cpu,
  max(cpu_pct) AS max_cpu
FROM metrics
GROUP BY bucket, host;

SELECT add_continuous_aggregate_policy('cpu_hourly',
  start_offset => INTERVAL '3 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');
```

Retention policies drop chunks:

```sql
SELECT add_retention_policy('metrics', INTERVAL '15 days');
SELECT add_retention_policy('cpu_hourly', INTERVAL '2 years');
```

Hypertable **compression** after 7 days further reduces storage — columnar compression on cold chunks.

## Query routing

Application or Grafana routes by time range:

```
if range <= 15d → raw hypertable / Prometheus
if range <= 90d → 5m rollup
else → hourly/daily
```

Automatic routing prevents accidental full-table scans on billion-row tables.

## Downsampling algorithms

| Method | Best for |
|--------|----------|
| avg | Gauges (CPU, memory) |
| max | Peaks (latency p99 proxy) |
| sum | Counters over interval |
| last | Gauge state at bucket end |

**Never average averages** without sample counts — use sum/count for correct global average.

## InfluxDB downsampling (conceptual)

Tasks downsample buckets to coarser retention buckets on schedule. Align task interval with bucket duration to avoid gaps.

## Operational checklist

- Model storage growth before enabling new high-cardinality labels.
- Alert on disk usage trend, not just threshold.
- Test query latency on cold tier quarterly.
- Document which dashboards require raw tier — migrate queries that do not.

Downsampling is lossy by design — lose sub-minute spikes in year-old data. That is acceptable when tier boundaries match how humans actually investigate old incidents. Keep raw hot, rollups honest, and retention explicit in runbooks.""",
)

POSTS["timeseries-influxdb-vs-timescale"] = (
    {
        "title": "InfluxDB vs TimescaleDB",
        "description": "A practical comparison of InfluxDB and TimescaleDB for time-series workloads: query models, ingest patterns, operational trade-offs, and when each engine fits.",
        "datePublished": "2026-02-03",
        "tags": ["Data", "Databases", "Time Series", "Architecture"],
        "keywords": "InfluxDB, TimescaleDB, time series database, Flux, SQL, hypertable, comparison",
        "faq": [
            {
                "q": "When should I choose InfluxDB over TimescaleDB?",
                "a": "Choose InfluxDB when your workload is metrics-native — high-cardinality tag/field ingest, built-in downsampling tasks, and you accept Flux or InfluxQL instead of SQL. Strong fit for greenfield observability pipelines and IoT telemetry with line protocol ingest.",
            },
            {
                "q": "When is TimescaleDB the better fit?",
                "a": "Choose TimescaleDB when you already run Postgres, need JOINs with relational data, want standard SQL tooling, or must combine time-series with transactional workloads. Hypertables, compression, and continuous aggregates extend Postgres without a separate query language.",
            },
            {
                "q": "Can I migrate from InfluxDB to TimescaleDB easily?",
                "a": "Not trivially — data models differ. Influx uses measurement, tags, and fields; TimescaleDB uses standard relational tables, often with a timestamp column and JSONB for flexible attributes. You'll need an ETL pipeline that maps tag/field semantics to relational columns. Plan for a parallel-run period where both systems ingest simultaneously before cutting over queries.",
            },
        ],
    },
    r"""The platform team debated InfluxDB vs TimescaleDB for six weeks. Observability engineers wanted line protocol and native rollups; product analytics wanted SQL JOINs with the users table. We ran both in staging with identical synthetic load. Influx won ingest ergonomics for pure metrics; Timescale won whenever someone asked "show revenue per region alongside error rate." The right database is not universal — it is the one whose query model matches who will write the queries.

## Data models

**InfluxDB (v2/v3 conceptual):**

```
measurement: http_request
tags: { service="api", status="500", region="us-east" }
fields: { latency_ms=42, bytes=1024 }
timestamp: 2026-07-17T10:00:00Z
```

Tags indexed for filter; fields hold values. High cardinality on tags is foot-gun.

**TimescaleDB:**

```sql
CREATE TABLE http_request (
  time TIMESTAMPTZ NOT NULL,
  service TEXT NOT NULL,
  status INT NOT NULL,
  region TEXT,
  latency_ms DOUBLE PRECISION,
  bytes INT
);
SELECT create_hypertable('http_request', 'time');
```

Looks like Postgres because it is — **hypertable** partitions by time under the hood.

## Query languages

Influx: **Flux** (or InfluxQL legacy):

```flux
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "http_request")
  |> filter(fn: (r) => r.status == "500")
  |> aggregateWindow(every: 5m, fn: mean)
```

Timescale: **SQL**:

```sql
SELECT time_bucket('5 minutes', time) AS bucket,
       avg(latency_ms)
FROM http_request
WHERE status = 500 AND time > now() - INTERVAL '1 hour'
GROUP BY bucket
ORDER BY bucket;
```

If your org hiring pool is SQL-heavy, Timescale reduces bus factor.

## Ingest paths

| Path | Influx | Timescale |
|------|--------|-----------|
| Line protocol | Native | Via Telegraf/custom |
| Postgres COPY | No | Native |
| ORM (Prisma) | Awkward | Natural |
| Kafka stream | Consumer plugins | Logical decoding, CDC |

Influx shines at firehose metrics. Timescale shines at **metrics + app data in one database**.

## Operations

**InfluxDB Cloud / Enterprise** — managed scaling, op complexity traded for vendor path.

**Timescale** — runs on managed Postgres (Timescale Cloud, RDS + extension). Backup/replication reuse Postgres playbook.

Compression:

- Timescale: columnar compression policies on hypertable chunks
- Influx: engine-managed compaction and retention buckets

## Cardinality and cost

Both punish unbounded label/tag cardinality. Influx tags become index entries; Timescale indexes on `(service, status)` explode with high distinct values.

Mitigation:

- Drop high-cardinality labels at scrape (Prometheus relabel)
- Aggregate before write
- Separate high-cardinality traces from metrics stores

## Decision matrix

| Requirement | Lean |
|-------------|------|
| Pure metrics, IoT | Influx |
| SQL analytics + JOINs | Timescale |
| Existing Postgres ops | Timescale |
| Greenfield observability stack | Influx or Mimir + object store |
| Long-term SQL BI on metrics | Timescale |

## Hybrid pattern

Hot path: Prometheus → remote write → Mimir/Influx.

Cold analytics: ETL to Timescale or warehouse for JOIN with business tables.

Do not force one engine to solve relational reporting and sub-second dashboard queries simultaneously without tiering.

## Migration realism

Parallel ingest for 30 days, compare query results within epsilon, cut over Grafana datasources per dashboard. Map Influx tags to columns deliberately — `user_id` as tag will ruin either engine.

InfluxDB vs TimescaleDB is not a benchmark winner — it is a **model fit** question. Pick the query language and ops story your team will still maintain after the lead engineer leaves.""",
)

POSTS["timeseries-prometheus-remote-write"] = (
    {
        "title": "Long-Term Storage with Remote Write",
        "description": "Configure Prometheus remote write for durable long-term metrics storage: receiver options, relabeling, backpressure, downsampling, and query federation patterns.",
        "datePublished": "2026-02-05",
        "tags": ["Data", "Observability", "Prometheus", "Infrastructure"],
        "keywords": "Prometheus remote write, long-term storage, Thanos, Mimir, Cortex, VictoriaMetrics, metrics retention",
        "faq": [
            {
                "q": "Why does Prometheus need remote write for long-term storage?",
                "a": "Prometheus stores metrics in a local time-series database optimized for recent, high-resolution data. Its default retention is 15 days, and extending local retention increases memory and disk pressure on the scraper itself. Remote write ships samples to an external store designed for durability, compression, and long retention — freeing Prometheus to focus on scraping and alerting while history lives elsewhere.",
            },
            {
                "q": "What are the main remote write receiver options?",
                "a": "The most common receivers are Thanos Receive, Grafana Mimir, Cortex, and VictoriaMetrics. Thanos adds object-storage-backed blocks and a unified query layer. Mimir is Grafana's horizontally scalable, multi-tenant metrics backend. Cortex is the CNCF project Mimir forked from. VictoriaMetrics is a single-binary option with excellent compression. All accept Prometheus remote write protocol and integrate with Grafana for querying.",
            },
            {
                "q": "How do I handle remote write backpressure and data loss?",
                "a": "Prometheus buffers samples in a WAL-backed queue when the remote endpoint is slow or unavailable. Configure queue capacity and retry behavior in the remote_write block. Monitor the prometheus_remote_storage_samples_failed_total and prometheus_remote_storage_queue_highest_sent_timestamp_seconds metrics. If the queue fills, samples drop — so size the receiver for peak ingest and run it with redundancy. Never treat remote write as fire-and-forget without alerting on failures.",
            },
        ],
    },
    r"""Grafana dashboards for last year's Black Friday only worked on one engineer's laptop — the Prometheus PVC they never backed up. Everyone else had fifteen days of history because nobody configured remote write. Prometheus is a excellent **recent** metrics engine, not a durable archive. Remote write ships samples to systems built for replication, multi-tenant query, and object-storage economics. Treat local TSDB as cache; treat remote storage as truth for history.

## Architecture

```
Targets → Prometheus (hot 15d) ──remote_write──▶ Mimir / Thanos Receive / VM
                                                      │
                                                      ▼
                                              Object storage (S3/GCS)
                                                      │
Grafana ◀────────────── query federation ─────────────┘
```

Prometheus handles alerting on fresh data; long-range dashboards query the backend via **Grafana Mimir** datasource or **Thanos Query**.

## Basic configuration

```yaml
# prometheus.yml
remote_write:
  - url: https://mimir.example.com/api/v1/push
    headers:
      X-Scope-OrgID: team-platform
    queue_config:
      capacity: 10000
      max_shards: 50
      min_shards: 1
      max_samples_per_send: 5000
      batch_send_deadline: 5s
    metadata_config:
      send: true
    write_relabel_configs:
      - source_labels: [__name__]
        regex: "expensive_.*"
        action: drop
```

**write_relabel_configs** drop high-cardinality series before they leave Prometheus — cheaper than storing garbage remotely.

## Receiver comparison

| System | Strength | Complexity |
|--------|----------|------------|
| Mimir | Multi-tenant Grafana native | Medium-high |
| Thanos Receive | Unified query with sidecar | Medium |
| VictoriaMetrics | Compression, simple cluster | Low-medium |
| Cortex | Mature, CNCF | Medium-high |

Single-team self-host often starts VictoriaMetrics or Mimir single-tenant.

## Backpressure and data loss

Prometheus queues unsent samples in WAL-backed **remote storage queue**. Metrics to watch:

```
prometheus_remote_storage_samples_failed_total
prometheus_remote_storage_samples_pending
prometheus_remote_storage_queue_highest_sent_timestamp_seconds
```

If **`highest_sent_timestamp`** lags wall clock by minutes, receiver or network is saturated. If **`samples_failed_total`** increases, samples dropped — incident severity.

Mitigations:

- Scale receive ingesters horizontally
- Drop labels via relabel before write
- Increase queue shards cautiously (memory cost)
- Run redundant remote_write endpoints only with dedup strategy — dual write can duplicate

## HA Prometheus considerations

Two Prometheus instances scraping same targets produce duplicate series unless **external labels** differentiate them and query layer deduplicates:

```yaml
global:
  external_labels:
    cluster: prod-us-east
    replica: $(POD_NAME)
```

Thanos Query dedups on `replica` label; Mimir has similar patterns.

## Recording rules before remote write

Pre-aggregate expensive queries at Prometheus:

```yaml
- record: job:http_requests:rate5m
  expr: sum by (job) (rate(http_requests_total[5m]))
```

Ship aggregates remotely; keep raw high-cardinality local briefly.

## Query federation

Grafana datasources:

- **Prometheus** — last 15 days, alerting
- **Mimir/Thanos** — `-30d` to years

Use **query frontend** splitting time range across stores automatically in advanced setups, or document dashboard time-range limits per datasource.

## Security

- TLS + auth on remote write endpoint
- Tenant headers for multi-tenant backends
- Network policy restricting push to receive pods only

## Runbook snippets

**Remote write lagging:**

1. Check receiver ingest rate vs Prometheus `scrape_samples_post_metric_relabeling`.
2. Inspect receiver disk and ingester memory.
3. Temporarily increase drop rules for non-critical metrics.
4. Scale receive tier.

**After receiver outage:**

Gaps are permanent — Prometheus does not backfill unsent queue beyond retention. Accept hole or replay from alternate archive if exists.

Remote write connects short-term operational Prometheus to long-term metrics memory. Configure queues, monitor failures, relabel aggressively, and query federated — or accept that last year's SLO review has no graph.""",
)
