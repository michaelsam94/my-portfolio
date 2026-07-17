---
title: "Draft Mode and Preview Content in Next.js"
slug: "nextjs-draft-mode-preview-content"
description: "Enable CMS preview with draftMode(), bypass cache safely, and protect preview routes."
datePublished: "2026-07-16"
dateModified: "2026-07-17"
tags:
keywords: "Next.js draft mode, preview content, draftMode CMS"
faq:
  - q: "How does Next.js Draft Mode differ from preview mode in Pages Router?"
    a: "Draft Mode sets a signed cookie via draftMode().enable() that tells Server Components and fetch to bypass static cache. Pages Router preview used __preview_data cookie with different semantics."
  - q: "How do I secure draft preview URLs?"
    a: "Never expose draft enable routes publicly without secret token validation. Use short-lived tokens from CMS webhooks, validate HMAC signatures, and disable indexing with X-Robots-Tag."
  - q: "Will draft mode affect production cache?"
    a: "Only requests with the draft cookie bypass cache. Normal visitors unaffected. Ensure enable route cannot be CSRF-triggered."
---
Your content team publishes at 5 PM Friday. Marketing previewed the hero copy Thursday—or thought they did. The CMS showed the draft, but the Next.js site served cached static HTML from Tuesday's build. Draft Mode exists so editors see unpublished content on the real site without rebuilding or busting CDN cache for everyone.

## Enabling draft mode from a CMS webhook

```typescript
// app/api/draft/route.ts
import { draftMode } from "next/headers";
import { redirect } from "next/navigation";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const secret = searchParams.get("secret");
  const slug = searchParams.get("slug");
  if (secret !== process.env.DRAFT_SECRET || !slug) {
    return new Response("Invalid", { status: 401 });
  }
  draftMode().enable();
  redirect(`/blog/${slug}`);
}
```

Sanity, Contentful, and Storyblok all support webhook-triggered preview URLs pointing at this route pattern.

## Fetching draft content in Server Components

```typescript
async function getPost(slug: string) {
  const { isEnabled } = draftMode();
  const res = await fetch(`${CMS}/posts/${slug}`, {
    headers: isEnabled ? { Authorization: `Bearer ${process.env.CMS_PREVIEW_TOKEN}` } : {},
    next: isEnabled ? { revalidate: 0 } : { tags: [`post-${slug}`] },
  });
  return res.json();
}
```

When draft mode is active, bypass cache entirely. When inactive, use normal ISR tags.

## Visual indicators and SEO protection

Always show a draft banner in preview so editors never confuse preview with production:

```tsx
export default async function Layout({ children }) {
  const { isEnabled } = draftMode();
  return (
    <>
      {isEnabled && <div role="status" className="draft-banner">Draft preview — not published</div>}
      {children}
    </>
  );
}
```

Set headers on draft responses: `X-Robots-Tag: noindex, nofollow`. Search engines must never index preview URLs.

## Route Handlers vs Middleware for preview auth

Validate preview secrets in Route Handlers, not middleware alone—middleware cannot easily call CMS validation APIs. Keep enable/disable routes out of sitemap and robots.txt.

## Disable draft mode

```typescript
// app/api/draft/disable/route.ts
import { draftMode } from "next/headers";

export async function GET() {
  draftMode().disable();
  return Response.json({ draft: false });
}
```

Provide editors a "Exit preview" link in the banner. Stale draft cookies confuse QA sessions days later.

## Testing preview flows

Integration test: call enable route with valid secret, assert draft banner visible, assert CMS preview token sent. Call disable, assert banner gone and cached content returns.

## Common failures

- Preview works locally but not production: `DRAFT_SECRET` missing in env
- Infinite redirect loop: enable route redirects before cookie set—use `draftMode().enable()` before redirect
- Editors see stale draft: fetch still tagged with ISR—force `cache: 'no-store'` when `isEnabled`

## Resources

- [Next.js Draft Mode](https://nextjs.org/docs/app/building-your-application/configuring/draft-mode)
- [Contentful preview](https://www.contentful.com/developers/docs/tutorials/general/preview-content/)


## Multi-environment preview tokens


Use separate CMS preview tokens for staging and production preview hosts. A token leak on staging should not expose production draft content. Rotate preview tokens quarterly and audit webhook URLs in CMS settings.


## Collaboration with content teams


Document preview URL format in CMS training docs. Editors bookmark enable URLs with slug parameters. Support 'share preview' links that expire in 24 hours for stakeholder review without permanent draft cookies.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on draft mode preview content

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.
