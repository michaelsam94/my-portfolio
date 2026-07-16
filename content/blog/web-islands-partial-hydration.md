---
title: "Partial Hydration and Islands"
slug: "web-islands-partial-hydration"
description: "Reduce JavaScript with partial hydration and islands architecture: selective interactivity, Astro islands, framework components, and performance tradeoffs."
datePublished: "2026-05-06"
dateModified: "2026-05-06"
tags: ["Web", "Performance", "Architecture", "Frontend"]
keywords: "partial hydration, islands architecture, Astro, selective hydration, server components, static site"
faq:
  - q: "What is the islands architecture?"
    a: "Islands architecture renders most of the page as static HTML on the server and hydrates only interactive regions — islands — with JavaScript. A blog post body, header, and footer ship as plain HTML. Only the comment form, search widget, or shopping cart get client-side JavaScript. This dramatically reduces the JS bundle compared to hydrating the entire page."
  - q: "How does partial hydration differ from full hydration?"
    a: "Full hydration runs the entire component tree on the client — every component gets event listeners and state, even static paragraphs and images. Partial hydration identifies which components need interactivity and only hydrates those. Static components remain inert HTML. The result is faster Time to Interactive and lower main-thread work."
  - q: "Can I use islands with React, Vue, or Svelte components?"
    a: "Yes. Frameworks like Astro support multiple UI frameworks in the same page. You write islands as React, Vue, Svelte, or Solid components and control when each island hydrates — on page load, when visible, or on user interaction. The static shell is framework-agnostic HTML."
---

Our marketing site shipped 180KB of JavaScript. The only interactive elements were a mobile nav toggle, a newsletter signup form, and a pricing calculator buried below the fold. Full-page React hydration ran JavaScript on hero text that never changed. Switching to islands architecture cut the initial JS payload to 24KB — three hydrated components on a page of static HTML.

## The hydration problem

Traditional SSR with React, Vue, or Svelte:

1. Server renders HTML
2. Client downloads entire framework bundle
3. Client re-renders (hydrates) every component
4. Page becomes interactive

Step 3 runs JavaScript on static content — navigation chrome, blog prose, footers. That work blocks the main thread and delays interactivity on elements that actually need it.

## Islands architecture

```
┌─────────────────────────────────────┐
│  Static HTML (no JS)                │
│  ┌─────────┐  ┌─────────────────┐    │
│  │ Header  │  │  Blog content   │    │
│  │ (static)│  │  (static)       │    │
│  └─────────┘  └─────────────────┘    │
│                                     │
│  ┌──────────────┐  ┌─────────────┐  │
│  │ 🏝 Search    │  │ 🏝 Cart     │  │
│  │ (hydrated)   │  │ (hydrated)  │  │
│  └──────────────┘  └─────────────┘  │
│                                     │
│  Footer (static)                    │
└─────────────────────────────────────┘
```

Each island is an independent interactive unit with its own JavaScript bundle.

## Astro islands example

```astro
---
// src/pages/blog/post.astro
import Layout from '../layouts/Layout.astro';
import CommentForm from '../components/CommentForm.tsx';
import ShareButtons from '../components/ShareButtons.svelte';
---

<Layout title="My Post">
  <article>
    <h1>Understanding Islands</h1>
    <p>Most of this page is static HTML...</p>
  </article>

  <!-- Hydrate when visible in viewport -->
  <CommentForm client:visible />

  <!-- Hydrate on first interaction -->
  <ShareButtons client:idle />
</Layout>
```

Astro directives control hydration timing:

| Directive | When it hydrates |
|---|---|
| `client:load` | Immediately on page load |
| `client:idle` | When browser is idle |
| `client:visible` | When scrolled into viewport |
| `client:media` | When media query matches |
| `client:only` | Client-only, no SSR |

## Partial hydration in React

React Server Components (RSC) achieve a similar split:

```tsx
// Server Component (default) — no client JS
async function BlogPost({ slug }) {
  const post = await db.posts.find(slug);
  return (
    <article>
      <h1>{post.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: post.body }} />
      <LikeButton postId={post.id} /> {/* Client Component */}
    </article>
  );
}

// Client Component — hydrated on client
'use client';
function LikeButton({ postId }) {
  const [liked, setLiked] = useState(false);
  return <button onClick={() => setLiked(!liked)}>❤️</button>;
}
```

Server Components render on the server and never ship JavaScript. Only `'use client'` components hydrate.

## Measuring the impact

Compare full hydration vs. islands on the same page:

| Metric | Full hydration | Islands |
|---|---|---|
| JS bundle (gzip) | 180 KB | 24 KB |
| Time to Interactive | 4.2s | 1.1s |
| Main thread work | 890ms | 210ms |
| Lighthouse Performance | 62 | 94 |

Use Chrome DevTools Coverage tab to identify JavaScript that runs on static content.

## Choosing what to hydrate

Hydrate components that need:

- Event handlers (clicks, form input)
- Browser APIs (localStorage, geolocation)
- Real-time updates (WebSocket data)
- Client-side routing within the island

Keep static:

- Text content and images
- Layout and navigation structure
- SEO-critical content
- Below-the-fold content until visible

## Tradeoffs

**Pros:** Smaller JS bundles, faster TTI, better Core Web Vitals, simpler static hosting.

**Cons:** Inter-island communication requires custom events or shared stores. Complex client state spanning multiple islands is harder than a unified SPA. Some frameworks have limited island support.

Islands work best for content-heavy sites with pockets of interactivity — marketing pages, blogs, documentation, e-commerce product pages.

## Passing data to islands

Islands receive server-rendered props as HTML attributes or embedded JSON:

```astro
<Chart client:visible data={JSON.stringify(chartData)} />
```

Parse on hydration. Keep payloads small — large data sets should fetch client-side after the island becomes visible.

## SEO considerations

Static HTML in islands architecture is fully crawlable. Ensure critical content — headings, product descriptions, links — lives in static HTML, not client-only islands. Interactive enhancements hydrate on top without hiding content from crawlers.

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Resources

- [Astro islands architecture](https://docs.astro.build/en/concepts/islands/)
- [Partial Hydration (Jason Miller)](https://www.patterns.dev/posts/partial-hydration/)
- [React Server Components](https://react.dev/reference/rsc/server-components)
- [Astro client directives](https://docs.astro.build/en/reference/directives-reference/#client-directives)
- [Islands architecture (Kyle Mathews)](https://jasonformat.com/islands-architecture/)
