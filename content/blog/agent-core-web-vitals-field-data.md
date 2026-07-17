---
title: "Core Web Vitals Field Data for Agent-Powered Products"
slug: "agent-core-web-vitals-field-data"
description: "Measure and improve LCP, INP, and CLS on real user sessions for streaming agent UIs — CrUX vs RUM, attribution, AI-specific regressions, and performance budgets in CI."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["AI Agents", "Performance", "Core Web Vitals", "Frontend"]
keywords: "Core Web Vitals field data, INP agent UI, LCP streaming chat, CrUX RUM, web vitals agent dashboard, performance monitoring"
faq:
  - q: "Why is lab Lighthouse insufficient for agent chat products?"
    a: "Lab tests use clean profiles, warm caches, and no concurrent streaming tokens or WebSocket backpressure. Agent UIs regress from long tasks during markdown rendering, layout shifts when tool cards mount, and INP spikes during input while tokens stream — only field data captures that mix."
  - q: "What is a realistic INP target for an agent input box?"
    a: "Aim for INP p75 under 200ms on field data for the chat input element. Streaming output can run on separate threads or requestAnimationFrame batches, but the send button and textarea must stay responsive — users type during generation."
  - q: "How do streaming tokens affect LCP?"
    a: "If the largest paint is the first assistant message bubble, LCP may fire late on slow models — sometimes after FCP by seconds. Track element-level LCP attribution; consider skeleton placeholders with fixed dimensions so LCP lands on stable chrome, not growing message height."
  - q: "Should agent telemetry include CrUX data or only custom RUM?"
    a: "Use both. CrUX gives competitive baseline and Search Console integration at origin level. Custom RUM adds route-level, tenant-level, and interaction attribution (which tool renderer caused CLS) that CrUX cannot provide."
---

Google Search Console flagged your marketing site as "needs improvement" on INP the same week product shipped streaming agent chat, markdown tool renderers, and a lazy-loaded code editor. Lab Lighthouse still scores 94. Real users on mid-tier Android wait 800ms for the send button to acknowledge a tap. **Core Web Vitals field data** — measurements from actual sessions, not your MacBook on gigabit — is the only honest scorecard for agent-powered web products.

Agent interfaces create performance patterns static sites never see: unbounded DOM growth from token streaming, layout shifts when tool cards hydrate, long main-thread tasks from syntax highlighting, and INP contention when users type while output renders. This post covers how to collect field vitals correctly, attribute regressions to agent-specific causes, and set budgets that survive model latency masquerading as frontend slowness.

## The three vitals and how agents break them

| Vital | Measures | Agent UI risk |
|-------|----------|---------------|
| **LCP** | Largest contentful paint | First message bubble, hero demo chat, large tool output panel |
| **INP** | Interaction to next paint (p75) | Send button, stop generation, copy code, expand tool trace |
| **CLS** | Cumulative layout shift | Streaming markdown, lazy images in RAG citations, font swap |

Field data aggregates **p75 over 28 days** of real Chrome sessions (CrUX) or your RUM pipeline. Lab scores are diagnostics; field data is accountability.

## CrUX vs your own RUM

**Chrome User Experience Report (CrUX)** is free, origin-level, and powers Search ranking signals. Limitations:

- No URL-level detail below popular origins
- No custom dimensions (tenant, agent version, model tier)
- 28-day rolling window — slow to confirm fixes

**Real User Monitoring (RUM)** with `web-vitals` library fills gaps:

```typescript
// lib/vitals.ts
import { onLCP, onINP, onCLS, onFCP, type Metric } from "web-vitals";

type VitalsPayload = {
  name: string;
  value: number;
  rating: "good" | "needs-improvement" | "poor";
  id: string;
  route: string;
  agentVersion: string;
  navigationType: string;
  attribution?: Record<string, unknown>;
};

function sendToAnalytics(metric: Metric) {
  const body: VitalsPayload = {
    name: metric.name,
    value: metric.value,
    rating: metric.rating,
    id: metric.id,
    route: window.location.pathname,
    agentVersion: window.__AGENT_CONFIG__?.version ?? "unknown",
    navigationType: metric.navigationType ?? "unknown",
    attribution: "attribution" in metric ? (metric as any).attribution : undefined,
  };

  navigator.sendBeacon("/api/rum/vitals", JSON.stringify(body));
}

export function initVitals() {
  onLCP(sendToAnalytics, { reportAllChanges: false });
  onINP(sendToAnalytics, { reportAllChanges: true });
  onCLS(sendToAnalytics, { reportAllChanges: true });
  onFCP(sendToAnalytics);
}
```

