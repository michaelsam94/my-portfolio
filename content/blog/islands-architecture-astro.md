---
title: "Islands Architecture with Astro"
slug: "islands-architecture-astro"
description: "Islands architecture with Astro explained: partial hydration, client:* directives, and shipping zero JS by default so only interactive components load JavaScript."
datePublished: "2026-01-12"
dateModified: "2026-01-12"
tags: ["Web", "Frontend", "Performance"]
keywords: "islands architecture, Astro, partial hydration, client islands, zero JS, static first, selective hydration"
faq:
  - q: "What is islands architecture?"
    a: "Islands architecture is a rendering pattern where a page is served as mostly static HTML with small, independent regions of interactivity — 'islands' — that hydrate on their own. Instead of shipping and hydrating one big JavaScript app, each interactive component loads only its own JavaScript, and the static content around it ships no JS at all. This drastically cuts the amount of code the browser must download and execute."
  - q: "How does Astro implement partial hydration?"
    a: "Astro renders every component to static HTML at build time by default and ships zero JavaScript. You opt specific components into interactivity with client directives like client:load, client:idle, and client:visible, which control when that island's JavaScript is downloaded and hydrated. Everything you don't mark stays static, so the JavaScript payload maps directly to actual interactivity."
  - q: "Can I use React and Vue components together in Astro?"
    a: "Yes. Astro is framework-agnostic and lets you mix components from React, Vue, Svelte, Solid, and others on the same page, each hydrating as its own island. This is useful for incremental migrations and for teams with mixed expertise, though in practice sticking to one UI framework per project keeps the bundle and mental model simpler."
---

Most web pages are mostly static. A blog post, a docs page, a marketing site, a product listing — the interactive parts are a search box, a menu toggle, maybe a cart widget, surrounded by content that never changes after render. Islands architecture takes that observation seriously: serve the whole page as static HTML, then hydrate only the interactive regions as isolated "islands," each loading just its own JavaScript. Astro is the framework that made this the default rather than an optimization you bolt on later.

The payoff is measured in kilobytes the user never downloads. I've migrated content sites from a conventional React SPA to Astro and watched JavaScript payloads drop by an order of magnitude, with Lighthouse scores going from "we should fix that eventually" to green without any heroics. The trick is that the architecture makes the fast path the easy path.

## The problem islands solve

A traditional SPA hydrates the entire page as one application. Even if 95% of the page is static text, the browser downloads the whole component tree's JavaScript, parses it, and runs hydration to attach event listeners that most of the DOM will never use. That's wasted bytes, wasted main-thread time, and a real hit to metrics like Time to Interactive — especially on mid-range phones, which is most of the world.

Islands flip the default. The page is HTML. JavaScript is the exception, requested per-island, only where interactivity actually exists. The mental model I use: you're not building an app that happens to have content; you're building a document that happens to have a few interactive widgets.

## Astro's zero-JS-by-default model

In Astro, components render to HTML at build (or request) time and ship no client JavaScript unless you say otherwise. An `.astro` component is server-only by nature. When you drop in a framework component — React, Svelte, Vue, Solid — it *also* renders to static HTML by default. It only becomes interactive when you add a `client:*` directive.

```astro
---
import Header from "../components/Header.astro";
import SearchBox from "../components/SearchBox.jsx";
import Newsletter from "../components/Newsletter.svelte";
---
<Header />                          <!-- static HTML, 0 KB JS -->
<SearchBox client:idle />          <!-- island: hydrates when the browser is idle -->
<article>{content}</article>        <!-- static -->
<Newsletter client:visible />      <!-- island: hydrates when scrolled into view -->
```

The directives are the whole control surface, and choosing the right one per island is where the performance lives:

| Directive | Hydrates when | Use for |
| --- | --- | --- |
| `client:load` | Immediately on page load | Above-the-fold, critical interactivity |
| `client:idle` | Browser hits idle time | Non-urgent widgets (search, menus) |
| `client:visible` | Component scrolls into viewport | Below-the-fold carousels, comment forms |
| `client:media` | A media query matches | Mobile-only or desktop-only UI |
| `client:only` | Client-side only, skip SSR | Components that can't render on the server |

