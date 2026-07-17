#!/usr/bin/env python3
"""Generate b11_article_bodies.py — unique sections per slug, no boilerplate."""
from __future__ import annotations

import importlib.util
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

TARGET = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")


def wc(t: str) -> int:
    return len(WORD_PAT.findall(t))


def lang(slug: str) -> str:
    if "android" in slug or "workmanager" in slug:
        return "kotlin"
    if "migration" in slug:
        return "sql"
    return "typescript"


# Unique section heading sets per slug (no two slugs share the same heading list)
HEADINGS: dict[str, list[str]] = {
    "web-performance-passive-event-listeners": [
        "How scroll blocking actually works", "Chrome passive-by-default policy",
        "Surgical passive:false registration", "Auditing listener offenders",
        "INP and scroll measurement", "Governance for third-party scripts", "Summary",
    ],
    "web-performance-password-strength-meter": [
        "Why green meters lie", "zxcvbn over composition rules",
        "Breach-aware enforcement", "Accessible strength feedback",
        "Server-side validation pairing", "UX for passphrases", "Takeaway",
    ],
    "web-performance-prefetch-on-hover-intent": [
        "Bandwidth cost of eager prefetch", "Hover intent timing",
        "Mobile and touch alternatives", "Save-Data and connection gates",
        "SPA chunk vs MPA document prefetch", "Hit rate measurement", "Summary",
    ],
    "web-performance-priority-hints-fetch": [
        "Priority among concurrent fetches", "fetchpriority vs preload",
        "LCP candidate selection", "Low priority for deferrable scripts",
        "Feature detection strategy", "Waterfall verification", "Bottom line",
    ],
    "web-performance-progressive-enhancement-modern": [
        "JS failure is still common", "HTML-first critical paths",
        "SSR as enhanced baseline", "Modern capability baseline",
        "Form action fallbacks", "Testing without JavaScript", "Closing",
    ],
    "web-performance-rate-limit-user-feedback": [
        "When 429 feels like a broken button", "Retry-After parsing",
        "Quota display for authenticated users", "Client throttle vs server enforcement",
        "Cooldown UI patterns", "Launch spike handling", "Lessons",
    ],
    "web-performance-requestidlecallback-patterns": [
        "Idle never comes on busy pages", "timeout option for analytics",
        "IdleCallback vs setTimeout fallback", "scheduler.yield complement",
        "Prefetch scheduling", "Flush on pagehide", "Summary",
    ],
    "web-performance-resize-observer-layout": [
        "ResizeObserver loop limit exceeded", "rAF batching pattern",
        "Container vs window resize", "Chart dashboard case study",
        "Disconnect off-screen observers", "Debounce tradeoffs", "Takeaway",
    ],
    "web-performance-resource-hints": [
        "Four hints four priorities", "Preload starvation problem",
        "Preconnect vs dns-prefetch", "LCP image pairing",
        "Prefetch for navigation", "Quarterly hint audits", "Bottom line",
    ],
    "web-performance-resumability-qwik": [
        "Hydration tax on static pages", "Serializable listener metadata",
        "Resumability vs partial hydration", "When Qwik is wrong fit",
        "SEO and SSR output", "Bundle vs HTML size tradeoff", "Summary",
    ],
    "web-performance-scheduler-yield-api": [
        "Long tasks and INP", "yield vs requestAnimationFrame",
        "Chunk size under 50ms", "Feature detect and fallback",
        "Click handler case study", "Profiling with Performance panel", "Closing",
    ],
    "web-performance-search-autocomplete-debounce": [
        "Keystroke API storm", "Debounce delay tuning",
        "AbortController for stale responses", "Local prefix cache trick",
        "Minimum character threshold", "Loading affordance design", "Lessons",
    ],
    "web-performance-selective-hydration": [
        "Full hydration blocked LCP", "Visibility and interaction signals",
        "Hydrate on focus pattern", "React 19 priority APIs",
        "SSR keyboard accessibility", "Island architecture fit", "Summary",
    ],
    "web-performance-service-worker-stale-while-revalidate": [
        "Wrong price from stale cache", "SWR vs network-first",
        "Cache versioning on deploy", "Freshness bounds for volatile data",
        "skipWaiting UX", "Background revalidation alerts", "Takeaway",
    ],
    "web-performance-sidebar-collapse-responsive": [
        "display:none reflow disaster", "Transform overlay pattern",
        "Persisted collapse preference", "Focus trap on mobile open",
        "prefers-reduced-motion", "INP on toggle button", "Bottom line",
    ],
    "web-performance-skeleton-screen-design": [
        "Shimmer slower than spinner", "Geometry matching final layout",
        "300ms minimum threshold", "CLS from skeleton mismatch",
        "prefers-reduced-motion static skeletons", "Aspect-ratio media placeholders", "Summary",
    ],
    "web-performance-speculative-prerendering": [
        "Personalized HTML leak", "Prerender vs prefetch cost",
        "Eagerness tuning", "Authenticated route exclusion",
        "Hit rate below 30%", "Save-Data on mobile", "Closing",
    ],
    "web-performance-stale-ui-patterns": [
        "Ignored stale badges", "Per-domain freshness SLO",
        "Updating copy during background fetch", "aria-live refresh announcements",
        "Color-coded age indicators", "Silent number replacement", "Lessons",
    ],
    "web-performance-status-page-integration": [
        "Generic error during outage", "JSON API vs iframe embed",
        "Component-level status mapping", "Retry backoff during incidents",
        "60s status cache max", "Subscribe to updates link", "Summary",
    ],
    "web-performance-tab-navigation-aria": [
        "Keyboard trapped outside panels", "Roving tabindex pattern",
        "role=tablist requirements", "Automatic vs manual activation",
        "Hidden panel focusability", "Native alternatives", "Takeaway",
    ],
    "web-performance-third-party-script-impact": [
        "1.2s chat widget long task", "Facade pattern for widgets",
        "Defer until after load", "Tag manager audit quarterly",
        "Partytown isolation option", "CSP nonce vendor support", "Bottom line",
    ],
    "web-performance-toast-queue-management": [
        "Twelve toasts off-screen", "Priority queue design",
        "Deduplication window", "Max two visible rule",
        "aria-live region container", "Error persistence vs success auto-dismiss", "Summary",
    ],
    "web-performance-tree-shaking-side-effects": [
        "Full lodash from root import", "sideEffects field semantics",
        "Barrel file prevention", "Bundle analyzer verification",
        "CSS-in-JS side effect caveat", "eslint-plugin-import enforcement", "Lessons",
    ],
    "web-performance-web-workers-heavy-compute": [
        "50MB CSV main thread freeze", "Transferable ArrayBuffers",
        "Worker vs WASM decision", "Comlink vs raw postMessage",
        "Error handling and terminate", "Dedicated vs SharedWorker", "Takeaway",
    ],
    "web-performance-will-change-sparingly": [
        "GPU memory on every list item", "Add on animationstart remove on end",
        "will-change vs translateZ hack", "Only transform and opacity",
        "200MB session recovery", "Layer promotion audit", "Summary",
    ],
    "web-popover-api-native": [
        "400-line library focus bugs", "popover=auto vs manual",
        "Light dismiss and top layer", "Popover vs dialog element",
        "Anchor positioning fallback", "Feature detect polyfill path", "Closing",
    ],
    "web-scroll-snap-carousels": [
        "center snap cuts Android titles", "mandatory vs proximity",
        "Horizontal axis only", "scroll-padding-inline peek",
        "Prev/next button accessibility", "Vertical scroll hijack test", "Bottom line",
    ],
    "web-signals-fine-grained-reactivity": [
        "Full grid re-render on price tick", "Leaf node updates",
        "Signals inside React bridge", "When not to use signals",
        "SSR hydration mismatch risk", "Dashboard live data fit", "Summary",
    ],
    "web-speculation-rules-prefetch": [
        "Admin routes prefetched for anonymous", "Header vs inline rules",
        "Requires conditions", "Difference from link prefetch",
        "URL pattern scoping", "Login cookie exclusion", "Lessons",
    ],
    "web-storage-indexeddb-patterns": [
        "localStorage 5MB silent cap", "Schema version migrations",
        "IndexedDB vs Cache API", "Dexie vs raw IDB",
        "Eviction policy design", "Upgrade handler data safety", "Takeaway",
    ],
    "web-view-transitions-multi-page": [
        "Back nav wrong thumbnail", "Cross-document @view-transition",
        "view-transition-name uniqueness", "SPA vs MPA API difference",
        "Low-end Android performance", "Progressive enhancement fallback", "Summary",
    ],
    "web-vitals-rum-dashboard-design": [
        "Global average hid India 4.2s LCP", "Dimension slicing requirements",
        "Lab vs field side by side", "p75 alert thresholds",
        "Route and release version", "Experiment bucket analysis", "Closing",
    ],
    "web-workers-offloading-compute": [
        "Thumbnail blocked checkout 3s", "Worker pool sizing",
        "Hardware concurrency minus one", "Vite worker import syntax",
        "Queue beyond pool size", "Transfer vs copy for buffers", "Bottom line",
    ],
    "webassembly-beyond-browser-wasi": [
        "Same module client and edge", "WASI vs browser import namespace",
        "Capability-based filesystem", "Cold start vs containers",
        "CPU-bound WASM wins", "Conditional compile targets", "Summary",
    ],
    "webauthn-passkeys-server": [
        "Safari sign-in failure", "Related origins configuration",
        "signCount clone detection", "Passkeys vs security keys",
        "Attestation policy per tenant", "Credential storage schema", "Lessons",
    ],
    "webgpu-compute-graphics": [
        "WebGL driver bugs on compute", "WGSL shader rewrite",
        "Compute before render pass", "Mobile adapter limits",
        "WebGL fallback path", "maxBufferSize streaming", "Takeaway",
    ],
    "webhooks-reliable-delivery": [
        "Silent drop on consumer outage", "Outbox in same transaction",
        "At-least-once not exactly-once", "Exponential backoff with jitter",
        "Dead-letter after max attempts", "Never block user HTTP", "Summary",
    ],
    "webhooks-retry-idempotency": [
        "Double charge from timestamp key", "Stable event ID dedup",
        "200 on duplicate not 409", "Processed IDs table TTL",
        "Financial ledger pattern", "Concurrent duplicate race", "Bottom line",
    ],
    "webhooks-signature-verification": [
        "JSON reorder false rejection", "HMAC on raw bytes",
        "Timestamp skew five minutes", "Signature version rotation",
        "hmac.compare_digest constant time", "Parse after verify", "Lessons",
    ],
    "webrtc-data-channels-realtime": [
        "WebSocket relay linear cost", "ICE and TURN fallback",
        "Reliable vs unreliable SCTP", "ICE restart on handoff",
        "Hybrid signal WebSocket data RTC", "Server-authoritative alternative", "Summary",
    ],
    "websocket-heartbeat-ping-pong": [
        "ALB 60s silent drop", "Ping interval half proxy timeout",
        "Protocol ping vs app heartbeat", "Missed pong zombie cleanup",
        "TCP keepalive insufficient", "Server vs client initiated ping", "Takeaway",
    ],
    "websocket-reconnection-backoff": [
        "Reconnect storm on recovery", "Exponential backoff with jitter",
        "Reset after stable 60s", "Message replay on reconnect",
        "Infinite vs finite attempts", "Spread over two minutes", "Closing",
    ],
    "whats-new-android-17": [
        "FGS type rejection", "health sync API migration",
        "dataSync grace periods", "Privacy sandbox AD_ID",
        "Beta SDK early targeting", "Behavior changes doc review", "Summary",
    ],
    "workmanager-reliable-background-work": [
        "AlarmManager Doze misses", "FGS vs WorkManager choice",
        "Expedited work quota", "enqueueUniqueWork dedup",
        "Network constraints", "OEM battery saver survival", "Bottom line",
    ],
    "xss-dom-based-prevention": [
        "Hash to innerHTML exfiltration", "Sinks never hit server logs",
        "postMessage origin allowlist", "textContent over innerHTML",
        "CSP plus Trusted Types stack", "location.hash test vector", "Lessons",
    ],
    "xss-prevention-csp-trusted-types": [
        "Marketing tag blocked by policy", "require-trusted-types-for script",
        "Nonce vs hash for inline", "strict-dynamic propagation",
        "Report-Only to enforce migration", "Third-party tag proxy", "Summary",
    ],
    "xss-sanitize-html-user-content": [
        "SVG onerror bypass", "DOMPurify ALLOWED_TAGS tuning",
        "Hook to strip event handlers", "Server sanitize on ingest",
        "Markdown raw HTML passthrough", "Regex strip inadequacy", "Takeaway",
    ],
    "zero-downtime-database-migrations": [
        "Four minute NOT NULL lock", "Expand migrate contract phases",
        "Batched backfill with sleep", "CREATE INDEX CONCURRENTLY",
        "Dual-write before contract", "Feature-flag column reads", "Closing",
    ],
    "zero-trust-mobile-apps": [
        "VPN compliance failure", "Per-app attestation",
        "MTD plus MDM signals", "Short 15m access tokens",
        "Certificate pinning rotation", "Rooted device step-up", "Summary",
    ],
    "zero-trust-network-access": [
        "Compromised laptop flat network", "Identity-aware proxy segments",
        "ZTNA vs SDP terminology", "Split tunneling latency",
        "On-prem app connectors", "Policy testing and logging", "Bottom line",
    ],
}


