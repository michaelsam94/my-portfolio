---
title: "AI Agents: Feature Flag Targeting Rules"
slug: "agent-feature-flag-targeting-rules"
description: "Feature Flag Targeting Rules: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-03-11"
dateModified: "2026-03-11"
tags: ["AI", "Agent", "Feature"]
keywords: "agent, feature, flag, targeting, rules, ai, production, engineering, architecture"
faq:
  - q: "What attributes should agent feature flags target on?"
    a: "Prefer stable identifiers: tenant_id, org_id, agent_version, deployment_region, and session_id for stickiness. Avoid targeting on free-text prompts or PII-derived guesses. For model experiments, target on hashed user_id with deterministic bucketing so the same user stays in cohort across requests."
  - q: "How do percentage rollouts work without biasing agent eval metrics?"
    a: "Use consistent hashing on a unit id (user or session) so cohort membership is stable. Never use random per-request rollouts for experiments measuring task completion — they contaminate within-session metrics. Report experiment results only on the assigned cohort, not global traffic."
  - q: "What is the kill-switch pattern for agent feature flags?"
    a: "Maintain a global override flag with highest priority that forces old model/prompt/tool path for all tenants — evaluated before any targeting rules. Agent incidents need sub-second disable without redeploy; cache locally with short TTL and fail closed to safe defaults when the flag service is unreachable."
  - q: "How do targeting rules interact with multi-tenant agent platforms?"
    a: "Order rules: global kill switch → tenant allowlist/blocklist → environment → percentage rollout within remainder. Enterprise tenants often require opt-in flags; never include them in blind percentage experiments without contract. Log evaluated rule id per request for support debugging."
---
The new RAG reranker flag was set to 10% of traffic using "random user" targeting. Support tickets spiked from enterprise tenants who happened to land in the bucket — but the dashboard showed flat global accuracy because the majority stayed on baseline. Worse, the same power users saw different rerankers on consecutive messages in one thread because targeting rolled dice per request. Targeting rules for agent platforms must be **deterministic, hierarchical, and tenant-aware** — not copy-pasted from web frontend flag tutorials.

Feature flags on agent stacks gate high-impact paths: model version, prompt template, tool allowlists, memory format, retrieval index. Targeting rules decide **who** gets **which** variant. Bad rules cause sticky incidents, biased experiments, and contractual violations with enterprise customers. This piece covers rule ordering, attribute selection, consistent hashing, kill switches, and observability for production agent targeting.

## Targeting model: hierarchy beats flat rules

Flat "if email ends with @corp.com" rules do not scale. Use a priority stack evaluated top-down; first match wins unless you explicitly accumulate (avoid that).

```
Priority 0 — GLOBAL_KILL (force baseline for all)
Priority 1 — TENANT_OVERRIDES (allowlist / blocklist / dedicated variant)
Priority 2 — ENVIRONMENT (staging always on)
Priority 3 — COHORT_EXPERIMENTS (percentage on hashed id)
Priority 4 — DEFAULT (off or production baseline)
```

Document this order in your flag spec. On-call should know kill switch is priority 0 without opening the vendor UI.

## Attributes safe for agent targeting

| Attribute | Use case | Caution |
|-----------|----------|---------|
| `tenant_id` / `org_id` | Enterprise beta, contractual features | Legal review for experiments |
| `user_id` (hashed) | Stable A/B on model quality | GDPR: lawful basis for bucketing |
| `session_id` | Stickiness within conversation | Session may span days |
| `agent_version` | Gradual rollout of orchestrator | Must update when deployment changes |
| `region` | Latency-sensitive model routing | Do not proxy as fairness proxy |
| `plan_tier` | Premium features | Clear product boundary |

**Never target on:** raw prompt text, inferred demographics, message embeddings, or real-time model outputs — unstable, non-reproducible, and often non-compliant.

## Consistent percentage rollouts

Per-request `random() < 0.1` breaks session coherence and poisons experiment analysis. Hash a stable key:

```typescript
import { createHash } from "crypto";

function bucket(key: string, experiment: string, buckets = 10000): number {
  const hash = createHash("sha256")
    .update(`${experiment}:${key}`)
    .digest();
  return hash.readUInt32BE(0) % buckets;
}

export function inRollout(
  unitId: string,
  flagKey: string,
  percentage: number,
): boolean {
  if (percentage <= 0) return false;
  if (percentage >= 100) return true;
  const threshold = Math.floor((percentage / 100) * 10000);
  return bucket(unitId, flagKey) < threshold;
}

// Targeting context for agent requests
export interface AgentFlagContext {
  tenantId: string;
  userId: string;
  sessionId: string;
  region: string;
  agentVersion: string;
  environment: "production" | "staging";
}

export function resolveRolloutUnit(ctx: AgentFlagContext, stickiness: "user" | "session"): string {
  return stickiness === "session" ? ctx.sessionId : ctx.userId;
}
```

Choose stickiness explicitly in flag metadata:

- **User stickiness** — model quality experiments, personalization.
- **Session stickiness** — prompt or tool schema changes that must not flip mid-run.

## Rule engine implementation

Vendor SDKs (LaunchDarkly, Unleash) provide targeting UI. For self-hosted or custom stacks, encode rules as data:

```yaml
# flags/rag-reranker-v2.yaml
key: rag-reranker-v2
default: false
rules:
  - name: global-kill
    priority: 0
    conditions:
      - flag: platform-kill-new-models
        equals: true
    variation: false

  - name: enterprise-blocklist
    priority: 1
    conditions:
      - attribute: tenant_id
        in: ["tenant_acme", "tenant_globex"]
    variation: false

  - name: staging-on
    priority: 2
    conditions:
      - attribute: environment
        equals: staging
    variation: true

  - name: beta-tenants
    priority: 3
    conditions:
      - attribute: tenant_id
        in: ["tenant_beta_1", "tenant_beta_2"]
    variation: true

  - name: canary-10pct
    priority: 4
    conditions:
      - attribute: rollout
        percentage: 10
        stickiness: user
        unit: user_id
    variation: true
```

