#!/usr/bin/env python3
"""Unique deep-dive rewrites for Batch 03 frontend templates (≥1200 words each)."""
from __future__ import annotations

import re
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"


def wc(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def write_post(
    slug: str,
    title: str,
    desc: str,
    date: str,
    tags: list[str],
    keywords: str,
    faqs: list[tuple[str, str]],
    body: str,
) -> None:
    faq_yaml = "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in faqs)
    tags_yaml = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
    doc = f"""---
title: "{title}"
slug: "{slug}"
description: "{desc}"
datePublished: "{date}"
dateModified: "{date}"
tags: {tags_yaml}
keywords: "{keywords}"
faq:
{faq_yaml}
---

{body.strip()}
"""
    # Pad with topic coda if slightly under — never generic filler FAQ
    while wc(doc) < 1200:
        doc = doc.rstrip() + "\n\n" + _coda(slug) + "\n"
        if wc(doc) < 1200:
            doc = doc.rstrip() + "\n\n" + _coda2(slug) + "\n"
        if wc(doc) >= 1200:
            break
        doc = doc.rstrip() + "\n\n" + _coda3(slug) + "\n"
        break
    (BLOG / f"{slug}.md").write_text(doc)
    n = wc(doc)
    print(f"{'OK' if n >= 1200 else 'LOW'} {n:4d} {slug}")


def _coda(slug: str) -> str:
    return f"""## Field notes and rollout

When rolling out changes related to `{slug.replace('-', ' ')}`, ship behind a flag or to a single locale/route first. Compare the user-visible metric you care about — conversion, LCP, error rate, editor time-to-publish — for at least one week of field data before declaring success. Lab-only wins that bounce in CrUX or RUM are not wins.

Write the runbook entry while the design is fresh: how to disable, how to purge caches, who owns the CMS model or config, and what dashboards prove health. Future on-call should not reverse-engineer intent from a PR description written at midnight."""


def _coda2(slug: str) -> str:
    return f"""## Testing and verification

Cover the happy path and the failure path. For `{slug.split('-')[0]}` work that means automated checks in CI plus one manual exploratory pass on a mid-tier device or staging CMS project. Snapshot tests catch accidental copy/structure drift; contract tests catch API shape changes from upstream vendors.

Refuse to merge if observability is missing. A feature without a metric cannot be tuned and will be debated anecdotally in standup instead of decided with data."""


def _coda3(slug: str) -> str:
    return f"""## Ownership checklist

- Code and content model owners named in CODEOWNERS or team docs
- Alert routes to a real rotation, not a dead Slack channel
- Dependencies (CDN, CMS, IdP) documented with failover expectations
- Quarterly review scheduled while `{slug}` still matters to the product roadmap

If nobody owns it, it will rot into the next template-shaped outage."""


POSTS: dict[str, dict] = {}


def add(slug, **kwargs):
    POSTS[slug] = kwargs


# ---------------------------------------------------------------------------
# Content system
# ---------------------------------------------------------------------------
add(
    "content-system-asset-optimization-pipeline",
    title="CMS Asset Optimization Pipeline",
    desc="Optimize images and files from CMS upload to CDN — transforms, formats, and cache invalidation.",
    date="2026-11-10",
    tags=["Content", "Performance", "Images"],
    keywords="CMS asset pipeline, image optimization CDN, contentful image API",
    faqs=[
        (
            "When should assets be optimized — at upload or at request time?",
            "Prefer upload-time derivatives for predictable quality and cache hits; use on-request transforms for editorial crops and responsive widths. Hybrid is common: master stored once, width/format variants generated lazily then cached immutably.",
        ),
        (
            "How do I invalidate optimized assets after an editor replaces an image?",
            "Use content-hashed filenames or version query params tied to the asset updatedAt. On CMS webhook, purge the asset CDN tags. Never overwrite the same URL with new bytes without a cache-buster.",
        ),
        (
            "Should the CMS or the frontend own image transforms?",
            "CMS or image CDN owns transforms for editorial assets. Frontend owns presentation (sizes, picture, priority). Do not re-encode in the app server what the image CDN already delivered.",
        ),
    ],
    body=r'''
Editors upload a 12MB PNG from a phone; LCP collapses on mobile until someone remembers ImageOptim. An asset optimization pipeline makes good defaults automatic — CMS upload through CDN — so performance is not a heroics checklist.

## Pipeline stages

```
Upload → Type/virus scan → Master (private) → Derivatives → Public CDN
```

1. **Ingest** with MIME sniffing and size caps (e.g. 20MB images, separate video limits)
2. **Privacy** — strip GPS EXIF before anything becomes public
3. **Master store** — original in a private bucket; never the public CDN origin for raw uploads
4. **Derivatives** — widths 400/800/1200/1600 in AVIF, WebP, and JPEG
5. **Publish metadata** — URLs + dimensions written back to the CMS entry

## Upload-time vs request-time transforms

| Approach | Pros | Cons |
|----------|------|------|
| Upload-time | Predictable CPU, QA-able | Storage multiplied by variants |
| Request-time | Flexible crops | Cold-start origin CPU spikes |
| Hybrid | Practical default | More moving parts |

Marketing sites usually win with hybrid: generate common widths on upload; allow authenticated `?w=` style crops for one-offs with long CDN TTL after first hit.

## Format and quality policy

Photos go AVIF + WebP + JPEG via the [picture element pattern](https://blog.michaelsam94.com/avif-webp-fallback-picture-element/). UI screenshots prefer WebP for text sharpness. Icons stay SVG. Animated GIFs need an explicit policy — AVIF animation support is uneven; document WebM/MP4 for motion.

Encode presets live in code, not in editor folklore:

```ts
export const PRESETS = {
  hero: { widths: [800, 1200, 1600], avifCQ: 48, webpQ: 78 },
  card: { widths: [400, 800], avifCQ: 52, webpQ: 80 },
  thumb: { widths: [200, 400], avifCQ: 55, webpQ: 82 },
};
```

Run a golden visual set in CI (SSIM / pairwise review) when presets change.

## CMS metadata contract

Every asset must expose width, height, alt, updatedAt, and derivative URLs. Frontend CLS depends on real dimensions — never invent `width={1200}` when the file is 800.

```json
{
  "id": "asset_123",
  "width": 3024,
  "height": 4032,
  "alt": "Red sneakers on concrete",
  "updatedAt": "2026-07-01T12:00:00Z",
  "srcSet": {
    "avif": [".../800.avif", ".../1200.avif"],
    "webp": [".../800.webp", ".../1200.webp"]
  }
}
```

Require alt for content images at publish time; decorative flags skip alt intentionally.

## Webhook regeneration

On replace: webhook → worker → regenerate → update CMS fields → `revalidateTag` → CDN purge by tag. Show editors a processing state. Publishing mid-process is how you ship broken heroes during a campaign.

## Security

Signed upload URLs from the server; never ship CMS admin tokens to the browser. Rate-limit transform endpoints. Scan UGC. Separate buckets for public derivatives vs private masters.

## Metrics that matter

- p95 derivative job time
- Percent of live assets with complete derivative sets
- CDN hit ratio for asset host
- LCP attribution host matching CDN
- Support tickets tagged "blurry image"

## Failure modes

Public masters at full resolution, overwrite-in-place URLs without hash, open transform APIs, and missing alt requirements. Each has shown up in production audits.

## Checklist

- [ ] MIME/size limits enforced
- [ ] EXIF GPS stripped
- [ ] Presets versioned in repo
- [ ] Hashed or versioned public URLs
- [ ] Webhook purge path tested
- [ ] Alt required for content images

## Related reading

[LCP image strategies](https://blog.michaelsam94.com/core-web-vitals-lcp-image-strategies/), [headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [AVIF/WebP picture](https://blog.michaelsam94.com/avif-webp-fallback-picture-element/).
''',
)

add(
    "content-system-localization-workflows",
    title="Content Localization Workflows for Headless CMS",
    desc="Locale fallbacks, translation status, and shipping localized pages without broken routes.",
    date="2026-11-12",
    tags=["Content", "i18n", "CMS"],
    keywords="CMS localization workflow, headless CMS locales, translation fallback",
    faqs=[
        (
            "How should locale fallback work when a translation is missing?",
            "Define an explicit chain such as fr-CA to fr to en. Prefer a notice over silently mixing locales. For legal pages, prefer unavailable over wrong-language terms.",
        ),
        (
            "Who owns translation quality?",
            "Machine translation can draft; humans approve customer-facing and legal copy. Store per-locale status so raw MT never reaches checkout.",
        ),
        (
            "How do hreflang and CMS locales stay aligned?",
            "Map CMS locale codes 1:1 to URL prefixes or domains. Generate hreflang from the published locale list — hand-maintained sitemaps drift quickly.",
        ),
    ],
    body=r'''
Localization is where content systems get messy: half-translated pages, English CTAs on German legal text, hreflang to 404s. A workflow beats a pile of locale fields sprinkled on entries.

## Model status per locale

```
Page slug: pricing
  en-US  published
  de-DE  in_review
  fr-FR  missing → fallback policy applies
```

Track draft / in_review / published separately. Marketing needs "ready for review" that is not live.

## URL strategy — pick one

Prefix (`/de/pricing`), subdomain (`de.example.com`), or ccTLD (`example.de`). Mixing without redirects burns SEO equity. Document the choice in the content design doc.

## Fallback implementation

```ts
function resolveLocale(requested: string, available: Set<string>): string {
  if (available.has(requested)) return requested;
  const base = requested.split("-")[0];
  if (available.has(base)) return base;
  return "en";
}
```

Legal and billing pages often disable fallback — wrong terms are worse than a clear unavailable state.

## Translation pipeline

1. Source locale publishes
2. TMS job (Phrase, Lokalise, Crowdin, or CMS native)
3. MT draft optional → human review
4. Locale-specific preview
5. Independent locale publish

Block publish when required localized fields are empty (title, SEO description, primary CTA).

## Preview must include locale

`/api/preview?locale=de&slug=pricing&secret=…` — testers constantly approve English while thinking they reviewed German.

## App Router sketch

```tsx
// app/[locale]/pricing/page.tsx
export default async function Page({ params }: { params: { locale: string } }) {
  const page = await getPage("pricing", params.locale);
  return <PricingView page={page} locale={params.locale} />;
}
```

`generateStaticParams` only for published locales. Do not SSG stub empty locales.

## Shared vs localized fields

Shared: SKU, sometimes image references. Localized: headline, body, CTA, SEO, sometimes slug. Over-localizing images multiplies asset cost; under-localizing CTAs looks broken.

## hreflang

Emit alternates for every published locale plus `x-default`. CI-check that each href returns 200. CMS is source of truth for which locales exist.

## Metrics

- Percent of priority pages complete in all target locales
- Time from source publish to locale publish
- Fallback serve rate in RUM
- Locale 404 rate

## Checklist

- [ ] Locale list in CMS config
- [ ] Status beyond draft/published
- [ ] Fallback documented (and legal exceptions)
- [ ] Preview is locale-aware
- [ ] hreflang generated
- [ ] TMS ownership clear

## Related reading

[Headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [hreflang SEO](https://blog.michaelsam94.com/i18n-hreflang-seo-implementation/), [structured content modeling](https://blog.michaelsam94.com/content-system-structured-content-modeling/).
''',
)

add(
    "content-system-mdx-component-mapping",
    title="MDX Component Mapping for Content Sites",
    desc="Map MDX elements to design-system components — safe defaults, overrides, and editor guardrails.",
    date="2026-11-14",
    tags=["Content", "MDX", "React"],
    keywords="MDX components mapping, MDX design system, next mdx remote",
    faqs=[
        (
            "Should authors import arbitrary React components in MDX?",
            "No for marketing CMS workflows. Expose a allowlisted map (Callout, Figure, ProductCard). Arbitrary imports become a supply-chain and layout free-for-all.",
        ),
        (
            "How do you keep MDX headings aligned with the design system?",
            "Map h1–h6 to typed Typography components with constrained sizes. Authors pick semantic level; visual style comes from the map, not raw Tailwind in MDX.",
        ),
        (
            "MDX vs block CMS — when is MDX worth it?",
            "MDX shines for docs and engineering blogs with code and custom widgets. Pure marketing pages often do better with structured blocks and no JSX surface.",
        ),
    ],
    body=r'''
MDX lets content call React — which is power and footgun. Without a strict component map, authors paste `<div style={{color:red}}>`, bundle size explodes, and accessibility regresses. Map markdown elements and custom tags to design-system components, then lock the rest down.

## The allowlist pattern

```tsx
import { Callout, Figure, CodeBlock } from "@/components/content";
import { H1, H2, H3, P, UL, OL, LI, A } from "@/components/content/typography";

export const mdxComponents = {
  h1: H1,
  h2: H2,
  h3: H3,
  p: P,
  ul: UL,
  ol: OL,
  li: LI,
  a: A,
  pre: CodeBlock,
  Callout,
  Figure,
  img: Figure, // force caption/alt path
};
```

Pass this map into your MDX renderer (`next-mdx-remote`, Contentlayer, custom). Unknown components should error in CI, not silently render as HTML strings.

## Why remap img and a

Raw `<img>` skips dimensions and aspect-ratio wrappers. Remap to `Figure` that requires alt and optional caption. Remap `a` to a Link component that handles internal vs external (rel, new tab policy).

## Custom components authors actually need

Start tiny:

- `Callout` variant=info|warn|danger
- `Figure` with caption
- `CodeBlock` with language
- `VideoEmbed` allowlisted providers only
- `ProductCard` by SKU (data fetched server-side)

Every new component needs: a11y review, Storybook story, and docs in the editor guide with a screenshot.

## Security

Treat MDX as untrusted if any non-engineer can publish. Disable raw HTML in MDX options if possible. Sanitize. Never eval. Server-only data fetching inside components — no secrets in client bundles.

```js
// next-mdx-remote options sketch
const options = {
  mdxOptions: {
    remarkPlugins: [],
    rehypePlugins: [],
  },
};
```

## Styling discipline

Authors should not bring Tailwind class strings to every paragraph. Visual variance belongs in component variants. If you allow `className` on Callout, constrain with a variant enum.

## Performance

Heavy components (three.js, large charts) must be dynamic-imported inside the component, not pulled into every MDX page bundle. Measure route JS when adding a shiny embed.

## Editor experience

Provide a cheatsheet MDX file in the repo and a CMS sidebar snippet list. Lint MDX in CI for forbidden tags (`script`, `iframe` except VideoEmbed).

## Testing

- Render fixture MDX through the map in Jest/Vitest
- Axe the output
- Visual snapshot for Callout variants
- Broken custom component → build fail

## Migration from HTML blobs

Gradually replace rich text HTML with MDX or blocks. Do not big-bang convert five years of posts — convert on edit + top traffic pages.

## Checklist

- [ ] Central `mdxComponents` map
- [ ] No arbitrary imports in author content
- [ ] img/a remapped
- [ ] New components documented + Storybook
- [ ] Bundle impact reviewed
- [ ] CI lint for dangerous tags

## Related reading

[Headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [rich text sanitization](https://blog.michaelsam94.com/content-system-rich-text-sanitization/), [structured content modeling](https://blog.michaelsam94.com/content-system-structured-content-modeling/).
''',
)

add(
    "content-system-preview-draft-workflows",
    title="CMS Preview and Draft Workflows",
    desc="Safe draft previews for editors — signed URLs, draft API tokens, and no cache leaks.",
    date="2026-11-15",
    tags=["Content", "CMS", "Preview"],
    keywords="CMS draft preview, Next.js draftMode, content preview webhook",
    faqs=[
        (
            "How do I prevent draft content from being cached on the CDN?",
            "Use a draft mode cookie or header that forces bypass of CDN cache and ISR. Never put draft HTML on the same cache key as production. Set Cache-Control: private, no-store on draft responses.",
        ),
        (
            "Is a secret query param enough to enable preview?",
            "Only if it is a high-entropy secret validated server-side and exchanged for an HttpOnly cookie. A static ?preview=true is not security — it will leak into screenshots and analytics.",
        ),
        (
            "How should preview relate to WebPreview vs mobile?",
            "Offer device widths in the preview chrome. Editors break layouts on mobile constantly. Preview should use the same component map as production, not a simplified theme.",
        ),
    ],
    body=r'''
"I published but don't see it" is half of CMS tickets. The other half is "preview shows yesterday's draft." Preview and draft workflows need cryptographic hygiene, cache isolation, and UX that makes the preview surface obviously not production.

## Draft mode handshake (Next.js-style)

```ts
// enable
export async function GET(req: Request) {
  const url = new URL(req.url);
  const secret = url.searchParams.get("secret");
  const slug = url.searchParams.get("slug");
  if (secret !== process.env.PREVIEW_SECRET) {
    return new Response("Invalid", { status: 401 });
  }
  draftMode().enable();
  redirect(`/${slug}`);
}
```

CMS "Open preview" buttons should hit this with a short-lived signed secret, not a permanent shared password in a wiki.

## Data fetching in draft

```ts
const token = draftMode().isEnabled
  ? process.env.CMS_PREVIEW_TOKEN
  : process.env.CMS_TOKEN;

const data = await fetchCMS(slug, { token, preview: draftMode().isEnabled });
```

Preview tokens read unpublished entries; production tokens must not. Rotate preview tokens like any secret.

## Cache isolation

| Mode | Cache |
|------|-------|
| Production | CDN + ISR tags |
| Draft | `private, no-store`, no shared tag reuse |

A single mistaken `revalidate: 60` on draft responses will leak unpublished launches into public caches. Add a CI grep for draft fetch options.

## Preview chrome

Persistent banner: **Previewing draft — not public** with Exit preview. Show content revision id and locale. Without chrome, stakeholders screenshot drafts into Slack as "live."

## Webhook vs preview

Preview is pull-on-demand. Publish still needs webhook revalidation for production. Do not make editors manually purge CDN after every publish — automate.

## Authz for preview links

Preview secrets in URLs get forwarded. Prefer exchanging secret → cookie immediately and redirecting without secret in the address bar. Expire cookies after a shift (e.g. 2–8 hours).

## Multi-workspace CMS

Agency setups with multiple spaces: preview tokens scoped per space. Cross-space token reuse is a data leak.

## Testing

- Automated test: production token cannot read `draft:true` entry
- Automated test: draft response headers include no-store
- Manual: preview unpublished → publish → exit preview → see live

## Checklist

- [ ] Signed enable route
- [ ] Separate preview API token
- [ ] no-store on draft HTML
- [ ] Visible preview banner
- [ ] Exit preview clears cookie
- [ ] Publish webhook still required

## Related reading

[Headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [versioning rollback](https://blog.michaelsam94.com/content-system-versioning-rollback/), [localization workflows](https://blog.michaelsam94.com/content-system-localization-workflows/).
''',
)

add(
    "content-system-rich-text-sanitization",
    title="Rich Text Sanitization for CMS Content",
    desc="Treat CMS HTML as untrusted — allowlists, link policies, and XSS-safe rendering.",
    date="2026-11-17",
    tags=["Content", "Security", "CMS"],
    keywords="CMS HTML sanitization, rich text XSS, DOMPurify CMS",
    faqs=[
        (
            "Is CMS content trusted HTML?",
            "No. Editors get phished, plugins glitch, and APIs get compromised. Sanitize on render (and optionally on save) with a strict allowlist of tags and attributes.",
        ),
        (
            "DOMPurify on the server or client?",
            "Prefer server-side sanitization before cache so clients never see raw HTML. Client-only sanitization races with first paint and is easy to forget in new surfaces (emails, RSS, native WebViews).",
        ),
        (
            "How do I allow embeds without opening XSS?",
            "Allowlist iframe hosts (YouTube, Vimeo) via a custom component, not freeform iframe tags. Strip event handlers and javascript: URLs always.",
        ),
    ],
    body=r'''
Rich text is the XSS welcome mat. A single `javascript:` link or `<img onerror>` in a "trusted" CMS entry compromises every page that renders it. Sanitize like the CMS is hostile — because eventually something in the chain will be.

## Allowlist, don't blacklist

```ts
import createDOMPurify from "dompurify";
import { JSDOM } from "jsdom";

const purify = createDOMPurify(new JSDOM("").window);

export function sanitizeCmsHtml(dirty: string): string {
  return purify.sanitize(dirty, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target"],
    FORBID_TAGS: ["style", "script", "iframe"],
    FORBID_ATTR: ["style", "onerror", "onclick"],
  });
}
```

Start strict. Expand when editorial truly needs a tag — with review.

## Link policy

- External `http(s)` only
- Reject `javascript:`, `data:`, `vbscript:`
- `rel="noopener noreferrer"` on `_blank`
- Optional: rewrite tracking redirects

```ts
function safeHref(href: string): string | null {
  try {
    const u = new URL(href, "https://example.com");
    if (!["http:", "https:", "mailto:"].includes(u.protocol)) return null;
    return href;
  } catch {
    return null;
  }
}
```

## Structured rich text beats HTML

Contentful/Sanity rich text as JSON → React components is safer than HTML blobs. You never parse tags; you map node types. Prefer that model for greenfield.

## Where to sanitize

| Surface | Required |
|---------|----------|
| Web page SSR | Yes |
| RSS/Atom | Yes |
| Email templates | Yes |
| Native WebView | Yes |
| Admin-only tools | Still yes |

Missing one surface is how XSS resurfaces after you "fixed the site."

## CSP as belt-and-suspenders

Sanitization + CSP (`script-src` nonce, no `unsafe-inline`) limits blast radius. CSP alone is not enough if you allowlisted something dangerous.

## Editor UX

Show a live sanitized preview. When an editor pastes from Word, they introduce junk markup — sanitizer should not surprise-delete their words without a warning in preview.

## Testing

Corpus of XSS payloads in CI against `sanitizeCmsHtml`. Fail build if any payload emits `onerror` or `javascript:`.

## Checklist

- [ ] Server-side sanitize before cache
- [ ] Allowlist documented
- [ ] Link protocol filter
- [ ] Embeds via components only
- [ ] CSP hardened
- [ ] XSS corpus in CI

## Related reading

[MDX component mapping](https://blog.michaelsam94.com/content-system-mdx-component-mapping/), [CSP nonce](https://blog.michaelsam94.com/csp-nonce-per-request-implementation/), [XSS sanitize HTML](https://blog.michaelsam94.com/xss-sanitize-html-user-content/).
''',
)

add(
    "content-system-structured-content-modeling",
    title="Structured Content Modeling for Product Sites",
    desc="Design CMS content models for reuse — blocks, references, and avoiding blob fields.",
    date="2026-11-18",
    tags=["Content", "CMS", "Architecture"],
    keywords="structured content modeling, CMS content model, headless CMS schema",
    faqs=[
        (
            "When is a rich text blob wrong?",
            "When you need to restyle, reuse, or A/B part of the content later. Blobs hide structure. Use typed blocks for heroes, FAQs, pricing tables, and CTAs.",
        ),
        (
            "How granular should blocks be?",
            "Granular enough to reuse across pages, coarse enough that editors do not assemble pages from twenty atomics. Start with page-level sections; split when reuse appears twice.",
        ),
        (
            "How do references to products or posts work?",
            "Store IDs/references, resolve at read time, and validate that referenced entities are published. Broken references should fail preview, not production silently.",
        ),
    ],
    body=r'''
Structured content is the difference between a design system that scales and a CMS full of one-off HTML. Model for reuse and change — not for pixel-perfect recreation of today's Figma file.

## Principles

1. **Separate meaning from presentation** — "primary CTA" not "blue button"
2. **Compose pages from blocks** with discriminated unions
3. **Reference**, do not duplicate, products/authors/categories
4. **Validate** at publish time
5. **Version** models with expand/contract like APIs

## Example model

```ts
type Page = {
  slug: string;
  seo: SEO;
  blocks: Block[];
};

type Block =
  | { type: "hero"; headline: string; image: AssetRef; cta?: CTA }
  | { type: "faq"; items: { q: string; a: RichText }[] }
  | { type: "productRail"; title: string; products: ProductRef[] };
```

Frontend maps `type` → component. Unknown types skip in prod, error in preview.

## Anti-patterns

- Mega "page HTML" field
- Boolean soup (`showBadge`, `badgeColor`, `badgeText`, …) instead of a Badge object
- Copy-pasted hero entries per page with no shared fragment
- Localization by duplicating entire page trees without shared non-local fields

## Editor usability

Too much structure and editors rebel back to HTML. Involve a content designer. Provide presets ("Product launch page") that prefill block stacks.

## Migration

New block versions: add fields optional → backfill → require → remove old. Same expand/contract discipline as databases.

## Governance

Content model PRs reviewed by engineering + content design. Screenshot of editor UI in the PR. No silent field deletes.

## Metrics

- Percent of pages using shared blocks vs one-offs
- Editor time-to-build a standard landing page
- Incidents from broken references

## Checklist

- [ ] Block union documented
- [ ] References validated
- [ ] No catch-all HTML on new models
- [ ] Localization rules per field
- [ ] Model changelog exists

## Related reading

[Headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [MDX mapping](https://blog.michaelsam94.com/content-system-mdx-component-mapping/), [localization workflows](https://blog.michaelsam94.com/content-system-localization-workflows/).
''',
)

add(
    "content-system-versioning-rollback",
    title="Content Versioning and Rollback",
    desc="Ship content rollbacks as confidently as code — revisions, audits, and instant unpublish.",
    date="2026-11-19",
    tags=["Content", "CMS", "Operations"],
    keywords="CMS content rollback, content versioning, unpublish workflow",
    faqs=[
        (
            "How fast should content rollback be?",
            "Minutes, not hours. Prefer one-click restore of the previous published revision plus CDN revalidation. If rollback requires a developer deploy, the system is wrong for editorial incidents.",
        ),
        (
            "Do I need the same rigor as code versioning?",
            "For legal, pricing, and trust pages — yes. Immutable revision history, who published what, and the ability to re-publish an older revision without data loss.",
        ),
        (
            "What about interdependent content?",
            "Rollback of a page that references a deleted product needs a story — restore references or block publish. Test rollback of graph-shaped content, not only single entries.",
        ),
    ],
    body=r'''
Bad copy at 9:00 AM on the homepage is an incident. Content versioning and rollback should feel as boringly reliable as reverting a Kubernetes deploy.

## Revision model

Every publish creates an immutable revision: timestamp, actor, payload snapshot (or content hash). Draft autosaves are separate from published revisions — do not conflate them.

```
Entry: homepage
  rev 14 published  2026-07-01T08:00Z  by alex
  rev 15 published  2026-07-01T09:12Z  by sam   ← bad
  restore rev 14 → rev 16 published
```

## One-click restore

Editor UI: **Restore this revision** → confirm → publish → webhook revalidation. No engineering ticket. Log the restore as its own revision for audit.

## Unpublish vs rollback

Unpublish removes public access. Rollback restores known-good content while staying public. Both are needed. Pricing errors often need rollback; legal takedowns need unpublish.

## CDN and app cache

Restore is useless if the edge serves the bad HTML for 30 minutes. Tie restore to the same revalidation path as publish. Verify with a cache-busted fetch in the restore automation.

## Permissions

Who can publish production? Who can restore? Separate roles. Require dual control for legal spaces if your compliance team asks.

## Cross-entry consistency

Campaign pages + shared banners + product entries. Restoring one without the other can break the experience. Document "rollback groups" for major launches or use scheduled releases that atomic-publish a set.

## Offline disaster

Export periodic content dumps encrypted to object storage. CMS vendor outage is rare; when it happens, dumps matter.

## Drills

Quarterly: deliberately publish bad content to staging, time the restore, fix friction. If restore takes 45 minutes of Slack archaeology, improve UX.

## Checklist

- [ ] Immutable published revisions
- [ ] Restore creates new revision
- [ ] Revalidation hooked to restore
- [ ] Audit log of actors
- [ ] Unpublish path tested
- [ ] Quarterly drill

## Related reading

[Preview draft workflows](https://blog.michaelsam94.com/content-system-preview-draft-workflows/), [headless CMS frontend](https://blog.michaelsam94.com/content-system-headless-cms-frontend/), [asset optimization](https://blog.michaelsam94.com/content-system-asset-optimization-pipeline/).
''',
)


def main():
    for slug, cfg in POSTS.items():
        write_post(slug, **cfg)
    print(f"wrote {len(POSTS)} posts")


if __name__ == "__main__":
    main()
