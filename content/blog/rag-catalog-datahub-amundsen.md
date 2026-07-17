---
title: "RAG: Catalog Datahub Amundsen"
slug: "rag-catalog-datahub-amundsen"
description: "DataHub and Amundsen metadata catalogs help RAG teams discover which tables, documents, and embeddings exist—lineage from source to chunk, ownership, and freshness signals for retrieval quality."
datePublished: "2025-03-08"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Catalog"]
keywords: "DataHub, Amundsen, data catalog, RAG metadata, lineage, document discovery, embedding registry, data governance, knowledge base inventory"
faq:
  - q: "Why does a RAG pipeline need a data catalog?"
    a: "RAG corpora span dozens of source systems—Confluence, S3 buckets, Postgres tables, SharePoint libraries. Without a catalog, teams cannot answer which documents are indexed, who owns them, when they were last ingested, or what downstream retrieval collections depend on a given source. Catalogs make corpus inventory auditable."
  - q: "DataHub vs Amundsen for RAG metadata—which should I choose?"
    a: "DataHub (LinkedIn) has stronger real-time lineage, schema evolution tracking, and a richer API for programmatic ingestion—better for large teams with complex pipelines. Amundsen (Lyft) has simpler deployment and excellent search UX—better for smaller teams prioritizing discoverability over lineage depth. Both can model document-level assets for RAG."
  - q: "How do you model RAG-specific assets in a data catalog?"
    a: "Extend standard table/file entities with custom aspects: chunk_count, embedding_model_version, retrieval_collection_id, last_ingest_timestamp, and source_authorization_tier. Link source documents to derived chunk tables and vector index collections via lineage edges."
---
An engineer debugged a RAG hallucination by tracing the bad answer to a chunk sourced from a Confluence page last edited eighteen months ago. The page owner had left the company. Nobody knew the page was indexed because ingestion was automated and the corpus had grown to 400,000 documents across twelve source systems. There was no inventory, no ownership metadata, and no way to query "show me all HR documents older than one year in the retrieval index."

Data catalogs—DataHub and Amundsen being the two most widely deployed open-source options—solve the discoverability and governance gap that RAG pipelines create at scale. They were built for analytics data assets but adapt cleanly to document corpora, embedding registries, and retrieval collection metadata.

## The RAG metadata problem catalogs solve

RAG pipelines generate a derived asset graph:

```
Source systems → Ingestion jobs → Raw document store → Chunking → Embedding → Vector index → Retrieval collections
```

Each edge is a transformation. Each node has metadata that affects retrieval quality:

- **Source freshness** — stale documents produce stale answers
- **Ownership** — who approves reindex when source changes
- **Authorization tier** — which retrieval collections may include this source
- **Embedding model version** — reindex required when model changes
- **Lineage** — if upstream table changes, which chunks are affected

Without a catalog, this graph lives in tribal knowledge, scattered YAML configs, and ingestion job logs. Catalogs centralize it.

## DataHub architecture for RAG assets

