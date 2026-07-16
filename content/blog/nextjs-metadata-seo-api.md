---
title: "SEO with the Next.js Metadata API"
slug: "nextjs-metadata-seo-api"
description: "Implement SEO with Next.js Metadata API: static and dynamic metadata, Open Graph, JSON-LD, sitemaps, and canonical URLs in the App Router."
datePublished: "2025-08-31"
dateModified: "2025-08-31"
tags: ["Web", "Next.js", "SEO", "Frontend"]
keywords: "Next.js Metadata API, Next.js SEO, Open Graph Next.js, JSON-LD structured data, dynamic metadata Next.js, sitemap Next.js"
faq:
  - q: "How do I set page-specific title and description in the App Router?"
    a: "Export a metadata object or generateMetadata function from page.tsx or layout.tsx. Static pages use export const metadata = { title, description }. Dynamic pages use export async function generateMetadata({ params }) to fetch data and return metadata per route."
  - q: "Does Next.js Metadata API replace next/head from Pages Router?"
    a: "Yes. The Metadata API in App Router replaces next/head. It generates head tags at build time or request time with type safety. You cannot use next/head in App Router components."
  - q: "How do I add JSON-LD structured data?"
    a: "Return a script tag with type application/ld+json from your page component or layout. Alternatively, include it in the metadata.other field. Validate with Google's Rich Results Test before deploying."
---

Search Console shows your product pages indexed with the site-wide title "My App" and no description. In the Pages Router you fixed this with `next/head` per page. The App Router replaces that with the Metadata API—typed, composable, and merged from layouts down to pages. Misconfigure it and every route inherits the root layout defaults, which is why your blog posts share the homepage title tag.

## Static metadata

```typescript
// app/about/page.tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About Us",
  description: "We build developer tools for observability teams.",
  openGraph: {
    title: "About Us | Acme",
    description: "We build developer tools for observability teams.",
    url: "https://acme.com/about",
    siteName: "Acme",
    images: [{ url: "https://acme.com/og-about.png", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "About Us | Acme",
    images: ["https://acme.com/og-about.png"],
  },
};
```

## Dynamic metadata

```typescript
// app/blog/[slug]/page.tsx
import type { Metadata } from "next";
import { getPost } from "@/lib/posts";

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = await getPost(params.slug);
  if (!post) return { title: "Post not found" };

  return {
    title: post.title,
    description: post.excerpt,
    alternates: {
      canonical: `https://acme.com/blog/${post.slug}`,
    },
    openGraph: {
      title: post.title,
      description: post.excerpt,
      type: "article",
      publishedTime: post.publishedAt,
      authors: [post.author.name],
      images: [{ url: post.ogImage, width: 1200, height: 630 }],
    },
  };
}
```

`generateMetadata` runs at build time for static routes and at request time for dynamic routes.

## Title templates

```typescript
// app/layout.tsx
export const metadata: Metadata = {
  title: {
    default: "Acme — Developer Tools",
    template: "%s | Acme",
  },
  description: "Developer tools for modern teams.",
  metadataBase: new URL("https://acme.com"),
};
```

A page exporting `title: "Blog"` renders as "Blog | Acme". `metadataBase` resolves relative URLs in Open Graph images.

## JSON-LD structured data

```tsx
// app/blog/[slug]/page.tsx
export default async function PostPage({ params }: Props) {
  const post = await getPost(params.slug);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    datePublished: post.publishedAt,
    author: { "@type": "Person", name: post.author.name },
    image: post.ogImage,
    description: post.excerpt,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article>{/* content */}</article>
    </>
  );
}
```

Validate at [Google Rich Results Test](https://search.google.com/test/rich-results) before shipping.

## Sitemap generation

```typescript
// app/sitemap.ts
import type { MetadataRoute } from "next";
import { getAllPosts } from "@/lib/posts";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getAllPosts();
  const postEntries = posts.map((post) => ({
    url: `https://acme.com/blog/${post.slug}`,
    lastModified: post.updatedAt,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  return [
    { url: "https://acme.com", lastModified: new Date(), priority: 1 },
    { url: "https://acme.com/blog", lastModified: new Date(), priority: 0.9 },
    ...postEntries,
  ];
}
```

Next.js serves this at `/sitemap.xml` automatically.

## Robots.txt

```typescript
// app/robots.ts
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/admin/"],
    },
    sitemap: "https://acme.com/sitemap.xml",
  };
}
```

## Canonical URLs and duplicate content

```typescript
export const metadata: Metadata = {
  alternates: {
    canonical: "https://acme.com/products/widget",
    languages: {
      "en-US": "https://acme.com/en-US/products/widget",
      "de-DE": "https://acme.com/de-DE/products/widget",
    },
  },
};
```

Set canonical on paginated lists pointing to page 1 or a "view all" URL. Set it on pages with query parameters (`?sort=price`) pointing to the clean URL.

## Metadata merge behavior

Child page metadata overrides parent for the same key. Arrays (like `openGraph.images`) replace rather than merge. Define shared Open Graph defaults in the root layout; override per page only what differs.

## Dynamic metadata at scale

`generateMetadata` runs per request — cache expensive fetches:

```typescript
export async function generateMetadata({ params }): Promise<Metadata> {
  const product = await getProduct(params.slug); // Redis-cached
  return {
    title: product.name,
    description: product.summary,
    openGraph: {
      images: [{ url: product.ogImage, width: 1200, height: 630 }],
    },
  };
}
```

Set `export const revalidate = 3600` on product pages so metadata regenerates hourly without hitting DB on every crawl.

## Structured data with JSON-LD

Combine Metadata API with JSON-LD for rich results:

```typescript
// app/products/[slug]/page.tsx
export default function ProductPage({ product }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    offers: { "@type": "Offer", price: product.price, priceCurrency: "USD" },
  };
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {/* page content */}
    </>
  );
}
```

Validate with Google Rich Results Test before launch — invalid JSON-LD hurts less than no structured data, but errors in Search Console waste debugging time.

## Social preview debugging

OG images fail silently in production. Checklist:

- [ ] Absolute URLs (not `/og.png` — use full domain)
- [ ] 1200×630 minimum for LinkedIn/Facebook
- [ ] `twitter:card` set to `summary_large_image`
- [ ] Test with opengraph.xyz and Twitter Card Validator

Pair with [Next.js image optimization](https://blog.michaelsam94.com/nextjs-image-optimization/) for generating OG images dynamically via `ImageResponse`.

## Common production mistakes

Teams get metadata seo api wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of metadata seo api fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Next.js Metadata API docs](https://nextjs.org/docs/app/building-your-application/optimizing/metadata) — complete reference
- [generateMetadata function](https://nextjs.org/docs/app/api-reference/functions/generate-metadata) — dynamic metadata
- [Next.js sitemap file](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap) — sitemap.ts convention
- [Google Search Central structured data](https://developers.google.com/search/docs/appearance/structured-data) — JSON-LD guidelines
- [Open Graph protocol](https://ogp.me/) — OG tag specification
