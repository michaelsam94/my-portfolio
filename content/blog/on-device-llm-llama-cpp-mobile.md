---
title: "Running llama.cpp on Mobile"
slug: "on-device-llm-llama-cpp-mobile"
description: "Run local LLMs on iOS and Android with llama.cpp: GGUF quantization, memory budgets, JNI/ Swift integration, and production patterns for on-device inference."
datePublished: "2025-08-20"
dateModified: "2025-08-20"
tags: ["AI", "Mobile", "On-Device", "LLM"]
keywords: "llama.cpp mobile, GGUF quantization, on-device LLM iOS Android, local LLM inference, mobile AI"
faq:
  - q: "Which llama.cpp quantization should mobile apps use?"
    a: "Q4_K_M is the usual starting point — good quality-to-size ratio for 3B–8B models on flagships. Q8_0 if you have RAM headroom and need better reasoning. Q2_K for experimentation only — quality drops sharply. Always benchmark on your minimum supported device, not just the dev phone."
  - q: "How much RAM does a local LLM need on mobile?"
    a: "Rough rule: model file size plus 20–40% overhead for KV cache and runtime. A 2GB Q4_K_M model needs ~2.5–3GB free RAM for comfortable context. iOS jetsam kills apps aggressively above memory limits — target 1–3B models for broad device support, 7B+ for Pro/flagship tiers only."
  - q: "Is llama.cpp production-ready for consumer apps?"
    a: "Yes for assisted features — summarization, rewrite, structured extraction with human review. Not for open-ended chat at 7B on older devices without tiered model delivery and graceful degradation. Wrap inference in timeouts, stream tokens to UI, and offer cloud fallback when device can't load model."
---

Shipping a 7B Q4 model added 4.2GB to our IPA and crashed on iPhone 12 at load time — jetsam before the first token. After switching to llama.cpp with a tiered 1.5B model for standard devices and optional 7B download for Pro hardware, on-device summarization worked offline for 89% of the fleet. llama.cpp is the pragmatic path to local LLMs on mobile: plain C++, GGUF quantizations, Metal on iOS and Vulkan/CPU on Android, no PyTorch runtime in your APK.

## Why llama.cpp on mobile

Alternatives compared:

| Runtime | Pros | Cons |
|---------|------|------|
| llama.cpp | Small binary, GGUF ecosystem, Metal/Vulkan | Manual integration |
| ML Kit / MediaPipe | Google-supported, simpler API | Fewer model choices |
| ONNX Runtime GenAI | Cross-platform | Heavier, model prep pipeline |
| MLC LLM | TVM-compiled, fast on Apple | Build complexity |

llama.cpp wins when you need control over model file delivery, quant format, and context length — and when you want one inference core across iOS and Android via shared C++.

## Model selection and GGUF quantizations

Download from Hugging Face (`TheBloke`, `bartowski` quantizations):

| Model | Q4_K_M size | Use case |
|-------|-------------|----------|
| Llama-3.2-1B-Instruct | ~770 MB | Broad iOS/Android support |
| Phi-3-mini-4k-instruct | ~2.3 GB | Better quality, flagship |
| Qwen2.5-3B-Instruct | ~2.0 GB | Strong multilingual |
| Gemma-2-2B-it | ~1.6 GB | Balanced |

```bash
# Pull GGUF locally for testing
huggingface-cli download bartowski/Llama-3.2-1B-Instruct-GGUF \
  Llama-3.2-1B-Instruct-Q4_K_M.gguf --local-dir ./models
```

Validate with `./llama-cli -m model.gguf -p "Summarize: ..." -n 128` on desktop before mobile integration.

## Memory and context budgeting

KV cache grows with context:

```
KV_memory ≈ 2 × n_layers × n_heads × head_dim × context_len × bytes_per_weight
```

Practical limits on mobile:
- **context 2048** — safe default for summarization
- **context 4096+** — monitor memory; offer user setting only on Pro tier
- **batch size 1** — always for inference (not training)

iOS: use `os_proc_available_memory()` before load; abort gracefully below threshold.

Android: `ActivityManager.getMemoryInfo()` — warn on `lowMemory`.



**iOS integration.**

Use official `llama.cpp` SPM package or bind via bridging header:

