---
title: "AI Agents: Lineage Openlineage Marquez"
slug: "agent-lineage-openlineage-marquez"
description: "Lineage Openlineage Marquez: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-03-06"
dateModified: "2025-03-06"
tags: ["AI", "Agent", "Lineage"]
keywords: "agent, lineage, openlineage, marquez, ai, production, engineering, architecture"
faq:
  - q: "What is the difference between OpenLineage and Marquez?"
    a: "OpenLineage is the event specification and client libraries that emit lineage — who read which dataset, ran which job, wrote what output. Marquez is an open-source metadata service that collects those events, stores them, and exposes a UI and API for graph queries. You can emit OpenLineage to Marquez, DataHub, or a custom backend."
  - q: "Should agent RAG pipelines emit lineage per chunk or per document?"
    a: "Emit at document and job level for catalog clarity — source URI, embedding model version, chunk policy. Optionally attach chunk IDs as facets on the output dataset, not as separate nodes, or graphs become unreadable at billion-chunk scale."
  - q: "How do you lineage-track ephemeral LLM calls?"
    a: "Model inference is a job facet on the transformation that consumes prompts and produces structured outputs — not every token stream needs a dataset node. Record model name, prompt template hash, and tool schema version as run facets for audit without exploding graph size."
  - q: "When does lineage block a production deploy?"
    a: "Use lineage in CI to verify expected upstream datasets exist and downstream consumers are notified — not as a hard gate until coverage exceeds 80% of critical paths. Missing lineage on a new agent tool should warn in PR checks, not page on-call at 2 a.m."
---
An auditor asks which training documents fed the embedding index serving customer support agents. Engineering opens three spreadsheets, a Notion page, and a Slack thread from six months ago. Nobody can prove the retrieval corpus at inference time matches what compliance approved — because the RAG pipeline never emitted structured lineage, only unstructured logs.

OpenLineage standardizes how data jobs describe inputs, outputs, and run metadata. Marquez collects those events into a queryable graph: datasets, jobs, runs, and the edges between them. Together they give AI platform teams something batch ETL has had for years — a map of how raw documents become vectors, how agent tools write back to warehouses, and which model version touched which table on every run.

This article covers designing lineage for agent and RAG stacks, instrumenting emitters, operating Marquez in production, and avoiding graphs so noisy that nobody trusts them.

## The lineage model for agent pipelines

OpenLineage events are JSON documents with three core objects:

| Object | Represents | Agent/RAG example |
|--------|------------|-------------------|
| **Dataset** | Named data asset with namespace | `s3://corp-docs/support/` or `postgres://rag.public.chunks` |
| **Job** | Transformation logic | `embed-documents`, `sync-confluence`, `agent-tool-write-crm` |
| **Run** | Single execution of a job | Nightly embed job `run_id=8f3a…` with START/COMPLETE/FAIL |

Each run lists `inputs` and `outputs` dataset references. Facets extend the schema — SQL query text, column lineage, model parameters, custom tags — without breaking consumers.

For RAG, think in layers:

```
[Source docs] → [Ingest job] → [Raw staging]
     → [Chunk + embed job] → [Vector index dataset]
     → [Retrieval job at query time] → [Agent context facet]
     → [Tool side-effect jobs] → [CRM / ticket updates]
```

Query-time retrieval is lineage-sensitive: you need to record which index snapshot and filter policy were active, not just that "the agent answered." Attach retrieval config as run facets on the inference job rather than creating a new dataset per user question.

## Emitting OpenLineage from Python ETL

Use the official Python client or HTTP emitter. Example nightly embedding job:

```python
from openlineage.client.run import RunEvent, RunState, Run, Job, Dataset
from openlineage.client.serde import Serde
from openlineage.client.transport.http import HttpTransport
import os
import uuid

transport = HttpTransport(
    url=os.environ["MARQUEZ_URL"],
    endpoint="api/v1/lineage",
)

def emit(state: RunState, run_id: str, rows_written: int):
    event = RunEvent(
        eventType=state,
        eventTime=datetime.utcnow().isoformat() + "Z",
        run=Run(runId=run_id),
        job=Job(
            namespace="rag.platform",
            name="embed-support-docs",
        ),
        inputs=[
            Dataset(
                namespace="s3",
                name="corp-docs/support/raw",
                facets={
                    "documentation": {"description": "Approved support KB exports"}
                },
            )
        ],
        outputs=[
            Dataset(
                namespace="postgres",
                name="rag.public.document_chunks",
                facets={
                    "schema": {
                        "fields": [
                            {"name": "chunk_id", "type": "uuid"},
                            {"name": "embedding", "type": "vector(1536)"},
                        ]
                    },
                    "dataSource": {"uri": os.environ["DATABASE_URL"]},
                },
            )
        ],
        producer="https://github.com/your-org/rag-ingest",
    )
    transport.emit(event)

run_id = str(uuid.uuid4())
emit(RunState.START, run_id, 0)
try:
    rows = run_embedding_pipeline()
    emit(RunState.COMPLETE, run_id, rows)
except Exception:
    emit(RunState.FAIL, run_id, 0)
    raise
```

Wrap every batch job, CDC consumer, and agent tool that mutates durable state. Streaming micro-batches can emit one COMPLETE per checkpoint with row counts in a custom facet.

## Marquez deployment and API usage

Marquez stores events in PostgreSQL and serves a React UI plus REST API. A minimal Kubernetes layout: Marquez API + UI deployment, Postgres StatefulSet, ingress with SSO.

Query lineage for a dataset:

```bash
curl -s "https://marquez.internal/api/v1/namespaces/postgres/datasets/rag.public.document_chunks" \
  | jq '.facets, .lastModifiedAt'
```

