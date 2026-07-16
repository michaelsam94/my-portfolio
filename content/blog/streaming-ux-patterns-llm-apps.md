---
title: "Streaming UX Patterns for LLM Apps"
slug: "streaming-ux-patterns-llm-apps"
description: "Streaming UX patterns for LLM apps: token streaming with SSE, handling tool calls and errors mid-stream, and the details that make AI feel fast, not flaky."
datePublished: "2026-03-31"
dateModified: "2026-03-31"
tags: ["LLM", "UX", "Frontend"]
keywords: "LLM streaming UX, token streaming, SSE, streaming UI, optimistic UI LLM, chat interface patterns"
faq:
  - q: "What are streaming UX patterns for LLM apps?"
    a: "They are the interaction and frontend techniques for displaying a model's output as it is generated, token by token, rather than waiting for the full response. This includes transport choices like server-sent events, showing intermediate states such as tool calls and reasoning, and gracefully handling cancellation and mid-stream errors. The goal is to make the app feel responsive when the underlying model may take many seconds to finish."
  - q: "Why stream LLM responses instead of waiting?"
    a: "Because time-to-first-token is far shorter than time-to-full-response, and users perceive the app as fast the moment text starts appearing. A ten-second full response feels broken, while the same response streaming from second one feels alive and lets users start reading and even interrupt early. Streaming turns unavoidable latency into a tolerable, even engaging, experience."
  - q: "What transport should I use for LLM streaming?"
    a: "Server-sent events over HTTP is the default for one-directional token streaming because it is simple, works over standard HTTP, and auto-reconnects. Use WebSockets when you need full duplex, such as live voice or collaborative sessions where the client streams data up while the model streams down. Plain chunked HTTP responses also work if you control both ends and want minimal machinery."
---

An LLM that takes eight seconds to answer feels broken if the screen sits blank, and perfectly fine if words start flowing at second one. That gap is entirely a UX problem, and streaming UX patterns are how you solve it: rendering the model's output incrementally as it's generated, surfacing intermediate states like tool calls, and handling interruption and failure without the interface freezing. The model's latency is mostly fixed; how it *feels* is yours to design.

I've built enough chat and assistant UIs to believe the streaming layer is where a lot of "this AI product feels premium" actually comes from. It's not the model — it's whether the interface respects the user's attention while the model thinks. Here's what goes into doing it well.

## Time-to-first-token is the metric that matters

Users don't experience your average latency; they experience the wait before *anything* happens. A response that takes 9 seconds total but shows its first token at 400ms feels dramatically faster than one that appears fully formed at 6 seconds. So optimize for time-to-first-token (TTFT) relentlessly, and stream everything after it.

This reframes performance work. Prompt bloat, a slow retrieval step, or a cold model all push TTFT out and cost you the perception of speed even if total generation is quick. Measure TTFT as a first-class metric alongside total latency, and treat a regression in it as seriously as an error rate spike.

## SSE is the right default transport

For streaming tokens from server to browser, server-sent events (SSE) is the pragmatic default. It rides ordinary HTTP, gives you a simple event stream, and reconnects automatically. The server flushes chunks as the model produces them; the client appends them to the DOM.

```typescript
const res = await fetch("/api/chat", {
  method: "POST",
  body: JSON.stringify({ messages }),
});
const reader = res.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  for (const line of decoder.decode(value).split("\n")) {
    if (!line.startsWith("data: ")) continue;
    const payload = line.slice(6);
    if (payload === "[DONE]") return;
    const { delta } = JSON.parse(payload);
    appendToBubble(delta);              // paint immediately
  }
}
```

Reach for WebSockets only when you genuinely need full duplex — live voice, collaborative editing, a session where the client streams audio up while the model streams tokens down. That bidirectional case is exactly the shape of [voice agents with STT and TTS pipelines](https://blog.michaelsam94.com/voice-agents-stt-tts-pipelines/), where SSE alone isn't enough. For text chat, SSE keeps the stack simpler and the reconnection story free.

## Show the machine thinking

Modern LLM apps don't just emit text — they call tools, retrieve documents, and sometimes reason in visible steps. Streaming only the final prose wastes the chance to make the wait *informative*. The states worth surfacing:

- **Thinking / retrieving.** A lightweight indicator while the model plans or fetches context, ideally naming what it's doing ("Searching your documents…") rather than a generic spinner.
- **Tool calls in flight.** When the model calls a tool, show it: "Looking up order #4821." This both fills dead time and builds trust by making the system legible.
- **Streaming tokens.** The main event — text appearing as generated.
- **Done, with affordances.** Copy, regenerate, and feedback controls appearing cleanly at completion.

The trap I keep seeing is treating everything before the final text as a black-box spinner. Users tolerate waiting far better when they can see *what* they're waiting for. If your app streams structured output — JSON, a form, function arguments — you also have to decide how to render partial structure, which ties into how you design [structured outputs and function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/); a half-streamed JSON object should degrade to a sensible loading state, not flash malformed content.

## Handle cancellation, errors, and reconnection as first-class

Happy-path streaming is easy. The reasons streaming UIs feel flaky are all on the unhappy paths.

**Cancellation.** Let users stop a runaway generation. Wire a stop button to an `AbortController` and actually cancel the upstream model request server-side — not just hide the tokens — so you stop paying for output nobody wants.

**Mid-stream errors.** The model can fail *after* emitting half a response — a timeout, a content filter, a dropped upstream connection. Decide the behavior deliberately: keep the partial text and append a clear "response interrupted, retry?" affordance, rather than blanking what the user was already reading. Never let a mid-stream error erase visible content.

**Reconnection.** Networks drop, especially on mobile. SSE reconnects, but you need server-side handling to resume or cleanly restart rather than replaying a duplicate stream. If you can, make the generation idempotent by request id so a reconnect doesn't double-charge or double-render.

## Small details that separate good from janky

The polish lives in a handful of interaction choices:

| Detail | Why it matters |
| --- | --- |
| Smooth token rendering | Batching paints per animation frame avoids jittery reflow on fast streams |
| Auto-scroll with escape hatch | Follow the stream, but stop auto-scrolling the instant the user scrolls up |
| Markdown streamed safely | Parse incrementally; don't render half-open code fences or broken tables |
| Debounced layout | Don't reflow the whole page on every token; contain updates to the bubble |
| Stable input during stream | Let users type their next message while the current one streams |

The auto-scroll one bites everybody: naive "always scroll to bottom" fights the user the moment they try to read something above, which is infuriating. Detect upward scroll intent and yield control, offering a "jump to latest" button instead.

Streaming Markdown safely is the other classic footgun. A code block streams in as an unterminated ` ``` ` for a second or two; a naive renderer will flash a broken, unclosed block. Buffer until fences balance, or use a parser built to tolerate partial input.

## Streaming is a UX contract, not a feature flag

The mistake is treating streaming as "we turned on `stream: true`." Done well, it's a contract with the user: *something is always happening, you can see what, you can stop it, and nothing you've read will vanish.* That contract is what makes a slow model feel like a fast product.

My advice: instrument TTFT, make intermediate states legible, and spend most of your engineering effort on cancellation, errors, and reconnection — because that's where perceived reliability is won or lost. The token-by-token typing effect is the easy 20%. The other 80% is what users feel without being able to name it.

## Resources

- [MDN — Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [WHATWG — Streams standard](https://streams.spec.whatwg.org/)
- [Vercel AI SDK — streaming documentation](https://sdk.vercel.ai/docs)
- [OpenAI — streaming API responses](https://platform.openai.com/docs/api-reference/streaming)
- [MDN — AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
