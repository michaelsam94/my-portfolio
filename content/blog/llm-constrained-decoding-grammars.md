---
title: "Constrained Decoding with Grammars"
slug: "llm-constrained-decoding-grammars"
description: "Force LLM outputs to match grammars and JSON schemas: GBNF constraints, Outlines, guidance, regex masking, and when constrained decoding beats post-hoc parsing."
datePublished: "2024-11-09"
dateModified: "2024-11-09"
tags: ["AI", "LLM", "Machine Learning", "Backend"]
keywords: "constrained decoding LLM, GBNF grammar, JSON schema LLM output, structured generation, Outlines library"
faq:
  - q: "Constrained decoding vs JSON mode — what's the difference?"
    a: "JSON mode (provider feature) asks the model to output valid JSON — usually reliable but schema compliance varies. Constrained decoding enforces grammar at the token level — invalid tokens are masked during generation, guaranteeing syntactic validity. For strict schemas (enum fields, nested structures), constrained decoding is more reliable."
  - q: "Does constrained decoding slow inference?"
    a: "Slightly — grammar compilation adds startup cost, and per-token masking adds 5–15% overhead on self-hosted engines. Provider JSON mode has minimal overhead. For high-QPS endpoints, benchmark: the latency cost is often less than retrying failed parses."
  - q: "When should I use regex vs full grammar constraints?"
    a: "Regex for simple patterns: dates, UUIDs, enum labels, phone numbers. Full context-free grammars for nested JSON, SQL, or domain-specific languages. Regex constraints on complex JSON get unmaintainable fast."
---

`json.loads()` failing on the fifth retry because the model added a trailing comma is a tax every LLM pipeline pays — until you stop asking the model to behave and start enforcing structure at decode time. Constrained decoding masks invalid tokens during generation so the output is guaranteed to match a grammar or schema. No parsing retries, no "please fix your JSON" follow-up calls, no regex surgery on half-formed SQL.

## How it works

At each generation step, the inference engine computes which tokens are valid given the current partial output and the grammar. Invalid tokens get logit = -∞.

```
Partial: {"name": "Alice", "age":
Valid next tokens: [digit tokens, null, ...]  — not ",}", random text
```

The model still chooses among valid continuations — you constrain syntax, not semantics.

## JSON schema enforcement

With Outlines (Python library for constrained generation):

```python
from outlines import models, generate
import outlines.types as ot

model = models.transformers("meta-llama/Llama-3.1-8B-Instruct")

schema = ot.Json({
    "name": ot.str,
    "age": ot.int,
    "role": ot.Literal("admin", "user", "guest"),
})

generator = generate.json(model, schema)
result = generator("Extract user info: Alice is 34 and an admin")
# Guaranteed valid: {"name": "Alice", "age": 34, "role": "admin"}
```

For self-hosted models via vLLM with guided decoding:

```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int
    role: Literal["admin", "user", "guest"]

response = await client.chat.completions.create(
    model="llama-3.1-8b",
    messages=[{"role": "user", "content": prompt}],
    extra_body={"guided_json": User.model_json_schema()},
)
```

## GBNF grammars

For non-JSON formats, define GBNF (GGML BNF):

```bnf
root   ::= ws "SELECT" ws column ws "FROM" ws table ws
column ::= "id" | "name" | "email" | "created_at"
table  ::= "users" | "orders" | "products"
ws     ::= [ \t\n]*
```

Use for SQL subsets, config file formats, DSL outputs. Keep grammars minimal — every allowed production is a possible hallucination path.

## Provider-native structured output

OpenAI and Anthropic offer schema-constrained responses without self-hosting:

```python
response = client.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[{"role": "user", "content": prompt}],
    response_format=Invoice,
)
invoice = response.choices[0].message.parsed
```

Under the hood, providers use constrained decoding or equivalent. Prefer this for managed APIs — no ops burden.

## When post-hoc parsing is enough

Constrained decoding adds complexity. Skip it when:

- Output is free text (summaries, chat)
- JSON mode works reliably on your eval set (>99.5% parse success)
- You're on a provider without guided decoding support and can't self-host

Use it when:

