---
title: "AI Agents: Cold Start Recommendations"
slug: "agent-cold-start-recommendations"
description: "Bootstrapping agent recommendations for new users, tools, and tenants — popularity priors, content-based fallbacks, LLM-generated profiles, and exploration without trashing early UX."
datePublished: "2025-07-14"
dateModified: "2025-07-14"
tags: ["AI", "Agent", "Cold"]
keywords: "cold start recommendations, agent personalization, new user agent UX, exploration exploitation agents, content-based agent routing"
faq:
  - q: "What cold-start problems do agent platforms face?"
    a: "Three distinct cases: new users (no interaction history), new tools/skills (no usage stats), and new tenants (no org-level priors). Each needs different fallback signals — global popularity, content metadata, role-based defaults, or LLM-inferred intent from onboarding forms."
  - q: "Should cold-start agents explore randomly or stay conservative?"
    a: "Conservative for safety-critical paths (finance, healthcare): show proven defaults until confidence threshold. Explore in low-risk surfaces (suggested prompts, optional tools) using Thompson sampling or epsilon-greedy with caps. Never A/B test auth flows on cold users without explicit consent."
  - q: "Can LLMs generate cold-start user profiles safely?"
    a: "Yes for non-sensitive inference: job title + stated goal → suggested agent modes and tool bundles. Never persist inferred demographics; treat LLM profiles as ephemeral session context; validate outputs against an allowlist of tools and data scopes before execution."
  - q: "How long until a user is 'warm' enough for personalized routing?"
    a: "Typical thresholds: 5+ completed sessions OR 20+ tool interactions OR explicit preference save. Below that, blend 70% global prior / 30% content-based. Enterprise tenants can warm faster via SSO group membership mapped to preset profiles."
---
A first-time user opens your agent workspace and sees an empty screen — or worse, recommendations trained on power users that suggest "batch reindex the vector store" and "write a custom MCP server." Cold start is not a niche ML problem for agent products; it is the **first-session experience** that determines whether someone returns. Recommendation systems built for e-commerce do not transfer cleanly: agent actions have side effects, tools touch live data, and a bad suggestion is a failed task, not a ignored product tile.

This piece covers cold-start strategies for agent personalization — what to recommend before you know the user, how to bootstrap new tools into the catalog, and how to explore without compromising safety.

## Three cold-start axes

Agent platforms hit cold start on three independent axes:

| Axis | Unknown | Risk if wrong |
|------|---------|---------------|
| User | Preferences, skill level, domain | Wrong tool → data leak or frustration |
| Item (tool/skill/prompt) | Quality, compatibility | New tool promoted → outages |
| Tenant/org | Compliance tier, data residency | Cross-tenant prior leakage |

Treat them separately. A warm user on a new tenant still needs tenant-scoped priors. A new user in a mature tenant inherits org defaults but not colleague behavior (privacy).

```
                    ┌──────────────────┐
         new user   │  onboarding form │
                    │  SSO groups      │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │   cold-start ranker         │
              │   blend: global + content   │
              │   + org prior + LLM sketch  │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  suggested tools / prompts  │
              │  (exploration budget capped)│
              └─────────────────────────────┘
```

## Global popularity priors — the honest baseline

Before personalization, **global task success rate** beats clever models:

```sql
-- nightly batch: tool popularity with success weighting
SELECT
  tool_id,
  count(*) AS uses,
  avg(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) AS success_rate,
  count(*) * avg(CASE WHEN outcome = 'success' THEN 1.0 ELSE 0.0 END) AS weighted_score
FROM agent_tool_events
WHERE created_at > now() - interval '30 days'
  AND tenant_id IS NOT NULL  -- exclude internal dogfood if biased
GROUP BY tool_id
HAVING count(*) >= 100
ORDER BY weighted_score DESC
LIMIT 20;
```

Expose top-N as "Popular with new users" only after Bayesian smoothing avoids ranking a tool with 3/3 successes above one with 970/1000:

```python
def smoothed_success_rate(successes: int, trials: int, prior_a: float = 2, prior_b: float = 2) -> float:
    """Beta-binomial mean — dampens tiny sample noise."""
    return (successes + prior_a) / (trials + prior_a + prior_b)
```

Popularity alone fails on long-tail domains — pair with content features.

## Content-based fallbacks from metadata

Every agent tool should ship with structured metadata:

```yaml
# tools/search_incidents.yaml
id: search_incidents
title: Search Incidents
description: Query PagerDuty and Jira for open incidents
tags: [sre, oncall, production]
required_scopes: [read_incidents]
risk_tier: low
embedding_text: "Find outages, pages, incident history, on-call"
```

At cold start, embed the user's stated goal from onboarding (or first message) and cosine-match against `embedding_text`:

```python
def content_based_tools(user_goal: str, catalog: list[Tool], embed_fn, k: int = 5) -> list[Tool]:
    q = embed_fn(user_goal)
    scored = [(t, cosine(q, embed_fn(t.embedding_text))) for t in catalog]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored[:k]]
```

Filter by **risk_tier** and **required_scopes** before ranking — content similarity must not surface admin tools to read-only users.

## LLM-generated session profiles (ephemeral)

Use an LLM once at session start to infer a structured profile — not stored PII, regenerated each session unless user saves preferences:

```python
PROFILE_SCHEMA = {
    "domain": "sre | support | data | general",
    "experience": "beginner | intermediate | expert",
    "suggested_tool_ids": ["list of ids from allowlist"],
    "starter_prompts": ["max 3 short prompts"],
}

async def infer_cold_start_profile(user_message: str, org_defaults: dict) -> dict:
    prompt = f"""Given user goal: {user_message}
Org default domain: {org_defaults.get('domain', 'general')}
Return JSON matching schema. Only suggest tool IDs from: {ALLOWLIST}."""
    return await llm.json_completion(prompt, schema=PROFILE_SCHEMA)
```

