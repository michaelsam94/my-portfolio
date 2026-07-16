---
title: "Vector Search in OpenSearch"
slug: "backend-search-opensearch-vector"
description: "OpenSearch k-NN indexes enable semantic search over embeddings. Set up HNSW vector fields, hybrid BM25 + vector queries, and filter metadata for RAG retrieval pipelines."
datePublished: "2024-11-24"
dateModified: "2024-11-24"
tags: ["Backend", "Search", "OpenSearch", "AI"]
keywords: "OpenSearch vector search, k-NN HNSW, semantic search embeddings, hybrid search BM25 vector, OpenSearch RAG retrieval"
faq:
  - q: "What is vector search in OpenSearch?"
    a: "Vector search finds documents by embedding similarity rather than keyword matching. Text is converted to a dense vector (e.g., 768 dimensions from a model like all-MiniLM-L6-v2), stored in a k-NN index, and queried with approximate nearest neighbor (ANN) algorithms like HNSW. Semantically similar content ranks high even without shared keywords."
  - q: "When should I combine vector search with BM25?"
    a: "Hybrid search merges keyword relevance (BM25) with semantic similarity (vector). Use hybrid when queries contain exact identifiers (SKUs, error codes) that embeddings miss, but also need semantic matching ('fix login bug' matching 'authentication failure resolution'). Pure vector search alone misses exact token matches."
  - q: "What HNSW parameters affect recall and latency?"
    a: "m (max connections per node) and ef_construction (build-time search depth) control index quality vs build time. ef_search (query-time) trades latency for recall — higher ef_search finds more true neighbors but slows queries. Start with m=16, ef_construction=128, ef_search=100 and tune from there."
---

Keyword search fails when users describe concepts differently than your documents. "How to reset my password" won't match a doc titled "Credential recovery procedure" with pure BM25. Vector search embeds both query and documents into a shared semantic space and retrieves by cosine similarity. OpenSearch ships native k-NN support with HNSW indexes — no separate vector database required if you're already on the OpenSearch stack.

## Index setup with k-NN

```json
PUT /documents
{
  "settings": {
    "index": {
      "knn": true,
      "knn.algo_param.ef_search": 100
    }
  },
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "content": { "type": "text" },
      "embedding": {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "nmslib",
          "parameters": {
            "ef_construction": 128,
            "m": 16
          }
        }
      },
      "category": { "type": "keyword" },
      "tenant_id": { "type": "keyword" }
    }
  }
}
```

Match `dimension` to your embedding model output — 384 for MiniLM, 1536 for OpenAI ada-002.

## Ingesting with embeddings

```typescript
import { pipeline } from '@xenova/transformers';

const embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');

async function indexDocument(doc: { title: string; content: string; category: string }) {
  const text = `${doc.title}\n${doc.content}`;
  const output = await embedder(text, { pooling: 'mean', normalize: true });
  const embedding = Array.from(output.data as Float32Array);

  await opensearch.index({
    index: 'documents',
    body: {
      title: doc.title,
      content: doc.content,
      category: doc.category,
      embedding,
    },
  });
}
```

Batch embedding generation offline for large corpora; don't embed at query-time for ingestion.

## Pure vector query

```json
GET /documents/_search
{
  "size": 10,
  "query": {
    "knn": {
      "embedding": {
        "vector": [0.023, -0.041, "... 384 dims ..."],
        "k": 10
      }
    }
  }
}
```

