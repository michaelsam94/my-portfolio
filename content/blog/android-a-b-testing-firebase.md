---
title: "A/B Testing Mobile Features"
slug: "android-a-b-testing-firebase"
description: "Run A/B tests on Android features with Firebase Remote Config and A/B Testing: experiment design, statistical rigor, feature flags, and avoiding common mobile pitfalls."
datePublished: "2026-07-09"
dateModified: "2026-07-09"
tags: ["Android", "Firebase", "Feature Flags", "Analytics"]
keywords: "Android A/B testing, Firebase A/B testing, mobile feature experiments, Remote Config experiments, mobile growth testing"
faq:
  - q: "How do you A/B test features on Android?"
    a: "Use Firebase Remote Config with A/B Testing to assign users to variants, serve different feature configurations, and measure impact on key metrics via Firebase Analytics or Google Analytics 4. The SDK handles randomization, persistence, and exposure tracking. Define one primary metric and guardrail metrics before launching."
  - q: "What makes mobile A/B testing different from web?"
    a: "Mobile users update apps slowly — you can't change UI instantly for everyone. Experiments run against installed app versions, so you must handle stale clients gracefully. Network conditions affect exposure timing, and app store review cycles delay when new variants can ship. Remote Config solves the runtime half; version gating solves the client half."
  - q: "How long should a mobile A/B test run?"
    a: "Run until you reach statistical significance on your primary metric — typically 1–2 weeks for apps with daily active users in the tens of thousands. Account for day-of-week effects by running at least 7 full days. Don't peek and stop early when results look good; that inflates false positive rate."
---

A/B testing on mobile isn't "show half the users a blue button." It's an experiment infrastructure problem: how do you assign variants reliably across app restarts, measure the right metrics without survivorship bias, and ship the winner without waiting for an app store release? Firebase Remote Config with A/B Testing handles the assignment and measurement layer, but the experiment design — what you test, what you measure, when you call it — is where teams get wrong answers confidently. I've run dozens of mobile experiments; the ones that changed product decisions had clear hypotheses and pre-registered metrics, not just "let's see what happens."

## Architecture

```
Firebase Console → Remote Config template → A/B experiment
        ↓                                        ↓
   App SDK fetches config              Analytics events → GA4
        ↓                                        ↓
   App renders variant A or B           Statistical analysis in console
```

The app doesn't implement randomization — Firebase assigns users to variants and persists the assignment. Your code reads a config value and renders accordingly.

## Setting up an experiment

Define the Remote Config parameter first:

```kotlin
// Remote Config parameter: checkout_layout
// Default: "control"
// Variant A: "single_page"
// Variant B: "multi_step"

val remoteConfig = Firebase.remoteConfig
remoteConfig.setDefaultsAsync(mapOf("checkout_layout" to "control"))

await remoteConfig.fetchAndActivate()

when (remoteConfig.getString("checkout_layout")) {
    "single_page" -> SinglePageCheckout()
    "multi_step" -> MultiStepCheckout()
    else -> ControlCheckout()
}
```

In Firebase Console, create an A/B test linked to this parameter. Define:
- **Target audience**: e.g., 20% of users on app version ≥ 3.2
- **Variants**: control (50%), single_page (25%), multi_step (25%)
- **Primary metric**: `purchase_completed` conversion rate
- **Guardrail metrics**: `app_crash`, `checkout_abandoned`, `session_duration`

## Experiment design principles

**One change per experiment.** Testing a new checkout layout AND a new payment method simultaneously means you can't attribute results. Run sequential experiments or use factorial design only if you have the traffic to power it.

**Pre-register your metrics.** Decide the primary metric before launch. If you launch with "conversion rate" as primary and switch to "revenue per user" when conversion looks flat, your result is meaningless.

**Minimum detectable effect.** Calculate the sample size you need before starting. Firebase's experiment calculator helps, but the rule of thumb: if you need to detect a 2% relative change in a 5% conversion rate, you need roughly 40K users per variant.

