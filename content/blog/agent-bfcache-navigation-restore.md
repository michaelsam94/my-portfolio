---
title: "AI Agents: Bfcache Navigation Restore"
slug: "agent-bfcache-navigation-restore"
description: "Back-forward cache restores agent chat pages instantly—but frozen WebSockets, stale SSE streams, and lost session state break streaming UIs unless you handle pageshow and pagehide correctly."
datePublished: "2026-05-27"
dateModified: "2026-05-27"
tags: ["AI", "Agent", "Bfcache"]
keywords: "bfcache, back-forward cache, pageshow persisted, pagehide, agent UI, WebSocket restore, SSE streaming, navigation API, SPA session recovery"
faq:
  - q: "What breaks in agent UIs when bfcache restores a page?"
    a: "WebSocket and EventSource connections are frozen or closed while the document is cached. In-flight streaming tokens stop updating, typing indicators hang, and tool-call status may show stale 'running' states. JavaScript timers and requestAnimationFrame pause until restore."
  - q: "How do I detect a bfcache restore versus a normal page load?"
    a: "Listen for the pageshow event and check event.persisted === true. Normal loads have persisted false. The Navigation API navigation.type === 'back_forward' corroborates in supporting browsers."
  - q: "Should agent apps disable bfcache to avoid complexity?"
    a: "Avoid blanket disable—it hurts Core Web Vitals and mobile UX. Instead, close unbufferable resources on pagehide, reconnect on pageshow persisted, and resync conversation state from the server. Use unload listeners sparingly; they can prevent bfcache eligibility."
  - q: "How do I measure bfcache impact on agent sessions?"
    a: "Use PerformanceNavigationTiming.type, Chrome's notRestoredReasons API, and custom RUM beacons on pageshow persisted. Track reconnect latency and duplicate-message rate after back navigation."
---
Users treat the browser back button as undo. In agent chat UIs, back navigation should return to the exact conversation—scroll position, partial assistant reply, tool status chips. Modern browsers deliver that via the **back-forward cache (bfcache)**: a frozen snapshot of the page in memory, restored in milliseconds without a network round trip.

For static content, bfcache is magic. For agent interfaces with open SSE streams, WebSocket heartbeats, and optimistic tool-call UI, bfcache is a **lifecycle edge** that breaks silently. The page looks correct; the stream died three navigations ago.

## Why agent pages fight bfcache eligibility

Browsers exclude pages from bfcache when they detect state that cannot be frozen—open IndexedDB transactions, active WebRTC, certain cache headers, or **`unload` handlers** (historically the biggest footgun).

Agent stacks commonly block eligibility accidentally:

- `beforeunload` prompts ("Leave chat?")
- `unload` closing WebSockets
- `Cache-Control: no-store` on HTML shell
- Service workers intercepting navigation without bfcache-aware logic
- Open `BroadcastChannel` without cleanup

Chrome exposes **`performance.getEntriesByType('navigation')[0].notRestoredReasons`** (origin trial / shipping in Chromium) listing why restore failed. Run this in RUM before deciding to disable bfcache globally.

## The lifecycle: pagehide, freeze, pageshow

When user navigates away, the browser may enter **pagehide** with `event.persisted === true`—the document might enter bfcache. While cached:

- Main thread JavaScript is paused
- Network connections may be suspended or terminated
- Timers do not fire

When user returns, **pageshow** fires with `event.persisted === true`. This is not a reload. `DOMContentLoaded` does not repeat. Your init code from first load does not re-run unless you branch on `persisted`.

