---
title: "AI Agents: Hierarchical Indexing Rag"
slug: "agent-hierarchical-indexing-rag"
description: "Hierarchical indexing for RAG—document trees, parent-child retrieval, multi-granularity embeddings, and query routing that beats flat chunking on long corpora."
datePublished: "2025-06-19"
dateModified: "2025-06-19"
tags: ["AI", "Agent", "Hierarchical"]
keywords: "agent, hierarchical, indexing, rag, ai, production, engineering, architecture"
faq:
  - q: "When does hierarchical indexing outperform flat chunking in RAG?"
    a: "Use hierarchy when documents have natural structure—manuals with sections, legal contracts with clauses, codebases with modules. Flat 512-token chunks lose section context; hierarchy preserves parent summaries while retrieving precise leaf passages."
  - q: "What is the parent-child chunk pattern?"
    a: "Embed small leaf chunks for precise retrieval, but store each leaf's parent section (or document summary) for LLM context. Search hits leaves; the generator reads parent context so answers reflect broader meaning, not isolated sentences."
  - q: "How many index levels should a production RAG system use?"
    a: "Three levels cover most cases: document summary, section/chapter, paragraph chunk. More levels add routing complexity without recall gains unless corpora exceed millions of tokens per document (genomics, legislation)."
  - q: "Does hierarchical RAG increase latency?"
    a: "Slightly—often two retrieval hops (route to section, then fetch leaves). Mitigate with parallel search, cached section embeddings, and routing classifiers that skip levels for short queries. Net latency drops when you send fewer irrelevant tokens to the LLM."
---
A legal-tech RAG pipeline chunked 400-page acquisition agreements into 512-token segments. Lawyers asked "What are the indemnification caps in the Delaware APA template?" Retrieval returned a chunk about *cap tables* from a unrelated section because "cap" matched semantically. Flat indexing treated every paragraph as an island; the model answered confidently from the wrong island.

Hierarchical indexing treats corpora as trees—documents, sections, subsections, leaves—and retrieves at the granularity the question demands. You search narrow when the query is specific, widen when it is exploratory, and always attach parent context so the LLM sees the forest, not a random tree ring.

## The flat chunking failure mode

Standard RAG: split text → embed chunks → top-k similarity → stuff context → generate.

Failure modes on structured long documents:

- **Context fragmentation** — a liability clause spans three chunks; none ranks in top-k alone
- **Semantic collision** — homonyms and abbreviations match wrong sections
- **Lost document identity** — chunks from template A and template B interleave in results
- **Over-stuffing** — retrieving ten chunks to reconstruct one section blows token budget

Hierarchical indexing addresses fragmentation and collision by making **structure a first-class retrieval signal**.

## Index topology: document → section → leaf

```
Document (summary embedding)
├── Section A (summary embedding)
│   ├── Leaf A.1 (detail embedding)
│   ├── Leaf A.2
│   └── Leaf A.3
├── Section B
│   ├── Leaf B.1
│   └── Leaf B.2
└── Section C
    └── ...
```

Three embedding types:

| Level | Content embedded | Typical size | Used for |
|-------|------------------|--------------|----------|
| Document | Title + abstract + headings outline | 200–500 tokens | Routing, filtering |
| Section | Heading + first paragraph + summary | 300–800 tokens | Coarse retrieval |
| Leaf | Paragraph or code block | 100–400 tokens | Precision retrieval |

Store parent pointers on every leaf. When leaf `B.2` hits, fetch section `B` summary and optionally document root summary for LLM context.

## Ingestion pipeline

```python
from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class IndexNode:
    id: str
    level: str  # "document" | "section" | "leaf"
    parent_id: Optional[str]
    doc_id: str
    text: str
    embedding: list[float]
    metadata: dict

def ingest_structured_document(doc: dict, embed_fn, split_fn) -> list[IndexNode]:
    nodes = []
    doc_id = doc["id"]
    doc_summary = summarize(doc["title"], doc.get("outline", ""))
    nodes.append(IndexNode(
        id=f"{doc_id}:root",
        level="document",
        parent_id=None,
        doc_id=doc_id,
        text=doc_summary,
        embedding=embed_fn(doc_summary),
        metadata={"title": doc["title"]},
    ))

    for sec_idx, section in enumerate(doc["sections"]):
        sec_id = f"{doc_id}:s{sec_idx}"
        sec_text = f"{section['heading']}\n{section['body'][:500]}"
        sec_summary = summarize(section["heading"], section["body"])
        nodes.append(IndexNode(
            id=sec_id,
            level="section",
            parent_id=f"{doc_id}:root",
            doc_id=doc_id,
            text=sec_summary,
            embedding=embed_fn(sec_summary),
            metadata={"heading": section["heading"]},
        ))

        for leaf_idx, chunk in enumerate(split_fn(section["body"], max_tokens=256)):
            leaf_id = f"{sec_id}:l{leaf_idx}"
            nodes.append(IndexNode(
                id=leaf_id,
                level="leaf",
                parent_id=sec_id,
                doc_id=doc_id,
                text=chunk,
                embedding=embed_fn(chunk),
                metadata={"section_heading": section["heading"]},
            ))
    return nodes
```

Use structure-aware splitters: Markdown headings, PDF outline bookmarks, HTML `<h1>`–`<h6>`, not naive character splits.

## Query routing: which level to search first?

