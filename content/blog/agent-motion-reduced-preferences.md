---
title: "AI Agents: Motion Reduced Preferences"
slug: "agent-motion-reduced-preferences"
description: "Agent UIs that stream, pulse, and animate can trigger vestibular symptoms. Honor prefers-reduced-motion at every layer—from CSS to tool status indicators—without stripping useful feedback."
datePublished: "2026-06-30"
dateModified: "2026-06-30"
tags: ["AI", "Agent", "Motion"]
keywords: "prefers-reduced-motion, vestibular accessibility, agent UI, streaming chat animation, WCAG motion, reduced motion React, a11y CSS"
faq:
  - q: "Does prefers-reduced-motion mean removing all animation?"
    a: "No. It means replacing motion that conveys no essential information, and swapping continuous or large movement for instant state changes or subtle opacity shifts. Progress can remain visible through text and static bars rather than pulsing shimmer effects."
  - q: "Where do agent interfaces most often violate motion preferences?"
    a: "Streaming token fade-ins, bouncing typing indicators, parallax tool cards, auto-scrolling message lists, and celebratory confetti on task completion. Each feels minor in isolation; together they dominate the viewport during long sessions."
  - q: "Should reduced motion follow OS setting or an in-app toggle?"
    a: "Both. Respect the OS media query by default, and expose an in-app override stored in user preferences so browser support gaps and remote-desktop quirks do not leave people stuck with animations they cannot tolerate."
  - q: "How do we test agent motion accessibility?"
    a: "Automated tests can assert CSS variables and class toggles under emulated media queries. Manual testing with Reduce Motion enabled on macOS/iOS is mandatory for streaming layouts because scroll anchoring bugs only appear during live token arrival."
---
The first bug report did not mention accessibility. It said the agent chat "made me dizzy" during long troubleshooting sessions. Repro steps: open the copilot, watch the typing indicator bounce for ninety seconds while a tool call spinner pulsed, let the message list auto-scroll with elastic easing as tokens streamed in. The engineer who picked up the ticket could not reproduce—until they enabled **Reduce Motion** in macOS settings and realized the product never listened to it.

`prefers-reduced-motion` is not a niche media query. It is a medical accommodation for vestibular disorders, migraine triggers, and ADHD-related distraction sensitivity. Agent interfaces are motion-heavy by design: they signal liveness while waiting on slow models and tools. That liveness must not come at the cost of users who need stillness.

## What the platform actually exposes

Browsers surface the user's OS preference through CSS and JavaScript:

```css
/* Global agent shell tokens */
:root {
  --motion-duration-fast: 180ms;
  --motion-duration-medium: 320ms;
  --motion-ease: cubic-bezier(0.4, 0, 0.2, 1);
  --typing-indicator: typing-bounce 1.2s ease-in-out infinite;
  --stream-reveal: token-fade-in var(--motion-duration-fast) var(--motion-ease);
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-duration-fast: 0ms;
    --motion-duration-medium: 0ms;
    --typing-indicator: none;
    --stream-reveal: none;
  }
}
```

JavaScript can read the same preference for React components that animate via libraries rather than CSS:

```typescript
// hooks/usePrefersReducedMotion.ts
import { useEffect, useState } from "react";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  return reduced;
}
```

Safari and Chromium differ on when `change` fires across tabs—persist an explicit user override in local storage or your account profile and merge it with the media query result.

## Agent-specific motion hotspots

Standard marketing sites animate hero sections once. Agent sessions loop motion for minutes or hours. Prioritize these surfaces:

### Streaming text reveal

Token-by-token fade-in looks polished but creates constant flicker in the peripheral vision. Under reduced motion, render accumulated text immediately on each chunk boundary without opacity transitions:

```tsx
// components/AgentMessage.tsx
import { usePrefersReducedMotion } from "../hooks/usePrefersReducedMotion";

type Props = { content: string; isStreaming: boolean };

export function AgentMessage({ content, isStreaming }: Props) {
  const reducedMotion = usePrefersReducedMotion();

  if (reducedMotion) {
    return (
      <div className="agent-message" aria-live="polite">
        <p>{content}</p>
        {isStreaming && (
          <span className="sr-only">Response in progress</span>
        )}
      </div>
    );
  }

  return (
    <div className="agent-message agent-message--animated" aria-live="polite">
      <p className="agent-message__stream">{content}</p>
    </div>
  );
}
```

Pair with `aria-live="polite"` so screen reader users hear progress without visual motion.

### Typing and tool-status indicators

Replace bouncing dots with a static label: "Agent is thinking" or "Running `search_logs` (12s)." Show elapsed time as text; it helps every user, not only those avoiding motion.

```css
.tool-status--reduced {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.tool-status--reduced::before {
  content: "";
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--color-accent);
  /* static dot — no pulse keyframes */
}
```

### Auto-scroll behavior

Auto-scrolling chat is motion. When reduced motion is active, pin scroll position unless the user is already at the bottom—avoid animated `scrollIntoView({ behavior: "smooth" })`.

