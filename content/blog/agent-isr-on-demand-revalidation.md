---
title: "AI Agents: Isr On Demand Revalidation"
slug: "agent-isr-on-demand-revalidation"
description: "Isr On Demand Revalidation: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-05-23"
dateModified: "2026-05-23"
tags: ["AI", "Agent", "Isr"]
keywords: "agent, isr, on, demand, revalidation, ai, production, engineering, architecture"
faq:
  - q: "What is on-demand revalidation in Next.js ISR and why do agent dashboards need it?"
    a: "ISR caches statically generated pages with a revalidate interval. On-demand revalidation lets backend events—agent run completed, eval score updated, knowledge base synced—purge specific paths immediately via revalidatePath or revalidateTag instead of waiting for time-based expiry. Agent UIs showing live metrics need this or users see stale run history."
  - q: "When should agents trigger revalidateTag vs revalidatePath?"
    a: "Use tags for shared data slices fetched across many routes (e.g., agent-list, tenant-123-metrics). Use paths for a single page (/dashboard/agents/run-abc). Tags scale better when one CMS or agent event invalidates dozens of ISR pages; paths are simpler for pinpoint updates."
  - q: "How do you secure on-demand revalidation webhooks from agent backends?"
    a: "Never expose unauthenticated revalidation routes. Use a shared secret in Authorization header, verify HMAC signature on payload, restrict to internal network or Vercel deployment protection, and rate-limit the endpoint. Agents should call revalidation only after durable writes commit—not optimistically before DB success."
  - q: "What breaks if agent pipelines revalidate too aggressively?"
    a: "Thundering herd regenerates ISR pages simultaneously, spiking origin load and LLM aggregation queries. Batch tag invalidations, debounce high-frequency agent events, and use stale-while-revalidate at CDN where possible. Monitor regeneration queue depth and p95 TTFB after deploys."
---
The agent ops dashboard showed a successful deployment from forty minutes ago while the run had failed three times since then. ISR cached `/dashboard/agents/[id]` with `revalidate: 300`—fine for marketing pages, wrong for operational surfaces fed by agent telemetry. Switching to **on-demand revalidation** wired to agent lifecycle webhooks fixed freshness without abandoning static performance for the shell layout.

Incremental Static Regeneration (ISR) in Next.js App Router lets you serve cached HTML with background refresh. **On-demand revalidation** invalidates that cache when data changes—critical when AI agents mutate backend state continuously and users expect near-real-time visibility. This deep dive covers App Router patterns, tag design, secure webhook routes, agent event integration, and operational guardrails against revalidation storms.

## ISR vs on-demand: when each applies

| Strategy | Mechanism | Best for |
|----------|-----------|----------|
| Time-based ISR | `revalidate: 60` in fetch or segment config | Slowly changing docs, public agent gallery |
| On-demand path | `revalidatePath('/dashboard/runs')` | Single route after known mutation |
| On-demand tag | `revalidateTag('agent-runs')` | Shared data across multiple ISR pages |

Agent products usually combine: long `revalidate` as safety net **plus** on-demand invalidation on events.

```
Agent worker completes run ──▶ webhook ──▶ /api/revalidate ──▶ revalidateTag('run:{id}')
                                                                    │
                                                                    ▼
                                                          Next.js purges cache entries
                                                                    │
                                                                    ▼
                                                          Next request regenerates page
```

## App Router fetch caching and tags

Tag data at fetch time so invalidation is precise:

```typescript
// app/dashboard/agents/[agentId]/page.tsx
import { notFound } from "next/navigation";

async function getAgentRuns(agentId: string) {
  const res = await fetch(
    `${process.env.API_URL}/agents/${agentId}/runs?limit=20`,
    {
      next: {
        revalidate: 600, // fallback TTL
        tags: [`agent-runs`, `agent-runs:${agentId}`],
      },
    },
  );
  if (!res.ok) notFound();
  return res.json();
}

export default async function AgentDashboardPage({
  params,
}: {
  params: { agentId: string };
}) {
  const runs = await getAgentRuns(params.agentId);
  return (
    <main>
      <h1>Agent {params.agentId}</h1>
      <RunTable runs={runs} />
    </main>
  );
}
```

