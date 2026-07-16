---
title: "On-Device Embeddings for Local Search"
slug: "on-device-embeddings-mobile-search"
description: "Build semantic search on mobile without cloud calls: embedding models on device, vector storage, quantization, and hybrid retrieval patterns for offline-first apps."
datePublished: "2025-08-17"
dateModified: "2025-08-17"
tags: ["AI", "Mobile", "Search", "On-Device"]
keywords: "on-device embeddings, mobile semantic search, local vector search, Core ML embeddings, offline search"
faq:
  - q: "Can mobile devices run embedding models locally?"
    a: "Yes. Small models like all-MiniLM-L6-v2 (~80MB FP32, ~22MB quantized) produce 384-dim vectors on mid-range phones in 20–80ms per short text chunk. Larger models trade accuracy for latency and battery. Match model size to query frequency and hardware floor."
  - q: "How do you store vectors on device for search?"
    a: "SQLite with sqlite-vec or USearch for brute-force cosine on <100k vectors. For larger corpora, use HNSW indexes (USearch, hnswlib mobile builds) or partition by category to keep search sub-100ms. Store raw text alongside vectors for result display."
  - q: "When is on-device semantic search better than cloud?"
    a: "Private notes, medical records, enterprise docs under air-gap policy, offline travel apps, and latency-sensitive typeahead where 200ms network RTT dominates. Cloud wins when corpus exceeds device storage or requires frequent global updates."
---

Users expected instant search across 12,000 saved recipe notes. Sending every keystroke to our API for embedding added 300ms RTT and leaked query text we promised stayed on-device. Moving to on-device embeddings cut perceived latency to under 50ms and let airplane-mode search work — same recall@10 on our eval set after quantizing MiniLM to INT8. On-device embeddings for local search is a systems problem: model size, index structure, and sync strategy matter as much as model accuracy.

## Architecture overview

```
User query ──► [Embedding model on device] ──► query vector
                                                    │
Corpus chunks ──► [Same model at index time] ──► vector index (SQLite/USearch)
                                                    │
                                                    ▼
                                            Top-k cosine similarity
                                                    │
                                                    ▼
                                            Rank + optional BM25 hybrid
```

Everything runs in the app process. No network unless syncing new documents from backend.

## Choosing an embedding model

| Model | Dims | Size (quantized) | Mobile latency (A14, 128 tokens) |
|-------|------|------------------|----------------------------------|
| all-MiniLM-L6-v2 | 384 | ~22 MB INT8 | ~30ms |
| multilingual-e5-small | 384 | ~30 MB | ~40ms |
| bge-small-en-v1.5 | 384 | ~24 MB | ~35ms |
| gte-small | 384 | ~24 MB | ~35ms |

Convert to mobile runtimes:
- **iOS:** Core ML via `coremltools` or ONNX → Core ML
- **Android:** TensorFlow Lite or ONNX Runtime Mobile
- **Flutter:** `tflite_flutter` or platform channels to native

```python
# Export pipeline (server-side prep)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
model.save("minilm_export")
# Then convert to TFLite / Core ML with optimum or onnxruntime
```

Validate quantized model against FP32 on your domain — recipe titles lost 2% recall@10; legal clause search lost 8% (needed bigger model).

## Indexing pipeline

Chunk documents for embedding:

```kotlin
data class SearchChunk(
    val id: String,
    val docId: String,
    val text: String,
    val vector: FloatArray,  // 384 dims
    val updatedAt: Long
)

fun chunkNote(note: Note): List<SearchChunk> {
    return note.body.splitIntoParagraphs(maxTokens = 128).mapIndexed { i, para ->
        SearchChunk(
            id = "${note.id}:$i",
            docId = note.id,
            text = para,
            vector = embedder.encode(para),
            updatedAt = note.updatedAt
        )
    }
}
```

**Index on write** — user saves note → embed chunks → upsert vectors. Background job re-embeds on model upgrade.

**Delete handling** — remove all chunks for `docId` before re-indexing edited docs.



**Vector storage options.**

