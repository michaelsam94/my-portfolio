---
title: "AI Agents: Auto Tagging Taxonomy"
slug: "agent-auto-tagging-taxonomy"
description: "Govern LLM-powered auto-tagging with controlled taxonomies—hierarchical tag schemas, constrained classification, human review queues, and drift detection when models invent labels."
datePublished: "2025-05-04"
dateModified: "2025-05-04"
tags: ["AI", "Agent", "Auto"]
keywords: "auto tagging taxonomy, controlled vocabulary, LLM classification, content tagging agents, taxonomy governance, tag drift detection"
faq:
  - q: "Should auto-tagging use an open vocabulary or fixed taxonomy?"
    a: "Fixed taxonomy for production metadata that powers search filters, access control, and analytics. Open vocabulary is fine for exploratory research queues if tags are promoted into the taxonomy through a review workflow—not written directly to canonical records."
  - q: "How do you stop LLMs from inventing tags outside the taxonomy?"
    a: "Constrained decoding: provide the full allowed tag list (or hierarchical JSON schema) in structured output mode. Reject responses containing unknown tags; retry with explicit error feedback once, then route to human review on second failure."
  - q: "When does auto-tagging need human review?"
    a: "When confidence is below threshold, when tags trigger policy rules (PII, legal hold topics), when the model proposes a tag that was deprecated in the last 30 days, or when inter-annotator disagreement rate spikes on a tag slice during weekly QA sampling."
  - q: "How often should taxonomies change without retraining?"
    a: "Minor: add synonyms and aliases anytime—map to canonical ids. Major: adding/removing top-level categories quarterly with comms to downstream consumers. LLM prompts and few-shot examples should version-lock to taxonomy_version; bump on every structural change."
---
Within a week of launch, our agent had applied 1,400 unique tags to 6,000 documents. Finance filtered by `cost-optimization` and got three results while `cost_optimization`, `FinOps`, and `saving-money` each had hundreds—**same concept, four strings, zero governance.** Search looked broken. Dashboards lied. The model was not wrong about content; we were wrong about letting it name things freely.

Auto-tagging with agents accelerates metadata work until taxonomy debt catches up. The fix is not "better prompts" alone—it is a controlled vocabulary, constrained outputs, promotion workflows, and metrics that catch drift before users notice. This deep dive walks through designing taxonomies agents can safely apply at scale.

## Taxonomy as product infrastructure

A taxonomy is not a spreadsheet of labels—it is a **versioned API** consumed by search, recommendations, retention policies, and reporting.

Core entities:

```
Taxonomy (versioned)
  └── Category (e.g., "Security")
        └── Tag (canonical id: sec.zero-trust)
              ├── display_name: "Zero Trust"
              ├── aliases: ["zero trust architecture", "ZTA"]
              ├── parent: sec.network
              ├── status: active | deprecated | pending
              └── policy_flags: [pii_adjacent, legal_review]
```

Rules:

- **Canonical ids never change** — `sec.zero-trust` persists even if display name updates.
- **Aliases absorb LLM variation** — map surface forms to ids, do not create new ids for synonyms.
- **Deprecation is soft** — deprecated tags remain in history; auto-tagging must not apply them to new content.
- **Max tags per document** — cap at 5–8 depending on domain; forces prioritization.

Store taxonomy in git or a CMS with PR review—same rigor as API schema changes.

## Classification pipeline overview

```
Document ingest
    → Preprocess (language detect, chunk if long)
    → Retrieve taxonomy subset (hierarchical filter)
    → LLM classify (structured output, constrained tags)
    → Validate (unknown tag rejection, policy rules)
    → Confidence gate → auto-apply | review queue
    → Publish event (taxonomy_version, tag_ids[])
```

Long documents: classify per section, merge with max-score-wins per tag id—avoid tagging entire PDFs from title alone.

## Hierarchical retrieval before LLM call

Dumping 2,000 tags into a prompt fails on context limits and accuracy. Two-stage classification:

1. **Coarse router:** pick 1–3 top-level categories (10–20 choices).
2. **Fine classifier:** only tags under those categories (50–200 choices).

```python
def taxonomy_subset(taxonomy: Taxonomy, doc: Document, top_k_categories: int = 3) -> list[Tag]:
    # Cheap embedding match against category descriptions
    categories = taxonomy.top_level()
    scores = embed_rank(doc.summary, [c.description for c in categories])
    chosen = [categories[i] for i in scores.argsort()[-top_k_categories:]]
    return taxonomy.tags_under(chosen)
```

For agent-driven tagging during conversations, pass user-selected workspace taxonomy scope explicitly—do not infer from global corpus.

## Structured output with hard constraints

```typescript
import { z } from "zod";

function buildTagSchema(allowedTags: Tag[]) {
  const ids = allowedTags.map((t) => t.id) as [string, ...string[]];
  return z.object({
    tags: z
      .array(
        z.object({
          id: z.enum(ids),
          confidence: z.number().min(0).max(1),
          evidence_span: z.string().max(300),
        })
      )
      .max(8),
    taxonomy_version: z.literal(TAXONOMY_VERSION),
  });
}

async function classifyDocument(
  doc: Document,
  allowedTags: Tag[]
): Promise<ClassifyResult> {
  const schema = buildTagSchema(allowedTags);
  for (let attempt = 0; attempt < 2; attempt++) {
    const raw = await llm.complete({
      response_format: schema,
      messages: [
        {
          role: "system",
          content:
            `Apply tags ONLY from the allowed list. ` +
            `Quote evidence_span from the document. ` +
            `taxonomy_version must be ${TAXONOMY_VERSION}.`,
        },
        {
          role: "user",
          content: formatPrompt(doc, allowedTags),
        },
      ],
    });
    const parsed = schema.safeParse(JSON.parse(raw));
    if (parsed.success) return parsed.data;
    // Retry with validation errors in prompt
  }
  return { status: "needs_review", reason: "schema_validation_failed" };
}
```

