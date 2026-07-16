---
title: "Web Components in 2026"
slug: "web-components-2026"
description: "Where web components stand in 2026: custom elements, shadow DOM, declarative shadow DOM for SSR, framework interop, and when Lit beats reaching for a full framework."
datePublished: "2026-03-07"
dateModified: "2026-03-07"
tags: ["Web", "Frontend", "Architecture"]
keywords: "web components, custom elements, shadow DOM, declarative shadow DOM, framework interop, lit"
faq:
  - q: "What are web components?"
    a: "Web components are a set of browser-native standards for building reusable, encapsulated custom HTML elements. The core pieces are Custom Elements (defining your own tags with lifecycle callbacks), Shadow DOM (scoped, encapsulated markup and styles), and HTML templates. Because they're built into the browser, a web component works in any framework or in plain HTML without a build step or runtime dependency."
  - q: "What is declarative shadow DOM and why does it matter?"
    a: "Declarative shadow DOM lets you express a component's shadow root directly in server-rendered HTML using a <template shadowrootmode> element, rather than requiring JavaScript to attach it. This finally makes web components server-side renderable: the encapsulated markup arrives in the initial HTML, so content is visible and styled before any JavaScript runs, fixing the biggest historical weakness of the standard."
  - q: "Should I use web components instead of React or Vue?"
    a: "Use web components when you need framework-agnostic, long-lived UI — design systems, shared widgets consumed by multiple teams or apps, or embeds that must work anywhere. Use a framework like React or Vue for cohesive application development where its ecosystem, state management, and developer experience pay off. The two aren't mutually exclusive; many teams ship a web-component design system consumed inside React apps, and reach for Lit when a component needs reactive state without a full framework."
---

Web components have had a strange reputation — perpetually "the future," never quite the present. In 2026 that framing is finally wrong. The standards matured, the missing pieces (server rendering, sane styling, form participation) landed, and the browser-native path to reusable, framework-agnostic UI is genuinely viable for real work. A web component is a custom HTML element you define yourself, with encapsulated markup and styles via shadow DOM, that runs anywhere HTML runs — no framework, no build step required.

I want to give an honest 2026 status report: what's solid, what the new capabilities unlock, where the friction still lives, and when I'd actually reach for them over a framework. I've shipped design systems both ways, and the calculus has genuinely shifted.

## The three primitives, briefly

The standard rests on a few browser APIs that have been stable for years:

- **Custom Elements** — register a tag name to a class extending `HTMLElement`, with lifecycle callbacks (`connectedCallback`, `attributeChangedCallback`, and friends).
- **Shadow DOM** — attach an encapsulated DOM subtree with scoped styles that don't leak in or out.
- **HTML templates** — inert `<template>` markup you clone at runtime.

A minimal element looks like this:

```javascript
class UserBadge extends HTMLElement {
  static observedAttributes = ["name"];

  connectedCallback() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>:host { display: inline-flex; gap: .5rem; }</style>
      <img part="avatar" alt="">
      <span>${this.getAttribute("name") ?? ""}</span>`;
  }
}
customElements.define("user-badge", UserBadge);
```

```html
<user-badge name="Michael"></user-badge>
```

That `<user-badge>` works in a React app, a Vue app, an Astro page, or a static HTML file. That portability is the entire reason the standard exists.

## What changed: declarative shadow DOM

The historical dealbreaker was server rendering. Shadow DOM used to require JavaScript (`attachShadow`) to exist at all, so a server-rendered page showed nothing until the component's JS ran — terrible for performance and SEO. Declarative shadow DOM fixes this at the HTML level:

```html
<user-badge>
  <template shadowrootmode="open">
    <style>:host { display: inline-flex; gap: .5rem; }</style>
    <img part="avatar" alt="">
    <span>Michael</span>
  </template>
