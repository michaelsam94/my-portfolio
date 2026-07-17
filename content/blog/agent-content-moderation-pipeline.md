---
title: "AI Agents: Content Moderation Pipeline"
slug: "agent-content-moderation-pipeline"
description: "Engineer content moderation pipelines for AI agents—multi-stage classifiers, human review queues, policy versioning, and latency budgets that block harm without killing conversational flow."
datePublished: "2025-05-06"
dateModified: "2025-05-06"
tags: ["AI", "Agent", "Content"]
keywords: "content moderation pipeline, AI safety classifier, human-in-the-loop review, agent output filtering, moderation latency, policy enforcement"
faq:
  - q: "Should moderation run on user input, model output, or both?"
    a: "Both, with different policies. Input moderation blocks prompt injection, illegal requests, and disallowed content before expensive agent runs. Output moderation catches model hallucinations of harmful content, PII leakage, and brand violations before users or downstream systems see results. Skipping either side leaves a hole attackers and models will find."
  - q: "How do teams keep moderation latency acceptable in real-time agent chat?"
    a: "Tier classifiers: fast regex and hash lists under 10ms, small ONNX or API classifiers under 100ms for sync path, heavy multimodal or LLM-judge models async with streaming holdback. Stream tokens to users only after first-chunk output scan passes or use a buffer window that trades slight delay for safety."
  - q: "When is human review required vs automated block?"
    a: "Automate clear allow and clear deny with high-confidence thresholds. Route ambiguous band—typically 0.4–0.7 calibrated scores—to human review queues with SLA timers. Agent products generating public-facing content or medical/legal adjacency should default ambiguous cases to hold, not allow."
  - q: "How should moderation policies version across model upgrades?"
    a: "Pin policy packs to semver independent of model weights. When swapping models, replay golden violation and false-positive suites before promotion. Log policy_version on every decision so incidents trace to ruleset, not mystery. Roll out policy changes canary per tenant before global enable."
---
A user asked our sales agent for "creative ways to describe our competitor's failures." The model complied with language that was legally actionable. The transcript looked fine in demo metrics—high satisfaction, fast response—until counsel saw the screenshot. We had a single OpenAI moderation API call on **input only**. Output sailed through unchecked because "the model is aligned." Alignment is statistical, not guaranteed. Production agent systems need moderation **pipelines**, not single API checks.

Content moderation for agents differs from static UGC platforms. Content is generated in multi-step tool loops, may include retrieved documents, and streams token-by-token. Policies span harassment, PII, regulated advice, and tenant-specific brand rules. The pipeline must be fast enough for chat, auditable enough for regulators, and flexible enough to update without redeploying the agent core.

## Pipeline architecture overview

```
User message ──► Input stage ──► Agent run ──► Output stage ──► User / tools
                    │                              │
                    ├─ block / rewrite              ├─ block / mask / hold
                    └─ log + policy_version         └─ human queue (async)
```

Stages should be **composable middleware**, not monolithic functions:

| Stage | Purpose | Typical latency |
|-------|---------|-----------------|
| L0: blocklists | hashes, regex, IP/domain deny | <5ms |
| L1: lightweight classifiers | toxicity, sexual, violence | 20–80ms |
| L2: domain policy | tenant rules, PII patterns | 10–50ms |
| L3: LLM judge | nuanced policy, context-heavy | 500ms–2s (async) |

Sync path covers L0–L2 for chat; L3 handles appeals, ambiguous flags, and batch review.

## Input moderation: before the agent runs

Input checks prevent wasted LLM spend and block attacks early.

**Prompt injection signals** — not solvable by keyword lists alone, but combine:

- Structural heuristics (system prompt override patterns)
- Embedding similarity to known injection corpus
- Classifier trained on ignore-previous-instructions variants

**Policy categories** — map to actions: `allow`, `rewrite`, `block`, `escalate`.

