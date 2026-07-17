---
title: "Image Optimization in Next.js"
slug: "nextjs-image-optimization"
description: "Optimize images in Next.js with next/image: responsive sizing, format negotiation, remote patterns, placeholders, and Core Web Vitals impact."
datePublished: "2025-08-28"
dateModified: "2026-07-17"
tags:
keywords: "Next.js Image component, next/image optimization, responsive images Next.js, WebP AVIF Next.js, LCP optimization, image loader"
faq:
  - q: "Should I use next/image or a regular img tag?"
    a: "Use next/image for any content image where you control dimensions or aspect ratio. It provides automatic srcset generation, lazy loading, format negotiation (WebP/AVIF), and CLS prevention via reserved space. Use img only for user-uploaded images with unknown dimensions where you cannot set width and height."
  - q: "How do I optimize images hosted on an external CDN?"
    a: "Add the domain to images.remotePatterns in next.config.js. Next.js will proxy and transform external images through its optimization API. For high-traffic sites, use a custom loader pointing to your CDN's image transformation service."
  - q: "Why is my LCP image loading slowly?"
    a: "LCP images need priority={true} to skip lazy loading and preload early. Set explicit width and height to prevent layout shift. Serve appropriately sized images—an 800px display does not need a 4000px source file."
---
Your Lighthouse score shows LCP at 4.2 seconds. The hero image is a 3.2 MB PNG loaded at full resolution on a 390px mobile screen. The `next/image` component exists specifically to prevent this: it generates responsive srcsets, serves modern formats, reserves layout space, and lazy-loads below-the-fold content. Misconfiguring it—wrong `sizes`, missing `priority`, unlisted remote domains—leaves most of the benefit on the table.

## Basic usage

```tsx
import Image from "next/image";
import hero from "@/public/hero.jpg";

export function Hero() {
  return (
    <Image
      src={hero}
      alt="Team collaborating in a bright office"
      priority
      placeholder="blur"
      sizes="100vw"
      style={{ width: "100%", height: "auto" }}
    />
  );
}
```

Static imports (`import hero from ...`) provide automatic `width`, `height`, and `blurDataURL` at build time.

## The sizes attribute

`sizes` tells the browser which srcset entry to download. Getting it wrong wastes bandwidth or serves blurry images.

```tsx
{/* Image fills full viewport width on mobile, half on desktop */}
<Image
  src="/product.jpg"
  alt="Product photo"
  width={1200}
  height={800}
  sizes="(max-width: 768px) 100vw, 50vw"
/>

{/* Fixed 200px thumbnail in a grid */}
<Image
  src={thumbnail}
  alt="Thumbnail"
  width={200}
  height={200}
  sizes="200px"
/>
```

Rule of thumb: match `sizes` to your CSS layout, not the source image dimensions.

## Remote images

```javascript
// next.config.js
module.exports = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "cdn.example.com",
        pathname: "/images/**",
      },
    ],
  },
};
```

```tsx
<Image
  src="https://cdn.example.com/images/product-42.jpg"
  alt="Product 42"
  width={800}
  height={600}
  sizes="(max-width: 768px) 100vw, 800px"
/>
```

## Priority and LCP

Any image visible in the initial viewport that is the LCP candidate needs `priority`:

```tsx
<Image src={heroImage} alt="Hero" priority sizes="100vw" />
```

`priority` adds a `<link rel="preload">` and disables lazy loading. Use on one image per page—typically the hero. Adding `priority` to every image defeats the purpose.

## Placeholders

```tsx
{/* Static import — automatic blur */}
<Image src={photo} alt="..." placeholder="blur" />

{/* Remote image — manual blurDataURL */}
<Image
  src="https://cdn.example.com/photo.jpg"
  alt="..."
  width={800}
  height={600}
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,/9j/4AAQSkZJRg..."
/>
```

Generate `blurDataURL` at build time with `plaiceholder` or `sharp` for remote images.

## Fill layout for unknown aspect ratios

```tsx
<div style={{ position: "relative", width: "100%", aspectRatio: "16/9" }}>
  <Image
    src={src}
    alt="Gallery item"
    fill
    sizes="(max-width: 768px) 100vw, 33vw"
    style={{ objectFit: "cover" }}
  />
</div>
```

The parent must have `position: relative`. `fill` removes the need for explicit width/height on the image.

## Custom loader for external CDNs

When Next.js image optimization becomes a bottleneck at scale, delegate to your CDN:

```javascript
// next.config.js
module.exports = {
  images: {
    loader: "custom",
    loaderFile: "./lib/image-loader.ts",
  },
};
```

