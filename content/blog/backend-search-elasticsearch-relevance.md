---
title: "Tuning Elasticsearch Relevance"
slug: "backend-search-elasticsearch-relevance"
description: "Default Elasticsearch BM25 scoring misses business intent. Tune relevance with field boosts, function scores, synonyms, and query-time boosts. Measure with precision@k and search analytics before shipping."
datePublished: "2024-11-19"
dateModified: "2024-11-19"
tags: ["Backend", "Search", "Elasticsearch", "Databases"]
keywords: "Elasticsearch relevance tuning, BM25 scoring, function score query, Elasticsearch synonyms, search relevance, field boost Elasticsearch"
faq:
  - q: "Why does Elasticsearch return irrelevant results?"
    a: "Default BM25 scoring treats all matched fields equally unless you configure boosts. A product match in the SKU field should rank higher than a match in the description. Without field weights, synonyms, and business signals (popularity, recency), users see technically matching but practically wrong results."
  - q: "What is a function_score query?"
    a: "function_score wraps a base query and modifies scores with functions — multiply by popularity, decay by age, boost in-stock items. It combines text relevance (BM25) with business logic (sales rank, freshness) in one query."
  - q: "How do I measure search relevance improvements?"
    a: "Build a golden set of 50–200 query-document pairs labeled relevant/irrelevant. Compute precision@10 and NDCG before and after tuning. Track zero-result rate and click-through rate in production. Never ship relevance changes without offline evaluation."
---

Users type "iphone case" and get results for "iphone" accessories, laptop cases, and a blog post mentioning iPhones. Technically relevant by BM25 standards; practically useless. Elasticsearch relevance tuning is the work of translating business intent into scoring — field weights, synonyms, popularity signals, and freshness decay — then measuring whether the top ten results actually answer the query.

## Index mapping with field boosts

```json
PUT /products
{
  "mappings": {
    "properties": {
      "title": {
        "type": "text",
        "analyzer": "english",
        "boost": 3.0
      },
      "brand": {
        "type": "text",
        "boost": 2.0
      },
      "description": {
        "type": "text",
        "analyzer": "english"
      },
      "sku": {
        "type": "keyword"
      },
      "popularity_score": { "type": "float" },
      "created_at": { "type": "date" }
    }
  }
}
```

Field-level boosts in mapping are static. Prefer query-time boosts for flexibility.

## Multi-match with field weights

```json
GET /products/_search
{
  "query": {
    "multi_match": {
      "query": "iphone case",
      "fields": ["title^3", "brand^2", "description", "sku^5"],
      "type": "best_fields",
      "fuzziness": "AUTO"
    }
  }
}
```

`sku^5` ensures exact SKU matches dominate. `best_fields` picks the highest-scoring field match per document.

## Function score for business signals

```json
GET /products/_search
{
  "query": {
    "function_score": {
      "query": {
        "multi_match": {
          "query": "iphone case",
          "fields": ["title^3", "brand^2", "description"]
        }
      },
      "functions": [
        {
          "field_value_factor": {
            "field": "popularity_score",
            "factor": 1.2,
            "modifier": "log1p",
            "missing": 1
          }
        },
        {
          "gauss": {
            "created_at": {
              "origin": "now",
              "scale": "90d",
              "decay": 0.5
            }
          },
          "weight": 0.3
        },
        {
          "filter": { "term": { "in_stock": true }},
          "weight": 1.5
        }
      ],
      "score_mode": "multiply",
      "boost_mode": "multiply"
    }
  }
}
```

Popular, in-stock, recent products float above text-only matches.

## Synonym handling

```json
PUT /products/_settings
{
  "analysis": {
    "filter": {
      "synonym_filter": {
        "type": "synonym",
        "synonyms": [
          "phone, mobile, smartphone",
          "laptop, notebook, computer",
          "tv, television"
        ]
      }
    },
    "analyzer": {
      "synonym_analyzer": {
        "tokenizer": "standard",
        "filter": ["lowercase", "synonym_filter"]
      }
    }
  }
}
```

Use synonym files for large sets. Index-time synonyms bloat the index; query-time synonyms (search analyzer only) are usually better.

## Disabling TF-IDF pitfalls

Short titles score lower than long descriptions because more term occurrences inflate TF. Mitigate with `title.raw` keyword exact match boost:

```json
{
  "query": {
    "bool": {
      "should": [
        { "multi_match": { "query": "iphone", "fields": ["title^3", "description"] }},
        { "term": { "title.raw": { "value": "iphone", "boost": 10 }}}
      ]
    }
  }
}
```

## Measaining relevance

Build a test set:

```json
{ "query": "wireless headphones", "relevant_ids": ["prod_123", "prod_456"], "irrelevant_ids": ["prod_789"] }
```

Evaluate with `_rank_eval`:

