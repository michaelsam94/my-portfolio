---
title: "AI Agents: Article Suggestion Confidence"
slug: "agent-article-suggestion-confidence"
description: "Calibrate and surface confidence for agent-driven article suggestions—combining retrieval scores, LLM self-assessment, and UX thresholds so editors trust what they see."
datePublished: "2025-05-02"
dateModified: "2025-05-02"
tags: ["AI", "Agent", "Article"]
keywords: "article suggestion confidence, RAG confidence scoring, recommendation calibration, LLM uncertainty, editorial AI, suggestion ranking"
faq:
  - q: "Should article suggestion confidence come from the retriever or the LLM?"
    a: "Both, blended. Retriever scores measure lexical/semantic similarity to the query; they miscalibrate across corpora. LLM self-reported confidence is useful for reasoning fit but overconfident on hallucinated citations. Combine with a learned calibrator trained on editor accept/reject labels."
  - q: "What confidence threshold should auto-surface suggestions?"
    a: "There is no universal number—calibrate per product. Start with 0.85 calibrated probability for auto-pin in CMS sidebars, 0.65–0.85 for 'suggested' chips requiring one click, below 0.65 hide unless the editor explicitly asks for exploratory mode."
  - q: "How do you prevent confident-but-wrong article suggestions?"
    a: "Require citation grounding: every suggestion above the display threshold must link retrieved chunks with overlap checks. Down-rank or block suggestions where the LLM summary diverges from source text beyond an edit-distance threshold."
  - q: "How should confidence change across a multi-turn agent session?"
    a: "Decay stale suggestions when the conversation topic shifts—recompute retrieval with the latest user intent summary, not the first message. Surface 'confidence dropped' when new context contradicts earlier picks."
---
The editor clicked "Accept" on three article suggestions in a row, then rejected the fourth with a note: "Confident tone, completely wrong topic." Our agent had ranked it first because the retriever loved overlapping keywords—"kubernetes," "scaling," "pods"—while the user's actual question was about **billing disputes**. The model's prose sounded sure. **Confidence without calibration is UX malpractice.**

Article suggestion confidence is the bridge between retrieval plumbing and editorial trust. Get it wrong and editors disable the feature; get it right and suggestions feel like a sharp research assistant. This deep dive covers scoring architecture, calibration, grounding checks, and the UI patterns that make confidence numbers honest.

## What "confidence" means in a suggestion pipeline

A suggestion is not a single score—it is a bundle:

```
User intent (summarized)
    → Candidate articles (retriever top-k)
    → Relevance features per candidate
    → Calibrated confidence P(accept | features)
    → Grounding verification
    → Display tier (auto / suggest / hide)
```

Define confidence operationally: **the estimated probability that a domain expert would accept this suggestion given current context.** That definition gives you a label for offline training (editor clicks) and keeps product and ML aligned.

Raw cosine similarity from your vector store is not a probability. A score of 0.82 on Monday means something different than 0.82 after you re-embed the corpus on Tuesday. Calibrate.

## Feature stack for ranking

Build a feature vector per (query, article) pair:

| Feature | Source | Notes |
|---------|--------|-------|
| `dense_sim` | Embedding cosine | Top retriever signal |
| `bm25_norm` | Lexical search | Catches proper nouns embeddings miss |
| `recency_days` | Article metadata | Decay stale news |
| `authority_score` | Internal PageRank or manual tier | Prefer canonical docs |
| `click_through_hist` | Past editor accepts | Cold-start carefully |
| `llm_match_grade` | Structured LLM rating 1–5 | Cheap cross-encoder substitute |
| `topic_overlap` | NER entity intersection | Penalize keyword collisions |
| `contradiction_flag` | NLI model | Down-rank conflicting claims |

Keep feature extraction deterministic and logged. When an editor rejects a 0.91 suggestion, you need to replay features—not guess.

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class SuggestionFeatures:
    dense_sim: float
    bm25_norm: float
    recency_days: float
    llm_match_grade: float
    topic_overlap: float
    contradiction_flag: float

def featurize(query: str, article_id: str, ctx: dict) -> SuggestionFeatures:
    chunks = ctx["retriever"].get_chunks(article_id, query)
    return SuggestionFeatures(
        dense_sim=chunks[0].score,
        bm25_norm=ctx["bm25"].score(query, article_id),
        recency_days=(ctx["now"] - ctx["articles"][article_id].published).days,
        llm_match_grade=ctx["grader"].grade(query, chunks[:3]),
        topic_overlap=entity_overlap(query, chunks),
        contradiction_flag=nli_contradiction(query, chunks),
    )
```

## Calibrating scores to probabilities

Train a lightweight model—logistic regression or gradient boosted trees—on historical `(features, accepted_bool)` rows. Evaluate with **calibration curves**, not just AUC. Editors experience probabilities, not ranking metrics.

```python
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression

base = LogisticRegression(max_iter=1000)
clf = CalibratedClassifierCV(base, method="isotonic", cv=5)
clf.fit(X_train, y_train)

def confidence(features: SuggestionFeatures) -> float:
    x = np.array([[
        features.dense_sim,
        features.bm25_norm,
        features.recency_days,
        features.llm_match_grade,
        features.topic_overlap,
        features.contradiction_flag,
    ]])
    return float(clf.predict_proba(x)[0, 1])
```

Re-calibrate monthly or when you change embedding models. Version calibrators (`calibrator_v2025_05`) and shadow-deploy new ones before switching production thresholds.

## LLM grading without overconfidence

Asking an LLM "how confident are you?" returns bloated numbers. Instead, use **structured rubric grading**:

```typescript
const gradeSchema = z.object({
  relevance: z.number().min(1).max(5),
  specificity: z.number().min(1).max(5),
  citation_support: z.number().min(1).max(5),
  reasoning: z.string().max(500),
});

