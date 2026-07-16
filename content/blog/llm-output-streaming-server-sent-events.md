---
title: "Streaming LLM Output with SSE"
slug: "llm-output-streaming-server-sent-events"
description: "Stream LLM responses with Server-Sent Events: FastAPI/Express patterns, token buffering, client reconnection, proxy timeouts, and UX that feels instant without fragile WebSockets."
datePublished: "2024-12-24"
dateModified: "2024-12-24"
tags: ["AI", "LLM", "Backend", "Web"]
keywords: "LLM streaming SSE, server-sent events LLM, stream OpenAI response, FastAPI SSE streaming, token streaming API"
faq:
  - q: "SSE vs WebSockets for LLM streaming — which should I use?"
    a: "SSE for one-way server-to-client token streaming — simpler, works through most proxies, auto-reconnects. WebSockets when you need bidirectional communication (user interrupts generation, sends messages over same connection). Most chat UIs only need SSE for the response stream and regular HTTP POST for user messages."
  - q: "How do I handle proxy and load balancer timeouts with SSE?"
    a: "Send periodic heartbeat comments (`: ping\\n\\n`) every 15–30 seconds to keep connections alive. Configure nginx/load balancer proxy_read_timeout above your max generation time. Disable response buffering on reverse proxies (`X-Accel-Buffering: no`). These three fixes resolve 90% of streaming disconnects."
  - q: "Should I stream raw tokens or buffered chunks to the client?"
    a: "Buffer into word or sentence chunks (30–80ms flush interval) rather than individual tokens. Token-level streaming flickers in UI and increases React re-render overhead. Chunk-level feels smooth and reduces client CPU. Send a final 'done' event with metadata (token count, citations)."
---

Users perceive a 3-second response as slow. The same response streaming visible text within 200ms feels fast — even if total generation time is identical. Streaming isn't a cosmetic feature; it's a latency perception hack that keeps users engaged instead of bouncing. Server-Sent Events (SSE) is the simplest reliable transport for one-way LLM token streams.

## SSE basics

SSE is HTTP with `Content-Type: text/event-stream`. Server pushes events; client listens via `EventSource`.

```
event: token
data: {"text": "Hello"}

event: token
data: {"text": " world"}

event: done
data: {"tokens": 42, "cost_usd": 0.001}
```

Each event: optional `event` type, `data` payload, double newline terminator.

## FastAPI implementation

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

async def generate_stream(prompt: str):
    yield "event: start\ndata: {}\n\n"
    buffer = ""
    async for chunk in llm_client.stream(prompt):
        buffer += chunk.text
        if should_flush(buffer):  # word boundary or 50ms elapsed
            payload = json.dumps({"text": buffer})
            yield f"event: token\ndata: {payload}\n\n"
            buffer = ""
        await asyncio.sleep(0)  # yield control
    if buffer:
        yield f"event: token\ndata: {json.dumps({'text': buffer})}\n\n"
    yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return StreamingResponse(
        generate_stream(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

## Client-side (React)

```typescript
async function streamChat(message: string, onChunk: (text: string) => void) {
  const response = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = parseSSE(buffer);
    for (const event of events.complete) {
      if (event.type === "token") onChunk(JSON.parse(event.data).text);
    }
    buffer = events.remainder;
  }
}
```

Use `fetch` + `ReadableStream`, not `EventSource` — EventSource only supports GET.

## Heartbeats and timeouts

```python
async def generate_with_heartbeat(prompt: str):
    queue = asyncio.Queue()
    asyncio.create_task(producer(prompt, queue))
    last_event = time.monotonic()
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
            if event is None:
                break
            yield event
            last_event = time.monotonic()
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"  # SSE comment, ignored by client
```

Nginx default `proxy_read_timeout` is 60s. Heartbeats prevent silent disconnects on long generations.

## Error handling mid-stream

Errors during generation must reach the client:

```python
try:
    async for chunk in llm_client.stream(prompt):
        yield format_event("token", chunk)
except LLMError as e:
    yield format_event("error", {"message": str(e), "code": e.code})
finally:
    yield format_event("done", {"status": "error" if failed else "complete"})
```

Client shows partial response + error banner — better than an abrupt disconnect.

## Cancellation

User clicks "Stop generating":

```python
@app.post("/chat/stream")
async def chat_stream(request: Request):
    cancel_event = asyncio.Event()

    async def stream():
        try:
            async for event in generate(request.message, cancel_event):
                if await request.is_disconnected():
                    cancel_event.set()
                    break
                yield event
        finally:
            cancel_event.set()

    return StreamingResponse(stream(), media_type="text/event-stream")
```

Abort the upstream LLM call on disconnect to stop burning tokens.

## Structured streaming

For JSON output, stream partial fields:

```python
# Stream markdown text for display
yield format_event("token", {"text": chunk})

# After complete, send structured metadata
yield format_event("metadata", {
    "citations": citations,
    "confidence": 0.92,
})
```

Don't try to stream-parse JSON on the client — stream display text, deliver structure in the final event.

## Express.js equivalent

```javascript
app.post("/chat/stream", async (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("X-Accel-Buffering", "no");

  const stream = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: req.body.messages,
    stream: true,
  });

  for await (const chunk of stream) {
    const text = chunk.choices[0]?.delta?.content || "";
    if (text) res.write(`event: token\ndata: ${JSON.stringify({ text })}\n\n`);
  }
  res.write(`event: done\ndata: {"status":"complete"}\n\n`);
  res.end();
});
```

Send heartbeat comments in SSE stream every 15s — proxies and load balancers drop idle connections without keepalive data.

## SSE event format for LLM streams

```
event: token
data: {"text": "Hello"}

event: done
data: {"usage": {"input_tokens": 10, "output_tokens": 5}}
```

Set headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`. Proxy timeout must exceed max generation time.

## Common production mistakes

Teams get output streaming server sent events wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around output streaming server sent events break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When output streaming server sent events misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MDN Server-Sent Events documentation](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenAI streaming API guide](https://platform.openai.com/docs/api-reference/streaming)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [Anthropic streaming messages](https://docs.anthropic.com/en/api/messages-streaming)
- [nginx proxy buffering for SSE](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)
