---
title: "Server-Side Feature Flags"
slug: "backend-feature-flags-server-side"
description: "Ship features safely with server-side feature flags: evaluation points, targeting rules, kill switches, and avoiding the config-as-code mess that slows every deploy."
datePublished: "2024-10-12"
dateModified: "2024-10-12"
tags: ["Backend", "Architecture", "DevOps"]
keywords: "server-side feature flags, feature toggles, kill switch, progressive delivery, LaunchDarkly, Unleash, OpenFeature"
faq:
  - q: "Why put feature flags on the server instead of the client?"
    a: "Server-side evaluation means you can change behavior without shipping a new binary, and sensitive rules never leak to the client. Mobile and web clients can still cache a boolean for UX, but the source of truth for entitlements, pricing experiments, and kill switches belongs where you control auth and audit logs."
  - q: "What's the difference between a release flag and an experiment flag?"
    a: "A release flag is a temporary gate you remove once the feature is stable for everyone. An experiment flag stays longer, usually with percentage rollouts and metrics attached. Mixing them is how flags become permanent debt — name them by intent and set a removal date for release flags."
  - q: "How do I avoid flags becoming unmaintainable?"
    a: "Treat every flag as an inventory item: owner, creation date, expected removal, and default when the flag service is down. Delete release flags in the same sprint that completes the rollout. Cap the number of long-lived flags per service, and fail closed or open deliberately — never randomly."
---

Client-side toggles are fine for showing a button. They're the wrong tool when the decision gates billing, data access, or a migration that must stay consistent across every request. Server-side feature flags put evaluation next to your auth and business logic so you can ship dark, roll out by cohort, and kill a bad path in seconds without waiting for app store review.

I've used flags to migrate a payment path while half the traffic still hit the old ledger code. Without a server-evaluated switch, that would have been a binary deploy with a prayer. With one, it was a percentage dial and a dashboard.

## Where evaluation belongs

Evaluate as close to the decision as you can, once per request (or once per session for sticky experiments), and pass the result down as an explicit boolean or enum — don't re-query the flag service in every helper.

```typescript
type FlagContext = {
  userId: string;
  tenantId: string;
  plan: "free" | "pro" | "enterprise";
  country: string;
};

async function resolveFlags(ctx: FlagContext): Promise<ResolvedFlags> {
  return flagClient.evaluateAll({
    targetingKey: ctx.userId,
    attributes: {
      tenantId: ctx.tenantId,
      plan: ctx.plan,
      country: ctx.country,
    },
  });
}

// In the handler — one evaluation, then branch
const flags = await resolveFlags(ctx);
if (flags.newCheckout) {
  return handleCheckoutV2(req);
}
return handleCheckoutV1(req);
```

Sticky targeting matters for experiments: the same user should not flip between variants mid-session because a percentage bucket reshuffled. Most vendors hash `targetingKey + flagKey` for that reason — use a stable identity, not a rotating session id, unless you intentionally want session-scoped tests.

## Targeting rules that stay sane

Start with three rule types and resist inventing more:

1. **Internal / employee** — dogfood before anyone else
2. **Allowlist / tenant** — enterprise pilots and beta cohorts
3. **Percentage rollout** — progressive delivery with a kill switch

Complex boolean trees ("pro users in DE except tenant X on Tuesdays") belong in a few well-named flags, not one mega-expression. When product asks for nested conditions, prefer composing two flags in code over a DSL nobody can debug at 2am.

```yaml
# Conceptual flag config — keep rules short
new-search:
  default: false
  rules:
    - if: plan in [pro, enterprise] AND country == "US"
      variation: true
    - rollout: 10%  # of remaining traffic
      variation: true
```

## Kill switches and fail modes

A flag is only a kill switch if your service still works when the flag service is down. Decide fail-open vs fail-closed per flag:

| Flag type | Prefer | Why |
|---|---|---|
| New risky path | Fail closed (old path) | Outage of flag service shouldn't enable the new code |
| Emergency disable of a feature | Fail closed (feature off) | Safer to hide than to keep serving a broken path |
| Entitlement / paid feature | Fail closed (deny) | Don't accidentally grant access |
| Cosmetic UI experiment | Fail open or cached last value | UX blip beats hard error |

Cache evaluations with a short TTL and a stale-if-error policy. Cold-starting every request against a remote SDK is how flag latency becomes your p99.

## OpenFeature and vendor lock-in

If you're early, pick one vendor or an open-source server (Unleash, Flagsmith, GrowthBook) and wrap it behind a thin interface. [OpenFeature](https://openfeature.dev/) is the portable API shape worth targeting so you're not rewriting every `if` when procurement changes tools.

```typescript
// Thin wrapper — swap provider without touching call sites
export async function boolFlag(
  key: string,
  ctx: FlagContext,
  defaultValue: boolean
): Promise<boolean> {
  try {
    return await client.getBooleanValue(key, defaultValue, toEvalCtx(ctx));
  } catch {
    return defaultValue; // explicit fallback
  }
}
```

