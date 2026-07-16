---
title: "Feedback Loops for Continuous Improvement"
slug: "llm-app-feedback-loops-improvement"
description: "Close the loop on LLM quality: thumbs signals, implicit metrics, human review queues, eval regression, and the pipeline that turns user friction into prompt and retrieval fixes."
datePublished: "2024-10-13"
dateModified: "2024-10-13"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "LLM feedback loop, continuous improvement AI, thumbs up down LLM, human in the loop ML, LLM quality monitoring"
faq:
  - q: "Are thumbs up/down buttons enough feedback?"
    a: "They're a start, not a system. Thumbs capture explicit sentiment on ~2–5% of turns and skew negative (users click when angry). Combine with implicit signals — copy events, follow-up rephrasing, session abandonment — and route high-confidence failures to human review."
  - q: "How often should I retrain or update prompts based on feedback?"
    a: "Prompt and retrieval fixes can ship weekly once you have a review queue. Fine-tuning waits until you have 500+ high-quality labeled examples per failure mode and evals prove the base model can't be prompt-fixed. Most quality gains come from retrieval and prompts, not weights."
  - q: "What should a human reviewer see?"
    a: "The user message, model response, retrieved chunks (with scores), tool call traces, and the feedback signal. Without retrieval context, reviewers blame the model for bad documents. Without traces, they can't tell tool failure from generation failure."
---

Thumbs-down on a chatbot response usually disappears into a database column nobody queries. Three months later the team wonders why satisfaction scores flatlined. Feedback loops fail not because users won't tell you what's wrong — because engineering never built the path from signal to fix.

A working loop has four stages: capture, triage, diagnose, deploy. Skip any one and you're collecting data for a dashboard that guilt-trips you at quarterly reviews.

## Capture: explicit and implicit

**Explicit signals**:

- Thumbs up/down with optional free-text
- "Regenerate" clicks (strong negative)
- Citation clicks (positive — user verified the source)
- Report/flag for safety issues

**Implicit signals** (no user effort):

```python
@dataclass
class ImplicitSignals:
    time_to_next_message_ms: int   # very fast = likely rephrasing
    session_ended_after_response: bool
    copied_response_text: bool
    follow_up_similarity: float    # embedding distance to prior user msg
```

A user who pastes the same question with different wording 8 seconds later didn't get what they needed — even if they never clicked thumbs-down.

Log everything with `trace_id`, `tenant_id`, `feature`, and `prompt_version` so you can correlate feedback to specific deployments.

## Triage: not all feedback is equal

Route to human review when:

- Explicit negative + high-value tenant
- Safety flag triggered
- Implicit rephrase score above threshold
- Response latency exceeded SLA (often indicates retrieval timeout → empty context → hallucination)

Sample 2–5% of positive interactions too — you need to know what "good" looks like for your golden dataset.

```python
async def triage(event: FeedbackEvent) -> ReviewPriority:
    if event.safety_flag:
        return ReviewPriority.P0
    if event.thumbs == "down" and event.tenant_tier == "enterprise":
        return ReviewPriority.P1
    if event.implicit.rephrase_score > 0.85:
        return ReviewPriority.P2
    if random.random() < POSITIVE_SAMPLE_RATE:
        return ReviewPriority.SAMPLE
    return ReviewPriority.SKIP
```

## Diagnose: label the failure mode

Reviewers shouldn't just say "bad." Use a fixed taxonomy:

| Label | Typical fix |
|-------|-------------|
| Retrieval miss | Ingestion, chunking, embedding model |
| Retrieval noise | Reranker, score threshold, filter |
| Prompt ambiguity | System prompt, few-shot examples |
| Tool failure | Handler code, timeout, auth |
| Hallucination | Grounding rules, citation requirement |
| Policy violation | Safety filter, output template |

Multiple labels allowed. "Hallucination" that was actually a retrieval miss sends you to fine-tune when you should re-index.

## Close the loop: from label to deploy

Every reviewed item should produce an actionable artifact:

1. **Golden eval case** — input + expected behavior added to CI eval suite
2. **Prompt change** — PR to prompt registry with version bump
3. **Document gap** — ticket to docs team to add missing content
4. **Bug** — tool handler fix with regression test

```yaml
# eval/golden/support_pricing_003.yaml
input: "Do you offer annual billing discounts?"
context_required:
  - doc: "pricing-faq-2024"
expected:
  must_mention: ["annual", "20%"]
  must_not_hallucinate: ["enterprise-only"]
source_feedback: "fb_8a3c2d"
```