```typescript
// lib/image-loader.ts
export default function cloudinaryLoader({
  src, width, quality,
}: { src: string; width: number; quality?: number }) {
  return `https://res.cloudinary.com/demo/image/upload/w_${width},q_${quality || 75},f_auto/${src}`;
}
```

Cloudinary, Imgix, and Cloudflare Images all support URL-parameter transformations.

## Performance checklist

- Convert source images to WebP or AVIF before upload; Next.js re-encodes but smaller sources process faster.
- Cap `deviceSizes` in config if you never serve above 1920px displays.
- Use `quality={75}` (default) for photos; `quality={90}` for graphics with text.
- Monitor Image Optimization API usage on Vercel—high-traffic sites hit plan limits.

```javascript
images: {
  deviceSizes: [640, 750, 1080, 1200, 1920],
  imageSizes: [16, 32, 48, 64, 96, 128, 256],
  formats: ["image/avif", "image/webp"],
}
```

## App Router vs Pages Router image handling

App Router (Next.js 13+) changes image optimization defaults:

```tsx
// app/page.tsx — App Router
import Image from "next/image";
import heroImage from "@/public/hero.jpg";  // static import for blur placeholder

export default function Page() {
  return (
    <Image
      src={heroImage}
      alt="Hero"
      priority          // LCP image — preload, no lazy load
      placeholder="blur" // automatic with static import
      sizes="100vw"
    />
  );
}
```

Static imports enable automatic blur placeholder generation. `priority` prop prevents lazy loading on LCP candidates — critical for Core Web Vitals.

## Remote image configuration

Secure remote image loading with explicit allowlist:

```javascript
// next.config.js
module.exports = {
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "cdn.example.com", pathname: "/images/**" },
      { protocol: "https", hostname: "*.cloudfront.net" },
    ],
    // Never use domains: [] — deprecated and less secure
  },
};
```

Wildcard hostnames supported in `remotePatterns`. Never allow `hostname: "**"` in production — open proxy risk.

## LCP optimization checklist

Largest Contentful Paint is usually the hero image:

```tsx
// LCP optimization pattern
<Image
  src="/hero.webp"
  alt="Product hero"
  width={1920}
  height={1080}
  priority                    // 1. disable lazy load
  sizes="100vw"               // 2. correct sizes attribute
  quality={80}                // 3. balance quality vs size
  placeholder="blur"          // 4. blur while loading
  blurDataURL={blurDataUrl}   // 5. inline blur hash
/>
```

Preload hint added automatically with `priority`. Combine with `fetchPriority="high"` on the Image component for explicit browser hint.

## Failure modes

- **LCP image lazy loaded** — missing `priority` prop; LCP delayed by lazy load
- **Wrong sizes attribute** — browser downloads oversized image; wasted bandwidth
- **remotePatterns too permissive** — open proxy via image optimization API
- **Unoptimized source images** — 5MB PNG sources slow optimization pipeline
- **quality={100} on all images** — unnecessary file size; 75–80 sufficient for photos

## Production checklist

- LCP candidate marked with `priority` prop
- `sizes` attribute matches actual rendered width
- remotePatterns allowlist (no wildcard hostnames)
- Source images in WebP/AVIF before upload
- quality={75} default; quality={90} only for text-heavy graphics
- deviceSizes capped at 1920px unless 4K display support required

## Resources

- [next/image documentation](https://nextjs.org/docs/app/api-reference/components/image) — props and behavior
- [Next.js image configuration](https://nextjs.org/docs/app/api-reference/next-config-js/images) — remotePatterns, sizes, formats
- [Web.dev LCP guide](https://web.dev/articles/lcp) — Largest Contentful Paint optimization
- [Responsive images (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTML/Responsive_images) — srcset and sizes fundamentals
- [plaiceholder library](https://plaiceholder.co/) — generating blur placeholders


## Production validation (1)

Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs.

When operating **Next.js image optimization** (`nextjs-image-optimization`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Failure modes (2)

Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call.

When operating **Next.js image optimization** (`nextjs-image-optimization`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Observability (3)

Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency.

When operating **Next.js image optimization** (`nextjs-image-optimization`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Security review (4)

Least-privilege credentials, no PII in logs, fail-closed auth defaults. Secrets rotate without redeploy where possible. Never log raw tokens or authorization headers.

When operating **Next.js image optimization** (`nextjs-image-optimization`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Testing strategy (5)

Integration tests against real Postgres/Redis in CI with Testcontainers. Load test at 2× peak with production-like payloads. Chaos: inject dependency latency and verify degradation matches runbooks.

When operating **Next.js image optimization** (`nextjs-image-optimization`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.
