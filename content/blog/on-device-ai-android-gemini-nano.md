---
title: "Adding On-Device AI to an Android App with Gemini Nano"
slug: "on-device-ai-android-gemini-nano"
description: "A practical guide to on-device AI on Android with Gemini Nano, AICore, and ML Kit GenAI APIs — summarization, rewriting, and image description that run fully offline."
datePublished: "2026-02-10"
dateModified: "2026-07-17"
tags: ["Android", "Gemini Nano", "On-Device AI", "ML Kit"]
keywords: "Gemini Nano, on-device AI Android, ML Kit GenAI, Android AI, AICore, on-device inference"
faq:
  - q: "What is Gemini Nano and where does it run?"
    a: "Gemini Nano is Google's smallest Gemini model, designed to run on-device through the AICore system service on supported Android phones. Inference happens locally, so data never leaves the device and features work offline."
  - q: "Which Android devices support Gemini Nano?"
    a: "Gemini Nano runs on a limited set of higher-end devices with the required NPU and AICore support — Pixel 9 series, recent Samsung Galaxy S flagships, and a growing list. Always check availability at runtime and provide a fallback for unsupported devices."
  - q: "Should I use Gemini Nano or a cloud model?"
    a: "Use Gemini Nano when privacy, offline support, and zero per-request cost matter and the task is well-scoped (summarize, rewrite, proofread, describe). Use a cloud model for complex reasoning, long context, or when consistent quality across all devices is required."
---

On-device AI finally crossed the line from demo to shippable on Android. With Gemini Nano running through AICore, you can summarize a chat thread, rewrite a message in a different tone, proofread text, or describe an image — all without a network call, without a per-request bill, and without user data leaving the phone. For a class of features that used to require a cloud round-trip, that's a meaningful shift.

The catch, and the thing most tutorials gloss over, is that on-device AI on Android is a *conditional* capability. It exists on a subset of devices, the model is small and task-specific, and you must design for graceful absence. Here's how to add Gemini Nano features properly, what the APIs actually give you, and where the sharp edges are.

## The pieces: AICore, Gemini Nano, and ML Kit GenAI

Three layers matter:

- **AICore** is a system service (updated via Google Play system updates) that manages the on-device foundation model — downloading it, running inference on the NPU, and isolating it from apps. Your app never ships the model; AICore owns it.
- **Gemini Nano** is the model AICore runs. It's small by design, tuned for on-device latency and power, not for open-ended reasoning.
- **ML Kit GenAI APIs** are the high-level, stable entry point for most apps. Rather than prompting the raw model, you call purpose-built APIs: **Summarization**, **Rewriting**, **Proofreading**, and **Image Description**. These wrap Gemini Nano with task-specific tuning and are the path I'd recommend for production.

For lower-level, prompt-based access there's the experimental generative APIs, but the ML Kit GenAI feature APIs are where reliability lives today.

## Always check availability first

The single most important habit: never assume the feature exists. Device support is narrow (Pixel 9 family, recent Galaxy S flagships, and expanding), and even on a supported device the model may still need to download. Check status and drive UI from it.

```kotlin
val summarizer = Summarization.getClient(
    SummarizerOptions.builder(context)
        .setInputType(InputType.ARTICLE)
        .setOutputType(OutputType.THREE_BULLETS)
        .setLanguage(Language.ENGLISH)
        .build()
)

when (summarizer.checkFeatureStatus().await()) {
    FeatureStatus.AVAILABLE -> runSummary(summarizer)
    FeatureStatus.DOWNLOADABLE -> {
        // trigger download, show progress, then run
        summarizer.downloadFeature(downloadCallback)
    }
    FeatureStatus.DOWNLOADING -> showDownloadingState()
    FeatureStatus.UNAVAILABLE -> useCloudFallbackOrHideFeature()
}
```

`UNAVAILABLE` is not an edge case — it's the majority of the installed base right now. Decide up front whether the feature degrades to a cloud call or simply hides, and make that decision per feature.

## Running a summarization

Once available, the API is stream-friendly, which matters for perceived latency because even on-device generation isn't instant:

```kotlin
val request = SummarizationRequest.builder(longText).build()

summarizer.runInference(request) { result ->
    // streamed chunks; append to UI as they arrive
    appendToUi(result.summary)
}
```

On a Pixel 9 I've seen short summaries complete in a couple of seconds with the model already resident. The first run after a cold start is slower because AICore loads the model into memory; subsequent runs are quick. Stream the output so the user sees progress rather than a spinner.

## What the model is good at (and not)

Gemini Nano is a small model. Calibrate expectations accordingly:

