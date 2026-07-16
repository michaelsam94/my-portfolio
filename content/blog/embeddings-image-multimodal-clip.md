---
title: "Multimodal Embeddings with CLIP"
slug: "embeddings-image-multimodal-clip"
description: "Build image-text search with CLIP: shared embedding space, zero-shot classification, fine-tuning cautions, and production indexing patterns."
datePublished: "2025-12-10"
dateModified: "2025-12-10"
tags: ["AI", "Machine Learning", "Embeddings", "Multimodal"]
keywords: "CLIP multimodal embeddings, OpenAI CLIP, image text search, zero-shot classification CLIP, contrastive image language, CLIP fine-tuning, SigLIP OpenCLIP"
faq:
  - q: "What does CLIP actually learn?"
    a: "CLIP trains image and text encoders with contrastive loss so matching image-caption pairs are close in embedding space and non-matching pairs are far apart. The result is a shared space where you can search images with text queries, text with images, or compare image-image similarity without task-specific classifiers."
  - q: "Should I use OpenAI CLIP, OpenCLIP, or SigLIP?"
    a: "OpenCLIP reproduces and extends CLIP with open weights and larger training sets — good default for self-hosted. SigLIP improves training stability and often beats CLIP at similar size. OpenAI's original weights are fine for prototypes; production usually wants maintained checkpoints with known licensing and eval on your domain."
  - q: "Do I need to fine-tune CLIP for product search?"
    a: "Start with pretrained encoders and measure recall on your catalog. Fine-tune when product photography style, domain objects, or caption vocabulary differ strongly from web alt-text (industrial parts, medical imaging, fashion on mannequins). Fine-tuning risks catastrophic forgetting of general alignment — use small learning rates and mixed generic pairs."
---

A user types "matte black wireless earbuds case open" and expects your catalog search to surface the right SKU — from product photos alone, no tags required. CLIP-style models make that possible by embedding images and text into the same vector space, trained on hundreds of millions of image-caption pairs so "semantic similarity" aligns with human association more than color histograms ever could. The architecture is simple; the engineering is indexing millions of images, picking the right checkpoint, and knowing where zero-shot CLIP stops and fine-tuning begins.

## Architecture: dual encoders, contrastive loss

```
Image ──► Image Encoder ──► L2 normalize ──► v_img ──┐
                                                      ├── cosine similarity
Text  ──► Text Encoder  ──► L2 normalize ──► v_txt ──┘
```

Training batch of N pairs treats N²−N implicit negatives. At inference, encode once, search with approximate nearest neighbors.

```python
import open_clip
import torch
from PIL import Image

model, _, preprocess = open_clip.create_model_and_transforms(
    "ViT-B-32", pretrained="laion2b_s34b_b79k"
)
tokenizer = open_clip.get_tokenizer("ViT-B-32")

image = preprocess(Image.open("product.jpg")).unsqueeze(0)
text = tokenizer(["wireless earbuds in open charging case"])

with torch.no_grad():
    img_feat = model.encode_image(image)
    txt_feat = model.encode_text(text)
    img_feat /= img_feat.norm(dim=-1, keepdim=True)
    txt_feat /= txt_feat.norm(dim=-1, keepdim=True)
    sim = (img_feat @ txt_feat.T).item()
```

Higher cosine similarity indicates alignment. Thresholds are dataset-specific — calibrate on validation queries.

## Zero-shot classification

Encode class prompts as text prototypes:

```python
labels = ["running shoes", "sandals", "boots", "loafers"]
text_tokens = tokenizer([f"a photo of {l}" for l in labels])
text_features = model.encode_text(text_tokens)
text_features /= text_features.norm(dim=-1, keepdim=True)

logits = (100.0 * img_feat @ text_features.T).softmax(dim=-1)
```

No classifier head retraining — useful for rapid taxonomy experiments. Production catalogs with fine-grained SKU distinctions usually outgrow zero-shot accuracy.

## Building image search index

Offline pipeline:

1. Resize/crop consistently (center crop vs pad affects fashion)
2. Batch `encode_image` on GPU
3. Store vectors + product IDs in FAISS/HNSW
4. Optional: store text embeddings from generated captions for hybrid retrieval

Query path: encode text → ANN search → rerank with metadata filters (price, stock).

