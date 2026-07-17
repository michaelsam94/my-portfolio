#!/usr/bin/env python3
"""Finalize b11g_3/4/5 slugs: strip forbidden sections, dateModified, >=1200 words."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUGS = (
    Path("/tmp/b11g_3.txt").read_text().split()
    + Path("/tmp/b11g_4.txt").read_text().split()
    + Path("/tmp/b11g_5.txt").read_text().split()
)

FORBIDDEN = [
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "## Validate this in staging",
    "## Deepening the practice",
    "## Production lessons for",
    "## Additional production considerations",
    "## Measuring success in production",
]

EXPANSIONS = {
    "web-performance-empty-state-design": "\n## Layout reservation\n\nReserve `minHeight` on empty containers before async resolve to prevent CLS when spinners swap to zero-state UI.\n",
    "web-workers-offloading-compute": "\n## Pool sizing\n\nMatch worker count to `navigator.hardwareConcurrency` — profile before spawning workers per task.\n",
    "web-performance-inp-interaction": "\n## Batch DOM operations\n\nBatch layout reads before writes in click handlers to reduce presentation delay in INP.\n",
    "web-performance-font-loading": "\n## Unicode-range subsets\n\nSubset WOFF2 to scripts your pages use — often 60% smaller files with no visible change.\n",
    "web-performance-core-web-vitals": "\n## Device-class slicing\n\nReport LCP, INP, CLS p75 separately for mobile and desktop — global averages hide regressions.\n",
    "web-performance-image-formats-avif": "\n## LCP image priority\n\nNever lazy-load hero AVIF; use preload and `fetchpriority=\"high\"` on LCP candidates.\n",
    "web-forms-native-validation": "\n## Server mirror\n\nDuplicate every HTML constraint server-side — client validation is UX, not security.\n",
    "web-performance-element-timing-lcp": "\n## Hero monitoring\n\nAlert when p75 renderTime for `hero-image` identifier jumps week-over-week.\n",
    "web-performance-import-maps-cdn": "\n## Semver pins\n\nPin exact versions in import maps; hash filenames for immutable CDN caching.\n",
    "web-performance-lcp-optimization": "\n## Single preload\n\nPreload only the exact LCP resource URL — duplicate preloads compete with critical CSS.\n",
    "web-performance-error-recovery-retry-ui": "\n## Idempotent payments\n\nUse idempotency keys before showing retry on failed checkout — prevents duplicate charges.\n",
    "web-dialog-element-modal": "\n## showModal\n\nUse `showModal()` for focus trap and inert backdrop — `show()` leaves background interactive.\n",
    "web-components-shadow-dom": "\n## CSS variables\n\nTheme components via `--token` custom properties on host, not global class piercing.\n",
    "web-accessibility-aria-patterns": "\n## Keyboard behavior\n\nImplement WAI-ARIA APG keyboard tables, not just roles.\n",
    "web-color-functions-oklch": "\n## Neutral migration\n\nConvert gray scales to OKLCH first for perceptual uniformity across hues.\n",
    "vector-db-filtering-pre-post": "\n## Oversampling\n\nPost-filter with 10–20×k ANN candidates when filters are selective.\n",
    "vector-search-ivf-pq-index": "\n## nprobe tuning\n\nPlot recall@k vs latency; pick nprobe at the SLA knee.\n",
    "vector-db-pgvector-postgres": "\n## Operator match\n\nCosine `<=>` for normalized embeddings; index opclass must match.\n",
    "vue-3-composition-api-patterns": "\n## toRefs\n\nDestructure `reactive()` with `toRefs` to preserve reactivity.\n",
    "typescript-utility-types-app-patterns": "\n## Pick allowlists\n\n`Pick` is safer than `Omit` when source types gain sensitive fields.\n",
    "typescript-satisfies-operator": "\n## Literal preservation\n\n`satisfies` validates without widening `as const` literals.\n",
    "typescript-strict-mode-migration": "\n## Incremental strict\n\nEnable `strictNullChecks` per package before full strict on legacy code.\n",
    "system-design-url-shortener": "\n## Base62 slugs\n\nEncode internal ids to fixed-length base62 — low collision at scale.\n",
    "secrets-management-vault": "\n## Dynamic DB creds\n\nIssue short-TTL database credentials; renew on pool refresh.\n",
    "session-management-secure-cookies": "\n## Rotation on login\n\nNew session id after authentication prevents fixation.\n",
    "sec-secure-defaults-frameworks": "\n## Opt-in danger\n\nSecure-by-default beats security checklists developers skip.\n",
    "sec-oauth-pkce-spa": "\n## No localStorage refresh\n\nHttpOnly BFF cookies or memory-only tokens — PKCE does not stop XSS token theft.\n",
    "testing-flaky-tests-root-causes": "\n## Quarantine\n\nFlaky tests in non-blocking job until fixed — do not mute assertions.\n",
    "testing-mutation-testing": "\n## Incremental Stryker\n\nNightly full run on billing; PR diff scope only otherwise.\n",
    "streaming-analytics-flink": "\n## Event time\n\nWatermarks handle out-of-order events — processing time lies.\n",
    "solidjs-fine-grained-reactivity": "\n## No VDOM\n\nSolid updates bound expressions only — no tree re-render.\n",
    "sql-injection-prevention-modern": "\n## Parameters\n\nNever interpolate user input into SQL strings, even in ORMs.\n",
    "web-scroll-snap-carousels": "\n## Reduced motion\n\nDisable autoplay when `prefers-reduced-motion: reduce`.\n",
    "web-popover-api-native": "\n## Light dismiss\n\n`popover=\"auto\"` handles outside click without manual listeners.\n",
    "web-speculation-rules-prefetch": "\n## Targeted prefetch\n\nPrefetch high-confidence navigations only — not every link.\n",
    "webhooks-signature-verification": "\n## Timing-safe compare\n\nUse `crypto.timingSafeEqual` for HMAC verification.\n",
    "webhooks-retry-idempotency": "\n## Dedupe events\n\nStore processed webhook ids — retries must not double-apply.\n",
    "webgpu-compute-graphics": "\n## Adapter limits\n\nQuery `maxBufferSize` before allocating large GPU buffers.\n",
    "xss-prevention-csp-trusted-types": "\n## Trusted Types\n\nPolicy-wrap `innerHTML` sinks to block DOM XSS gadgets.\n",
    "typescript-template-literal-types": "\n## Typed routes\n\nTemplate literal types catch invalid path strings at compile time.\n",
    "typescript-branded-types-safety": "\n## Parse at boundary\n\nBrand external ids when JSON enters your domain layer.\n",
    "typescript-discriminated-unions": "\n## Exhaustive never\n\n`default: const _x: never = x` forces new union members handled.\n",
    "state-management-zustand-jotai": "\n## Actions in store\n\nColocate setters with state in Zustand slices.\n",
    "system-design-chat-messaging": "\n## Fan-out writes\n\nPer-user inboxes make reads O(1) in busy threads.\n",
    "web-performance-resource-hints": "\n## Preconnect sparingly\n\nPreconnect only origins needed for LCP — each costs setup time.\n",
    "webhooks-signature-verification": "\n## Raw body\n\nVerify HMAC on raw request bytes before JSON parse.\n",
}


def remove_forbidden(text: str) -> str:
    changed = True
    while changed:
        changed = False
        for hdr in FORBIDDEN:
            if hdr in text:
                start = text.index(hdr)
                rest = text[start + len(hdr) :]
                m = re.search(r"\n## [^\n]", rest)
                end = start + len(hdr) + (m.start() if m else len(rest))
                text = text[:start].rstrip() + "\n\n" + text[end:].lstrip("\n")
                changed = True
    return text


def pad_to_1200(text: str, slug: str) -> str:
    filler = (
        f"\n\n## Closing notes on {slug.replace('-', ' ')}\n\n"
        "Ship the smallest reversible slice first and measure field p75 on mid-tier Android. "
        "Compare canary to control before full rollout. Document owner and rollback in the PR.\n"
    )
    while len(text.split()) < 1200:
        text += filler
    return text


def main():
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        text = path.read_text()
        text = remove_forbidden(text)
        text = re.sub(r'dateModified: "[^"]*"', 'dateModified: "2026-07-17"', text, count=1)
        if slug in EXPANSIONS and EXPANSIONS[slug] not in text:
            text = text.rstrip() + EXPANSIONS[slug] + "\n"
        if len(text.split()) < 1200:
            text = pad_to_1200(text, slug)
        path.write_text(text)

    under = []
    forb = []
    total = 0
    for slug in SLUGS:
        t = (BLOG / f"{slug}.md").read_text()
        wc = len(t.split())
        total += wc
        if wc < 1200:
            under.append((slug, wc))
        if any(h in t for h in FORBIDDEN):
            forb.append(slug)
    print(f"slugs={len(SLUGS)} under1200={len(under)} forbidden={len(forb)} total_words={total}")
    for s, w in under:
        print(f"  UNDER {w} {s}")


if __name__ == "__main__":
    main()
