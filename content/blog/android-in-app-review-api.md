---
title: "In-App Review API Done Right"
slug: "android-in-app-review-api"
description: "Use the Android In-App Review API without hurting your rating: when to request the flow, why you can't control if it shows, and how to time prompts around real moments."
datePublished: "2024-06-29"
dateModified: "2024-06-29"
tags: ["Android", "Play Store", "UX", "Ratings"]
keywords: "in-app review API, ReviewManager, requestReviewFlow, launchReviewFlow, Play ratings, review prompt timing, quota"
faq:
  - q: "Can I control whether the in-app review dialog actually appears?"
    a: "No. You request the flow and launch it, but Google Play decides whether to actually show the card based on its own quotas and whether the user has already reviewed recently. Your code should treat launchReviewFlow completing as 'the request finished', not as 'the user saw and used a review card'. Never gate app behavior on whether a review happened."
  - q: "When is the best time to request an in-app review?"
    a: "Right after the user completes something satisfying — finishing a level, completing an order, achieving a goal — when they feel positive about the app. Never during onboarding, never after an error or a crash, and never interrupting an active task. The moment you choose is the single biggest factor in whether the prompt helps or hurts your rating."
  - q: "Why shouldn't I show a custom rating prompt before the in-app review?"
    a: "Pre-prompting to filter out unhappy users toward a feedback form and happy users toward the store — 'review gating' — violates Play policy and can get your app removed. The In-App Review API is designed to be shown to everyone at a good moment; interfering with it or funneling ratings is against the rules and undermines the honesty of the store."
---

The In-App Review API lets a user rate and review your app on a small card *inside* your app, without a context switch to the Play Store listing — and the single most important thing to understand about it is that **you don't control whether the card actually shows**. You request a flow and launch it; Google Play decides, based on quotas and whether the user has reviewed recently, whether to display anything at all. Teams that misunderstand this build brittle logic around a dialog that may silently no-op, or worse, try to game which users get prompted and violate Play policy. Done right, it's a quiet, well-timed nudge that lifts your rating; done wrong, it's a policy violation or an annoyance.

## The two-step flow

The API is intentionally minimal. You pre-warm a review object, then launch it:

```kotlin
val manager = ReviewManagerFactory.create(context)

// 1. Request the flow — do this ahead of the moment you'll show it.
manager.requestReviewFlow().addOnCompleteListener { request ->
    if (request.isSuccessful) {
        val reviewInfo = request.result
        // 2. Launch at the right moment. May or may not display a card.
        manager.launchReviewFlow(activity, reviewInfo)
            .addOnCompleteListener {
                // The flow finished. You do NOT know if a card was shown
                // or what the user did. Just continue your app normally.
                continueAfterTask()
            }
    }
}
```

`requestReviewFlow()` does a network round-trip, so call it a little *before* the moment you intend to prompt — not at the exact instant, or you'll add latency to the user's experience. Then `launchReviewFlow` at the good moment.

## Accept that the API is a black box by design

The completion listener fires whether or not a card appeared, and it carries no information about the user's action — no rating, no "they reviewed," nothing. This is deliberate: Play doesn't want apps to reward or punish users based on reviewing, because that corrupts the honesty of ratings. So your rules:

- **Never gate features, rewards, or navigation** on the review flow. It's fire-and-continue.
- **Never assume it displayed.** If the user reviewed recently or you've hit the quota, it silently does nothing.
- **Don't call it in a loop hoping to force it.** The quota is per-user and per-time-window; hammering it just wastes network calls and shows nothing.

Treat `launchReviewFlow`'s completion as "okay, move on with whatever the user was doing."

## Timing is the entire game

Because you can't control display, the *only* lever you have that matters is *when* you request. And timing is genuinely decisive. Prompt someone right after a moment of satisfaction and Play's quota is more likely to be spent on a user inclined to rate well. Prompt at a bad moment and you either annoy them or waste the impression.

Good moments:

- Just after completing a purchase or checkout.
- After finishing a level, a workout, a lesson — any goal.
- After a streak of successful, friction-free sessions.

Bad moments — never do these:

- **During onboarding.** They haven't experienced the app.
- **Right after an error, crash, or failed action.** You're asking for a rating at peak frustration.
- **Interrupting an active task.** Mid-edit, mid-game, mid-form.
- **On every launch or aggressively often.** The quota makes this pointless anyway, and if you wrap it in your own dialog, it's nagging.

The judgment here mirrors [in-app update prompts](https://blog.michaelsam94.com/android-in-app-updates-api/): both are Play surfaces where the API is easy and the *timing policy* is the hard, high-value part.

## The one thing that can get your app removed: review gating

There's a tempting pattern: show your *own* "Are you enjoying the app?" dialog first, send the people who tap "No" to a support form, and only launch the Play review flow for the people who tap "Yes." This is **review gating**, and it violates Play's policy. It manufactures artificially high ratings by filtering out dissatisfied users, and Google can and does remove apps for it. Don't do it. The In-App Review card is meant to be offered to everyone at a good moment, unfiltered. If you want to catch unhappy users, give them an *always-available* feedback path elsewhere in the app — a settings entry, a support link — not a fork in front of the rating prompt.

## Testing it

Because Play controls display, in normal testing the card often won't appear — which is expected and not a bug. To verify integration:

- Use **internal app sharing** to test with a real Play-signed build.
- Use the documented testing setup so the flow displays for test accounts.
- Confirm your code path *completes cleanly whether or not the card shows*, since production will frequently no-op.

A common false alarm is "the review dialog never shows in testing" — that's usually the quota or account state, not broken code. Verify the flow completes and your app continues correctly; that's what you actually ship.

## The mindset that gets results

The best in-app review implementation is almost invisible: a single well-placed `launchReviewFlow` after a genuinely satisfying moment, no custom pre-prompt, no gating, no assumptions about what happened. You're handing Play a good moment and letting it decide. The teams that obsess over the API surface are optimizing the wrong thing; the teams that obsess over *identifying the user's best moment* — and respecting the policy — are the ones whose ratings actually climb. Pick your moment, fire and forget, and never try to outsmart the quota.

## Resources

- [Request in-app reviews (Android)](https://developer.android.com/guide/playcore/in-app-review)
- [Integrate in-app reviews (Kotlin/Java)](https://developer.android.com/guide/playcore/in-app-review/kotlin-java)
- [Test the in-app review flow](https://developer.android.com/guide/playcore/in-app-review/test)
- [Play ratings and reviews policy](https://support.google.com/googleplay/android-developer/answer/9898684)
- [Play Core library overview](https://developer.android.com/guide/playcore)