Not every query needs three hops. A lightweight router classifies intent:

- **Specific fact** ("What is the indemnification cap in section 8?") → search leaves directly with metadata filter on section
- **Section overview** ("Summarize termination provisions") → search sections, expand top sections' leaves
- **Document comparison** ("How does template A differ from B on reps?") → search document summaries, then fan out

```typescript
type QueryScope = "leaf" | "section" | "document";

async function routeQuery(query: string, classifier: ScopeClassifier): Promise<QueryScope> {
  const scope = await classifier.predict(query);
  return scope; // e.g. "leaf" for factoid, "section" for thematic
}

async function hierarchicalRetrieve(
  query: string,
  vectorStore: VectorStore,
  embedder: Embedder
): Promise<RetrievalBundle[]> {
  const qVec = await embedder.embed(query);
  const scope = await routeQuery(query, classifier);

  if (scope === "document") {
    const docs = await vectorStore.search(qVec, { level: "document", k: 3 });
    return expandToSections(docs, vectorStore, qVec);
  }

  if (scope === "section") {
    const sections = await vectorStore.search(qVec, { level: "section", k: 5 });
    return expandToLeaves(sections, vectorStore, qVec, kPerSection: 3);
  }

  const leaves = await vectorStore.search(qVec, { level: "leaf", k: 8 });
  return attachParents(leaves, vectorStore);
}
```

Log routing decisions. Mis-routed queries are eval gold—add them to the classifier training set.

## Parent-child retrieval and context assembly

After leaf hits, assemble context bottom-up:

1. Deduplicate leaves from same section (keep highest score)
2. Fetch parent section text (summary + heading)
3. Optionally include document-level disclaimer or effective date
4. Order context: document metadata → section → leaves (most relevant first)

Token budget allocation:

```
30% — document/section framing
70% — leaf passages
```

This beats stuffing ten unrelated leaves because each leaf arrives with its section frame—the model sees "Section 8: Indemnification" above the cap clause.

## Hybrid search at each level

Pure vector search misses exact matches (SKU codes, statute numbers, function names). At each level, combine:

- **Dense** embedding similarity
- **Sparse** BM25 on same text field
- **Metadata filters** — doc type, jurisdiction, version date

```sql
-- pgvector + tsvector hybrid (simplified)
SELECT id, text,
  0.7 * (1 - (embedding <=> query_vec)) +
  0.3 * ts_rank(tsv, plainto_tsquery('english', query_text)) AS score
FROM index_nodes
WHERE level = 'leaf' AND doc_id = ANY($allowed_docs)
ORDER BY score DESC
LIMIT 8;
```

Run hybrid at leaf level; section/document levels often suffice with dense search alone.

## Evaluation metrics for hierarchical RAG

Flat RAG eval (nDCG@k on chunks) under-reports hierarchy value. Add:

- **Section recall** — did retrieval include the correct section for labeled Q&A?
- **Parent attachment rate** — % of answers where parent context changed correctness in blind eval
- **Token efficiency** — answer quality vs. context tokens sent
- **Routing accuracy** — scope classifier confusion matrix

Build eval sets with questions that *require* structure: cross-section reasoning, "compare section 3 and 7," "list all obligations in Article IV."

## Operational concerns

**Reindex cost** — three levels triples embedding calls vs. flat. Batch embed; use smaller models for summaries; cache section embeddings when leaves change but section summary does not.

**Version skew** — document v3 sections must not mix with v2 leaves. Tag every node with `doc_version`; filter at query time.

**Stale summaries** — if sections are edited heavily, regenerate section embeddings on diff detection, not only on full re-ingest.

**Storage** — parent pointers enable graph walks without joins; store in same vector DB collection with `level` filter or use a document graph table.

## When not to use hierarchy

Skip hierarchy for:

- Short FAQs (< 2 pages total)
- Uniformly sized chat logs
- Corpora where structure is fake (PDFs with no real headings)

Flat chunking with metadata tags may be simpler. Hierarchy pays off when **structure carries meaning** the embeddings alone lose.

## Agent integration: tool-aware retrieval

When agents call retrieval as a tool, pass hierarchy metadata back to the orchestrator—not just raw text. Include `section_heading`, `doc_title`, and `node_level` in tool results so the agent can cite accurately ("per Section 8.2, Indemnification Caps") and decide whether to drill deeper with a follow-up retrieval scoped to a parent section ID. Agents that only receive anonymous chunks tend to hallucinate section references; structured metadata closes that gap without extra LLM rounds.

## The takeaway

Hierarchical indexing RAG matches how humans navigate documents—skim the outline, dive into a section, read the paragraph. Implement document/section/leaf embeddings, route queries to the right level, attach parent context on leaf hits, and evaluate section recall—not just chunk similarity. The Delaware APA question gets section 8, not the cap table—and your agent stops sounding confident about the wrong contract.

## Resources

- [LlamaIndex hierarchical node parser](https://docs.llamaindex.ai/en/stable/module_guides/indexing/document_management/)
- [LangChain multi-vector retriever (parent document retriever)](https://python.langchain.com/docs/how_to/multi_vector/)
- [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://arxiv.org/abs/2401.18059)
- [Microsoft GraphRAG — community hierarchy](https://microsoft.github.io/graphrag/)
- [Pinecone hybrid search documentation](https://docs.pinecone.io/guides/data/understanding-hybrid-search)
