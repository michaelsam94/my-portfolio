---
title: "Speech-to-Text with Whisper"
slug: "multimodal-audio-transcription-whisper"
description: "Build production speech-to-text pipelines with OpenAI Whisper: model selection, chunking long audio, timestamps, language detection, and deployment trade-offs."
datePublished: "2025-08-04"
dateModified: "2026-07-17"
tags:
keywords: "OpenAI Whisper, speech to text, audio transcription, Whisper API, automatic speech recognition, timestamp extraction"
faq:
  - q: "Which Whisper model should I use in production?"
    a: "Whisper large-v3 offers the best accuracy for mixed accents and noisy audio. Whisper small or medium balances cost and speed for clean studio recordings. For real-time use, distil-whisper or faster-whisper with CTranslate2 cuts latency by 4–6x at modest accuracy cost."
  - q: "How do I transcribe audio longer than 25 minutes?"
    a: "Split audio into overlapping chunks (30–60 seconds with 2-second overlap), transcribe each chunk, then merge text while deduplicating overlap regions. Use voice activity detection (VAD) to skip silence and reduce API cost."
  - q: "Can Whisper handle multiple speakers?"
    a: "Whisper transcribes mixed audio as a single stream without speaker labels. Add a diarization step—pyannote.audio or similar—to assign speaker IDs before or after transcription."
---
A support team uploads 40-minute call recordings and needs searchable transcripts by morning. Generic cloud STT charges per minute and garbles product names. Whisper—OpenAI's open-weight speech recognition model—handles 99 languages, noisy phone lines, and technical vocabulary when you pick the right variant and chunking strategy. The API wraps the same models; self-hosting with faster-whisper gives you cost control at scale.

## Model landscape

| Model | Parameters | Relative speed | Best for |
|-------|-----------|----------------|----------|
| tiny | 39M | Fastest | Prototyping, edge devices |
| base | 74M | Fast | Low-latency drafts |
| small | 244M | Moderate | Clean podcasts, meetings |
| medium | 769M | Slower | Accented speech |
| large-v3 | 1.5B | Slowest | Production accuracy |

`large-v3` added improved multilingual performance and reduced hallucinations on silence. For batch jobs overnight, accuracy wins. For live captions, `small` on a GPU with faster-whisper often suffices.

## Basic transcription

**OpenAI API:**

```python
from openai import OpenAI

client = OpenAI()
with open("call.wav", "rb") as f:
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        response_format="verbose_json",
        timestamp_granularities=["word"],
    )
print(result.text)
for seg in result.words:
    print(f"{seg.start:.2f}s: {seg.word}")
```

**Self-hosted faster-whisper:**

```python
from faster_whisper import WhisperModel

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe("call.wav", beam_size=5, vad_filter=True)

print(f"Language: {info.language} ({info.language_probability:.2f})")
for seg in segments:
    print(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}")
```

`vad_filter=True` skips silent regions—critical for hour-long files where 30% is hold music.

## Chunking long audio

Whisper processes ~30 seconds optimally; longer inputs degrade at boundaries. Pipeline:

1. Convert to 16 kHz mono WAV (Whisper's training format).
2. Run Silero VAD or WebRTC VAD to find speech segments.
3. Group segments into 30-second windows with 2-second overlap.
4. Transcribe each window; merge by aligning overlap text with fuzzy matching.

```python
def merge_chunks(chunks: list[str], overlap_words: int = 8) -> str:
    if not chunks:
        return ""
    merged = chunks[0]
    for chunk in chunks[1:]:
        tail = merged.split()[-overlap_words:]
        head = chunk.split()[:overlap_words]
        # find longest common subsequence in overlap zone
        merged = merged + chunk[max(0, len(chunk) - len(chunk.split()) + overlap_words):]
    return merged
```

For word-level timestamps across chunks, offset each segment's `start`/`end` by the chunk's position in the original file.

## Reducing hallucinations

Whisper invents text on pure silence or very quiet noise—"Thank you for watching" is a infamous artifact. Mitigations:

- **VAD pre-filter:** Drop segments below -40 dBFS.
- **`condition_on_previous_text=False`:** Stops error propagation across chunks (slightly worse coherence).
- **`no_speech_threshold`:** Raise from default 0.6 to 0.8 for noisy environments.
- **Prompt engineering (API):** Pass domain vocabulary: `"Product names: AcmeWidget, CloudSync Pro."`

## Production deployment

**Batch pipeline:** S3 trigger → Lambda/ECS job → faster-whisper on GPU → transcript to OpenSearch. Cost: ~$0.003/minute self-hosted vs ~$0.006/minute API.

**Streaming:** Whisper is not natively streaming. Use a sliding window: transcribe the last 10 seconds every 2 seconds, display partial results. Expect 2–4 second lag with `small` on a T4 GPU.

**Hardware:** `large-v3` needs ~10 GB VRAM at float16. `medium` fits on a 6 GB card. CPU inference works for `tiny`/`base` only—plan 10–20x slower.

Store raw audio and transcripts with matching job IDs. Re-run when models improve; transcription is deterministic given fixed model weights and decoding parameters.

## Evaluation

Measure word error rate (WER) on a held-out set from your domain:

```
WER = (substitutions + insertions + deletions) / total_reference_words
```

Target WER under 10% for clean English; 15–20% is acceptable for accented call-center audio. Track WER by audio quality bucket (SNR, codec) to decide when human review is mandatory.

## Language detection and routing

Whisper auto-detects language but misidentifies similar languages (Norwegian/Danish, Hindi/Urdu). For production:

```python
result = model.transcribe(audio, language=None)  # auto-detect
if result["language_probability"] < 0.85:
    result = model.transcribe(audio, language=user_locale_hint)
```

Route high-stakes transcripts (legal, medical) to human review when confidence is low — WER doubles on domain jargon without fine-tuning.

## Speaker diarization

Whisper doesn't separate speakers natively. Pipeline options:

1. **pyannote.audio** — speaker segments, then Whisper per segment
2. **AssemblyAI / Deepgram** — hosted diarization + transcription
3. **Channel separation** — stereo call recordings with agent/customer on separate channels

Diarization errors cascade — wrong speaker label on a compliance call is worse than no label. Validate on sample calls before automating QA scoring.

## Cost optimization

| Approach | Cost/min | Latency | Quality |
|----------|----------|---------|---------|
| OpenAI Whisper API | ~$0.006 | Low | High |
| Self-hosted large-v3 | ~$0.003 (GPU amortized) | Medium | High |
| distil-whisper | ~$0.001 | Low | Good |
| tiny on CPU | ~$0.0005 | High | Fair |

Batch overnight transcription for non-real-time use cases — spot GPU instances cut cost 60–70% vs on-demand.

Pair with [multimodal document understanding](https://blog.michaelsam94.com/multimodal-document-understanding/) when transcripts feed downstream extraction pipelines.

## Resources

- [OpenAI Whisper paper (arXiv)](https://arxiv.org/abs/2212.04356) — architecture and training details
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) — CTranslate2-accelerated inference
- [OpenAI Audio API reference](https://platform.openai.com/docs/guides/speech-to-text) — hosted transcription endpoints
- [Silero VAD](https://github.com/snakers4/silero-vad) — voice activity detection for chunking
- [Hugging Face distil-whisper](https://huggingface.co/distil-whisper) — distilled models for lower latency

## Production notes for LLM stacks

When `multimodal-audio-transcription-whisper` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `speech-to-text with whisper` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
