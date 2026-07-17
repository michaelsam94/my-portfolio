---
title: "View Transitions in Agent SPAs and Multi-Page Apps"
slug: "agent-view-transitions-spa-mp"
description: "Use the View Transitions API for agent UI navigation: shared element transitions between chat and settings, MPA vs SPA tradeoffs, and fallbacks when streaming content updates mid-transition."
datePublished: "2025-05-05"
dateModified: "2026-07-17"
tags: ["AI Agents", "Frontend", "CSS", "UX"]
keywords: "view transitions API agent UI, SPA MPA agent portal, shared element transition chat, document startViewTransition"
faq:
  - q: "Should agent portals use View Transitions for every route change?"
    a: "No — reserve for high-frequency navigations users perform repeatedly: chat ↔ history, chat ↔ agent settings, thread ↔ tool detail. One-off admin pages don't benefit; motion fatigue sets in. Keep transitions under 300ms."
  - q: "Do View Transitions work with SSR and MPAs?"
    a: "Cross-document view transitions (Chrome 126+) enable MPA transitions with `@view-transition` meta and matching `view-transition-name` on shared elements. SPAs use `document.startViewTransition()` in JS. Agent portals on Next.js can mix both."
  - q: "What happens if agent tokens stream during an active transition?"
    a: "DOM mutations mid-transition cause jank or aborted animations. Pause scroll-to-bottom on chat container until `transition.finished`, or exclude streaming message list from named transition elements. Prefer transitioning chrome (header, sidebar) not token stream."
  - q: "Fallback for Safari and Firefox?"
    a: "Feature detect `document.startViewTransition`; instant navigation without animation. Don't polyfill with heavy JS layout thrashing — degraded instant swap is fine. ~70% Chrome coverage is enough for enhancement, not dependency."
---

Agent UIs jump between chat, run history, tool traces, and billing settings — hard cuts make the product feel like four different apps stitched in a hurry. The **View Transitions API** gives you shared-element morphs and cross-fade page swaps with browser-composited animations, not React state fighting CSS transitions. Agent-specific wrinkle: SSE token streams mutate the DOM while transitions expect stable snapshots.

## SPA vs MPA for agent portals

| Pattern | Pros for agents | View Transition approach |
|---------|-----------------|--------------------------|
| SPA (Vite/React) | Instant thread switch, WS reuse | `startViewTransition()` + client router |
| MPA (Next.js app router) | SEO for docs, simpler data boundaries | Cross-document + `@view-transition` |
| Hybrid | Chat SPA in shell, settings MPA | Named elements on layout shell only |

Most production agent dashboards are SPA-heavy for chat; use MPA transitions only on marketing/docs boundaries.

## Basic SPA transition wrapper

```typescript
function navigateWithTransition(
  callback: () => void,
  options?: { skipTransition?: boolean }
) {
  if (options?.skipTransition || !document.startViewTransition) {
    callback();
    return;
  }
  document.startViewTransition(() => {
    callback();
  });
}

// React Router example
function useTransitionNavigate() {
  const navigate = useNavigate();
  return (to: string) => {
    navigateWithTransition(() => navigate(to));
  };
}
```

CSS defaults cross-fade root snapshot old/new — customize:

```css
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 250ms;
  animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
```

## Shared element: agent avatar sidebar → settings header

Assign matching `view-transition-name`:

```tsx
// ChatSidebar.tsx
<img
  src={agent.avatarUrl}
  alt=""
  style={{ viewTransitionName: "agent-avatar" }}
/>

// SettingsHeader.tsx — same name
<img
  src={agent.avatarUrl}
  alt=""
  style={{ viewTransitionName: "agent-avatar" }}
/>
```

Browser morphs position/size between routes automatically when names match.

## Excluding streaming content

Chat message list grows every 50ms during generation — do **not** name-transition the list:

```tsx
<div className="chat-chrome" style={{ viewTransitionName: "chat-shell" }}>
  <AgentHeader agent={agent} style={{ viewTransitionName: "agent-header" }} />
  <MessageList
    messages={messages}
    /* no viewTransitionName — live region */
    aria-live="polite"
  />
</div>
```

Gate auto-scroll during transition:

```typescript
const transitionNavigate = useTransitionNavigate();

useEffect(() => {
  if (document.startViewTransition) {
    const vt = (document as any).activeViewTransition;
    if (vt) {
      vt.finished.then(() => scrollToBottom());
      return;
    }
  }
  scrollToBottom();
}, [messages]);
```

## Cross-document MPA transitions

Enable on both pages:

```html
<!-- layout.html -->
<meta name="view-transition" content="same-origin" />
```

```css
/* shared-styles.css */
.agent-sidebar-logo {
  view-transition-name: agent-logo;
}
```

Same-origin requirement: chat.example.com → settings.example.com needs same site; subdomains require consistent policy.

Next.js App Router — opt in per layout:

```tsx
export default function AgentLayout({ children }) {
  return (
    <>
      <meta name="view-transition" content="same-origin" />
      <aside className="agent-sidebar-logo">...</aside>
      {children}
    </>
  );
}
```

## Transition vs agent state persistence

SPA transitions don't unmount WebSocket/SSE if layout route persists — good. Full page MPA transitions tear down streams — reconnect on `pageshow`:

```typescript
window.addEventListener("pageshow", (e) => {
  if (e.persisted) reconnectAgentStream(sessionId);
});
```

Persist `sessionId` in `sessionStorage` for bfcache restore.

## Accessibility

- Respect `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation: none !important;
  }
}
```

- Focus management: move focus to `h1` on new route after `transition.finished`.
- Don't rely on motion alone for state change — announce route change to screen readers.

## Performance notes

View transitions capture DOM snapshots — expensive on huge DOMs. Agent chat with 10k messages: virtualize list **before** enabling transitions, or transition only layout chrome.

DevTools → Rendering → "Show view transition snapshots" for debugging stuck transitions.

## Testing

```typescript
test("navigates chat to settings with transition", async ({ page }) => {
  await page.goto("/chat/agent-1");
  await page.click('[data-testid="settings-link"]');
  await expect(page).toHaveURL("/settings/agent-1");
  await expect(page.locator("h1")).toContainText("Agent Settings");
});
```

Visual regression on transition mid-frame is flaky — assert final state, optional Percy on `transition.finished` hook in test harness.

## Resources

- [MDN — View Transition API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)
- [Chrome Developers — Cross-document view transitions](https://developer.chrome.com/docs/web-platform/view-transitions/cross-document)
- [web.dev — Smooth transitions with the View Transitions API](https://web.dev/articles/view-transitions)
- [React Router — future.v7_startTransition integration patterns](https://reactrouter.com/)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