```typescript
// app/bfcacheLifecycle.ts
type AgentSessionHandle = {
  reconnect(): Promise<void>;
  resyncFromServer(conversationId: string): Promise<void>;
};

let session: AgentSessionHandle | null = null;

window.addEventListener("pageshow", (event: PageTransitionEvent) => {
  if (!event.persisted) return;

  metrics.increment("agent.bfcache.restore");

  const conversationId = getConversationIdFromUrl();
  session?.reconnect().then(() => {
    return session?.resyncFromServer(conversationId);
  }).catch((err) => {
    metrics.increment("agent.bfcache.resync_failed");
    showReconnectBanner();
  });
});

window.addEventListener("pagehide", (event: PageTransitionEvent) => {
  if (!event.persisted) {
    // Document is actually unloading — tear down cleanly
    session?.closePermanently();
    return;
  }
  // Entering bfcache — close resources browsers won't freeze reliably
  session?.suspendForBfcache();
});
```

Never use `unload` for cleanup. Prefer `pagehide` and distinguish `persisted`.

## Streaming SSE: close on hide, resync on show

Server-sent event streams for LLM tokens rarely survive bfcache. Pattern:

1. On **pagehide persisted** — `eventSource.close()`; mark UI as disconnected
2. On **pageshow persisted** — open new EventSource from last known `message_id` cursor
3. Server supports **resume** query param — replays missed deltas or sends snapshot

```typescript
// streaming/sseClient.ts
export class AgentSSE {
  private es: EventSource | null = null;
  private lastEventId = "";

  suspendForBfcache(): void {
    this.es?.close();
    this.es = null;
  }

  async reconnect(conversationId: string): Promise<void> {
    const url = new URL(`/api/chat/${conversationId}/stream`, window.location.origin);
    if (this.lastEventId) url.searchParams.set("after", this.lastEventId);

    this.es = new EventSource(url.toString());
    this.es.onmessage = (ev) => {
      this.lastEventId = ev.lastEventId || this.lastEventId;
      applyTokenDelta(ev.data);
    };
    this.es.onerror = () => {
      this.es?.close();
      throw new Error("SSE reconnect failed");
    };
  }
}
```

Server must idempotent-resume: if `after` points to completed message, send full message body once, not duplicate tokens client already rendered. Include `message_version` hash in stream events for client deduplication.

## WebSocket agent channels

Bidirectional agent UIs (voice, collaborative editing, live tool progress) often use WebSockets. Same rule: **close before cache, reconnect after restore**.

```typescript
export class AgentSocket {
  private ws: WebSocket | null = null;
  private heartbeatTimer: number | null = null;

  suspendForBfcache(): void {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.ws?.close(1000, "bfcache");
    this.ws = null;
  }

  async reconnect(token: string): Promise<void> {
    this.ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
    await new Promise<void>((resolve, reject) => {
      this.ws!.onopen = () => resolve();
      this.ws!.onerror = () => reject(new Error("ws failed"));
    });
    this.ws.send(JSON.stringify({ type: "resync", since: this.lastSeq }));
    this.startHeartbeat();
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = window.setInterval(() => {
      this.ws?.send(JSON.stringify({ type: "ping" }));
    }, 25_000);
  }
}
```

Use sequence numbers on server events so resync replays from `lastSeq + 1`. Clear stale "tool running" spinners when resync shows terminal state.

## Resolving stale UI state after restore

Visual DOM from bfcache may show:

- Half-typed assistant response (stream stopped mid-token)
- "Connecting…" from pre-navigation
- Optimistic user message not yet ACK'd

On resync, prefer **server authoritative state**:

```typescript
async function resyncFromServer(conversationId: string): Promise<void> {
  const resp = await fetch(`/api/chat/${conversationId}/snapshot`);
  const snapshot: ConversationSnapshot = await resp.json();

  reconcileMessages(snapshot.messages); // merge by id, fix ordering
  reconcileToolCalls(snapshot.toolCalls); // terminal states win
  setStreamCursor(snapshot.lastStreamCursor);
  clearTransientUI(); // remove stale typing indicators
}
```

Diff merge avoids flicker: update text nodes only when snapshot differs from frozen DOM.

## Framework pitfalls: React, Next.js, Vue

SPAs often assume mount-on-load semantics. bfcache restore skips remount.

**React 18+**: effects with empty deps do not re-run on persisted pageshow. Register bfcache handlers outside React or in a module-level singleton; expose `useBfcacheRestore(callback)`.

