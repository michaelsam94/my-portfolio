---
title: "Fine-Tuning Embeddings for Your Domain"
slug: "embeddings-fine-tuning-domain"
description: "Adapt pretrained embedding models to your domain with contrastive fine-tuning: triplet loss, hard negatives, evaluation with MRR, and deployment pitfalls."
datePublished: "2025-12-07"
dateModified: "2025-12-07"
tags: ["AI", "Machine Learning", "Embeddings", "Fine-Tuning"]
keywords: "fine-tune embedding model, domain specific embeddings, contrastive learning, triplet loss, sentence transformers fine-tuning, hard negative mining, embedding evaluation MRR"
faq:
  - q: "When is fine-tuning embeddings worth it versus using a general model?"
    a: "Fine-tune when your domain vocabulary and similarity notion diverge from general web text — legal clauses, medical codes, internal SKU descriptions, or support tickets with company jargon. If general models already achieve strong recall@10 on your eval queries, fine-tuning adds cost without gain."
  - q: "How much training data do I need?"
    a: "Contrastive fine-tuning can show gains with a few thousand (query, positive document) pairs if negatives are hard and diverse. More data helps tail queries. Synthetic pairs from click logs need deduplication and label noise filtering — garbage pairs teach garbage geometry."
  - q: "Should I fine-tune the full model or only add a projection head?"
    a: "Full fine-tuning of smaller models (100M–400M params) often gives the best retrieval quality on domain data. LoRA on larger models reduces GPU memory and preserves some general capability. Train both and compare on a held-out query set with the same chunking pipeline you use in production."
---

Generic `text-embedding-3-large` returns plausible neighbors for "reset OAuth client secret" but ranks your internal runbook below a Stack Overflow thread about unrelated OAuth libraries. The geometry of a general embedding space optimizes for broad semantic similarity on internet text — not for your ticket taxonomy, product catalog, or compliance document structure. Fine-tuning embeddings with contrastive pairs reshapes the space so queries land near documents your humans would label relevant, which is the whole point of RAG retrieval.

## Define similarity for your domain

Before training, write down what "relevant" means:

- **Symmetric** — two product descriptions are duplicates
- **Asymmetric** — short query maps to long document (search)
- **Hard negatives** — same category, wrong variant (size 10 vs size 12 shoe)

Collect `(query, positive_passage, negative_passages)` from:

- Search click logs (clicked = positive, skipped impressions = weak negatives)
- Support agent macros matched to resolved tickets
- Synthetic Q&A from docs with human review

Clean aggressively: near-duplicate positives collapse diversity; false positives poison the space worse than missing data.

## Contrastive training with sentence-transformers

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

model = SentenceTransformer("BAAI/bge-base-en-v1.5")

train_examples = [
    InputExample(texts=[query, positive, negative1, negative2]),
    # MultipleNegativesRankingLoss uses in-batch negatives too
]

loader = DataLoader(train_examples, shuffle=True, batch_size=32)
loss = losses.MultipleNegativesRankingLoss(model)

