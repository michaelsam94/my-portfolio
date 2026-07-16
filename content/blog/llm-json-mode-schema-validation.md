---
title: "JSON Mode and Schema Validation"
slug: "llm-json-mode-schema-validation"
description: "Get reliable structured output from LLMs: JSON mode, schema validation with Pydantic/Zod, repair strategies, and production patterns for extraction and API integration."
datePublished: "2024-12-12"
dateModified: "2024-12-12"
tags: ["AI", "LLM", "Backend", "Architecture"]
keywords: "LLM JSON mode, structured output LLM, schema validation LLM, Pydantic LLM output, JSON schema OpenAI"
faq:
  - q: "JSON mode vs structured outputs — which should I use?"
    a: "Use structured outputs (schema-constrained) when your provider supports it and you need guaranteed schema compliance — enums, nested objects, required fields. JSON mode guarantees valid JSON syntax but not schema shape. JSON mode is the fallback for older models or simpler needs."
  - q: "What should I do when JSON parsing fails?"
    a: "Retry once with the error message appended ('your previous response failed validation: missing field X'). If still failing, fall back to a repair prompt or constrained re-generation. Log failures — recurring schema mismatches mean your prompt or schema needs simplification, not more retries."
  - q: "How do I handle optional fields in LLM schemas?"
    a: "Make genuinely optional fields nullable in the schema rather than omitting them — models handle explicit null better than missing keys. Limit optional fields; every optional field is a chance for inconsistency. Default values in your Pydantic/Zod model catch omissions gracefully."
---

Your pipeline expects `{"amount": 847.32, "currency": "USD"}`. The model returns `{"amount": "$847.32", "currency": "US Dollar"}`. Valid JSON. Useless to your code. JSON mode solved the era of responses wrapped in markdown fences — schema validation solves the era of technically-valid JSON that doesn't match your contract.

## Layered approach

```
Prompt + schema definition
    ↓
Provider structured output / JSON mode
    ↓
json.loads() — syntax check
    ↓
Pydantic/Zod validation — semantic check
    ↓
Business logic validation — domain rules
    ↓
Downstream consumer
```

Each layer catches different failures.

## OpenAI structured outputs

```python
from pydantic import BaseModel, Field
from typing import Literal

class Invoice(BaseModel):
    vendor: str
    amount: float = Field(gt=0)
    currency: Literal["USD", "EUR", "GBP"]
    line_items: list[str]
    due_date: str = Field(pattern=r"\d{4}-\d{2}-\d{2}")

response = client.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[{"role": "user", "content": extract_prompt}],
    response_format=Invoice,
)
invoice = response.choices[0].message.parsed
if invoice is None:
    handle_refusal(response)
```

`parsed` is a validated Pydantic object or None if the model refused.

## Anthropic tool use for structured output

Define a single "output" tool with your schema:

```python
tools = [{
    "name": "submit_extraction",
    "description": "Submit the extracted data",
    "input_schema": Invoice.model_json_schema(),
}]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": text}],
    tools=tools,
    tool_choice={"type": "tool", "name": "submit_extraction"},
)
invoice = Invoice.model_validate(response.content[0].input)
```

Forcing tool choice guarantees structured output on Anthropic.

## Schema design for LLMs

Schemas models handle well:

```python
class GoodSchema(BaseModel):
    category: Literal["billing", "technical", "other"]  # enum, not free string
    priority: int = Field(ge=1, le=5)
    summary: str = Field(max_length=200)
    tags: list[str] = Field(max_length=5)
```

Schemas models struggle with:

- Deeply nested optional objects (flatten if possible)
- Union types with 5+ variants (use string + post-validation)
- Regex patterns the model can't reliably satisfy
- 30+ fields (split into multiple extraction passes)

## Validation and repair

```python
def extract_with_retry(text: str, schema: type[BaseModel], max_retries: int = 2) -> BaseModel:
    messages = [{"role": "user", "content": build_prompt(text, schema)}]
    for attempt in range(max_retries + 1):
        raw = llm.complete(messages, response_format=schema)
        try:
            return schema.model_validate_json(raw)
        except ValidationError as e:
            if attempt == max_retries:
                raise
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Validation failed: {e}. Fix and retry."})
```

