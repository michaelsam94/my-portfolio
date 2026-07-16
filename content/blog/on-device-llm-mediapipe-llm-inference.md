---
title: "On-Device LLM Inference with MediaPipe"
slug: "on-device-llm-mediapipe-llm-inference"
description: "Run LLMs on Android and iOS with MediaPipe LLM Inference API: model conversion, GPU acceleration, streaming, and integration patterns for production mobile apps."
datePublished: "2025-08-23"
dateModified: "2025-08-23"
tags: ["AI", "Mobile", "On-Device", "MediaPipe"]
keywords: "MediaPipe LLM inference, on-device LLM Android, Google AI Edge, mobile LLM API, Gemma mobile"
faq:
  - q: "What models does MediaPipe LLM Inference support?"
    a: "Primarily Gemma (1B, 2B), Phi-2, Falcon, and StableLM variants converted to MediaPipe's flatbuffer format (.task or bundled weights). The supported model list evolves — check Google's AI Edge documentation for current conversions and hardware requirements."
  - q: "How does MediaPipe compare to llama.cpp on mobile?"
    a: "MediaPipe offers a higher-level Android/iOS API with GPU delegation (OpenCL/Vulkan/Metal) and Google-maintained integration — less JNI boilerplate. llama.cpp offers broader GGUF model support and finer control. Choose MediaPipe for faster integration with supported models; llama.cpp for custom models and quant flexibility."
  - q: "Can MediaPipe LLM run fully offline?"
    a: "Yes. Models ship in-app or download once to device storage. Inference requires no network after model load. Verify model checksum on download and store in app-private storage."
---

Google's MediaPipe LLM Inference API gave us a working Android prototype in an afternoon — load Gemma 2B, stream tokens to a Compose `Text`, GPU acceleration enabled with one flag. The same task took three days with raw llama.cpp JNI, though we eventually switched for a custom Qwen quant llama.cpp didn't support yet. MediaPipe sits in the middle: opinionated, Google-maintained, optimized for Gemma and a short list of models, with less plumbing than rolling your own C++ bridge.

## MediaPipe LLM Inference stack

```
┌─────────────────────────────────────────┐
│  Your app (Kotlin / Swift)              │
├─────────────────────────────────────────┤
│  MediaPipe Tasks GenAI API              │
│  LlmInference · LlmInferenceSession     │
├─────────────────────────────────────────┤
│  GPU delegate (OpenCL / Metal) or CPU   │
├─────────────────────────────────────────┤
│  Converted model (.bin / task bundle)   │
└─────────────────────────────────────────┘
```

Part of **Google AI Edge** — same family as MediaPipe vision/audio tasks, unified delegate system.

## Setup (Android Gradle)

```kotlin
// libs.versions.toml / build.gradle.kts
dependencies {
    implementation("com.google.mediapipe:tasks-genai:0.10.24")
}
```

Copy converted model to device storage or assets:

```kotlin
class LocalLlmRepository(private val context: Context) {
    private var llm: LlmInference? = null

    suspend fun initialize(modelPath: String) = withContext(Dispatchers.IO) {
        val options = LlmInference.LlmInferenceOptions.builder()
            .setModelPath(modelPath)
            .setMaxTokens(512)
            .setPreferredBackend(LlmInference.Backend.GPU)
            .build()
        llm = LlmInference.createFromOptions(context, options)
    }
}
```

Fallback to CPU when GPU delegate fails (common on emulators):

```kotlin
try {
    options.setPreferredBackend(LlmInference.Backend.GPU)
} catch (e: MediaPipeException) {
    options.setPreferredBackend(LlmInference.Backend.CPU)
}
```



**Streaming generation.**

```kotlin
fun summarize(text: String): Flow<String> = callbackFlow {
    val session = LlmInferenceSession.createFromOptions(
        llm!!,
        LlmInferenceSession.LlmInferenceSessionOptions.builder()
            .setTopK(40)
            .setTemperature(0.8f)
            .build()
    )

    session.addQueryChunk("""
        Summarize in 3 bullet points:
        $text
    """.trimIndent())

    session.generateResponseAsync { partial, done ->
        trySend(partial)
        if (done) close()
    }

    awaitClose { session.close() }
}
```

Collect in ViewModel with `stateIn` — update UI per partial token for responsive feel.



**iOS integration.**

```swift
import MediaPipeTasksGenAI

var llm: LlmInference?

func loadModel(path: String) throws {
    var options = LlmInferenceOptions()
    options.modelPath = path
    options.maxTokens = 512
    options.preferredBackend = .gpu
    llm = try LlmInference(options: options)
}

func generate(prompt: String) async throws -> AsyncStream<String> {
    var sessionOptions = LlmInferenceSessionOptions()
    sessionOptions.topK = 40
    sessionOptions.temperature = 0.8
    let session = try LlmInferenceSession(llm: llm!, options: sessionOptions)
    try session.addQueryChunk(inputText: prompt)
    return session.generateResponseAsync()
}
```