My default is `client:visible` for anything below the fold and `client:idle` for things near it. Reserve `client:load` for genuinely critical interactivity, because it's the one that competes with everything else at startup.

## Why isolation matters

The word "islands" is doing real work. Each island is an independent hydration root. If your comment widget throws during hydration, the search box and the rest of the page are unaffected — there's no single app tree to take down. Compare that to a monolithic SPA where one bad component in the tree can break hydration for the entire page.

That isolation also makes performance debugging tractable. Each island's JavaScript cost is attributable to that island. When a bundle grows, you know exactly which widget did it, instead of staring at one giant chunk. For teams, it means you can be generous with static content and stingy, deliberately, with JavaScript.

## Where islands fit — and where they don't

Islands architecture is not a universal answer, and I'd be doing you a disservice to pretend it is. It excels for **content-first** sites: blogs, documentation, marketing, e-commerce catalogs, news. The more of your page is static content, the bigger the win.

It's a worse fit for **application-first** experiences — a design tool, a trading dashboard, a collaborative editor — where nearly everything is interactive and shares client state. If most of your page needs to be an island, you've just rebuilt an SPA with extra ceremony, and a framework built for that (or [React Server Components in production](https://blog.michaelsam94.com/react-server-components-production/)) will serve you better. Cross-island state sharing is the pain point: islands are isolated by design, so coordinating state between them requires nano-stores, custom events, or lifting shared logic out — friction that a single-tree SPA doesn't have.

## Islands versus other partial-rendering ideas

The industry converged on the same insight — ship less JavaScript, render more on the server — from several directions at once, and it's worth knowing how they relate. [Partial prerendering in Next.js](https://blog.michaelsam94.com/partial-prerendering-nextjs/) blends a static shell with streamed dynamic holes within a React app, keeping you in one framework's model. Astro's islands take a more framework-agnostic, document-centric stance: static by default, interactivity as explicit opt-in, any UI library welcome.

They're not strictly competing so much as optimizing for different starting points. If you already live in React and want the same app to be faster, the RSC and PPR direction is incremental. If you're building content-heavy sites and want the JavaScript budget to start at zero, Astro's islands are the more direct route. I've used both; the deciding factor is almost always "how much of this page is truly interactive."

## Practical advice from shipping it

A few things I'd tell my past self:

- **Audit your islands like a budget.** Every `client:*` directive is a line item. Periodically ask whether a "widget" could just be static HTML with a `<details>` element or a CSS-only interaction.
- **Prefer `client:visible` aggressively.** Most below-the-fold interactivity doesn't need to hydrate at load; deferring it keeps the initial main thread free.
- **Watch for framework duplication.** Mixing React and Vue islands means shipping two runtimes. It's allowed, and great for migrations, but consolidate to one framework for greenfield work.
- **Use `.astro` components for the static skeleton.** They're the cheapest thing on the page and keep the JavaScript surface honest.

Islands architecture is one of those ideas that feels obvious in hindsight: don't hydrate what isn't interactive. Astro's contribution is making that the effortless default instead of the thing you promise to optimize next quarter. For the large category of sites that are content wrapped around a little interactivity, it's the fastest architecture I know that still lets you use the component tools you like.

## Resources

- [Astro — official documentation](https://docs.astro.build/)
- [Astro — Islands architecture guide](https://docs.astro.build/en/concepts/islands/)
- [Jason Miller — Islands Architecture (original article)](https://jasonformat.com/islands-architecture/)
- [patterns.dev — Islands Architecture](https://www.patterns.dev/vanilla/islands-architecture/)
- [web.dev — Rendering on the web](https://web.dev/articles/rendering-on-the-web)
- [Astro GitHub repository](https://github.com/withastro/astro)