</user-badge>
```

The browser parses that `<template shadowrootmode>` and attaches the shadow root during HTML parsing — no script needed. The encapsulated content is visible and styled in the initial response, then JavaScript hydrates behavior on top. This is the single most important web-components development of the last few years, because it removes the "you can't SSR them" objection that kept them out of serious stacks.

## Styling grew up too

Shadow DOM's style encapsulation was always a double-edged sword: great isolation, but themeing across the boundary was painful. The tools that make it workable now:

- **CSS custom properties** pierce the shadow boundary, so `--brand-color` set on the host flows in — the sanctioned theming channel.
- **`::part()`** lets consumers style specific internal elements you expose via `part="..."`, without breaking full encapsulation.
- **Constructable stylesheets** (`adoptedStyleSheets`) let many instances share one parsed stylesheet instead of duplicating `<style>` blocks — a real memory win at scale.

The mental model: encapsulation is the default, and you deliberately open specific, named seams (`--vars` and `part`s) for theming. It's more disciplined than global CSS, which is exactly what a design system wants.

## Lit versus vanilla

You *can* write everything by hand, but manual attribute reflection and imperative DOM updates get old fast. [Lit](https://lit.dev/) is the pragmatic middle ground — about 5KB, reactive properties, and efficient template updates, producing standard web components with no proprietary lock-in:

```javascript
import { LitElement, html, css } from "lit";

class CounterBtn extends LitElement {
  static properties = { count: { type: Number } };
  static styles = css`button { font: inherit; padding: .4rem .8rem; }`;
  constructor() { super(); this.count = 0; }

  render() {
    return html`<button @click=${() => this.count++}>
      Clicked ${this.count}×
    </button>`;
  }
}
customElements.define("counter-btn", CounterBtn);
```

Here's my rule of thumb:

| Approach | Best for | Cost |
| --- | --- | --- |
| Vanilla custom elements | Tiny, mostly-static widgets | Manual DOM/attr plumbing |
| Lit | Interactive, reactive components | ~5KB dependency |
| Full framework | Whole applications | Larger runtime, framework lock-in |

For anything with reactive state, I reach for Lit. For a one-off static badge, vanilla is fine. For a whole app, a web component is the wrong unit — reach for a framework.

## Framework interop is the killer use case

The strongest argument for web components in 2026 is *organizational*, not technical. If you have React, Vue, and legacy apps across teams, a web-component design system is the one artifact all of them can consume without duplication. React 19 finally handles custom elements' properties and events properly, and the other frameworks have long supported them. You build the button, card, and modal once, and every app uses the same real element.

They also compose beautifully with server-centric approaches. A [hypermedia-driven app with HTMX](https://blog.michaelsam94.com/htmx-hypermedia-apps/) can sprinkle interactive web components into server-rendered fragments, and modern browser features like the [View Transitions API for smooth SPAs](https://blog.michaelsam94.com/view-transitions-api/) work on custom elements just like any other DOM. The standards-based pieces stack without fighting each other, which is the quiet advantage of building on the platform.

## The friction that remains

I won't oversell it. The rough edges in 2026:

- **Form participation is workable but fiddly.** The `ElementInternals` API lets custom elements participate in forms (submit values, validity), but it's more code than a native `<input>` and easy to get subtly wrong.
- **SSR tooling is younger than framework SSR.** Declarative shadow DOM is the standard; the libraries that render Lit components to that markup are solid but less battle-tested than Next.js-grade tooling.
- **DX is thinner.** Fewer devtools niceties, less Stack Overflow coverage, and hot-reload stories that vary by setup compared to the framework mainstream.
- **Accessibility across shadow boundaries.** ARIA references (`aria-labelledby` pointing across a shadow root) have historically been awkward; newer APIs help, but audit carefully.

## The verdict

Web components in 2026 are the right tool for framework-agnostic, long-lived UI: design systems, shared widgets, and embeddable elements that must work everywhere. They are *not* the right tool for building a whole application — the ecosystem, state management, and DX of a real framework still win there. The teams getting the most value ship a web-component design system and consume it inside their React or Vue apps, getting portability at the component layer and productivity at the app layer.

The reason to care now, versus the last decade of "someday," is declarative shadow DOM plus mature styling. Those closed the two gaps that made the standard impractical for serious use. It's no longer a bet on the future — it's a solid, boring, browser-native option, and for the specific job of shared UI, boring and browser-native is exactly what you want.

## Resources

- [MDN — Web Components](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
- [Lit — official documentation](https://lit.dev/docs/)
- [web.dev — Declarative Shadow DOM](https://web.dev/articles/declarative-shadow-dom)
- [MDN — Using shadow DOM](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM)
- [WHATWG — HTML Standard: custom elements](https://html.spec.whatwg.org/multipage/custom-elements.html)
- [Open Web Components — guides and tooling](https://open-wc.org/)