Metal delegate on Apple Silicon and recent A-series chips.



**Model conversion.**

MediaPipe models aren't raw GGUF — convert via Google-provided scripts or download preconverted:

```bash
# Example pattern — check current ai-edge-torch docs for exact commands
python -m mediapipe_model_maker.convert \
  --model_path gemma-2b-it \
  --output_path gemma-2b-it.task
```

Preconverted models often hosted on [Kaggle Models](https://www.kaggle.com/models) or Google's model zoo. Verify:
- Model license (Gemma terms)
- File size vs app store limits
- Minimum SDK / iOS version for GPU delegate



**Configuration tuning.**

| Parameter | Effect | Mobile recommendation |
|-----------|--------|----------------------|
| `maxTokens` | Output cap | 256–512 for summaries |
| `topK` | Sampling diversity | 20–40 |
| `temperature` | Randomness | 0.3 factual, 0.8 creative |
| `preferredBackend` | GPU vs CPU | GPU first, CPU fallback |

Long input contexts consume RAM linearly — truncate input text before `addQueryChunk`. For long documents, map-reduce: chunk → summarize each → merge summaries.



**Model delivery.**

1. **Bundled in APK/IPA** — instant, increases store download size
2. **Play Asset Delivery / ODR** — large models on-demand
3. **First-run download** — ProgressBar + Wi-Fi-only checkbox

```kotlin
suspend fun ensureModel(): String {
    val dest = File(context.filesDir, "gemma-2b.task")
    if (!dest.exists()) {
        downloadWithChecksum(MODEL_URL, dest, expectedSha256 = HASH)
    }
    return dest.absolutePath
}
```



**Error handling and lifecycle.**

- **Load once, reuse session pool** — model load is seconds; don't reload per query
- **Close sessions** after generation — leak GPU memory otherwise
- **Process death** — persist pending jobs; don't assume in-memory model survives background kill
- **Timeout** — wrap generation in `withTimeout(30_000)`; cancel session on expiry



**MediaPipe vs llama.cpp.**

| Criterion | MediaPipe | llama.cpp |
|-----------|-----------|-----------|
| Time to first demo | Hours | Days |
| Model catalog | Google-curated | Any GGUF |
| GPU on Android | Built-in delegate | Vulkan manual |
| iOS Metal | Supported | Supported |
| Community models | Limited | Extensive |
| Binary size | tasks-genai AAR | libllama.so per ABI |

Hybrid approach: MediaPipe for MVP with Gemma; migrate to llama.cpp if you need Qwen/Llama custom quants.

## Production checklist

- [ ] Benchmark on minimum supported device (not Pixel 8 Pro only)
- [ ] Thermal test — 10 consecutive generations
- [ ] Memory profile in Android Studio / Instruments
- [ ] Offline airplane mode verification
- [ ] Privacy disclosure — prompts stay on device
- [ ] Output moderation for user-visible text
- [ ] Cloud fallback when `initialize()` throws OOM

We shipped MediaPipe Gemma 1B for email subject-line suggestions — 40 tok/s on Pixel 7a, 1.1GB model via PAD. Quality sufficient; 2B was marginal gain for 2× RAM.

Lock `tasks-genai` version in Gradle and CocoaPods — Google updates can change delegate behavior between patch releases. Test emulator CPU-only path explicitly; GPU delegates fail silently on CI emulators while working on hardware. Provide user-visible "downloading model" and "preparing AI" states; first load takes seconds and feels broken without feedback. Compare MediaPipe latency against llama.cpp on the same device before committing — for unsupported models, hybrid fallback may be cheaper than waiting for official conversions. Document minimum SDK and chip requirements in store listings to reduce one-star "doesn't work" reviews from incompatible devices. Re-run load tests after each `tasks-genai` bump; delegate selection logic changes more often than release notes suggest. Treat first-token latency as a product metric, not just an engineering benchmark.

## Common production mistakes

Teams get on device llm mediapipe llm inference wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of on device llm mediapipe llm inference fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Google AI Edge — LLM Inference overview](https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference)
- [MediaPipe Tasks GenAI Android API](https://developers.google.com/mediapipe/solutions/genai/llm_inference/android)
- [MediaPipe Tasks GenAI iOS API](https://developers.google.com/mediapipe/solutions/genai/llm_inference/ios)
- [Gemma model family](https://ai.google.dev/gemma)
- [Kaggle Models — MediaPipe-compatible weights](https://www.kaggle.com/models)
