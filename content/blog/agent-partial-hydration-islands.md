---
title: "AI Agents: Partial Hydration Islands"
slug: "agent-partial-hydration-islands"
description: "Ship agent dashboards that stay fast by hydrating only interactive surfaces — chat input, tool traces, and approval buttons — while leaving static shell markup server-rendered."
datePublished: "2026-05-18"
dateModified: "2026-05-18"
tags: ["AI", "Agent", "Partial"]
keywords: "partial hydration, astro islands, selective hydration, agent UI performance, client:visible, server components agent dashboard"
faq:
  - q: "What is the difference between partial hydration and full SPA hydration?"
    a: "A full SPA hydrates the entire page tree on load, attaching event listeners and component state everywhere. Partial hydration leaves most HTML inert and attaches JavaScript only to named islands — typically the chat composer, streaming message list, and tool-approval widgets in agent UIs."
  - q: "Which agent UI parts should be islands vs static HTML?"
    a: "Hydrate anything with streaming, WebSocket, or drag-and-drop behavior. Keep navigation chrome, documentation sidebars, session metadata headers, and legal footers as static HTML. If it does not change after first paint, it should not hydrate."
  - q: "Does partial hydration break accessibility for screen readers?"
    a: "Not if you render meaningful static HTML first. Hydration adds behavior, not structure. Problems appear when islands start empty and fill via client fetch — use server-rendered message history and live regions only on the streaming island."
  - q: "How do I measure whether islands are worth the complexity?"
    a: "Compare Total Blocking Time and JS transfer size before and after. Agent consoles often drop 40–70% of client JS when logs and settings panels stay static. Track Time to Interactive on a mid-tier laptop, not just developer M-series metrics."
---
The first version of our internal agent console was a React SPA. It felt fine on a MacBook Pro with thirty tabs closed. On a contractor's Thinkpad, opening a run detail page pulled 890 KB of gzipped JavaScript, blocked the main thread for two seconds, and only then started subscribing to the SSE stream that had already been buffering events on the server.

The fix was not a rewrite to a different framework religion. It was **partial hydration**: ship HTML that works without JavaScript, then attach interactivity only where the agent loop actually needs it.

## Hydration cost in agent surfaces

Agent UIs look interactive everywhere but are not. A typical run detail page includes:

- A header with run ID, model name, and timestamps — static after SSR
- A scrollable transcript — needs streaming updates
- A tool-call timeline with expand/collapse — needs client state
- A sidebar of JSON metadata — static unless you add search
- An approval bar for human-in-the-loop gates — needs click handlers and optimistic UI

Fully hydrating that page means paying for React (or equivalent) on the metadata sidebar nobody clicks during incidents. Partial hydration inverts the default: **assume static until proven interactive.**

## Islands architecture in practice

