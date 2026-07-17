#!/usr/bin/env python3
"""Humanize + deep-dive rewrite for /tmp/b11_w8.txt (20 web-performance posts)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILE = Path("/tmp/b11_w8.txt")
TARGET = 1200

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

W8_TOPICS: dict[str, tuple] = {
    "web-performance-http2-multiplexing-assets": (
        "We shipped HTTP/2 on the CDN and split our 400 KB vendor bundle into twelve files — LCP regressed 300 ms because parse cost dominated the pretty parallel waterfall.",
        "HTTP/2 multiplexing and asset loading strategy",
        "When your CDN serves h2/h3 and you are revisiting HTTP/1.1 bundling assumptions",
        "Unbundling everything because multiplexing removes connection limits while ignoring JavaScript parse and cache invalidation cost",
        [
            ("Does HTTP/2 make bundling unnecessary?", "Multiplexing removes per-connection queues but bundling still affects parse cost and cache granularity. Use route-level chunks with long-lived vendor bundles, not one file or twelve micro-files without measurement."),
            ("Why was HTTP/2 Server Push deprecated?", "Push sent resources browsers often cached, wasting bandwidth. Use 103 Early Hints or link preload instead — browsers respect cache state when deciding to fetch."),
            ("How do I verify HTTP/2 is active?", "DevTools Network Protocol column shows h2 or h3. Log nextHopProtocol in RUM to segment users on HTTP/1.1 fallback."),
        ],
    ),
    "web-performance-http3-quic-benefits": (
        "Desktop A/B showed no LCP gain from HTTP/3; mobile p75 improved 180 ms on lossy LTE because QUIC isolates stream loss from whole-connection stalls.",
        "HTTP/3 and QUIC for web applications",
        "When mobile tail latency and packet loss dominate your field metrics",
        "Enabling QUIC and declaring victory without segmenting RUM by protocol and geography",
        [
            ("When does HTTP/3 beat HTTP/2?", "On lossy mobile and international routes — often 0–5% on clean desktop fiber. Measure your audience before investing in custom QUIC origin setup."),
            ("Do I change application code for HTTP/3?", "Usually no — enable at CDN edge. Origin still speaks HTTP/1.1 or HTTP/2 to the edge in most architectures."),
            ("What blocks HTTP/3 in enterprise?", "Firewalls blocking UDP/443. Browsers fall back to HTTP/2 silently — monitor h3 ratio by customer segment."),
        ],
    ),
    "web-performance-image-formats-avif": (
        "Converting hero JPEGs to AVIF at equivalent quality cut homepage weight 42% and LCP 900 ms on 4G — WebP alone had saved less than half that.",
        "AVIF and WebP image delivery",
        "When image bytes dominate LCP resource load duration on photo-heavy pages",
        "Serving AVIF without picture fallbacks, wrong sizes attributes, or lazy-loading the LCP hero",
        [
            ("AVIF or WebP in 2026?", "AVIF first with WebP and JPEG fallbacks via picture or CDN negotiation. SVG for icons; PNG when lossless UI artifacts matter."),
            ("Does AVIF slow CI?", "Encode is CPU-heavy — precompute in build or CDN on first request. Never synchronous encode on the hot request path."),
            ("Do formats fix LCP alone?", "No — SSR the hero, preload, set dimensions, then optimize format. Format is step four, not step one."),
        ],
    ),
    "web-performance-import-maps-cdn": (
        "Design system docs shipped React demos without webpack using import maps — until an unpinned CDN URL upgraded Friday night and broke hydration.",
        "import maps with CDN-hosted ES modules",
        "When you want native modules without a bundler on documentation or lightweight surfaces",
        "Unpinned CDN URLs and missing Subresource Integrity on mapped module graphs",
        [
            ("What do import maps solve?", "They resolve bare specifiers like 'react' to URLs. Without them, only relative and absolute imports work in native modules."),
            ("Are CDN import maps production-safe?", "Only with pinned versions, SRI, and self-hosted copies for SLAs — treat like any third-party script supply chain."),
            ("Do import maps replace bundlers?", "Rarely at scale — tree-shaking and code splitting still favor Vite/webpack for large apps."),
        ],
    ),
    "web-performance-inline-validation-timing": (
        "Real-time email validation on every keystroke pushed checkout abandonment up — blur validation with reserved error space recovered conversion without losing correctness.",
        "inline form validation timing",
        "When long forms or checkout need errors that help instead of interrupt",
        "Validating on input before the user finishes composing the value",
        [
            ("Keystroke or blur validation?", "Blur for most fields. Keystroke only for non-punitive hints like character count or phone masking."),
            ("When is async validation worth it?", "Username availability, coupons, tax IDs — debounce after blur, never global form lockout."),
            ("How to announce errors accessibly?", "aria-describedby to role=alert on blur/submit — not on every keypress. Focus first invalid field on submit."),
        ],
    ),
    "web-performance-inp-interaction": (
        "Support said the pay button was broken — RUM showed 680 ms INP on Android from a click handler that recalculated tax synchronously before showing a spinner.",
        "Interaction to Next Paint optimization",
        "When field INP fails Core Web Vitals while LCP looks fine",
        "Optimizing lab Lighthouse while ignoring worst-click attribution in RUM",
        [
            ("What counts as an INP interaction?", "Click, tap, key press until next paint with feedback — not scroll or hover alone."),
            ("Good INP target?", "200 ms or less at p75 in field data — not lab synthetic clicks on developer laptops."),
            ("Debouncing vs scheduler.yield?", "Debounce reduces frequency; yield splits long main-thread work so input can paint between chunks."),
        ],
    ),
    "web-performance-intersection-observer-debounce": (
        "Chart.js loaded on every product page until Intersection Observer with 300 px rootMargin initialized it only when users scrolled — 180 ms less JS on first load.",
        "Intersection Observer for lazy initialization",
        "When heavy widgets sit below the fold or off-screen on first paint",
        "Using scroll listeners with getBoundingClientRect instead of Intersection Observer",
        [
            ("What rootMargin should I use?", "Start 200–400 px below viewport — tune by widget weight. Never IO-lazy the LCP image."),
            ("Disconnect after first intersection?", "Yes for one-shot init. Keep observing only for pause/resume behaviors like video."),
            ("Better than scroll listeners?", "Yes — IO callbacks are async and coalesced; scroll handlers force layout every frame."),
        ],
    ),
    "web-performance-islands-architecture": (
        "Marketing shipped 340 KB JavaScript so one FAQ accordion could toggle — islands reduced first-load JS to 45 KB by hydrating only interactive leaves.",
        "islands architecture and partial hydration",
        "When static content dominates pages wrapped in full SPA hydration",
        "Marking the page root as client component when only small regions need JavaScript",
        [
            ("Islands in one sentence?", "Mostly static HTML with small interactive regions that hydrate independently with scoped JS bundles."),
            ("Different from code splitting?", "Code splitting still hydrates a root runtime — islands skip hydration for static regions entirely."),
            ("Islands in Next.js?", "Server Components are the React expression — push 'use client' to the smallest interactive subtree."),
        ],
    ),
    "web-performance-layout-shift-debugging": (
        "CrUX CLS 0.18 on homepage but lab 0.02 — field logging showed EU consent banner injecting 72 px without reserved space on first visit only.",
        "layout shift debugging with field attribution",
        "When CrUX CLS fails but lab reproduction is inconsistent",
        "Fixing CLS from Lighthouse alone without Layout Instability API in RUM",
        [
            ("How to find shifting elements?", "PerformanceObserver layout-shift entry.sources — log tag, class, rects in RUM above threshold."),
            ("Do web fonts always cause CLS?", "Only when metrics differ from fallback — use size-adjust, preload, font-display optional."),
            ("Exclude user-initiated shifts?", "Some tools exclude hadRecentInput — still reserve space for modals and accordions users trigger."),
        ],
    ),
    "web-performance-lcp-optimization": (
        "Product LCP was 4.8 s because the hero image was injected three seconds after client fetch — SSR plus preload brought it to 1.6 s with the same bytes.",
        "Largest Contentful Paint optimization",
        "When LCP element is known and TTFB or discovery order is the bottleneck",
        "Lazy-loading the hero or using CSS background-image for the LCP candidate",
        [
            ("What can be the LCP element?", "Usually hero img, large text block, or video poster — not below-fold content or iframes."),
            ("Why preload LCP image?", "Starts fetch during HTML parse — saves discovery chain through CSS or late JavaScript."),
            ("TTFB and LCP?", "LCP cannot start until HTML arrives — fix TTFB before micro-optimizing compression."),
        ],
    ),
    "web-performance-loading-state-hierarchy": (
        "Users triple-clicked Refresh because a full-screen spinner blocked the dashboard while only the recommendations panel refetched.",
        "loading state hierarchy across page, section, and component",
        "When parallel data fetches and route transitions need scoped feedback",
        "Global loading overlays for partial refetches that leave most of the page usable",
        [
            ("What is loading hierarchy?", "Page-level for route changes, section-level for panels, component-level for buttons — never all three nested."),
            ("Skeletons vs spinners?", "Skeletons for content-shaped waits over 300 ms; spinners for short indeterminate actions."),
            ("Should loading block the UI?", "Only irreversible actions — use stale-while-revalidate for parallel sections."),
        ],
    ),
    "web-performance-long-tasks-monitoring": (
        "INP regressed after tag manager update — long task beacons attributed 340 ms blocks to session replay running synchronously on every click in production only.",
        "long task monitoring in production RUM",
        "When INP regresses without obvious lab reproduction",
        "Monitoring INP without long task attribution to script URLs",
        [
            ("What is a long task?", "Main thread work exceeding 50 ms — blocks input and contributes to INP input delay."),
            ("Identify causing script?", "Chrome PerformanceLongTaskTiming.attribution — containerSrc and containerName when available."),
            ("How many long tasks acceptable?", "Eliminate during first 3 s on critical routes; zero synchronous long tasks on click handlers."),
        ],
    ),
    "web-performance-main-thread-work": (
        "CSV import froze the tab four seconds — not network, but 80 MB parsed synchronously in the click handler before any progress UI painted.",
        "reducing main thread work with yield and workers",
        "When long tasks block input despite fast network and small bundles",
        "Running CPU-heavy work synchronously in click handlers without yield or Web Workers",
        [
            ("Main thread work?", "Parse, JS, style, layout, paint, input — all compete on one thread in typical pages."),
            ("Worker vs scheduler.yield?", "Workers for CPU without DOM; yield for chunked DOM-touching updates between frames."),
            ("Is requestIdleCallback still relevant?", "Yes for background prefetch and analytics — never for user-visible feedback paths."),
        ],
    ),
    "web-performance-maintenance-mode-page": (
        "Maintenance page said 'back soon' with no ETA while status.example.com had the timeline — two hundred tickets asked whether to wait five minutes or five hours.",
        "maintenance mode page UX and HTTP semantics",
        "During planned downtime when you must communicate without breaking SEO trust",
        "Returning 200 OK with maintenance body or omitting Retry-After on 503 responses",
        [
            ("HTTP status for maintenance?", "503 Service Unavailable with Retry-After for temporary planned work — not 200 substituting homepage."),
            ("Admin bypass?", "Edge cookie or IP allowlist — never client-only bypass that leaks partial app shell."),
            ("Auto-refresh?", "Yes every 30–60 s with health check endpoint excluded from maintenance routing."),
        ],
    ),
    "web-performance-memory-leak-detection": (
        "After a day of route changes, Chrome showed 1.8 GB heap from 14,000 detached divs retained by a scroll cache Map that never deleted on unmount.",
        "memory leak detection in SPAs",
        "When the app slows after long sessions or many client navigations",
        "Global Maps caching DOM nodes or listeners without cleanup on route unmount",
        [
            ("Common SPA leak causes?", "Uncleared listeners, timers, detached DOM references, unbounded module-level caches."),
            ("Leak vs normal growth?", "Repeat flow ten times after GC — retained detached nodes should not climb each cycle."),
            ("Performance impact without crash?", "More GC pauses, worse INP, mobile tab kills — 'refresh fixes it' is a leak signal."),
        ],
    ),
}

# Slugs 16–20 use hb.TOPICS from chunk3
ALL_TOPICS = {**hb.TOPICS, **W8_TOPICS}


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}
    meta = ALL_TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_metadata", "words": 0}
    raw = path.read_text(encoding="utf-8")
    existing = hb.parse_fm(raw)
    existing["slug"] = slug
    fm = hb.build_frontmatter(existing, meta[4])
    body = hb.build_body(slug, meta)
    path.write_text(fm + "\n\n" + body, encoding="utf-8")
    w = hb.wc(body)
    status = "done" if w >= TARGET else "under_target"
    return {"slug": slug, "status": status, "words": w}


def main() -> None:
    slugs = [s.strip() for s in SLUG_FILE.read_text().splitlines() if s.strip()]
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {"done": done, "total": len(slugs), "results": results, "samples": samples}
    out = ROOT / "scripts" / "humanize-progress" / "b11-w8.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples}, indent=2))
    for r in results:
        if r["status"] != "done":
            print(f"  ISSUE: {r['slug']} — {r['status']} ({r['words']} words)")


if __name__ == "__main__":
    main()