Post-validate: `evidence_span` must appear as substring (normalized whitespace) in source text—blocks hallucinated justifications.

## Synonym resolution layer

Before validation, normalize model output:

```python
def resolve_tag(raw: str, taxonomy: Taxonomy) -> str | None:
    if raw in taxonomy.canonical_ids:
        return raw
    if raw in taxonomy.alias_map:
        return taxonomy.alias_map[raw]
    # fuzzy only above high threshold — otherwise None
    match = taxonomy.fuzzy_match(raw, threshold=0.92)
    return match.id if match else None
```

Log unresolved strings to a **candidate tag inbox**—product reviews weekly, promotes to alias or rejects. Never auto-create canonical ids from inbox without human approval.

## Confidence and review queues

Calibrate tag confidence separately from article suggestion confidence (related but different label distribution). Use historical accept rates from human reviewers.

| Calibrated P(correct) | Action |
|----------------------|--------|
| ≥ 0.90 | Auto-apply tags |
| 0.70 – 0.89 | Apply with `pending_review` flag visible in CMS |
| < 0.70 | Review queue only |

Review UI shows: document excerpt, proposed tags, evidence spans, alternative tags from second-pass model with temperature 0. Reviewer actions: accept, edit tags, reject—all feed training labels.

```sql
CREATE TABLE tag_review_queue (
  id            UUID PRIMARY KEY,
  document_id   TEXT NOT NULL,
  proposed_tags JSONB NOT NULL,
  reason        TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  resolved_at   TIMESTAMPTZ,
  resolver_id   TEXT,
  final_tags    JSONB
);
```

SLA review queue depth alerts—backlog > 500 items pages content ops, not ML.

## Policy-triggered mandatory review

Some tags always require human eyes regardless of confidence:

```yaml
# taxonomy policy overlay
mandatory_review:
  - tag_id: legal.subpoena
  - tag_id: pii.ssn_detected
  - flag: pii_adjacent
  - tag_id_pattern: "med.*"
```

Agent auto-tagging pipelines must load policy overlay at runtime—cached with taxonomy version.

## Multi-label metrics and drift detection

Track weekly:

- **Tag cardinality:** unique tags applied / documents — spikes signal drift
- **Unknown tag rejection rate** — should be near zero if constraints work
- **Deprecated tag usage** — should be zero on new docs
- **Inter-reviewer disagreement** on 5% sample
- **Coverage:** % docs with ≥1 tag after 24h

Alert when a tag's application rate jumps 3σ without corresponding content campaign—often precedes alias explosion.

```python
def detect_drift(tag_id: str, window_days: int = 7) -> bool:
    current = count_applications(tag_id, days=window_days)
    baseline = historical_mean(tag_id, weeks=12)
    return current > baseline + 3 * historical_std(tag_id)
```

## Agent workflow integration

When agents tag during live sessions (not batch ingest):

- Tag suggestions appear as **proposals** until user confirms—unlike batch auto-apply tiers.
- Session context narrows taxonomy: "This workspace uses marketing taxonomy v3 only."
- Tool definition:

```json
{
  "name": "apply_document_tags",
  "parameters": {
    "document_id": "string",
    "tag_ids": { "type": "array", "items": { "enum": ["...allowed ids..."] } }
  }
}
```

OpenAI-style tool enums enforce constraints at the API boundary—backup if structured output fails.

## Taxonomy versioning and migrations

Bump `taxonomy_version` when:

- Adding/removing top-level categories
- Merging tags (add `merged_into` pointer, stop auto-applying loser)
- Splitting tags (manual remap job on historical docs)

Migration job pattern:

```sql
-- merge sec.zero-trust and sec.zero_trust into sec.zero-trust-canonical
UPDATE document_tags SET tag_id = 'sec.zero-trust-canonical'
WHERE tag_id IN ('sec.zero-trust-legacy-a', 'sec.zero-trust-legacy-b');
```

Run migrations before enabling new classifier prompts. Dual-write tags under old and new ids during transition window if downstream consumers lag.

## Evaluation set construction

Build a golden set of 200–500 documents with expert labels:

- Stratify across categories, languages, doc lengths, edge cases (images-only PDFs, tables).
- Measure micro-F1 per tag and macro-F1 overall—macro catches neglected rare tags.
- Regression gate in CI: macro-F1 cannot drop >2 points vs main on golden set when prompt or model changes.

Include ** adversarial ** docs designed to tempt hallucinated tags ("This document mentions Kubernetes but is about employee benefits").

## What not to do

- Let each customer invent uncontrolled tags in shared multi-tenant search—namespace per tenant instead.
- Train embeddings on deprecated tags without filtering history.
- Use tag string as primary key in analytics—always canonical id.
- Skip reviewer tooling because "the model is 95% accurate"—the 5% clusters on high-risk content.

Taxonomies feel bureaucratic until search, compliance, and agents all consume the same ids. Auto-tagging agents are fast clerks; the taxonomy is the law they operate under. Constrain outputs, measure drift, promote synonyms deliberately, and treat taxonomy changes like API migrations—because that is what they are.

## Resources

- [SKOS Simple Knowledge Organization System (W3C)](https://www.w3.org/TR/skos-reference/)
- [Google Taxonomy Guidelines for Product Categories (pattern reference)](https://support.google.com/merchants/answer/6324406)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [Hierarchical Multi-Label Classification overview — Silla & Freitas](https://doi.org/10.1016/j.artmed.2010.08.003)
- [Apache Atlas — metadata taxonomy patterns](https://atlas.apache.org/)
