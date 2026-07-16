---
title: "Extracting Knowledge Graphs with LLMs"
slug: "llm-knowledge-graph-extraction"
description: "Build knowledge graphs from unstructured text using LLMs: entity extraction, relation triples, graph storage, deduplication, and pipelines that turn documents into queryable structure."
datePublished: "2024-12-15"
dateModified: "2024-12-15"
tags: ["AI", "LLM", "Machine Learning", "Data"]
keywords: "knowledge graph extraction LLM, entity relation extraction, LLM graph building, knowledge graph RAG, triple extraction NLP"
faq:
  - q: "LLM extraction vs traditional NER — when to use which?"
    a: "Traditional NER/relation extraction models are faster, cheaper, and more consistent for well-defined entity types in high-volume pipelines. LLMs win on diverse document types, complex relations, zero-shot entity types, and one-off extraction without training data. Hybrid: LLM for initial schema discovery, fine-tuned model for production scale."
  - q: "What graph database should I use for LLM-extracted graphs?"
    a: "Neo4j for rich graph queries and mature tooling. Amazon Neptune for managed AWS deployments. Postgres with pg_graph or adjacency tables for moderate graph complexity already in your stack. Property graphs (Neo4j) fit entity-relation models naturally. Choose based on query patterns, not hype."
  - q: "How do I handle entity deduplication?"
    a: "Normalize entity names (lowercase, strip titles), embed entity descriptions and merge above similarity threshold, maintain alias tables ('IBM' = 'International Business Machines'), and use human review for high-confidence merges. LLMs over-extract duplicates — dedup is 30% of the pipeline effort."
---

Your RAG system returns three chunks about "Project Atlas" that never connect it to the same "Atlas initiative" mentioned in a board memo. Flat retrieval misses relationships — who reports to whom, which products depend on which APIs, which contracts reference which clauses. Knowledge graph extraction turns unstructured documents into nodes and edges you can traverse: "What services depend on the payment API that Contract X covers?"

## Extraction pipeline

```
Documents → Chunk → LLM extract (entities + relations) → Normalize → Dedup → Graph store
                                                          ↓
                                                    Vector index (for hybrid retrieval)
```

## Entity and relation extraction

Prompt for structured triples:

```python
EXTRACTION_PROMPT = """
Extract entities and relationships from the text.

Entity types: Person, Organization, Product, Concept, Date, Location
Relation types: WORKS_AT, DEPENDS_ON, PART_OF, MENTIONED_IN, OWNS

Return JSON:
{
  "entities": [{"id": "e1", "type": "Person", "name": "...", "properties": {}}],
  "relations": [{"source": "e1", "relation": "WORKS_AT", "target": "e2", "confidence": 0.9}]
}

Text: {chunk}
"""
```

Process chunk-by-chunk, then merge across chunks:

```python
async def extract_from_document(doc: Document) -> Graph:
    graph = Graph()
    for chunk in chunk_document(doc, size=1500, overlap=200):
        result = await llm.extract(EXTRACTION_PROMPT, chunk.text)
        graph.merge(result)
    return deduplicate(graph)
```

Overlap prevents relations split across chunk boundaries from being lost.

## Schema-first vs schema-free

**Schema-first** — define entity/relation types upfront. Higher precision, misses unexpected relations.

**Schema-free** — let the LLM propose types. Good for exploration; noisy at scale.

Production approach: schema-first with an "Other" escape hatch logged for schema evolution review.

## Deduplication

```python
def merge_entities(entities: list[Entity], threshold: float = 0.92) -> list[Entity]:
    clusters = []
    for entity in entities:
        emb = embed(f"{entity.name} {entity.type} {entity.description or ''}")
        matched = find_cluster(clusters, emb, threshold)
        if matched:
            matched.add_alias(entity.name)
            matched.merge_properties(entity.properties)
        else:
            clusters.append(EntityCluster(entity, emb))
    return [c.canonical for c in clusters]
```

Maintain provenance — every entity tracks source documents:

```python
@dataclass
class Entity:
    id: str
    name: str
    type: str
    aliases: list[str]
    source_chunks: list[str]  # provenance
    properties: dict
```

## Graph storage

Neo4j ingestion:

```cypher
MERGE (p:Person {id: $id})
SET p.name = $name, p.aliases = $aliases
WITH p
UNWIND $relations AS rel
MERGE (t:Entity {id: rel.target_id})
MERGE (p)-[:WORKS_AT {confidence: rel.confidence}]->(t)
```

