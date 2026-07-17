---
title: "Feature-Flag-Driven Releases"
slug: "ops-feature-flag-driven-releases"
description: "Ship code dark and release with feature flags: trunk-based delivery, flag lifecycle, kill switches, and integrating LaunchDarkly or open-source alternatives into CI/CD."
datePublished: "2026-01-09"
dateModified: "2026-07-17"
tags: ["DevOps", "Feature Flags", "CI/CD", "Release Engineering"]
keywords: "feature flag driven release, trunk based development, LaunchDarkly CI CD, feature toggle deployment, dark launch"
faq:
  - q: "What is a feature-flag-driven release?"
    a: "You merge completed code to main behind a disabled flag, deploy continuously, then enable the flag for progressively larger audiences when ready. The release decision (who sees the feature) separates from the deploy decision (what code is in production)."
  - q: "How is this different from A/B testing?"
    a: "Feature flags control rollout and kill switches for unfinished or risky features. A/B tests measure variant performance against a hypothesis. Same infrastructure often powers both, but the goals differ: safety vs experimentation."
  - q: "When should feature flags be removed?"
    a: "Within 30–90 days of full rollout. Permanent flags become technical debt — two code paths to test, stale conditionals, and flags nobody remembers. Schedule flag cleanup tickets alongside the launch ticket."
---

We stopped doing "release branches" the day checkout v2 sat in `release/2024-q3` for eleven weeks while prod ran divergent hotfixes. Feature-flag-driven releases didn't fix our merge conflicts overnight, but they let us merge to main daily and decide on Tuesday whether Brazil sees the new payment flow — without a deploy on Tuesday.

## Deploy vs release

| Term | Meaning |
|------|---------|
| Deploy | Code reaches production servers |
| Release | Users experience the change |

Traditional release branches conflate both. Feature flags decouple them: deploy always; release when ready.

```
main branch ──► CI ──► deploy to prod (flag OFF)
                              │
                         flag ON for 5% ──► metrics OK ──► 100%
                              │
                         flag OFF (kill switch) if error rate spikes
```

## Flag types and when to use each

**Release flags.** Short-lived. Gate incomplete features. Remove after full rollout.

**Ops kill switches.** Long-lived. Disable third-party integration, expensive code path, or non-critical feature during incident. Document in runbooks.

**Permission flags.** Entitlements, beta access, plan tiers. Long-lived by design.

**Experiment flags.** A/B variants. Tie to analytics; auto-expire when experiment concludes.

Mixing release and ops flags in the same boolean creates confusion. Namespace them: `release.checkout_v2`, `ops.external_search_enabled`.

## Implementation sketch

```typescript
// Server-side evaluation — never trust client-only flags for auth/billing
async function getCheckoutFlow(userId: string): Promise<'v1' | 'v2'> {
  const ctx = { key: userId, custom: { plan: await getPlan(userId) } };
  const enabled = await ldClient.variation('release-checkout-v2', ctx, false);
  return enabled ? 'v2' : 'v1';
}
```

Evaluate server-side for anything affecting money, data access, or security. Client-side flags are fine for UI experiments where tampering only affects that user's display.

Open-source options: Unleash (self-hosted), Flagsmith, Go Feature Flag. LaunchDarkly and Split if you want enterprise targeting and audit trails without running infra.

## CI/CD integration

Our pipeline:

1. Merge PR with flag default `false` in all environments
2. Deploy to prod automatically (flag off — dark launch)
3. Enable in staging via flag UI, run E2E
4. Progressive rollout in prod: internal → 1% → 10% → 100%
5. Create cleanup ticket to remove flag + dead code path

```yaml
# Optional: gate flag enablement on CI smoke pass
- name: Enable flag in staging
  run: |
    curl -X PATCH "$UNLEASH_URL/api/admin/projects/default/features/checkout-v2/environments/staging/on" \
      -H "Authorization: $UNLEASH_TOKEN"
```

Don't auto-enable in prod from CI without human approval unless your metric gates are solid (see Flagger-style analysis).