Validate every suggested `tool_id` ∈ allowlist ∩ user's RBAC scopes. Reject profiles that mention credentials, bypass flows, or out-of-scope data sources.

Starter prompts reduce blank-page anxiety without executing tools — low risk, high UX value.

## Org and SSO priors for enterprise tenants

Enterprise cold start is often **warm at org level, cold at user level**. Map IdP groups to preset bundles:

```json
{
  "Okta_Group_SRE": {
    "pinned_tools": ["search_runbooks", "query_metrics", "create_incident"],
    "default_agent_mode": "ops_copilot",
    "exploration_allowed": false
  },
  "Okta_Group_Support": {
    "pinned_tools": ["search_kb", "draft_reply", "lookup_customer"],
    "default_agent_mode": "support_assist",
    "exploration_allowed": true
  }
}
```

Sync group mappings nightly; never infer group membership from behavior. Document in privacy policy which attributes come from SSO vs observed actions.

## Item cold start: launching new tools

New tools have zero usage history — downrank them in global popularity but **boost in targeted exploration slots**:

```python
def explore_exploit_score(
    tool: Tool,
    user_trust: float,
    global_rate: float,
    context_match: float,
    exploration_bonus: float = 0.1,
) -> float:
    if tool.launched_at > now() - timedelta(days=14):
        # UCB-style bonus for new items
        bonus = exploration_bonus * math.sqrt(math.log(total_sessions) / (tool.exposures + 1))
    else:
        bonus = 0
    return user_trust * (0.5 * global_rate + 0.5 * context_match) + bonus
```

Cap new-tool exposure at 5% of cold-start sessions until `exposures >= 500` and `success_rate >= org_median`. Kill-switch tools that spike error rates.

Shadow mode: run new tool recommendations in log-only (`would_recommend`) for a week before surfacing in UI.

## Exploration policies that respect agent safety

Multi-armed bandits popular in recommender systems need guardrails for agents:

1. **Arms = low-risk suggestions only** — prompts, read-only tools, UI layouts
2. **Never bandit-select** write tools, external HTTP, or code execution for cold users
3. **Thompson sampling** on success rate with Beta priors — explore tools with uncertain outcomes
4. **Epsilon-greedy** with ε ≤ 0.05 for consumer; ε = 0 for regulated

```python
import numpy as np

def thompson_sample_tool(tools: list[Tool]) -> Tool:
    samples = []
    for t in tools:
        a, b = t.successes + 2, (t.trials - t.successes) + 2
        samples.append((t, np.random.beta(a, b)))
    return max(samples, key=lambda x: x[1])[0]
```

Log every exploration decision with `policy_version` for audit.

## Warm-up transitions and hybrid scoring

Define explicit transition from cold → warm:

```python
def personalization_weight(interactions: int, sessions: int) -> float:
    """0 = fully cold, 1 = fully personalized."""
    if sessions >= 5 and interactions >= 20:
        return 1.0
    if sessions >= 2:
        return 0.4
    return 0.0

def final_rank(user_id: str, candidates: list[Tool]) -> list[Tool]:
    w = personalization_weight(get_stats(user_id))
    cold = content_popularity_blend(user_id)
    warm = collaborative_filter_score(user_id)
    return merge_scores(candidates, (1 - w) * cold + w * warm)
```

Sudden switches feel jarring — interpolate over 2–3 sessions. Show "We're learning your preferences" when `w` crosses 0.3.

## Metrics that matter for cold start

Dashboard four KPIs:

| Metric | Target | Notes |
|--------|--------|-------|
| First-session task completion | > 60% | Primary north star |
| Time-to-first-successful-tool-call | < 90s | Includes onboarding |
| Day-7 retention (cold cohort) | baseline + lift | A/B cold-start policies |
| Bad suggestion rate | < 2% | User dismiss + error within 30s |

Segment by acquisition channel — users from docs land differently from blank signups.

## Privacy and compliance

Cold-start systems tempt over-collection. Minimum viable onboarding: role + goal text. Do not require company size, location, or phone for agent recommendations.

If using LLM inference on onboarding text, route through data processing agreement-covered endpoints; redact before logging.

Right-to-erasure must delete warm profiles **and** derived popularity contributions — use differential privacy or per-user contribution caps if k-anonymity matters.

Cold-start recommendations for agents balance exploration with safety constraints generic recsys ignores. Start with smoothed global popularity and content metadata; add org SSO priors for enterprise; use ephemeral LLM profiles validated against allowlists; promote new tools through capped exploration; blend into collaborative filtering only after explicit warm-up thresholds. The first session is not a data collection exercise — it is a contract that the agent understands what the user is trying to do before suggesting tools that touch production.

## Resources

- [Recommender Systems Handbook — cold start chapter](https://link.springer.com/book/10.1007/978-1-4899-7637-6)
- [Microsoft Recommenders — cold-start notebooks](https://github.com/recommenders-team/recommenders)
- [Thompson sampling for online decision making](https://web.stanford.edu/~bvr/pubs/TS_Tutorial.pdf)
- [NIST AI RMF — user transparency for adaptive systems](https://www.nist.gov/itl/ai-risk-management-framework)
- [Bayesian Methods for Hackers — Beta distributions](https://github.com/CamDavidsonPilon/Probabilistic-Programming-and-Bayesian-Methods-for-Hackers)