```typescript
export function scrollChatContainer(
  el: HTMLElement | null,
  reducedMotion: boolean
) {
  if (!el) return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  if (!atBottom) return; // respect reading position

  if (reducedMotion) {
    el.scrollTop = el.scrollHeight;
  } else {
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }
}
```

### Celebratory feedback

Confetti and success Lottie animations on completed agent tasks are high-amplitude motion. Swap for inline success text and optional sound off by default.

## Central motion policy in design tokens

Scattershot `@media` blocks rot quickly. Define a motion tier system consumed by all agent components:

| Tier | Default | Reduced motion |
|------|---------|----------------|
| **Essential** | Focus rings, opacity on disabled controls | Unchanged (accessibility-required) |
| **Informative** | Progress bars, step transitions | Instant jumps, no easing |
| **Decorative** | Shimmer skeletons, parallax | Removed entirely |

```typescript
// design/motionPolicy.ts
export type MotionTier = "essential" | "informative" | "decorative";

export function motionAllowed(tier: MotionTier, reduced: boolean): boolean {
  if (tier === "essential") return true;
  if (reduced) return false;
  return true;
}

export function durationMs(tier: MotionTier, reduced: boolean): number {
  if (!motionAllowed(tier, reduced)) return 0;
  return tier === "informative" ? 200 : 0;
}
```

Storybook stories should include a **Reduced motion** toolbar toggle that sets a global decorator, not a one-off CSS hack per component.

## Server-rendered and email agents

Not all agent UX is SPA. If you send actionable emails or SSE-powered static pages, inline styles cannot rely on media queries alone. Respect `Sec-CH-Prefers-Reduced-Motion` client hint where available, and honor stored user preference from your profile API when rendering HTML on the server:

```python
# render/agent_panel_html.py
def render_status_banner(user, tool_name: str) -> str:
    reduced = user.preferences.reduced_motion or user.client_hints.reduced_motion
    if reduced:
        return f'<p class="status">Running {tool_name}…</p>'
    return f'<p class="status animated-pulse">Running {tool_name}…</p>'
```

## Testing matrix

| Test | Pass criteria |
|------|---------------|
| Emulate `(prefers-reduced-motion: reduce)` in Playwright | No `animation-name` other than `none` on chat surfaces |
| macOS Reduce Motion manual pass | No parallax, bounce, or smooth scroll during 5-minute session |
| Screen reader + reduced motion | `aria-live` announces streaming without requiring visual motion |
| In-app toggle | Overrides OS setting both directions; persists reload |
| Performance | Removing decorative motion lowers main-thread time on low-end laptops |

Automated snapshot tests fail on animation frames—prefer computed-style assertions:

```typescript
test("agent chat disables decorative animation when reduced", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/agent");
  const animation = await page.locator(".typing-indicator").evaluate(
    (el) => getComputedStyle(el).animationName
  );
  expect(animation).toBe("none");
});
```

## Organizational habits that stick

- Add **motion review** to design crit checklist alongside color contrast.
- Document allowed keyframes in the design system; anything not listed is disallowed by default.
- Track support tickets tagged vestibular/motion—spikes after a flashy release mean regression.
- Train PMs that "delightful" micro-interactions in agent waiting states accumulate.

## Canvas, voice, and multimodal agent surfaces

Voice agents introduce motion on waveform visualizers and speaking avatars. Under reduced motion, replace oscillating waveforms with a static microphone icon and captioned transcript updates. Lip-synced avatars should freeze mouth movement while audio continues—users still hear progress without visual oscillation.

When agents render charts or diagrams (code execution tools, data viz), avoid animated draw-on effects. Render the final SVG frame immediately; let users expand sections manually. Map libraries often animate pan/zoom by default—pass `preferReducedMotion: true` into chart configs where supported.

Multimodal chat that embeds video previews should not autoplay loops in reduced-motion mode. Poster frames plus explicit play buttons respect both bandwidth and vestibular needs.

## Performance side effects worth measuring

Teams sometimes discover that disabling decorative motion improves battery life on laptops during hour-long agent sessions. Track CPU utilization before and after a reduced-motion rollout; the data helps justify accessibility work to stakeholders who only speak performance.

Motion reduced preferences are not a CSS footnote—they are part of how agent products respect sustained attention. Stream status, tool progress, and completion feedback can be clear and calm at the same time. Build the still version first; add motion only where it teaches something essential, and gate it behind policies that survive your next UI refresh.

## Resources

- [MDN: prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion) — media query reference and user preference semantics
- [WCAG 2.2: Animation from Interactions (2.3.3)](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html) — related accessibility guidance
- [WebAIM: Reducing Motion](https://webaim.org/articles/motion/) — practical overview for vestibular sensitivity
- [Apple Human Interface Guidelines: Motion](https://developer.apple.com/design/human-interface-guidelines/motion) — platform expectations for Reduce Motion settings
- [React Aria: usePrefersReducedMotion](https://react-spectrum.adobe.com/react-aria/usePrefersReducedMotion.html) — battle-tested hook patterns for component libraries