When the fix ships, run eval regression before deploy. The feedback that triggered the fix becomes the test that prevents recurrence.

## Weekly improvement cadence

What works for teams I've seen:

- **Daily**: auto-alert on feedback rate spikes per feature
- **Weekly**: 30-minute review of P1/P2 queue, assign fixes
- **Bi-weekly**: eval score trend review, prompt version changelog
- **Monthly**: retrieval quality audit (sample 50 queries, manual relevance grading)

Don't wait for perfect attribution. Ship small prompt fixes weekly; measure eval delta; roll back if regression.

## Avoiding feedback pollution

- **Bot self-feedback**: filter automated test traffic from metrics
- **Position bias**: users thumbs-down the third regenerate regardless of quality — cap regenerations in analysis
- **Reviewer drift**: calibrate reviewers monthly against a shared gold set
- **Overfitting to loud users**: weight by tenant revenue and by failure severity, not click volume

## Thumbs feedback to eval case pipeline

Automated pipeline from production feedback to golden eval cases:

```python
async def process_feedback(feedback: FeedbackEvent):
    if feedback.rating == "down" and feedback.severity >= "P2":
        # Extract failure case
        eval_case = {
            "id": f"fb_{feedback.id}",
            "input": feedback.messages,
            "context": feedback.retrieval_context,
            "expected": {
                "must_not_include": extract_failure_reason(feedback.comment),
                "source_feedback": feedback.id,
            },
            "status": "pending_review",
        }
        await eval_case_queue.add(eval_case)

    elif feedback.rating == "up" and feedback.is_exemplary:
        # High-quality response becomes few-shot example
        await few_shot_pool.add(feedback.messages, quality_score=feedback.rating)
```

Every thumbs-down on P2+ severity becomes a candidate eval case. Human review before adding to golden set — don't auto-add unreviewed cases.

## Retrieval quality feedback loop

Feedback often indicates retrieval failure, not generation failure:

```python
async def diagnose_feedback(feedback: FeedbackEvent) -> DiagnosisType:
    if not feedback.retrieval_context:
        return "no_retrieval"
    relevance = await score_relevance(feedback.query, feedback.retrieval_context)
    if relevance < 0.5:
        return "retrieval_miss"  # fix: improve indexing, not prompt
    if feedback.hallucination_detected:
        return "generation_hallucination"  # fix: prompt or fine-tune
    return "generation_quality"  # fix: prompt engineering
```

Route feedback to correct team: retrieval miss → data/embedding team. Generation issue → prompt/ML team. Misrouting wastes fix cycles.

## Closed-loop improvement metrics

Track the full feedback → fix → eval cycle:

```python
IMPROVEMENT_METRICS = [
    "feedback.thumbs_down_rate",           # should trend down
    "feedback.to_eval_case_conversion",    # % of P2 feedback → eval cases
    "eval.regression_rate_post_fix",       # % of fixes that cause new failures
    "eval.pass_rate_trend",                # should trend up over months
    "time_to_fix_p2_feedback_hours",       # target <48 hours
]
```

Monthly review: pass rate trend, top failure categories, fix velocity. Stagnant pass rate despite fixes indicates eval set not representative of production failures.

## Failure modes

- **Feedback not linked to request context** — can't reproduce failure for eval case
- **All feedback treated as generation issue** — retrieval misses fixed with prompt changes
- **Eval cases added without review** — noisy cases degrade eval quality
- **No regression test after fix** — same failure recurs next month
- **Overfitting to loud users** — high-volume free tier drives roadmap over paying customers

## Production checklist

- P2+ thumbs-down automatically creates candidate eval case
- Feedback diagnosed: retrieval miss vs generation issue vs hallucination
- Eval case human-reviewed before addition to golden set
- Fix PR must show eval pass rate improvement before merge
- Feedback linked to full request context (messages, retrieval, model version)
- Monthly improvement metrics review with pass rate trend

## Resources

- [LangSmith feedback and evaluation](https://docs.smith.langchain.com/evaluation/how_to_guides/human_feedback)
- [OpenAI evals framework](https://github.com/openai/evals)
- [Ragas evaluation metrics for RAG](https://docs.ragas.io/)
- [Humanloop prompt management and feedback](https://humanloop.com/docs)
- [Intercom AI quality monitoring patterns](https://www.intercom.com/blog/)