- Parse failure rate exceeds 1% and retries are expensive
- Invalid output causes downstream errors (database inserts, API calls)
- You're generating code, SQL, or config that must be syntactically valid

## Error handling

Constrained decoding guarantees syntax, not semantics:

```python
result = generator(prompt)
# Valid JSON, but age = -5 or role = "superadmin" (not in enum if schema loose)
validated = User.model_validate(result)  # Pydantic catches semantic errors
```

Add validation after generation. Constraints reduce but don't eliminate bad outputs.

## Performance tips

- **Compile grammars once** — cache compiled automata across requests
- **Keep schemas small** — deeply nested optional fields explode valid token paths
- **Prefer enums over free strings** where possible — tighter constraints, faster decoding
- **Warm up** — first request after deploy pays compilation cost

## Comparison table

| Approach | Syntax guarantee | Semantic validation | Self-host | Provider support |
|----------|-----------------|--------------------|-----------|--------------------|
| Prompt + parse | No | Manual | Yes | All |
| JSON mode | Mostly | Manual | Yes | OpenAI, others |
| Constrained decoding | Yes | Manual | Yes (vLLM, Outlines) | Some |
| Structured output API | Yes | Pydantic/Zod | No | OpenAI, Anthropic |

## GBNF grammar for JSON output

Define JSON structure as a GBNF grammar for llama.cpp/vLLM:

```bnf
root ::= object
object ::= "{" ws members ws "}"
members ::= pair ("," ws pair)*
pair ::= string ws ":" ws value
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" [^"]* "\""
number ::= [0-9]+ ("." [0-9]+)?
array ::= "[" ws (value ("," ws value)*)? ws "]"
ws ::= [ \t\n]*
```

```python
from outlines import models, generate

model = models.vllm("meta-llama/Llama-3.1-8B")
generator = generate.grammar(model, grammar=JSON_GRAMMAR)
result = generator("Extract user info from: John, age 30, admin role")
# Guaranteed valid JSON syntax
```

Grammar guarantees syntax — Pydantic validation still required for semantics (age > 0, role in enum).

## Regex-constrained generation

For simpler patterns, regex constraints are faster than full grammars:

```python
from outlines import generate

# Force ISO date format
date_generator = generate.regex(model, r"\d{4}-\d{2}-\d{2}")
date = date_generator("Today's date is")

# Force enum choice
role_generator = generate.regex(model, r"admin|editor|viewer")
role = role_generator("User role:")
```

Use regex for single-field extraction. Use GBNF/JSON schema for structured objects.

## When constrained decoding fails

Constraints can cause generation to stall if prompt makes valid output impossible:

```python
# Grammar requires JSON object but prompt asks for plain text
# → decoder loops or returns empty object

# Mitigation: validate prompt + grammar compatibility in CI
def test_grammar_prompt_compatibility(prompt_template, grammar, test_inputs):
    for inp in test_inputs:
        result = generate_with_grammar(prompt_template.format(inp), grammar)
        assert result, f"Empty output for input: {inp}"
```

Test grammar + prompt combinations in CI. Empty or partial output indicates incompatible constraint.

## Failure modes

- **Grammar guarantees syntax not semantics** — valid JSON with wrong field values
- **Overly complex grammar** — compilation slow; generation stalls
- **Grammar incompatible with prompt** — empty output without error
- **No post-generation validation** — constrained output assumed correct
- **Grammar not cached** — compilation cost on every request

## Production checklist

- Grammar compiled once and cached across requests
- Pydantic/Zod validation after constrained generation
- Grammar + prompt compatibility tested in CI
- Regex constraints for single-field patterns; GBNF for structured objects
- Fallback to unstructured generation + retry if constrained output empty
- Performance benchmarked: constrained vs unstructured latency delta

## Resources

- [Outlines constrained generation library](https://dottxt-ai.github.io/outlines/)
- [vLLM guided decoding](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#guided-decoding)
- [GBNF grammar specification](https://github.com/ggerganov/llama.cpp/blob/master/grammars/README.md)
- [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [Guidance library (Microsoft)](https://github.com/guidance-ai/guidance)