## Targeting rules that prevent surprises

- **Internal first.** `@acme.com` emails or `employee: true` attribute
- **Geographic canary.** Single region before global
- **Plan tier isolation.** Free tier before enterprise
- **Sticky bucketing.** Same user always gets same variant (hash userId + flag key)

Log flag evaluations at debug level during rollout. When support tickets spike, you need to know which flag state the user had.

## Flag lifecycle hygiene

Permanent flags rot. Our quarterly audit finds flags like `use_new_api_2023` still wrapping 400 lines.

Rules:
- Every flag has an owner and `expires:` date in code comment or flag description
- PR template asks: "Does this PR add a flag? Link cleanup ticket."
- After full rollout, delete flag and `if/else` in same PR if possible — don't leave `if (true)`

```typescript
// BAD: flag stuck at 100% for 8 months
if (flags.checkoutV2) { ... } else { ... }

// GOOD: after rollout, delete the branch entirely
```

## Failure modes

**Split-brain during rollout.** 5% on v2, 95% on v1, shared session state incompatible. Fix: session versioning or don't flag breaking backend changes without dual-write period.

**Flag service outage.** Decide default behavior: fail closed (feature off) vs fail open. Payment features fail closed; cosmetic UI can fail open.

**Client cache staleness.** Mobile apps cache flag state. Use short TTL or push config updates; server-side evaluation for critical paths.

## Testing with flags in CI

Run your test suite twice in CI when flags matter: once with flag off, once with flag on. Catch branches that break when the new path activates. Feature flag debt accumulates when only the default path is tested.

For LaunchDarkly and similar SDKs, use offline test fixtures or env-var overrides in CI rather than hitting the vendor API. Flaky CI from flag service rate limits wastes engineer trust.

Snapshot flag configuration per environment in Git (terraform or flags.yml) even if vendor UI is source of truth — drift between staging and prod flag targeting has caused "worked in staging" incidents more than once.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get feature flag driven releases wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of feature flag driven releases fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When feature flag driven releases misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Flag taxonomy and lifecycle

| Type | Lifetime | Example |
|------|----------|---------|
| Release | Days–weeks | New checkout UI |
| Ops kill-switch | Permanent | Payment provider toggle |
| Experiment | Weeks | Pricing A/B |
| Permission | Permanent | Enterprise tier feature |

Schedule flag removal in ticket system — stale flags create dead code paths and security holes (old auth flow still reachable).

## Backend vs frontend flag coordination

Ship backend changes dark (flag off) before enabling UI — frontend enabling first against old API causes 404 storms. Use **same flag key** across stack or explicit dependency graph in LaunchDarkly/Unleash.

## Audit and compliance

Regulated environments need flag change audit logs — who enabled `skip_fraud_check` in prod? Tie flag changes to approval workflow for kill-switches affecting money movement.

## Kill-switch drills

Quarterly game day: flip `payments_enabled` false in staging, measure time to detect and restore. Production kill-switch without practiced runbook panics teams into enabling wrong flag.

## Flag payload complexity

JSON flag values for routing percentages — validate schema in SDK; malformed flag should fail closed to safe default, not crash checkout initialization.

## Flag-driven schema compatibility

Release flag hides UI for new column — old code path must ignore unknown JSON fields from API. Forward-compatible protobuf/JSON schemas pair with flag rollouts.

## Percentage rollout correlation

LaunchDarkly percentage rollout is per-user stable — good. Random per-request percentage without sticky bucketing breaks canary analysis. Verify SDK sticky behavior.

## Resources

- [LaunchDarkly feature flag best practices](https://docs.launchdarkly.com/guides/flags/flag-best-practices)
- [Unleash documentation](https://docs.getunleash.io/)
- [Trunk Based Development](https://trunkbaseddevelopment.com/)
- [Martin Fowler on feature toggles](https://martinfowler.com/articles/feature-toggles.html)
- [OpenFeature specification](https://openfeature.dev/docs/reference/specification/)
