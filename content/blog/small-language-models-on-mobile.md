---
title: "Small Language Models on Mobile: The On-Device AI Shift"
slug: "small-language-models-on-mobile"
description: "Small language models and on-device AI for mobile apps: SLM sizing, Gemini Nano, llama.cpp on Android, and when cloud LLMs still win on latency and quality."
datePublished: "2026-01-25"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "small language models, SLM, on-device AI, mobile LLM, Gemini Nano, edge AI"
faq:
  - q: "SLM vs cloud LLM?"
    a: "SLMs trade capability for latency, offline use, and data staying on device."
  - q: "Quantization?"
    a: "INT4 shrinks size but test task-specific accuracy after quant."
  - q: "Frameworks?"
    a: "Core ML, TensorFlow Lite, ONNX Runtime Mobile — match to hardware delegates."
---

The center of gravity in mobile AI is moving from the cloud to the device, and small language models are why. For a decade I've built Android and Flutter apps where every intelligent feature meant a network round-trip to a server. That assumption is breaking. A 1–4 billion parameter model now runs directly on a flagship phone's NPU, summarizing a thread or drafting a reply in a few hundred milliseconds, with the data never leaving the device.

This isn't a smaller version of the cloud story — it's a different architecture with different constraints. SLMs give you privacy, offline capability, zero per-request cost, and latency a network can't match. In exchange you accept a capability ceiling and a real memory and battery budget. Knowing where that line sits is the whole game for mobile engineers right now.

## Why "small" is the point on mobile

A frontier cloud model has hundreds of billions of parameters and a datacenter behind it. That's the wrong tool for "summarize this notification" — it's slow, it costs money per call, it needs connectivity, and it ships the user's private message to a server. An on-device SLM inverts every one of those:

- **Privacy by architecture.** The data is processed where it lives. For messaging, health, and finance apps, this is the difference between a feature you can ship and one legal won't approve. It's the same principle behind [on-device AI for privacy](https://blog.michaelsam94.com/on-device-ai-for-privacy/).
- **Offline.** It works on a plane, in a tunnel, on [flaky mobile networks](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) — the conditions real phones actually live in.
- **Latency.** No round-trip means results feel instant, which changes what interactions are worth building.
- **Cost.** Inference on the user's silicon is free to you. At scale that's enormous.

The tradeoff is capability. A 3B model won't match a frontier model at complex reasoning. But a shocking amount of mobile AI is *not* complex reasoning — it's summarize, rewrite, classify, extract, suggest. SLMs handle those well, and those are the features users actually touch dozens of times a day.

## The platform runtimes doing the heavy lifting

You don't ship a raw GGUF in your app bundle. The platforms now provide managed on-device model runtimes, which is the right layer to build on:

- **Android — Gemini Nano** via the AICore system service and ML Kit GenAI APIs. The model is managed by the OS, shared across apps, and hardware-accelerated. I covered the integration details in [on-device AI on Android with Gemini Nano](https://blog.michaelsam94.com/on-device-ai-android-gemini-nano/).
- **Apple** provides on-device foundation models through its Foundation Models framework, callable from Swift with structured output support.
- **Cross-platform** options exist too — MediaPipe LLM Inference, and llama.cpp-based runtimes for [running local LLMs on-device](https://blog.michaelsam94.com/running-local-llms-on-device/) when you need control the platform APIs don't give.

Using the OS-managed model matters: it's shared memory across apps, updated by the platform, and tuned for that specific silicon. Bundling your own model is a last resort for when you need a specific one the platform doesn't offer.

## The constraints you must design around

On-device is not free lunch. Three budgets bind you, and ignoring them produces janky, battery-draining apps:

| Constraint | Reality on mobile | Design response |
| --- | --- | --- |
| Memory | Model + KV cache competes with your app for RAM | Prefer OS-shared models; keep context short |
| Battery/thermal | Sustained inference heats the device and drains battery | Batch work, avoid inference in tight loops |
| Latency | First-token load can lag if the model was evicted | Warm the model before the user needs it |

Memory is the tightest. A phone that "has 8GB" doesn't give your app 8GB — the OS, other apps, and your own UI need it. This is why OS-managed shared models are so valuable: the model's memory footprint isn't multiplied per app. Treat inference like camera or GPS — a heavyweight resource you acquire deliberately and release promptly, not something you leave running.

## A hybrid architecture is usually right

The pragmatic pattern isn't "on-device *or* cloud" — it's routing. Handle what the SLM does well locally, and escalate the rest:

```kotlin
suspend fun handleRequest(task: AiTask): AiResult =
    when {
        task.isSensitive || !network.isAvailable() ->
            onDeviceModel.run(task)          // privacy or offline: stay local
        task.complexity == Complexity.LOW ->
            onDeviceModel.run(task)          // simple: local is faster and free
        else ->
            cloudModel.run(task)             // hard reasoning / long context: cloud
    }
```

This gives you the best of both: private and instant for the common case, powerful when the task genuinely demands it. The routing logic itself becomes a small product decision — err toward on-device for anything sensitive, and let complexity or context length be the trigger to escalate. The economics of that escalation connect directly to [cutting LLM costs with routing](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/).

## What this means for mobile engineers

After years of treating AI as a server-side concern, on-device SLMs pull it back into the client, and that reshapes how we build. Features that were impossible for privacy reasons become shippable. Latency-sensitive interactions — live suggestions, instant summaries — become viable. And the app keeps working when the network doesn't, which for mobile is not an edge case but the baseline.

My advice to teams: start by identifying the features that are simple enough for a small model *and* benefit from privacy, offline, or instant response. Those are where on-device SLMs win decisively today. Build them on the platform-managed runtime, budget memory and battery honestly, and keep a cloud fallback for the hard cases. The device in the user's pocket is now a capable inference machine — the shift is learning to treat it like one. If you're weighing where AI belongs in your mobile stack, [I'm happy to talk it through](https://michaelsam94.com/#contact).

## Thermal throttling during on-device STT

Ninety seconds continuous inference throttled mid-tier Android CPU 3×. Mitigation: chunk audio with breath gaps; prefer NPU delegate; offer cloud fallback with explicit consent when skin temp API signals pressure — users prefer slower correct transcript to device heat warning.

## Thermal throttling during on-device STT

Ninety seconds continuous inference throttled mid-tier Android CPU 3×. Mitigation: chunk audio with breath gaps; prefer NPU delegate; offer cloud fallback with explicit consent when skin temp API signals pressure — users prefer slower correct transcript to device heat warning.

## Field metrics and rollback

Capture baseline p75 error rate and latency on tier-1 routes before merge. Compare seven days post-deploy sliced by mobile and region. Document rollback in PR and runbook.

## Notes on small language models on mobile

Measure battery impact of inference on target devices over thirty minute session — thermal throttling changes latency. Quantize after fine-tune; evaluate perplexity on domain vocabulary, not generic benchmarks. Fallback to cloud when on-device confidence below threshold keeps quality acceptable.

## Resources

- [Android — AICore and Gemini Nano](https://developer.android.com/ai/gemini-nano)
- [Google AI — Gemini Nano and on-device docs](https://ai.google.dev/edge)
- [Apple — Foundation Models framework](https://developer.apple.com/documentation/foundationmodels)
- [Google — MediaPipe LLM Inference](https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference)
- [llama.cpp — GitHub](https://github.com/ggml-org/llama.cpp)
- [Hugging Face — small models and edge deployment](https://huggingface.co/models)

Benchmark on lowest supported device with thermal throttling, not M-series Macs.

Ship small language models on mobile changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff.