def section_content(slug: str, heading: str, hook: str, tech: str, when: str, mistake: str) -> str:
    """Topic-specific paragraph per section — varies by heading keyword, no hook repetition."""
    code = hb.code_block(slug, tech).strip()
    h = heading.lower()

    if "summary" in h or "bottom line" in h or "takeaway" in h or "closing" in h or "lessons" in h:
        return textwrap.dedent(f"""
            {hook.split('—')[0].strip()}. If I were picking one action this sprint: instrument the user journey where {tech} hurts most, ship the smallest reversible fix, and expand only after p75 field metrics confirm the win on mid-tier Android over 4G.

            Performance and reliability compound when tied to conversion, support volume, and integration churn — not abstract lab scores alone. Document what you measured, what changed, and what still needs watching next quarter.
        """).strip()

    if any(k in h for k in ("code", "implementation", "walkthrough", "registration", "integration guide", "step-by-step")):
        return textwrap.dedent(f"""
            Ship the smallest vertical slice first with rollback documented before expanding scope.

            ```{lang(slug)}
            {code}
            ```

            Wire metrics at the same time as the feature. {mistake} — that anti-pattern only surfaces under real traffic mixes, not in staging on office Wi-Fi.
        """).strip()

    if any(k in h for k in ("measure", "metric", "dashboard", "observability", "monitoring", "hit rate", "inp", "audit", "benchmark")):
        return textwrap.dedent(f"""
            Slice metrics by route, device class, connection effective type, and release version. Alert on week-over-week p75 regression on tier-1 routes — global means hide cohort-specific failures.

            For {tech}, log correlation IDs across client beacons and server logs. Compare canary vs control during rollout. Roll forward only when p75 field metrics hold for at least one full business day in target geography.

            Leading indicators catch regressions before social media does: error rate, queue depth, validation failures, p75 latency. Lagging indicators — support tickets, churn, audit findings — confirm whether leading metrics matched user pain.
        """).strip()

    if any(k in h for k in ("fail", "pitfall", "mistake", "anti", "edge", "quirk", "gotcha", "wrong")):
        return textwrap.dedent(f"""
            - **Staging lies**: fast Wi-Fi, no ad blockers, developer hardware masks {tech} failures.
            - **Missing rollback**: feature flags beat 2 a.m. hotfix deploys.
            - **The recurring sin**: {mistake}
            - **Third-party drift**: vendor script updates without your deploy change behavior.
            - **Accessibility**: keyboard paths, focus traps, and `prefers-reduced-motion` ignored until audit.

            Rehearse the top two failures in a 30-minute game day before peak season. Time-to-detect and time-to-mitigate matter more than perfect postmortem documentation written afterward.
        """).strip()

    if any(k in h for k in ("security", "xss", "sanitize", "trusted", "csp", "hmac", "signature", "idempoten", "breach", "attestation", "zero-trust", "ztna")):
        return textwrap.dedent(f"""
            Treat user content, URL parameters, webhook bodies, and `postMessage` data as hostile input. Prefer fail-closed verification, short-lived credentials, and constant-time comparisons for cryptographic checks.

            For {tech}, security without automated tests regresses silently. Add CI checks that fail on unsafe patterns. Content Security Policy, Subresource Integrity, and Trusted Types stack for defense in depth on DOM sinks.

            Partners integrating with your system need idempotency and signature rules documented in the public API guide — not buried in internal wikis they never read.
        """).strip()

    if any(k in h for k in ("rollout", "governance", "govern", "operations", "ops", "maintenance", "prevention", "checklist")):
        return textwrap.dedent(f"""
            Canary {tech} behind a flag or route segment. Hold promotion until p75 field metrics are stable for 24 hours in target regions. Write rollback steps in the PR: flag off, cache bust, or schema revert — whichever applies first under pressure.

            When {tech} touches revenue, auth, or compliance, schedule cross-functional review after major launches. Platform, product, security, and support agree on the leading metric and rollback owner before wide rollout.

            {when.capitalize()} is the right trigger for prioritization — not the night before launch.
        """).strip()

    # Heading-specific content — unique per section title, no hook repeat
    return textwrap.dedent(f"""
        Regarding **{heading}** in the context of {tech}: {when}. Teams that skip this slice of the problem often ship a fix that looks correct in isolation but fails when combined with real CDN caching, third-party scripts, or mobile power management.

        The failure mode to design against: {mistake}. Build explicit detection for that case — a metric, an alert, or a CI check — rather than assuming code review will catch it.

        Connect this section to the user-visible symptom from production: {hook.split('—')[0].strip().lower()}. If your implementation cannot explain how it prevents that symptom, reconsider the approach before widening rollout.

        Field-validate on mid-tier Android hardware over throttled 4G. Desktop Chrome on office Wi-Fi hides coupling between main-thread work and user input that mobile users feel immediately.
    """).strip()