**Next.js App Router**: client components hydrating once may hold dead closures over WebSocket refs. Store connection handles in refs cleared on `pagehide`.

**Vue**: `onMounted` won't repeat; use `document.addEventListener('pageshow', ...)` in root setup.

Avoid `beforeunload` unless legally required—Safari and Chrome penalize bfcache. Use in-app navigation guards instead for internal routing.

## Navigation API for typed back/forward

The **`navigation`** API (Chromium) exposes `navigation.type` and intercepts transitions. Useful for agent apps using client-side routing without full reload:

```typescript
if ("navigation" in window) {
  (window as any).navigation.addEventListener("navigate", (e: NavigateEvent) => {
    if (e.navigationType === "traverse" && e.destination.index < e.from?.index!) {
      // back forward — prefetch snapshot early
      prefetchConversationSnapshot(getConversationIdFromUrl(e.destination.url));
    }
  });
}
```

Prefetching snapshot during navigation reduces visible stale window after restore.

## Measuring bfcache in production RUM

Instrument:

```typescript
function reportBfcacheMetrics(): void {
  const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
  if (nav?.type === "back_forward") {
    metrics.timing("agent.nav.back_forward_ms", nav.loadEventEnd - nav.startTime);
  }

  if ("notRestoredReasons" in nav) {
    const reasons = (nav as any).notRestoredReasons;
    if (reasons?.length) {
      metrics.increment("agent.bfcache.blocked", { reasons: reasons.join(",") });
    }
  }
}

window.addEventListener("pageshow", (e) => {
  if (e.persisted) metrics.increment("agent.bfcache.hit");
});
```

Target: bfcache hit rate > 50% on mobile back navigations for chat routes. If blocked, top reasons guide fixes (remove unload, relax no-store on shell).

## Testing bfcache behavior

Manual test sequence:

1. Open agent chat; start streaming response
2. Navigate to settings (same tab)
3. Press back — response should complete or resync within 2s
4. Repeat with DevTools **Application → Back-forward cache** diagnostics (Chrome)

Automate with Playwright where supported—navigate away, `page.goBack()`, assert reconnect beacon fired. Flaky tests often mean missing `pagehide` cleanup leaving zombie listeners.

## Security considerations on restore

Frozen pages retain in-memory auth tokens. bfcache is same-origin isolated—other sites cannot read it. Risk: shared device, user navigates back to agent tab hours later with active session.

Mitigations:

- Short access token TTL with silent refresh only on visible document (`document.visibilityState`)
- On **pageshow persisted** after > N minutes, require visibility-triggered re-auth check
- Clear sensitive message content from bfcache on **pagehide** for high-security tenants (forces full reload—trade UX for policy)

Do not store PCI or secrets in DOM attributes that survive restore without policy review.

## Closing

bfcache makes agent chat feel native-fast on back navigation, but streaming architectures must treat restore as a **reconnection event**, not a no-op. Close SSE and WebSockets on `pagehide` when `persisted`, resync from server snapshot on `pageshow`, dedupe stream cursors, and measure hit rates plus reconnect latency. The back button should not resurrect a beautiful corpse of a dead WebSocket.

## Resources

- [MDN: Back-forward cache (bfcache)](https://developer.mozilla.org/en-US/docs/Glossary/bfcache) — eligibility rules and lifecycle overview
- [Chrome Developers: bfcache article](https://developer.chrome.com/docs/web-platform/back-forward-cache) — notRestoredReasons and best practices
- [WebKit: Page Cache (Safari)](https://webkit.org/blog/516/webkit-page-cache-i-the-basics/) — Safari-specific behavior differences
- [HTML spec: pageshow and pagehide](https://html.spec.whatwg.org/multipage/nav-history-apis.html#the-pageshowevent-interface) — normative persisted semantics
- [PerformanceNavigationTiming](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceNavigationTiming) — detecting back_forward navigations in RUM
