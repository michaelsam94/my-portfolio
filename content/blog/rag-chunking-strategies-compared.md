---
title: "RAG Chunking Strategies Compared"
slug: "rag-chunking-strategies-compared"
description: "Compare RAG chunking strategies — fixed-size, recursive, semantic, document-based, and agentic — with guidance on matching strategy to corpus type and query patterns."
datePublished: "2024-11-25"
dateModified: "2026-07-17"
tags: ["AI", "RAG", "Chunking", "Retrieval"]
keywords: "RAG chunking strategies, semantic chunking, recursive splitting, document chunking, text segmentation, retrieval optimization"
faq:
  - q: "Can you mix chunking strategies in one RAG index?"
    a: "Yes — route by doc_type metadata: markdown uses header split, PDFs use semantic, tickets use fixed 384. Single index with strategy tag in metadata."
  - q: "Which strategy fails most on PDF exports?"
    a: "Fixed-size without layout-aware extraction — tables become garbage chunks. Preprocess with Unstructured or Docling before strategy selection."
  - q: "How often re-evaluate chunking strategy?"
    a: "On corpus format migration, embedding model change, or recall@5 drop exceeding 5 points on weekly eval."
  - q: "Agentic chunking — when is cost justified?"
    a: "When rule-based strategies fail eval on high-value legal or medical sets and manual chunking cost exceeds LLM boundary detection at index time."
---

Two teams indexed the same 10,000-page knowledge base. One used 500-token fixed windows and complained that retrieval kept returning truncated tables. The other used heading-aware document splitting and watched recall@5 jump 18 points on the same eval set. Chunking strategy is the highest-leverage RAG decision most teams undertune because "we used the default splitter" sounds reasonable until you measure it.

## Fixed-size chunking

Split every N tokens or characters regardless of content structure. Simple, fast, predictable index size.

```python
splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
```

**Pros:** Easy to implement, consistent chunk dimensions, works on any text.
**Cons:** Cuts through paragraphs, code blocks, tables, and numbered lists without mercy.

Use fixed-size as a baseline for benchmarking other strategies, not as a production default for structured content.

## Recursive character splitting

Try a hierarchy of separators — `\n\n`, `\n`, `. `, space — and split on the largest separator that keeps chunks under the size limit. LangChain's `RecursiveCharacterTextSplitter` is the de facto standard.

**Pros:** Respects paragraph and sentence boundaries when possible. Handles mixed prose well.
**Cons:** Still blind to semantic topic shifts within long paragraphs. Code and tables need custom separators.

Best starting point for general documentation, wikis, and support articles.

## Document-based splitting

Split on document structure: markdown headings, HTML tags, PDF section markers, JSON keys. Each section becomes a chunk (or gets further split if oversized).

```python
from langchain_text_splitters import MarkdownHeaderTextSplitter

headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
```

**Pros:** Chunks align with author intent. API docs stay grouped by endpoint; policies stay grouped by clause.
**Cons:** Requires consistent authoring structure. Legacy PDFs with no headings need preprocessing.

Best for technical docs, Notion exports, Confluence pages, and any corpus with reliable heading hierarchy.

## Semantic chunking

Embed sentences or short passages, measure similarity between consecutive segments, and split where similarity drops below a threshold — indicating a topic change.

```python
# Conceptual flow
embeddings = embed(sentences)
for i in range(1, len(sentences)):
    if cosine_similarity(embeddings[i], embeddings[i-1]) < threshold:
        create_chunk_boundary()
```

**Pros:** Chunks follow topical coherence. Long unstructured prose — research papers, legal opinions, interview transcripts — retrieves better.
**Cons:** Expensive at index time. Threshold tuning is corpus-specific. Variable chunk sizes complicate storage planning.

Best for unstructured long-form text where structural markers are absent or unreliable.

## Agentic and LLM-guided chunking

Use an LLM to propose chunk boundaries based on content understanding: "Split this document into self-contained sections suitable for search retrieval." Emerging and expensive, but handles messy formats — slides, emails, scanned OCR — where rule-based splitters fail.

**Pros:** Handles irregular formats. Can generate chunk summaries as metadata.
**Cons:** Highest indexing cost. Non-deterministic boundaries complicate re-indexing. Needs validation to prevent over-fragmentation.

Reserve for high-value document sets where other strategies failed evals, not for bulk indexing.

## Strategy comparison at a glance

| Strategy | Index cost | Recall on structured docs | Recall on unstructured prose | Complexity |
|----------|-----------|---------------------------|------------------------------|------------|
| Fixed-size | Low | Poor | Poor | Trivial |
| Recursive | Low | Good | Moderate | Low |
| Document-based | Low | Excellent | N/A (needs structure) | Low |
| Semantic | High | Moderate | Excellent | Medium |
| Agentic/LLM | Very high | Good | Good | High |