Enable **`reportAllChanges` for INP and CLS** during development; production can sample 10–30% of sessions to control volume.

Correlate RUM with CrUX weekly. If RUM p75 INP is 180ms but CrUX shows "poor," your RUM sample may skew desktop — weight by device class.

## INP: the agent chat bottleneck

INP replaced FID because modern apps have long tasks after input — exactly what token streaming causes.

Common agent INP failures:

1. **Main thread blocked during stream processing** — parsing markdown on every chunk
2. **Synchronous JSON.stringify on large tool payloads** for debug panels
3. **Re-render entire message list** instead of appending tail
4. **Heavy React reconciliation** when message array grows unbounded

Fix pattern — **incremental render pipeline**:

```typescript
// hooks/useStreamingMessage.ts
import { useRef, useCallback } from "react";

export function useStreamingMessage() {
  const bufferRef = useRef("");
  const rafRef = useRef<number | null>(null);

  const appendToken = useCallback((token: string, onFlush: (text: string) => void) => {
    bufferRef.current += token;
    if (rafRef.current !== null) return;

    rafRef.current = requestAnimationFrame(() => {
      onFlush(bufferRef.current);
      rafRef.current = null;
    });
  }, []);

  return { appendToken };
}
```

Batch token DOM updates to one frame. Measure INP on the send button with Performance API:

```typescript
// Mark interaction start on pointerdown, measure to next paint
sendButton.addEventListener("pointerdown", () => {
  performance.mark("send-start");
});

// After handler completes and paints
performance.measure("send-inp", "send-start");
```

**Target:** INP p75 < 200ms field; investigate any agent route above 500ms.

Use **`scheduler.postTask`** or Web Workers for markdown parsing if tokens arrive faster than 60fps consumption.

## LCP when content is model-generated

Static LCP advice ("optimize hero image") misses agent UIs where LCP element is dynamic text.

Strategies:

**Stable skeleton with fixed height.** Render chat shell and placeholder bubble before first token. LCP anchors on shell, not growing content.

```tsx
<div className="message assistant" style={{ minHeight: 120 }}>
  {!firstTokenReceived && <Skeleton lines={3} />}
  {content}
</div>
```

**Element timing API** — mark when assistant message mounts:

```typescript
onLCP((metric) => {
  const lcpElement = metric.entries?.[0]?.element;
  console.log("LCP element:", lcpElement?.className, metric.value);
});
```

If LCP is consistently the assistant bubble, separate **Time to First Token (TTFT)** as a product metric — model latency — from **Time to Stable Layout**, a frontend metric.

Do not conflate "model took 3s" with "frontend LCP failed." Track both on the same dashboard with different labels.

## CLS from tool renderers and citations

Agent messages embed unpredictable content: images from RAG, code blocks with async highlighting, expandable tool traces. Each injection shifts layout.

CLS prevention checklist:

- **Width/height on citation thumbnails** — or fixed aspect-ratio containers
- **Reserve space for code blocks** — min-height from line count estimate
- **`font-display: optional`** or preloaded fonts for monospace code
- **Avoid inserting banners above existing messages** — toast notifications steal space

```css
.tool-card {
  content-visibility: auto;
  contain-intrinsic-size: 0 200px; /* reserve approximate height */
}

.citation-thumb {
  aspect-ratio: 16 / 9;
  width: 100%;
  max-width: 320px;
  object-fit: cover;
}
```

Measure CLS attribution in web-vitals v4+ — identify which tool renderer (`code`, `chart`, `table`) correlates with shift events.

