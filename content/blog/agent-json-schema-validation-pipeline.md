---
title: "JSON Schema Validation Pipeline for Agent Tool Outputs"
slug: "agent-json-schema-validation-pipeline"
description: "Build a multi-stage JSON Schema validation pipeline for LLM tool calls—strict mode, repair loops, schema versioning, and observability so malformed agent output never reaches production side effects."
datePublished: "2025-02-14"
dateModified: "2025-02-14"
tags: ["AI Agents", "JSON Schema", "Validation", "Tool Calling"]
keywords: "json schema validation, agent tool output, structured output, LLM repair loop, schema versioning, ajv, pydantic"
faq:
  - q: "Should JSON Schema validation run before or after the LLM generates tool arguments?"
    a: "Validate after generation and before any side effect. Inject the schema into the tool definition so the model sees constraints, but never trust generation alone—run a validator on the parsed JSON, reject or repair, and only then call external APIs, databases, or billing systems."
  - q: "What JSON Schema draft works best with OpenAI and Anthropic structured output?"
    a: "Draft 2020-12 is the practical default for new pipelines. OpenAI structured outputs and most SDK converters target a subset of 2020-12. Avoid draft-04 unless legacy systems require it. Pin the draft in your CI and reject schemas that use unsupported keywords like unevaluatedProperties if your provider strips them."
  - q: "How many repair attempts should an agent validation pipeline allow?"
    a: "Two repair attempts after the initial failure is a common production cap—one targets syntax or type errors, the second targets semantic constraints the model missed. Log every failure with schema path and raw output. Beyond two attempts, fall back to a safe default or human handoff rather than looping and burning tokens."
  - q: "How do you version schemas without breaking in-flight agent runs?"
    a: "Attach schema_version to each run and tool invocation record. Support N and N-1 concurrently during rollout. Additive changes (new optional fields) ship in minor versions; breaking changes require a new schema_id, feature flag, and sunset date for the old version. Never mutate a schema in place that already has production traffic."
---

The support agent tried to refund $500 instead of $5.00 because the model returned `"amount": 500` without decimal semantics, and your handler coerced it blindly. The ticket queue had fifty similar failures that week—not hallucinations, but **valid JSON that violated your business schema**. A JSON Schema validation pipeline sits between generation and side effects so bad structure never becomes bad money movement.

LLMs are excellent at approximate JSON. They are unreliable at **exact contracts**. Tool calling APIs return parseable strings most of the time, but production needs guarantees: types, enums, bounds, required fields, and cross-field rules (`end_date` after `start_date`). Validation is not pessimism—it is the cheapest guardrail before irreversible actions.

## Pipeline stages

Treat validation as a **sequential pipeline**, not a single `JSON.parse` check:

| Stage | Purpose | Fail action |
|-------|---------|-------------|
| Extract | Strip markdown fences, find first `{`…`}` | Reject with `PARSE_EXTRACT_FAILED` |
| Parse | `JSON.parse` / `json.loads` | Reject with `PARSE_SYNTAX` |
| Schema validate | JSON Schema against tool contract | Repair or reject |
| Semantic validate | Business rules beyond schema | Reject or escalate |
| Authorize | Tenant quotas, RBAC on fields | Reject with `FORBIDDEN` |
| Execute | Side effect (API, SQL, charge) | Idempotent handler |

Each stage emits structured errors with a **path** (`/refund/amount`), **keyword** (`maximum`), and **received value**. That metadata feeds repair prompts and dashboards.

## Schema design for agent tools

Agent tool schemas should be **strict and small**. Models fill large optional objects with plausible noise.

Principles:

1. **Required fields only for what execution needs** — optional fields invite invention
2. **`additionalProperties: false`** on every object — catches hallucinated keys early
3. **Enums over free strings** for actions (`approve`, `reject`, not arbitrary verbs)
4. **Numeric bounds** with `minimum`, `maximum`, `multipleOf` for currency (cents as integers)
5. **`pattern` for IDs** — `^T-[0-9]{4,8}$` beats prose descriptions in the prompt

Example refund tool schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://api.example.com/schemas/refund-v3.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["ticket_id", "amount_cents", "reason_code"],
  "properties": {
    "ticket_id": {
      "type": "string",
      "pattern": "^T-[0-9]{4,8}$"
    },
    "amount_cents": {
      "type": "integer",
      "minimum": 1,
      "maximum": 50000
    },
    "reason_code": {
      "type": "string",
      "enum": ["duplicate_charge", "service_failure", "goodwill", "billing_error"]
    },
    "note": {
      "type": "string",
      "maxLength": 500
    }
  }
}
```

Store schemas in git, publish to an internal registry, and compile once at deploy—not on every request.

## Validator implementation

Use a compiled validator. Ajv for Node, `jsonschema` or `pydantic` TypeAdapter for Python. Warm compilation at startup:

```typescript
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);

const compiled = new Map<string, ValidateFunction>();

export function loadSchema(schemaId: string, schema: object): void {
  compiled.set(schemaId, ajv.compile(schema));
}

export type ValidationResult =
  | { ok: true; data: unknown }
  | { ok: false; errors: SchemaError[] };

