---
title: "AI Agents: Parent Child Chunk Linking"
slug: "agent-parent-child-chunk-linking"
description: "How parent-child chunk linking preserves retrieval precision while giving LLMs enough surrounding context — schema design, expansion rules, and eval metrics for production RAG."
datePublished: "2025-06-21"
dateModified: "2025-06-21"
tags: ["AI", "Agent", "Parent"]
keywords: "parent child chunk linking, RAG retrieval, small-to-big retrieval, hierarchical chunks, vector search expansion, document chunking strategy"
faq:
  - q: "When should I use parent-child linking instead of a single chunk size?"
    a: "Use it when your embedding model performs best on 256–512 token chunks but users ask questions that require paragraph- or section-level context. Linking lets retrieval stay precise while generation reads a wider parent window."
  - q: "Should the parent or the child be embedded?"
    a: "Almost always embed the child (small chunk) and store the parent text separately. Embedding large parents dilutes semantic signal; embedding children and expanding to parents at query time is the standard small-to-big pattern."
  - q: "How do I prevent retrieving the wrong parent for overlapping chunks?"
    a: "Give every child an immutable parent_id and byte/char offsets into the parent. Never recompute parent boundaries at query time from heuristics — re-chunking events must version parent records so stale links fail loudly in ingest validation."
  - q: "What metrics prove parent-child linking is working?"
    a: "Track context precision (did expanded text contain the answer span?), citation accuracy, and nDCG@k on a labeled set where gold evidence lives in known child IDs. Regression in child recall with flat parent embedding is a sign your link graph broke."
---
A support agent once answered a billing question with a perfectly relevant sentence — pulled from the middle of a three-page policy PDF — and still got escalated because the sentence mentioned a grandfathered rate without the table header that defined who qualifies. The retrieval stack did its job: cosine similarity found the right needle. The generation step had a needle without the haystack around it.

Parent-child chunk linking exists to split that problem in two. Small **child** chunks drive vector search; larger **parent** chunks supply the context window at answer time. The pattern shows up under names like small-to-big retrieval, hierarchical chunking, and parent-document expansion, but the engineering contract is the same: store two granularities, search one, read the other.

## The failure mode of one chunk size

Teams usually start with fixed-size splits — 512 tokens, 20% overlap, ship it. That works until documents have internal structure: nested headings, tables, cross-references, legal definitions that appear once and bind clauses ten pages later.

Shrink chunks and recall improves; context collapses. Grow chunks and the embedding averages away the specific phrase a user typed. Overlap helps at the margins but doubles storage and still severs tables from captions.

Parent-child linking encodes an explicit bet: **retrieval and reading have different optimal granularities.** Children compete in vector space; parents compete for token budget in the prompt.

## Data model

At minimum you need four fields on every child record:

| Field | Role |
|-------|------|
| `child_id` | Stable primary key used in retrieval logs |
| `parent_id` | Foreign key to the parent text blob |
| `embedding` | Vector for the child only |
| `child_text` | Optional; store if you rerank on lexical features |

Parents carry `parent_text`, source metadata (path, version, ACL), and optionally a outline breadcrumb (`"Refund Policy > Enterprise > SLA Credits"`). Keep parents immutable per `parent_id`; when the source document changes, mint new parent IDs and re-link children rather than overwriting in place — otherwise eval sets and audit trails reference ghosts.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ParentChunk:
    parent_id: str
    doc_id: str
    doc_version: int
    text: str
    heading_path: tuple[str, ...]

@dataclass(frozen=True)
class ChildChunk:
    child_id: str
    parent_id: str
    start_char: int
    end_char: int
    text: str
    embedding: list[float]

def validate_link(child: ChildChunk, parent: ParentChunk) -> None:
    if child.parent_id != parent.parent_id:
        raise ValueError("parent_id mismatch")
    excerpt = parent.text[child.start_char : child.end_char]
    if excerpt.strip() != child.text.strip():
        raise ValueError("child offsets do not match parent text")
```

Validation at ingest catches the most common production bug: a pipeline re-chunked documents but only re-embedded children, leaving offsets pointed at the wrong parent version.

## Ingest: splitting with structure awareness

Structure-aware splitting beats naive token windows for parent boundaries. A practical approach:

1. Parse documents into sections (Markdown headings, PDF outline, HTML `h1–h6`).
2. Each section becomes a **parent** if it fits under your max parent token budget (often 1,500–3,000 tokens).
3. Split each parent into **children** of 256–512 tokens with modest overlap (50–80 tokens) *inside* the parent only.

Overlap should never cross parent borders. If a user query matches the last child of section A and the first child of section B, you want two distinct parent expansions — not a synthetic merge that never existed in the source doc.

For code repositories, parents often map to file paths or symbol blocks; children map to function bodies or comment paragraphs. For chat exports, parents map to conversation sessions; children map to individual turns. The linking logic is identical even when the splitter changes.

## Query path: search small, expand big

The runtime pipeline has three beats:

```typescript
type RetrievedChild = {
  childId: string;
  parentId: string;
  score: number;
};

