---
title: "A Non-Fatal Logging Strategy with Crashlytics"
slug: "android-crashlytics-nonfatal-strategy"
description: "Design a Crashlytics non-fatal logging strategy that surfaces real bugs: what to log as non-fatal, adding keys and breadcrumbs, and avoiding noise that hides signal."
datePublished: "2024-10-05"
dateModified: "2024-10-05"
tags: ["Android", "Crashlytics", "Observability", "Debugging"]
keywords: "Crashlytics non-fatal, recordException, custom keys Crashlytics, non-fatal logging strategy, Android error reporting, crashlytics breadcrumbs"
faq:
  - q: "What is a non-fatal in Crashlytics?"
    a: "A non-fatal is an exception you report to Crashlytics with recordException() that did not crash the app — you caught it and handled it, but you want visibility into how often it happens. Crashlytics groups non-fatals by stack trace like crashes, so you can track recurring handled errors such as failed network calls, parsing failures, or unexpected states. They're the tool for seeing bugs that degrade the experience without taking the app down."
  - q: "How do I add context to a Crashlytics report?"
    a: "Attach custom keys with setCustomKey for structured state (screen name, feature flag, user tier) and use log() to leave breadcrumb messages that appear in the report's timeline. Custom keys let you filter and segment issues; breadcrumbs reconstruct what happened before the error. Together they turn a bare stack trace into something you can actually diagnose."
  - q: "Can too many non-fatals be a problem?"
    a: "Yes. Logging every caught exception indiscriminately creates noise that buries the non-fatals that matter and can hit reporting limits. Be selective: record exceptions that represent real, actionable problems, and use custom keys to segment them rather than logging expected control-flow conditions. A focused non-fatal stream is far more useful than an exhaustive one."
---

Crashes get all the attention, but most of the bugs quietly degrading your app never crash it. A network call that silently fails and shows an empty screen. A parse error swallowed by a `try/catch` that leaves a feature broken. A "this should never happen" branch that happens 5,000 times a day. **Non-fatals** — exceptions you catch, handle, and *report* to Crashlytics — are how you make those visible. Used well, they're the highest-signal part of your observability. Used carelessly, they become a firehose of noise that hides the very problems they're meant to surface. The strategy is entirely about *selectivity and context*.

## What a non-fatal is, and why it beats a log line

`recordException()` sends a caught exception to Crashlytics, which groups it by stack trace exactly like a crash. That grouping is the value: instead of a `Log.e` that vanishes into logcat on one device, you get an aggregated, counted, trended issue across your whole install base. You learn that "image upload fails" happens to 3% of users on a specific OS version — something a local log could never tell you.

```kotlin
try {
    uploadAvatar(file)
} catch (e: IOException) {
    // handled: show retry UI, but I want visibility on the rate
    FirebaseCrashlytics.getInstance().recordException(e)
    showRetry()
}
```

The mental test for "should this be a non-fatal": *is this a handled error I'd want to know the rate and trend of?* If yes, record it. If it's expected control flow (user cancelled, cache miss), it's not a non-fatal — it's normal.

## The line between signal and noise

This is where most non-fatal strategies fail. Every caught exception is *tempting* to record, but recording everything is how you end up with 200 non-fatal issues and no idea which three matter. My rules:

- **Record actionable, unexpected errors.** Something is wrong and someone should look. Network failures beyond expected rates, deserialization failures, illegal states, failed writes.
- **Don't record expected conditions.** A 404 you handle by showing "not found," a user-cancelled operation, a validation the UI already communicates. These aren't bugs; logging them as non-fatals is noise.
- **Don't record what you can't act on.** If you'd never change code in response to seeing it, it doesn't belong in the crash reporter.
- **Deduplicate at the source.** An error firing in a tight loop or on every frame can flood your quota. Rate-limit or aggregate before recording.

The goal is a non-fatal stream where every issue is a question worth answering. When I inherit a project with a noisy Crashlytics, cutting the non-fatals *down* usually improves signal more than any dashboard change.