Evaluator with audit trail:

```typescript
interface RuleMatch {
  flagKey: string;
  matchedRule: string;
  variation: boolean;
  unitId: string;
}

export function evaluateFlag(
  spec: FlagSpec,
  ctx: AgentFlagContext,
): RuleMatch {
  const sorted = [...spec.rules].sort((a, b) => a.priority - b.priority);

  for (const rule of sorted) {
    if (matches(rule, ctx, spec.key)) {
      return {
        flagKey: spec.key,
        matchedRule: rule.name,
        variation: rule.variation,
        unitId: resolveRolloutUnit(ctx, rule.stickiness ?? "user"),
      };
    }
  }
  return {
    flagKey: spec.key,
    matchedRule: "default",
    variation: spec.default,
    unitId: ctx.userId,
  };
}
```

Emit `matchedRule` to structured logs — support asks "why did this session get v2?" daily.

## Kill switch and fail-safe defaults

Agent incidents require instant revert. Patterns:

**Platform kill flag** — one boolean disables all experimental model paths; evaluated first in every request.

**Local cache with stale-while-revalidate** — flag SDK outage should not block requests; default to `false` for enable-new-behavior flags and `true` for safety flags (e.g., `require-content-filter`).

```typescript
const CACHE_TTL_MS = 30_000;
const cache = new Map<string, { value: boolean; expires: number }>();

export async function getFlagSafe(key: string, ctx: AgentFlagContext, fallback: boolean): Promise<boolean> {
  const cacheKey = `${key}:${ctx.tenantId}:${ctx.userId}`;
  const hit = cache.get(cacheKey);
  if (hit && hit.expires > Date.now()) return hit.value;

  try {
    const result = evaluateFromControlPlane(key, ctx);
    cache.set(cacheKey, { value: result, expires: Date.now() + CACHE_TTL_MS });
    return result;
  } catch {
    metrics.increment("flag_eval_fallback_total", { key });
    return fallback;
  }
}
```

Run game days: disable flag vendor API and verify agents continue on safe defaults without elevated error rates.

## Multi-variate and mutual exclusion

Launching reranker-v2 and prompt-v3 simultaneously confounds metrics. Use **mutually exclusive experiment groups**:

```typescript
const EXPERIMENT_LAYER = "rag-quality-q1";

export function assignVariant(userId: string): "control" | "reranker" | "prompt" {
  const b = bucket(userId, EXPERIMENT_LAYER, 3);
  if (b === 0) return "control";
  if (b === 1) return "reranker";
  return "prompt";
}
```

One hash bucket maps to one variant. Document layer salt so future experiments do not collide.

## Observability and experiment integrity

Dashboards per flag:

- `flag_evaluation_total{flag, rule, variation}`
- Conversion metrics **split by matched_rule** not just variation
- Sample ratio mismatch (SRM) alerts when cohort sizes deviate from configured percentage

For agent task completion, pre-register:

- Primary metric (e.g., `task_resolved_without_escalation`)
- Guardrail metrics (latency p95, token cost, safety refusal rate)
- Minimum runtime before peeking

Targeting mistakes show up as SRM — if enterprise blocklist fails open, canary percentage skews and experiment results are invalid.

## Testing targeting rules

Unit-test rule ordering with table-driven cases:

```typescript
describe("rag-reranker-v2 targeting", () => {
  it("kill switch overrides beta tenant allowlist", () => {
    const ctx = baseCtx({ tenantId: "tenant_beta_1" });
    mockFlag("platform-kill-new-models", true);
    expect(evaluateFlag(spec, ctx).variation).toBe(false);
    expect(evaluateFlag(spec, ctx).matchedRule).toBe("global-kill");
  });

  it("consistent bucket for same user", () => {
    const ctx = baseCtx({ userId: "user-42" });
    const a = evaluateFlag(spec, ctx);
    const b = evaluateFlag(spec, ctx);
    expect(a).toEqual(b);
  });
});
```

Integration tests: synthetic tenants hitting each rule path; verify logs contain `matchedRule`.

## Governance

- Require PM + eng signoff for rules affecting >1% production traffic.
- Enterprise tenants: written opt-in for experiments; dedicated override rules.
- Rotate experiment layers quarterly; retire flags with zero evaluations for 30 days.

## The takeaway

Feature flag targeting for agent platforms is a control-plane product: hierarchical rules, stable bucketing units, session vs user stickiness, global kill switches, and logged rule matches. Random percentage rollouts and flat attribute checks fail under multi-tenant load and long-lived sessions. Implement consistent hashing, explicit priority stacks, fail-safe defaults, and experiment layers — then wire observability so every support question about variant assignment has an auditable answer.

## Resources

- [LaunchDarkly — Targeting rules](https://docs.launchdarkly.com/home/flags/targeting-rules)
- [Unleash — Activation strategies](https://docs.getunleash.io/reference/activation-strategies)
- [Split — Consistent hashing for experiments](https://www.split.io/blog/consistent-hashing/)
- [Google — Overlapping experiment design](https://developers.google.com/analytics/devguides/collection/analyticsjs/experiments)
- [Evan Miller — Sample ratio mismatch](https://www.evanmiller.org/experiment-design.html)
- [OpenFeature — Vendor-neutral flag SDK spec](https://openfeature.dev/)