Dual tags enable global list invalidation (`agent-runs`) or single-agent scope (`agent-runs:uuid`).

## Secure revalidation API route

```typescript
// app/api/revalidate/route.ts
import { revalidatePath, revalidateTag } from "next/cache";
import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function verifySignature(body: string, signature: string | null): boolean {
  if (!signature || !process.env.REVALIDATE_SECRET) return false;
  const expected = crypto
    .createHmac("sha256", process.env.REVALIDATE_SECRET)
    .update(body)
    .digest("hex");
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected),
  );
}

export async function POST(req: NextRequest) {
  const raw = await req.text();
  const sig = req.headers.get("x-revalidate-signature");

  if (!verifySignature(raw, sig)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const payload = JSON.parse(raw) as {
    tags?: string[];
    paths?: string[];
  };

  for (const tag of payload.tags ?? []) {
    revalidateTag(tag);
  }
  for (const path of payload.paths ?? []) {
    revalidatePath(path);
  }

  return NextResponse.json({
    revalidated: true,
    tags: payload.tags ?? [],
    paths: payload.paths ?? [],
    now: Date.now(),
  });
}
```

Agent backends sign payloads after durable commit:

```python
import hashlib
import hmac
import json
import requests


def notify_revalidate(tags: list[str], secret: str, base_url: str) -> None:
    body = json.dumps({"tags": tags}, separators=(",", ":"))
    signature = hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    resp = requests.post(
        f"{base_url}/api/revalidate",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-revalidate-signature": signature,
        },
        timeout=5,
    )
    resp.raise_for_status()
```

## Agent event → tag mapping

Design tags around entity lifecycle:

| Agent event | Tags to invalidate |
|-------------|-------------------|
| Run completed | `run:{id}`, `agent-runs:{agentId}`, `agent-runs` |
| Eval score updated | `evals:{agentId}`, `leaderboard` |
| KB document ingested | `kb-chunk:{docId}`, `kb-search` |
| Tenant config changed | `tenant:{tenantId}` |

Avoid blanket `revalidateTag('everything')`—regeneration storms follow.

```typescript
export function tagsForAgentRunComplete(event: {
  runId: string;
  agentId: string;
  tenantId: string;
}): string[] {
  return [
    `run:${event.runId}`,
    `agent-runs:${event.agentId}`,
    `agent-runs`,
    `tenant-metrics:${event.tenantId}`,
  ];
}
```

Debounce high-frequency events (streaming token counts) with 2–5 second windows; batch tags in one webhook call.

## Partial prerendering and dynamic islands

Not every agent UI element belongs in ISR. Split:

- **Static shell** — layout, nav, design system (ISR-friendly)
- **Dynamic island** — live run logs via client SSE or Server Components with `cache: 'no-store'`

On-demand revalidation suits **aggregate** views; streaming logs stay dynamic. Mixing both prevents over-invalidation of pages that should never cache.

```typescript
// components/LiveRunLog.tsx — client component, no ISR
"use client";

import { useEffect, useState } from "react";

export function LiveRunLog({ runId }: { runId: string }) {
  const [lines, setLines] = useState<string[]>([]);

  useEffect(() => {
    const es = new EventSource(`/api/runs/${runId}/stream`);
    es.onmessage = (e) => setLines((prev) => [...prev, e.data]);
    return () => es.close();
  }, [runId]);

  return <pre>{lines.join("\n")}</pre>;
}
```

## CDN and deployment considerations

On Vercel, `revalidateTag` purges Data Cache entries; CDN may still serve stale HTML briefly depending on headers. Set appropriate `Cache-Control` on ISR responses and use `stale-while-revalidate` where UX allows soft freshness.

Self-hosted Next.js behind nginx: ensure purge hooks reach all origin instances or use shared cache layer (Redis for fetch cache in experimental setups).