## Combining strategies in a pipeline

Production systems often chain splitters:

1. **Pre-split** on document boundaries (PDF pages, markdown files, email messages).
2. **Structure-split** on headings within each document.
3. **Recursive-split** oversized sections to cap chunk size.
4. **Enrich** with metadata: source, heading path, page number, last-updated date.

```python
sections = markdown_splitter.split(doc)
final_chunks = []
for section in sections:
    if token_count(section) > 768:
        final_chunks.extend(recursive_splitter.split(section))
    else:
        final_chunks.append(section)
```

This preserves heading context while preventing megachunks that dilute embeddings.

## How to pick for your corpus

Run the same 50-question eval set through at least three strategies. Measure recall@5 and end-to-end answer accuracy. The strategy that wins on recall but loses on answer accuracy is fragmenting context the generator needs — consider parent-document retrieval or larger chunks for that corpus.

Re-evaluate when document formats change. A Confluence-to-Notion migration can invalidate heading-based splitting overnight.

## Chunk size tuning methodology

```python
def evaluate_chunk_sizes(docs, questions, sizes=[256, 512, 768, 1024]):
    results = {}
    for size in sizes:
        splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=size // 10)
        index = build_index(docs, splitter)
        results[size] = evaluate_recall(index, questions)
    return results
```

Plot recall@5 vs chunk size — diminishing returns above 768 tokens for many embedding models. Overlap typically 10–20% of chunk size preserves boundary context.

## Metadata enrichment per chunk

Every chunk should carry:

```json
{
  "source": "handbook/engineering/oncall.md",
  "heading_path": "Engineering > On-call > Escalation",
  "page": 12,
  "chunk_index": 3,
  "token_count": 487,
  "last_modified": "2026-01-15T10:00:00Z"
}
```

Heading path prepended to chunk text at embed time improves retrieval without larger chunks:

```python
text_to_embed = f"{metadata['heading_path']}\n\n{chunk_text}"
```

Pair with [RAG parent document retrieval](https://blog.michaelsam94.com/rag-parent-document-retrieval/) when small chunks retrieve well but generation needs wider context.

## Common production mistakes

Teams get chunking strategies compared wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for chunking strategies compared degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Pipeline chaining in production

Real systems rarely use one strategy:

```python
def chunk_document(doc: ParsedDoc) -> list[Chunk]:
    if doc.format == "markdown":
        sections = markdown_header_split(doc)
    elif doc.format == "pdf":
        sections = unstructured_extract_then_semantic_split(doc)
    else:
        sections = recursive_split(doc)
    return [c for s in sections for c in split_if_oversized(s, max_tokens=768)]
```

Tag each chunk with `chunk_strategy` in metadata — debug recall regressions by strategy slice in eval dashboard.

## Eval-driven strategy selection

Run identical 100-question eval across fixed, recursive, header, semantic on **your** corpus. The winner on recall@5 may lose on answer accuracy if chunks are too small for generation — measure both.

Document the decision in ADR: "We use header + recursive because semantic added 4× index cost for 2-point recall gain."

## Re-index cost by strategy

Semantic and agentic chunking increase index-time compute — budget 4–10× wall clock vs recursive on same corpus. Schedule strategy upgrades during maintenance window with embed GPU pool pre-scaled; communicate search quality improvement timeline to stakeholders.

## Language-specific chunking

CJK corpora without whitespace need character or morphological splitters — recursive `
` and space separators fail. Japanese technical docs often use 300–400 character chunks vs 512 English tokens for equivalent semantic unit size.

## Versioning chunk strategy in metadata

When switching strategies on live corpus, bump `chunk_strategy_version` in metadata — mixed-strategy indexes confuse eval dashboards unless queries filter by strategy tag during A/B comparison window.

## Regression suite per strategy

Maintain separate eval JSON file per chunking strategy in git — comparing strategies six months later requires frozen query sets, not ad-hoc manual questions.

## SLA for strategy migration

Document expected search quality dip duration when migrating chunking strategy — stakeholders accept hours of reindex if eval improvement is published beforehand.

## Resources

- [LangChain text splitter reference](https://python.langchain.com/docs/how_to/recursive_text_splitter/)
- [LlamaIndex semantic chunking](https://docs.llamaindex.ai/en/stable/api_reference/node_parsers/semantic_splitter/)
- [Unstructured.io — document parsing and chunking](https://unstructured-io.github.io/unstructured/)
- [Chonkie — open-source chunking library](https://github.com/chonkie-ai/chonkie)
- [Pinecone — chunking strategies guide](https://www.pinecone.io/learn/chunking-strategies/)