**Guardrail metrics protect you.** A variant that increases conversion but doubles crash rate is a net loss. Set guardrails before launch and auto-stop if they breach thresholds.

## Mobile-specific pitfalls

**Stale app versions.** Users on v2.0 can't see your v3.2 experiment UI. Target experiments by app version:

```kotlin
remoteConfig.setCustomSignals(mapOf("app_version" to BuildConfig.VERSION_NAME))
```

In Console, add an audience condition: `app_version >= 3.2.0`.

**Exposure before activation.** `fetchAndActivate()` is async. Log exposure only after activation, not at app start before config arrives:

```kotlin
await remoteConfig.fetchAndActivate()
val variant = remoteConfig.getString("checkout_layout")
if (variant != "control") {
    analytics.logEvent("experiment_exposure") {
        param("experiment_id", "checkout_layout_test")
        param("variant", variant)
    }
}
renderCheckout(variant)
```

**Network dependency.** Cache the last activated config so offline users stay in their assigned variant:

```kotlin
remoteConfig.setConfigSettingsAsync(
    remoteConfigSettings {
        minimumFetchIntervalInSeconds = 3600  // 1 hour in production
    }
)
```

Default fetch interval in production should be hours, not seconds — Remote Config isn't a real-time feature flag service.

## Feature flags vs A/B tests

Use [feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) for operational control (kill switches, gradual rollouts). Use A/B tests for learning (which variant is better?). They share Remote Config infrastructure but serve different purposes:

| Purpose | Feature flag | A/B test |
|---------|-------------|----------|
| Goal | Safe rollout | Measure impact |
| Audience | Everyone (eventually) | Random sample |
| Duration | Permanent | Time-bounded |
| Analysis | Monitor errors | Statistical comparison |

Don't run an A/B test when you just need a kill switch. Don't ship a feature flag change as an experiment without measurement.

## Analyzing results

Firebase A/B Testing integrates with GA4 for analysis. In the console:

- Wait for "Statistical significance reached" badge
- Check primary metric lift and confidence interval
- Verify guardrail metrics didn't degrade
- Segment by platform, country, app version for hidden effects

If the result is significant but the lift is 0.3% on a metric that doesn't move business outcomes, it's statistically significant but practically irrelevant. Pre-define what "winning" means in business terms.

## After the experiment

1. **Ship the winner** — update the Remote Config default value
2. **Remove experiment code paths** in the next app release (don't accumulate variant branches)
3. **Document the result** — what you tested, what you learned, what you'd test next
4. **Clean up Remote Config** — archive the experiment, remove unused parameters

## Common production mistakes

Teams get a b testing firebase wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping a b testing firebase on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When a b testing firebase misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Experiment interference

Overlapping Remote Config experiments on same key collide — namespace keys per experiment (`checkout_v2_enabled`). Holdout groups need sticky assignment via Firebase Analytics user properties, not random per fetch.

## Instant rollback

Remote Config `minimumFetchIntervalInSeconds` production should be 3600+ but keep emergency zero interval channel for incident kill switch operator role only.

## A B Testing Firebase Supplement 0 on Samsung and Pixel divergence

Exercise a b testing firebase supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching a; regressions above 8% block release for `android-a-b-testing-firebase-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "A B Testing Firebase Supplement 0" should map to a single runbook section with known workarounds.

## Firebase regression gates for Play Vitals

Before promoting `android-a-b-testing-firebase-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Firebase A/B Testing documentation](https://firebase.google.com/docs/ab-testing)
- [Firebase Remote Config guide](https://firebase.google.com/docs/remote-config)
- [Google Analytics 4 event reference](https://developers.google.com/analytics/devguides/collection/ga4/reference/events)
- [Firebase Remote Config strategies](https://blog.michaelsam94.com/android-firebase-remote-config-strategies/)
- [Feature flags and trunk-based development](https://blog.michaelsam94.com/feature-flags-trunk-based-development/)