For **reverse image search**, encode query image and search the image index directly — useful for duplicate detection and "shop the look."

## Caption generation vs CLIP alone

Some pipelines generate alt-text with a VLM, then embed text with a text-only model. CLIP skips the caption bottleneck but misses OCR text in images (screenshots, labels). Hybrid approach:

- CLIP image vector
- OCR text embedded separately
- Concatenate or weighted fusion at rerank stage

Test which failure mode hurts your catalog more: visual similarity without words, or words without visual nuance.

## Fine-tuning cautions

Fine-tune with image-text pairs from your domain using contrastive loss in OpenCLIP training scripts. Use:

- Low learning rate (1e-6 to 1e-5 for encoders)
- Mix 10–30% general LAION-style pairs to preserve alignment
- Early stopping on retrieval recall, not training loss

Avoid overfitting to studio backgrounds — augment with crop, color jitter, and random JPEG compression matching user-upload quality.

## Production indexing pipeline

End-to-end CLIP search deployment:

```
Catalog images → batch encode (GPU cluster) → vector DB (FAISS/Pinecone/pgvector)
User query text → encode text → ANN search → metadata filter → rerank → results
```

Batch encoding throughput matters at scale — ViT-B-32 processes ~500 images/sec on A100. Plan GPU capacity for initial index build and nightly incremental updates for new products.

```python
# Batch indexing pattern
def index_catalog(image_paths: list[str], batch_size: int = 64):
    vectors = []
    for batch in chunked(image_paths, batch_size):
        images = torch.stack([preprocess(Image.open(p)) for p in batch])
        with torch.no_grad():
            feats = model.encode_image(images)
            feats /= feats.norm(dim=-1, keepdim=True)
        vectors.extend(feats.cpu().numpy())
    index.add(np.array(vectors))
```

Store product metadata separately — ANN returns IDs, application layer joins price/stock/availability.

## Evaluation before production

Build a retrieval eval set before launching:

```python
# Golden set: query_text → relevant_product_ids
eval_set = [
    {"query": "black running shoes", "relevant": ["sku-123", "sku-456"]},
    {"query": "wireless charger stand", "relevant": ["sku-789"]},
]

def recall_at_k(queries, index, k=10):
    hits = 0
    total = 0
    for item in eval_set:
        results = search(item["query"], index, k=k)
        if any(r in item["relevant"] for r in results):
            hits += 1
        total += 1
    return hits / total
```

Target recall@10 > 0.85 on your eval set before shipping. Zero-shot CLIP often achieves 0.6–0.7 on domain-specific catalogs — fine-tuning or hybrid retrieval closes the gap.

## Hybrid retrieval pattern

CLIP alone misses exact SKU matches and OCR text. Combine:

1. **CLIP text→image** — semantic similarity (primary)
2. **BM25 on product title/description** — keyword matching
3. **Exact SKU filter** — when query matches SKU pattern

Rerank combined results with learned weights or simple score fusion. See [Elasticsearch relevance tuning](https://blog.michaelsam94.com/backend-search-elasticsearch-relevance/) for BM25 side.

## Failure modes

- **Zero-shot on fine-grained catalog** — "nike air max 90" vs "nike air max 95" confusion; need fine-tuning or metadata
- **Studio vs user-upload photo gap** — CLIP trained on web photos; user-uploaded product images differ
- **No eval set** — launch with unknown recall; discover bad search in production
- **OCR text ignored** — product labels in images invisible to CLIP; add OCR pipeline
- **Catastrophic forgetting on fine-tune** — model loses general alignment; mix generic pairs

## Production checklist

- Eval set with recall@10 measured before launch
- Batch indexing pipeline with incremental update for new products
- Hybrid retrieval (CLIP + BM25 + SKU exact match)
- OCR pipeline for text-heavy product images
- Fine-tuning only after zero-shot eval shows gap
- Vector index sized for catalog growth with HNSW parameters tuned

## Resources

- [OpenCLIP GitHub repository](https://github.com/mlfoundations/open_clip)
- [Learning Transferable Visual Models (CLIP paper)](https://arxiv.org/abs/2103.00020)
- [SigLIP — sigmoid loss for language-image pre-training](https://arxiv.org/abs/2303.15343)
- [LAION datasets](https://laion.ai/)
- [FAISS vector search](https://github.com/facebookresearch/faiss)