```typescript
type ModerationAction = "allow" | "rewrite" | "block" | "escalate";

interface ModerationDecision {
  action: ModerationAction;
  categories: string[];
  confidence: number;
  policyVersion: string;
  requestId: string;
}

export async function moderateInput(
  text: string,
  tenant: TenantPolicy
): Promise<ModerationDecision> {
  const l0 = blocklist.match(text);
  if (l0) return deny(l0.category, 1.0, tenant.policyVersion);

  const l1 = await classifier.score(text, tenant.enabledCategories);
  if (l1.maxScore >= tenant.blockThreshold) return deny(l1.topCategory, l1.maxScore, tenant.policyVersion);
  if (l1.maxScore >= tenant.escalateThreshold) return escalate(l1);

  return { action: "allow", categories: [], confidence: 1 - l1.maxScore, policyVersion: tenant.policyVersion, requestId: crypto.randomUUID() };
}
```

Log every decision with `requestId` correlated to agent `run_id` for downstream tracing.

## Output moderation: streaming complexity

Batch moderation is easy; streaming is where products fail. Options:

**Buffer window** — hold first N tokens or first sentence until L1 passes, then stream with periodic re-scan every M tokens. Users see slight startup delay.

**Dual stream** — internal buffer full speed; user-facing stream lags one chunk behind moderation checkpoint.

**Post-hoc retract** — stream immediately but ability to redact and send correction if late flag fires—bad UX for serious violations, acceptable for minor PII slips with apology pattern.

```typescript
async function* moderatedStream(
  source: AsyncIterable<string>,
  policy: OutputPolicy
): AsyncIterable<string> {
  let buffer = "";
  for await (const chunk of source) {
    buffer += chunk;
    if (buffer.length >= policy.initialBufferChars) {
      const decision = await moderateOutput(buffer, policy);
      if (decision.action === "block") {
        yield policy.blockedMessage;
        return;
      }
      yield buffer;
      buffer = "";
    }
  }
  if (buffer) {
    const decision = await moderateOutput(buffer, policy);
    if (decision.action !== "block") yield buffer;
  }
}
```

For tool outputs (JSON, HTML snippets), run structured moderation—HTML through sanitizer plus category classifier; JSON through schema-aware PII detectors.

## Human-in-the-loop review queues

Automated systems misclassify. Human review is the appeal layer and training signal.

Queue design:

- Priority by severity score and user visibility (public share > private draft)
- SLA timers with auto-action on expiry (default deny for high-risk tenants)
- Reviewer UI shows full agent context: user message, retrieved docs, tool calls, model version, policy_version
- Single-click labels feed back into classifier retraining

```sql
CREATE TABLE moderation_reviews (
  review_id       UUID PRIMARY KEY,
  run_id          UUID NOT NULL,
  stage           TEXT NOT NULL, -- 'input', 'output', 'tool'
  payload_ref     TEXT NOT NULL,
  classifier_score FLOAT,
  status          TEXT NOT NULL, -- 'pending', 'approved', 'rejected'
  reviewer_id     UUID,
  decided_at      TIMESTAMPTZ,
  policy_version  TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Avoid showing raw moderator decisions to end users as "you were flagged"—generic messaging reduces gaming.

## Tenant and vertical policy packs

Base platform policy plus tenant overlays:

```yaml
# policies/tenant-healthcare overlay
extends: base-v2
categories:
  medical_advice:
    action: block
    threshold: 0.35  # stricter than default 0.6
  pii_phi:
    action: escalate
    patterns:
      - mr_number
      - ndc_code
output:
  require_citation_for: [medical_claims]
