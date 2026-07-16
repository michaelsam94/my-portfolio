---
title: "Server-Driven UI with htmx"
slug: "web-htmx-server-driven-ui"
description: "Build interactive web apps with htmx: HTML-over-the-wire, hx-get and hx-post attributes, partial page updates, and when server-driven UI beats SPA complexity."
datePublished: "2026-05-05"
dateModified: "2026-05-05"
tags: ["Web", "htmx", "Backend", "Frontend"]
keywords: "htmx, server-driven UI, HTML over the wire, partial updates, hypermedia, hx-get, hx-swap"
faq:
  - q: "What problem does htmx solve compared to a React or Vue SPA?"
    a: "htmx lets you add interactivity — partial page updates, form submissions, polling — using HTML attributes instead of a JavaScript framework. The server returns HTML fragments, and htmx swaps them into the DOM. You avoid client-side routing, state management, build tooling, and API serialization. The tradeoff is less client-side interactivity and more server round-trips."
  - q: "How does htmx differ from traditional AJAX with fetch?"
    a: "With fetch, you write JavaScript to parse JSON, build DOM nodes, and handle errors. htmx sends requests and swaps HTML responses directly into the page using declarative attributes like hx-get and hx-target. The server renders partial templates — the same templating engine used for full pages — and the client just inserts the result."
  - q: "Can htmx work with any backend framework?"
    a: "Yes. htmx is backend-agnostic because it consumes HTML responses. Django, Rails, Express, Go templates, PHP — any framework that renders HTML works. The server returns HTML fragments instead of JSON, and htmx handles the DOM update. You may add an HX-Request header check to return partial layouts."
---

Our admin dashboard was a React SPA with 200 API endpoints returning JSON that the client re-rendered into HTML. Adding a filter dropdown required a new API route, a TypeScript type, a React component, and a loading state. We rebuilt one section with htmx: the server returned an HTML table fragment, the client swapped it in. The feature shipped in an afternoon.

## Core attributes

```html
<!-- Load content on click -->
<button hx-get="/stats" hx-target="#stats-panel" hx-swap="innerHTML">
  Load stats
</button>
<div id="stats-panel"></div>

<!-- Submit form, replace table body -->
<form hx-post="/users/search" hx-target="#user-table" hx-swap="outerHTML">
  <input name="q" type="search" placeholder="Search users" />
  <button type="submit">Search</button>
</form>
<table id="user-table">...</table>

<!-- Auto-refresh every 30 seconds -->
<div hx-get="/notifications/count" hx-trigger="every 30s" hx-swap="innerHTML">
  3 new
</div>
```

| Attribute | Purpose |
|---|---|
| `hx-get`, `hx-post`, `hx-put`, `hx-delete` | HTTP method and URL |
| `hx-target` | CSS selector for swap target |
| `hx-swap` | How to insert response (`innerHTML`, `outerHTML`, `beforeend`, `delete`) |
| `hx-trigger` | Event that fires request (`click`, `submit`, `every 2s`, `revealed`) |
| `hx-indicator` | Loading spinner element |

## Server-side partial rendering

Detect htmx requests and return fragments:

```python
# Django view
def user_list(request):
    users = User.objects.filter(name__icontains=request.GET.get('q', ''))
    template = 'users/_table.html' if request.headers.get('HX-Request') else 'users/list.html'
    return render(request, template, {'users': users})
```

```html
<!-- templates/users/_table.html -->
<table id="user-table">
  {% for user in users %}
  <tr>
    <td>{{ user.name }}</td>
    <td>{{ user.email }}</td>
  </tr>
  {% endfor %}
</table>
```

Return only the fragment when `HX-Request: true` is in the request header.

## Out-of-band swaps

Update multiple page regions from one response:

```html
<!-- Response includes -->
<div id="cart-count" hx-swap-oob="true">5 items</div>
<div id="cart-items" hx-swap-oob="true">
  <!-- updated cart list -->
</div>
```

The primary swap target gets the main response body. Elements with `hx-swap-oob="true"` update their matching IDs elsewhere on the page.

## Loading and error states

```html
<button
  hx-delete="/items/42"
  hx-target="#item-42"
  hx-swap="outerHTML swap:1s"
  hx-confirm="Delete this item?"
  hx-indicator="#spinner"
>
  Delete
</button>
<span id="spinner" class="htmx-indicator">Deleting...</span>
```

CSS hides indicators by default:

```css
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
```

Handle errors with the `htmx:responseError` event:

```javascript
document.body.addEventListener('htmx:responseError', (e) => {
  const target = e.detail.target;
  target.innerHTML = '<p class="error">Something went wrong. Try again.</p>';
});
```

## When to use htmx vs. SPA

| Use htmx | Use SPA framework |
|---|---|
| CRUD admin panels | Real-time collaborative editing |
| Search/filter tables | Complex client-side state |
| Multi-step forms | Offline-first apps |
| Dashboards with periodic refresh | Heavy animation and transitions |
| Internal tools | Public consumer apps with SEO needs |

htmx excels where server rendering already exists and interactivity needs are moderate.

## Progressive enhancement

Without JavaScript, forms submit normally and links navigate to full pages. htmx enhances progressively:

```html
<form action="/search" method="get" hx-get="/search" hx-target="#results">
  <input name="q" />
  <button type="submit">Search</button>
</form>
```

The `action` and `method` attributes provide the fallback behavior.

## hx-boost for full-page navigation

Upgrade regular links to AJAX navigation without JavaScript routers:

```html
<body hx-boost="true">
  <a href="/about">About</a> <!-- navigates without full reload -->
</body>
```

The server returns a full HTML document; htmx swaps the body content. Progressive enhancement for multi-page apps.

## hx-swap-oob for toasts

Return toast notifications alongside main content:

```html
<div id="toast" hx-swap-oob="true" class="success">Saved!</div>
```

Update notification areas without targeting them explicitly in hx-target.

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

- [htmx documentation](https://htmx.org/docs/)
- [htmx examples](https://htmx.org/examples/)
- [Hypermedia Systems (book)](https://hypermedia.systems/)
- [django-htmx integration](https://django-htmx.readthedocs.io/)
- [htmx vs React comparison](https://htmx.org/essays/a-response-to-rich-harris/)