model.fit(
    train_objectives=[(loader, loss)],
    epochs=3,
    warmup_steps=100,
    output_path="models/support-embeddings-v1",
)
```

`MultipleNegativesRankingLoss` treats other batch items as negatives — batch size directly affects difficulty. For hard negatives mined offline, `CachedMultipleNegativesRankingLoss` or triplet loss with margin helps.

## Hard negative mining loop

1. Embed corpus with baseline model.
2. For each query, retrieve top-50 excluding known positive.
3. Label or heuristic-filter false positives out.
4. Retrain; repeat two to three iterations.

Hard negatives that are semantically close but wrong force the model to learn fine distinctions — easy random negatives barely move weights.

## Evaluation that matches production

Offline metrics on a held-out query set:

```python
def mrr_at_k(ranked, relevant, k=10):
    for rank, doc_id in enumerate(ranked[:k], start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0
```

Also measure:

- **Recall@k** — any relevant in top k
- **nDCG** — graded relevance if available
- **Latency** — embedding dimension affects index size

Evaluate with the same chunk size, preprocessing, and metadata filters as production. Fine-tuning on titles only but retrieving body chunks at inference is a common mismatch.

## Deployment considerations

- **Version embeddings** — re-embed entire corpus on model change; store `model_version` on vectors.
- **Normalize** — L2-normalize if using cosine distance in the index.
- **Batch inference** — GPU batch embed offline; online queries single-vector.
- **Rollback** — keep previous index snapshot until new recall validated in shadow traffic.

Monitor retrieval click-through and human thumbs-down after deploy — offline MRR can improve while user satisfaction drops if labels were biased.

## When not to fine-tune

Try hybrid search (BM25 + vectors), metadata filters, and query expansion first. Fine-tuning adds ML ops surface: training pipelines, eval sets, embedding regeneration, and model drift tracking. Earn that complexity with measured recall gaps on real queries.

## Hard negative mining strategies

Random in-batch negatives are easy — hard negatives (similar but wrong documents) improve discrimination:

```python
from sentence_transformers import SentenceTransformer, losses

model = SentenceTransformer('BAAI/bge-base-en-v1.5')

# Mine hard negatives: top-k similar docs that aren't the correct answer
def mine_hard_negatives(corpus, queries, model, k=5):
    index = faiss.IndexFlatIP(768)
    index.add(model.encode(corpus))
    hard_negs = []
    for q in queries:
        _, indices = index.search(model.encode([q]), k + 1)
        hard_negs.append([corpus[i] for i in indices[0] if corpus[i] != correct_doc])
    return hard_negs
```

Use `MultipleNegativesRankingLoss` with mined hard negatives for 10–20% recall improvement over random negatives on domain benchmarks.

## Training data format for domain embeddings

Contrastive pairs need domain-specific structure:

```json
[
  {
    "anchor": "What is the refund policy for annual subscriptions?",
    "positive": "Annual subscriptions are refundable within 30 days of purchase...",
    "negative": "Monthly subscriptions renew automatically on the 1st of each month..."
  }
]
```

Anchor = user query phrasing. Positive = correct document chunk. Negative = plausible but wrong chunk (hard negative). Generate anchors from real user queries, not synthetic paraphrases — distribution match matters.

Aim for 1,000–5,000 triplets for domain fine-tune. More data helps, but quality of negatives matters more than quantity.

## Hybrid search after fine-tuning

Fine-tuned embeddings improve semantic recall; BM25 still wins on exact keyword matches:

```python
def hybrid_search(query, alpha=0.7):
    bm25_scores = bm25_index.search(query)
    vector_scores = vector_index.search(embed_model.encode(query))
    combined = alpha * normalize(vector_scores) + (1 - alpha) * normalize(bm25_scores)
    return top_k(combined, k=10)
```

Deploy hybrid search alongside fine-tuned embeddings — don't replace BM25 entirely. Tune alpha on held-out query set.

## Failure modes

- **Fine-tune on titles, retrieve body chunks** — train/inference mismatch
- **Random negatives only** — model doesn't learn fine-grained domain distinctions
- **No held-out eval set** — overfit to training queries; production recall drops
- **Embedding regeneration skipped** — old vectors in index; fine-tune has no effect
- **No model version on vectors** — mixed embedding versions in same index

## Production checklist

- Hybrid search (BM25 + vectors) before fine-tuning attempted
- Hard negatives mined from existing index
- Training triplets from real user queries, not synthetic
- Held-out eval set with Recall@5 and nDCG measured
- Full corpus re-embedded on model change with version tag
- Shadow traffic comparison before switching index

Hold out 20% of domain pairs for eval during embedding fine-tune — training metrics lie when you optimize on the full set.

## Resources

- [Sentence Transformers training overview](https://www.sbert.net/docs/training/overview.html)
- [MultipleNegativesRankingLoss documentation](https://www.sbert.net/docs/package_reference/sentence_transformers/losses.html)
- [BGE embedding models (BAAI)](https://github.com/FlagOpen/FlagEmbedding)
- [BEIR benchmark for retrieval evaluation](https://github.com/beir-cellar/beir)
- [Hard negative mining strategies (research survey)](https://arxiv.org/abs/2010.01412)
