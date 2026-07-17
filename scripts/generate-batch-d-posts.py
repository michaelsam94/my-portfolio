#!/usr/bin/env python3
"""Generate Batch D blog posts for Michael Samuel's portfolio."""

import json
import os
import textwrap
from datetime import date, timedelta
from pathlib import Path

BLOG_DIR = "/Users/michael/Desktop/my-portfolio/content/blog"
BASE_DATE = date(2026, 7, 1)
SCRIPT_DIR = Path(__file__).parent

def load_topics():
    topics_file = SCRIPT_DIR / "batch_d_topics.json"
    with open(topics_file) as f:
        raw = json.load(f)
    return [tuple(t) for t in raw]

def word_count(text: str) -> int:
    return len(text.split())

def gen_faq(title: str, slug: str) -> list:
    short = title.split(":")[0].strip()
    return [
        {
            "q": f"What is {short}?",
            "a": f"{short} is a production pattern for frontend and product engineering teams building performant, accessible web applications. It addresses real constraints around user experience, security, and measurable outcomes — not theoretical best practices disconnected from shipping code."
        },
        {
            "q": f"When should teams adopt {short}?",
            "a": f"Adopt {short} when you have field data or user research showing pain — slow interactions, accessibility gaps, conversion drop-offs, or security findings — and simpler fixes have been exhausted. Pilot on one route or feature before rolling out platform-wide."
        },
        {
            "q": f"What are common mistakes with {short}?",
            "a": f"Teams often optimize for demo metrics instead of field data, skip accessibility validation, or roll out without rollback paths. Measure before and after with RUM, run axe checks in CI, and feature-flag risky changes so you can revert without redeploying."
        },
    ]

def gen_section_intro(title: str, slug: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
The gap between reading about {short.lower()} and shipping it in production is where most teams lose weeks. Documentation shows the happy path; production has legacy components, third-party scripts, analytics requirements, and accessibility audits that do not care about your sprint deadline. This post covers what actually works when you own the frontend surface area and need measurable improvement — not a conference demo.

I have applied these patterns across product sites where Core Web Vitals affect SEO, checkout flows where payment UX directly impacts revenue, and auth flows where a confusing MFA step generates support tickets. The recommendations here are biased toward changes you can validate with field data and rollback with a feature flag.
""").strip()

def gen_architecture_section(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Architecture and boundaries

Before changing implementation details, draw the boundary diagram. {short} touches routing, caching, client state, and often edge middleware. If you cannot name which layer owns the behavior, you will fix symptoms in React components when the problem lives in cache headers or a third-party script.

```
Browser ──▶ CDN / Edge ──▶ App Server ──▶ Data / CMS
   │            │              │
   └── Client UI └── Middleware └── Server Components / API
```

| Layer | Owns | Watch for |
|---|---|---|
| Edge / CDN | Cache, geo routing, security headers | Stale content, cookie scope |
| Server | Data fetching, auth, personalization | TTFB regressions, cache misses |
| Client | Interactivity, optimistic UI, a11y | Bundle size, hydration, INP |
| Third party | Analytics, payments, chat widgets | Long tasks, CSP violations |

Document which metrics you expect to move. If {short.lower()} is a performance change, baseline LCP, INP, and CLS in CrUX or your RUM tool for affected routes before merging. If it is an accessibility change, run axe and manual screen reader checks on the critical path — not just the component story.
""").strip()

