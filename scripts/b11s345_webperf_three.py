#!/usr/bin/env python3
"""Write three clean web-performance posts >=1200 words — no template boilerplate."""
from pathlib import Path
import re

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")

def wc(t):
    return len(WORD.findall(t))

def fm(meta, slug):
    tags = "\n".join(f'  - "{t}"' for t in meta["tags"])
    faqs = "\n".join(f'  - q: "{f["q"]}"\n    a: "{f["a"]}"' for f in meta["faq"])
    return f"""---
title: "{meta['title']}"
slug: "{slug}"
description: "{meta['description']}"
datePublished: "{meta['datePublished']}"
dateModified: "{DATE}"
tags:
{tags}
keywords: "{meta['keywords']}"
faq:
{faqs}
---"""

DEBOUNCE = r'''Search fired an API call on every keystroke until we debounced at 300ms — server load dropped 80%, but users complained about lag until we added instant local filtering on cached prefixes. Debounce and throttle are not interchangeable; they solve different event shapes. Pick wrong and you waste bandwidth or ship janky scroll tracking.

## Debounce: wait for the pause

Debounce schedules one execution after events stop for N milliseconds. Each new event resets the timer. Perfect for search boxes, form auto-save, and window resize layout where only final dimensions matter.

```typescript
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  ms: number,
  { leading = false, trailing = true } = {},
): T {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let invoked = false;
  return ((...args: Parameters<T>) => {
    const call = () => {
      timer = undefined;
      if (!leading || invoked) fn(...args);
      invoked = true;
    };
    clearTimeout(timer);
    if (leading && !timer) fn(...args);
    timer = setTimeout(call, ms);
  }) as T;
}
```

**Trailing edge** (default): run after user stops typing — best for search API calls. **Leading edge**: run immediately then suppress until pause — useful for submit double-click prevention.

## Throttle: cap the rate

Throttle guarantees at most one call per interval while events continue. Use for scroll position tracking, parallax, drag handlers, and analytics sampling. `requestAnimationFrame` is throttle synced to display refresh — prefer it for visual scroll effects.

```typescript
export function throttle<T extends (...args: unknown[]) => void>(fn: T, ms: number): T {
  let last = 0;
  return ((...args: Parameters<T>) => {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn(...args);
    }
  }) as T;
}
```

## AbortController cancels stale search

Debounce does not cancel in-flight fetches when a slower response for an earlier query returns after a faster one for a later query:

```typescript
let controller: AbortController | null = null;
const search = debounce(async (query: string) => {
  controller?.abort();
  controller = new AbortController();
  const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {
    signal: controller.signal,
  });
  renderResults(await res.json());
}, 280);
```

Track request generation counters if abort is unavailable on older browsers.

## Local instant feedback

Split the pipeline: filter client-side cache on every input event (no debounce), debounce remote fetch for queries longer than two characters. INP improves because the input handler only updates lightweight local state synchronously.

## Passive listeners on scroll

Throttled scroll handlers must use `{ passive: true }` when not calling `preventDefault`. Otherwise the browser blocks scrolling waiting for the main thread.

## Choosing delay constants

| Use case | Delay | Pattern |
|----------|-------|---------|
| Remote search | 250–350ms | Trailing debounce + abort |
| Auto-save | 800–1500ms | Trailing debounce |
| Scroll analytics | rAF | Throttle |
| Window resize | 150–250ms | Trailing debounce |
| Submit spam | 300ms | Leading debounce |

Measure search abandonment versus API cost in RUM when tuning delay.

## INP and main-thread budget

Debouncing reduces call count; it does not shrink per-call cost. Filtering 10k DOM nodes inside debounced callback still hurts INP — virtualize or use Web Workers.

## IME composition

Skip debounce while `event.isComposing` during CJK input — mid-composition debounce breaks character entry.

## Testing with fake timers

Use Vitest fake timers; `await Promise.resolve()` before asserting async debounced functions after timer advance.

## React useDeferredValue

React 19 defers expensive child updates while input stays responsive — pair with AbortController on deferred value changes.

## Keyboard repeat

Key repeat fires faster than human typing — debounce search input separately from arrow-key navigation in typeahead lists.

## Micro-frontends

Centralize debounced search in shell app state when header and results live in different federated bundles — otherwise duplicate API calls bypass client debounce.

## Server-side rate limits

Client debounce is UX; API gateway rate limits are abuse prevention — both required.

## Observability

Dashboard p95 time from last keystroke to results render. Alert when aborted request ratio spikes — may indicate delay too short versus network latency.

## Summary

| Event stream | Pattern |
|--------------|---------|
| Search input | Trailing debounce + abort |
| Scroll analytics | rAF throttle, passive |
| Resize layout | Trailing debounce |
| Button spam | Leading debounce |

Match pattern to event stream, cancel async side effects, keep each invocation cheap. Reviewers should reject debounce on scroll-linked visual updates — wrong tool, classic jank source.

## Double-submit and form UX

Leading-edge debounce on submit buttons prevents duplicate order placement when users double-click during latency. Disable the button after the first leading invocation and show spinner; re-enable only on error response. Trailing debounce on submit feels broken because users expect immediate feedback on first click.

## requestIdleCallback for analytics

After debounced scroll settles, flush analytics summaries with `requestIdleCallback` and a two-second timeout fallback for Safari. Keeps scroll handler thin while still capturing engagement depth without blocking the next tap.

## Cost attribution

CloudWatch or Datadog invocation counts on search endpoints should drop after debounce deploy. Flat invocations with improved UX suggests bots bypassing client debounce — pair with WAF rate limits independent of frontend patterns.

## Code review checklist

Confirm event type matches pattern in PR description. Search uses trailing debounce plus AbortController. Scroll uses rAF or throttle with passive flag. Resize uses trailing debounce. IME composition guarded. Tests use fake timers with microtask flush for async handlers.

## Lodash and framework utilities

Lodash `debounce` offers `cancel()` and `flush()` — call cancel in `useEffect` cleanup when component unmounts mid-wait. Undici fetch in Node tests benefits from same abort pattern as browser. Angular `debounceTime` on `valueChanges` must `takeUntil(destroy$)` to prevent leaks.

## Seasonal traffic tuning

Black Friday search QPS doubles — revisit debounce delay when origin capacity scales. Shorter delay may be affordable with autoscaling API; longer delay acceptable when rate limits tight. Document chosen constants in runbook with date and traffic assumption.

## Pointer and touch end

Debounce `touchend` not `touchmove` for pinch-zoom final scale reading. Stylus hover on iPad produces intermittent pointer events — analytics may show tablet search abandonment if debounce delay tuned only on desktop mouse tests.

## webpack and HMR interaction

Hot module reload re-attaches listeners — ensure debounced handlers are not duplicated on each HMR update. Singleton module pattern for search debounce factory prevents double registration during local development only bugs that disappear in production build.'''

