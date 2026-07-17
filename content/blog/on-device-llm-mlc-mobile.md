---
title: "On-Device Models with MLC LLM"
slug: "on-device-llm-mlc-mobile"
description: "Run LLMs on phones and edge devices with MLC LLM: model compilation, memory budgets, Metal/Vulkan backends, and what actually works in production mobile apps."
datePublished: "2025-12-16"
dateModified: "2026-07-17"
tags: ["AI", "Mobile", "MLC LLM", "On-Device"]
keywords: "MLC LLM mobile, on-device LLM, llama mobile inference, MLC compile, edge AI"
faq:
  - q: "Which model sizes are realistic on a mid-range phone with MLC LLM?"
    a: "A phone with 6–8 GB RAM can run 3B–4B parameter models at 4-bit quantization with acceptable latency for chat. 7B models work on flagship devices with aggressive quantization but expect 2–4 tokens per second. Anything above 7B belongs on a server unless you target tablets with 12 GB+ RAM."
  - q: "How does MLC LLM differ from llama.cpp on mobile?"
    a: "MLC LLM compiles models ahead of time into optimized kernels for Metal, Vulkan, or CUDA using TVM, which often yields better sustained throughput on mobile GPUs. llama.cpp is simpler to integrate and has broader community support, but MLC tends to win on Apple Silicon and Android GPU paths when you've invested in the compile pipeline."
  - q: "Do I need to ship model weights inside the app bundle?"
    a: "Not necessarily. Many apps download quantized weights on first launch from CDN and cache them locally. App Store and Play Store size limits make bundling anything above a tiny model impractical. Treat the model as downloadable content with integrity checks and version pinning."
---

Last quarter I shipped a note-taking app with on-device summarization. The product requirement was simple: summarize a meeting transcript without sending it to our API. The engineering requirement was harder — run a 3B model on a three-year-old Android phone without draining the battery in ten minutes. We landed on MLC LLM after burning a week on a generic ONNX runtime that couldn't hold 30 tokens per second on anything but a Pixel 8.

MLC LLM (Machine Learning Compilation for LLM) takes a Hugging Face checkpoint, quantizes it, and compiles device-specific kernels through Apache TVM. The output is a `mlc-chat` bundle you embed in iOS, Android, or even a browser via WebGPU. The compile step is painful; the runtime is fast.

## The compile pipeline

You don't drop a `.safetensors` file into your app. You run `mlc_llm package` (or the Python `mlc_llm compile` flow) against a chosen quantization scheme:

```bash
# Example: compile Llama-3.2-3B for iOS Metal
mlc_llm compile \
  HF://meta-llama/Llama-3.2-3B-Instruct \
  --quantization q4f16_1 \
  --device iphone \
  -o ./dist/llama-3.2-3b-iphone
```

The quantization flag matters more than the model name. `q4f16_1` is the usual starting point — 4-bit weights with fp16 activations. Drop to `q3f16` if you're memory-bound; quality degrades noticeably on reasoning tasks but stays fine for summarization.

Compile once per target device family. iOS Metal, Android Vulkan, and macOS are separate artifacts. CI should cache compiled bundles keyed by `(model_id, quant, device)` because recompiling Llama-3B takes 15–30 minutes.

## Memory budgeting on mobile

On-device inference fails in predictable ways:

| Resource | Typical limit | What breaks first |
|----------|---------------|-------------------|
| RAM | 1.5–2× model size + KV cache | OOM kill on background |
| GPU memory | Shared with display compositor | Frame drops during inference |
| Thermal | Sustained GPU load | Throttling after 60–90s |
| Storage | 1.5–3 GB per model | User uninstalls |

Size the KV cache explicitly. A 4096-token context on a 3B model at 4-bit can add 200–400 MB beyond weights. For a summarization feature, cap context at 2048 tokens and chunk long documents server-side or with a sliding window — don't pretend the phone is a datacenter.

