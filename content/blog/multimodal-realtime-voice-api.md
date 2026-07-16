---
title: "Real-Time Voice with the Realtime API"
slug: "multimodal-realtime-voice-api"
description: "Build low-latency voice agents with OpenAI's Realtime API: WebSocket sessions, audio streaming, turn detection, function calling, and interruption handling."
datePublished: "2025-08-13"
dateModified: "2025-08-13"
tags: ["AI", "Audio", "API", "Real-time"]
keywords: "OpenAI Realtime API, voice agent, real-time speech AI, WebSocket audio streaming, conversational AI voice, speech-to-speech"
faq:
  - q: "How is the Realtime API different from chaining Whisper and TTS?"
    a: "The Realtime API processes audio in a single speech-to-speech model over a persistent WebSocket, cutting end-to-end latency to 300–800 ms. A Whisper → LLM → TTS pipeline typically adds 2–5 seconds per turn due to serial API calls and buffering."
  - q: "How do I handle user interruptions (barge-in)?"
    a: "Enable server-side voice activity detection or send client-side VAD events. When the user speaks during model output, send response.cancel to stop audio generation immediately. Buffer only 200–300 ms of playback on the client for smooth cutoffs."
  - q: "Can I use function calling with voice agents?"
    a: "Yes. Define tools in the session configuration. The model emits function_call events during conversation; execute the tool server-side and return results via conversation.item.create before requesting the next response."
---

Phone support bots that wait three seconds after you stop talking feel broken. Users expect the rhythm of human conversation—overlap, interruption, quick acknowledgments. OpenAI's Realtime API maintains a persistent WebSocket where audio flows in both directions, processed by a single multimodal model. You build a voice agent without stitching together separate STT, chat, and TTS services.

## Session lifecycle

```
Client                    Realtime API (wss)
  |--- session.update ---->|  (configure voice, tools, VAD)
  |--- input_audio_buffer ->|  (stream PCM16 chunks)
  |<-- response.audio -----|  (stream output audio)
  |--- response.cancel --->|  (on user interrupt)
  |--- session end -------->|
```

Audio format: 24 kHz PCM16 mono, base64-encoded in JSON events. Chunk size: 20–100 ms of audio per message balances latency and overhead.

## Server-side session setup

Never expose your API key in browser JavaScript. Proxy through your backend:

```python
# FastAPI endpoint that upgrades to WebSocket proxy
from fastapi import WebSocket
import websockets
import os

@app.websocket("/voice")
async def voice_proxy(client_ws: WebSocket):
    await client_ws.accept()
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
        extra_headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
    ) as api_ws:
        await api_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {"type": "server_vad"},
                "instructions": "You are a concise support agent for Acme Cloud.",
            },
        }))
        await asyncio.gather(
            relay(client_ws, api_ws),
            relay(api_ws, client_ws),
        )
```

## Client audio capture

```javascript
const SAMPLE_RATE = 24000;
const ws = new WebSocket("wss://app.example.com/voice");

const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
const source = ctx.createMediaStreamSource(stream);
const processor = ctx.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
  const pcm = float32ToInt16(e.inputBuffer.getChannelData(0));
  ws.send(JSON.stringify({
    type: "input_audio_buffer.append",
    audio: btoa(String.fromCharCode(...new Uint8Array(pcm.buffer))),
  }));
};
source.connect(processor);
processor.connect(ctx.destination);
```

Commit audio when VAD detects end of speech, or let server VAD handle turn boundaries automatically.

## Function calling in voice

```json
{
  "type": "session.update",
  "session": {
    "tools": [{
      "type": "function",
      "name": "check_order_status",
      "description": "Look up order by ID",
      "parameters": {
        "type": "object",
        "properties": {
          "order_id": { "type": "string" }
        },
        "required": ["order_id"]
      }
    }],
    "tool_choice": "auto"
  }
}
```

On `response.function_call_arguments.done`, execute the function and inject the result:

```json
{
  "type": "conversation.item.create",
  "item": {
    "type": "function_call_output",
    "call_id": "call_abc",
    "output": "{\"status\": \"shipped\", \"eta\": \"2025-08-15\"}"
  }
}
```

Then send `response.create` to let the model speak the answer.

## Interruption handling

When `input_audio_buffer.speech_started` fires while audio plays:

```javascript
ws.send(JSON.stringify({ type: "response.cancel" }));
audioQueue.clear();
```

On the client, maintain a short playback buffer. Canceling within 300 ms of detected speech sounds natural; longer delays feel like the bot is ignoring the user.