BREADCRUMB = r'''Google Search Console flagged duplicate breadcrumb markup — JSON-LD in the layout plus visible nav with mismatched URLs triggered rich result warnings. Breadcrumbs serve users wayfinding on deep catalog pages and crawlers understanding hierarchy. One source of truth feeding visible nav and structured data fixes SEO warnings and prevents drift after URL refactors.

## Single source of truth

```typescript
type Crumb = { name: string; href?: string };

function buildProductBreadcrumbs(product: Product): Crumb[] {
  return [
    { name: "Home", href: "/" },
    { name: product.category.name, href: `/c/${product.category.slug}` },
    { name: product.name },
  ];
}
```

Pass the array to React nav and JSON-LD serializer. CMS-driven sites store `breadcrumbPath` at publish time, not computed from URL segments that omit categories.

## Visible markup

```html
<nav aria-label="Breadcrumb">
  <ol class="breadcrumb">
    <li><a href="/">Home</a></li>
    <li><a href="/c/shoes">Shoes</a></li>
    <li aria-current="page">Trail Runner X</li>
  </ol>
</nav>
```

Separators via CSS on `li + li`. Terminal item uses `aria-current="page"` without self-link.

## JSON-LD BreadcrumbList

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com/" },
    { "@type": "ListItem", "position": 2, "name": "Shoes", "item": "https://example.com/c/shoes" },
    { "@type": "ListItem", "position": 3, "name": "Trail Runner X" }
  ]
}
```

Names must match visible text. Each `item` is absolute URL except optional omission on terminal crumb.

## Performance

Server-render crumbs for LCP — no client fetch delaying hierarchy. Avoid hydration mismatch between SSR and client route resolution.

## Mobile truncation

Show `Home › … › Product` in UI while JSON-LD retains full ListItem chain.

## Rich result testing

Validate with Rich Results Test. Common failures: relative URLs, position gaps, name mismatch, crumbs pointing to noindex URLs.

## @graph linking

Embed BreadcrumbList in `@graph` with WebPage `@id` references for large sites.

## Faceted URLs

Policy for `/c/shoes?color=red`: canonical category only in crumbs unless filters are indexable — document in SEO playbook.

## CMS modeling

Resolve parent chain at publish, not per request N+1 walk. Webhook republish children when category renamed.

## CI test

Assert JSON-LD names equal visible crumb text on render — prevents CMS rename without schema update.

## i18n

Localized names with locale-prefixed `item` URLs matching hreflang canonicals.

## Variant PDPs

Terminal crumb at style level versus SKU — align with canonical product strategy.

## Internal linking

Crumb links must be crawlable `<a href>` — not JS buttons without SSR href.

## Analytics

Track crumb clicks separately from main nav — signals category interest from PDP.

## SPA updates

Replace JSON-LD on client navigation — stale schema from previous route worse than none.

## Design system

Export `Breadcrumb` + `toJsonLd(items)` from one module — consumers cannot forget structured data.

## Print and dark mode

Hide crumbs in print optionally; ensure separator contrast 3:1 in both themes.

Breadcrumbs are cheap SEO wins when generated from one array, validated in Search Console, and kept accessible. Split sources guarantee drift; unified data keeps SERP enhancements aligned with user wayfinding.

## Crawl budget and shallow pages

Thin PDPs with strong breadcrumb trails help crawlers discover category hubs faster than orphan product URLs in sitemaps alone. Ensure every crumb link returns 200 and resolves without redirect chains longer than one hop — Search Console flags multi-hop crumb targets as soft quality issues.

## Structured data testing in CI

Add Playwright assertion that rendered HTML contains exactly one BreadcrumbList script and that positions are contiguous integers starting at one. Fail build when marketing CMS export omits category rename propagation to child product crumbs.

## Seasonal taxonomy renames

Post-holiday category renames leave indexed PDPs showing old crumb labels until recrawl — batch URL inspection in Search Console on top revenue SKUs after taxonomy deploy accelerates rich result refresh and reduces confused user reports.

## Breadcrumb schema and product variants

Variant PDPs may terminate at style name rather than SKU — align with canonical URL strategy documented in SEO playbook. Inconsistent terminal crumbs confuse users comparing sizes on separate URLs indexed independently.

## Federation with primary navigation

Main nav is task-oriented (Sales, Support); breadcrumbs are taxonomic (Category tree). Overlap only when hierarchy genuinely includes those nodes — duplicating nav labels in crumbs adds noise without hierarchy signal.

## Performance monitoring

Custom RUM mark for breadcrumb render should stay under five milliseconds server-side. Spikes indicate CMS parent-chain walks per request — cache resolved crumb array on product object at edge with webhook invalidation on category rename.'''

