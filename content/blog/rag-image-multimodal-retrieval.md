---
title: "Multimodal RAG with Images"
slug: "rag-image-multimodal-retrieval"
description: "Build multimodal RAG pipelines that retrieve and reason over images: CLIP embeddings, document figures, screenshots, and vision-language model integration."
datePublished: "2024-12-27"
dateModified: "2024-12-27"
tags: ["AI", "RAG", "Multimodal", "Vision"]
keywords: "multimodal RAG, image retrieval, CLIP embeddings, vision language model, document figures, image search RAG"
faq:
  - q: "How do I index images for RAG retrieval?"
    a: "Convert images to embeddings using a multimodal model like CLIP, OpenAI's image embeddings, or a vision-language model's image encoder. Store vectors alongside text chunk embeddings in your vector database, tagged with metadata for source document, page number, and any extracted caption or OCR text. At query time, embed the user's text query with the same model and search the combined index."
  - q: "Should I use OCR or image embeddings for document figures?"
    a: "Use both when possible. OCR and caption extraction give you searchable text for diagrams with labels and tables. Image embeddings capture visual layout, color patterns, and wordless diagrams that OCR misses. A hybrid approach — text from OCR plus image embedding stored as linked metadata — handles the widest range of document figure types."
  - q: "How do vision-language models change multimodal RAG?"
    a: "VLMs like GPT-4o, Claude, and Gemini can accept images directly in the generation step. A common pattern retrieves candidate images via CLIP, then passes them to a VLM with the user's question for detailed analysis. This separates fast visual retrieval from slow but accurate visual reasoning, keeping latency manageable."
---

The support engineer asked your internal search "what does the error banner on the billing settings page look like?" and text-only RAG returned a paragraph describing error messages — not the screenshot showing the red-bordered alert with the specific icon users were seeing. Half your knowledge base lives in architecture diagrams, UI mockups, and scanned PDFs with embedded figures. Text-only RAG ignores all of it.

## Where images matter in knowledge bases

Multimodal content appears everywhere:

- **Technical docs** — architecture diagrams, sequence charts, network topology maps.
- **Support materials** — screenshots of error states, UI walkthroughs.
- **Scanned documents** — PDFs with figures, tables rendered as images.
- **Product catalogs** — product photos with visual attributes text does not capture.
- **Medical and scientific papers** — charts, microscopy, radiology.

If your corpus includes any of these, text-only chunking leaves retrievable information on the table.

## Architecture for multimodal RAG

A practical pipeline has four stages:

1. **Extract** — pull images from documents (PDF image extraction, HTML `<img>` tags, dedicated image files).
2. **Enrich** — run OCR, generate captions, extract surrounding text context.
3. **Embed** — create vector representations with a multimodal embedding model.
4. **Retrieve and reason** — search by text query against image embeddings, then optionally pass retrieved images to a VLM for answer generation.

```python
from PIL import Image

def index_image(image: Image, metadata: dict):
    # Enrichment
    ocr_text = run_ocr(image)
    caption = generate_caption(image)  # VLM or captioning model

    # Embedding
    image_embedding = clip_embed(image)
    text_embedding = embed(f"{caption}\n{ocr_text}")

    vector_store.upsert(
        id=metadata["image_id"],
        embedding=image_embedding,
        metadata={
            **metadata,
            "ocr_text": ocr_text,
            "caption": caption,
            "modality": "image",
        },
    )
```

Store both image and text embeddings when your vector database supports multiple vectors per object, or concatenate caption and OCR text for a single text embedding as a simpler starting point.

## CLIP-based retrieval

CLIP (Contrastive Language-Image Pre-training) maps images and text into a shared embedding space. A text query embeds near visually relevant images without generating a hypothetical image.

```python
import clip

model, preprocess = clip.load("ViT-L/14")
image_input = preprocess(image).unsqueeze(0)
text_input = clip.tokenize(["billing settings error banner"])

with torch.no_grad():
    image_features = model.encode_image(image_input)
    text_features = model.encode_text(text_input)
    similarity = cosine_similarity(image_features, text_features)
```

CLIP works well for UI screenshots, product photos, and diagrams with visual distinctiveness. It struggles with fine-grained text in images — pair it with OCR for those cases.

## Passing retrieved images to a VLM

Retrieval narrows thousands of images to top-k candidates. A VLM analyzes them for the final answer:

```python
def multimodal_rag(query: str) -> str:
    # Retrieve candidate images
    candidates = clip_search(query, top_k=5)

    # Also retrieve text chunks
    text_chunks = vector_search(query, top_k=5)

    # Generate with VLM
    response = vlm.generate(
        prompt=f"Answer based on the provided images and text:\n{query}",
        images=[c.image for c in candidates],
        text_context=text_chunks,
    )
    return response
```

This two-stage approach keeps retrieval fast (CLIP embeddings are cheap) and reserves VLM inference for a handful of images.

## Handling PDFs with mixed content

PDFs contain text and images interleaved. Extraction strategy:

1. Extract text with page boundaries (PyMuPDF, pdfplumber).
2. Extract images per page with position metadata.
3. Link images to nearest text section by page and vertical position.
4. Chunk text normally; index images separately with `page_number` and `section` metadata.

```python
for page in pdf.pages:
    text_chunks = chunk_text(page.text, page_num=page.number)
    for img in page.images:
        index_image(img, metadata={
            "source": pdf.filename,
            "page_number": page.number,
            "surrounding_text": page.text[:500],
        })
```

When a text chunk retrieves, also pull linked images from the same page as supplementary context.

## Evaluation challenges

Multimodal RAG evals are harder than text-only:

- Build questions that require visual information to answer correctly.
- Include "text-only sufficient" and "image-required" question categories.
- Measure whether image retrieval returns the correct figure, not just any image.

Start with 20–30 image-dependent questions from support tickets and engineer queries. If image retrieval does not beat text-only baseline on these, multimodal indexing is not earning its cost yet.

## Cost and storage considerations

Image embeddings add storage — one vector per image, typically 512–1024 dimensions. OCR and captioning add indexing compute. VLM calls at generation time are the largest cost per query.

Index images selectively: skip decorative icons and logos; prioritize diagrams, screenshots, and figures referenced in surrounding text.

## Common production mistakes

Teams get image multimodal retrieval wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for image multimodal retrieval degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When image multimodal retrieval misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenAI CLIP repository](https://github.com/openai/CLIP)
- [OpenAI vision API documentation](https://platform.openai.com/docs/guides/vision)
- [Anthropic vision capabilities](https://docs.anthropic.com/en/docs/build-with-claude/vision)
- [PyMuPDF image extraction](https://pymupdf.readthedocs.io/en/latest/recipes-images.html)
- [LlamaIndex multi-modal RAG guide](https://docs.llamaindex.ai/en/stable/examples/multi_modal/)