## Lifecycle: the part teams skip

Flags that never die become a second, poorly typed codebase. Practical process:

- Prefix release flags with `tmp_` or `release_` and require a ticket link + removal date in the PR that adds them
- Run a weekly "flag debt" query: flags older than 30 days with 100% or 0% traffic
- When a flag hits 100% for a week, delete the old branch and the flag in one PR — don't "leave it just in case"

Server-side flags are progressive delivery infrastructure, not a permanent configuration language. Use them to decouple deploy from release, keep evaluation next to the decision, and delete them like you delete feature branches.

## Flag types and when to use each

Martin Fowler's taxonomy maps to practical decisions:

| Type | Lifespan | Example | Removal trigger |
|---|---|---|---|
| Release | Days–weeks | `release_new_checkout` | 100% rollout stable 1 week |
| Experiment | Weeks–months | `exp_search_algorithm_b` | Statistical significance reached |
| Ops | Permanent (rare) | `ops_maintenance_mode` | Never — but review quarterly |
| Permission | Permanent | `perm_beta_features` | Tied to plan/role system |
| Kill switch | Permanent | `kill_external_api_calls` | Never — emergency use only |

Release flags must have a ticket and removal date. Experiment flags need an owner and success metric. Ops and kill switches are the only acceptable permanent flags — and even those should be ≤5 per service.

## Percentage rollout mechanics

Hash-based bucketing ensures sticky assignment:

```
bucket = hash(userId + flagKey) % 100
if bucket < rolloutPercentage → enabled
```

Critical properties:
- Same user always gets same variant (unless you change the rollout percentage significantly)
- Increasing rollout from 10% to 20% adds new users; existing enabled users stay enabled
- Decreasing rollout may disable users who were previously enabled — communicate this for experiments

For infrastructure changes (database migration), use tenant-level flags instead of percentage — migrate tenant-by-tenant, not user-by-user.

## Auditing and compliance

Server-side flags affect who sees what — audit trail matters:

```typescript
async function evaluateWithAudit(key: string, ctx: FlagContext): Promise<boolean> {
  const result = await boolFlag(key, ctx, false);
  if (key.startsWith('perm_') || key.startsWith('kill_')) {
    auditLog.record({
      flag: key,
      userId: ctx.userId,
      tenantId: ctx.tenantId,
      result,
      timestamp: new Date(),
    });
  }
  return result;
}
```

Log flag evaluations for permission and kill-switch flags. Required for SOC2 and enterprise customers who ask "why did user X see feature Y?"

## Testing with flags

Flags make testing harder if not managed:

```typescript
// Test both paths explicitly
describe('checkout', () => {
  it('v1 path', async () => {
    await withFlag('new_checkout', false, () => {
      expect(processCheckout(order)).toMatchSnapshot('v1');
    });
  });

  it('v2 path', async () => {
    await withFlag('new_checkout', true, () => {
      expect(processCheckout(order)).toMatchSnapshot('v2');
    });
  });
});
```

CI should run tests with both flag states. When removing a flag, delete the old path's tests in the same PR.

## Anti-patterns I've cleaned up

- **50+ flags per service** — nobody knows what half of them do; quarterly audit mandatory
- **Flags in database queries** — `if (flag) query += ' AND new_column IS NOT NULL'` creates untestable SQL; branch at service level
- **Client-side flag as source of truth for billing** — client shows feature, server doesn't enforce; always evaluate server-side for money/access
- **No default when flag service down** — undefined behavior; explicit default per flag
- **Flag per customer request** — becomes undebuggable config soup; use tenant allowlist rule instead

## Failure modes

- **Flag service latency dominates p99** — cache evaluations; evaluate once per request
- **Stale cache serves wrong variant** — tune TTL vs freshness for experiments
- **Removing flag without removing old code path** — dead code accumulates; delete both
- **Non-sticky percentage rollout** — users flip variants mid-session; use stable targeting key
- **Fail-open on paid features** — grants access during outage; fail-closed for entitlements

## Production checklist

- One evaluation per request; result passed explicitly to handlers
- Fail-open/closed documented per flag with explicit default
- Cached evaluations with stale-if-error policy
- Release flags have ticket link and removal date in PR
- Weekly flag debt review (flags older than 30 days at 0% or 100%)
- CI tests both flag states for release flags
- Audit logging for permission and kill-switch flags
- OpenFeature or thin wrapper to avoid vendor lock-in

## Resources

- [OpenFeature specification](https://openfeature.dev/docs/reference/intro)
- [Martin Fowler — Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)
- [Unleash documentation](https://docs.getunleash.io/)
- [LaunchDarkly — flag best practices](https://docs.launchdarkly.com/guides/flags)
---
