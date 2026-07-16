---
title: "The Android Privacy Sandbox for Developers"
slug: "android-privacy-sandbox"
description: "A developer's guide to the Android Privacy Sandbox: the SDK Runtime, Topics API, and attribution reporting, and what changes for privacy Android ads."
datePublished: "2026-01-21"
dateModified: "2026-01-21"
tags: ["Android", "Privacy", "Security"]
keywords: "Android Privacy Sandbox, SDK Runtime, Topics API, attribution reporting, privacy Android ads"
faq:
  - q: "What is the Android Privacy Sandbox?"
    a: "The Android Privacy Sandbox is a set of APIs from Google that let apps do advertising and measurement without the cross-app tracking that relied on the Advertising ID. It replaces device-wide identifiers with privacy-preserving building blocks: the SDK Runtime for isolating ad SDKs, the Topics API for coarse interest signals, and the Attribution Reporting API for conversion measurement without joining user identity."
  - q: "Does the Privacy Sandbox mean the Advertising ID is going away?"
    a: "Not immediately, but that's the direction. Google has kept the Advertising ID available while the Sandbox APIs mature, but the whole program exists to move the ecosystem off device-wide identifiers. If your monetization depends on the ad ID today, treat the Sandbox as the migration target and start measuring the gap now rather than after a deprecation deadline."
  - q: "Do I need to change my app if I don't run ads?"
    a: "Mostly no for the ad-serving APIs, but the SDK Runtime still matters if you bundle third-party SDKs that could be isolated in the future. And the privacy posture matters everywhere: the same discipline of not leaking cross-app identifiers applies to analytics, crash reporting, and attribution. Audit what your dependencies collect regardless of whether you sell ads."
---

For most of Android's history, ad targeting and measurement leaned on one thing: a device-wide Advertising ID that any app could read and any SDK could ship off-device to be joined against a profile somewhere. The Android Privacy Sandbox is Google's attempt to keep advertising economically viable while removing that shared identifier. It does this with three main pieces — the SDK Runtime, the Topics API, and the Attribution Reporting API — each designed so that useful signals survive but cross-app tracking of an individual does not.

I've spent enough time near ad SDKs to be cynical about "privacy-preserving advertising" as a phrase. But the Sandbox is worth understanding on its technical merits, because it changes where code runs, what data crosses process boundaries, and how you'll measure whether a campaign worked. If your app monetizes with ads, this is a migration you'll be doing whether you like the framing or not.

## The SDK Runtime: ad SDKs in their own sandbox

The most structurally interesting part is the **SDK Runtime**. Today a third-party ad SDK runs inside your app's process with your app's permissions. It can read your files, your memory, and — historically — the Advertising ID. The SDK Runtime moves participating SDKs out of your process into a separate, dedicated runtime with a much narrower set of permissions and no direct access to your app's data.

Practically, this means a "runtime-enabled SDK" is loaded by the platform, communicates with your app over a defined interface, and can't quietly exfiltrate whatever it finds in your process. For you as the app developer, the win is real: you stop being fully liable for what an opaque binary does inside your walls. The cost is that integration becomes an IPC-style contract rather than a `implementation("com.adnetwork:sdk")` line, and you depend on the SDK vendor shipping a runtime-enabled build.

My honest take: the SDK Runtime is the part of the Sandbox that would matter even if targeted ads vanished tomorrow, because process isolation of untrusted third-party code is just good engineering. It's the same instinct behind the privacy work I cover in [privacy engineering for mobile and GDPR](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/) — reduce the blast radius of code you don't control.

## The Topics API: interests without a profile

The **Topics API** replaces "read the ad ID, look up this user's profile" with a coarse, on-device inference. The platform observes which apps a user engages with, maps them to a taxonomy of human-readable topics (think "Fitness", "Cooking", "Travel"), and exposes a small number of recent topics to callers — with deliberate noise and limits.

The design choices are the whole point:

- Topics come from a **fixed, public, human-readable taxonomy**, not an opaque profile.
- Only a handful of topics per epoch (roughly weekly) are returned, and they age out.
- There's **injected noise** — a fraction of returned topics are random — so no single observation is trustworthy at the individual level.
- A caller only sees topics for apps the user also used *with that caller present*, which limits fishing.