Trace upstream dependencies for impact analysis before dropping a column:

```bash
curl -s "https://marquez.internal/api/v1/lineage?nodeId=dataset:postgres:rag.public.document_chunks&depth=5"
```

Configure retention and compaction — run metadata accumulates fast when agent tools emit per-invocation events. Tier policies:

- **Batch jobs:** keep all runs 90 days, aggregate older into daily summaries.
- **High-frequency tools:** emit START/COMPLETE only on writes, sample reads at 1% with exemplar trace IDs linked in logs.

## Agent-specific facets worth standardizing

Define an internal facet schema so dashboards stay consistent:

```json
{
  "embeddingModel": {
    "name": "text-embedding-3-large",
    "dimensions": 1536,
    "version": "2025-01-15"
  },
  "chunkPolicy": {
    "maxTokens": 512,
    "overlap": 64,
    "splitter": "recursive-markdown"
  },
  "agentContext": {
    "retrievalTopK": 8,
    "indexSnapshot": "2025-03-05T04:00:00Z",
    "filterTags": ["support", "prod"]
  }
}
```

Record **prompt template hash** and **tool JSON schema version** on inference runs. When compliance asks what changed between March 1 and March 5, you diff facets — not raw prompts stored in lineage (avoid PII in the graph).

## Integrating with Airflow, Dagster, and dbt

Most orchestrators have OpenLineage adapters. Prefer adapter-maintained emitters over hand-rolled HTTP in every task — adapters handle run ID propagation and parent/child job nesting.

For dbt, enable OpenLineage in `dbt_project.yml`:

```yaml
models:
  +openlineage:
    namespace: "dbt.rag"
```

dbt emits column-level lineage for warehouse models that feed agent analytics. Combine with custom Python jobs for vector stores adapters do not cover.

## DataHub vs Marquez

Teams often ask whether to use Marquez or DataHub. Practical split:

- **Marquez** — lighter weight, purpose-built for OpenLineage graph visualization, quick to self-host.
- **DataHub** — broader catalog (ownership, glossary, quality assertions) with OpenLineage ingestion.

You can emit once to Kafka and fan out to both. Do not double-instrument jobs with separate custom trackers — one emitter, many consumers.

## Security, PII, and access control

Lineage graphs contain dataset names, URIs, and sometimes SQL — treat Marquez as **internal confidential**:

- SSO on UI and API; namespace-level RBAC for tenant isolation.
- Redact connection strings in facets; use logical names (`postgres://rag/chunks`) not credentials.
- Never attach raw user prompts or retrieved chunk text to events — store retrieval IDs referenceable from a secured audit store.
- Encrypt Postgres at rest; backup with same policy as warehouse metadata.

For GDPR erasure, lineage must not become an immutable PII ledger. Emit document IDs that can be tombstoned; when a user deletes data, run a compensating job that emits a `DatasetVersionDeleted` facet or your org's equivalent policy event.

## Testing lineage coverage

Add CI checks that fail when critical jobs lack emitters:

```python
# tests/test_lineage_coverage.py
CRITICAL_JOBS = [
    "rag.platform/embed-support-docs",
    "rag.platform/sync-tickets",
]

def test_emitter_registered():
    from ingest.registry import registered_jobs
    for job in CRITICAL_JOBS:
        assert job in registered_jobs, f"missing lineage for {job}"
```

In staging, run a full ingest and assert Marquez shows expected edges within 60 seconds. Contract-test event JSON against OpenLineage JSON Schema on each client upgrade.

## Operating Marquez in production

Monitor:

- **Emitter error rate** — HTTP 4xx/5xx from agents and batch workers.
- **Kafka consumer lag** if using async ingestion.
- **Postgres disk** — run table bloat and partition by month.
- **API p95** — impact analysis queries spike during incident response.

Runbooks should include "break glass" SQL to find all jobs downstream of a compromised S3 prefix — the query product managers actually need during incidents.

Game-day: disable an upstream export bucket and verify on-call can trace which agent tools and indexes depend on it within five minutes using Marquez UI or API.

## Common mistakes

**One node per chunk.** Billion-node graphs choke browsers. Aggregate at document or partition level.

**Lineage only in batch.** Agent tools that write CRM notes without emitters create blind spots — the highest-risk path for audit failure.

**Stale namespace conventions.** Mixed `s3://` and `aws:s3` namespaces duplicate datasets; enforce lint in CI.

**No run failure events.** Only emitting COMPLETE hides broken pipelines that silently stop — always emit FAIL with error facet.

## The takeaway

OpenLineage gives agent and RAG platforms a portable vocabulary for "what touched what." Marquez turns that stream into an operational graph for impact analysis, compliance, and onboarding. Start with batch ingest and vector index jobs, standardize facets for models and chunk policies, keep PII out of events, and expand coverage to agent tools that mutate production data. Lineage earns trust when it is complete on critical paths and readable at a glance — not when every token has a node.

## Resources

- [OpenLineage specification](https://openlineage.io/docs/) — event schema, facets, and integration guides
- [Marquez GitHub repository](https://github.com/MarquezProject/marquez) — server, UI, and Docker compose quickstart
- [OpenLineage Python client](https://github.com/OpenLineage/OpenLineage/tree/main/client/python) — emitters and transports
- [dbt OpenLineage integration](https://docs.getdbt.com/docs/collaborate/govern/model-contracts) — warehouse model lineage
- [DataHub OpenLineage ingestion](https://datahubproject.io/docs/metadata-ingestion/integration_docs/openlineage/) — fan-out to enterprise catalog