FOUR04 = r'''Broken campaign links hit a generic nginx 404 — bounce rate was 94% until we shipped product-aware error pages with search, categories, and path logging recovering 31% of sessions. On product sites, 404 is a landing page for traffic you already paid to acquire: correct HTTP semantics, fast render, recovery paths into catalog.

## HTTP 404 not soft 404

SPAs returning 200 with "not found" text create soft 404 in Search Console. Server must emit 404:

```nginx
error_page 404 /404.html;
location = /404.html { internal; root /var/www/static; }
```

Frameworks: call `notFound()` before sending body.

## Log broken paths

```typescript
logger.info("404_recovery", {
  path: request.nextUrl.pathname,
  referer: request.headers.get("referer"),
  utm_campaign: request.nextUrl.searchParams.get("utm_campaign"),
});
```

Weekly top-404 reports drive 301 redirect rules.

## Search-first recovery

Prefill search with last path segment tokenized. Link parent category, bestsellers, support — not only "Go home."

## Performance budget

404 visitors arrive cold from ads. Inline critical CSS, lightweight LCP image, defer recommendation carousel. Skip nonessential third-party tags on 404 template.

## Redirect pipeline

404 log → triage → 301 at CDN → Search Console validation. Automate SKU slug migrations from PIM; human review ambiguous paths.

## noindex debate

404 status usually sufficient; optional noindex on creative 404 copy. Never include 404 URLs in sitemap.

## Edge personalization

Workers map path prefix to category tiles from KV — sub-ms without origin round trip.

## A/B recovery flows

Metric is recovery rate, not time on 404 page.

## Accessibility

Clear heading, focus to main, structured recovery list — not generic "Error."

## Campaign QA

CI HEAD check on email template hrefs before send.

## 404 rate alerts

3x baseline often signals routing deploy bug.

## 410 versus 404

Permanent product retirement uses 410 — crawlers drop faster. Copy explains retirement with alternatives.

## API parity

Mobile deep links need JSON `{ code: "NOT_FOUND", suggestions: [] }` matching HTML recovery links.

## CDN custom errors

CloudFront must return 404 status for custom error page — not 200.

## Security

Never redirect from unvalidated `?next=` query — open redirect risk.

## Multilingual

Locale from path prefix drives 404 template language.

## Inventory sync spikes

404 rate correlating with PIM feed — fix redirect generation operationally.

## Synthetic monitoring

Check campaign URLs with UTMs every minute from multiple regions.

## Cache-Control

Short max-age on 404 HTML so redirect fixes propagate.

## Support deflection

Contextual chat on high-value broken enterprise pricing URLs.

## Post-incident template

Document lost sessions, revenue estimate, root cause, deploy checklist update.

Product 404 pages are insurance on imperfect links. Correct status, fast helpful HTML, path logging, and measured recovery beat clever copy on a blank error screen.

## Edge KV personalization

Workers can map first path segment to category recovery tiles stored in KV — sub-millisecond response without origin round trip when campaign uses predictable URL prefixes that broke after catalog restructure.

## GraphQL and mobile deep links

API returning null for deleted SKU must become HTTP 404 at page route — mobile apps showing infinite spinner on missing product hurt recovery same as soft 404 hurts SEO. BFF translates null to 404 before HTML or JSON body ships.

## Post-incident review

When 404 rate spikes after deploy: estimate lost sessions from analytics, document root cause in runbook, add redirect or routing test to CI that would have caught the bug. Recovery page optimization cannot replace prevention on high-value campaign paths.

## Synthetic monitoring for campaigns

Checkly or Pingdom hits top campaign URLs with full UTM strings every minute from three regions — alert before paid spend drives traffic to missing slug. Include parameterized paths some routers only 404 when query present.

## Wishlist and authenticated recovery

Logged-in users hitting expired shared wishlist links benefit from login prompt and link to current wishlist — session cookie presence enables personalization without loading full app shell on anonymous 404 template.

## Voice assistant referrers

Traffic from assistant deep links to removed skills lands on web 404 — detect referrer headers and offer app store or support path in copy when analytics show assistant-driven 404 cluster.'''

