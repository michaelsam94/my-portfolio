---
title: "Structured Data Extraction with LLMs"
slug: "llm-structured-extraction-pipelines"
description: "Extract structured fields from unstructured text with LLMs: schema design, chunking strategies, confidence scoring, and validation pipelines that survive production."
datePublished: "2025-03-25"
dateModified: "2026-07-17"
tags:
keywords: "LLM structured extraction, information extraction pipeline, JSON extraction LLM, document parsing AI, entity extraction production"
faq:
  - q: "When should I use an LLM instead of regex or NER for extraction?"
    a: "Use LLMs when the source text is unstructured or semi-structured with high format variability — invoices from 200 vendors, clinical notes, legal contracts. Regex and traditional NER break when layout changes. LLMs generalize across formats but cost more per document and need validation guardrails."
  - q: "How do I handle documents longer than the context window?"
    a: "Chunk the document with overlap, extract from each chunk independently, then merge results with deduplication rules. For extraction tasks, use targeted chunking — split by section headers, page breaks, or semantic boundaries rather than fixed token counts."
  - q: "How do I know if an extraction is reliable?"
    a: "Run constrained decoding to guarantee schema validity, then add semantic validation — check that dates parse, amounts are positive, referenced IDs exist in your database. Track per-field confidence by running the same extraction twice at different temperatures and comparing results."
---
Your operations team receives 500 invoices daily as PDFs, emails, and photographed receipts. Each one needs vendor name, line items, totals, and tax amounts pushed into your accounting system. A rules engine worked when you had three vendors with consistent formats. Vendor number 47 uses a layout nobody has seen before, and the regex pipeline returns empty fields.

LLM-based structured extraction handles format variability that breaks traditional parsers. The catch: you need a pipeline, not a single prompt. Schema design, chunking, constrained generation, validation, and human review hooks determine whether extraction survives contact with real documents.

## Define the extraction schema first

Start with the target data model, not the prompt:

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class LineItem(BaseModel):
    description: str = Field(description="Product or service description")
    quantity: float = Field(description="Number of units")
    unit_price: float = Field(description="Price per unit in dollars")
    total: float = Field(description="Line total in dollars")

class Invoice(BaseModel):
    vendor_name: str = Field(description="Company that issued the invoice")
    invoice_number: str
    invoice_date: date
    due_date: Optional[date] = None
    line_items: list[LineItem]
    subtotal: float
    tax: Optional[float] = None
    total: float = Field(description="Final amount due")
```

Pydantic models serve double duty: they define the schema for constrained decoding and validate the output afterward. Field descriptions guide the model's semantic understanding — `"Price per unit in dollars"` prevents the model from returning cents as dollars.

## Extraction with constrained decoding

Use the schema directly with Outlines or provider structured output:

```python
import outlines

model = outlines.models.transformers("meta-llama/Llama-3.1-8B-Instruct")
generator = outlines.generate.json(model, Invoice)

document_text = ocr_result.text  # from PDF OCR or direct text extraction
result = generator(
    f"Extract invoice data from this document:\n\n{document_text}"
)
invoice = Invoice.model_validate(result)
```

Constrained decoding guarantees the output parses as valid JSON matching your schema. It does not guarantee the values are correct — that requires validation.

## Chunking long documents

A 40-page contract exceeds most context windows. Chunk strategically:

```python
def chunk_by_sections(text: str, max_tokens: int = 3000) -> list[str]:
    sections = re.split(r'\n(?=#{1,3}\s)', text)  # split on markdown headers
    chunks, current = [], ""

    for section in sections:
        if token_count(current + section) > max_tokens:
            if current:
                chunks.append(current)
            current = section
        else:
            current += "\n" + section
    if current:
        chunks.append(current)
    return chunks
```

Extract from each chunk, then merge:

```python
from functools import reduce

partial_results = [extract(chunk) for chunk in chunks]
merged = merge_extractions(partial_results, dedup_key="invoice_number")
```

Merge logic depends on your schema. For lists (line items), concatenate. For scalars (vendor name), take the first non-null value or vote across chunks.

## Pre-processing: OCR and layout

LLMs extract from text, not pixels. The quality of your OCR directly bounds extraction quality:

```python
# For PDFs with text layers
text = pdfplumber.open(path).pages[0].extract_text()

# For scanned documents
from azure.ai.formrecognizer import DocumentAnalysisClient
result = client.begin_analyze_document("prebuilt-layout", pdf_bytes).result()
text = "\n".join(line.content for page in result.pages for line in page.lines)
```

Preserve layout hints when possible. Table structure matters for line items:

```
| Description    | Qty | Price  | Total  |
| Widget A       | 10  | $5.00  | $50.00 |
| Widget B       | 3   | $12.00 | $36.00 |
```

Markdown table formatting from layout-aware OCR (Azure Document Intelligence, AWS Textract) gives the LLM structural context that plain text flattening loses.

## Validation pipeline

Schema validity is necessary but not sufficient:

```python
def validate_extraction(invoice: Invoice) -> list[str]:
    errors = []

    # Arithmetic checks
    computed_subtotal = sum(item.total for item in invoice.line_items)
    if abs(computed_subtotal - invoice.subtotal) > 0.01:
        errors.append(f"Subtotal mismatch: computed {computed_subtotal}, got {invoice.subtotal}")

    # Business rules
    if invoice.total <= 0:
        errors.append("Total must be positive")

    if invoice.due_date and invoice.due_date < invoice.invoice_date:
        errors.append("Due date before invoice date")

    # Cross-reference with known data
    if not vendor_exists(invoice.vendor_name):
        errors.append(f"Unknown vendor: {invoice.vendor_name}")

    return errors
```

Route documents with validation errors to human review rather than silently inserting bad data.

## Confidence and human-in-the-loop

Not every document needs the same scrutiny:

```python
def extraction_confidence(invoice: Invoice, validation_errors: list[str]) -> str:
    if validation_errors:
        return "low"
    if len(invoice.line_items) == 0:
        return "low"
    if invoice.total > 10000:
        return "medium"  # high-value invoices get review regardless
    return "high"

if confidence != "high":
    queue_for_review(invoice, document_id)
else:
    auto_approve(invoice)
```

For critical fields, run dual extraction — two passes at temperature 0 and 0.3 — and flag fields where results diverge.

## Common production mistakes

Teams get structured extraction pipelines wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around structured extraction pipelines break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When structured extraction pipelines misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Outlines structured generation](https://outlines-dev.github.io/outlines/)
- [Pydantic model validation](https://docs.pydantic.dev/latest/)
- [Azure Document Intelligence layout model](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-layout)
- [LangChain extraction chains](https://python.langchain.com/docs/how_to/extraction/)
- [OpenAI structured outputs for extraction](https://platform.openai.com/docs/guides/structured-outputs)