```swift
import llama

final class LocalLLM {
    private var model: OpaquePointer?
    private var context: OpaquePointer?

    func load(modelPath: String, contextLen: Int32 = 2048) throws {
        var params = llama_model_default_params()
        params.n_gpu_layers = 99  // Metal offload all layers
        guard let m = llama_load_model_from_file(modelPath, params) else {
            throw LLMError.loadFailed
        }
        model = m

        var ctxParams = llama_context_default_params()
        ctxParams.n_ctx = UInt32(contextLen)
        ctxParams.n_batch = 512
        guard let c = llama_new_context_with_model(m, ctxParams) else {
            throw LLMError.contextFailed
        }
        context = c
    }

    func generate(prompt: String, maxTokens: Int32 = 256) -> AsyncStream<String> {
        // Tokenize, llama_decode loop, stream via AsyncStream
    }
}
```

Run inference off main thread — `Task.detached(priority: .userInitiated)`.

Ship model via:
- **On-demand resource (ODR)** — Apple hosts, downloads on first use
- **Background URLSession** — your CDN, verify SHA-256 before load



**Android integration.**

Community wrappers: `llama-android`, `LocalLLM` bindings, or direct JNI to `libllama.so`:

```kotlin
class LlamaEngine(private val modelPath: String) {
    external fun loadModel(nGpuLayers: Int): Long
    external fun generate(contextPtr: Long, prompt: String, maxTokens: Int): String

    companion object {
        init { System.loadLibrary("llama") }
    }
}
```

Build `libllama.so` per ABI (`arm64-v8a` minimum; drop `armeabi-v7a` for LLM apps — too slow):

```bash
cmake -B build-android -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 \
  -DLLAMA_VULKAN=ON
cmake --build build-android --config Release
```

Vulkan acceleration on Adreno/Mali; CPU fallback when GPU busy.



**Prompting small models.**

Small models need tighter prompts:

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
Summarize the following text in 3 bullet points. Be factual. Do not invent details.<|eot_id|>
<|start_header_id|>user<|end_header_id|>
{user_text}<|eot_id|>
<|start_header_id|>assistant<|end_header_id|>
```

Use model-specific chat templates (Llama 3, Phi-3, Qwen each differ). Wrong template = gibberish output.

Cap input length — truncate with sentence boundaries, not mid-word chop.



**Production patterns.**

**Tiered delivery:**
- App bundle: no model (small IPA) or tiny 1B for instant demo
- CDN download: larger model after Wi-Fi confirmation
- Cloud fallback: if load fails or user on unsupported device

**Streaming UI:** emit tokens as generated — perceived latency drops even if total time is unchanged.

**Cancellation:** user navigates away → set abort flag on decode loop; llama.cpp supports context interruption patterns.

**Thermal throttling:** monitor `ProcessInfo.processInfo.thermalState` (iOS) — pause or reduce max tokens when `.serious`.

**Analytics (privacy-safe):** log tokens/sec, load time, OOM rate — not prompt content.



**Performance benchmarks.**

| Device | Model | tok/s | First token |
|--------|-------|-------|-------------|
| iPhone 15 Pro | Llama-3.2-1B Q4 | ~85 | ~180ms |
| iPhone 12 | Llama-3.2-1B Q4 | ~32 | ~420ms |
| Pixel 8 | Qwen2.5-3B Q4 Vulkan | ~28 | ~350ms |
| Mid-range Android | Phi-3-mini Q4 | ~12 | ~900ms |

Set user expectations — "on-device" doesn't mean ChatGPT speed on 2020 hardware.



**Legal and store compliance.**

- Disclose on-device AI in App Store / Play Data Safety
- Model license — Llama Community License has MAU thresholds; Gemma, Qwen have own terms
- Content moderation still your responsibility — filter outputs in sensitive apps

Gate model load on available RAM and thermal state; expose "on-device AI" as opt-in in settings for users on older phones. Hash-verify downloaded GGUF files before load — CDN bitrot and partial downloads cause obscure crash loops. Log aggregate tok/s and OOM rate, never prompt text, in your analytics pipeline. App Store review notes should mention optional large downloads and battery impact. Maintain a matrix of supported models per device tier in docs support can reference. When Apple or Google updates OS GPU drivers, rerun benchmarks — Metal and Vulkan performance shifts between OS versions more than app releases.

Quantize to Q4_K_M minimum for usable speed on phone — Q8 models quality gains don't justify 3× latency on battery power.

## Resources

- [llama.cpp GitHub repository](https://github.com/ggerganov/llama.cpp)
- [GGUF format specification](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
- [Hugging Face GGUF models](https://huggingface.co/models?library=gguf)
- [Apple On-Demand Resources](https://developer.apple.com/library/archive/documentation/DeveloperTools/onboarding/introduction.html)
- [Meta Llama mobile deployment guide](https://llama.meta.com/docs/deploy/)