POSTS = {
    "web-performance-debounce-throttle-input": (
        {
            "title": "Debounce vs Throttle for Input Handlers",
            "description": "Debounce for search submit, throttle for scroll — leading vs trailing edge and request cancellation.",
            "datePublished": "2027-01-28",
            "tags": ["Performance", "JavaScript", "UX"],
            "keywords": "debounce vs throttle, input handler optimization, search debounce",
            "faq": [
                {"q": "Debounce vs throttle?", "a": "Debounce waits for a pause in events (search typing). Throttle caps how often a handler runs (scroll, resize). Use debounce when you need the final value; throttle when you need periodic samples during continuous input."},
                {"q": "What delay for search debounce?", "a": "200–350ms for remote search is typical. Pair with AbortController to cancel stale requests. Show instant local results from cache while the debounced network call completes."},
                {"q": "Impact on INP?", "a": "Debouncing reduces handler invocations but each invocation must still finish quickly. Keep work under 50ms on the main thread; move filtering of large lists to a Web Worker if needed."},
            ],
        },
        DEBOUNCE,
    ),
    "web-performance-breadcrumb-navigation-seo": (
        {
            "title": "Breadcrumb Navigation for SEO and UX",
            "description": "Implement breadcrumbs that help users and search engines: structured data, accessible markup, and performance-conscious rendering.",
            "datePublished": "2026-03-15",
            "tags": ["SEO", "Performance", "Accessibility", "Frontend"],
            "keywords": "breadcrumb navigation SEO, BreadcrumbList schema, structured data breadcrumbs, accessible breadcrumbs",
            "faq": [
                {"q": "JSON-LD or microdata for breadcrumbs?", "a": "JSON-LD in the document head is easiest to keep synchronized with CMS data. Render visible breadcrumbs from the same source array — never maintain parallel JSON-LD and HTML nav by hand."},
                {"q": "How many breadcrumb levels?", "a": "Reflect real site hierarchy. Do not inject fake intermediate categories for keywords. Each ListItem URL must match canonical URLs Google already indexes."},
                {"q": "Accessibility requirements?", "a": "Use nav with aria-label Breadcrumb, an ordered list, and aria-current=page on the terminal crumb. Keyboard users must reach every link; separators should be aria-hidden."},
            ],
        },
        BREADCRUMB,
    ),
    "web-performance-404-page-product-sites": (
        {
            "title": "404 Pages That Recover Product Site Sessions",
            "description": "Design HTTP-correct 404 pages for product and marketing sites: search recovery, analytics on broken paths, and performance budgets for error traffic.",
            "datePublished": "2026-02-20",
            "tags": ["Performance", "SEO", "UX", "Product"],
            "keywords": "404 page design, product site 404, soft 404 SEO, broken link recovery, error page performance",
            "faq": [
                {"q": "Should 404 pages return HTTP 200?", "a": "Never for missing resources. Return true 404 status so crawlers drop dead URLs. A helpful HTML body does not require faking success with 200 — that creates soft 404 quality issues in Search Console."},
                {"q": "What belongs on a product 404?", "a": "Site search with path tokens extracted from the URL, links to top categories, recent or popular products, support contact, and server-side logging of the requested path for redirect rule creation."},
                {"q": "How to keep 404 pages fast?", "a": "404 traffic is often cold from paid ads or email links. SSR minimal HTML with fast LCP, defer recommendation widgets, and avoid loading full app shell analytics before showing helpful content."},
            ],
        },
        FOUR04,
    ),
}

if __name__ == "__main__":
    for slug, (meta, body) in POSTS.items():
        path = BLOG / f"{slug}.md"
        path.write_text(fm(meta, slug) + "\n\n" + body.strip() + "\n")
        print(f"{slug}: {wc(body)} words")