```kotlin
val manager = TopicsManager.get(context)
val request = GetTopicsRequest.Builder()
    .setAdsSdkName("com.example.adsdk")
    .build()

manager.getTopics(request, executor, object : OutcomeReceiver<GetTopicsResponse, Exception> {
    override fun onResult(response: GetTopicsResponse) {
        response.topics.forEach { topic ->
            // topic.topicId maps to the public taxonomy; use it as a weak signal
            serveContextualPlusTopics(topic.topicId)
        }
    }
    override fun onError(error: Exception) {
        serveContextualOnly() // always have a no-topics fallback
    }
})
```

The engineering reality: Topics is a *weak* signal by construction. If your monetization model assumed a rich per-user profile, Topics won't reproduce it, and pretending otherwise leads to disappointment in the numbers. Treat it as a coarse contextual boost, and always have a topics-absent code path.

## Attribution Reporting: measurement without the join

Conversion measurement used to work by matching a click identifier to an install or purchase identifier — a join on user identity across two apps. The **Attribution Reporting API** breaks that join. It lets an ad tech register "sources" (an ad view/click) and "triggers" (a conversion), and the platform later emits reports that are either:

- **Event-level reports** — coarse, delayed, and noisy, tying a source to a small conversion signal, or
- **Aggregatable reports** — encrypted contributions that only become useful after being combined across many users in an aggregation service, never revealing one person's path.

The deliberate friction — delay, noise, limited bits of information — exists to prevent reconstructing an individual's cross-app journey. For engineers, the mental shift is from "I know user X clicked then converted" to "in aggregate, this campaign drove roughly this many conversions, ± noise." That's uncomfortable for teams used to deterministic attribution, and it's the single biggest cultural adjustment the Sandbox demands.

## What actually changes in your codebase

Concretely, plan for these:

| Area | Old world | Privacy Sandbox world |
| --- | --- | --- |
| Identifier | Device-wide Advertising ID | No shared ID; Topics + attribution |
| Ad SDK | Runs in your process | Isolated in the SDK Runtime |
| Targeting | Per-user profile lookup | Coarse Topics + contextual |
| Measurement | Deterministic click→convert join | Noisy event / aggregatable reports |
| Failure mode | ID unavailable = broken | Design for signal-absent by default |

The most important line in that table is the last one. Every Sandbox API can return nothing — no topics, a delayed report, an SDK that isn't runtime-enabled yet. Code that treats the privacy-preserving path as the exception and the identifier path as normal will be brittle. Invert it: assume you have coarse or absent signals, and treat any richer data as a bonus.

## A senior engineer's migration stance

If I were leading this migration, I'd sequence it like this. First, inventory every SDK that touches identity, ads, or attribution — you can't migrate what you haven't mapped. Second, stand up **contextual and first-party** signals independent of the Sandbox, because a robust first-party foundation makes you far less sensitive to how well Topics performs. Third, run the Sandbox APIs in parallel with existing measurement to quantify the gap honestly before any deadline forces your hand.

The teams that will struggle are the ones that treat this as a compliance checkbox two months before a deprecation. The teams that will do fine are the ones already investing in on-device processing and first-party data — the same shift I describe in [on-device AI for privacy](https://blog.michaelsam94.com/on-device-ai-for-privacy/), where keeping computation and identity on the device is the design default rather than an afterthought.

The Privacy Sandbox won't make advertising as precise as the ad-ID era, and Google isn't pretending otherwise. What it offers is a way to keep the ecosystem funded while making individual cross-app tracking structurally hard rather than merely discouraged. Build for the noisy, signal-absent case, isolate the third-party code you can't audit, and you'll come out of this migration with an app that's both compliant and, frankly, better engineered.

## Resources

- [Android Privacy Sandbox — developer documentation](https://developer.android.com/design-for-safety/privacy-sandbox)
- [SDK Runtime overview](https://developer.android.com/design-for-safety/privacy-sandbox/sdk-runtime)
- [Topics API documentation](https://developer.android.com/design-for-safety/privacy-sandbox/topics)
- [Attribution Reporting API](https://developer.android.com/design-for-safety/privacy-sandbox/attribution)
- [Privacy Sandbox on Android — program site](https://privacysandbox.com/android/)
