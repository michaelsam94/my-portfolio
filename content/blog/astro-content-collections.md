---
title: "Content Collections in Astro"
slug: "astro-content-collections"
description: "Type-safe Markdown and MDX with Astro Content Collections: schemas, Zod validation, referencing, and patterns for blogs and docs sites."
datePublished: "2024-12-28"
dateModified: "2024-12-28"
tags: ["Web", "Astro", "Frontend"]
keywords: "Astro content collections, Zod schema Astro, getCollection, Astro MDX blog, content layer"
faq:
  - q: "What problem do Content Collections solve?"
    a: "Loose Markdown frontmatter becomes a typed, validated catalog. You define a Zod schema once; Astro fails the build when a post is missing `title` or has a bad date — instead of discovering it at runtime or in production."
  - q: "Can collections include non-Markdown data?"
    a: "Yes. JSON and YAML data collections work for authors, changelog entries, or product catalogs. Mix Markdown posts with a JSON authors collection and reference between them with `reference()` in the schema."
  - q: "How do I query posts in pages?"
    a: "Use `getCollection('blog')` then filter/sort in the page or a utility. For a single entry, `getEntry('blog', slug)`. In Astro 4+/5 content layer APIs, prefer the current `getCollection` docs for your version — APIs evolved from the legacy content module."
---

A blog with thirty Markdown files is fine until someone typos `datePublished` and your homepage sorts NaN to the top. Astro Content Collections turn that pile of files into a schema-checked dataset — the same instinct as typed APIs, applied to content. Once you've been burned by a silent frontmatter typo in production, build-time validation stops feeling optional.

## Define a collection

Astro 5's content layer uses a config module and loaders:

```typescript
// src/content.config.ts
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string().max(200),
    datePublished: z.coerce.date(),
    dateModified: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
```

Bad frontmatter fails `astro build`. That's the feature. Use `z.coerce.date()` so ISO strings from YAML become `Date` objects. Add `.optional()` carefully — optional fields are how drafts ship without descriptions; required fields are how you keep the RSS feed honest.

## Query and render

```astro
---
import { getCollection, render } from "astro:content";

const posts = (await getCollection("blog"))
  .filter((p) => !p.data.draft)
  .sort((a, b) => b.data.datePublished.valueOf() - a.data.datePublished.valueOf());
---

<ul>
  {posts.map((post) => (
    <li>
      <a href={`/blog/${post.id}/`}>{post.data.title}</a>
    </li>
  ))}
</ul>
```

For the post page:

```astro
---
import { getEntry, render } from "astro:content";
const entry = await getEntry("blog", Astro.params.slug!);
if (!entry) return Astro.redirect("/404");
const { Content, headings } = await render(entry);
---
<article>
  <h1>{entry.data.title}</h1>
  <Content />
</article>
```

`headings` is enough to build a table of contents without a second Markdown pass.

## References between collections

Authors, categories, and changelog entries fit data collections:

```typescript
import { defineCollection, reference, z } from "astro:content";

const authors = defineCollection({
  loader: glob({ pattern: "**/*.json", base: "./src/content/authors" }),
  schema: z.object({
    name: z.string(),
    twitter: z.string().optional(),
  }),
});

const blog = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    author: reference("authors"),
  }),
});
```

Resolve with `getEntry(post.data.author)` when rendering — no stringly-typed author names drifting from a bio file. If the author id is wrong, the build fails.

## Drafts, RSS, and sitemaps

Filter `draft` in every public surface: index, tag pages, RSS, sitemap. Generating the feed from `getCollection` with the same filter as the homepage means they can't diverge. A common helper:

```typescript
export async function publishedPosts() {
  return (await getCollection("blog"))
    .filter((p) => import.meta.env.DEV || !p.data.draft)
    .sort((a, b) => b.data.datePublished.valueOf() - a.data.datePublished.valueOf());
}
```

In dev, show drafts; in prod builds, hide them.

## MDX and components

Use MDX when a post needs interactive diagrams or shared callout components. Keep the **same Zod schema** for `.md` and `.mdx` so the catalog stays uniform. Don't invent parallel frontmatter conventions per format.

## Migration tips

- Keep slugs stable when moving files into collections — URLs are the product
- Start with a strict schema, then relax only with reason
- Prefer one `blog` collection over twenty micro-collections unless domains truly differ
- CI should run `astro check` / build on content PRs so authors get schema errors before merge

Content Collections are how Astro sites stay honest as the archive grows — validation at build time beats hope at deploy time.

## Reference relationships between collections

Link collections with Zod references for type-safe cross-collection queries:

```typescript
// content/config.ts
const authors = defineCollection({
  type: "data",
  schema: z.object({
    name: z.string(),
    avatar: z.string().optional(),
    bio: z.string(),
  }),
});

const blog = defineCollection({
  type: "content",
  schema: z.object({
    title: z.string(),
    author: reference("authors"),  // typed reference
    datePublished: z.date(),
    tags: z.array(z.string()).default([]),
  }),
});

// Usage in template
const post = await getEntry("blog", "my-post");
const author = await getEntry(post.data.author);
// author.data.name is typed string
```

References validated at build time — broken author links fail CI, not production.

## Dynamic routes with getStaticPaths

Generate pages from collection entries:

```typescript
// src/pages/blog/[...slug].astro
export async function getStaticPaths() {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return posts.map((post) => ({
    params: { slug: post.slug },
    props: { post },
  }));
}

const { post } = Astro.props;
const { Content } = await post.render();
```

Adding a new `.md` file automatically creates a route — no manual route registration. Removing a file removes the route.

## Image optimization in collections

Use Astro's built-in image optimization with collection data:

```typescript
import { Image } from "astro:assets";

// In schema
coverImage: image(),  // Astro image schema helper

// In template
import cover from "../../assets/cover.jpg";
<Image src={post.data.coverImage} alt={post.title} width={800} height={400} />
```

Images referenced in frontmatter are validated at build time — missing image file fails CI.

## Failure modes

- **Loose schema** — invalid frontmatter reaches production; strict schema from day one
- **Draft posts in RSS/sitemap** — forgotten filter; use shared `publishedPosts()` helper
- **Slug change breaks URLs** — set explicit slug in frontmatter; never rely on filename alone
- **No CI build on content PRs** — schema errors discovered at deploy time
- **Multiple collection schemas for same content type** — inconsistency; one schema per collection

## Production checklist

- Zod schema defined for every collection before first content added
- Shared `publishedPosts()` helper filters drafts consistently
- Explicit slug in frontmatter (stable URLs)
- `astro check` and build in CI on content PRs
- Reference relationships typed with `reference()` helper
- RSS, sitemap, and index all use same published filter

## Resources

- [Astro — Content Collections](https://docs.astro.build/en/guides/content-collections/)
- [Zod documentation](https://zod.dev/)
- [Astro — Content layer API](https://docs.astro.build/en/reference/content-loader-reference/)
- [Astro — RSS feeds](https://docs.astro.build/en/guides/rss/)
---