[DataHub](https://datahubproject.io/) uses a metadata graph model with entities, aspects, and relationships ingested via REST API, Kafka, or Python SDK.

### Modeling document sources

Register each source system as a dataset entity:

```python
# ingestion/register_confluence_source.py
from datahub.emitter.mce_builder import make_dataset_urn
from datahub.emitter.rest_emitter import DatahubRestEmitter
from datahub.metadata.schema_classes import (
    DatasetPropertiesClass,
    GlobalTagsClass,
    TagAssociationClass,
)

emitter = DatahubRestEmitter(gms_server="http://datahub-gms:8080")

for space in confluence_spaces:
    urn = make_dataset_urn(platform="confluence", name=space.key, env="PROD")
    emitter.emit_mcp({
        "entityType": "dataset",
        "entityUrn": urn,
        "aspectName": "datasetProperties",
        "aspect": DatasetPropertiesClass(
            name=space.name,
            description=space.description,
            customProperties={
                "rag_collection": f"confluence-{space.key}",
                "authorization_tier": space.classification,
                "document_count": str(space.page_count),
            },
        ),
    })
```

### Custom aspects for RAG metadata

DataHub supports custom aspect schemas. Define RAG-specific metadata:

```yaml
# schemas/rag_corpus_aspect.yaml
aspectName: ragCorpusInfo
entityTypes:
  - dataset
fields:
  - name: chunkCount
    type: number
  - name: embeddingModelVersion
    type: string
  - name: lastIngestTimestamp
    type: string
  - name: retrievalCollectionIds
    type: array
    items: string
  - name: avgChunkTokens
    type: number
```

Attach to datasets after each ingestion run:

```python
emitter.emit_aspect(
    entity_urn=source_urn,
    aspect={
        "chunkCount": 12450,
        "embeddingModelVersion": "text-embedding-3-large-v1",
        "lastIngestTimestamp": "2026-07-15T08:00:00Z",
        "retrievalCollectionIds": ["general-kb", "engineering-runbooks"],
        "avgChunkTokens": 512,
    },
    aspect_name="ragCorpusInfo",
)
```

### Lineage from source to vector index

DataHub lineage connects upstream sources to downstream derived assets:

```python
from datahub.emitter.mce_builder import make_dataset_urn
from datahub.metadata.schema_classes import UpstreamClass, UpstreamLineageClass

source_urn = make_dataset_urn(platform="confluence", name="ENG", env="PROD")
chunk_table_urn = make_dataset_urn(platform="postgres", name="rag.chunks_confluence_eng", env="PROD")
index_urn = make_dataset_urn(platform="pinecone", name="prod/general-kb", env="PROD")

emitter.emit_aspect(
    entity_urn=chunk_table_urn,
    aspect=UpstreamLineageClass(upstreams=[
        UpstreamClass(dataset=source_urn, type="TRANSFORMED"),
    ]),
)

emitter.emit_aspect(
    entity_urn=index_urn,
    aspect=UpstreamLineageClass(upstreams=[
        UpstreamClass(dataset=chunk_table_urn, type="TRANSFORMED"),
    ]),
)
```

Now "what depends on this Confluence space?" is a graph query, not an archaeology expedition.

## Amundsen for RAG discoverability

[Amundsen](https://www.amundsen.io/) prioritizes search UX and simpler deployment. It models tables (and extensible resources) with descriptions, tags, owners, and programmatic descriptions.

### Extending Amundsen for document assets

Amundsen's databuilder framework ingests from custom extractors:

```python
# databuilder/extractors/rag_corpus_extractor.py
from databuilder.extractor.base_extractor import Extractor
from databuilder.models.table import Table, Column

class RagCorpusExtractor(Extractor):
    def init(self, conf):
        self.collections = load_rag_collections()

    def get_model_to_extract(self, record_iterator):
        for coll in self.collections:
            yield Table(
                database="rag",
                cluster="production",
                schema="corpus",
                name=coll.id,
                description=coll.description,
                tags=[coll.authorization_tier, f"model:{coll.embedding_version}"],
                owners=[Owner(email=coll.owner_email, label="owner")],
            )
            yield Column(
                database="rag", cluster="production", schema="corpus",
                table_name=coll.id,
                name="chunk_count",
                description=str(coll.chunk_count),
                col_type="integer",
            )
```

Users search "HR documents" in Amundsen UI and find the corpus entity with owner, last updated, and link to ingestion job.

## Operational workflows enabled by catalog integration

### Stale document audits

Query catalog for documents where `lastIngestTimestamp` > 90 days and `sourceLastModified` is older:

```sql
-- DataHub GraphQL or search API equivalent
SELECT urn, customProperties.source_url, ragCorpusInfo.lastIngestTimestamp
FROM datasets
WHERE platform = 'confluence'
  AND ragCorpusInfo.lastIngestTimestamp < NOW() - INTERVAL '90 days'
```

Feed results into reindex queue or owner notification workflow.

### Embedding model migration planning

When upgrading embedding model:

1. Query all datasets with `embeddingModelVersion != 'new-version'`
2. Lineage query finds affected vector index collections
3. Generate reindex job list with chunk counts for capacity forecasting
4. Track migration progress by updating aspect after each collection completes

### Authorization review

Map retrieval collections to source authorization tiers:

```
retrieval_collection "customer-support" 
  → sources: [confluence-CS (public), zendesk-articles (public)]
  → MUST NOT include: confluence-HR (confidential)
```

Catalog lineage makes incorrect inclusions visible during security review.

### Incident response

When a source system has bad data (incorrect policy page published):

1. Find dataset URN in catalog
2. Lineage query: which indexes contain chunks from this source?
3. Trigger targeted invalidation for those collections
4. Notify retrieval collection owners from catalog metadata

## Ingestion automation patterns

Keep catalog metadata fresh by wiring ingestion jobs to emit metadata:

```python
# ingestion/pipeline.py
async def ingest_collection(source_config: SourceConfig):
    chunks = await extract_and_chunk(source_config)
    await embed_and_index(chunks, source_config.collection_id)

    # Always update catalog after successful ingest
    await datahub_client.emit_rag_corpus_info(
        source_urn=source_config.urn,
        chunk_count=len(chunks),
        embedding_model_version=EMBEDDING_MODEL_VERSION,
        last_ingest_timestamp=datetime.utcnow().isoformat(),
        retrieval_collection_ids=source_config.target_collections,
    )
```

Failed ingestion should emit a `DataQualityWarning` aspect, not silently skip catalog update.

## DataHub vs Amundsen decision matrix

| Criterion | DataHub | Amundsen |
|-----------|---------|----------|
| Lineage depth | Excellent (column-level) | Good (table-level) |
| Real-time updates | Kafka-based streaming | Batch ingestion |
| Custom metadata | Flexible aspect schema | Extensible via models |
| Search UX | Good (improving) | Excellent |
| Deployment complexity | Higher (Kafka, ES, MySQL) | Lower |
| API richness | Comprehensive REST/GraphQL | Adequate |
| Community/ecosystem | Larger, active | Stable, smaller |

For RAG teams already running DataHub for analytics, extend it. Starting fresh with primarily document assets, Amundsen's simpler ops may win.

## Governance and compliance

Catalogs support audit questions regulators ask:

- What personal data sources feed the RAG index? (tag `pii:true`)
- Who approved inclusion of each source? (ownership + approval workflow)
- When was each source last verified accurate? (`lastVerifiedTimestamp`)
- What is the blast radius of retiring a source? (downstream lineage)

Integrate catalog with data retention policies: sources marked for deletion trigger lineage-based index purge.

## Getting started

1. Inventory current RAG sources in a spreadsheet (bridge step)
2. Deploy DataHub or Amundsen in staging
3. Write extractor for largest source system
4. Add custom RAG aspect with chunk count and embedding version
5. Wire ingestion pipeline to emit metadata on every run
6. Build stale document audit query
7. Expand to all sources over 4–6 weeks

A catalog does not fix retrieval quality directly—it makes the corpus legible so quality problems become manageable.

## Cross-team workflows enabled by catalog metadata

When product managers ask "which documents feed the customer support RAG collection," the catalog answers in seconds via lineage graph—not a three-day engineering investigation. Legal teams query for PII-tagged sources before GDPR audits. New engineers onboarding to the RAG platform search Amundsen for corpus ownership instead of Slack archaeology.

Establish catalog hygiene rituals: weekly stale-source reports to owners, monthly embedding-version audit before model upgrades, quarterly authorization-tier review aligned with security team. Catalogs decay without ownership—assign a platform engineer as catalog maintainer with SLAs for metadata freshness after each ingestion deploy.

## Resources

- [DataHub documentation](https://datahubproject.io/docs/)
- [Amundsen documentation](https://www.amundsen.io/amundsen/)
- DataHub Python SDK ingestion examples
- OpenMetadata as alternative catalog option