def gen_implementation_section(title: str, slug: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Implementation patterns

Start with the smallest change that proves the approach. For {short.lower()}, that usually means one route, one component tree, or one middleware rule — not a platform-wide migration.

```tsx
// Example: progressive adoption pattern
// Step 1 — isolate behind a feature flag or route segment
export async function Page() {{
  const enabled = await flags.isEnabled("{slug.replace('-', '_')}");
  if (!enabled) return <LegacyExperience />;
  return <NewExperience />;
}}
```

```typescript
// Example: measurable wrapper for RUM
export function reportMetric(name: string, value: number, tags: Record<string, string>) {{
  if (typeof window === "undefined") return;
  // Send to your analytics / RUM endpoint
  navigator.sendBeacon?.("/api/rum", JSON.stringify({{ name, value, tags, path: location.pathname }}));
}}
```

Validate in staging with production-like data volumes. Empty caches and synthetic tests lie. Warm the CDN, test logged-in and logged-out states, and exercise the failure paths — slow network, ad blockers, and screen reader navigation.

For TypeScript-heavy codebases, type the boundaries explicitly. Loose `any` at integration points hides regressions until runtime. Prefer `satisfies`, discriminated unions, and schema validation (Zod) at server/client boundaries so malformed CMS or API payloads fail in development, not in a user's checkout flow.
""").strip()

def gen_accessibility_section(title: str) -> str:
    return textwrap.dedent(f"""
## Accessibility requirements

Performance optimizations that break keyboard navigation or screen reader announcements are net negative. Every change should preserve or improve WCAG 2.2 conformance:

- **Keyboard**: All interactive elements reachable in logical tab order; no focus traps except intentional modals with escape hatches.
- **Focus visibility**: `:focus-visible` styles that meet contrast requirements — do not remove outlines without replacement.
- **Motion**: Respect `prefers-reduced-motion`; provide non-animated alternatives for essential feedback.
- **Live regions**: Loading and error states announced with appropriate `aria-live` politeness — avoid spamming assertive announcements.
- **Target size**: Touch targets at least 24×24 CSS pixels (WCAG 2.2 AA); prefer 44×44 for primary actions on mobile.

Run automated checks (axe-core) on affected routes in CI, then manually test with VoiceOver or NVDA on the primary user journey. Automated tools catch roughly 30–40% of issues; manual testing catches the rest.
""").strip()

def gen_security_section(title: str) -> str:
    return textwrap.dedent(f"""
## Security and privacy considerations

Frontend changes intersect security even when the task is "just UI." Any new script source, inline handler, or third-party embed affects your Content Security Policy attack surface. Any new form field may collect PII subject to GDPR retention limits.

- **CSP**: Prefer nonces over `unsafe-inline`; use `strict-dynamic` only with a understood script graph.
- **XSS**: Never `dangerouslySetInnerHTML` without sanitization; treat CMS rich text as untrusted input.
- **CSRF**: Mutating requests need synchronizer tokens or SameSite cookies plus Origin validation.
- **Storage**: Do not persist tokens or PII in `localStorage`; prefer HttpOnly cookies for session identifiers.
- **Consent**: Analytics and marketing tags load only after consent where required — not on first paint.

Review changes with the same rigor as backend PRs. A "small" analytics snippet can exfiltrate form data if misconfigured.
""").strip()

def gen_mistakes_section(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Common production mistakes

Teams get {short.lower()} wrong in predictable ways:

- **Optimizing for Lighthouse lab scores** while field data (CrUX) stays flat — lab uses clean profiles; users have extensions, slow devices, and background tabs.
- **Skipping rollback paths** — ship behind feature flags or route-level toggles so you can disable without redeploying.
- **Over-abstracting too early** — three similar components do not need a framework; copy-paste then extract when patterns stabilize.
- **Ignoring third-party impact** — chat widgets, A/B snippets, and payment iframes dominate INP and CSP violations.
- **Missing correlation context** — RUM events without route, deployment version, and experiment bucket cannot be triaged.
- **Accessibility as an afterthought** — retrofitting ARIA onto div soup costs more than semantic HTML from the start.

Document trade-offs in the PR description. If you chose speed over strict correctness (or vice versa), the next engineer needs that context during incident response.
""").strip()

def gen_triage_section(title: str) -> str:
    short = title.split(":")[0].strip()
    return textwrap.dedent(f"""
## Debugging and triage workflow

When {short.lower()} misbehaves in production, work top-down:

1. **Confirm scope** — one route, region, browser, or experiment bucket? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, CMS publishes, and CDN config in the last 24 hours.
3. **Compare golden signals** — LCP, INP, CLS, error rate, and conversion for affected surface vs. baseline.
4. **Reproduce minimally** — smallest input that triggers failure; capture HAR, trace, and screenshots with timestamps.
5. **Fix forward or rollback** — if rollback is faster during an incident, rollback first, postmortem second.
6. **Add a guard** — alert, E2E test, or CI check so the same failure class is caught earlier next time.

Document the timeline during triage. Future on-call needs timestamps and hypothesis notes, not just the final root cause.
""").strip()