async function gradeMatch(
  userIntent: string,
  articleExcerpt: string
): Promise<z.infer<typeof gradeSchema>> {
  const response = await llm.complete({
    model: "gpt-4o-mini",
    response_format: gradeSchema,
    messages: [
      {
        role: "system",
        content:
          "Grade how well the excerpt helps answer the intent. " +
          "citation_support=1 if excerpt does not contain evidence for claims.",
      },
      {
        role: "user",
        content: `Intent: ${userIntent}\n\nExcerpt:\n${articleExcerpt}`,
      },
    ],
  });
  return gradeSchema.parse(JSON.parse(response));
}
```

Map rubric grades to features, not directly to UI percentages. The calibrator learns how much to trust the grader on your corpus.

## Grounding gate before display

High confidence with ungrounded text is worse than moderate confidence with citations. Before surfacing:

1. Retrieve top chunks for the suggested article.
2. Check that the suggestion blurb's factual claims appear in chunk text (token overlap + entailment).
3. If grounding fails, cap displayed confidence at 0.5 regardless of model score.

```python
def grounding_penalty(suggestion_text: str, chunks: list[str]) -> float:
    claims = extract_claims(suggestion_text)  # sentence split + filter
    supported = 0
    for claim in claims:
        if any(entails(chunk, claim) for chunk in chunks):
            supported += 1
    if not claims:
        return 1.0
    ratio = supported / len(claims)
    return ratio  # multiply into final confidence
```

Log grounding failures separately—they often indicate summarization drift, not retrieval failure.

## UX tiers editors actually understand

Do not show raw floats like `0.847`. Map to three tiers with honest copy:

| Calibrated P(accept) | UI tier | Copy |
|---------------------|---------|------|
| ≥ 0.85 | Strong match | "Highly relevant — verified against source" |
| 0.65 – 0.84 | Possible match | "Related — review before inserting" |
| < 0.65 | Hidden (default) | Shown only in "Explore more" drawer |

Optional: show **why** in a collapsible panel—top matching entities, recency, excerpt highlight—not the raw feature vector.

When confidence drops between turns, animate stale suggestions gray and label "Context changed — refresh suggestions." Editors forgive machine uncertainty; they do not forgive silent wrongness.

## Multi-turn intent tracking

Article suggestions tied to message one become wrong by message five. Maintain a rolling **intent summary** updated each turn:

```typescript
async function updateIntentSummary(
  prior: string,
  latestUserMessage: string
): Promise<string> {
  const { summary, shift_detected } = await llm.complete({
    schema: z.object({
      summary: z.string(),
      shift_detected: z.boolean(),
    }),
    messages: [
      {
        role: "system",
        content:
          "Merge the prior intent with the new message. " +
          "Set shift_detected if topic materially changed.",
      },
      { role: "user", content: `Prior: ${prior}\nNew: ${latestUserMessage}` },
    ],
  });

  if (shift_detected) {
    metrics.increment("suggestion.intent_shift");
  }
  return summary;
}
```

Re-run retrieval against the summary, not the full transcript, to keep latency bounded. Invalidate cached suggestions when `shift_detected` is true.

## Evaluation harness

Weekly offline eval notebook is not enough. Automate:

**Ranking metrics:** NDCG@5 against held-out editor sessions.

**Calibration error:** Expected Calibration Error (ECE) binned by 0.1 probability buckets.

**Slice analysis:** Confidence accuracy on low-traffic topics, non-English queries, breaking news.

**Online A/B:** Accept rate, time-to-insert, downstream article corrections within 24h (proxy for silent wrongness).

Alert when ECE exceeds 0.08 or when accept rate drops 15% WoW on the same traffic slice.

## Failure modes we have seen

**Keyword collision:** "Apple" the company vs fruit. Fix with entity linking in features, not bigger embeddings alone.

**Popularity bias:** Calibrator learns "always suggest top 10 articles." Penalize candidates with excessive historical impressions without accepts.

**Stale calibrator after model swap:** Embedding model upgrade shifts score distribution. Shadow calibrator for two weeks minimum.

**Over-filtering exploratory mode:** Power users want low-confidence tangents. Offer explicit "wide search" that disables the 0.65 floor with a warning banner.

## Operational checklist

- [ ] Calibrator version pinned in config; rollback documented
- [ ] Grounding penalty logged with rejection reason codes
- [ ] Dashboard: accept rate by confidence tier
- [ ] Editor feedback button feeds label store within 5 minutes
- [ ] Intent shift metric on-call runbook entry

Confidence is a product surface, not an ML vanity metric. When editors trust the tier labels, they move faster. When they do not, they bypass your agent entirely—and no retrieval tweak fixes that.

Ship a weekly "confidence report" email to editorial leads: top rejected high-confidence suggestions, emerging topic gaps, and calibration drift by section. That loop closes the gap between model metrics and newsroom reality faster than any offline benchmark refresh.

## Resources

- [Guo et al. — On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599)
- [PyTorch Temperature Scaling for calibration](https://github.com/gpleiss/temperature_scaling)
- [Google PAIR — People + AI Guidebook (confidence in UX)](https://pair.withgoogle.com/guidebook/chapters/mental-models/)
- [BEIR benchmark — retrieval evaluation across domains](https://github.com/beir-cellar/beir)
- [Anthropic — Constitutional AI and uncertainty (research context)](https://www.anthropic.com/research)