export function validateToolArgs(
  schemaId: string,
  raw: string
): ValidationResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, errors: [{ path: "", keyword: "parse", message: "Invalid JSON" }] };
  }

  const validate = compiled.get(schemaId);
  if (!validate) throw new Error(`Unknown schema: ${schemaId}`);

  if (validate(parsed)) return { ok: true, data: parsed };

  return {
    ok: false,
    errors: (validate.errors ?? []).map((e) => ({
      path: e.instancePath,
      keyword: e.keyword ?? "unknown",
      message: e.message ?? "validation failed",
      params: e.params,
    })),
  };
}
```

Enable `allErrors: true` so repair prompts list every violation in one pass—cheaper than whack-a-mole retries.

## Repair loop without infinite spend

When validation fails, feed errors back to the model in a **structured repair message**, not a vague "try again":

```python
REPAIR_TEMPLATE = """
The tool call failed JSON Schema validation for {tool_name} (schema {schema_version}).

Errors:
{error_lines}

Original arguments:
{raw_json}

Return ONLY corrected JSON matching the schema. Do not include markdown fences.
"""

def build_repair_prompt(tool_name: str, schema_version: str, raw: str, errors: list) -> str:
    lines = [f"- {e['path'] or '/'}: {e['message']} ({e['keyword']})" for e in errors]
    return REPAIR_TEMPLATE.format(
        tool_name=tool_name,
        schema_version=schema_version,
        error_lines="\n".join(lines),
        raw_json=raw[:4000],
    )
```

Cap attempts at two. Track `validation.repair_attempts` and `validation.repair_success_rate` per tool. Tools with chronic repair failure need schema or prompt changes—not a third retry.

For high-risk tools (payments, deletes), **skip repair** and route to human review on first schema failure.

## Semantic validation layer

JSON Schema cannot express every rule. Add a pure function stage:

```typescript
function semanticRefundCheck(data: RefundArgs, ctx: RunContext): SemanticError[] {
  const errs: SemanticError[] = [];
  if (data.amount_cents > ctx.ticket.max_refundable_cents) {
    errs.push({
      path: "/amount_cents",
      code: "EXCEEDS_TICKET_MAX",
      message: `Max refundable is ${ctx.ticket.max_refundable_cents} cents`,
    });
  }
  if (ctx.ticket.status === "closed" && data.reason_code !== "billing_error") {
    errs.push({ path: "/reason_code", code: "CLOSED_TICKET", message: "Closed tickets need billing_error" });
  }
  return errs;
}
```

Keep semantic checks **deterministic and testable**. The LLM should not be the only line of defense for "amount exceeds order total."

## Schema registry and CI

Wire schemas into CI so drift never reaches production:

```yaml
# .github/workflows/schema-check.yml
jobs:
  validate-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run schemas:compile-all
      - run: npm run schemas:golden-fixtures
      - run: npm run schemas:breaking-diff -- --base origin/main
```

Golden fixtures are JSON files that must pass or fail validation—committed alongside schemas. Breaking-diff compares `$id` and required fields against main; block merges that remove fields without a major version bump.

## Observability

Metrics that matter:

- `agent.validation.pass_rate` by `tool_name`, `schema_version`
- `agent.validation.failure_keyword` top-N (`additionalProperties`, `enum`, `maximum`)
- `agent.validation.repair_success` after attempt 1 vs 2
- `agent.validation.latency_ms` p95 for compile cache hits

Log a hash of raw model output on failure—never log full PII payloads in hot paths. Sample 1% of successes for quality audits.

Traces should span: `llm.generate` → `validate.schema` → `validate.semantic` → `tool.execute`. When finance disputes a refund, you need the exact invalid intermediate JSON, not just "model said refund."

## Provider structured output integration

OpenAI `response_format: json_schema` and similar APIs push validation upstream. Still run your pipeline:

1. Provider schemas may lag your registry
2. Network proxies can mutate payloads
3. You may switch models or vendors

Use provider structured output to **reduce** repair loops, not to **eliminate** server-side validation.

Map internal schema IDs to provider-compatible subsets—automate the diff in CI when OpenAI updates supported keywords.

## Security considerations

Validation is part of your trust boundary. Never `eval` or dynamic code on model output. Reject deeply nested JSON (`maxDepth` check before schema) to mitigate billion-laughs-style bombs. Limit string lengths at schema and parser level.

Tool schemas are not authorization. A valid `delete_user` payload still requires RBAC checks in the execute stage.

## Rollout strategy

Ship new schema versions behind flags:

1. Deploy validator with v4 compiled, default still v3
2. Canary 5% of runs to v4 with shadow validation (log-only)
3. Compare failure rates for one week
4. Flip default, keep v3 for in-flight runs until TTL expires
5. Decommission v3 on announced date

Shadow mode catches "we tightened enum and 40% of production calls fail" before users see errors.

## The takeaway

A JSON Schema validation pipeline turns agent tool calling from hopeful parsing into engineered contracts: extract, parse, schema-validate, semantic-validate, then execute. Keep schemas strict and versioned, compile validators at deploy, cap repair loops, and instrument every failure path. The model will still surprise you—your job is ensuring surprises never reach the database.

## Resources

- [JSON Schema 2020-12 specification](https://json-schema.org/draft/2020-12/json-schema-core)
- [Ajv JSON Schema validator](https://ajv.js.org/)
- [OpenAI — Structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Anthropic — Tool use documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Pydantic — JSON Schema generation](https://docs.pydantic.dev/latest/concepts/json_schema/)
