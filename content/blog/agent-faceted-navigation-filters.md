---
title: "AI Agents: Faceted Navigation Filters"
slug: "agent-faceted-navigation-filters"
description: "Faceted search and filter UX for agent knowledge bases — conjunctive vs disjunctive facets, cardinality control, URL state, Elasticsearch aggregations, and keeping RAG retrieval aligned with user-selected filters."
datePublished: "2025-07-09"
dateModified: "2025-07-09"
tags: ["AI", "Agent", "Faceted"]
keywords: "faceted navigation, faceted search, filters, Elasticsearch aggregations, agent knowledge base, RAG UI, search UX"
faq:
  - q: "What is the difference between conjunctive and disjunctive facets?"
    a: "Conjunctive (AND) facets narrow results — selecting 'Python' and 'API' returns docs tagged with both. Disjunctive (OR) facets within one dimension — selecting 'Python' and 'JavaScript' returns docs with either language. Most UIs use OR within a facet group and AND across groups. Wrong semantics confuse counts and empty result sets."
  - q: "How do facet counts stay accurate when filters are applied?"
    a: "Use Elasticsearch post_filter for user-selected filters while running aggregations on a filtered query that excludes the current facet group (classic self-filter exclusion). Without this, counts show zero for other values in the same group after one selection — the 'facet count collapse' bug users hate."
  - q: "Should agent RAG retrieval respect UI facet filters?"
    a: "Yes. When users pick jurisdiction=EU or product_tier=enterprise, pass those as hard filters to retrieval — not soft boosts. Agents that ignore explicit filters erode trust fast. Log filter state in the retrieval trace so evals reproduce user sessions."
  - q: "How many facet values should the UI expose?"
    a: "Show top 8–12 by count with a 'show more' expansion. Cap cardinality at index time with normalized taxonomy fields — free-text tags with 50k unique values make unusable facets. Use hierarchical facets (Category > Subcategory) for large catalogs."
---
The support agent retrieved twelve chunks about refunds. Nine were US policy. The user had clicked **Region: EU** in the sidebar thirty seconds earlier. The UI sent filters to search; the RAG pipeline ignored them and fused vector scores on unfiltered corpora.

Faceted navigation is the difference between "search a pile" and "navigate a catalog." For agent knowledge bases — runbooks, policies, API docs, ticket macros — facets encode the structured dimensions agents and humans use to disambiguate context. Building them well requires index design, aggregation math, URL state, and tight coupling to retrieval. Building them poorly produces empty states, lying counts, and agents that confidently cite the wrong jurisdiction.

## Facets are a contract with the user

A facet is a navigable dimension with:

- **Field** — `jurisdiction`, `product`, `doc_type`, `severity`
- **Display values** — human labels mapped from canonical IDs
- **Selection mode** — single vs multi, AND vs OR within group
- **Counts** — how many results match each value given other active filters

When a user selects `doc_type=runbook`, they are not suggesting a preference. They are constraining the result set. Agent pipelines must treat facet selections as **hard filters** unless the product explicitly offers a "expand search" escape hatch.

## Index mapping for facet-friendly fields

Facets run on keyword fields (or `keyword` subfields), never analyzed text:

```json
PUT /agent_knowledge
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "fields": { "keyword": { "type": "keyword", "ignore_above": 256 } }
      },
      "content": { "type": "text" },
      "jurisdiction": { "type": "keyword" },
      "product": { "type": "keyword" },
      "doc_type": { "type": "keyword" },
      "tags": { "type": "keyword" },
      "last_updated": { "type": "date" }
    }
  }
}
```

Normalize values at ingest — `EU`, `eu`, and `Europe` as three facet buckets is a taxonomy failure, not a UI problem.

```python
from pydantic import BaseModel, field_validator

class KnowledgeDoc(BaseModel):
    title: str
    content: str
    jurisdiction: str
    product: str
    doc_type: str
    tags: list[str]

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, v: str) -> str:
        mapping = {"europe": "EU", "eu": "EU", "us": "US", "usa": "US"}
        return mapping.get(v.lower(), v.upper())
```

## Elasticsearch aggregation query with self-filter exclusion

The classic pattern for accurate counts when `product` is already filtered:

```json
POST /agent_knowledge/_search
{
  "size": 20,
  "query": {
    "bool": {
      "must": [
        { "multi_match": { "query": "refund policy", "fields": ["title^3", "content"] } }
      ],
      "filter": [
        { "term": { "jurisdiction": "EU" } },
        { "term": { "doc_type": "policy" } }
      ]
    }
  },
  "post_filter": {
    "term": { "product": "billing" }
  },
  "aggs": {
    "product_facet": {
      "filter": {
        "bool": {
          "filter": [
            { "term": { "jurisdiction": "EU" } },
            { "term": { "doc_type": "policy" } }
          ]
        }
      },
      "aggs": {
        "values": {
          "terms": { "field": "product", "size": 12, "order": { "_count": "desc" } }
        }
      }
    },
    "jurisdiction_facet": {
      "filter": {
        "bool": {
          "filter": [
            { "term": { "product": "billing" } },
            { "term": { "doc_type": "policy" } }
          ]
        }
      },
      "aggs": {
        "values": {
          "terms": { "field": "jurisdiction", "size": 8 }
        }
      }
    }
  }
}
```

