---
title: "CSS Container Queries for Responsive Components"
slug: "rag-container-queries-responsive"
description: "Build responsive AI agent UIs with CSS container queries—chat panels, tool result cards, and embedded widgets that adapt to parent width, not just viewport breakpoints."
datePublished: "2026-06-04"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Container"]
keywords: "CSS container queries, @container, responsive agent UI, chat layout, component queries, embedded agent widget"
faq:
  - q: "Why are viewport media queries insufficient for agent interfaces?"
    a: "Agent UIs appear in split views, slide-over panels, iframe embeds, and mobile webviews where the viewport is wide but the chat column is 320px. Media queries see the phone or desktop; container queries see the actual space the agent UI occupies. Breakpoints tied to viewport cause broken tool cards and unreadable streaming text in narrow embeds."
  - q: "Which elements should be container query roots in an agent chat?"
    a: "Establish containment on the chat shell, each message column, and tool result cards—not the entire page. The chat shell drives thread density; message columns handle avatar and bubble layout; tool cards switch between table and stacked field layouts when width drops below usable thresholds."
  - q: "Do container queries work in shadow DOM agent widgets?"
    a: "Yes, when the shadow host or an inner wrapper sets container-type and styles use @container within the same shadow tree. External page CSS cannot query your shadow containers—design self-contained responsive rules inside the widget bundle."
---
Our agent dashboard looked perfect in Figma at 1440px. In production, half of enterprise users ran it inside a 380px sidebar next to their CRM. Tool result tables overflowed horizontally, citation chips wrapped into illegible stacks, and the streaming markdown renderer reflowed so aggressively that users reported motion sickness. We had `@media (min-width: 768px)` everywhere. The viewport was 1920px. The agent panel was not.

Responsive design for AI agent interfaces is a container problem, not a device problem. Agents ship as embeddable widgets, copilot sidebars, and multi-pane workspaces where the same component must breathe in a full-page chat and survive a narrow plugin slot. CSS container queries (`@container`) let components respond to their parent's size—the geometry users actually perceive.

## Viewport vs container: the mental model

**Media queries** answer: how big is the browser window?

**Container queries** answer: how big is the box I am laid out in?

```
┌─────────────────────────────────────────────┐  viewport 1440px
│  CRM header                                 │
├──────────────┬──────────────────────────────┤
│   CRM list   │  Agent panel (380px) ◄───────┼── container query root
│              │  ┌─────────────────────────┐ │
│              │  │ Tool result card        │ │
│              │  │ @container (narrow)     │ │
│              │  └─────────────────────────┘ │
└──────────────┴──────────────────────────────┘
```

Agent products increasingly embed in host apps you do not control. Container queries decouple your responsive rules from host page breakpoints.

## Establishing containment

A query container requires explicit containment on an ancestor:

```css
.agent-chat-shell {
  container-type: inline-size;
  container-name: agent-chat;
  /* optional: height containment for block-axis queries */
  /* container-type: size; requires defined block size */
}
```

`inline-size` is the common case—width-driven layout for Western locales. Use `size` when vertical space determines layout (collapsed transcript modes in short modals).

Child components query with:

```css
@container agent-chat (max-width: 480px) {
  .message-row {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .message-avatar {
    display: none;
  }

  .tool-result-table {
    display: block;
  }

  .tool-result-table tr {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border-subtle);
  }
}
```

Name containers when multiple nested contexts exist—chat shell vs individual tool card:

```css
.tool-card {
  container-type: inline-size;
  container-name: tool-card;
}

@container tool-card (max-width: 360px) {
  .tool-field-label {
    font-size: 0.75rem;
  }
}
```

## Layout patterns for production chat

### Message thread density

Wide containers show multi-column metadata: model name, latency, token count inline. Narrow containers collapse metadata into a disclosure:

```css
.message-meta-inline { display: flex; gap: 0.75rem; }
.message-meta-compact { display: none; }

@container agent-chat (max-width: 520px) {
  .message-meta-inline { display: none; }
  .message-meta-compact { display: block; }
}
```

### Tool invocation cards

Tool calls render structured JSON—tables break in narrow widths. Use a **responsive field list** pattern:

```css
.tool-fields {
  display: grid;
  grid-template-columns: minmax(8rem, 30%) 1fr;
  gap: 0.5rem 1rem;
}

@container tool-card (max-width: 400px) {
  .tool-fields {
    grid-template-columns: 1fr;
  }
}
```

For arrays of results (search hits, database rows), switch from table to card stack below threshold—do not horizontal-scroll tables in 320px embeds unless data is inherently wide (then offer expand-to-modal).

### Streaming markdown and code blocks

Streaming content grows unpredictably. Container-aware rules:

```css
.prose pre {
  max-width: 100%;
  overflow-x: auto;
}

@container agent-chat (max-width: 480px) {
  .prose {
    font-size: 0.9375rem;
    line-height: 1.55;
  }

  .prose pre {
    font-size: 0.8125rem;
  }
}
```

Avoid animating width-dependent properties on every token—prefer stable font-size steps at container breakpoints, not continuous reflow.

## React component structure

Colocate container styles with agent UI components. Example shell:

```tsx
export function AgentChatPanel({ children }: { children: React.ReactNode }) {
  return (
    <div className="agent-chat-shell" data-testid="agent-chat-shell">
      <div className="agent-chat-transcript">{children}</div>
      <AgentComposer />
    </div>
  );
}
```

```css
/* agent-chat.module.css */
.agent-chat-shell {
  container-type: inline-size;
  container-name: agent-chat;
  display: flex;
  flex-direction: column;
  min-height: 0; /* allow flex shrink in embeds */
  height: 100%;
}
```

When the same `ToolResultCard` renders in full-page and sidebar contexts, it inherits the nearest container—no prop drilling for `isNarrow`.

## Embeds, iframes, and shadow DOM

Third-party embeds should ship self-contained CSS with container queries—host pages should not need application-specific breakpoints.

For shadow DOM widgets:

```javascript
const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host {
    display: block;
    height: 100%;
  }
  .root {
    container-type: inline-size;
    container-name: widget;
  }
  @container widget (max-width: 420px) {
    .composer textarea { min-height: 2.5rem; }
  }
`);
shadow.adoptedStyleSheets = [sheet];
```

Test embeds at host widths host apps actually use—Salesforce, Zendesk, and Notion sidebar widths differ.

## Fallbacks and progressive enhancement

Container query support is broad in modern browsers but not universal in locked-down enterprise environments. Pattern:

```css
.message-row {
  /* fallback: stack on small viewport */
  grid-template-columns: 1fr;
}

@media (min-width: 768px) {
  .message-row {
    grid-template-columns: auto 1fr;
  }
}

@container agent-chat (min-width: 520px) {
  .message-row {
    grid-template-columns: auto 1fr;
  }
}
```

Viewport fallback provides baseline; container query overrides when containment is available—embedded narrow panels get correct layout even on desktop viewports.

Feature detection:

```css
@supports (container-type: inline-size) {
  .agent-chat-shell { container-type: inline-size; }
}
```

## Testing responsive agent UI

Automated visual regression should resize **container**, not only viewport:

```typescript
test("tool card stacks fields in narrow container", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/agent-demo");
  await page.locator('[data-testid="agent-chat-shell"]').evaluate((el) => {
    (el as HTMLElement).style.width = "360px";
  });
  await expect(page.locator(".tool-fields")).toHaveScreenshot("tool-narrow.png");
});
```

Storybook 8+ supports container query decorators—define stories at 320, 480, and 720px container widths alongside full viewport stories.

Manual QA checklist:

- Sidebar embed at 320px and 400px
- Split pane resize drag mid-conversation
- Long German tool labels without overflow clip
- Streaming message through container breakpoint boundary

## Performance considerations

Container queries recalculate when container size changes—split pane drags can fire many layout passes. Mitigations:

- Avoid expensive `size` containment unless needed
- Debounce non-critical layout-dependent JS reads
- Use `content-visibility: auto` on off-screen transcript segments in long threads

Do not nest deep container trees unnecessarily—each level adds style invalidation cost during resize.

## Accessibility in responsive agent layouts

When avatars hide in narrow containers, preserve speaker identity for screen readers:

```css
@container agent-chat (max-width: 480px) {
  .message-avatar { display: none; }
}
```

```html
<article aria-labelledby="msg-42-author">
  <span id="msg-42-author" class="visually-hidden">Assistant said</span>
  ...
</article>
```

Touch targets in narrow composers must stay ≥44px. Container shrink should not collapse send buttons below usable size—wrap actions vertically instead.

## Container query units: cqw, cqh, and cqi

Beyond breakpoint-style `@container (max-width: 480px)` rules, container query length units express sizes relative to the container itself:

```css
.tool-card-title {
  font-size: clamp(0.875rem, 2.5cqw + 0.5rem, 1.125rem);
}

.citation-chip {
  max-width: 40cqw;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

`cqw` is one percent of the query container's width—useful for citation chips and inline badges that should scale smoothly as users drag split-pane dividers without jumping between media-query steps. Pair `clamp()` with container units to avoid unreadably small text in very narrow embeds while capping growth in wide panels. Test `cqi` (inline axis) if you ship RTL locales where inline direction differs from physical width.

## Related concepts

Container queries pair with [partial hydration islands](https://blog.michaelsam94.com/agent-partial-hydration-islands/) for embeddable agent widgets and [motion-reduced preferences](https://blog.michaelsam94.com/agent-motion-reduced-preferences/) when layout shifts animate.

## The takeaway

Agent UIs live in containers users resize, embed, and split—not viewports designers pick. `@container` lets chat threads, tool cards, and streaming markdown adapt to real available width. Establish named containment on chat shells and cards, provide viewport fallbacks for legacy environments, and test by resizing the panel—not just the browser window.

## Field checklist for container queries responsive

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.

## Resources

- [MDN: CSS container queries](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries) — syntax and containment fundamentals
- [web.dev: Container queries land in stable browsers](https://web.dev/blog/container-queries-stable) — rollout and migration guidance
- [CSS Containment Module Level 3](https://www.w3.org/TR/css-contain-3/) — specification
- [Storybook container query addon patterns](https://storybook.js.org/blog/) — component-level responsive testing
- [Inclusive Components responsive patterns](https://inclusive-components.design/) — accessible layout switching
