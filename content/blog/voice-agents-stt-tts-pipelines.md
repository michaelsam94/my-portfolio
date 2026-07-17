---
title: "Voice Agents: Building STT and TTS Pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: "How to build a real-time voice agent: streaming STT, LLM turn-taking, TTS, and the latency budget, VAD, and barge-in details that make it feel like a conversation."
datePublished: "2026-02-12"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "speech to text, text to speech, voice agents, STT TTS pipeline, voice AI, streaming ASR, voice activity detection"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---

title: "Voice Agents: Building STT and TTS Pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: "How to build a real-time voice agent: streaming STT, LLM turn-taking, TTS, and the latency budget, VAD, and barge-in details that make it feel like a conversation."
datePublished: "2026-02-12"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "speech to text, text to speech, voice agents, STT TTS pipeline, voice AI, streaming ASR, voice activity detection"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "voice-agents-stt-tts-pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "voice-agents-stt-tts-pipelines"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "voice-agents-stt-tts-pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "voice-agents-stt-tts-pipelines"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "voice-agents-stt-tts-pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "voice-agents-stt-tts-pipelines"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "Voice Agents: Building STT and TTS Pipelines"
slug: "voice-agents-stt-tts-pipelines"
description: "How to build a real-time voice agent: streaming STT, LLM turn-taking, TTS, and the latency budget, VAD, and barge-in details that make it feel like a conversation."
datePublished: "2026-02-12"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "speech to text, text to speech, voice agents, STT TTS pipeline, voice AI, streaming ASR, voice activity detection"
faq:
  - q: "What is the main production risk with voice agents stt tts pipelines?"
    a: "Teams ship without field measurement—voice agents stt tts pipelines failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize voice agents stt tts pipelines?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate voice agents stt tts pipelines changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

A voice agent that feels natural is mostly an exercise in hiding latency. The models — speech-to-text, an LLM, text-to-speech — are the easy part; each has a good hosted option. The hard part is stitching them into a loop that responds in under a second, lets the user interrupt, and doesn't talk over background noise. Get the plumbing wrong and even great models produce a stilted, walkie-talkie experience.

The core architecture almost everyone converges on is a **cascaded streaming pipeline**: stream audio into STT, stream partial transcripts into an LLM, stream the LLM's tokens into TTS, and stream synthesized audio back — all overlapping in time. Below is how each stage works and the specific details that decide whether it feels like a conversation or a phone tree.

## The latency budget is the whole design

Humans read conversational timing precisely. A gap over ~1 second after you stop talking feels like the other side is confused. So the target is roughly 500-800ms from end-of-user-speech to start-of-agent-speech, and that budget is tight:

| Stage | Rough budget |
|---|---|
| Endpointing (detect user stopped) | 100-300ms |
| STT final transcript | overlapped, ~100ms after end |
| LLM time-to-first-token | 200-500ms |
| TTS time-to-first-audio | 100-300ms |
| Network + jitter buffer | 50-150ms |

These don't add up naively because you overlap them. The trick is to start the next stage on *partial* output of the previous one, not wait for completion.

## Streaming, not request/response

The naive version records the whole utterance, transcribes it, sends the full text to the LLM, waits for the full response, synthesizes it, and plays it. Every stage waits for the previous to finish, and the latency stacks to several seconds. Unusable.

The streaming version feeds each stage continuously:

```python
# Conceptual overlap of the pipeline
async def run_turn(mic_stream):
    async for partial in stt.stream(mic_stream):      # interim transcripts
        if partial.is_final:
            break
    # LLM starts as soon as we have the final (or a confident partial)
    async for token in llm.stream(build_prompt(partial.text)):
        tts.feed(token)                                # push tokens as they arrive
    async for audio_chunk in tts.stream():
        speaker.play(audio_chunk)                      # play first audio before LLM finishes
```

The key line is `tts.feed(token)` — sentence-level chunking of the LLM output into the TTS engine so audio starts playing while the LLM is still generating the rest of the answer. First audio out the door is what the user perceives as responsiveness.

## Endpointing and VAD: knowing when it's your turn

Voice Activity Detection (VAD) tells you when the user is speaking; endpointing tells you when they've *finished a turn*. These are different and both matter.