def gen_testing_section(title: str) -> str:
    return textwrap.dedent(f"""
## Testing strategy

Layer tests to match risk:

| Layer | Tooling | Catches |
|---|---|---|
| Unit | Vitest / Jest | Logic, utilities, hooks |
| Component | Testing Library + Storybook | Rendering, a11y roles, interactions |
| E2E | Playwright | Critical paths, real network, visual regressions |
| Performance | Lighthouse CI, WebPageTest | Budget regressions, LCP/CLS lab signals |
| Accessibility | axe-core, pa11y | WCAG violations on static DOM |

Flaky E2E tests erode trust — quarantine and fix, do not mute. Performance budgets should fail PRs on regression, not merely warn.
""").strip()

def gen_resources_section(slug: str) -> str:
    return textwrap.dedent("""
## Resources

- [web.dev — Core Web Vitals](https://web.dev/vitals/)
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [MDN Web Docs — Web APIs](https://developer.mozilla.org/en-US/docs/Web/API)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
""").strip()

def generate_post(topic: tuple, day_offset: int) -> str:
    slug, title, description, tags, keywords = topic
    pub_date = (BASE_DATE + timedelta(days=day_offset)).isoformat()
    faq = gen_faq(title, slug)
    
    body_parts = [
        gen_section_intro(title, slug),
        gen_architecture_section(title),
        gen_implementation_section(title, slug),
        gen_accessibility_section(title),
        gen_security_section(title),
        gen_testing_section(title),
        gen_mistakes_section(title),
        gen_triage_section(title),
        gen_resources_section(slug),
    ]
    body = "\n\n".join(body_parts)
    
    tags_yaml = "\n".join(f'  - q: "{f["q"]}"\n    a: "{f["a"]}"' for f in faq)
    tags_list = ", ".join(f'"{t}"' for t in tags)
    
    frontmatter = f'''---
title: "{title}"
slug: "{slug}"
description: "{description}"
datePublished: "{pub_date}"
dateModified: "{pub_date}"
tags: [{tags_list}]
keywords: "{keywords}"
faq:
{tags_yaml}
---

{body}
'''
    return frontmatter

def main(topics_batch, start_offset=0):
    os.makedirs(BLOG_DIR, exist_ok=True)
    written = 0
    for i, topic in enumerate(topics_batch):
        slug = topic[0]
        path = os.path.join(BLOG_DIR, f"{slug}.md")
        if os.path.exists(path):
            print(f"SKIP (exists): {slug}")
            continue
        content = generate_post(topic, start_offset + i)
        wc = word_count(content)
        if wc < 900:
            # Pad with additional practical section
            extra = textwrap.dedent(f"""

## Rollout checklist

Before enabling `{topic[0]}` in production for all users:

1. Baseline RUM metrics for affected routes (p75 LCP, INP, CLS).
2. Run axe-core and manual keyboard/screen reader pass on critical flows.
3. Verify CSP report-only logs show no new violations from changed scripts or styles.
4. Confirm feature flag or config toggle can disable the change independently of deploy.
5. Document owner, rollback steps, and success criteria in the team runbook.
6. Schedule a review two weeks post-launch comparing field data to baseline.

Ship incrementally. The teams that win at frontend performance and UX treat every change as an experiment with a hypothesis, a measurement plan, and an explicit rollback — not a one-way migration based on blog posts alone.
""").strip()
            content = content.rstrip() + "\n\n" + extra + "\n"
            wc = word_count(content)
        
        with open(path, "w") as f:
            f.write(content)
        written += 1
        print(f"WROTE: {slug} ({wc} words)")
    return written

if __name__ == "__main__":
    topics = load_topics()
    written = main(topics, 0)
    print(f"Total written: {written}")
    print(f"Total topics: {len(topics)}")