Pre-filter with metadata:

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "embedding": {
              "vector": [...],
              "k": 20
            }
          }
        }
      ],
      "filter": [
        { "term": { "tenant_id": "acme" }},
        { "term": { "category": "support" }}
      ]
    }
  }
}
```

Always filter tenant_id in multi-tenant setups — k-NN without filters leaks cross-tenant results.

## Hybrid search (BM25 + vector)

OpenSearch 2.x hybrid query:

```json
GET /documents/_search
{
  "query": {
    "hybrid": {
      "queries": [
        {
          "match": {
            "content": {
              "query": "password reset login",
              "boost": 0.3
            }
          }
        },
        {
          "knn": {
            "embedding": {
              "vector": [...],
              "k": 20,
              "boost": 0.7
            }
          }
        }
      ]
    }
  }
}
```

Tune BM25 vs vector boost weights against your golden query set. Support queries often need higher BM25 weight (exact error codes); exploratory queries need higher vector weight.

## RAG retrieval pipeline

```
User query → embed query → hybrid search (top-k) → rerank → LLM context
```

Retrieve 20–50 candidates, rerank with a cross-encoder (Cohere rerank, bge-reranker) to top 5, inject into LLM prompt. Vector search is recall-oriented; reranking is precision-oriented.

## Operational considerations

| Concern | Guidance |
|---------|----------|
| Index size | 384-dim float32 = ~1.5KB/doc vector overhead |
| Reindex on model change | New model = new embeddings = full reindex |
| Recall vs latency | Increase ef_search for better recall |
| Freshness | Near-real-time indexing default 1s refresh |

Monitor p95 query latency and recall@10 on labeled sets when tuning HNSW parameters.

## Choosing an embedding model

Model choice affects recall, latency, and index size:

| Model | Dimensions | Size | Best for |
|---|---|---|---|
| all-MiniLM-L6-v2 | 384 | Small | General text, fast inference |
| all-mpnet-base-v2 | 768 | Medium | Higher quality, slower |
| OpenAI text-embedding-3-small | 1536 | API | Best quality, vendor lock-in |
| Cohere embed-v3 | 1024 | API | Multilingual |

Match index `dimension` to model output. Changing models requires full reindex — version your embedding model in index metadata:

```json
{
  "settings": {
    "index.knn": true,
    "meta": { "embedding_model": "all-MiniLM-L6-v2", "embedding_version": "1" }
  }
}
```

Run dual indexes during model migration — query both, compare recall, cut over when new model wins on golden set.

## Pre-filtering vs post-filtering

k-NN search with filters has two strategies:

**Pre-filtering** — apply metadata filters before ANN search. Faster when filters are selective (tenant_id on 0.1% of docs). Required for multi-tenant isolation.

**Post-filtering** — retrieve top-k vectors, then filter. Higher recall when filters are broad but may return fewer than k results after filtering.

```json
{
  "query": {
    "knn": {
      "embedding": {
        "vector": [...],
        "k": 50,
        "filter": {
          "bool": {
            "must": [
              { "term": { "tenant_id": "acme" }},
              { "range": { "created_at": { "gte": "now-90d" }}}
            ]
          }
        }
      }
    }
  }
}
```

If post-filter returns too few results, increase k before filtering (retrieve 100, filter to 10).

## Hybrid search tuning methodology

BM25 vs vector boost weights aren't guessable — tune systematically:

1. Build golden set with query, relevant doc IDs, and query type (keyword-heavy vs semantic)
2. Run grid search: BM25 weight 0.0–1.0 in 0.1 increments, vector weight = 1 - BM25
3. Measure recall@10 and MRR per query type
4. Consider query-type routing: SKU queries → BM25-heavy; natural language → vector-heavy

```python
# Pseudocode: query-type routing
def search(query: str):
    if re.match(r'^[A-Z]{2,}-\d+$', query):
        return bm25_search(query, boost=0.9)
    if len(query.split()) <= 2:
        return hybrid_search(query, bm25_weight=0.6)
    return hybrid_search(query, bm25_weight=0.3)
```

## RAG-specific considerations

Vector search for RAG differs from user-facing search:

- **Chunk size** — 256–512 tokens with overlap (50 tokens) balances context and precision
- **Metadata filtering** — filter by document type, date, access permissions before k-NN
- **Retrieve wide, rerank narrow** — k=50 from vector search, rerank to top 5 with cross-encoder
- **Score threshold** — discard chunks below cosine similarity 0.7 to reduce hallucination grounding failures
- **Duplicate chunks** — deduplicate near-identical vectors from overlapping chunks before LLM context injection

## Index lifecycle and reindexing

Vector indexes are expensive to rebuild. Plan for:

- **Incremental updates** — index new documents individually; batch reindex for model changes
- **Force merge** — after bulk ingest, force merge segments for query performance
- **Warm replicas** — pre-load vector indexes into memory on replica nodes
- **Snapshot before reindex** — vector reindex takes hours on large corpora; snapshot first

## Failure modes

- **Cross-tenant leakage** — k-NN without tenant filter returns semantically similar docs from other tenants
- **Stale embeddings** — document updated but embedding not regenerated; search returns outdated content
- **Dimension mismatch** — indexing 768-dim vectors in 384-dim field fails silently or truncates
- **Over-fetching k** — k=1000 on large index degrades latency; start k=20, increase if recall insufficient
- **Ignoring BM25 in hybrid** — pure vector misses exact error codes and SKUs users paste literally

## Production checklist

- Embedding model version tracked in index metadata
- tenant_id filter on every k-NN query in multi-tenant setups
- Hybrid weights tuned on golden query set, not defaults
- RAG pipeline: retrieve k=20–50, rerank to top 5, score threshold applied
- p95 latency monitored; ef_search tuned against recall@10
- Reindex runbook for model migration with dual-index cutover plan

## Resources

- [OpenSearch k-NN documentation](https://opensearch.org/docs/latest/search-plugins/knn/index/)
- [OpenSearch hybrid search](https://opensearch.org/docs/latest/query-dsl/compound/hybrid/)
- [HNSW algorithm paper](https://arxiv.org/abs/1603.09320)
- [OpenSearch vector search performance tuning](https://opensearch.org/docs/latest/search-plugins/knn/performance-tuning/)
- [Sentence Transformers models](https://www.sbert.net/docs/pretrained_models.html)