**sqlite-vec** (extension):

```sql
CREATE VIRTUAL TABLE chunks USING vec0(
  id TEXT PRIMARY KEY,
  embedding FLOAT[384]
);

INSERT INTO chunks(id, embedding) VALUES (?, ?);

SELECT id, distance
FROM chunks
WHERE embedding MATCH ?
ORDER BY distance
LIMIT 20;
```

Good for <500k vectors on phone storage.

**USearch** — HNSW index, faster at scale:

```swift
// Swift USearch example pattern
var index = USearchIndex.make(
    metric: .cosine,
    dimensions: 384,
    connectivity: 16
)
index.add(key: chunkId, vector: vector)
let results = index.search(query: queryVector, count: 10)
```

Persist index to disk; rebuild on corruption via background full re-index.



**Query path.**

```dart
Future<List<SearchResult>> search(String query) async {
  final queryVec = await embedder.encode(query);
  final hits = await vectorIndex.search(queryVec, k: 20);

  // Optional hybrid: combine with SQLite FTS5 keyword score
  final ftsHits = await db.rawQuery('''
    SELECT doc_id, bm25(notes_fts) AS score
    FROM notes_fts WHERE notes_fts MATCH ?
    ORDER BY score LIMIT 20
  ''', [query]);

  return reciprocalRankFusion(hits, ftsHits);
}
```

Hybrid retrieval rescues exact-match queries ("ISO-27001") where pure semantic search drifts. Reciprocal Rank Fusion (RRF) merges ranked lists without score normalization.



**Performance tuning.**

- **Batch embed** offline imports — 32 chunks per inference batch
- **Cache query embeddings** for debounced typeahead (same prefix → same vec approximate with caution)
- **Quantize vectors to INT8** in index — 4× storage savings, minimal recall hit
- **Partition index** by notebook/folder — search subset when scope filter active
- **Run embedder on background isolate** — never block UI thread

Battery test: continuous search while scrolling killed 8% battery/hour with unbatched embed on main thread — fixed with queue + debounce 150ms.



**Sync and multi-device.**

On-device index is local truth for search UX. Sync strategies:

1. **Embed on each device** — sync raw documents via CRDT/CloudKit/Firestore; each device builds own index (consistent after sync, no vector transfer)
2. **Sync precomputed vectors** — faster first open, but model version must match exactly across fleet
3. **Server embed + download index snapshot** — bulk import for initial corpus; incremental local embed for edits

We embed locally after doc sync — avoids 150MB vector blob download on cellular.



**Privacy and compliance.**

- Query text never leaves device
- Vectors are reversible-ish with attack models — treat as sensitive if source text is sensitive; encrypt index at rest with SQLCipher
- Model files ship in app bundle — no runtime download of unknown models without user consent



**When not to go on-device.**

- Corpus >500MB text (storage + index RAM)
- Requires cross-user search (global catalog)
- Embedding model updates weekly from central knowledge base
- Sub-5ms search at billions of vectors (datacenter problem)

Ship an index rebuild path: model upgrades change vector geometry — plan full re-embed on app update with progress UI for large libraries. Benchmark search on minimum supported hardware with a full index, not empty state. Privacy reviews should note embeddings are not encryption; sensitive corpora need SQLCipher or file-level encryption for the vector store. A/B test hybrid vs pure semantic on real queries — legal and SKU-style searches often need keyword recall. Monitor index size in settings so users understand storage impact. If sync brings documents from server, re-embed locally rather than trusting server vectors unless model version bytes match exactly.

## Common production mistakes

Teams get on device embeddings mobile search wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of on device embeddings mobile search fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [sentence-transformers model hub](https://huggingface.co/sentence-transformers)
- [sqlite-vec extension](https://github.com/asg017/sqlite-vec)
- [USearch vector search library](https://github.com/unum-cloud/usearch)
- [ONNX Runtime Mobile](https://onnxruntime.ai/docs/get-started/with-mobile.html)
- [Apple Core ML Tools](https://coremltools.readme.io/docs)
