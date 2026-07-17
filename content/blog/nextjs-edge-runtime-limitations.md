---
title: "Edge Runtime Limitations in Next.js"
slug: "nextjs-edge-runtime-limitations"
description: "What works and breaks on Edge: Node APIs, bundle size, cold starts, and when to stay on Node.js runtime."
datePublished: "2026-07-18"
dateModified: "2026-07-17"
tags:
keywords: "Next.js edge runtime limitations, Edge vs Node runtime Next.js"
faq:
  - q: "What APIs are unavailable on Edge Runtime?"
    a: "Node.js core modules like fs, crypto.createHash (limited), child_process, and native addons. Use Web APIs: fetch, Web Crypto, TextEncoder. Database drivers needing TCP often fail."
  - q: "Should Route Handlers use Edge by default?"
    a: "Only for lightweight auth checks, geo routing, A/B assignment, and proxying. Data mutations and ORM access belong on Node.js runtime."
  - q: "How do I debug Edge bundle size errors?"
    a: "Run next build and inspect .next/server/edge chunks. Use @vercel/nft or bundle analyzer. Split heavy logic to Node Route Handlers called from Edge."
---
Your middleware worked perfectly in development. In production on Edge, `fs.readFile` throws, Prisma fails to connect, and a 2MB dependency blows past the bundle limit. Edge Runtime trades Node.js compatibility for global low-latency deployment—but only some workloads fit.

## ('Choosing Edge vs Node runtime', "Export `runtime = 'edge'` only when you have measured latency win and confirmed dependency compatibility.\n\n```typescript\nexport const runtime = 'edge';\n\nexport async function GET() {\n  const country = request.headers.get('x-vercel-ip-country') ?? 'US';\n  return Response.json({ country });\n}\n```\n\nDefault to Node.js runtime until profiling proves Edge benefit.")

## ('Bundle size constraints', 'Edge functions ship as bundled JavaScript with strict size limits (typically 1–4MB depending on platform). ORMs, PDF libraries, and image processing libraries exceed limits quickly.\n\nPattern: Edge validates JWT and routes; Node handler processes business logic via internal fetch.')

## ('Database and ORM pitfalls', 'Prisma, pg, mysql2 use Node TCP sockets unavailable on Edge. Use HTTP-based data APIs: Prisma Accelerate, PlanetScale serverless driver, Supabase REST, or your own Node API.\n\nNever import PrismaClient in edge middleware—it fails at build or runtime.')

## ('Cold starts and latency', 'Edge cold starts are faster than Node serverless but still exist. Keep handler logic minimal. Avoid top-level await of heavy initialization.\n\nWarm critical paths with scheduled pings only if your platform charges for invocations—often unnecessary on Vercel Edge.')

## ('Web Crypto vs Node crypto', "Use Web Crypto API for JWT verification on Edge:\n\n```typescript\nimport { jwtVerify } from 'jose';\n\nconst { payload } = await jwtVerify(token, secret);\n```\n\n`jsonwebtoken` depends on Node crypto—replace with `jose` for Edge compatibility.")

## ('Production decision matrix', '| Use case | Runtime |\n|----------|--------|\n| Geo redirect | Edge |\n| JWT gate | Edge |\n| Stripe webhook | Node |\n| PDF generation | Node |\n| RSC data fetch with ORM | Node |')



## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on edge runtime limitations

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.
