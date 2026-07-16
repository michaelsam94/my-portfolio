---
title: "Encapsulation with Shadow DOM"
slug: "web-components-shadow-dom"
description: "Use Shadow DOM for web component encapsulation: open vs closed mode, styling strategies, slot composition, event retargeting, and when shadow DOM helps versus hurts."
datePublished: "2026-03-19"
dateModified: "2026-03-19"
tags: ["Web", "Web Components", "Shadow DOM", "Frontend"]
keywords: "Shadow DOM, web components, encapsulation, slots, shadow root, custom elements"
faq:
  - q: "What is Shadow DOM and what problem does it solve?"
    a: "Shadow DOM creates an isolated DOM subtree attached to a host element, with its own scoped styles and DOM structure hidden from the outer page. External CSS cannot leak in and internal styles cannot leak out. This solves the naming collision and style override problems that plague traditional widget development, where a class name like .button or .header in your component conflicts with the same class on the host page."
  - q: "What is the difference between open and closed Shadow DOM?"
    a: "Open shadow DOM is accessible via element.shadowRoot, allowing debugging tools and JavaScript to inspect the internal structure. Closed shadow DOM returns null from shadowRoot, fully hiding the internals. Open mode is recommended for nearly all use cases because debugging, testing, and accessibility tools need access to the shadow tree. Closed mode provides security through obscurity but breaks DevTools inspection and automated testing."
  - q: "When should I avoid Shadow DOM?"
    a: "Avoid Shadow DOM when you need global styles to penetrate your component (design system tokens applied via CSS custom properties are the exception), when you use third-party libraries that query the document directly (charts, maps, rich text editors), or when server-side rendering requires full HTML access. Shadow DOM adds complexity to testing, E2E automation, and form association. Use it when style and DOM encapsulation are genuine requirements, not as a default for every custom element."
---

I shipped a widget library without Shadow DOM. Three months later, a consumer's global CSS rule `div { margin: 16px }` broke layout in every component. We added a prefix to every class name. Then their Tailwind reset removed our list styles. Then their `!important` theme overrode our button colors. We spent more time fighting style collisions than building features. Shadow DOM would have prevented all of it by scoping styles inside an isolated subtree. It's not free — it complicates testing, theming, and SSR — but for reusable components distributed across unknown host pages, encapsulation is worth the trade-off.

## Creating a shadow root

```javascript
class UserCard extends HTMLElement {
  constructor() {
    super();
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
      <style>
        .card { padding: 1rem; border: 1px solid #e5e7eb; border-radius: 8px; }
        .name { font-size: 1.25rem; font-weight: 600; }
        .email { color: #6b7280; }
      </style>
      <div class="card">
        <div class="name"><slot name="name">Unknown</slot></div>
        <div class="email"><slot name="email"></slot></div>
      </div>
    `;
  }
}

customElements.define('user-card', UserCard);
```

```html
<user-card>
  <span slot="name">Alice Chen</span>
  <span slot="email">alice@example.com</span>
</user-card>
```

External CSS cannot affect `.card`, `.name`, or `.email` inside the shadow tree. Internal styles don't leak out.

## Open vs closed mode

```javascript
// Open (recommended): shadowRoot is accessible
this.attachShadow({ mode: 'open' });

// Closed: shadowRoot returns null
this.attachShadow({ mode: 'closed' });
```

Use open mode. Closed mode breaks:
- Chrome DevTools element inspection
- `element.shadowRoot.querySelector()` in tests
- Accessibility tree traversal in some screen readers
- Event delegation from the host page

## Slots: composable content

Slots project light DOM content into shadow DOM positions:

```html
<!-- Component definition -->
<template id="card-tmpl">
  <style>
    header { font-weight: bold; }
    ::slotted(img) { max-width: 100%; border-radius: 4px; }
  </style>
  <header><slot name="title">Default Title</slot></header>
  <div class="body"><slot>Default body content</slot></div>
  <footer><slot name="footer"></slot></footer>
</template>

<!-- Usage -->
<my-card>
  <span slot="title">Product Name</span>
  <p>Product description here.</p>
  <span slot="footer">$29.99</span>
</my-card>
```

- Named slots (`slot="title"`) map to `<slot name="title">`
- Default slot (no name) catches unslotted content
- `::slotted()` styles slotted content from inside the shadow tree (limited to display and inherited properties)

## Styling strategies

### Encapsulated (default)

Styles inside shadow DOM scope to the component. No collisions.

### CSS custom properties for theming

The escape hatch for host-page theming:

```css
/* Inside shadow DOM */
.card {
  background: var(--card-bg, white);
  color: var(--card-text, #1f2937);
  border-color: var(--card-border, #e5e7eb);
}
```

```css
/* On the host page */
user-card {
  --card-bg: #1e293b;
  --card-text: #f1f5f9;
  --card-border: #334155;
}
```

Custom properties pierce shadow boundaries. This is the standard theming contract for web components.

### ::part() for targeted styling

Expose specific shadow elements for external styling:

```css
/* Inside shadow DOM */
.button { /* internal styles */ }
```

```html
<button class="button" part="button">Click</button>
```

```css
/* On the host page */
user-card::part(button) {
  background: #2563eb;
  border-radius: 999px;
}
```

`:host` styles the custom element itself from inside shadow DOM:

```css
:host { display: block; }
:host([disabled]) { opacity: 0.5; pointer-events: none; }
:host-context(.dark-theme) { color: white; }
```

## Event retargeting

Events that originate inside shadow DOM are retargeted at the host element:

```javascript
const card = document.querySelector('user-card');
card.addEventListener('click', (e) => {
  console.log(e.target);    // user-card (not the internal button)
  console.log(e.composedPath()); // [button, shadow-root, user-card, ...]
});
```

For events that need to escape shadow DOM, set `composed: true`:

```javascript
this.dispatchEvent(new CustomEvent('select', {
  detail: { id: this.itemId },
  bubbles: true,
  composed: true  // crosses shadow boundary
}));
```

## When to use shadow DOM

**Use it:**
- Reusable component libraries distributed to third parties
- Widgets embedded on pages you don't control
- Components where style isolation is a hard requirement

**Skip it:**
- App-internal components where you control all CSS
- Components wrapping libraries that need document access (D3, Leaflet, Monaco)
- SSR-heavy apps where shadow DOM hydration is problematic
- Simple components where a CSS module or scoped class is sufficient

## Testing shadow DOM components

```javascript
// Open mode: query inside shadow root
const card = document.querySelector('user-card');
const name = card.shadowRoot.querySelector('.name');
expect(name.textContent).toBe('Alice Chen');

// Playwright: pierce shadow
const button = page.locator('user-card').locator('.button');
await button.click();
```

For closed mode, testing requires the component to expose test hooks — another reason to prefer open mode.

## Common production mistakes

Teams get components shadow dom wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of components shadow dom fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When components shadow dom misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MDN Shadow DOM](https://developer.mozilla.org/en-US/docs/Web/API/Web_components/Using_shadow_DOM)
- [MDN slot element](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/slot)
- [CSS shadow parts](https://developer.mozilla.org/en-US/docs/Web/CSS/::part)
- [web.dev shadow DOM v1](https://web.dev/articles/shadowdom-v1)
- [Open UI shadow DOM explainer](https://open-ui.org/components/custom-elements/)