Index entity names and types for lookup. Full-text index for fuzzy search.

## Graph-enhanced RAG

Combine vector retrieval with graph traversal:

```python
async def graph_rag(query: str, tenant_id: str) -> str:
    # Step 1: vector search for relevant entities/chunks
    seeds = await vector_search(query, tenant_id, k=5)
    # Step 2: expand via graph (1-2 hops)
    subgraph = await graph.expand(seeds, hops=2)
    # Step 3: generate with graph context
    context = format_subgraph(subgraph)
    return await llm.generate(query, context=context)
```

"What teams depend on the auth service?" becomes a graph traversal, not a semantic guess.

## Quality control

LLMs hallucinate relations. Validate:

- **Source grounding** — relation must appear in source chunk text (NLI check)
- **Confidence threshold** — discard relations below 0.7
- **Human review queue** — sample 5% of extractions
- **Consistency checks** — Person WORKS_AT two companies simultaneously → flag

Track precision/recall on a labeled eval set of 50–100 documents.

## Incremental updates

Documents change. Update strategy:

- Re-extract changed documents only (content hash diff)
- Mark stale entities from removed documents
- Version the graph — `valid_from`/`valid_to` on relations for temporal queries

## Entity resolution and deduplication

Extracted entities need deduplication before graph insertion:

```python
def resolve_entity(name: str, entity_type: str, existing_entities: list) -> str:
    # Exact match
    for e in existing_entities:
        if e.name.lower() == name.lower() and e.type == entity_type:
            return e.id
    # Fuzzy match for aliases ("IBM" = "International Business Machines")
    candidates = fuzzy_match(name, existing_entities, threshold=0.85)
    if len(candidates) == 1:
        return candidates[0].id
    # New entity
    return create_entity(name, entity_type)
```

Without entity resolution, "Apple Inc.", "Apple", and "AAPL" become three nodes — graph queries return incomplete results.

## Graph schema design

Define entity and relation types before extraction:

```cypher
// Entity types
(:Person {name, title, email})
(:Company {name, domain, industry})
(:Product {name, version, category})
(:Document {title, source_url, content_hash})

// Relation types with constraints
(:Person)-[:WORKS_AT {since, role}]->(:Company)
(:Person)-[:AUTHORED]->(:Document)
(:Company)-[:PRODUCES]->(:Product)
(:Document)-[:MENTIONS]->(:Person|:Company|:Product)
```

Constrain relation types in extraction prompts — unconstrained extraction produces inconsistent relation names ("works_at", "employed_by", "WORKS_FOR") that don't compose in queries.

## Evaluating extraction quality

Build a labeled eval set of 50–100 documents with gold-standard entities and relations:

```python
def eval_extraction(predicted, gold):
    entity_precision = len(predicted.entities & gold.entities) / len(predicted.entities)
    entity_recall = len(predicted.entities & gold.entities) / len(gold.entities)
    relation_precision = len(predicted.relations & gold.relations) / len(predicted.relations)
    return {
        "entity_f1": harmonic_mean(entity_precision, entity_recall),
        "relation_precision": relation_precision,
    }
```

Target: entity F1 >0.85, relation precision >0.75. Below these thresholds, GraphRAG retrieval quality degrades vs plain vector search.

## Failure modes

- **No entity resolution** — duplicate nodes; incomplete graph traversal
- **Unconstrained relation types** — inconsistent naming; queries fail silently
- **Hallucinated relations** — LLM invents connections not in source text
- **No temporal versioning** — stale relations persist after document update
- **Full re-extraction on every update** — expensive; use content hash diff

## Production checklist

- Entity resolution with fuzzy matching for aliases
- Graph schema defined with constrained entity and relation types
- NLI grounding check: relation must appear in source chunk text
- Eval set of 50–100 labeled documents with entity/relation F1 tracked
- Incremental update via content hash diff (re-extract changed docs only)
- Temporal versioning (`valid_from`/`valid_to`) on relations

Validate extracted triples against schema before graph insert — one bad extraction poisons multi-hop queries permanently.

## Resources

- [Neo4j LLM knowledge graph builder](https://neo4j.com/labs/genai-ecosystem/)
- [Microsoft GraphRAG project](https://github.com/microsoft/graphrag)
- [LangChain knowledge graph modules](https://python.langchain.com/docs/how_to/graph/)
- [REBEL relation extraction model](https://huggingface.co/Babelscape/rebel-large)
- [Knowledge Graphs book (Hogan et al.)](https://link.springer.com/book/10.1007/978-3-031-00719-6)