```json
POST /products/_rank_eval
{
  "requests": [
    {
      "id": "wireless_headphones",
      "request": { "query": { "match": { "title": "wireless headphones" }}},
      "ratings": [
        { "id": "prod_123", "rating": 3 },
        { "id": "prod_789", "rating": 0 }
      ]
    }
  ]
}
```

Track mean reciprocal rank (MRR) across your golden set after every scoring change.

## Production observability

Log queries with clicked result position. High zero-result rate → synonym gaps. Position-5 clicks → top results aren't relevant. I've fixed more relevance bugs from click logs than from offline metrics alone.

## Understanding BM25 before tuning

Elasticsearch default similarity is BM25 — a probabilistic ranking function that considers term frequency (TF), inverse document frequency (IDF), and field length normalization. Long documents accumulate more term hits and score higher unless you compensate. Short product titles with one exact match often lose to lengthy descriptions mentioning the term incidentally.

Key BM25 parameters in index settings:

```json
PUT /products/_settings
{
  "index": {
    "similarity": {
      "default": {
        "type": "BM25",
        "k1": 1.2,
        "b": 0.75
      }
    }
  }
}
```

- **k1** — term frequency saturation. Lower k1 (0.5) reduces the boost from repeated terms; useful when descriptions repeat product names many times.
- **b** — length normalization. Higher b (0.9) penalizes long fields more aggressively; helps titles compete with descriptions.

Tune these only after field boosts and function scores — they're global and affect every query.

## Query understanding pipeline

Production search rarely sends raw user input directly to Elasticsearch:

```
User input → spell correction → synonym expansion → intent detection → ES query → reranking → results
```

**Spell correction:** "iphoen case" → "iphone case" via `term` suggester or a dedicated spellcheck index.

**Intent detection:** Queries containing SKU patterns (regex `[A-Z]{2,}-\d+`) route to exact `term` match on `sku` field with high boost. Brand-only queries ("Apple") filter by brand facet.

**Zero-result fallback:** If primary query returns <3 results, retry with fuzziness increased, synonyms expanded, or category broadened. Log fallback triggers — they reveal synonym gaps.

## Faceted search and filters

Relevance and filtering interact — filters reduce the candidate set before scoring:

```json
{
  "query": {
    "bool": {
      "must": {
        "multi_match": {
          "query": "wireless headphones",
          "fields": ["title^3", "brand^2", "description"]
        }
      },
      "filter": [
        { "term": { "in_stock": true }},
        { "range": { "price": { "gte": 50, "lte": 200 }}},
        { "term": { "category": "electronics" }}
      ]
    }
  },
  "aggs": {
    "brands": { "terms": { "field": "brand.keyword" }},
    "price_ranges": { "range": { "field": "price", "ranges": [
      { "to": 50 }, { "from": 50, "to": 100 }, { "from": 100 }
    ]}}
  }
}
```

Filters don't affect score — use them for hard constraints (in stock, tenant_id). Boost in-stock items via function_score when you want availability to influence ranking, not eliminate results.

## Personalization and learning to rank

Function scores handle simple business signals. Learning to Rank (LTR) trains a model on click logs:

```
Features: BM25 score, popularity, recency, user category affinity, price distance from median
Label: clicked (1) / skipped (0)
Model: LambdaMART via elasticsearch-learning-to-rank plugin
```

LTR is worth the investment at scale (millions of queries/month) when function_score tuning plateaus. Start with function_score; graduate to LTR when you have sufficient click data (typically 10k+ labeled query-document pairs).

## Common failure modes

- **Over-boosting SKU** — exact SKU match dominates even when user searched a descriptive phrase; cap SKU boost or require SKU pattern detection
- **Synonym explosion** — "apple" → fruit and brand; use contextual synonyms or disambiguation via category filter
- **Stale popularity scores** — monthly batch update means new products never surface; decay old popularity or blend with recency
- **Ignoring zero-result queries** — the best relevance signal you're not using; weekly review of zero-result logs
- **A/B testing without guardrails** — relevance regressions hurt conversion silently; monitor add-to-cart rate alongside CTR

## Production checklist

- Golden query set (50–200 pairs) with precision@10 tracked in CI
- Query-time field boosts, not static mapping boosts
- Synonym file maintained by product/content team, not engineers alone
- Click position logged with query ID for offline evaluation
- Zero-result queries reviewed weekly
- Function_score weights documented and version-controlled
- `_rank_eval` run before every scoring change deploys

## Resources

- [Elasticsearch function score query](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html)
- [Elasticsearch synonyms guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-synonym-tokenfilter.html)
- [BM25 similarity tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules-similarity.html)
- [Search Relevance evaluation (_rank_eval)](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-rank-eval.html)
- [Learning to Rank plugin (advanced)](https://github.com/o19s/elasticsearch-learning-to-rank)