A VAD like Silero runs cheaply on-device and gates the audio you send to STT — no point transcribing silence, and it saves money on per-second STT billing. Endpointing is harder: end a turn too eagerly and you interrupt someone who paused mid-thought; too late and you add dead air. A practical approach is a short silence timer (e.g. 500-700ms of silence) combined with the STT provider's own endpoint signal, tuned to your domain. Support agents who read long addresses need a more patient endpointer than a quick-command assistant.

## Barge-in: let people interrupt

Nothing makes a voice agent feel more robotic than being unable to interrupt it. Barge-in is table stakes. The mechanics:

1. Keep the mic open and VAD running *while TTS is playing*.
2. When VAD detects the user speaking over the agent, immediately stop audio playback.
3. Discard the rest of the queued TTS and, usually, cancel the in-flight LLM generation.
4. Treat the interruption as a new turn.

The subtlety is echo: the microphone hears the agent's own voice from the speaker. Without acoustic echo cancellation (AEC), your VAD triggers on the agent itself and it interrupts its own sentence. On phones you get AEC from the platform audio stack; in a browser, `getUserMedia` with `echoCancellation: true`; on custom hardware you own this problem. This is the same class of real-time, hostile-environment plumbing I've dealt with in [WebSocket architecture at scale](https://blog.michaelsam94.com/websocket-architecture-at-scale/) — the models are new, the systems discipline isn't.

## Cascaded vs. speech-to-speech

Newer native speech-to-speech models (audio in, audio out, no text in the middle) offer lower latency and can carry tone, laughter, and interruptions more gracefully. But they trade away control: text-based tool calling is cleaner in a cascade, you can log and moderate the transcript, and you can swap any single component. For most production agents — especially anything doing [function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/) against real systems — I still start with a cascaded pipeline and reach for speech-to-speech only when the interaction quality genuinely demands it.

## Details that separate demo from product

- **Punctuation and formatting** from STT matter for the LLM's comprehension and for TTS prosody. Use models that emit punctuation.
- **Filler and thinking sounds.** A short "let me check that" while a tool call runs beats dead silence. Pre-synthesize a few fillers.
- **Tool-call latency.** If the LLM calls a slow backend, the user hears a gap. Speak an acknowledgment first, then the result.
- **Numbers, dates, and units** need normalization for TTS — "$19.99" should be read as money, not characters.
- **Graceful degradation** on poor networks: buffer, and have a fallback message rather than a frozen agent when a stage times out. Flaky mobile networks are the norm, not the exception — see [handling flaky networks on mobile](https://blog.michaelsam94.com/handling-flaky-networks-mobile/).

Build it as a streaming, overlapped pipeline with VAD, endpointing, barge-in, and echo cancellation treated as first-class, and the models will do the rest. The engineering that makes voice feel human is almost entirely in the timing.

## Latency breakdown instrumentation

Log structured timestamps per session:

```json
{
  "utterance_end": 1710000000100,
  "stt_final": 1710000000250,
  "llm_first_token": 1710000000450,
  "tts_first_byte": 1710000000520,
  "audio_play_start": 1710000000580
}
```

Aggregate p50/p95 per stage weekly. Teams optimize LLM while STT dominates—data prevents misfocus.

## Multi-language and code-switching

STT models vary by locale—route by user language setting, not browser default alone. Code-switching (English product terms in Hindi sentences) challenges monolingual models; choose STT with multilingual training or accept higher error rate with confirmation prompts ("Did you say X?").

TTS voice selection affects brand—cache generated audio for fixed system phrases (greeting, error messages) to skip synthesis latency on every session open.

## Barge-in and half-duplex

Users interrupt TTS playback — detect VAD during playback and cancel TTS stream. Half-duplex without barge-in feels like phone tree; full-duplex needs echo cancellation. Log barge-in rate — high rate may mean TTS too slow or prompts too long.

## SSML and prosody for brand voice

Plain TTS sounds robotic on error messages — SSML breaks and emphasis for critical phrases. Cache SSML templates for fixed system strings to skip synthesis latency on every session open.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [OpenAI — Realtime API](https://platform.openai.com/docs/guides/realtime)
- [Deepgram — Streaming speech-to-text docs](https://developers.deepgram.com/docs)
- [ElevenLabs — Text-to-speech docs](https://elevenlabs.io/docs)
- [Silero VAD (GitHub)](https://github.com/snakers4/silero-vad)
- [LiveKit Agents framework](https://docs.livekit.io/agents/)
- [WebRTC — Official site](https://webrtc.org/)
