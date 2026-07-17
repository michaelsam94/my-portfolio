---
title: "AI Agents: Query Understanding Nlu"
slug: "agent-query-understanding-nlu"
description: "Build a query understanding layer for agent pipelines: intent classification, slot filling, coreference across turns, and when to escalate from rules and embeddings to a full NLU stack."
datePublished: "2025-04-16"
dateModified: "2025-04-16"
tags: ["AI", "Agent", "Query"]
keywords: "query understanding NLU agents, intent classification slot filling, coreference resolution dialogue, hybrid NLU LLM routing, agent query parser"
faq:
  - q: "Do agents still need classical NLU if the LLM understands natural language?"
    a: "Yes, for routing, safety, and cost. A 20ms intent classifier that sends 'reset my password' to the auth tool and 'summarize this PDF' to the doc tool saves hundreds of tokens per turn. Use the LLM for ambiguous or multi-intent utterances, not every keystroke."
  - q: "How many intents should an agent product define before NLU becomes unmaintainable?"
    a: "Stay under 30–40 top-level intents with hierarchical sub-intents. Beyond that, prefer retrieval over a tool catalog (embed tool descriptions, fetch top-k) instead of flat softmax classification. Merge intents that differ only in backend implementation."
  - q: "What is the hardest NLU problem in multi-turn agent chat?"
    a: "Contextual slot carryover and ellipsis: 'make it shorter' after a summarize request, or 'use the one from yesterday' referring to a file. Track dialogue state explicitly; do not rely on the raw chat transcript alone."
  - q: "How do you measure NLU quality independently from end-to-end agent success?"
    a: "Maintain a labeled set with intent, slots, and coreference links per turn. Report per-intent F1, slot extraction F1, and out-of-scope detection recall. End-to-end task success can improve while NLU regresses if the LLM compensates — that compensation is expensive."
---

"Book a flight to Boston next Tuesday" and "actually make that Wednesday" are two messages. A retrieval-only agent sends both verbatim into embedding search and hopes the chunk about cancellation policy isn't the top hit. Query understanding — the NLU layer — turns messy human language into **structured requests** your router, tools, and policies can act on without re-deriving semantics from scratch every turn.

## The output you are actually building

Query understanding is not sentiment analysis for chatbots. For agents, the minimum useful artifact looks like:

```json
{
  "utterance_id": "u_1042",
  "intents": [
    { "name": "modify_travel_search", "confidence": 0.91 }
  ],
  "slots": {
    "destination": { "value": "Boston", "span": [18, 24], "source": "carried" },
    "departure_date": { "value": "2025-04-23", "normalized": true, "source": "current" }
  },
  "dialogue_acts": ["correction"],
  "routing": {
    "primary_tool": "search_flights",
    "requires_clarification": false
  },
  "language": "en",
  "out_of_scope": false
}
```

Everything downstream — tool selection, argument validation, rate limits, audit logs — consumes this object. If your NLU layer only returns a string label, you will push slot parsing into the LLM and pay for it on every request.

## Pipeline architecture: cascade, not monolith

A production cascade balances latency, cost, and accuracy:

```
User text
    │
    ▼
┌─────────────┐
│ Normalize   │  lowercase, unicode NFKC, spell-check domain terms
└──────┬──────┘
       ▼
┌─────────────┐
│ Fast path   │  regex + gazetteers for high-precision patterns
└──────┬──────┘
       │ miss
       ▼
┌─────────────┐
│ Embed match │  cosine similarity to intent exemplars (top-3)
└──────┬──────┘
       │ low confidence
       ▼
┌─────────────┐
│ LLM parse   │  structured output JSON schema, temperature 0
└──────┬──────┘
       ▼
 State merge + validator
```

Implement the fast path seriously. Support tickets follow predictable templates; regex is unfashionable and extremely reliable for them.

```python
from dataclasses import dataclass
from datetime import date
import re

@dataclass
class ParseResult:
    intent: str
    slots: dict
    confidence: float
    path: str

INVOICE_PATTERN = re.compile(
    r"(?:invoice|receipt)\s+#?(\d{4,})", re.IGNORECASE
)

def fast_parse(text: str) -> ParseResult | None:
    m = INVOICE_PATTERN.search(text)
    if m:
        return ParseResult(
            intent="lookup_invoice",
            slots={"invoice_id": m.group(1)},
            confidence=0.98,
            path="regex",
        )
    return None
```

## Slot filling with types, not strings

Agents fail when slots stay untyped. `"next Tuesday"` must become an ISO date in the user's timezone; `"50"` in `"refund 50 dollars"` must bind to `currency_amount`, not `quantity`.

```typescript
const SlotSchema = z.object({
  departure_date: z.string().datetime().optional(),
  passenger_count: z.number().int().min(1).max(9).optional(),
  cabin_class: z.enum(["economy", "premium", "business"]).optional(),
});

type DialogueState = {
  active_intent: string | null;
  filled_slots: Partial<z.infer<typeof SlotSchema>>;
  pending_slot: keyof z.infer<typeof SlotSchema> | null;
};

function mergeSlots(
  state: DialogueState,
  incoming: Partial<z.infer<typeof SlotSchema>>,
  acts: string[]
): DialogueState {
  const filled = { ...state.filled_slots };

  for (const [key, value] of Object.entries(incoming)) {
    if (value !== undefined) {
      filled[key as keyof typeof filled] = value;
    }
  }

  if (acts.includes("correction")) {
    // correction overrides same slot without clearing unrelated slots
    return { ...state, filled_slots: filled, pending_slot: null };
  }

  const pending = requiredSlotMissing(filled, state.active_intent);
  return { ...state, filled_slots: filled, pending_slot: pending };
}
```