`post_filter` applies user selection without affecting aggregation filters for sibling facets. Each facet aggregation excludes its own dimension from the filter context. Libraries like Algolia and Typesense handle this internally; raw Elasticsearch requires explicit bool gymnastics.

## URL state and agent session continuity

Facets belong in the URL — not only component state — so refreshes, shared links, and agent traces reproduce context:

```
/kb/search?q=refund&jurisdiction=EU&product=billing&doc_type=policy
```

```typescript
type FacetState = Record<string, string[]>;

export function parseFacetParams(params: URLSearchParams): FacetState {
  const facets: FacetState = {};
  for (const key of ["jurisdiction", "product", "doc_type", "tags"]) {
    const raw = params.get(key);
    if (raw) facets[key] = raw.split(",").filter(Boolean);
  }
  return facets;
}

export function facetsToEsFilter(facets: FacetState): object[] {
  return Object.entries(facets).flatMap(([field, values]) =>
    values.length === 1
      ? [{ term: { [field]: values[0] } }]
      : [{ terms: { [field]: values } }],
  );
}

export function buildAgentRetrievalContext(
  query: string,
  facets: FacetState,
): { query: string; filters: object[]; facetSnapshot: FacetState } {
  return {
    query,
    filters: facetsToEsFilter(facets),
    facetSnapshot: facets,
  };
}
```

Pass `facetSnapshot` into agent logs and eval datasets. Replaying a failed session without facet state is debugging with one eye closed.

## UI patterns that survive real catalogs

**Selected filter chips** above results — removable, keyboard accessible, announce count changes to screen readers.

**Empty state guidance:** "No EU billing policies match 'refund'. Remove Product filter or broaden Region." Never a bare zero.

**Hierarchical facets** for deep taxonomies:

```
Support > Billing > Refunds
```

Use `composite` aggregations or nested `parent/child` mappings sparingly — prefer materialized path keyword (`support.billing.refunds`) for simpler queries.

**Range facets** for dates and numeric severity:

```json
"aggs": {
  "updated": {
    "date_range": {
      "field": "last_updated",
      "ranges": [
        { "key": "Last 30 days", "from": "now-30d/d" },
        { "key": "Last year", "from": "now-1y/d" }
      ]
    }
  }
}
```

Cap `terms` aggregation size; use `sum_other_doc_count` to show "+ 142 more" instead of rendering ten thousand checkboxes.

## Wiring facets into hybrid RAG retrieval

Pipeline order matters:

1. Parse query + facet filters from UI/session.
2. Apply filters as Elasticsearch `filter` context (no score impact, cacheable).
3. Run BM25 + vector hybrid within filtered set.
4. Rerank top-k.
5. Pass chunks + facet metadata to LLM system prompt.

```python
def retrieve(
    query: str,
    facets: dict[str, list[str]],
    k: int = 12,
) -> list[dict]:
    filters = []
    for field, values in facets.items():
        if len(values) == 1:
            filters.append({"term": {field: values[0]}})
        else:
            filters.append({"terms": {field: values}})

    body = {
        "size": k,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "content"],
                        }
                    }
                ],
                "filter": filters,
            }
        },
    }
    # Hybrid: add knn clause in ES 8.x or parallel vector query + RRF merge
    return es.search(index="agent_knowledge", body=body)["hits"]["hits"]
```

Optional **soft fallback:** if filtered retrieval returns < 3 hits, suggest widening filters in UI — do not silently drop filters in the agent backend without telling the user.

## Performance and caching

- Filter context queries cache bitsets — facet-heavy browse sessions benefit from warm caches.
- Debounce facet clicks 150–250ms before firing search to avoid aggregation storms.
- Precompute popular facet combinations for landing pages (`jurisdiction=US&doc_type=policy`).
- CDN-cache facet-free search pages separately from highly personalized filter states.

Monitor p95 search latency split: query phase vs aggregation phase. High-cardinality `cardinality` aggregations on `tags` hurt — use `significant_terms` for exploratory facets only, not primary navigation.

## Accessibility

Facets are form controls, not decoration:

- Fieldset/legend per facet group.
- Checkbox `aria-checked` updates when counts change (`aria-live="polite"` on result count).
- Focus management when filters remove all results — move focus to suggestion link, not page reset.

## Testing

1. **Count correctness:** golden tests — given fixture index and filter state, assert facet buckets match expected counts.
2. **URL round-trip:** serialize → parse → identical facet state.
3. **Agent integration:** eval set where correct answer requires `jurisdiction=EU` filter — measure retrieval recall@k with and without filters.
4. **Load:** simulate 50 rapid facet toggles; aggregation QPS stays within cluster budget.

## The takeaway

Faceted navigation turns agent knowledge bases from monolithic haystacks into navigable inventories. Encode dimensions as normalized keywords, implement self-excluding aggregations for honest counts, persist state in URLs, and enforce filters in retrieval — not just the UI. Agents inherit user intent from facets; ignoring that intent is a product bug dressed as an AI limitation.

## Resources

- [Elasticsearch aggregations reference](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-aggregations.html)

- [Faceted Search (Manning, Daniel Tunkelang)](https://manning.com/books/faceted-search)

- [Algolia facet design documentation](https://www.algolia.com/doc/guides/managing-results/refine-results/faceting/)

- [Typesense faceting guide](https://typesense.org/docs/guide/#faceting)

- [W3C ARIA practices for checkbox groups](https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/)
