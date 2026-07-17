---
title: "AI Agents: Internationalization Rtl Logical"
slug: "agent-internationalization-rtl-logical"
description: "Internationalization for agent UIs with RTL locales and CSS logical properties — bidirectional chat layouts, mirrored icons, locale-aware formatting, and testing Arabic and Hebrew agent surfaces without breaking LTR defaults."
datePublished: "2026-07-02"
dateModified: "2026-07-02"
tags: ["AI", "Agent", "Internationalization"]
keywords: "internationalization, RTL, logical properties, CSS inline-start, agent UI, bidirectional text, i18n, locale, Arabic, Hebrew, chat layout"
faq:
  - q: "Should agent chat UIs use physical CSS (left/right) or logical properties?"
    a: "Use logical properties — inline-start, inline-end, margin-inline, padding-inline, border-inline-start — so one stylesheet serves LTR and RTL. Physical left/right hardcodes direction and breaks when locale switches or when mixed-direction content (English product names in Arabic UI) appears inside bubbles."
  - q: "How do I handle RTL for streaming agent responses?"
    a: "Set dir on the message container from locale, not per-token. Stream text into a pre-established directional context; do not recompute dir on every chunk. For markdown rendering, sanitize and preserve Unicode bidi controls; avoid injecting LTR-only CSS into rendered HTML from the model."
  - q: "Which agent UI elements should mirror in RTL vs stay fixed?"
    a: "Mirror asymmetric navigation (back arrows, chevrons, send button alignment, tool call timelines). Do not mirror symmetric icons (play, search, close), numbers, code blocks, or latinate model output unless wrapped in dir=ltr spans. Media controls and charts generally stay LTR; labels use logical alignment."
  - q: "How should agents format dates, numbers, and currencies per locale?"
    a: "Use Intl APIs (Intl.DateTimeFormat, Intl.NumberFormat, Intl.RelativeTimeFormat) with the user's locale from auth or browser — never hardcode en-US. Store UTC in the backend; format at render. Currency follows user or tenant locale policy, not server region."
---
The agent dashboard shipped in English with `margin-left: 12px` on every chat bubble and a send icon pointing right. Enterprise rollout added Arabic and Hebrew tenants; messages aligned to the wrong edge, tool-call timelines read backwards, and mixed English SKUs inside RTL bubbles collapsed into unreadable bidi tangles. Fixing it required neither a full rewrite nor separate RTL CSS files — it required logical properties, explicit `dir` on conversational containers, and locale-aware formatting wired through the same component tree.

Internationalization for agent products is not translation alone. RTL locales expose every physical `left`/`right` assumption in chat layouts, streaming markdown, tool traces, and citation chips. Logical CSS and directional context make one UI code path serve global users.

## RTL fundamentals for conversational UI

**Direction** (`dir=rtl` or `dir=ltr`) sets the inline axis: start is right in RTL, left in LTR.

**Writing mode** defaults to horizontal-tb; vertical scripts are rare in agent UIs but `writing-mode` matters for CJK density tweaks.

**Unicode bidi** algorithm reorders mixed scripts automatically — but only if the DOM establishes correct directional isolates. An Arabic sentence containing `"SKU-90210-X"` needs surrounding context; otherwise Latin segments jump.

Agent chat differs from marketing pages:

- Continuous streaming updates text node content
- User and assistant bubbles share a thread with opposing alignment conventions
- Tool calls embed JSON, code, and citations with strong LTR bias
- Timestamps and avatars anchor to thread edges

Each pattern needs deliberate `dir` and logical layout — not accidental inheritance from `<html dir="ltr">`.

## Logical properties replace physical ones

Map physical habits to logical equivalents:

| Physical | Logical |
|----------|---------|
| `margin-left` | `margin-inline-start` |
| `margin-right` | `margin-inline-end` |
| `padding-left` | `padding-inline-start` |
| `text-align: left` | `text-align: start` |
| `left: 0` | `inset-inline-start: 0` |
| `border-left` | `border-inline-start` |
| `float: left` | avoid floats; use flex/grid |