async function retrieveWithExpansion(
  queryEmbedding: number[],
  topK: number,
): Promise<{ parentId: string; text: string; childHits: RetrievedChild[] }[]> {
  const childHits = await vectorIndex.search(queryEmbedding, topK * 3);

  // Dedupe by parent — keep best-scoring child per parent
  const byParent = new Map<string, RetrievedChild>();
  for (const hit of childHits) {
    const prev = byParent.get(hit.parentId);
    if (!prev || hit.score > prev.score) byParent.set(hit.parentId, hit);
  }

  const ranked = [...byParent.values()]
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);

  const parents = await parentStore.batchGet(ranked.map((r) => r.parentId));

  return ranked.map((r) => ({
    parentId: r.parentId,
    text: parents.get(r.parentId)!.text,
    childHits: childHits.filter((h) => h.parentId === r.parentId),
  }));
}
```

Notice the `topK * 3` fan-out: multiple children from the same parent often land in the top band. Deduping before expansion prevents one long policy section from consuming four slots in the context window.

Optional refinement: **lost-in-the-middle** mitigation. If the parent is large, highlight the matched child span inside the parent with markers or extract a window centered on the child offsets while still passing heading breadcrumbs. Some teams store a tertiary "window" text precomputed at ingest.

## Prompt assembly and citations

Agents should cite `child_id` (precision) while the model reads `parent_text` (context). A citation format that worked well in production:

```
[source: doc_version=42 parent=refund-policy#enterprise child=rc_8912]
```

Log both IDs in retrieval traces. When an answer is wrong, you can tell whether embedding search failed or the parent was right but the model ignored a clause.

Deduping parents also simplifies attribution: one parent expanded once even if three children matched.

## Tuning knobs that actually matter

**Child size** is the main recall lever. If eval shows correct answers exist in the document but never surface in top-20 child hits, shrink children before retraining embeddings.

**Parent size** is the main faithfulness lever. If answers hallucinate qualifiers, parents are probably too small or missing structural headings.

**topK vs fan-out multiplier** trades latency for diversity. Agent workloads with tool calls often use lower topK (3–5 parents) because each parent consumes 1,500+ tokens before tool results arrive.

**Metadata filters** (tenant, product SKU, doc ACL) should apply before vector search when possible. Linking does not fix authorization bugs — a retrieved parent still must pass document-level ACL checks at expansion time.

## Evaluation without guessing

Build a gold set where each question maps to a `child_id` that contains the answer span *and* a `parent_id` required for full context. Score separately:

- **Child recall@k** — is the correct child in the top k vector hits?
- **Parent recall@k** — after dedupe, is the correct parent expanded?
- **Answer correctness** — human or LLM-judge with rubric, given expanded context only.

A healthy stack shows high child recall and slightly higher parent recall. If parent recall lags child recall, your dedupe or `batchGet` path is dropping IDs. If answer correctness lags parent recall, the problem moved downstream to prompting or model behavior.

## Operational hazards

**Re-ingestion drift.** CI should fail when `doc_version` increments but child count delta exceeds a threshold without a signed migration note.

**Duplicate parents.** Two parents with near-identical text from PDF + HTML ingestion paths will steal top-k slots. Canonicalize on `doc_id` at index time.

**Cross-language children.** Multilingual embeddings may match a translated child while the parent remains monolingual. Store language tags and filter when the agent detects query locale.

**Token budget blowups.** Guard `sum(parent.text.length)` with a hard cap; truncate lowest-scoring parents first and log when truncation fires — it is a leading indicator that parent size or topK is miscalibrated.

## Closing perspective

Parent-child chunk linking is not exotic infrastructure. It is a relational join between two chunk granularities — one optimized for geometry in embedding space, one optimized for human-readable structure. The teams that skip the explicit link graph usually recreate it accidentally with bigger chunks and worse recall. Making the relationship first-class in schema, ingest validation, and eval splits retrieval precision from generation context — which is exactly where RAG systems come apart under real documents.

## Resources

- [LlamaIndex recursive retriever documentation](https://docs.llamaindex.ai/en/stable/examples/retrievers/recursive_retriever/)
- [LangChain parent document retriever](https://python.langchain.com/docs/how_to/parent_document_retriever/)
- [PostgreSQL foreign keys and referential integrity](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)
- [Pinecone metadata filtering guide](https://docs.pinecone.io/guides/data/filter-with-metadata)
- [BEIR benchmark for retrieval evaluation](https://github.com/beir-cellar/beir)