[Astro islands](https://docs.astro.build/en/concepts/islands/) popularized the model, but the pattern ports anywhere: mark component boundaries with explicit hydration directives.

```
┌─────────────────────────────────────────────┐
│  Static shell (SSR HTML, zero client JS)    │
│  ┌─────────────────────────────────────┐    │
│  │ Island: ChatStream (client:visible) │    │
│  └─────────────────────────────────────┘    │
│  ┌──────────┐  ┌──────────────────────────┐ │
│  │ Static   │  │ Island: ToolApproval     │ │
│  │ metadata │  │ (client:idle)            │ │
│  └──────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────┘
```

Each island ships its own JavaScript bundle. The shell never pays for tool-approval code on pages without pending approvals.

### Hydration directives that match agent behavior

| Directive | Use on agent UI |
|-----------|-----------------|
| `client:load` | Chat composer on the primary agent page — user expects immediate input |
| `client:visible` | Long transcripts and log tails — hydrate when scrolled into view |
| `client:idle` | Secondary panels: diff viewers, optional JSON formatters |
| `client:media` | Mobile-only compact tool trace layout |
| `client:only` | Last resort for browser-only APIs (Clipboard, File System Access) |

Default to `visible` or `idle`, not `load`. Agent dashboards are read-heavy during incident response; users stare at streaming output before they click anything.

## Astro example: run detail page

```astro
---
// RunDetail.astro — server component
import ChatStream from '../islands/ChatStream.jsx';
import ToolApproval from '../islands/ToolApproval.jsx';
import { fetchRun, fetchMessages } from '../lib/runs';

const { id } = Astro.params;
const run = await fetchRun(id);
const messages = await fetchMessages(id); // SSR first page of history
---

<layout title={`Run ${run.id}`}>
  <header>
    <h1>{run.agentName}</h1>
    <p>Model: {run.model} · Started {run.startedAt}</p>
  </header>

  <aside class="meta">
    <h2>Configuration</h2>
    <pre>{JSON.stringify(run.config, null, 2)}</pre>
  </aside>

  <main>
    <ChatStream
      client:visible
      runId={run.id}
      initialMessages={messages}
      sseUrl={`/api/runs/${run.id}/events`}
    />
  </main>

  {run.pendingApproval && (
    <ToolApproval
      client:idle
      approvalId={run.pendingApproval.id}
      toolName={run.pendingApproval.tool}
      args={run.pendingApproval.args}
    />
  )}
</layout>
```

The transcript renders complete HTML for the first N messages on the wire. The island hydrates, opens SSE, and appends deltas — users without JavaScript still see history; they lose live updates only.

## The streaming island implementation

Keep streaming logic isolated. Mixing fetch + SSE + markdown rendering in the page shell reintroduces full-app coupling.

```tsx
// islands/ChatStream.tsx
import { useEffect, useRef, useState } from "react";

type Message = { id: string; role: string; content: string };

export default function ChatStream(props: {
  runId: string;
  initialMessages: Message[];
  sseUrl: string;
}) {
  const [messages, setMessages] = useState(props.initialMessages);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource(props.sseUrl);
    es.addEventListener("message.delta", (ev) => {
      const delta = JSON.parse(ev.data);
      setMessages((prev) => appendDelta(prev, delta));
    });
    es.addEventListener("message.done", (ev) => {
      const finalMsg = JSON.parse(ev.data);
      setMessages((prev) => finalize(prev, finalMsg));
    });
    return () => es.close();
  }, [props.sseUrl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div role="log" aria-live="polite" aria-relevant="additions">
      {messages.map((m) => (
        <article key={m.id} data-role={m.role}>
          <header>{m.role}</header>
          <div>{m.content}</div>
        </article>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
```

`aria-live="polite"` on the island container preserves screen reader announcements without hydrating the static sidebar.

## Framework alternatives

Partial hydration is not Astro-exclusive:

- **Next.js App Router** — Server Components by default; add `"use client"` only on interactive leaves. Equivalent mental model with different syntax.
- **Qwik** — Resumability instead of hydration; excellent for pages with bursty interactivity.
- **Marko** — Partial hydration from the server-first era; still relevant for high-throughput marketing + agent embed hybrids.

Pick based on team familiarity. The architectural rule — static shell, interactive archipelagos — survives framework churn.

## State boundaries and data fetching

The mistake that kills island performance is lifting all state to a parent provider that wraps the entire layout. If your Zustand or Redux store wraps the shell, you have rebuilt an SPA with extra steps.

Rules that held up across deployments:

1. **Colocate state inside the island** that owns the UX.
2. **Pass serializable props from SSR** — initial messages, approval payloads, feature flags.
3. **Use URL search params for shareable view state** (expanded tool ID) instead of global stores when possible.
4. **Never client-fetch data already in SSR HTML** unless paginating beyond the first window.

For paginated transcripts, SSR the first page and let the island fetch older pages on scroll-up — still cheaper than hydrating a virtualized list on load.

## Security and human-in-the-loop gates

Approval islands handle destructive tool calls. They should:

- Render the pending action server-side (so security scanners see it in HTML snapshots)
- Hydrate confirm/cancel handlers only on the approval bar
- POST with CSRF tokens issued at SSR time
- Disable double-submit with a client flag, but enforce idempotency on the server

Partial hydration does not relax server validation. The island is UX; the API is authority.

## Performance checklist before launch

Run these on throttled hardware (6× CPU slowdown, Fast 3G):

- [ ] **JS transferred** for a read-only run view with no pending approval — target under 150 KB gzip
- [ ] **Lighthouse TBT** under 200 ms on run detail
- [ ] **First contentful paint** includes transcript text, not a spinner shell
- [ ] **SSE connection opens** within 500 ms after island hydration
- [ ] **No hydration mismatch warnings** — SSR and client initial state must match for `initialMessages`

If read-only views still pull more than 300 KB JS, audit imports inside shared island utilities. One `import { format } from 'date-fns'` re-exporting the full locale bundle in a shared helper hydrates the cost everywhere.

## When partial hydration is the wrong tool

Skip islands if the page is genuinely one interactive canvas — collaborative whiteboards, node-based agent workflow editors, or embedded Monaco instances. Those pages are mostly island; forcing SSR splits adds complexity without savings.

Also skip if your team lacks SSR infrastructure. Partial hydration assumes a server that renders HTML per request or at build time with incremental updates. Client-only Vite SPAs need a hosting migration first.

## Parting thought

Agent products train users to stare at streaming text, not click through marketing nav. That usage pattern rewards server-rendered transcripts with surgical client attachment points. Partial hydration islands are how you keep the console snappy without giving up rich tool approval flows — measure JS eliminated from the static shell, not framework novelty.

## Resources

- [Astro islands architecture](https://docs.astro.build/en/concepts/islands/)
- [Astro client directives reference](https://docs.astro.build/en/reference/directives-reference/#client-directives)
- [Next.js Server and Client Components](https://nextjs.org/docs/app/building-your-application/rendering/server-components)
- [web.dev Total Blocking Time](https://web.dev/articles/tbt)
- [MDN EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