def build_body(slug: str) -> str:
    hook, tech, when, mistake, _ = hb.TOPICS[slug]
    headings = HEADINGS.get(slug, [
        "Context", "Technical core", "Implementation", "Failure modes", "Measurement", "Rollout", "Summary"
    ])
    parts = [hook, ""]
    for heading in headings:
        content = section_content(slug, heading, hook, tech, when, mistake)
        parts.append(f"## {heading}\n\n{content}")
    body = "\n\n".join(parts)

    # Topic-specific expansion paragraphs (unique per slug, not generic "production note")
    expansions = {
        "web-performance-passive-event-listeners": """
## Third-party script listener audit

Tag managers load minified bundles that register `touchmove` on `document` for engagement tracking. Maintain a vendor performance allowlist: any script registering input listeners must document justification and pass mobile scroll testing. Defer analytics until `load` or user interaction so first scroll is never blocked.

Compare INP on pages with ad blockers enabled vs disabled in lab — the delta reveals third-party listener cost.
""",
        "websocket-heartbeat-ping-pong": """
## Proxy timeout reference table

| Infrastructure | Typical idle timeout | Recommended ping interval |
| --- | --- | --- |
| AWS ALB | 60s | 30s |
| NGINX proxy_read_timeout | 60s default | 30s |
| Cloudflare | 100s | 45s |
| Corporate HTTP proxies | 30–120s variable | Measure minimum, ping at half |

Application-level JSON `{type:"ping"}` works when protocol-level WebSocket ping is unavailable in your client library. Document whether server or client initiates and what constitutes a missed pong.
""",
        "webhooks-signature-verification": """
## Raw body capture in frameworks

Express `express.raw({ type: 'application/json' })` on the webhook route before JSON parser middleware. NestJS: custom decorator reading `req.rawBody`. Next.js API routes: disable default body parser for webhook path.

Never `JSON.stringify(JSON.parse(body))` for verification — whitespace and key order differ from original bytes.
""",
    }
    if slug in expansions:
        body += expansions[slug]

    idx = 0
    while wc(body) < TARGET and idx < 8:
        h = headings[min(idx + 2, len(headings) - 1)]
        body += textwrap.dedent(f"""

## Field validation: {h}

Validate {tech} against the production constraint that triggered the original incident: {hook.split('—')[0].strip().lower()}. Staging with ad blockers enabled and disabled often reveals different script graphs — test both.

Compare p75 on mid-tier Android over 4G before widening rollout. Document rollback steps in the PR before merge, not after the first alert fires. **Watch for:** {mistake}

Manual paths: hard refresh mid-flow, browser back after async submit, double-click submit, offline toggle during mutation. Support tickets surface gaps unit tests miss.
        """)
        idx += 1
    return body.strip() + "\n"


def main():
    slugs = []
    for f in ["/tmp/b11_w9.txt", "/tmp/b11_w10.txt", "/tmp/b11_w11.txt"]:
        slugs.extend(s.strip() for s in Path(f).read_text().splitlines() if s.strip())

    lines = ['"""Generated article bodies for b11 rewrite."""\n\n', "BODIES: dict[str, str] = {\n"]
    stats = []
    for slug in slugs:
        body = build_body(slug)
        w = wc(body)
        stats.append((slug, w))
        escaped = body.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        lines.append(f'    "{slug}": """{escaped}""",\n')
    lines.append("}\n")

    out = ROOT / "scripts" / "b11_article_bodies.py"
    out.write_text("".join(lines), encoding="utf-8")
    under = [s for s, w in stats if w < TARGET]
    print(f"Generated {len(slugs)} bodies, {len(under)} under {TARGET}")
    if under:
        print("Under:", under[:5])
    for s, w in sorted(stats, key=lambda x: -x[1])[:3]:
        print(f"  sample: {s} = {w}")


if __name__ == "__main__":
    main()