## Context is what makes a non-fatal useful

A bare stack trace tells you *where* but rarely *why*. Two mechanisms fix that.

**Custom keys** attach structured state that Crashlytics indexes, so you can filter and segment:

```kotlin
val crashlytics = FirebaseCrashlytics.getInstance()
crashlytics.setCustomKey("screen", "checkout")
crashlytics.setCustomKey("payment_method", method.name)
crashlytics.setCustomKey("cart_size", items.size)
crashlytics.setCustomKey("experiment_new_flow", isNewFlowEnabled)
```

Now when a checkout non-fatal comes in, you can see it only happens with a specific payment method, or only in the new-flow experiment. That's the difference between "checkout sometimes fails" and "checkout fails for PayPal users in the new flow" — one is a mystery, the other is a fix.

**Breadcrumbs** via `log()` reconstruct the sequence of events leading up to the error:

```kotlin
crashlytics.log("checkout: fetched cart (3 items)")
crashlytics.log("checkout: applied promo GOOD10")
crashlytics.log("checkout: submitting payment")
// ...exception recorded here shows all three breadcrumbs in its timeline
```

The breadcrumbs appear in the report's timeline, so you can see the path the user took. For an error that only reproduces under a specific navigation sequence, this is often the whole diagnosis.

## A layered strategy

Structure non-fatals in tiers so the important ones stay visible:

| Tier | What | How reported |
| --- | --- | --- |
| Critical handled errors | Failed payment, data loss risk, corrupt state | `recordException` + rich custom keys, alert on rate |
| Degraded experience | Failed loads, retries exhausted, feature unavailable | `recordException`, track trend per release |
| Diagnostic breadcrumbs | User actions, state transitions | `log()` only (no exception) |
| Expected conditions | Cancels, validations, cache misses | Not reported |

Set custom keys **proactively** as the user moves through the app (current screen, key flags), not just at the catch site — that way *every* report, including actual crashes, carries the context. This complements crash analysis and pairs naturally with the [ANR cluster analysis](https://blog.michaelsam94.com/android-anr-cluster-analysis-vitals/) workflow: crashes, ANRs, and non-fatals together give you the full picture of what's degrading the app.

## Wiring it into how you work

A non-fatal stream is only useful if someone acts on it:

- **Triage on a cadence.** New non-fatal issues should get looked at like new crashes — weekly at least. An unwatched stream rots into noise.
- **Watch per-release trends.** A non-fatal that spikes in a new version is a regression you introduced; catching it early beats a support ticket flood.
- **Set velocity alerts** on the critical tier so a sudden surge (a backend change breaking parsing, say) pages you instead of waiting for the next triage.
- **Close the loop.** When you fix one, confirm the rate drops in the shipping release — same discipline as crashes and ANRs.

The observability instinct here is identical whether you're on mobile or backend: structured context, selective signal, and trends per release. It's the mobile face of the same principles behind good [production observability](https://blog.michaelsam94.com/observability-metrics-logs-traces/).

## What I'd take away

Non-fatals are your window into the bugs that degrade the app without crashing it — but only if you're ruthless about signal. Record handled errors you'd actually act on, skip expected conditions and unactionable noise, and rate-limit anything that fires in a loop. Enrich every report with custom keys (screen, flags, user segment) set proactively and breadcrumbs that reconstruct the path to the error, so a stack trace becomes a diagnosis. Tier your reporting, triage on a cadence, alert on the critical tier, and verify fixes by watching rates drop per release. A lean, well-contextualized non-fatal stream will find more real bugs than any amount of exhaustive logging.

## Resources

- [Firebase Crashlytics — customize crash reports](https://firebase.google.com/docs/crashlytics/customize-crash-reports)
- [Record non-fatal exceptions](https://firebase.google.com/docs/crashlytics/get-deobfuscated-reports)
- [Crashlytics custom keys and logs](https://firebase.google.com/docs/crashlytics/customize-crash-reports?platform=android#add-keys)
- [Android Vitals overview](https://developer.android.com/topic/performance/vitals)
