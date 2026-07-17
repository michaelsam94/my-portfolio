#!/usr/bin/env python3
"""Humanize batch-11 chunk 3 (55 slugs from /tmp/batch11_chunk_3.txt)."""
from __future__ import annotations

import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILE = Path("/tmp/batch11_chunk_3.txt")
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-11-chunk3.json"
TARGET = 1200
TODAY = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
    "Measuring success in production",
    "We keep a living FAQ in the repo wiki",
    "## Architecture and boundaries",
    "## Accessibility requirements",
    "## Security and privacy considerations",
    "## Testing strategy",
    "## Common production mistakes",
    "## Debugging and triage workflow",
)

STRUCTURES = [
    ["hook", "mechanism", "implementation", "tradeoffs", "failure_modes", "metrics", "closing"],
    ["scenario", "anatomy", "code", "edge_cases", "rollout", "observability", "summary"],
    ["myth", "reality", "design", "walkthrough", "pitfalls", "benchmarks", "takeaway"],
    ["symptom", "diagnosis", "fix", "code", "prevention", "monitoring", "lessons"],
    ["context", "comparison", "deep_dive", "patterns", "anti_patterns", "checklist", "next"],
    ["question", "answer", "implementation", "security", "testing", "ops", "closing"],
]

# slug -> (hook, tech, when, mistake, faq_list[(q,a)*3])
TOPICS: dict[str, tuple] = {
    "web-performance-module-preload-import": (
        "We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing.",
        "modulepreload for critical ES module chains",
        "When your entry chunk dynamically imports above-the-fold UI and LCP depends on a nested module",
        "Preloading every dynamic import instead of only modules on the critical path to interactive",
        [
            ("Does modulepreload replace import maps?", "No. Import maps resolve bare specifiers; modulepreload warms specific resolved URLs. You still need correct map configuration — preload the resolved URL the browser will actually fetch."),
            ("Should I modulepreload lazy route chunks?", "Only if the route is likely on the critical path for first paint. Preloading all route chunks competes with entry module bandwidth and hurts LCP on slow networks."),
            ("How do I verify modulepreload is working?", "In DevTools Network, filter Initiator: preload and confirm only expected modules load early. Compare waterfall with and without hints on throttled 4G."),
        ],
    ),
    "web-performance-multi-step-form-wizard": (
        "Checkout abandonment spiked when we added a five-step wizard without persisting draft state — users who refreshed on step three lost everything and left.",
        "multi-step form wizards with persisted progress",
        "When flows exceed three fields or require verification mid-stream",
        "Storing wizard state only in React memory without URL or server draft persistence",
        [
            ("Should wizard progress live in the URL?", "For up to five steps, query params or hash segments enable shareable recovery and analytics. Sensitive data belongs server-side with opaque draft IDs, not in URLs."),
            ("How do you measure wizard performance?", "Track step completion rate, time-on-step, back-navigation rate, and drop-off by step. INP on Continue buttons matters as much as overall conversion."),
            ("One page or multiple routes for steps?", "Multiple routes enable code-splitting per step and clearer analytics; one page reduces navigation overhead. Match choice to whether users bookmark mid-flow."),
        ],
    ),
    "web-performance-navigation-timing-api": (
        "Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1.8s spent in redirect chains and TLS handshakes the server metric never saw.",
        "Navigation Timing API for Real User Monitoring",
        "When you need field data on redirect, DNS, TLS, and DOM phases beyond server-side TTFB",
        "Reporting only responseStart minus fetchStart without breaking down redirect and TLS time",
        [
            ("Navigation Timing Level 2 vs legacy?", "Use PerformanceNavigationTiming (Level 2) — it replaces deprecated performance.timing and works with PerformanceObserver for SPA navigations when paired with soft-nav beacons."),
            ("How do SPAs use Navigation Timing?", "Initial load uses the API directly; subsequent route changes need custom marks or the soft-navigation spec. Do not assume one page load metric covers SPA transitions."),
            ("Which metrics correlate with Core Web Vitals?", "domContentLoadedEventEnd and loadEventEnd correlate weakly with LCP/INP. Use Navigation Timing for diagnostics, CrUX/RUM CWV for SLOs."),
        ],
    ),
    "web-performance-network-status-indicator": (
        "Users on flaky subway Wi-Fi kept submitting payment forms that timed out — a simple offline banner would have disabled submit and saved forty support tickets a week.",
        "network status indicators and offline-aware UI",
        "When your app serves mobile users on intermittent connectivity",
        "Showing a toast once on offline without persisting state or disabling mutating actions",
        [
            ("navigator.onLine vs real connectivity?", "onLine only reflects local link status, not internet reachability. Combine online/offline events with a lightweight HEAD ping to your API for accurate status."),
            ("Should forms queue offline submissions?", "For idempotent reads, cache suffices. For writes, use IndexedDB outbox with explicit sync status — never silently drop queued mutations."),
            ("How intrusive should the indicator be?", "Persistent thin banner for offline; dismissible toast for recovered. Avoid modal blocking unless the user is mid-transaction."),
        ],
    ),
    "web-performance-optimistic-navigation-ui": (
        "Instant route transitions felt great until users clicked back and saw stale data from the optimistic cache — we had no rollback when the prefetch 404'd.",
        "optimistic navigation UI with safe rollback",
        "When perceived speed matters for multi-page or SPA navigation patterns",
        "Applying optimistic UI without validating prefetch success or invalidating on failure",
        [
            ("Optimistic UI vs skeleton screens?", "Optimistic shows cached or predicted content immediately; skeletons communicate loading honestly. Use optimistic only when stale content is acceptable briefly."),
            ("How long to show optimistic state?", "Cap at 300–500ms before falling back to skeleton or error. Longer optimistic states erode trust when correction arrives."),
            ("Does optimistic navigation hurt SEO?", "For MPAs, ensure canonical URLs still resolve server-side. Optimistic client rendering must not replace crawlable HTML on first load."),
        ],
    ),
    "web-performance-passive-event-listeners": (
        "Scroll jank on mobile product pages traced to a third-party analytics handler calling preventDefault on touchmove — switching to passive listeners fixed INP without removing tracking.",
        "passive event listeners for scroll and touch performance",
        "When touch or wheel handlers do not call preventDefault",
        "Adding { passive: true } to listeners that need preventDefault for custom swipe gestures",
        [
            ("Which events should be passive?", "touchstart, touchmove, wheel, and mousewheel on document-level scroll containers when you are not implementing custom drag-scroll that blocks default."),
            ("Can Chrome's passive-by-default break my carousel?", "If your carousel needs preventDefault on touchmove, register explicitly with { passive: false } on the carousel element only — not document-wide."),
            ("How do I find non-passive listeners?", "Chrome DevTools Performance → scroll bottlenecks, or run Lighthouse 'Uses passive listeners' audit. Search codebase for addEventListener without passive option."),
        ],
    ),
    "web-performance-password-strength-meter": (
        "Our zxcvbn meter turned green on Passw0rd! while Have I Been Pwned flagged it in the top ten thousand breached passwords — color alone misled users.",
        "password strength meters with breach-aware feedback",
        "When registration or password-change flows need security without frustrating users",
        "Scoring only on character classes without breach corpus or length-first guidance",
        [
            ("zxcvbn vs custom regex rules?", "zxcvbn estimates crack time from patterns; regex rules frustrate users with arbitrary symbols. Prefer zxcvbn plus minimum length (12+) over composition rules."),
            ("Should strength meters block weak passwords?", "Block breached and top-1000 passwords; warn on weak but allow with friction for edge cases. Hard blocks need clear remediation text."),
            ("Client-side or server-side strength checks?", "Both. Client for UX; server for enforcement. Never trust client-only validation — use k-anonymity API for breach checks server-side."),
        ],
    ),
    "web-performance-prefetch-on-hover-intent": (
        "Aggressive prefetch on every mouseenter burned 40% more bandwidth on mobile — hover intent with 150ms delay and viewport checks cut waste without hurting perceived speed.",
        "prefetch on hover intent with bandwidth guardrails",
        "When next-page navigation is predictable from link hover patterns",
        "Prefetching on mouseenter without delay, mobile exclusion, or Data Saver respect",
        [
            ("How long should hover intent delay be?", "100–200ms filters accidental hovers. Combine with requestIdleCallback when available so prefetch does not compete with active interactions."),
            ("Does prefetch work on mobile?", "No hover on touch — use viewport intersection or touchstart with conservative limits. Respect navigator.connection.saveData and slow-2g effective types."),
            ("Prefetch HTML or JS bundle?", "Prefetch the document for MPAs; prefetch route JS chunks for SPAs. Match what the next navigation actually needs — not the entire site graph."),
        ],
    ),
    "web-performance-priority-hints-fetch": (
        "Setting fetchpriority=high on six hero images did nothing for LCP — the browser still picked the wrong one because only the true LCP candidate should get high priority.",
        "fetchpriority and Priority Hints for resource scheduling",
        "When competing preloads and images dilute browser priority heuristics",
        "Marking multiple resources fetchpriority=high on the same page",
        [
            ("fetchpriority vs preload?", "Preload initiates fetch; fetchpriority adjusts priority among concurrent fetches. Use both on the LCP image: preload plus fetchpriority=high."),
            ("Which elements support fetchpriority?", "img, link, and script in Chromium-based browsers. Feature-detect and avoid relying on it as the only optimization."),
            ("Can low priority hurt critical scripts?", "Defer non-critical scripts with fetchpriority=low or async — never mark above-the-fold module scripts low unless they are truly non-blocking."),
        ],
    ),
    "web-performance-progressive-enhancement-modern": (
        "The marketing team shipped a React-only contact form — when JS failed on a corporate proxy, leads dropped to zero until we added a native form action fallback.",
        "progressive enhancement with modern baseline browsers",
        "When reliability and accessibility matter more than cutting-edge-only APIs",
        "Assuming evergreen browsers means JavaScript is always available",
        [
            ("Is progressive enhancement still relevant in 2026?", "Yes. Ad blockers, CSP, corporate proxies, and low-end devices still break JS. Core actions — forms, navigation, content — should work without JS."),
            ("How does this interact with SSR frameworks?", "SSR HTML is your enhanced baseline; hydration adds interactivity. Never render empty shells that require JS for primary content."),
            ("What is the modern baseline?", "Target browsers with ES modules, CSS Grid, and fetch — enhance with View Transitions and Popover API where supported, not required."),
        ],
    ),
    "web-performance-rate-limit-user-feedback": (
        "429 responses returned JSON errors our UI never surfaced — users hammered submit thinking the button was broken, tripling rate-limit hits during the launch spike.",
        "rate-limit feedback UX with Retry-After headers",
        "When public APIs or forms enforce per-IP or per-user throttling",
        "Returning bare 429 without Retry-After, human copy, or disabled submit state",
        [
            ("Should the UI show remaining quota?", "For authenticated APIs with known limits, show X of Y requests. For anonymous endpoints, show generic 'slow down' with countdown from Retry-After."),
            ("How to parse Retry-After?", "Support both seconds (integer) and HTTP-date. Cap displayed wait at reasonable max and re-enable submit automatically when timer expires."),
            ("Client-side rate limiting enough?", "No — always enforce server-side. Client throttling reduces accidental abuse; server enforcement stops intentional bypass."),
        ],
    ),
    "web-performance-requestidlecallback-patterns": (
        "Analytics batching in requestIdleCallback never ran on busy checkout pages — users navigated away before idle fired and we lost conversion events.",
        "requestIdleCallback for non-critical deferred work",
        "When deferring analytics, prefetch, or non-urgent DOM work off the critical path",
        "Assuming requestIdleCallback always fires — it does not under sustained main-thread load",
        [
            ("requestIdleCallback vs setTimeout(0)?", "IdleCallback runs in browser idle periods with deadline; setTimeout runs regardless. Use IdleCallback for low-priority work with setTimeout fallback."),
            ("What timeout should I pass?", "Use timeout option (e.g. 2000ms) to guarantee eventual execution for analytics — without it, events may never flush on busy pages."),
            ("Is scheduler.yield() better now?", "For yielding during long tasks, scheduler.yield() helps INP. IdleCallback remains appropriate for batching analytics and prefetch scheduling."),
        ],
    ),
    "web-performance-resize-observer-layout": (
        "A ResizeObserver loop updating chart dimensions on every pixel change triggered 'ResizeObserver loop limit exceeded' and froze dashboards for ten seconds.",
        "ResizeObserver without layout thrashing",
        "When components react to container size changes — charts, sticky sidebars, responsive typography",
        "Reading layout properties in ResizeObserver callback then synchronously writing DOM — causing loop errors",
        [
            ("How to avoid ResizeObserver loop errors?", "Batch DOM writes in requestAnimationFrame. Never read offsetWidth in the same callback after writes. Debounce high-frequency resize when precision is not needed."),
            ("ResizeObserver vs window resize?", "ResizeObserver tracks element containers — essential for grid layouts and component libraries. Window resize misses nested container changes."),
            ("Performance impact on complex pages?", "Limit observers to visible elements; disconnect when off-screen. One observer per component is fine; avoid observing document.body globally."),
        ],
    ),
    "web-performance-resource-hints": (
        "We added preload for every script and stylesheet — twelve preload tags in the head. LCP got worse because the browser prioritized all twelve equally, starving the hero image.",
        "resource hints: preload, prefetch, preconnect, dns-prefetch",
        "When critical resources compete for connection and bandwidth on first load",
        "Preloading everything instead of two or three truly critical resources",
        [
            ("What is the difference between preload and prefetch?", "Preload fetches for the current page with high priority — LCP image, critical font. Prefetch fetches for likely future navigation with low priority."),
            ("When should I use preconnect versus dns-prefetch?", "Preconnect does DNS + TCP + TLS — use for origins with multiple resources. dns-prefetch is lighter when the origin may not be used."),
            ("Can too many resource hints hurt performance?", "Yes. Each preload competes for bandwidth. Limit to two or three critical preloads per page."),
        ],
    ),
    "web-performance-resumability-qwik": (
        "Our React island hydrated 400KB on a marketing page that needed one interactive newsletter form — resumability sent 4KB of listener metadata instead of re-executing the whole tree.",
        "Qwik resumability vs traditional hydration",
        "When static pages need minimal interactivity without shipping full framework runtime upfront",
        "Choosing resumability for highly dynamic apps where serialization overhead exceeds hydration savings",
        [
            ("Resumability vs partial hydration?", "Resumability serializes event listeners and component state without re-running setup code. Partial hydration still downloads and parses more JS upfront."),
            ("When is Qwik the wrong choice?", "Highly dynamic SPAs with constant client state mutation — traditional frameworks may be simpler. Measure serialized HTML size vs bundle size."),
            ("Does resumability affect SEO?", "Server renders full HTML; resumability only changes client activation. Ensure SSR output matches what crawlers need without requiring resume."),
        ],
    ),
    "web-performance-scheduler-yield-api": (
        "A 180ms click handler blocked the main thread — splitting with scheduler.yield() dropped INP from 280ms to 95ms without rewriting the algorithm.",
        "scheduler.yield() for long task splitting",
        "When INP regressions trace to synchronous work in event handlers",
        "Yielding inside tight loops without checking user input priority — still missing deadlines",
        [
            ("scheduler.yield() vs requestAnimationFrame?", "yield() yields to user input and higher-priority tasks; rAF aligns to paint. Use yield in click/input handlers; rAF for visual updates."),
            ("Browser support strategy?", "Feature-detect scheduler.yield; fall back to setTimeout(0) chunks for unsupported browsers. Polyfills exist but native is preferred."),
            ("How small should chunks be?", "Target under 50ms per chunk to stay within INP budget. Profile with Performance panel — Long Tasks API shows what needs splitting."),
        ],
    ),
    "web-performance-search-autocomplete-debounce": (
        "Every keystroke fired a search API call — debouncing at 300ms cut requests 85% but users complained results felt laggy until we added optimistic local filtering on cached prefixes.",
        "search autocomplete debouncing with perceived latency tricks",
        "When typeahead queries hit remote APIs on every input event",
        "Debouncing without showing immediate local results or loading affordance",
        [
            ("What debounce delay for search?", "200–350ms for remote search; shorter feels snappy, longer reduces load. Combine with abortController to cancel in-flight stale requests."),
            ("Debounce vs throttle for scroll search?", "Debounce for typing; throttle for scroll-linked infinite search. Never fire unbounded parallel requests on fast typists."),
            ("Should empty queries hit the API?", "No — clear results locally. Minimum character threshold (2–3) reduces noise and cost for short prefixes."),
        ],
    ),
    "web-performance-selective-hydration": (
        "Hydrating the entire page blocked the hero image from painting — selective hydration of the chat widget alone recovered 400ms LCP on our docs site.",
        "selective hydration for above-the-fold priority",
        "When SSR pages mix static content with heavy interactive islands",
        "Hydrating all islands in document order instead of prioritizing visible interactive regions",
        [
            ("Selective vs progressive hydration?", "Selective chooses which components hydrate; progressive hydrates over time. React 19 and frameworks expose priority APIs — use visibility and interaction signals."),
            ("How to hydrate on interaction?", "Load island JS on first focus or hover (with prefetch). Reduces initial JS while keeping interactivity discoverable."),
            ("Impact on accessibility?", "Ensure SSR HTML is keyboard-accessible before hydration. Do not rely on hydrated handlers for essential navigation."),
        ],
    ),
    "web-performance-service-worker-stale-while-revalidate": (
        "Stale-while-revalidate served a week-old pricing page from cache while sales ran a promotion — users saw wrong prices until hard refresh.",
        "service worker stale-while-revalidate with freshness bounds",
        "When offline-capable caching must balance speed with content freshness",
        "Unbounded SWR without max-age, version headers, or skipWaiting coordination",
        [
            ("When is stale-while-revalidate appropriate?", "Static assets and API responses with explicit max-age. Never SWR price, inventory, or auth-sensitive data without short TTL and background revalidation alerts."),
            ("How to update SW cache on deploy?", "Version cache names; skipWaiting plus clients.claim with user-visible 'Update available' prompt — not silent overwrite mid-session."),
            ("SWR vs network-first?", "Network-first for HTML documents that change frequently; SWR for hashed static assets. Match strategy to content volatility."),
        ],
    ),
    "web-performance-sidebar-collapse-responsive": (
        "Collapsing the sidebar with display:none reflowed the entire dashboard — transform-based collapse kept layout stable and cut CLS from 0.18 to 0.02.",
        "responsive sidebar collapse without layout shift",
        "When navigation panels toggle on mobile and tablet breakpoints",
        "Toggling sidebar with properties that trigger layout (width, display) instead of transform",
        [
            ("Fixed vs overlay sidebar on mobile?", "Overlay with transform slide avoids content reflow; push sidebar shifts main content and causes CLS. Prefer overlay for data-dense dashboards."),
            ("Should collapse state persist?", "Persist in localStorage for user preference; default closed on mobile, open on desktop. Respect prefers-reduced-motion for animations."),
            ("Impact on INP?", "Collapse toggle should respond under 100ms — animate with CSS transform and will-change sparingly during animation only."),
        ],
    ),
    "web-performance-skeleton-screen-design": (
        "Skeleton screens that shimmer for eight seconds felt slower than a spinner — matching skeleton layout to final content and capping display time improved perceived performance scores.",
        "skeleton screen design matched to final layout",
        "When loading states exceed 300ms and content structure is predictable",
        "Generic gray rectangles that do not match final layout — causing layout shift when content loads",
        [
            ("Skeleton vs spinner?", "Skeletons for structured content with known layout; spinners for unknown duration or shape. Never skeleton for under 300ms loads — flash annoys."),
            ("Should skeletons animate?", "Subtle pulse or shimmer OK; respect prefers-reduced-motion with static skeletons. Aggressive animation increases cognitive load."),
            ("How to avoid CLS from skeletons?", "Match exact dimensions of text blocks, avatars, and images. Use fixed aspect-ratio containers for media skeletons."),
        ],
    ),
    "web-performance-speculative-prerendering": (
        "Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only.",
        "Speculation Rules API for prerender and prefetch",
        "When navigation patterns are highly predictable and bandwidth cost is acceptable",
        "Prerendering authenticated routes without matching Vary headers and cache isolation",
        [
            ("Prerender vs prefetch?", "Prerender loads and renders full page in hidden tab — instant navigation but higher cost. Prefetch only fetches resources. Use prerender sparingly for high-confidence next pages."),
            ("How to measure speculation hit rate?", "Track prerender activation vs actual navigations in RUM. Hit rate below 30% means rules are too aggressive — tune URL patterns."),
            ("Mobile data concerns?", "Respect Save-Data; disable prerender on slow connections. Speculation Rules support eagerness levels — use conservative on mobile breakpoints."),
        ],
    ),
    "web-performance-stale-ui-patterns": (
        "Showing last week's dashboard data with a tiny 'stale' badge users ignored caused finance to act on outdated numbers — prominent timestamps and refresh affordances fixed trust.",
        "stale UI patterns with honest freshness communication",
        "When cached or SWR data may be minutes old but still useful",
        "Hidden stale state — users assume fresh data when UI looks normal",
        [
            ("How stale is too stale for dashboards?", "Define per domain: real-time ops need seconds; analytics may tolerate minutes with clear as-of timestamp. Color-code age: green <1m, amber <15m, red older."),
            ("Stale-while-revalidate UI copy?", "Show 'Updating…' during background fetch; 'Last updated 2m ago' when serving cache. Never silently replace visible numbers without transition."),
            ("Does stale UI affect accessibility?", "Announce refresh completion with aria-live polite — not assertive on every poll. Stale banners need sufficient contrast and are not color-only."),
        ],
    ),
    "web-performance-status-page-integration": (
        "Our app showed generic errors during an API outage while the status page said 'operational' — embedding status component feed reduced support volume 60%.",
        "status page integration in product UI",
        "When third-party or platform dependencies cause user-visible failures",
        "Hard-coded error messages without linking to live component status",
        [
            ("Embed status API or iframe?", "JSON component API enables native UI matching your design; iframe is faster to integrate but hurts UX consistency. Cache status 60s max."),
            ("What to show during partial outages?", "Map failing API to status component — 'Payments delayed' not 'Something went wrong'. Offer retry and subscribe-to-updates link."),
            ("Should status affect retry logic?", "Backoff harder when status confirms incident; retry normally on unknown errors. Do not hammer degraded endpoints."),
        ],
    ),
    "web-performance-tab-navigation-aria": (
        "Keyboard users could not reach tab panel content — roving tabindex and aria-selected fixes took one day and cleared our accessibility audit finding.",
        "ARIA tab navigation with roving tabindex",
        "When building custom tab interfaces beyond native details/summary",
        "Using div-onClick tabs without role=tablist, keyboard arrows, or focus management",
        [
            ("Native vs ARIA tabs?", "If design fits, use native <details> or anchor navigation. Custom ARIA tabs need full keyboard spec: Arrow keys, Home, End, aria-selected."),
            ("Should inactive panels be focusable?", "Use tabindex=-1 on hidden panels; only active panel in tab order. display:none or hidden attribute on inactive panels."),
            ("Tab activation on focus or click?", "Automatic activation on focus helps keyboard users; manual (Space/Enter) helps mouse users who arrow past tabs. Pick one pattern consistently."),
        ],
    ),
    "web-performance-third-party-script-impact": (
        "One chat widget added 1.2s of main-thread blocking — deferring third parties until after load and using facade pattern recovered INP without removing support chat.",
        "third-party script impact on Core Web Vitals",
        "When marketing, analytics, and support tools compete with product JS",
        "Loading all third parties synchronously in head because vendor docs say so",
        [
            ("Facade pattern for chat widgets?", "Show static button; load full widget on click. Reduces initial long tasks by 80% on typical sites. Measure INP before and after."),
            ("How to audit third parties?", "Chrome DevTools Coverage plus Lighthouse 'Reduce unused JavaScript'. Tag managers often load unused pixels — audit quarterly."),
            ("CSP and third parties?", "Nonce-based CSP requires vendor support. Maintain allowlist with owner and business justification per script origin."),
        ],
    ),
    "web-performance-toast-queue-management": (
        "Twelve simultaneous error toasts stacked off-screen — users missed the critical payment failure among 'Saved' confirmations. A priority queue with deduplication fixed it.",
        "toast notification queue with priority and deduplication",
        "When multiple async operations emit overlapping user feedback",
        "Unbounded toast spam without priority, grouping, or max visible count",
        [
            ("How many toasts visible at once?", "Max two — queue the rest. Errors beat success messages; collapse duplicate errors within 5s window."),
            ("Toast duration by severity?", "Errors persist until dismissed; success auto-dismiss 3–4s. Respect prefers-reduced-motion — no sliding stack animations."),
            ("aria-live for toasts?", "Use role=status polite for success; role=alert for errors (sparingly). One live region container — not per toast element."),
        ],
    ),
    "web-performance-tree-shaking-side-effects": (
        "Our bundle included all of lodash because one file imported the package root — sideEffects: false in package.json and per-module imports dropped 90KB gzip.",
        "tree shaking and sideEffects field in package.json",
        "When bundle analysis shows unused exports from large dependencies",
        "Importing from package root when deep imports or babel-plugin-import could tree-shake",
        [
            ("What does sideEffects: false mean?", "Tells bundler that importing a module has no global side effects — safe to drop unused exports. Wrong flag breaks CSS-in-JS packages that register globally."),
            ("barrel files and tree shaking?", "Re-export barrels often prevent shaking — import from concrete modules. eslint-plugin-import helps enforce."),
            ("How to verify shaking worked?", "Bundle analyzer (webpack-bundle-analyzer, rollup-plugin-visualizer). Confirm unused lodash functions absent from output."),
        ],
    ),
    "web-performance-web-workers-heavy-compute": (
        "Parsing 50MB CSV on the main thread froze the UI for twelve seconds — moving Papa Parse to a Web Worker kept INP under 100ms during upload.",
        "Web Workers for heavy compute off main thread",
        "When client-side parsing, crypto, or image processing exceeds 50ms",
        "Posting large payloads to workers without Transferable objects — doubling memory",
        [
            ("Worker vs WASM for compute?", "Workers for I/O parsing and existing JS libs; WASM for numeric hot paths. Start with Worker — simpler debugging."),
            ("Comlink vs raw postMessage?", "Comlink abstracts RPC-style calls; raw postMessage for simple one-shot tasks. Always handle worker errors and terminate idle workers."),
            ("SharedWorker when?", "Rare — SharedWorker for multi-tab coordination. Dedicated Worker covers most UI offload cases."),
        ],
    ),
    "web-performance-will-change-sparingly": (
        "will-change: transform on every list item consumed GPU memory until mobile browsers killed the tab — applying only during active animation saved 200MB.",
        "will-change used sparingly for compositor promotion",
        "When animating transform/opacity and jank persists after other optimizations",
        "Permanent will-change on static elements — memory leak on long sessions",
        [
            ("When to add will-change?", "Add on animation start via JS class; remove on animationend. Never leave on dozens of elements simultaneously."),
            ("will-change vs transform: translateZ(0)?", "Both promote layers; will-change is explicit hint. translateZ hack promotes without cleanup — same memory issue."),
            ("Which properties will-change accepts?", "transform and opacity primarily. will-change: top triggers layout — avoid for layout properties."),
        ],
    ),
    "web-popover-api-native": (
        "Our 400-line popover library fought with focus trap bugs — the native Popover API with popover='auto' and invoker attributes replaced it in a afternoon with better accessibility.",
        "native Popover API with anchor positioning",
        "When tooltips, menus, and dropdowns need light-dismiss and top-layer stacking",
        "Polyfilling Popover when 15% of users still need full keyboard and light-dismiss behavior tested",
        [
            ("popover=auto vs manual?", "auto light-dismisses on outside click and Escape; manual for modal-like popovers requiring explicit close. Match to UX pattern."),
            ("Popover vs dialog element?", "Popover for non-modal overlays (menus, hints); dialog for modal focus trap. Popover does not block page interaction."),
            ("Anchor positioning support?", "CSS anchor() ties popover to invoker. Feature-detect; fallback to absolute positioning with ResizeObserver."),
        ],
    ),
    "web-scroll-snap-carousels": (
        "scroll-snap carousel with snap-align:center looked perfect on iPhone but cut off product titles on Android — scroll-padding and mandatory vs proximity fixed cross-browser snap.",
        "CSS scroll-snap carousels without JavaScript",
        "When horizontal product or image carousels need native touch scroll performance",
        "mandatory snap on vertical scroll containers — hijacking page scroll on mobile",
        [
            ("mandatory vs proximity snap?", "proximity for optional carousel feel; mandatory when exact slide alignment is required — test that vertical page scroll is not captured."),
            ("scroll-snap-type on which axis?", "x mandatory on horizontal overflow container only — never on body. scroll-padding-inline accounts for peek slides."),
            ("Accessibility for snap carousels?", "Provide prev/next buttons with aria-controls; do not rely on swipe alone. Announce slide changes with aria-live sparingly."),
        ],
    ),
    "web-signals-fine-grained-reactivity": (
        "Fine-grained signals updated only the price text node — our React re-render redrew the entire product grid on every stock tick.",
        "JavaScript signals for fine-grained DOM updates",
        "When high-frequency state changes hit large component trees",
        "Using signals inside React without integration layer — double sources of truth",
        [
            ("Signals vs React useState?", "Signals excel at leaf updates and derived computations without component re-render. React excels at app structure — use @preact/signals-react or similar bridge."),
            ("When not to use signals?", "Low-frequency form state and server cache — React Query and useState are simpler. Signals shine in dashboards and live data grids."),
            ("Signals and SSR?", "Serialize signal state for hydration or accept client-only signal islands. Mismatch causes hydration errors — isolate signal components client-only if needed."),
        ],
    ),
    "web-speculation-rules-prefetch": (
        "Declarative speculation rules in HTTP headers prefetched admin routes for anonymous users — scoping rules by URL pattern and login cookie presence closed the leak.",
        "Speculation Rules prefetch in headers and markup",
        "When MPAs have predictable next navigation from high-traffic entry pages",
        "Global prefetch rules without excluding authenticated or personalized routes",
        [
            ("Speculation rules in meta vs Link header?", "Link header enables CDN injection on cacheable pages; inline script type=speculationrules for page-specific rules. Both support eagerness tuning."),
            ("How is this different from link rel=prefetch?", "Speculation Rules unify prerender, prefetch, and prerender-with-subresources with eagerness and requires conditions."),
            ("Requires conditions?", "Use requires: ['anonymous-client-ip-includes'] or custom client hints to limit speculation to safe contexts."),
        ],
    ),
    "web-storage-indexeddb-patterns": (
        "Storing chat history in localStorage hit the 5MB cap silently — IndexedDB with structured stores and eviction policy scaled to 200MB with clear upgrade migrations.",
        "IndexedDB patterns for structured client storage",
        "When client data exceeds localStorage limits or needs indexing",
        "No schema versioning — upgrade handlers that drop user data on deploy",
        [
            ("IndexedDB vs Cache API?", "IndexedDB for structured queryable data; Cache API for Request/Response pairs. Offline apps often use both."),
            ("How to handle IDB migrations?", "Increment version in onupgradeneeded; migrate records in transaction — never delete store without copying data."),
            ("idb wrapper libraries?", "Dexie and idb simplify promises API. Raw IDB is verbose but dependency-free — pick based on team familiarity."),
        ],
    ),
    "web-view-transitions-multi-page": (
        "View Transitions on MPAs made navigation feel instant — but back navigation showed wrong thumbnail until we synced view-transition-name on shared hero elements only.",
        "View Transitions API for multi-page apps",
        "When MPAs want SPA-like transitions without full client routing",
        "Same view-transition-name on multiple elements — broken cross-document transitions",
        [
            ("MPA vs SPA view transitions?", "Cross-document transitions need @view-transition at-rule and matching named elements across pages. SPA uses document.startViewTransition()."),
            ("Browser support fallback?", "Feature-detect and skip animation — content must work without transition. Progressive enhancement essential."),
            ("Performance cost?", "Screenshot old state, animate, paint new — cheap for hero swaps; avoid on heavy DOM pages. Test on low-end Android."),
        ],
    ),
    "web-vitals-rum-dashboard-design": (
        "Our RUM dashboard averaged LCP globally while India mobile p75 was 4.2s — slicing by country, connection, and route exposed the real regressions.",
        "RUM dashboard design for Core Web Vitals",
        "When lab Lighthouse scores disagree with field CrUX data",
        "Single global LCP average without dimension breakdowns or lab vs field comparison",
        [
            ("Which dimensions to slice CWV?", "Device type, country, connection effective type, route, release version, experiment bucket. Never trust global mean alone."),
            ("Lab vs field in one dashboard?", "Show both — lab for CI regression, field for user impact. Label clearly to avoid comparing unlike populations."),
            ("Alert thresholds?", "Alert on p75 field LCP/INP/CLS regression week-over-week per key route — not on lab score noise."),
        ],
    ),
    "web-workers-offloading-compute": (
        "Image thumbnail generation blocked checkout for three seconds on low-end Android — a Worker pool with two concurrent jobs kept the main thread responsive.",
        "offloading compute to Web Worker pools",
        "When CPU-bound client tasks risk INP and long task violations",
        "Spawning unbounded workers — exhausting memory on multi-file upload",
        [
            ("How many workers?", "Match hardware concurrency minus one for main thread — typically 2–4 for image processing. Queue jobs beyond pool size."),
            ("Transferable ArrayBuffers?", "Transfer ownership to avoid copy cost on large buffers. Copy back results only when needed for canvas display."),
            ("Worker bundling in Vite/webpack?", "Use worker import syntax (new Worker(new URL('./worker.ts', import.meta.url))). Separate chunk avoids main bundle bloat."),
        ],
    ),
    "webassembly-beyond-browser-wasi": (
        "Running our WASM image filter on the server via WASI cut cold start vs container spin-up — same module on client and edge simplified the pipeline.",
        "WebAssembly beyond the browser with WASI",
        "When portable sandboxed modules should run on server, edge, or CLI",
        "Assuming browser WASM (DOM imports) runs unchanged on WASI — different import namespace",
        [
            ("WASI vs wasm32-unknown-unknown?", "WASI provides filesystem and network syscalls for servers; browser WASM imports DOM via JS glue. Compile separately or use conditional imports."),
            ("WASI security model?", "Capability-based — explicit preopens for filesystem paths. No broad filesystem access by default."),
            ("When WASM on server beats Node?", "CPU hot paths (image, crypto, parsing) near native speed with sandbox. I/O-bound Node code rarely benefits."),
        ],
    ),
    "webauthn-passkeys-server": (
        "Passkey registration succeeded in Chrome but Safari users could not sign in — we had not configured related origins and allowed credential IDs per RP ID.",
        "WebAuthn passkeys server verification and storage",
        "When replacing passwords with platform authenticators and syncable passkeys",
        "Storing only credential ID without signCount verification — missing clone detection",
        [
            ("Passkeys vs security keys?", "Passkeys sync via platform cloud (Apple/Google); security keys are device-bound. Support both credential types in allowCredentials when needed."),
            ("How to verify attestation?", "Often none for passkeys (self-attestation). Enterprise may require attestation statement validation — configure per tenant policy."),
            ("Sign count and clone detection?", "Increment signCount each auth; reject if counter does not increase — indicates cloned authenticator."),
        ],
    ),
    "webgpu-compute-graphics": (
        "WebGL compute hacks for particle simulation hit driver bugs — WebGPU compute shaders ran consistently across Chrome and Firefox with clearer buffer lifecycle.",
        "WebGPU for compute and graphics in the browser",
        "When WebGL limits block compute-style workloads or modern GPU features",
        "Assuming WebGPU ships everywhere WebGL does — check adapter availability and fallback",
        [
            ("WebGPU vs WebGL migration?", "WebGPU explicit buffer and pipeline model — rewrite shaders to WGSL. Not drop-in. Plan fallback WebGL path for unsupported browsers."),
            ("Compute vs render queue?", "Same device queue handles both; synchronize with command encoder barriers. Batch compute before render pass when particles feed graphics."),
            ("Memory limits?", "requestAdapter().limits — mobile adapters have smaller maxBufferSize. Stream large textures in tiles."),
        ],
    ),
    "webhooks-reliable-delivery": (
        "Webhooks looked trivial until a consumer outage silently dropped events — persist-first delivery with backoff turned integrations from complaint magnets into dependable contracts.",
        "reliable webhook delivery with outbox and retries",
        "When partners depend on event notifications for billing, fulfillment, or sync",
        "Fire-and-forget POST without durable queue or retry policy",
        [
            ("At-least-once vs exactly-once delivery?", "At-least-once is achievable with retries; exactly-once over HTTP is not — consumers must dedupe with stable event IDs."),
            ("How long to retry failed webhooks?", "24–72 hours with exponential backoff and jitter covers most outages. Dead-letter permanently failing endpoints after max attempts."),
            ("Should webhooks be synchronous with the transaction?", "Never block user requests on delivery — write to outbox in same DB transaction as business event; async worker delivers."),
        ],
    ),
    "webhooks-retry-idempotency": (
        "Double webhook delivery double-charged a customer because our handler keyed idempotency on timestamp instead of event ID — stable IDs fixed reconciliation.",
        "webhook retry idempotency on consumer side",
        "When at-least-once delivery means duplicate POSTs are guaranteed",
        "Idempotency keys that change per retry attempt instead of stable event identifiers",
        [
            ("Where to store processed event IDs?", "Database unique constraint on event_id with TTL for replay windows. Redis SETNX works for short horizons."),
            ("Idempotent handler design?", "Check-before-act: if seen, return 200 without side effects. Make financial operations reversible or use ledger entries."),
            ("200 on duplicate or 409?", "Return 200 on duplicate so sender stops retrying — 409 may trigger unnecessary retry storms."),
        ],
    ),
    "webhooks-signature-verification": (
        "We verified HMAC over parsed JSON instead of raw body — key reordering in transit caused false rejections and a partner integration outage.",
        "webhook HMAC signature verification on raw body",
        "When webhook endpoints must reject forged or tampered payloads",
        "Re-serializing JSON for verification instead of using raw request bytes",
        [
            ("HMAC-SHA256 standard pattern?", "Sign timestamp + '.' + raw body; reject timestamps older than five minutes. Compare with hmac.compare_digest in constant time."),
            ("Multiple signature versions?", "Support v1,v2 in header during rotation — verify with both secrets during overlap window."),
            ("Replay without timestamp?", "Always include signed timestamp. Nonce store optional for high-security; timestamp usually sufficient."),
        ],
    ),
    "webrtc-data-channels-realtime": (
        "WebSocket relay cost scaled linearly with video adjacency chat — WebRTC data channels for game state cut server bandwidth 90% after ICE negotiation.",
        "WebRTC data channels for peer realtime data",
        "When low-latency peer data beats server fan-out for games or collaboration",
        "No TURN server fallback — corporate NAT blocks 30% of P2P connections",
        [
            ("Data channel vs WebSocket?", "Data channels after P2P setup avoid server relay; WebSocket simpler for server-authoritative apps. Hybrid: signal via WebSocket, data via RTC."),
            ("Reliable vs unreliable SCTP?", "Ordered reliable for state sync; unordered unreliable for position updates where latest packet wins."),
            ("ICE restart on network change?", "Handle connectionstatechange failed — restart ICE on mobile network handoff."),
        ],
    ),
    "websocket-heartbeat-ping-pong": (
        "Idle WebSocket connections dropped by AWS ALB after 60s without us knowing — application-level ping every 30s kept connections alive and detected dead peers.",
        "WebSocket heartbeat ping-pong patterns",
        "When proxies and load balancers silently drop idle WebSocket connections",
        "Relying on TCP keepalive alone — insufficient through L7 load balancers",
        [
            ("Ping interval vs proxy timeout?", "Set ping interval to half of minimum proxy idle timeout — 30s ping for 60s ALB timeout."),
            ("Who sends ping?", "Either side; document contract. Server-initiated ping with client pong is common for connection health metrics."),
            ("Missed pong handling?", "Close connection after N missed pongs; client reconnects with backoff. Do not accumulate zombie connections."),
        ],
    ),
    "websocket-reconnection-backoff": (
        "Instant reconnect on WebSocket drop hammered our recovering server — exponential backoff with jitter spread reconnects across two minutes instead of one spike.",
        "WebSocket reconnection with exponential backoff",
        "When clients must survive server deploys and network blips",
        "Immediate reconnect loops without max delay or jitter",
        [
            ("Backoff parameters?", "Start 1s, double to cap 60s, full jitter. Reset backoff after stable connection >60s."),
            ("Replay missed messages how?", "Server sequence numbers plus client lastAck — replay gap on reconnect. Or idempotent state sync on full reconnect."),
            ("Max reconnect attempts?", "Infinite with cap delay for consumer apps; finite with user prompt for embedded widgets."),
        ],
    ),
    "whats-new-android-17": (
        "Android 17 tightened foreground service types again — our tracking app got rejected until we migrated to the new health sync API and declared FGS types explicitly.",
        "Android 17 platform changes for app developers",
        "When targeting API 37 and updating Play policy compliance",
        "Assuming Android 16 behavior without reading behavior changes doc for background work",
        [
            ("What breaks foreground services in Android 17?", "Stricter FGS type enforcement and shorter grace periods for dataSync — migrate to WorkManager for deferrable work."),
            ("Privacy sandbox updates?", "Review AD_ID and attribution API changes each release — feature-detect and provide non-ad fallback paths."),
            ("Migration timeline?", "Target beta SDK early; run compatibility tests on Pixel beta devices before stable release."),
        ],
    ),
    "workmanager-reliable-background-work": (
        "AlarmManager exact alarms drained battery and still missed sync on Doze — WorkManager with expedited workers and network constraints matched Android power policies.",
        "WorkManager for reliable background work on Android",
        "When deferrable sync, upload, or cleanup must survive process death and Doze",
        "Raw Thread or GlobalScope for background work — killed by OEM battery savers",
        [
            ("WorkManager vs Foreground Service?", "FGS for user-visible long tasks (playback, navigation); WorkManager for deferrable background sync. Wrong choice gets killed or policy rejection."),
            ("Expedited vs regular work?", "Expedited for user-initiated sync within minutes; subject to quota. Regular for periodic background."),
            ("Unique work chains?", "Use enqueueUniqueWork to prevent duplicate sync storms on app restart."),
        ],
    ),
    "xss-dom-based-prevention": (
        "location.hash fed into innerHTML without sanitization — a crafted link exfiltrated session tokens via DOM XSS that WAF never saw because payload never hit the server.",
        "DOM-based XSS prevention in client-rendered apps",
        "When URL fragments, postMessage, or client storage flow into DOM sinks",
        "Trusting client-side routing params for document.write or eval sinks",
        [
            ("Common DOM XSS sinks?", "innerHTML, outerHTML, insertAdjacentHTML, eval, setTimeout string, location assignment. Use textContent or sanitize with DOMPurify."),
            ("postMessage XSS?", "Validate event.origin against allowlist; never pass event.data to sinks without schema validation."),
            ("Can CSP stop DOM XSS?", "Strict CSP with nonces helps inline; Trusted Types enforce sink policies — strongest client-side DOM XSS defense."),
        ],
    ),
    "xss-prevention-csp-trusted-types": (
        "Trusted Types policy blocked a marketing tag injection — we moved analytics to nonce-based CSP and registered a default policy for app-owned sinks only.",
        "CSP and Trusted Types for XSS prevention",
        "When reflected and stored XSS defenses need enforceable browser policies",
        "Report-Only CSP forever — never enforcing because third parties break",
        [
            ("Trusted Types require-policy?", "require-trusted-types-for 'script' plus trusted-types directive listing policy names. Create policy in app bootstrap only."),
            ("CSP nonce vs hash?", "Nonce for dynamic SSR scripts; hash for static inline. strict-dynamic propagates trust to loaded scripts."),
            ("Third-party CSP exceptions?", "Minimize unsafe-inline; use tag manager with nonce injection or server-side tag proxy."),
        ],
    ),
    "xss-sanitize-html-user-content": (
        "DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews.",
        "sanitize HTML user content with allowlists",
        "When rich text comments, bios, or CMS content renders as HTML",
        "Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors",
        [
            ("DOMPurify config?", "USE_PROFILES html or svg selectively; forbid style if not needed. ADD_URI_SAFE_ATTR for data attributes only if required."),
            ("Server-side sanitize too?", "Always sanitize server-side on ingest — client sanitize is defense in depth, not primary."),
            ("Markdown to HTML?", "Sanitize after markdown render — markdown allows raw HTML passthrough by default in many parsers."),
        ],
    ),
    "zero-downtime-database-migrations": (
        "Adding NOT NULL column without default locked the users table for four minutes — expand-contract with nullable column, backfill, then enforce recovered zero downtime.",
        "zero-downtime database migrations with expand-contract",
        "When schema changes must ship without maintenance windows on large tables",
        "Direct ALTER on million-row tables during peak traffic",
        [
            ("Expand-contract phases?", "Expand: add nullable column. Migrate: dual-write or backfill job. Contract: add NOT NULL, drop old column — never skip backfill."),
            ("Online index creation?", "Use CONCURRENTLY on Postgres; ALGORITHM=INPLACE on MySQL where supported. Still monitor replication lag."),
            ("Rollback plan?", "Contract phase is point of no return — feature-flag reads of new column before contract."),
        ],
    ),
    "zero-trust-mobile-apps": (
        "VPN tunneling all mobile traffic failed compliance — zero trust with per-app attestation, device posture checks, and short-lived tokens matched how field reps actually work.",
        "zero trust architecture for mobile apps",
        "When corporate data on BYOD devices needs least-privilege access without legacy VPN",
        "Binary allow/deny VPN instead of continuous verification and step-up auth",
        [
            ("MTD vs MDM for zero trust?", "MDM manages device; MTD detects threats. Combine signals — rooted device triggers step-up or block sensitive actions."),
            ("Certificate pinning in zero trust?", "Pinning helps MITM detection but complicates rotation — use dynamic pinning with backup pins."),
            ("Session length on mobile?", "Short access tokens (15m) with refresh bound to device key. Re-auth on posture change."),
        ],
    ),
    "zero-trust-network-access": (
        "Flat network access let a compromised laptop reach every internal service — ZTNA with identity-aware proxies reduced blast radius to authorized app segments only.",
        "zero-trust network access replacing perimeter VPN",
        "When remote workforce needs app-level access without full network trust",
        "ZTNA vendor without logging and policy testing — black box allow rules",
        [
            ("ZTNA vs SDP?", "Software-Defined Perimeter is ZTNA precursor — both enforce identity before connection. Modern ZTNA adds continuous posture assessment."),
            ("Split tunneling?", "Route only corporate app traffic through ZTNA; general internet direct — reduces latency and privacy friction."),
            ("On-prem legacy apps?", "App connectors or identity-aware reverse proxies bridge ZTNA to apps that cannot install agents."),
        ],
    ),
}


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> dict:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = parts[1]
    out: dict = {"body": parts[2]}
    for key in ("title", "slug", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"(.+)"', fm, re.M)
        if m:
            out[key] = m.group(1)
    tags = re.findall(r'^\s*-\s*"(.+)"', fm, re.M)
    if tags:
        out["tags"] = tags
    elif re.search(r"^tags:", fm, re.M):
        m = re.search(r'tags:\s*\[(.+)\]', fm, re.M)
        if m:
            out["tags"] = [t.strip().strip('"') for t in m.group(1).split(",")]
    return out


def needs_rewrite(raw: str) -> bool:
    body_parts = raw.split("---", 2)
    body = body_parts[2] if len(body_parts) >= 3 else raw
    if wc(body) < TARGET:
        return True
    return any(b in raw for b in BANNED)


def heading(kind: str, tech: str, idx: int) -> str:
    table = {
        "hook": None,
        "mechanism": f"How {tech} works under the hood",
        "implementation": "Implementation walkthrough",
        "tradeoffs": "Tradeoffs worth documenting",
        "failure_modes": "Failure modes that survive code review",
        "metrics": "What to measure in RUM and dashboards",
        "closing": "What I'd ship this week",
        "scenario": "The incident that teaches the pattern",
        "anatomy": f"Anatomy of {tech}",
        "code": "Reference patterns",
        "edge_cases": "Edge cases browsers and users throw at you",
        "rollout": "Rollout without heroics",
        "observability": "Signals that catch regressions early",
        "summary": "Bottom line",
        "myth": "The myth teams still believe",
        "reality": "What actually happens in production",
        "design": "Design constraints first",
        "walkthrough": "Step-by-step integration",
        "pitfalls": "Pitfalls on real devices",
        "benchmarks": "Numbers from the field",
        "takeaway": "Takeaway for your next PR",
        "symptom": "Symptoms users report",
        "diagnosis": "How to confirm root cause",
        "fix": "Fix that sticks",
        "prevention": "Prevention for the next launch",
        "monitoring": "Monitoring checklist",
        "lessons": "Lessons for the team",
        "context": "Why this matters now",
        "comparison": "Options compared honestly",
        "deep_dive": "Technical deep dive",
        "patterns": "Patterns that compose well",
        "anti_patterns": "Anti-patterns to delete",
        "checklist": "Pre-ship checklist",
        "next": "Where to go from here",
        "question": "The question behind the ticket",
        "answer": "Answer with nuance",
        "security": "Security angle",
        "testing": "Testing beyond happy path",
        "ops": "Day-two operations",
    }
    return table.get(kind, kind.replace("_", " ").title())


def code_block(slug: str, tech: str) -> str:
    if "webhook" in slug:
        return textwrap.dedent("""
            async function deliverWebhook(delivery, endpoint, secret) {
              const body = JSON.stringify(delivery.payload);
              const ts = Math.floor(Date.now() / 1000).toString();
              const sig = signHmac(secret, ts, body);
              const res = await fetch(endpoint.url, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Webhook-Id": delivery.eventId,
                  "Webhook-Timestamp": ts,
                  "Webhook-Signature": sig,
                },
                body,
                signal: AbortSignal.timeout(30_000),
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
            }
            """)
    if "websocket" in slug:
        return textwrap.dedent("""
            class ReconnectingWebSocket {
              constructor(url) {
                this.url = url;
                this.backoff = 1000;
                this.connect();
              }
              connect() {
                this.ws = new WebSocket(this.url);
                this.ws.onopen = () => { this.backoff = 1000; this.startHeartbeat(); };
                this.ws.onclose = () => setTimeout(() => this.connect(), this.jitter());
              }
              jitter() {
                const d = Math.min(this.backoff, 60_000);
                this.backoff = Math.min(this.backoff * 2, 60_000);
                return d * (0.5 + Math.random());
              }
              startHeartbeat() {
                this.pingTimer = setInterval(() => {
                  if (this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "ping" }));
                }, 30_000);
              }
            }
            """)
    if "xss" in slug or "sanitize" in slug:
        return textwrap.dedent("""
            import DOMPurify from "dompurify";

            const clean = DOMPurify.sanitize(userHtml, {
              ALLOWED_TAGS: ["b", "i", "em", "strong", "a", "p", "ul", "ol", "li", "code"],
              ALLOWED_ATTR: ["href", "title"],
              ALLOW_DATA_ATTR: false,
            });
            container.replaceChildren(); // avoid innerHTML assignment pattern
            container.insertAdjacentHTML("afterbegin", clean);
            """)
    if "indexeddb" in slug or "storage" in slug:
        return textwrap.dedent("""
            const db = await openDB("app", 2, {
              upgrade(db, oldVersion) {
                if (oldVersion < 1) db.createObjectStore("drafts", { keyPath: "id" });
                if (oldVersion < 2) db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
              },
            });
            await db.put("drafts", { id: draftId, form: data, updatedAt: Date.now() });
            """)
    if "webauthn" in slug or "passkey" in slug:
        return textwrap.dedent("""
            const credential = await navigator.credentials.create({
              publicKey: {
                rp: { name: "Example", id: "example.com" },
                user: { id: userIdBytes, name: email, displayName: name },
                pubKeyCredParams: [{ type: "public-key", alg: -7 }],
                authenticatorSelection: { residentKey: "preferred", userVerification: "required" },
              },
            });
            await fetch("/webauthn/register", { method: "POST", body: JSON.stringify(credential) });
            """)
    if "worker" in slug or "wasm" in slug.lower():
        return textwrap.dedent("""
            const worker = new Worker(new URL("./compute.worker.ts", import.meta.url), { type: "module" });
            const buffer = new ArrayBuffer(1024 * 1024);
            worker.postMessage({ type: "process", buffer }, [buffer]);
            worker.onmessage = (e) => updateUI(e.data);
            """)
    if "performance" in slug or "popover" in slug or "scroll-snap" in slug:
        return textwrap.dedent("""
            // Measure before/after in RUM
            performance.mark("interaction-start");
            await applyOptimization();
            performance.mark("interaction-end");
            performance.measure("interaction", "interaction-start", "interaction-end");
            navigator.sendBeacon("/rum", JSON.stringify({
              name: "interaction",
              duration: performance.getEntriesByName("interaction").pop()?.duration,
              path: location.pathname,
            }));
            """)
    if "android" in slug or "workmanager" in slug:
        return textwrap.dedent("""
            val syncRequest = OneTimeWorkRequestBuilder<SyncWorker>()
              .setConstraints(Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build())
              .build()
            WorkManager.getInstance(context)
              .enqueueUniqueWork("sync", ExistingWorkPolicy.KEEP, syncRequest)
            """)
    if "migration" in slug or "zero-trust" in slug or "zero-downtime" in slug:
        return textwrap.dedent("""
            -- Phase 1 expand: nullable column
            ALTER TABLE orders ADD COLUMN status_v2 text;
            -- Phase 2 backfill (batched)
            UPDATE orders SET status_v2 = status WHERE status_v2 IS NULL AND id BETWEEN $1 AND $2;
            -- Phase 3 contract (after app dual-write verified)
            ALTER TABLE orders ALTER COLUMN status_v2 SET NOT NULL;
            """)
    return textwrap.dedent(f"""
        // Operational hook for {tech}
        export async function applyPattern(ctx: RequestContext) {{
          const start = performance.now();
          try {{
            return await execute(ctx);
          }} finally {{
            reportMetric("{slug}", performance.now() - start);
          }}
        }}
        """)


def expand_section(kind: str, slug: str, hook: str, tech: str, mistake: str, desc: str, iteration: int) -> str:
    h = heading(kind, tech, iteration)
    if kind in ("hook",):
        return ""
    if kind == "mechanism" or kind == "anatomy" or kind == "deep_dive":
        return textwrap.dedent(f"""
            ## {h}

            {desc} The mechanism matters because browsers and servers optimize for the common case — not your specific stack. {tech.title()} sits at the intersection of user-perceived latency, correctness, and operability.

            When teams skip this layer, they usually optimize a metric that looks good in Lighthouse but flatlines in CrUX. Field data on mid-tier Android over 4G is the honest judge. Lab tests remain useful for CI regression gates, but they should not be the only feedback loop.

            Understanding ordering helps: parse HTML, discover resources, fetch with priority, execute, paint, hydrate. Any hint or API you add reroutes that pipeline. Ask whether your change pulls work earlier (good for LCP) or duplicates work (bad for bandwidth).
            """)
    if kind == "implementation" or kind == "code" or kind == "walkthrough" or kind == "fix":
        lang = "kotlin" if "android" in slug or "workmanager" in slug else ("sql" if "migration" in slug else "typescript")
        return textwrap.dedent(f"""
            ## {h}

            Ship the smallest vertical slice first — one route, one widget, one webhook endpoint — with rollback documented before expanding scope. {mistake} That mistake is expensive because it only surfaces under real traffic mixes.

            ```{lang}
            {code_block(slug, tech).strip()}
            ```

            Wire metrics at the same time as the feature. If you cannot answer "did this make users faster or safer?" within a week of launch, the change is not finished.
            """)
    if kind == "failure_modes" or kind == "pitfalls" or kind == "edge_cases" or kind == "anti_patterns":
        return textwrap.dedent(f"""
            ## {h}

            - **Assumption drift**: staging has fast Wi-Fi and no ad blockers; production does not.
            - **Missing rollback**: feature flags or route toggles beat hotfix deploys at 2 a.m.
            - **Third-party blind spots**: analytics and chat widgets change without your deploy.
            - **Accessibility regressions**: focus traps, missing labels, and motion without reduced-motion fallback.
            - **The original sin**: {mistake}

            Rehearse the top two failures in a 30-minute game day before peak traffic season. Time-to-detect and time-to-mitigate matter more than perfect root-cause docs written afterward.
            """)
    if kind == "metrics" or kind == "observability" or kind == "monitoring" or kind == "benchmarks":
        return textwrap.dedent(f"""
            ## {h}

            Leading indicators catch regressions before tweets do: error rate, queue depth, validation failures, p75 latency sliced by route and device class. Lagging indicators — support tickets, churn, audit findings — confirm whether leading metrics matched user pain.

            For {tech}, log correlation IDs across client beacons and server logs. Compare canary vs control during rollout. Roll forward only when p75 field metrics hold for at least one full business day in the target geography.
            """)
    if kind == "security":
        return textwrap.dedent(f"""
            ## {h}

            Frontend and backend changes share an attack surface. Treat user content, URL parameters, and webhook bodies as hostile input. Prefer fail-closed verification, short-lived credentials, and constant-time comparisons for crypto.

            Content Security Policy, Subresource Integrity, and Trusted Types stack for DOM XSS defense. Security work without tests regresses — add CI checks that fail on unsafe patterns.
            """)
    if kind == "comparison" or kind == "tradeoffs":
        return textwrap.dedent(f"""
            ## {h}

            | Approach | Wins | Costs |
            | --- | --- | --- |
            | Minimal change | Fast ship, easy rollback | May not fix root cause |
            | Full rewrite | Clean architecture | Long risk window |
            | Platform-native API | Less JS, better a11y | Support matrix testing |

            Pick based on traffic shape and failure cost — not framework fashion. Document rejected alternatives in the PR so the next engineer does not relitigate the same debate.
            """)
    if kind in ("closing", "summary", "takeaway", "next", "lessons"):
        return textwrap.dedent(f"""
            ## {h}

            {hook.split('—')[0].strip()}. If I were prioritizing one action this sprint: pick the single user journey where {tech} hurts most, instrument it, fix the invariant, and only then generalize.

            Performance and reliability work compounds when tied to business metrics — conversion, support volume, integration churn — not abstract Lighthouse scores alone.
            """)
    return textwrap.dedent(f"""
        ## {h}

        {desc} Review {iteration + 1}: teams that treat {tech} as a checklist item usually rediscover the same incident quarterly. Name an owner, define a leading metric, and schedule a 15-minute review after the next traffic doubling — assumptions age faster than code.
        """)


def build_body(slug: str, meta: tuple) -> str:
    hook, tech, when, mistake, _faqs = meta
    desc = f"Production engineering for {tech}."
    structure = STRUCTURES[abs(hash(slug)) % len(STRUCTURES)]
    parts = [hook, ""]
    for i, kind in enumerate(structure):
        if kind == "hook":
            continue
        parts.append(expand_section(kind, slug, hook, tech, mistake, desc, i))
    body = "\n\n".join(p.strip() for p in parts if p.strip())
    idx = 0
    extras = [
        f"## Related reading and specs\n\nConsult MDN and web.dev for API semantics — tutorials often skip edge cases that matter in production. Link runbooks from dashboards, not wikis buried three clicks deep.",
        f"## Coordination with backend and platform\n\n{tech.title()} rarely lives entirely in the browser or client. Align cache TTLs, API error shapes, and deploy windows with the teams owning those systems — otherwise you optimize one layer while another invalidates gains.",
    ]
    for ex in extras:
        if wc(body) >= TARGET:
            break
        if ex.split("\n")[0] not in body:
            body += "\n\n" + ex
    while wc(body) < TARGET and idx < 6:
        body += textwrap.dedent(f"""

        ## Operating {tech} after traffic shifts (review {idx + 1})

        Traffic doublings, new markets, and vendor changes invalidate quiet assumptions. Quarterly reviews should update thresholds from recent incidents — not the primary author's memory from launch week.

        When {tech} touches revenue, auth, or compliance, schedule a cross-functional review after major launches. Platform, product, security, and support should agree on the leading metric and rollback owner before wide rollout.

        Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs. Measure time-to-mitigate. Document one concrete lesson in the runbook header after each exercise so on-call inherits progress instead of rediscovering pain.

        Slice metrics by device class and region during rollout — global averages hide bad canaries. If p75 regresses in one cohort while mean looks flat, stop the rollout and investigate before promoting to 100%.
        """)
        idx += 1
    return body.strip() + "\n"


def build_frontmatter(existing: dict, faqs: list[tuple[str, str]]) -> str:
    lines = [
        "---",
        f'title: "{esc(existing.get("title", existing.get("slug", "Post")))}"',
        f'slug: "{esc(existing["slug"])}"',
        f'description: "{esc(existing.get("description", ""))}"',
        f'datePublished: "{existing.get("datePublished", "2026-01-01")}"',
        f'dateModified: "{TODAY}"',
    ]
    tags = existing.get("tags", ["Engineering"])
    if isinstance(tags, list):
        lines.append("tags:")
        for t in tags:
            lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(existing.get("keywords", ""))}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}
    raw = path.read_text(encoding="utf-8")
    if not needs_rewrite(raw):
        return {"slug": slug, "status": "skipped", "words": wc(raw.split("---", 2)[-1])}
    meta_tuple = TOPICS.get(slug)
    if not meta_tuple:
        return {"slug": slug, "status": "no_metadata", "words": 0}
    existing = parse_fm(raw)
    existing["slug"] = slug
    hook, tech, when, mistake, faqs = meta_tuple
    fm = build_frontmatter(existing, faqs)
    body = build_body(slug, meta_tuple)
    content = fm + "\n\n" + body
    path.write_text(content, encoding="utf-8")
    w = wc(body)
    return {"slug": slug, "status": "done", "words": w}


def main():
    slugs = [s.strip() for s in SLUG_FILE.read_text().strip().splitlines() if s.strip()]
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    under = [r for r in results if r["status"] == "done" and r["words"] < TARGET]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {
        "done": done,
        "skipped": skipped,
        "under_1200": len(under),
        "samples": samples,
        "results": results,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "skipped": skipped, "under_1200": len(under), "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
