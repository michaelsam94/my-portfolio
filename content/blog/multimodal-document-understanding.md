---
title: "Document Understanding with VLMs"
slug: "multimodal-document-understanding"
description: "Extract structured data from PDFs and scans using vision-language models: layout parsing, table extraction, OCR fallbacks, and accuracy validation."
datePublished: "2025-08-07"
dateModified: "2026-07-17"
tags:
keywords: "vision language models, document understanding, PDF extraction, VLM OCR, structured document parsing, invoice processing AI"
faq:
  - q: "When should I use a VLM instead of traditional OCR plus rules?"
    a: "Use VLMs when document layouts vary widely—invoices from hundreds of vendors, handwritten forms, or mixed tabular and free-text content. Traditional OCR plus regex breaks on layout changes. VLMs generalize across formats but need validation for financial fields."
  - q: "How do I get reliable JSON output from a VLM?"
    a: "Use structured output modes (JSON schema enforcement), few-shot examples in the prompt, and post-validate with Pydantic or JSON Schema. Run extraction twice on critical fields and flag disagreements for human review."
  - q: "What is the cost of processing documents with GPT-4o or Claude?"
    a: "A 10-page PDF at 150 DPI costs roughly $0.05–$0.30 depending on model and tile count. Pre-process with layout detection to send only relevant regions. Cache extractions by document hash."
---
Accounts payable receives 2,000 invoices monthly—PDFs, phone photos, faxes. A rules engine built in 2019 handles your top 12 vendors and fails on everything else. Vision-language models read documents the way humans do: they see layout, context, and handwriting without per-template configuration. The trade-off is cost per page and the need for validation on fields that move money.

## Pipeline architecture

```
PDF/Image → Preprocess (deskew, DPI) → Layout detection → Region crops
    → VLM extraction (per page or per region) → Schema validation → Human queue
```

Don't send entire 50-page contracts in one prompt. Detect tables, headers, and signature blocks first; route each region to a focused extraction prompt.

## Preprocessing

Convert PDF pages to images at 150–200 DPI. Higher DPI helps small text but quadruples token cost.

```python
from pdf2image import convert_from_path

pages = convert_from_path("invoice.pdf", dpi=200, fmt="png")
for i, page in enumerate(pages):
    page.save(f"page_{i:03d}.png")
```

Deskew scanned pages with OpenCV:

```python
import cv2
import numpy as np

def deskew(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    coords = np.column_stack(np.where(gray < 128))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    M = cv2.getRotationMatrix2D(
        (image.shape[1] // 2, image.shape[0] // 2), angle, 1.0
    )
    return cv2.warpAffine(image, M, (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
```

## VLM extraction with structured output

**OpenAI GPT-4o:**

```python
from openai import OpenAI
import base64

client = OpenAI()

with open("page_000.png", "rb") as f:
    b64 = base64.standard_b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="gpt-4o",
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "invoice",
            "schema": {
                "type": "object",
                "properties": {
                    "vendor_name": {"type": "string"},
                    "invoice_number": {"type": "string"},
                    "total_amount": {"type": "number"},
                    "line_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "quantity": {"type": "number"},
                                "unit_price": {"type": "number"},
                            },
                            "required": ["description", "quantity", "unit_price"],
                        },
                    },
                },
                "required": ["vendor_name", "invoice_number", "total_amount"],
            },
        },
    },
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Extract invoice fields. Amounts are USD."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }],
)
```

**Claude with document vision** follows the same pattern—pass images as base64 content blocks and request tool-use with a defined schema.

## Layout-aware extraction

General-purpose VLMs miss fine table structure. Combine specialized layout models with VLMs:

1. **LayoutParser / DocLayNet model** detects titles, tables, figures.
2. Crop each table region; prompt the VLM: "Return this table as JSON rows."
3. For key-value pairs (forms), crop the label-value pairs together.

Open-source options: **LLaVA-NeXT**, **Qwen2-VL**, **Florence-2** for on-prem deployments where data cannot leave your network.

## Validation and confidence

Never auto-post financial data without checks:

```python
from pydantic import BaseModel, field_validator

class Invoice(BaseModel):
    invoice_number: str
    total_amount: float
    line_items: list[dict]

    @field_validator("total_amount")
    @classmethod
    def sum_matches(cls, v, info):
        items = info.data.get("line_items", [])
        if items:
            computed = sum(i["quantity"] * i["unit_price"] for i in items)
            if abs(computed - v) > 0.02:
                raise ValueError(f"total {v} != sum {computed}")
        return v
```

Flag documents where line-item sum disagrees with stated total, dates parse to the future, or vendor name fuzzy-matches no known supplier.

## Hybrid OCR fallback

For dense text pages (legal contracts), run **Tesseract** or **Azure Document Intelligence** for raw text, then pass text plus page image to the VLM for structured extraction. Pure image tokens cost more than text tokens for the same information.

## Production metrics

Track per vendor:
- Field-level accuracy (exact match vs fuzzy)
- Human correction rate
- Cost per document
- Processing latency P95

Improve prompts from correction logs—store `(document_hash, field, predicted, corrected)` and mine weekly for systematic errors.

## Document preprocessing pipeline

Quality upstream beats smarter prompts downstream:

```
PDF upload → page rasterization (300 DPI)
          → deskew + contrast normalize
          → layout detection (tables vs text blocks)
          → crop regions per field
          → VLM extraction per region
```

Handwritten fields, stamps, and watermarks need separate handling — don't send full-page images when you only need the invoice total block. Cropping reduces tokens 60–80% on multi-page documents.

## Confidence scoring and human review

Route low-confidence extractions to review queue:

```python
@dataclass
class ExtractionResult:
    field: str
    value: str
    confidence: float  # model logprob or self-reported

def needs_review(results: list[ExtractionResult]) -> bool:
    return any(r.confidence < 0.85 for r in results) or has_arithmetic_mismatch(results)
```

SLA tiers: auto-approve above 0.95 confidence on non-financial fields; mandatory human review on amounts above $10K regardless of confidence.

## Multi-page table extraction

Tables spanning pages break naive VLM extraction. Strategies:

- **LayoutParser + OCR** for cell boundaries, VLM for header mapping
- **Page-by-page with merge** — reconcile row counts across pages
- **Dedicated table models** (Table Transformer, Donut) for structured grids

Validate extracted tables: row count matches visual row count, column sums match footer totals.

Pair with [multimodal audio transcription Whisper](https://blog.michaelsam94.com/multimodal-audio-transcription-whisper/) when documents include embedded audio notes or call transcripts.

## Resources

- [GPT-4o vision guide](https://platform.openai.com/docs/guides/vision) — image input and structured outputs
- [Anthropic vision documentation](https://docs.anthropic.com/en/docs/build-with-claude/vision) — document image handling
- [LayoutParser](https://layout-parser.github.io/) — document layout detection toolkit
- [Qwen2-VL technical report](https://arxiv.org/abs/2409.12191) — open multimodal document model
- [Azure Document Intelligence](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/) — enterprise OCR and layout API

## Production notes for LLM stacks

When `multimodal-document-understanding` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `document understanding with vlms` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