## Separating model latency from frontend vitals

Agent products confuse teams because slow **feels** uniform:

| Signal | Source | Owner |
|--------|--------|-------|
| TTFT | API stream TTFB | Model / backend |
| Token rate | API stream | Model / backend |
| Stream render FPS | RUM custom | Frontend |
| INP on input | web-vitals | Frontend |
| LCP element timing | web-vitals | Frontend + design |

```typescript
// Custom metric: stream render health
performance.mark("stream-first-chunk");
// ... on first rAF flush after chunk
performance.mark("stream-first-paint");
performance.measure("stream-render-delay", "stream-first-chunk", "stream-first-paint");
```

If `stream-render-delay` p95 > 100ms while TTFT is fine, optimize frontend batching — not the model route.

## Field data collection hygiene

**Sample wisely.** 100% RUM on high-traffic agent routes is expensive. Stratified sample: 20% overall, 100% for new agent version first 48 hours.

**Segment reports** by:

- `deviceMemory` / mobile vs desktop
- `agentVersion` (feature flags)
- `route` (/chat, /embed, /dashboard)
- `streamEnabled` boolean
- Geographic region (latency to API region)

**Privacy.** Vitals payloads must not include message content. IDs only.

**Bot filtering.** CrUX excludes bots; your RUM may not. Filter headless user agents from INP aggregates.

## Performance budgets in CI

Lab tests still gate regressions before deploy — they just do not replace field data.

```javascript
// lighthouse-ci assert (agent chat route)
module.exports = {
  ci: {
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.75 }],
        "interactive": ["error", { maxNumericValue: 4000 }],
        "total-blocking-time": ["error", { maxNumericValue: 300 }],
      },
    },
  },
};
```

Add **custom lab scenario**: load `/agent/chat`, simulate 500-token stream via mocked SSE, measure long tasks > 50ms during stream.

Pair with **bundle budgets**:

```json
{
  "path": "dist/agent-chat-*.js",
  "maxSize": "180 kB"
}
```

Syntax highlighters and chart libraries blow budgets silently when added to tool renderers.

## CrUX API for dashboards

Pull origin-level history for executive reporting:

```python
# scripts/crux_fetch.py
import requests

API = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
params = {
    "origin": "https://app.example.com",
    "formFactor": "PHONE",
    "metrics": ["largest_contentful_paint", "interaction_to_next_paint", "cumulative_layout_shift"],
}

# Requires API key; returns p75 distribution and histogram
```

Compare phone vs desktop CrUX monthly. Agent power users on desktop hide mobile CLS disasters.

## Regression response playbook

When field INP crosses "needs improvement" threshold:

1. **Check deploy correlation** — agent version flag, new tool renderer
2. **Slice RUM attribution** — which interaction target (send, stop, copy)
3. **Long task profiler** — reproduce on Moto G4 equivalent device
4. **Stream off experiment** — if INP recovers, blame render path not input handler
5. **Rollback or hotfix** — feature flag off new renderer; confirm CrUX recovery in 28 days or faster via RUM

Document wins. "Reserved 200px for tool cards" is reusable knowledge.

## The takeaway

Core Web Vitals field data exposes what Lighthouse misses on agent UIs: interaction delay during streaming, layout shift from tool output, and LCP driven by dynamic content. Instrument with web-vitals RUM, attribute regressions to specific renderers and interactions, separate model TTFT from frontend render delay, and set CI budgets that include streaming scenarios. CrUX tells you if Google thinks you are slow; RUM tells you why and where — you need both to ship agent products that feel fast on real devices.

## Resources

- [web.dev — Core Web Vitals](https://web.dev/vitals/)
- [Chrome UX Report API documentation](https://developer.chrome.com/docs/crux/api)
- [web-vitals JavaScript library](https://github.com/GoogleChrome/web-vitals)
- [web.dev — Optimize INP](https://web.dev/articles/optimize-inp)
- [Search Console — Core Web Vitals report](https://support.google.com/webmasters/answer/9205520)