```css
/* agent-chat/message.css */
.agent-message-row {
  display: flex;
  flex-direction: row;
  gap: 0.75rem;
  padding-inline: 1rem;
  margin-block-end: 0.5rem;
}

.agent-message-row--user {
  flex-direction: row-reverse; /* avatar + bubble; mirrors in RTL automatically */
}

.agent-bubble {
  border-inline-start: 3px solid var(--accent);
  padding-inline: 1rem;
  padding-block: 0.75rem;
  text-align: start;
  max-inline-size: 42rem;
}

.agent-composer {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-inline: 1rem;
  padding-block: 0.75rem;
  border-block-start: 1px solid var(--border);
}

.agent-composer__input {
  flex: 1;
  text-align: start;
}

.agent-composer__send {
  /* Icon mirrored via transform when dir=rtl if asymmetric */
  margin-inline-start: 0.25rem;
}
```

With logical properties, switching locale updates `dir` on `<html>` or a locale root — components reflow without duplicate rulesets.

## Establishing directional context in React

Set `dir` and `lang` together from the active locale:

```tsx
// i18n/LocaleRoot.tsx
import { useLocale } from "./useLocale";

const RTL_LOCALES = new Set(["ar", "he", "fa", "ur"]);

export function LocaleRoot({ children }: { children: React.ReactNode }) {
  const { locale } = useLocale();
  const dir = RTL_LOCALES.has(locale.split("-")[0]) ? "rtl" : "ltr";

  return (
    <div lang={locale} dir={dir} className="agent-app-root">
      {children}
    </div>
  );
}
```

Per-message override for known LTR payloads (code, JSON tool results):

```tsx
function ToolResultBlock({ content }: { content: string }) {
  return (
    <pre dir="ltr" className="agent-tool-result">
      <code>{content}</code>
    </pre>
  );
}
```

Do not set `dir="ltr"` on the entire assistant bubble when the natural language answer is Arabic — only isolate LTR subtrees.

## Streaming agent responses without bidi bugs

Streaming complicates bidi: browsers reshuffle glyphs as chunks arrive.

Guidelines:

1. Create the bubble element with correct `dir` before first token.
2. Append chunks to a single text node or marked span; avoid splitting words across elements.
3. For markdown renderers, run bidi isolation on finished blocks where possible; debounce re-parse during stream if needed.
4. Never strip Unicode isolates (U+2066–U+2069) in sanitization unless you replace them with HTML isolates.

```typescript
// stream/appendToken.ts
export function appendStreamToken(
  container: HTMLElement,
  token: string,
  localeDir: "ltr" | "rtl",
) {
  if (!container.dataset.initialized) {
    container.dir = localeDir;
    container.dataset.initialized = "true";
  }
  container.insertAdjacentText("beforeend", token);
}
```

If the model emits markdown with hardcoded `style="text-align:left"`, strip or override in post-processing — LLM output often assumes LTR English layout.

## Mirroring rules for agent chrome

**Mirror:** back arrows, disclosure chevrons, thread indentation gutters, progress timelines for multi-step tool plans, slide-over panels that enter from the inline-start edge.

**Do not mirror:** symmetric icons, logos, maps, charts, video controls, checkmarks (usually symmetric), numeric keypads.

For asymmetric SVG icons:

```css
[dir="rtl"] .icon-chevron-next {
  transform: scaleX(-1);
}
```

Prefer SVG `transform` over separate RTL assets unless the icon encodes direction semantically (e.g., text cursor).

Tool-call traces read chronologically top-to-bottom; order does not mirror — only horizontal alignment and connector lines use logical positioning.

## Locale-aware formatting with Intl

Agents surface times ("updated 3 minutes ago"), currency in billing tools, and large token counts.

```typescript
// i18n/format.ts
export function formatRelativeTime(
  date: Date,
  locale: string,
): string {
  const diffSec = Math.round((date.getTime() - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (Math.abs(diffSec) < 60) return rtf.format(diffSec, "second");
  const diffMin = Math.round(diffSec / 60);
  if (Math.abs(diffMin) < 60) return rtf.format(diffMin, "minute");
  const diffHr = Math.round(diffMin / 60);
  return rtf.format(diffHr, "hour");
}

export function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(value);
}
```

Server-side agent logs stay UTC. User-facing timestamps in the UI convert with `Intl.DateTimeFormat` and the tenant timezone preference — not the server's `TZ`.