After deploy, tag associations persist but regenerated pages use new code—smoke test revalidation in staging with production-shaped tags.

## Testing strategy

- **Integration** — POST signed revalidate; assert subsequent page fetch includes new data (playwright + fixture API)
- **Auth** — reject missing/invalid signatures
- **Idempotency** — duplicate webhooks safe (revalidate is idempotent)
- **Load** — burst 100 tag invalidations; monitor origin CPU and regeneration latency

Include revalidation in agent CI when dashboard pages depend on ISR tags introduced in the same PR.

## Operational metrics

Track:

- `revalidation_requests_total{source}`
- `isr_regeneration_duration_seconds`
- `cache_hit_ratio` for tagged fetches
- Time from agent run complete → dashboard reflects terminal state (end-to-end SLO)

Alert when regeneration p95 exceeds user-facing freshness SLO or origin error rate spikes after invalidation bursts.

## Common failure modes

- **Revalidate before DB commit** — user refreshes into stale-or-error state; webhook only after transaction commit
- **Tag typo** — silent cache never clears; lint tag strings from shared constants package
- **Missing tags on fetch** — page never invalidates; code review checklist for `next.tags`
- **Over-broad paths** — `revalidatePath('/', 'layout')` nukes entire site cache

## Multi-tenant agent platforms

Scope tags with `tenantId` prefix—`tenant:abc:agent-runs`—so one tenant's agent activity does not invalidate another's cached pages in shared deployments.

Row-level security in API must match tag scope; ISR pages must not embed cross-tenant data in shared tags.

## Preview and draft agent configs

Agents often support draft configs users preview before publish. ISR must not serve draft data from production cache:

- Preview routes use `cache: 'no-store'` or separate `/preview/` path namespace
- Publishing draft → active triggers `revalidateTag(`agent-config:${id}`)` plus path invalidation for public agent gallery

```typescript
export async function publishAgentConfig(agentId: string, tenantId: string) {
  await db.transaction(async (tx) => {
    await tx.agentConfig.promoteDraftToActive(agentId);
  });
  await notifyRevalidate([
    `agent-config:${agentId}`,
    `tenant:${tenantId}:agents`,
    "agent-gallery",
  ]);
}
```

Never share tags between preview and production fetch calls—tag collision leaks unpublished prompts into cached HTML, a critical confidentiality bug.

## Stale-while-revalidate UX for agent metrics

Full synchronous regeneration on every run completion can spike TTFB. For non-critical metrics cards, return cached ISR page immediately while revalidation runs in background—Next.js default ISR behavior.

Display `lastUpdated` timestamp from API inside the page so users interpret sub-minute staleness correctly. Live run **status** (running vs failed) should still use on-demand revalidation or client polling—do not rely on 10-minute time-based revalidate for terminal state transitions.

Balance: operational clarity beats perfect cache efficiency for failed-run visibility.

## The takeaway

ISR on-demand revalidation keeps agent-facing Next.js dashboards fast and fresh: tag fetches at the data layer, invalidate surgically on agent lifecycle events, secure webhooks with HMAC, and debounce high-frequency updates to avoid regeneration storms. Time-based revalidate alone is insufficient for operational agent UIs—wire explicit invalidation into every durable state change users expect to see immediately.

## Resources

- [Next.js on-demand revalidation docs](https://nextjs.org/docs/app/building-your-application/data-fetching/incremental-static-regeneration)
- [revalidateTag and revalidatePath API reference](https://nextjs.org/docs/app/api-reference/functions/revalidateTag)
- [Vercel ISR and Data Cache](https://vercel.com/docs/incremental-static-regeneration)
- [Companion: Server Components Cache Revalidate](/agent-server-components-cache-revalidate/)
- [Companion: CDN Stale-While-Revalidate](/agent-cdn-stale-while-revalidate/)
- [Companion: Realtime Dashboard WebSocket](/agent-realtime-dashboard-websocket/)
