---
title: "GraphRAG: Retrieval Over Knowledge Graphs"
slug: "graphrag-knowledge-graphs"
description: "GraphRAG builds a knowledge graph from your corpus so retrieval traverses entities and relations — answering multi-hop questions vector RAG can't."
datePublished: "2026-02-02"
dateModified: "2026-02-02"
tags: ["RAG", "LLM", "Knowledge Graphs", "Retrieval"]
keywords: "GraphRAG, knowledge graph RAG, entity extraction, graph retrieval, community detection, structured retrieval"
faq:
  - q: "What is GraphRAG?"
    a: "GraphRAG is a retrieval-augmented generation approach that first builds a knowledge graph from your documents — extracting entities and the relationships between them — and then retrieves by traversing that graph instead of, or alongside, vector similarity search. This lets the system answer multi-hop questions that require connecting facts across documents and 'global' questions about themes across the whole corpus. Microsoft Research popularized the term with its open-source GraphRAG project."
  - q: "When does GraphRAG beat vector RAG?"
    a: "GraphRAG wins on questions that require connecting information across many documents — multi-hop reasoning ('which suppliers are affected if factory X closes?') and global summarization ('what are the main themes in these 10,000 reports?'). Plain vector RAG retrieves locally similar chunks and struggles to synthesize across them. For simple fact lookup where the answer sits in one passage, vector RAG is cheaper and just as good."
  - q: "What is the main cost of GraphRAG?"
    a: "Indexing. Building the graph requires running LLM-based entity and relationship extraction over your entire corpus, which is expensive in tokens and time, and it must be maintained as documents change. You're trading a heavy up-front and ongoing indexing cost for better answers on complex queries, so it only pays off when your questions actually need graph-structured retrieval."
---

Vector RAG is great at finding passages that look like your question and terrible at answering questions whose answer is spread across many passages. Ask "what are the recurring risk themes across these 5,000 incident reports?" and top-k similarity search hands you five reports that happen to mention risk — not a synthesis. GraphRAG exists to close that gap. It builds a knowledge graph from your corpus — entities as nodes, relationships as edges — and retrieves by traversing that structure, so it can connect facts across documents and reason about the corpus as a whole.

I want to be clear up front, because the hype gets ahead of the reality: GraphRAG is not a drop-in upgrade to vector RAG. It's a heavier, more expensive machine that pays off on a specific class of questions and is overkill for the rest. Knowing which is which is the whole skill.

## The two questions vector RAG can't answer

Standard retrieval — the kind I broke down in [RAG in production: chunking, reranking, and evals](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/) — retrieves *locally*. It finds the chunks most similar to the query. That works beautifully for "what's our refund window?" where the answer lives in one place. It breaks on two shapes:

1. **Multi-hop questions.** "Which customers are affected if supplier X has an outage?" requires linking supplier X → products → customers, facts that live in different documents. No single chunk contains the chain.
2. **Global/thematic questions.** "What are the main themes across all these documents?" requires reasoning over the *whole* corpus, not a top-k sample of it. Similarity search can't summarize what it didn't retrieve.

GraphRAG targets exactly these. If your users never ask questions like this, you probably don't need it.

## How the graph gets built

The indexing pipeline is where GraphRAG spends its money. Roughly:

1. **Chunk** the documents (same as vector RAG).
2. **Extract entities and relationships** from each chunk with an LLM — "Acme Corp (organization) *supplies* Widget-9 (product)". This is the expensive step; you're running an extraction prompt over the entire corpus.
3. **Build the graph** by merging duplicate entities across chunks into canonical nodes and accumulating edges.
4. **Detect communities** — cluster the graph into groups of densely connected entities using an algorithm like Leiden.
5. **Summarize each community** with an LLM, producing hierarchical summaries from fine-grained clusters up to broad themes.

That last step is the clever part of Microsoft's [GraphRAG](https://github.com/microsoft/graphrag) design. Pre-computed community summaries are what let it answer global questions cheaply at query time — instead of re-reading the corpus, it reads the summaries.

## How retrieval works at query time

GraphRAG typically offers two retrieval modes, and the distinction matters:

| Mode | Question type | How it retrieves |
| --- | --- | --- |
| Local search | Specific entity questions | Start at relevant entities, traverse neighbors, gather connected facts |
| Global search | Corpus-wide themes | Map over community summaries, then reduce into a synthesized answer |

**Local search** anchors on the entities in your question and walks the graph outward, pulling in related entities, relationships, and their source text. This is what handles multi-hop: the traversal *is* the hop. **Global search** ignores local similarity entirely and instead does a map-reduce over the community summaries — asking each summary to contribute to the answer, then combining. That's how it summarizes 10,000 documents without reading all 10,000 at query time.

## The cost reality

Here's the part vendors underplay. Building the graph means LLM-based extraction over your *entire* corpus, plus community summarization. For a large corpus that's a serious token bill and hours of processing — and it's not one-time. Documents change, so you're re-extracting and re-summarizing on some cadence. You're also now running a graph database or graph store alongside your [vector database in production](https://blog.michaelsam94.com/vector-databases-in-production/), with its own operational surface.

So the honest cost model is: **heavy, recurring indexing cost in exchange for better answers on complex queries**. If your query mix is 90% simple lookups, GraphRAG's indexing cost is a bad trade — plain vector RAG answers those fine for a fraction of the price. If your product's core value is synthesis across a knowledge base — think analyst tools, research assistants, compliance review — the trade flips and GraphRAG earns it.

## A pragmatic hybrid

In practice I don't treat this as GraphRAG *versus* vector RAG. The strongest systems use both and route the query to the right retriever:

- **Simple fact lookup** → vector search (cheap, fast, sufficient).
- **Multi-hop / entity-relationship** → graph local search.
- **Thematic / global summarization** → graph global search.

You can even reuse the same chunks and embeddings for the vector path while layering the graph on top for the queries that need it. A small classifier up front — "does this question require connecting multiple entities?" — decides the path, which is the same routing instinct that shows up all over production LLM systems. That hybrid keeps the expensive graph machinery reserved for the queries that actually justify it, instead of taxing every request.

## Should you build it?

My decision checklist:

- **Do users ask multi-hop or thematic questions?** If not, stop here — vector RAG is enough.
- **Is your corpus relationship-rich?** Graphs shine on documents full of named entities and connections (org charts, supply chains, research literature) and add little to a pile of unrelated FAQ snippets.
- **Can you afford the indexing?** Both the initial build and the maintenance as content changes.
- **Do you have graph-store ops capacity?** It's another stateful system to run.

If you answer yes across the board, GraphRAG is a genuine capability unlock — it answers questions that vector RAG simply cannot, and community summaries make corpus-scale synthesis tractable. If you're answering "no" on cost or query mix, resist the shiny object. The best retrieval architecture is the cheapest one that answers your users' actual questions, and for a lot of products that's still boring vector search with good chunking and reranking.

## Resources

- [From Local to Global: A Graph RAG Approach to Query-Focused Summarization (Microsoft, arXiv)](https://arxiv.org/abs/2404.16130)
- [Microsoft GraphRAG — open-source project](https://github.com/microsoft/graphrag)
- [Microsoft Research — GraphRAG project page](https://www.microsoft.com/en-us/research/project/graphrag/)
- [Neo4j — knowledge graphs and RAG documentation](https://neo4j.com/docs/genai/)
- [From Louvain to Leiden: guaranteeing well-connected communities (arXiv)](https://arxiv.org/abs/1810.08473)
- [LlamaIndex — knowledge graph index documentation](https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/)
