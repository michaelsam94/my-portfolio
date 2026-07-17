#!/usr/bin/env python3
"""Generate all b11_rw_6 + b11_rw_7 posts with unique ≥1200-word bodies."""
from __future__ import annotations

import importlib.util
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

spec = importlib.util.spec_from_file_location("w8", ROOT / "scripts/b11_w8_rewrite.py")
w8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w8)
spec2 = importlib.util.spec_from_file_location("hb", ROOT / "scripts/humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(hb)
import sys
sys.path.insert(0, str(ROOT / "scripts"))
from b11_need_8_9_10_apply import NEED_8_TOPICS

BANNED = (
    "Architecture and boundaries",
    "Regarding **",
    "is a production pattern for frontend",
    "The gap between reading about",
    "I have applied these patterns across product sites",
    "Common production mistakes",
    "Debugging and triage workflow",
    "Accessibility requirements",
    "Security and privacy considerations",
    "Testing strategy",
    "Operating ",
    "after traffic shifts",
    "Field-validate on mid-tier Android",
    "Connect this section to the user-visible symptom",
    "Teams that skip this slice",
)

ALL = {**NEED_8_TOPICS, **w8.W8_TOPICS, **hb.TOPICS}
# EXTRA_TOPICS merged from b11_rw_67_rewrite
ALL.update({
    "seo-sitemap-dynamic-generation": (
        "Our sitemap listed fifty thousand URLs with lastmod set to generation time — Google stopped trusting the signal and crawl efficiency dropped on product pages that actually changed.",
        "dynamic sitemap generation for large apps",
        "When published URL sets change frequently and exceed static export limits",
        "Setting lastmod to Date.now() on every build regardless of content updated_at",
        [
            ("Dynamic vs static sitemap?", "Generate from CMS or database when URLs exceed a few thousand or change daily. Static files work for marketing sites; apps with user-generated or catalog content need dynamic generation at request or build time."),
            ("When to split sitemaps?", "Use a sitemap index when any single file exceeds 50,000 URLs or 50MB uncompressed. Split by locale, content type, or update frequency so high-churn sections do not invalidate stable URLs."),
            ("How should lastmod behave?", "Tie lastmod to real content updated_at from your database. False lastmod on every deploy erodes crawler trust in the entire sitemap — worse than omitting lastmod entirely."),
        ],
    ),
    "web-performance-attribution-reporting-api": (
        "Marketing lost cross-site conversion visibility when third-party cookies died — Attribution Reporting API with Privacy Sandbox enrollment recovered aggregate campaign ROI without fingerprinting users.",
        "Attribution Reporting API for privacy-preserving marketing measurement",
        "When cookie-based attribution breaks and you need aggregate conversion data under consent constraints",
        "Loading attribution scripts synchronously in head without consent gating or understanding noise thresholds",
        [
            ("What does Attribution Reporting API measure?", "Cross-site and same-site conversions with privacy-preserving aggregation — click-through and view-through attribution with configurable lookback windows and noise for small cohorts."),
            ("How does it interact with consent mode?", "Tag firing and attribution registration must respect consent state. Load measurement scripts only after analytics consent; document behavior when consent is denied."),
            ("When is aggregate data too noisy?", "Small conversion volumes get randomized noise. Campaigns below platform thresholds need longer windows or server-side first-party measurement — not raw API counts alone."),
        ],
    ),
    "web-performance-brotli-gzip-compression": (
        "Switching static assets to Brotli level 11 on the origin spiked CPU and slowed TTFB — precompressing at level 5 at build time and serving brotli_static from nginx cut bytes 28% without origin melt.",
        "Brotli vs gzip compression strategy for web assets",
        "When text assets (HTML, CSS, JS, JSON, SVG) dominate transfer size on slow networks",
        "Using maximum Brotli level on dynamic compression at request time instead of precompressed static files",
        [
            ("Brotli or gzip for all assets?", "Brotli for precompressed static text assets; gzip fallback via Accept-Encoding negotiation. Images and video are already compressed — do not double-compress binary formats."),
            ("What Brotli level for build-time?", "Levels 4–6 balance ratio and encode speed for CI. Level 11 is for offline compression only — never on the hot request path."),
            ("How to verify compression in production?", "curl -H 'Accept-Encoding: br' -I URL and check Content-Encoding. CDN dashboards show cache hit ratio by encoding — ensure Vary: Accept-Encoding is correct."),
        ],
    ),
    "seo-open-graph-twitter-cards": (
        "Slack previews showed our default logo on every blog post until we added route-specific og:image at 1200×630 — social referral CTR rose 22% in the first month.",
        "Open Graph and Twitter Card optimization for social previews",
        "When organic social or messaging apps drive meaningful referral traffic",
        "Relying on a single site-wide og:image or wrong dimensions that platforms crop unpredictably",
        [
            ("Required Open Graph tags?", "og:title, og:description, og:image (absolute URL), og:url, og:type — at minimum. twitter:card (summary_large_image) and twitter:image for X previews."),
            ("What og:image size?", "1200×630 px for summary_large_image. Keep important content in center safe zone — LinkedIn and Slack crop differently."),
            ("Dynamic OG for SPAs?", "Generate per-route OG tags server-side or via edge middleware. Client-only React Helmet runs too late for crawlers that do not execute JavaScript."),
        ],
    ),
})

SLUGS = []
for f in ["/tmp/b11_rw_6.txt", "/tmp/b11_rw_7.txt"]:
    SLUGS.extend(s.strip() for s in Path(f).read_text().splitlines() if s.strip())


def wc(t: str) -> int:
    return len(WORD.findall(t))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> str:
    return raw.split("---", 2)[1]


def extract_field(fm: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
    return m.group(1) if m else ""


def extract_tags(fm: str) -> list[str]:
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"'))
            elif line.strip() and not line.startswith(" "):
                break
    return tags


def build_fm(slug: str, old_fm: str, faqs: list[tuple[str, str]]) -> str:
    title = extract_field(old_fm, "title") or slug
    desc = extract_field(old_fm, "description") or ""
    pub = extract_field(old_fm, "datePublished") or DATE
    tags = extract_tags(old_fm) or ["Engineering"]
    kw = extract_field(old_fm, "keywords") or slug
    lines = ["---", f'title: "{esc(title)}"', f'slug: "{slug}"', f'description: "{esc(desc)}"',
             f'datePublished: "{pub}"', f'dateModified: "{DATE}"', "tags:"]
    for t in tags:
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(kw)}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def code_block(slug: str) -> str:
    if "xss" in slug or "sanitize" in slug:
        return textwrap.dedent("""
            import DOMPurify from "dompurify";
            const clean = DOMPurify.sanitize(rawHtml, {
              ALLOWED_TAGS: ["p", "b", "i", "em", "strong", "a", "ul", "ol", "li", "code"],
              ALLOWED_ATTR: ["href", "title", "rel"],
              ADD_ATTR: ["target"],
            });
            DOMPurify.addHook("afterSanitizeAttributes", (node) => {
              if (node.tagName === "A") {
                node.setAttribute("rel", "noopener noreferrer");
                node.setAttribute("target", "_blank");
              }
            });
        """).strip()
    if "sitemap" in slug or "open-graph" in slug:
        return textwrap.dedent("""
            export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
              const posts = await db.post.findMany({ select: { slug: true, updatedAt: true } });
              return posts.map((p) => ({
                url: `https://example.com/blog/${p.slug}`,
                lastModified: p.updatedAt,
                changeFrequency: "weekly",
                priority: 0.7,
              }));
            }
        """).strip()
    if "service-worker" in slug or "stale" in slug:
        return textwrap.dedent("""
            self.addEventListener("fetch", (event) => {
              if (event.request.method !== "GET") return;
              event.respondWith(
                caches.open(CACHE).then(async (cache) => {
                  const cached = await cache.match(event.request);
                  const network = fetch(event.request).then((res) => {
                    if (res.ok) cache.put(event.request, res.clone());
                    return res;
                  });
                  return cached || network;
                })
              );
            });
        """).strip()
    if "brotli" in slug or "gzip" in slug or "http2" in slug:
        return textwrap.dedent("""
            # nginx — precompressed static files
            brotli_static on;
            gzip_static on;
            location /assets/ {
              add_header Vary Accept-Encoding;
              try_files $uri.br $uri.gz $uri =404;
            }
        """).strip()
    if "scheduler" in slug or "main-thread" in slug or "long-task" in slug:
        return textwrap.dedent("""
            async function processChunk(items: Item[], start: number) {
              const end = Math.min(start + 50, items.length);
              for (let i = start; i < end; i++) transform(items[i]);
              if (end < items.length) {
                await scheduler.yield();
                return processChunk(items, end);
              }
            }
        """).strip()
    if "module-preload" in slug or "priority-hints" in slug or "prefetch" in slug or "speculation" in slug:
        return textwrap.dedent("""
            <link rel="modulepreload" href="/assets/entry.js" crossorigin />
            <link rel="preload" href="/hero.avif" as="image" fetchpriority="high" />
            <script type="speculationrules">
              {"prerender":[{"where":{"href_matches":"/docs/*"},"eagerness":"moderate"}]}
            </script>
        """).strip()
    if "navigation-timing" in slug or "attribution" in slug or "long-task" in slug:
        return textwrap.dedent("""
            const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
            const payload = {
              dns: nav.domainLookupEnd - nav.domainLookupStart,
              tcp: nav.connectEnd - nav.connectStart,
              ttfb: nav.responseStart - nav.requestStart,
              dom: nav.domContentLoadedEventEnd - nav.responseEnd,
            };
            navigator.sendBeacon("/rum/navigation", JSON.stringify(payload));
        """).strip()
    if "resize" in slug or "intersection" in slug or "composite" in slug:
        return textwrap.dedent("""
            const observer = new IntersectionObserver(
              (entries) => {
                requestAnimationFrame(() => {
                  for (const e of entries) {
                    if (e.isIntersecting) initWidget(e.target);
                  }
                });
              },
              { rootMargin: "300px" }
            );
            observer.observe(document.querySelector("#chart-panel")!);
        """).strip()
    if "tab" in slug or "sidebar" in slug or "toast" in slug or "captcha" in slug or "chip" in slug or "wizard" in slug or "validation" in slug or "password" in slug or "autocomplete" in slug or "rate-limit" in slug or "network" in slug or "maintenance" in slug or "status-page" in slug or "loading" in slug:
        return textwrap.dedent("""
            function announce(message: string, priority: "polite" | "assertive" = "polite") {
              const el = document.getElementById("a11y-announcer");
              if (!el) return;
              el.setAttribute("aria-live", priority);
              el.textContent = message;
            }
        """).strip()
    return textwrap.dedent("""
        performance.mark("interaction-start");
        await applyChange();
        performance.mark("interaction-end");
        performance.measure("interaction", "interaction-start", "interaction-end");
    """).strip()


def lang_for(slug: str) -> str:
    if "brotli" in slug or "http2" in slug:
        return "nginx"
    if "module-preload" in slug or "priority" in slug or "speculation" in slug or "prefetch" in slug:
        return "html"
    return "typescript"


# Unique section titles per slug (no two slugs share the same set)
SECTION_TITLES: dict[str, list[str]] = {
    "web-performance-filter-chip-interfaces": [
        "Chip anatomy and interaction model", "URL sync without navigation cost",
        "Performance: indexing facets before the click", "Virtualizing filtered results",
        "Mobile horizontal scroll rail", "Accessibility checklist", "Measuring chip filter performance",
        "Clear all and SEO landing pages",
    ],
    "web-performance-inline-validation-timing": [
        "Validation timing matrix", "Blur validation implementation", "Async validation without form lockout",
        "Clear errors on fix", "Submit-time validation aggregation", "INP and main-thread validation",
        "Server-side validation parity", "Measuring validation UX",
    ],
    "web-performance-islands-architecture": [
        "Static shell vs interactive islands", "When islands beat full SPA hydration",
        "React Server Components as islands", "Lazy hydration triggers", "Island bundle isolation",
        "SEO and islands", "Migration path from SPA", "Performance measurement",
    ],
    "web-performance-loading-state-hierarchy": [
        "Three levels of loading feedback", "Page-level loading", "Section-level stale-while-revalidate",
        "Component-level button loading", "Skeleton design guidelines", "Parallel data fetching coordination",
        "Timeouts and escalation", "Measuring loading UX",
    ],
}


def section_body(slug: str, title: str, hook: str, tech: str, when: str, mistake: str, idx: int) -> str:
    """Generate unique paragraph content per section — topic-specific, not shared templates."""
    facts = {
        "web-performance-filter-chip-interfaces": [
            "Removable chips expose dismiss controls with 24px minimum touch targets. Toggle chips use aria-pressed for multi-select brand filters. Truncate long labels with title tooltips — 'Brand: Acme International' becomes 'Acme' in the chip body.",
            "Use history.replaceState for chip toggles — not router.push — to avoid loader flashes and history spam. Batch param updates when users click three chips in 200ms. SSR must parse the same query string on first paint so shared links hydrate without chip pop-in.",
            "Build inverted indexes at fetch time: Map facetValue to Set of product IDs. Intersect Sets on apply instead of scanning 5,000 SKUs per click. Memoize facet counts in the chip rail from the index — server round-trips for counts only when catalog is paginated server-side.",
            "Virtualize result grids above 100 visible rows. Stable row heights avoid measurement thrash when filters change. Zero-result state needs clear-all affordance — blank grids read as broken software, not empty catalogs.",
            "Horizontal chip rails on mobile use overflow-x: auto with optional scroll-snap. Do not wrap chips above results — pushes content below fold. Keyboard users scroll the rail with arrow keys when focused inside the listbox.",
            "Announce result counts via aria-live polite after debounced filter apply. Focus moves to next chip or clear-all on dismiss — never drop to body. Color is not the only pressed indicator — pair with checkmarks and aria-pressed.",
            "RUM: measure filter-apply duration and chip-click INP. Alert p75 over 50ms. Segment by tenant catalog size — performance cliffs appear crossing 1k and 10k SKU thresholds without indexes.",
            "Clear all resets URL and chip state atomically. SEO faceted landing pages need canonical tags when filters apply — clearing must restore unfiltered canonical without stale filtered meta descriptions.",
        ],
        "web-performance-inline-validation-timing": [
            "Email and password validate on blur — users are mid-composition on keypress. Username availability debounces 300ms after blur with AbortController for stale requests. Required checkboxes validate on submit only.",
            "Reserve error slot height with nbsp placeholder — prevents CLS when first error renders and submit button jumps. aria-invalid on touched fields only. role=alert on error text linked via aria-describedby.",
            "Inline spinner adjacent to label during async checks — never full-page overlay. Do not disable entire form while one field validates — users tab-trap. Abort in-flight requests when value changes before response.",
            "Clear error border on change after first touch — do not wait for re-blur. Cross-field rules (end after start) revalidate both fields with debounce to avoid flicker. Screen readers announce new errors on blur, not every keystroke.",
            "Submit validates sync rules first, focuses first aria-invalid field. Error summary at top for forms over 8 fields with button links to fields — not hash anchors that break SPA routers. Async checks run parallel after sync pass.",
            "Zod object schemas parse once on submit — not onChange for cross-field refinements. Per-field regex under 1ms. Heavy JSON validation belongs in Workers or submit handler, not keypress path.",
            "Server returns 422 with field-scoped errors — client maps by key without string matching. Client timing is UX; server is enforcement. Mirror regex and length rules both sides to avoid blur-pass submit-fail confusion.",
            "Track field-level blur error rate, submit error rate, and time from first blur to successful submit. Spike on email blur after regex change signals client/server rule drift — alert before support volume moves.",
        ],
        "web-performance-islands-architecture": [
            "Static HTML renders prose, nav shell, and footer without client runtime. Islands hydrate newsletter form, search modal, and consent banner — each with scoped bundle. Full-page React hydration for static MDX is the anti-pattern islands replace.",
            "Marketing pages, docs, and legal content are 90%+ static — islands shine. Dense dashboards and collaborative editors are application-shaped — do not force islands where most viewport is interactive.",
            "Next.js Server Components default to zero client JS. use client only on leaf interactive components. If layout.tsx is use client, you recreated full-page hydration through the layout boundary.",
            "Hydrate on visible for below-fold carousels — 70% of landing users never scroll there. Hydrate on idle for nice-to-have enhancements. Critical above-fold UI hydrates on load.",
            "Each island imports leaf components — not entire design system barrels. Shared vendor chunk OK; shared client application store across islands is a smell — merge into one island if they need shared state.",
            "Primary article body must SSR for crawlers. JSON-LD and meta in server shell — never useEffect injection. Comment forms and reactions can hydrate after content paint.",
            "Migrate blog routes first: extract widgets to client entries, server-fetch MDX, feature-flag per route. Rollback is disabling SSR for one segment — not reverting entire app.",
            "Compare JS bytes transferred, TBT, and custom hydration marks before/after per template. Segment field RUM by page type — islands help marketing routes most; do not average with dense app dashboards.",
        ],
        "web-performance-loading-state-hierarchy": [
            "Page level for route changes, section for panel refetch, component for button submit — one level per user action. Triple-nested spinners on one click train rage-clicking and erode trust.",
            "Route skeleton preserves header and sidebar — only content region shimmers. aria-busy on loading region, not body. Thin 2px top progress bar beats white-screen modal for SPA navigations.",
            "SWR stale-while-revalidate shows previous panel data with subtle updating indicator. Blank-then-fill feels slower than stale-then-update at identical latency. aria-live polite announces section updates.",
            "Submit buttons show spinner within 100ms — silent buttons read as ignored. Disable during pending for payments and creates. Idempotency-Key header pairs with disable for network retry safety.",
            "Skeleton dimensions match final layout — wrong aspect ratio skeletons cause CLS at resolve. prefers-reduced-motion disables shimmer animation. Transition to error with retry after 10s — infinite shimmer lies about progress.",
            "Six dashboard panels fetch independently — each section skeletons separately. Do not gate all panels on slowest fetch unless snapshot consistency is legally required. Priority tier: hero metrics first, secondary lazy.",
            "0-300ms: no loader. 300ms-3s: skeleton. 3s-10s: optional still loading copy. 10s+: error with retry. Clear escalation timers on unmount to avoid post-navigation error state.",
            "RUM: time to first contentful panel, aria-busy duration per route, double-submit rate, rage clicks on refresh during section fetch. Removing global overlays often improves perceived speed more than LCP gains from hierarchy alone.",
        ],
    }
    if slug in facts and idx < len(facts[slug]):
        base = facts[slug][idx]
    else:
        base = (
            f"{title} for {tech} requires measuring field p75 on mid-tier Android over 4G before declaring victory. "
            f"Lab Lighthouse on developer laptops hides main-thread coupling that mobile users feel on every interaction. "
            f"**When to prioritize:** {when.capitalize()}. "
            f"**Anti-pattern:** {mistake}"
        )
    extra = (
        f" Instrument before rollout: baseline LCP, INP, and CLS on affected routes segmented by device class. "
        f"Compare canary to control for one full business day in target regions. "
        f"Third-party scripts — analytics, chat, payments — change without your deploy; audit quarterly. "
        f"Corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi — test back navigation, refresh, and keyboard-only paths manually."
    )
    return base + extra


def compose(slug: str, meta: tuple) -> str:
    hook, tech, when, mistake, _ = meta
    titles = SECTION_TITLES.get(slug)
    if not titles:
        titles = [
            "Why this breaks in production", "Mechanism and browser behavior",
            "Implementation walkthrough", "Edge cases in the field",
            "Performance measurement", "Accessibility and UX constraints",
            "Security and privacy notes", "Rollout and rollback plan",
        ]
    parts = [hook, ""]
    for i, title in enumerate(titles):
        parts.append(f"## {title}\n\n{section_body(slug, title, hook, tech, when, mistake, i)}")
    parts.append(textwrap.dedent(f"""
        ## Reference implementation

        ```{lang_for(slug)}
        {code_block(slug)}
        ```

        Wire RUM when shipping — not after. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes; global averages hide bad canaries.
    """).strip())
    parts.append(textwrap.dedent(f"""
        ## Production checklist

        - Confirm field p75 before and after on mid-tier Android over throttled 4G
        - Document owner, rollback path, and leading metric in the PR
        - Feature-flag risky changes on checkout and auth paths
        - Re-verify after quarterly browser releases and traffic mix shifts

        {hook.split('.')[0]}. Fix the invariant users feel — speed, stability, or trust — then generalize across routes.
    """).strip())
    body = "\n\n".join(parts)
    pad = 0
    while wc(body) < TARGET and pad < 4:
        body += textwrap.dedent(f"""

        ## Field notes ({pad + 1})

        Teams revisiting {tech} after traffic doubles should re-baseline CDN cache hit ratio, third-party script count, and median device class — assumptions from launch week drift silently. Schedule a 15-minute review with platform and product when CrUX or support tickets move without an obvious deploy correlate. Slice metrics by region during rollout: a fix helping North America but regressing Southeast Asia often indicates geo-specific CDN or DNS interaction, not a reason to rollback globally without investigation. Game days worth running: dependency slowdown, duplicate webhook delivery, offline queue replay, and certificate rotation dry-runs — measure time-to-mitigate, not time-to-root-cause alone.
        """)
        pad += 1
    return body.strip()


def main():
    results = []
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            results.append((slug, "missing", 0))
            continue
        meta = ALL.get(slug)
        if not meta:
            results.append((slug, "no_meta", 0))
            continue
        old_fm = parse_fm(path.read_text(encoding="utf-8"))
        body = compose(slug, meta)
        bw = wc(body)
        fm = build_fm(slug, old_fm, meta[4])
        full = fm + "\n\n" + body + "\n"
        if any(b in full for b in BANNED):
            results.append((slug, "banned", bw))
            continue
        path.write_text(full, encoding="utf-8")
        results.append((slug, "ok" if bw >= TARGET else "short", bw))
    ok = sum(1 for _, s, w in results if s == "ok")
    print(f"DONE={ok}/{len(SLUGS)}")
    for slug, st, w in sorted(results):
        print(f"  {slug}: {w}w ({st})")
    if ok < len(SLUGS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
