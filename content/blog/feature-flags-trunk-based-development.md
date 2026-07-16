---
title: "Feature Flags and Trunk-Based Development"
slug: "feature-flags-trunk-based-development"
description: "How feature flags and trunk-based development let teams ship to main daily with progressive rollout, canary releases, and safe kill switches — without long-lived branches."
datePublished: "2026-05-30"
dateModified: "2026-05-30"
tags: ["Continuous Delivery", "Feature Flags", "DevOps", "Backend"]
keywords: "feature flags, trunk-based development, feature toggles, continuous delivery, progressive rollout, canary release, kill switch"
faq:
  - q: "Do feature flags replace feature branches?"
    a: "They replace long-lived feature branches. You still branch for a few hours, but unfinished work merges to main behind a flag that keeps it dark in production. The flag, not the branch, becomes the boundary between 'merged' and 'released'."
  - q: "How do I stop feature flags from becoming permanent tech debt?"
    a: "Treat release flags as short-lived and give each one an owner and an expiry. Add the flag to your backlog the moment you create it, and delete both the flag and its dead code path within a sprint or two of full rollout."
  - q: "Can small teams benefit from trunk-based development?"
    a: "Yes, and often more than large ones. A two- or three-person team avoids merge hell almost for free, and a lightweight flag library plus a config file is enough to get progressive rollout without buying a platform."
---

The first time I watched a release get stuck for three weeks because two long-lived branches had drifted too far apart to merge cleanly, I decided branches were the problem, not the solution. Feature flags and trunk-based development are how you stop that from happening: everyone commits to `main` at least daily, and unfinished work ships to production hidden behind a toggle instead of quarantined on a branch that rots.

The core idea is a separation most teams conflate. **Deploy** means the code is running in production. **Release** means users can see it. Feature flags decouple the two, so you can deploy an unfinished feature a dozen times a day and flip it on for real users only when it's ready — or for 1% of them first.

## Why long-lived branches fail

A branch that lives for two weeks is a bet that the rest of the codebase won't change underneath it. That bet almost always loses. The longer a branch survives, the larger the eventual merge, and large merges are where subtle regressions hide — the conflict resolves cleanly in git but the semantics are wrong.

Trunk-based development inverts the default. You branch, but only for hours, and you merge back to `main` while the diff is still small enough to review in one sitting. Integration happens continuously, so conflicts surface as one-line annoyances instead of week-long archaeology projects. The catch is obvious: if `main` must always be releasable, how do you merge a half-built feature? That's the job the flag does.

## The flag as a boundary

A feature flag is a runtime conditional whose value comes from configuration, not code. In its simplest form it's a boolean:

```kotlin
if (flags.isEnabled("checkout_v2", user)) {
    renderNewCheckout()
} else {
    renderLegacyCheckout()
}
```

The new checkout can merge to `main` while it's still missing half its edge cases, because `checkout_v2` defaults to `false` everywhere. Your CI pipeline builds and deploys it; production users never see it. When the feature is done, you flip the default — and if it misbehaves, you flip it back in seconds without a rollback deploy.

That last property is why I care about flags more than any other CD technique. A kill switch is a config change that propagates in seconds; a rollback is a full redeploy that takes minutes and re-runs your whole pipeline. When something is on fire at 2 a.m., seconds matter.

## Kinds of flags, and why the distinction matters

Not every flag is the same, and treating them identically is how you end up with 400 toggles nobody understands. I keep four categories in my head:

| Type | Lifetime | Purpose | Owner |
|---|---|---|---|
| Release | days–weeks | hide in-progress work | the developer |
| Experiment | weeks | A/B tests, measure impact | product/data |
| Ops | long | kill switches, load shedding | platform/SRE |
| Permission | permanent | entitlements, plan tiers | product |

The dangerous confusion is treating a **release** flag as if it's permanent. Release flags are temporary scaffolding. Every one you create is a small debt, and the interest is a combinatorial explosion of untested code paths: ten independent boolean flags is 1,024 possible states, and you are not testing all of them.

## Progressive rollout and canary

Once a feature is behind a flag, the on/off switch becomes a dial. Instead of flipping `checkout_v2` to `true` for everyone, you target a widening ring: internal staff, then 1% of users, then 5%, 25%, 100% — watching error rates and latency at each step. This is a canary release driven by configuration rather than by routing traffic between two deployments.

```yaml
flags:
  checkout_v2:
    default: false
    rules:
      - segment: internal_staff
        value: true
      - percentage: 5        # sticky bucketing by hashed user id
        value: true
```

Two details make percentage rollouts trustworthy. First, bucketing must be **sticky**: hash the user id so the same person stays in the same bucket across requests, otherwise a user flickers between old and new UI on every reload. Second, you need a metric to watch. Rolling out to 5% is only useful if you're comparing that cohort's error rate against the other 95% and can halt automatically when it diverges. Pair this with solid [SLOs and error budgets](https://blog.michaelsam94.com/designing-for-observability-slos/) so the rollout gate has something concrete to check against.

## Testing when main is always shippable

The rule "`main` is always releasable" only holds if your pipeline enforces it. Trunk-based development leans hard on fast, reliable automated tests — every commit runs them, and a red build blocks everyone, so it gets fixed immediately. This is where a healthy [test strategy](https://blog.michaelsam94.com/testing-pyramid-vs-trophy/) pays off: the suite has to be quick enough that developers run it before pushing, or they'll stop merging frequently and drift back to branches.

For flagged code, test the paths that will actually run in production. At minimum that means the flag-on and flag-off states of anything currently rolling out. I've been burned by a flag whose "on" path passed every test while its "off" path — the one 99% of users saw — had quietly broken, because nobody wrote a test for the branch they assumed was untouched.

## Keeping flag debt under control

The failure mode of every flagging system I've seen is accumulation. Flags outlive their features, nobody remembers what `enable_new_thing_v3` gates, and eventually someone deletes the wrong one during a cleanup and takes down checkout.

A few habits keep it manageable. Give every release flag an owner and an expiry date at creation time, and have a job that flags stale toggles in a channel where humans see them. When a feature hits 100% and stays there for a sprint, the follow-up is not optional: delete the flag *and* the dead code path it guarded. I treat leftover flags as part of [ongoing technical-debt work](https://blog.michaelsam94.com/managing-technical-debt/) rather than a separate chore, because that's exactly what they are — scaffolding you forgot to take down.

## Where it fits

Trunk-based development with feature flags is the substrate under most mature continuous delivery. It's what lets a team deploy dozens of times a day without ceremony, roll features out to a fraction of users, and turn a bad launch off with a config change instead of a fire drill. The discipline it demands — tiny merges, fast tests, and ruthless flag cleanup — is real, but it's cheaper than the branch-integration tax it replaces. If you're wiring this into a delivery pipeline, [my portfolio](https://michaelsam94.com/) has more on the systems side of shipping mobile and backend software safely.

## Resources

- [Trunk-Based Development](https://trunkbaseddevelopment.com/)
- [Martin Fowler — Feature Toggles (Flags)](https://martinfowler.com/articles/feature-toggles.html)
- [Martin Fowler — Continuous Integration](https://martinfowler.com/articles/continuousIntegration.html)
- [Google — DORA / DevOps capabilities: Trunk-based development](https://dora.dev/capabilities/trunk-based-development/)
- [OpenFeature — Feature flagging standard](https://openfeature.dev/)
- [Google SRE Book — Canarying Releases](https://sre.google/workbook/canarying-releases/)