```kotlin
// Android: initialize MLC engine with explicit limits
val engine = MLCEngine(
    modelPath = cacheDir.resolve("llama-3.2-3b-q4").absolutePath,
    maxSeqLen = 2048,
    prefillChunkSize = 512,  // reduces peak memory during prompt ingestion
)
```

## Integration patterns that survive App Review

**Download-on-first-use.** Ship a 50 MB binary; fetch the 1.8 GB model after consent. Show storage requirements upfront. Pin SHA-256 of the weight file.

**Background inference is a trap.** iOS will suspend you mid-generation. Run inference only in foreground with a visible progress indicator, or use `BGProcessingTask` for non-interactive batch work with tight time limits.

**Fallback to cloud.** If `MLCEngine.init()` fails (low memory, corrupt cache), degrade gracefully to your API. Log the failure reason — low-end device clusters show up quickly in analytics.

**Streaming UI.** Token streaming keeps users patient during 3 tok/s generation. Buffer tokens and flush to the TextView every 50 ms to avoid layout thrash.

## Performance tuning beyond defaults

Prefill (processing the prompt) and decode (generating tokens) have different bottlenecks. Long prompts bottleneck on compute; long outputs bottleneck on memory bandwidth.

- Reduce `prefillChunkSize` if you see OOM spikes when the user pastes a wall of text.
- Use speculative decoding only if you have a draft model small enough to fit alongside the main model — rare on phones.
- Warm up the engine on app launch with a one-token generation. First inference after cold start can be 3× slower.

On iPhone 15 Pro we saw ~25 tok/s prefill and ~18 tok/s decode on Llama-3.2-3B q4f16. On a Galaxy A54, the same model ran ~8 tok/s decode — still usable for a two-paragraph summary.

## When MLC is the wrong choice

Skip MLC if you need frequent model updates (compile latency kills iteration), if your feature requires 70B-class reasoning, or if your team has no one willing to own the TVM compile toolchain. For a single fixed model on iOS and Android with latency requirements under 5 seconds for short outputs, it's the best open-source path I've used.

If you only target Apple and want less compile ceremony, Apple's MLX Swift bindings are worth evaluating. MLC wins when you need the same model artifact story on both platforms.

## Common production mistakes

Teams get on device llm mlc mobile wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of on device llm mlc mobile fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When on device llm mlc mobile misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## MLC compile targets and TVM artifacts

MLC compiles models per device family — iPhone 15 and iPhone 12 get different `.mlc` bundles. CI must build matrix artifacts or use runtime JIT compile (slow first launch). Ship smallest bundle for broad support; offer "high quality model" download like games ship HD textures.

## Memory pool configuration

MLC exposes `memory_usage` and prefill chunk settings. Tuning `prefill_chunk_size` trades time-to-first-token against peak RAM — profile with Instruments Allocations on oldest supported iPhone.

## Unified API across platforms

MLC's ChatModule API is consistent Python/Swift/Kotlin — good for teams sharing inference code. Downside: compile pipeline learning curve. Budget a week for engineer training before production commitments.

## App Store size limits

Multiple MLC bundles blow cellular download limits — use on-demand resources (iOS) or Play Feature Delivery (Android) for >150MB model artifacts. Show Wi-Fi-only download toggle default on.

## Quantization artifacts per SKU

Maintain spreadsheet: device model → recommended bundle → max context. Support reads sheet from remote config — engineering updates without app release when new iPhone launches.

## Model license click-through

First run show license acceptance for bundled weights — required for some Hugging Face gated models packaged in app.

## Xcode build settings for MLC

Embed MLC bundle in Copy Bundle Resources — CI must verify bundle present; missing bundle fails silently at runtime with obscure TVM error.

## Resources

- [MLC LLM GitHub repository](https://github.com/mlc-ai/mlc-llm)
- [MLC LLM iOS/Android deployment docs](https://llm.mlc.ai/docs/deploy/ios.html)
- [Apache TVM documentation](https://tvm.apache.org/docs/)
- [Llama model cards on Hugging Face](https://huggingface.co/meta-llama)
- [Apple Metal Performance Shaders overview](https://developer.apple.com/metal/)
