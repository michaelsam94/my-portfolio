---
title: "Fetch Cache and next.revalidate in Next.js"
slug: "nextjs-fetch-cache-next-revalidate"
description: "Time-based ISR with fetch next.revalidate, stale-while-revalidate semantics, and per-fetch TTL tuning."
datePublished: "2026-12-30"
dateModified: "2026-07-17"
tags:
keywords: "Next.js fetch revalidate, next.revalidate ISR, fetch cache TTL"
faq:
  - q: "What is the difference between export const revalidate and next.revalidate?"
    a: "Route segment revalidate sets default for the page. fetch next.revalidate overrides per request. The shortest TTL wins when composing multiple fetches on one page."
  - q: "Does next.revalidate work with POST fetch?"
    a: "No. Only GET and HEAD responses cache. Mutations must use cache: 'no-store'."
  - q: "What happens during revalidation window?"
    a: "Users may see stale content until background revalidation completes—stale-while-revalidate. First request after TTL triggers regeneration; concurrent requests still get stale until new cache entry ready."
---
Product listings refresh every 60 seconds; legal disclaimers change twice a year. One global `revalidate` export on the page forces both to the same TTL. Per-fetch `next.revalidate` lets each data source declare its own freshness contract.

## ('Per-fetch TTL', '```typescript\nconst products = await fetch(`${API}/products`, {\n  next: { revalidate: 60 },\n});\n\nconst legal = await fetch(`${API}/legal`, {\n  next: { revalidate: 86400 },\n});\n```\n\nDocument TTL rationale in code comments—future engineers will otherwise unify TTLs incorrectly.')

## ('Combining revalidate with tags', "```typescript\nawait fetch(url, {\n  next: { revalidate: 300, tags: ['products'] },\n});\n```\n\nTags enable on-demand invalidation before TTL expires. Use both: TTL as safety net, tags for event-driven updates.")

## ('Stale-while-revalidate behavior', "After TTL expires, Next.js serves cached response while regenerating in background. Monitor `x-nextjs-cache: STALE` during incidents.\n\nFor zero-stale requirements, use cache: 'no-store' or on-demand revalidation only.")

## ('Self-hosted considerations', 'Multi-instance deployments need shared cache for consistent revalidate behavior. Single-node `next start` uses filesystem cache—scale horizontally requires custom cache handler or platform support.')

## ('Testing TTL', 'Use `next build && next start`, not dev server. Wait TTL duration or mock time in integration tests. Assert content updates after revalidate window plus regeneration time.')

## ('Anti-patterns', 'Setting revalidate: 1 on high-traffic pages—regeneration storm under load. Setting revalidate: false (infinite) without tags—content never updates until redeploy.')



## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on fetch cache next revalidate

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.