## Translation keys and pluralization

Agent UI strings — "Send", "Regenerate", "Tool running…" — belong in ICU MessageFormat catalogs, not inline English.

```json
{
  "composer.send": "Send",
  "tool.status.running": "{count, plural, =0 {No tools running} one {# tool running} other {# tools running}}",
  "citation.source": "Source {index}"
}
```

RTL does not affect translation file structure; the same keys serve all locales. Avoid concatenating strings with variables in code (`"You have " + n + " messages"`) — plural and gender rules vary.

LLM system prompts are separate from UI i18n: localize the **interface**, and optionally run the model in the user's language — but do not assume translation of dynamic model output via UI string tables.

## Mixed-direction citations and mentions

RAG citations often embed English URLs and titles in Arabic answers. Wrap citations:

```html
<span dir="rtl" lang="ar">راجع </span>
<cite dir="ltr" lang="en">API Reference v2.3</cite>
<span dir="rtl" lang="ar"> للتفاصيل.</span>
```

In components, use `unicode-bidi: isolate` on citation chips:

```css
.agent-citation {
  unicode-bidi: isolate;
  direction: ltr; /* URLs and latinate titles */
  display: inline-block;
  margin-inline: 0.25rem;
}
```

## Testing RTL agent surfaces

Automated:

- Visual regression with `dir=rtl` snapshot per critical screen (Storybook stories with locale decorator)
- axe-core i18n rules for `lang` attribute presence
- Unit tests asserting logical CSS classes exist — no `ml-` Tailwind physical utilities on layout primitives unless mapped to logical plugin

Manual checklist:

- [ ] User and assistant bubbles align to correct inline edges
- [ ] Composer send control reachable thumb zone on mobile RTL
- [ ] Streaming long Arabic message without cursor jump
- [ ] Tool JSON blocks readable LTR inside RTL thread
- [ ] Date and number formats match locale (ar-SA vs ar-EG)
- [ ] Keyboard focus order follows visual reading order

Pseudo-locale (`en-XA` with lengthened strings) catches truncation; RTL screenshots catch alignment.

## Tailwind and design tokens

If using Tailwind, enable logical utilities or use plugins mapping `ms-` / `me-` / `ps-` / `pe-` consistently. Mixing physical `ml-4` on some components undoes locale switching.

Design tokens for spacing should name `inline-sm`, `block-md` — not `left-gutter`.

## Agent-specific pitfalls

**Suggested prompt chips** in LTR English below an RTL composer confuse scanning order — localize chips and lay out with flex `wrap` on logical axis.

**Voice input and IME** composition must not fight `dir` changes mid-composition.

**PDF or email export** from agent sessions needs explicit `dir` in HTML templates; browser screen RTL does not transfer to attachments automatically.

**Accessibility:** screen readers use `lang` and `dir` for pronunciation. Missing `lang` on Arabic UI is a WCAG failure independent of visual RTL.

## Performance and hydration in SSR agents

Next.js and similar frameworks must emit correct `dir`/`lang` on first HTML byte — otherwise RTL users see LTR flash (FOUC). Read locale from cookie or `Accept-Language` on server; pass to root layout.

Hydration mismatch occurs when client locale differs from server guess — prefer explicit user preference over browser default once logged in.

## Closing

Internationalization with RTL and logical properties is structural, not cosmetic. Agent chat UIs stream dynamic bidi text, embed LTR tool artifacts, and must mirror chrome without breaking numbers or code. One component tree with logical CSS, explicit directional isolates, and Intl formatting serves LTR and RTL tenants — provided you never shipped physical left/right as the layout foundation.

## Resources

- [MDN: CSS logical properties and values](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_logical_properties_and_values)
- [W3C Internationalization: Structural markup and right-to-left text](https://www.w3.org/International/questions/qa-html-dir)
- [Unicode TR9: Bidirectional Algorithm](https://unicode.org/reports/tr9/)
- [FormatJS / ICU MessageFormat syntax](https://formatjs.io/docs/core-concepts/icu-syntax/)
- [RTL styling on web.dev](https://web.dev/articles/building-rtl-aware-web-components)