One retry fixes most issues. More retries usually means schema or prompt problem.

## Partial extraction

For large documents, extract in passes:

```python
# Pass 1: header fields
header = extract(text[:2000], HeaderSchema)
# Pass 2: line items
items = extract(text, LineItemsSchema)
# Merge
return FullDocument(header=header, items=items)
```

Smaller schemas per pass = higher accuracy than one giant extraction.

## Type coercion

Models output strings for numbers. Pydantic coerces:

```python
class Order(BaseModel):
    quantity: int       # "5" → 5
    price: Decimal      # "19.99" → Decimal("19.99")
    active: bool        # "true" → True
```

For dates, use string with pattern validation rather than datetime — model date formats vary.

## Monitoring

Track in production:

- Parse success rate (target > 99%)
- Validation failure breakdown by field
- Retry rate
- Refusal rate (model declines to extract)

Spike in `amount` validation failures? Someone changed currency formatting in source documents.

## Provider-specific structured output APIs

Each provider implements schema enforcement differently:

**OpenAI structured outputs** — JSON Schema enforced at decode time via constrained generation:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    response_format={
        "type": "json_schema",
        "json_schema": {"name": "order", "schema": Order.model_json_schema(), "strict": True}
    },
    messages=[{"role": "user", "content": "Extract order from: ..."}]
)
```

**Anthropic tool use** — schema via tool definition; model returns tool call with structured args:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    tools=[{"name": "extract_order", "input_schema": Order.model_json_schema()}],
    tool_choice={"type": "tool", "name": "extract_order"},
    messages=[...]
)
```

**Instructor library** — provider-agnostic wrapper with Pydantic validation and automatic retry:

```python
import instructor
client = instructor.from_openai(openai_client)
order = client.chat.completions.create(
    model="gpt-4o",
    response_model=Order,
    messages=[{"role": "user", "content": "Extract order from: ..."}],
    max_retries=3
)
```

Prefer native structured outputs when available — constrained generation beats parse-and-retry.

## Retry strategies on validation failure

When validation fails, retry with error context:

```python
def extract_with_retry(client, text, schema, max_retries=3):
    messages = [{"role": "user", "content": f"Extract structured data from:\n{text}"}]
    for attempt in range(max_retries):
        response = client.generate(messages, schema=schema)
        try:
            return schema.model_validate_json(response)
        except ValidationError as e:
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Validation failed: {e}. Fix and retry."})
    raise ExtractionFailed(f"Failed after {max_retries} attempts")
```

Include the validation error in the retry prompt — models often fix format issues on second attempt. Cap retries at 3 to avoid runaway token cost.

## Schema design for LLM extraction

Design schemas models can reliably fill:

```python
class LineItem(BaseModel):
    description: str = Field(description="Product name or description")
    quantity: int = Field(ge=1, description="Number of units")
    unit_price: Decimal = Field(description="Price per unit in USD")

class Invoice(BaseModel):
    invoice_number: str = Field(pattern=r"INV-\d{4,}")
    date: str = Field(description="Invoice date in YYYY-MM-DD format")
    line_items: list[LineItem] = Field(min_length=1)
    total: Decimal = Field(description="Total amount in USD")
```

Use Field descriptions — they guide the model. Avoid deeply nested schemas (>3 levels) — split into multiple extraction passes.

## Failure modes

- **Free-form JSON mode without schema** — valid JSON but wrong structure
- **Datetime fields** — model outputs inconsistent date formats; use string with pattern
- **No retry on validation failure** — 5% failure rate becomes production errors
- **Giant schema in one pass** — accuracy drops; split into header + line items
- **No monitoring on parse failure rate** — silent degradation when source format changes

## Production checklist

- Native structured outputs or Instructor with Pydantic validation
- Retry with validation error context (max 3 attempts)
- Field descriptions on all schema properties
- Split large extractions into multiple passes
- Parse success rate monitored (target >99%)
- Validation failure breakdown by field tracked

## Resources

- [OpenAI structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Pydantic validation documentation](https://docs.pydantic.dev/latest/concepts/models/)
- [Anthropic tool use for structured data](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Zod schema validation for TypeScript](https://zod.dev/)
- [Instructor library (Python structured extraction)](https://python.useinstructor.com/)