## Latency budget

| Stage | Target |
|-------|--------|
| Mic capture → WebSocket | 20–50 ms |
| Server VAD end-of-turn | 300–500 ms |
| Model inference + first audio | 200–400 ms |
| Playback start | 50 ms |
| **Total perceived** | **~600–1000 ms** |

Log `response.audio_transcript.done` timestamps against `input_audio_buffer.speech_stopped` to measure your actual turn latency.

## Cost and limits

Realtime API bills per audio token (input and output). A 5-minute conversation costs roughly $0.30–$0.60 depending on model. Set `max_response_output_tokens` to prevent runaway monologues. Monitor session duration and implement idle timeouts (60 seconds of silence closes the session).

## WebSocket session management

Production Realtime API requires robust session lifecycle:

```javascript
class RealtimeSession {
  constructor(apiKey) {
    this.ws = new WebSocket("wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
      ["realtime", `openai-insecure-api-key.${apiKey}`]);
    this.audioQueue = [];
    this.isResponding = false;
  }

  configure() {
    this.ws.send(JSON.stringify({
      type: "session.update",
      session: {
        turn_detection: { type: "server_vad", silence_duration_ms: 500 },
        input_audio_format: "pcm16",
        output_audio_format: "pcm16",
        max_response_output_tokens: 512,
        instructions: "You are a helpful voice assistant. Be concise.",
      }
    }));
  }

  sendAudio(pcm16Buffer) {
    this.ws.send(JSON.stringify({
      type: "input_audio_buffer.append",
      audio: btoa(String.fromCharCode(...new Uint8Array(pcm16Buffer))),
    }));
  }
}
```

Always configure session before sending audio. Server VAD handles turn detection — don't implement client-side VAD unless latency requires it.

## Audio format and buffering

Realtime API expects PCM16 at 24kHz mono:

```javascript
// Capture from microphone
const audioContext = new AudioContext({ sampleRate: 24000 });
const processor = audioContext.createScriptProcessor(4096, 1, 1);
processor.onaudioprocess = (e) => {
  const pcm16 = float32ToPcm16(e.inputBuffer.getChannelData(0));
  session.sendAudio(pcm16);
};

// Playback: buffer 100ms before starting to avoid underruns
const PLAYBACK_BUFFER_MS = 100;
function onAudioDelta(base64Audio) {
  audioQueue.push(decodePcm16(base64Audio));
  if (!isPlaying && bufferDuration() >= PLAYBACK_BUFFER_MS) startPlayback();
}
```

Mismatch in sample rate causes pitch/speed distortion. Resample in browser if mic doesn't support 24kHz natively.

## Function calling in voice sessions

Extend voice agents with tool use:

```javascript
// Register tools in session config
session: {
  tools: [{
    type: "function",
    name: "lookup_order",
    description: "Look up order status by order ID",
    parameters: { type: "object", properties: { order_id: { type: "string" } } }
  }]
}

// Handle tool calls
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === "response.function_call_arguments.done") {
    const result = await lookupOrder(msg.arguments.order_id);
    ws.send(JSON.stringify({
      type: "conversation.item.create",
      item: { type: "function_call_output", call_id: msg.call_id, output: JSON.stringify(result) }
    }));
    ws.send(JSON.stringify({ type: "response.create" }));
  }
};
```

Voice + tools enables transactional voice agents (order lookup, appointment booking) — not just conversational.

## Failure modes

- **No barge-in handling** — user speaks while bot talks; feels ignored
- **Wrong audio sample rate** — pitch distortion; validate 24kHz PCM16
- **No idle timeout** — session runs indefinitely; cost accumulates
- **WebSocket not reconnected on drop** — session lost mid-conversation
- **max_response_output_tokens not set** — runaway monologue; unexpected cost

## Production checklist

- Server VAD configured (silence_duration_ms: 500)
- Barge-in: response.cancel on speech_started during playback
- Idle timeout: close session after 60s silence
- Audio format: PCM16 24kHz mono validated end-to-end
- max_response_output_tokens set (512 for concise, 1024 for detailed)
- Session duration and cost monitored per conversation

## Resources

- [OpenAI Realtime API guide](https://platform.openai.com/docs/guides/realtime) — event reference and session config
- [OpenAI Realtime WebSocket protocol](https://platform.openai.com/docs/api-reference/realtime) — full event type listing
- [Web Audio API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API) — browser audio capture and playback
- [WebRTC VAD alternatives](https://github.com/wiseman/py-webrtcvad) — client-side speech detection
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/) — proxy pattern for browser clients