| Good fit | Poor fit |
|---|---|
| Summarize a thread or article | Multi-step reasoning |
| Rewrite tone (formal ↔ casual) | Long-context analysis (many pages) |
| Proofread / fix grammar | Factual Q&A requiring world knowledge |
| Describe an image for accessibility | Anything needing consistent output across all devices |

The task-specific ML Kit APIs exist precisely because a small model does far better on a narrow, well-defined job than on an open prompt. Lean into that. If your feature needs genuine reasoning or long context, that's a cloud job — possibly with [RAG](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/) — and trying to force it onto Nano will disappoint users on the few devices that even run it.

## Why bother, given the device limits

Three reasons make on-device worth the conditional complexity:

**Privacy.** The text or image never leaves the phone. For messaging, health, journaling, or anything sensitive, that's a feature you can put in marketing copy — and it sidesteps a pile of [mobile privacy and GDPR](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/) obligations that come with shipping user content to a server.

**Offline.** Summarization on the subway, proofreading on a plane. No connectivity dependency.

**Cost.** Zero marginal cost per inference. At scale, moving even a fraction of requests on-device meaningfully dents a cloud LLM bill.

## Production checklist

Things I'd verify before shipping a Gemini Nano feature:

- **Model download UX.** The feature model can be hundreds of megabytes and downloads via AICore. Handle metered-connection preferences and show honest progress; don't block the UI waiting for it.
- **Fallback strategy.** Explicitly decide cloud-fallback vs. hide per feature, and test the `UNAVAILABLE` path on a device that doesn't support Nano — which is most of them.
- **Thermal and battery.** Sustained inference warms the device. For one-shot actions this is fine; don't build a feature that runs Nano in a tight loop.
- **Localization.** Language support is limited and set at client creation. Verify your target languages are covered before promising the feature.
- **Testing.** On-device behavior varies by hardware. Test on real supported devices, not just the emulator.

On-device AI is a great addition to the Android toolbox — it's not a replacement for cloud models, it's a complementary tier for well-scoped, privacy-sensitive, offline-friendly tasks. Treat it as one, design for absence, and it becomes a differentiator rather than a support headache. It pairs naturally with the broader [on-device AI for Android](https://blog.michaelsam94.com/on-device-ai-for-privacy/) privacy story.

## Prompt injection on-device still matters

Even without network exfiltration, malicious text in a summarization input can manipulate output ("ignore previous instructions"). Sanitize inputs: max length caps, block known jailbreak prefixes, and display summaries as **assistive** not authoritative for medical or legal content.

## AICore storage and enterprise MDM

Enterprise devices with MDM may block Google Play system updates — AICore never arrives, Nano stays `UNAVAILABLE`. Detect MDM-restricted devices and document support matrix for IT procurement. Offer cloud fallback behind explicit enterprise policy toggle.

## Benchmarking on minimum hardware

Before marketing "on-device AI," test on your **minimum supported device**, not the Pixel on your desk:

```kotlin
fun benchmarkSummary(text: String, iterations: Int = 10): Stats {
    val times = (1..iterations).map {
        measureTimeMillis { summarizer.runInferenceBlocking(text) }
    }
    return Stats(p50 = times.percentile(50), p95 = times.percentile(95))
}
```

Publish p95 latency in feature specs — "2–8 seconds on supported devices" sets expectations better than demo videos.

## Feature flags per device capability

Remote config: `summarization_enabled` requires `FeatureStatus.AVAILABLE` AND `Build.VERSION.SDK_INT >= 34` AND min RAM check. Gradual rollout by device model percentage — Pixel-first betas before Samsung matrix expansion.

## Content safety filters

Apply on-device blocklist for regulated content categories before inference — reduces harmful output without sending text to cloud moderation. Log blocked attempts locally for abuse investigation; don't upload raw text.

## User education strings

In-app FAQ: "Processed on this device" with link to privacy policy section. Reduces support tickets asking if data uploaded to cloud — transparency beats vague "AI-powered" badge.

## Enterprise MDM blocking AICore

Document workaround path when MDM blocks Google system updates — feature gracefully off with IT admin documentation link. Procurement checklist includes MDM compatibility sign-off.

## Resources

- [Android Developers — AICore and on-device GenAI](https://developer.android.com/ai/gemini-nano)
- [ML Kit — GenAI APIs](https://developers.google.com/ml-kit/genai)
- [Google AI Edge](https://ai.google.dev/edge)
- [Android Developers — ML and AI overview](https://developer.android.com/ai)
- [Google — Gemini Nano announcement](https://blog.google/technology/ai/google-gemini-ai/)
- [Android Developers — Google Play system updates](https://developer.android.com/guide/topics/system/play-system-updates)