```

Compile YAML to runtime evaluators; hot-reload with version bump. Agent orchestrator reads `policy_version` at run start and pins for session consistency.

## PII and secrets detection

Agents amplify leakage—models quote retrieved docs verbatim. Layer detectors:

- Regex for credit cards, SSN patterns (locale-aware)
- NER models for names, emails, phone numbers
- Entropy-based secret detection (API keys in tool output)

Action hierarchy: **mask** (replace with `[REDACTED]`) when meaning preserved; **block** when entire message is toxic leak; **escalate** when uncertain.

```python
def redact_pii(text: str, spans: list[Span]) -> str:
    out = []
    last = 0
    for s in sorted(spans, key=lambda x: x.start):
        out.append(text[last:s.start])
        out.append("[REDACTED]")
        last = s.end
    out.append(text[last:])
    return "".join(out)
```

Run PII detection on **tool returns** before they enter model context again—prevents echo loops.

## Metrics and calibration

Track precision/recall on golden sets weekly—not just volume:

| Metric | Why |
|--------|-----|
| False positive rate | User frustration, support load |
| False negative rate (sampled audit) | Safety incidents |
| Time-to-decision p95 | Chat latency budget |
| Human queue depth | Staffing signal |
| Block rate by category | Policy drift detector |

Calibrate thresholds per category; universal 0.5 score is lazy. Medical advice and spam need different operating points.

Shadow mode new policies: log WOULD_BLOCK without enforcing, compare to human labels, then promote.

## Integration with agent orchestration

Moderation failures must integrate with run state:

- **Block input** — return user-visible explanation without starting run; do not charge credits.
- **Block output** — mark run `completed_with_safety_stop`; store internal full transcript under restricted ACL for review.
- **Escalate** — pause run in `awaiting_review`; resume webhook on human decision.

Tool calls that post externally (email, Slack) require **outbound moderation** gate—stricter than display moderation.

```typescript
async function beforeToolExecute(call: ToolCall, ctx: RunContext) {
  const text = serializeForModeration(call.args);
  const decision = await moderateOutput(text, ctx.tenant.outboundPolicy);
  if (decision.action === "block") {
    throw new ToolBlockedError(decision);
  }
}
```

## Legal, locale, and language

Moderation models trained predominantly on English fail on code-switching and dialect. Route by detected language to appropriate classifier or multilingual model. Locale affects PII patterns and legally sensitive categories (EU hate speech laws vs US First Amendment contexts in platform policy, not legal advice).

Document moderation decisions as **platform policy enforcement**, not government speech adjudication—legal teams care about this distinction in user-facing ToS.

## Testing the pipeline

Maintain adversarial suites:

- Known injection strings
- Benign edge cases (medical discussion in healthcare app = allow)
- Retrieved doc containing hidden instructions
- Token-split evasion (`h@te` boundaries across stream chunks)

CI runs golden tests on every policy YAML change. Load test moderation services separately from LLM—spikes in chat should not collapse L1 classifiers.

## Related concepts

Moderation connects to [toxicity classifier thresholds](https://blog.michaelsam94.com/agent-toxicity-classifier-threshold/), [responsible AI review](https://blog.michaelsam94.com/agent-responsible-ai-review/), and [watermarking outputs](https://blog.michaelsam94.com/agent-watermarking-outputs/) for synthetic media disclosure.

## The takeaway

Agent content moderation is a staged pipeline with distinct input, output, and outbound tool gates—not a single API call you add before launch. Design for streaming latency, human review of ambiguous cases, versioned tenant policies, and audit logs that tie every decision to a policy version and run ID. Models change weekly; your moderation layer is what keeps production conversations inside the boundary users and lawyers expect.

## Resources

- [OpenAI Moderation API documentation](https://platform.openai.com/docs/guides/moderation) — baseline classifier integration
- [Perspective API](https://perspectiveapi.com/) — toxicity scoring reference
- [Google Jigsaw safety models research](https://jigsaw.google.com/) — classifier context
- [NCMEC CyberTipline reporting requirements](https://www.missingkids.org/gethelpnow/cybertipline) — CSAM legal obligations for platforms
- [Partnership on AI synthetic media guidance](https://partnershiponai.org/) — disclosure and labeling practices