When a required slot is missing, the agent should ask a **targeted clarification** ("Which date — April 22 or 23?") instead of re-running full retrieval.

## Coreference and ellipsis across turns

The utterance "cancel it" is unparseable without state. Maintain a lightweight **entity ledger** per session:

| Entity ID | Type | Label | Last mentioned turn |
|-----------|------|-------|---------------------|
| e1 | flight_search | BOS→SFO Apr 22 | 3 |
| e2 | user_document | Q1_report.pdf | 1 |

Resolve "it" by recency + type compatibility with the predicted intent's expected object type. Log resolution confidence; below threshold, clarify ("Which booking should I cancel?").

Do not dump the entire ledger into the LLM each turn. Pass only entities implicated by the detected intent's schema.

## Hybrid LLM parsing: constrain the output

When the cascade escalates to the LLM, use a rigid JSON schema and reject malformed responses:

```python
PARSE_PROMPT = """Extract intent and slots from the user message.
Allowed intents: {intents}
Today: {today} (user timezone: {tz})
Active dialogue state: {state_json}

Return JSON only matching the schema."""

async def llm_parse(message: str, state: dict) -> dict:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PARSE_PROMPT.format(...)},
            {"role": "user", "content": message},
        ],
    )
    parsed = json.loads(response.choices[0].message.content)
    return validate_against_registry(parsed)  # raises if unknown intent
```

Cache parses by `(normalized_message_hash, state_hash)` for idempotent retries. NLU should be deterministic where possible.

## Evaluation harness you will actually run

Build `nlu_eval.jsonl` with one row per turn:

```json
{"text": "change the Boston trip to Wednesday", "intent": "modify_travel_search", "slots": {"destination": "Boston", "departure_date": "2025-04-23"}, "acts": ["correction"]}
```

Track:

- **Intent macro-F1** stratified by traffic volume
- **Slot F1** per slot type (dates and currency hurt most)
- **Escalation rate** to LLM parse (cost proxy)
- **Clarification rate** (UX proxy)

Run the harness on every prompt change, embedding model swap, and new intent addition. Regression in out-of-scope detection is a safety issue — failing open routes garbage to expensive tools.

## Out-of-scope and adversarial input

NLU is a guardrail. Train or few-shot an **out_of_scope** intent for requests your agent cannot fulfill. Pair with input length limits and homoglyph normalization before classification.

Jailbreak attempts often masquerade as benign intents early in the cascade. If fast-path regex matches but subsequent validation fails policy checks, short-circuit before tool dispatch.

Query understanding is the compression layer between human ambiguity and machine contracts. Invest in it when your agent has more than three tools, more than one turn of memory, or a finance team asking why token spend doubled after a prompt tweak.

## Multilingual and code-switching queries

Agent products rarely stay monolingual. Users mix languages mid-session ("réserve un vol to NYC") or inject product-specific English into non-English UI. Handle this explicitly:

1. **Language ID first** — fastText or a tiny classifier on the normalized utterance
2. **Locale-aware date/number parsers** — `03/04/2025` is ambiguous; bind timezone from user profile, not server UTC
3. **Intent exemplars per language** — embedding match fails when all exemplars are English but the query is Spanish; maintain at least five exemplars per top intent per supported locale
4. **Fallback to LLM parse** with language hint in the system prompt

```python
def normalize_multilingual(text: str, locale: str) -> str:
    lang = detect_language(text)
    if lang != locale.split("_")[0]:
        metrics.increment("nlu_language_mismatch", labels={"detected": lang, "expected": locale})
    # Don't translate preemptively — translation adds latency and entity loss
    return unicodedata.normalize("NFKC", text)
```

Code-switching breaks regex gazetteers. Prefer embedding match or LLM parse when language ID confidence is below 0.85 or when mixed-script ratio exceeds a threshold.

## Deployment: shadow mode before routing changes

Never flip NLU routing in production without shadow evaluation:

```typescript
async function routeMessage(msg: string, state: DialogueState) {
  const [production, candidate] = await Promise.all([
    nluV2.parse(msg, state),
    nluV3Shadow.parse(msg, state), // shadow — result discarded from routing
  ]);

  logShadowDiff({
    utterance_hash: hash(msg),
    prod_intent: production.intent,
    cand_intent: candidate.intent,
    prod_slots: production.slots,
    cand_slots: candidate.slots,
  });

  return production; // only production path affects tools
}
```

After a week, compare shadow diffs against human-labeled sample. Promote candidate when intent agreement exceeds 98% on top-traffic intents and slot F1 doesn't regress. Shadow mode catches "the new classifier sends refund requests to the shipping tool" before customers do.

## Ownership and on-call expectations

NLU regressions look like model quality issues in support queues long before eval dashboards turn red. Assign an explicit owner for the intent registry, the labeled eval set, and the escalation thresholds. On-call runbooks should include "disable LLM parse escalation" and "force regex-only mode" feature flags — not rollback of the entire agent stack.

## Resources

- [Rasa NLU pipeline documentation](https://rasa.com/docs/rasa/nlu-training-data/)
- [spaCy linguistic features and rule-based matching](https://spacy.io/usage/linguistic-features)
- [Snips NLU (legacy but clear slot-filling model)](https://github.com/snipsco/snips-nlu)
- [ISO 8601 date parsing pitfalls](https://www.w3.org/TR/NOTE-datetime)
- [Dialogue state tracking survey (ACM)](https://dl.acm.org/doi/10.1145/3368555.3381452)
