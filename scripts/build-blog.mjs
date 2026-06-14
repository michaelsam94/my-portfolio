/**
 * Static blog generator — runs AFTER `vite build`.
 *
 * Reads Markdown posts from `content/blog/*.md`, renders each to a fully static,
 * schema-rich HTML page at `dist/blog/<slug>/index.html`, builds the `/blog` hub
 * page, copies the standalone stylesheet, and regenerates `dist/sitemap.xml`.
 *
 * Why static (not a client route): the site is a client-rendered Vite SPA, so a
 * React-only route would be an empty shell to crawlers. These pages ship as real
 * HTML so Google indexes the full content. Each post links back to the home
 * Person entity (`#person`) so blog authority supports the main entity.
 */
import { readdir, readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import matter from "gray-matter";
import { marked } from "marked";
import { projects, workSlug } from "../src/data/portfolio.ts";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CONTENT_DIR = path.join(ROOT, "content/blog");
const DIST = path.join(ROOT, "dist");
const BLOG_DIST = path.join(DIST, "blog");

const SITE_ORIGIN = "https://michaelsam94.tech";
const AUTHOR = "Michael Samuel Naeem";
const PERSON_ID = `${SITE_ORIGIN}/#person`;
const DEFAULT_OG = `${SITE_ORIGIN}/profile-photo.png`;

const escapeHtml = (s = "") =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

const readingTime = (md) => Math.max(1, Math.round(md.split(/\s+/).length / 200));

/** Shared <head> markup for every generated page. */
function head({ title, description, canonical, ogImage, jsonLd, ogType = "article" }) {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(title)}</title>
  <meta name="description" content="${escapeHtml(description)}" />
  <meta name="author" content="${AUTHOR}" />
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1" />
  <link rel="canonical" href="${canonical}" />
  <link rel="icon" type="image/png" sizes="48x48" href="/favicon-48.png" />
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  <meta name="theme-color" content="#7c5cff" />
  <meta name="color-scheme" content="dark" />
  <meta name="geo.region" content="EG-C" />
  <meta name="geo.placename" content="Cairo" />
  <meta property="og:type" content="${ogType}" />
  <meta property="og:site_name" content="Michael Samuel Naeem — Portfolio" />
  <meta property="og:title" content="${escapeHtml(title)}" />
  <meta property="og:description" content="${escapeHtml(description)}" />
  <meta property="og:url" content="${canonical}" />
  <meta property="og:image" content="${ogImage}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${escapeHtml(title)}" />
  <meta name="twitter:description" content="${escapeHtml(description)}" />
  <meta name="twitter:image" content="${ogImage}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/blog/assets/blog.css" />
  <script type="application/ld+json">${JSON.stringify(jsonLd)}</script>
</head>`;
}

const siteNav = `<header class="site-nav">
  <div class="nav-inner">
    <a class="brand" href="/">Michael Samuel Naeem</a>
    <nav class="nav-right" aria-label="Primary">
      <a href="/blog/">Blog</a>
      <a href="/#projects">Projects</a>
      <a href="/#contact">Contact</a>
    </nav>
  </div>
</header>`;

const siteFooter = `<footer class="site-footer">
  <div class="wrap">
    <p>Written by <a href="/">${AUTHOR}</a> — senior Android &amp; Flutter developer, mobile architect, based in Cairo, Egypt. Open to remote roles in Europe and the US.</p>
    <p><a href="/">← Back to portfolio</a> · <a href="/blog/">All articles</a></p>
  </div>
</footer>`;

const postCta = `<div class="post-cta">
  <h3>Hiring a senior Android / Flutter engineer?</h3>
  <p>I architect and ship production mobile software — Kotlin, Jetpack Compose, Flutter — for robotics, EV infrastructure, fintech, and real-time systems. Open to remote roles in Europe and the US.</p>
  <a class="btn" href="/#contact">Get in touch →</a>
</div>`;

function postJsonLd(p) {
  const url = `${SITE_ORIGIN}/blog/${p.slug}/`;
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BlogPosting",
        "@id": `${url}#article`,
        headline: p.title,
        description: p.description,
        image: p.ogImage || DEFAULT_OG,
        datePublished: p.datePublished,
        dateModified: p.dateModified || p.datePublished,
        keywords: p.keywords || (p.tags || []).join(", "),
        articleSection: (p.tags || [])[0] || "Engineering",
        inLanguage: "en",
        author: { "@id": PERSON_ID, "@type": "Person", name: AUTHOR, url: `${SITE_ORIGIN}/` },
        publisher: { "@id": PERSON_ID },
        mainEntityOfPage: { "@type": "WebPage", "@id": url },
        url,
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: `${SITE_ORIGIN}/` },
          { "@type": "ListItem", position: 2, name: "Blog", item: `${SITE_ORIGIN}/blog/` },
          { "@type": "ListItem", position: 3, name: p.title, item: url },
        ],
      },
    ],
  };
}

function renderPost(p, related) {
  const url = `${SITE_ORIGIN}/blog/${p.slug}/`;
  const relatedBlock = related.length
    ? `<aside class="related"><h3>Related reading</h3><ul>${related
        .map((r) => `<li><a href="/blog/${r.slug}/">${escapeHtml(r.title)}</a></li>`)
        .join("")}</ul></aside>`
    : "";
  const tags = (p.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  return `${head({
    title: `${p.title} — Michael Samuel Naeem`,
    description: p.description,
    canonical: url,
    ogImage: p.ogImage || DEFAULT_OG,
    jsonLd: postJsonLd(p),
  })}
<body>
  ${siteNav}
  <div class="wrap">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="/">Home</a> / <a href="/blog/">Blog</a> / <span>${escapeHtml(p.title)}</span>
    </nav>
    <article>
      <h1>${escapeHtml(p.title)}</h1>
      <p class="post-meta">By ${AUTHOR} · ${fmtDate(p.datePublished)} · ${readingTime(p.markdown)} min read</p>
      <div class="tags">${tags}</div>
      ${p.html}
      ${postCta}
      ${relatedBlock}
    </article>
  </div>
  ${siteFooter}
</body>
</html>`;
}

function renderHub(posts) {
  const cards = posts
    .map(
      (p) => `<a class="post-card" href="/blog/${p.slug}/">
        <h2>${escapeHtml(p.title)}</h2>
        <p>${escapeHtml(p.description)}</p>
        <p class="post-meta">${fmtDate(p.datePublished)} · ${readingTime(p.markdown)} min read</p>
      </a>`,
    )
    .join("\n");
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    "@id": `${SITE_ORIGIN}/blog/#blog`,
    name: "Engineering Insights — Michael Samuel Naeem",
    description:
      "Deep dives on Android, Kotlin, Jetpack Compose, Flutter, Clean Architecture, and real-time mobile systems by senior Android developer Michael Samuel Naeem.",
    url: `${SITE_ORIGIN}/blog/`,
    inLanguage: "en",
    publisher: { "@id": PERSON_ID },
    blogPost: posts.map((p) => ({
      "@type": "BlogPosting",
      headline: p.title,
      url: `${SITE_ORIGIN}/blog/${p.slug}/`,
      datePublished: p.datePublished,
    })),
  };
  return `${head({
    title: "Engineering Insights — Android, Kotlin, Flutter | Michael Samuel Naeem",
    description:
      "Technical deep dives on Android, Kotlin, Jetpack Compose, Flutter, Clean Architecture, and real-time mobile systems from a senior Android developer and mobile architect in Cairo.",
    canonical: `${SITE_ORIGIN}/blog/`,
    ogImage: DEFAULT_OG,
    jsonLd,
  })}
<body>
  ${siteNav}
  <div class="wrap hub-wrap">
    <header class="hub-head">
      <h1>Engineering Insights</h1>
      <p class="lede">Deep dives on Android, Kotlin, Jetpack Compose, Flutter, and the real-time mobile systems I build — robotics, EV infrastructure, and streaming at scale.</p>
    </header>
    <main class="post-grid">
      ${cards}
    </main>
  </div>
  ${siteFooter}
</body>
</html>`;
}

/* ---- Project case-study pages (/work/<slug>) ---------------------------- */

/**
 * FAQ content for local-tool case-study pages, keyed by `workSlug(name)`.
 * Rendered as a visible <section> AND mirrored as FAQPage JSON-LD (Google requires
 * the structured Q&A to match on-page text) to compete for "People Also Ask".
 */
const WORK_FAQ = {
  privai: [
    {
      q: "Does PrivAI work without an internet connection?",
      a: "Yes. PrivAI is built privacy-first and runs on-device — notes, voice transcription, OCR text extraction, and AI summaries are processed locally without requiring a cloud connection.",
    },
    {
      q: "Is my data private in PrivAI?",
      a: "Yes. Transcripts, extracted text, and summaries are processed and stored on your device rather than uploaded to a server, so your content stays under your control.",
    },
    {
      q: "What can PrivAI do?",
      a: "PrivAI is an on-device workspace for notes, voice-to-text transcription, OCR text extraction from images, and local AI summarization.",
    },
  ],
  devpocket: [
    {
      q: "Does DevPocket work offline?",
      a: "Yes. DevPocket is a fully offline Android developer toolbox — the code workspace, formatters, regex playground, and local sandbox all run on-device with no network required.",
    },
    {
      q: "What tools does DevPocket include?",
      a: "It bundles a code workspace, code formatters, a regex playground, a local JavaScript/math sandbox, and developer reference material in one offline app.",
    },
    {
      q: "Can DevPocket run code on the device?",
      a: "Yes. It includes a local sandbox that executes JavaScript and math expressions on-device without sending anything to a server.",
    },
  ],
  insightlyspend: [
    {
      q: "Does InsightlySpend work offline?",
      a: "Yes. InsightlySpend is an offline-first personal finance app — wallets, budgets, transactions, and receipts are stored locally using Room-backed on-device storage.",
    },
    {
      q: "Is my financial data uploaded to a server?",
      a: "No. Your wallets, transactions, and receipts stay on your device with local storage; the app is designed to keep financial data private.",
    },
    {
      q: "What does InsightlySpend track?",
      a: "It tracks wallets, budgets, transactions, and receipts, and surfaces local spending insights so you can see where your money goes.",
    },
  ],
  subtrackr: [
    {
      q: "What does SubTrackr do?",
      a: "SubTrackr tracks your subscriptions and licenses, sends renewal reminders, shows spending analytics, and helps you manage cancellations so you avoid unwanted charges.",
    },
    {
      q: "Can SubTrackr remind me before a subscription renews?",
      a: "Yes. It provides renewal reminders and tracking so recurring charges never surprise you.",
    },
    {
      q: "Does SubTrackr show how much I spend on subscriptions?",
      a: "Yes. It includes spending analytics across your subscriptions so you can see your total recurring cost at a glance.",
    },
  ],
};

/** Normalize a project's link(s) into a [{label, href}] list. */
const projectLinks = (p) => {
  if (Array.isArray(p.links)) return p.links;
  if (p.link) {
    const label = p.link.includes("play.google.com")
      ? "View on Google Play"
      : p.link.includes("github.com")
        ? "View source on GitHub"
        : "Visit project";
    return [{ label, href: p.link }];
  }
  return [];
};

/** Pick the most relevant launch article for a project, by tag/name overlap. */
function relatedPostFor(project, posts) {
  const hay = `${project.name} ${(project.tags || []).join(" ")}`.toLowerCase();
  const score = (post) =>
    (post.tags || []).filter((t) => hay.includes(t.toLowerCase())).length +
    (hay.includes("ev") || hay.includes("charging") ? (post.slug.includes("ev-charging") ? 3 : 0) : 0) +
    (hay.includes("flutter") ? (post.slug.includes("riverpod") ? 2 : 0) : 0) +
    (hay.includes("compose") ? (post.slug.includes("compose") ? 2 : 0) : 0);
  return [...posts].sort((a, b) => score(b) - score(a)).find((p) => score(p) > 0);
}

function workJsonLd(p, url) {
  const faq = WORK_FAQ[workSlug(p.name)];
  const isApp = projectLinks(p).some((l) => l.href.includes("play.google.com"));
  const node = isApp
    ? {
        "@type": "SoftwareApplication",
        applicationCategory: "MobileApplication",
        operatingSystem: "Android",
      }
    : { "@type": "CreativeWork" };
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        ...node,
        "@id": `${url}#project`,
        name: p.name,
        description: p.description,
        url,
        keywords: (p.tags || []).join(", "),
        ...(p.company ? { creator: { "@type": "Organization", name: p.company } } : {}),
        author: { "@id": PERSON_ID },
        ...(projectLinks(p)[0] ? { sameAs: projectLinks(p).map((l) => l.href) } : {}),
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: `${SITE_ORIGIN}/` },
          { "@type": "ListItem", position: 2, name: "Work", item: `${SITE_ORIGIN}/work/` },
          { "@type": "ListItem", position: 3, name: p.name, item: url },
        ],
      },
      ...(faq
        ? [
            {
              "@type": "FAQPage",
              "@id": `${url}#faq`,
              mainEntity: faq.map((f) => ({
                "@type": "Question",
                name: f.q,
                acceptedAnswer: { "@type": "Answer", text: f.a },
              })),
            },
          ]
        : []),
    ],
  };
}

function renderWork(p, posts) {
  const slug = workSlug(p.name);
  const url = `${SITE_ORIGIN}/work/${slug}/`;
  const faq = WORK_FAQ[slug];
  const faqBlock = faq
    ? `<section class="faq"><h2>Frequently asked questions</h2>${faq
        .map((f) => `<h3>${escapeHtml(f.q)}</h3><p>${escapeHtml(f.a)}</p>`)
        .join("")}</section>`
    : "";
  const links = projectLinks(p)
    .map((l) => `<a class="btn" href="${l.href}" rel="noopener" target="_blank">${escapeHtml(l.label)} ↗</a>`)
    .join(" ");
  const tags = (p.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("");
  const related = relatedPostFor(p, posts);
  const relatedBlock = related
    ? `<aside class="related"><h3>Related deep dive</h3><ul><li><a href="/blog/${related.slug}/">${escapeHtml(related.title)}</a></li></ul></aside>`
    : "";
  const title = `${p.name}${p.company ? ` · ${p.company}` : ""} — Case Study | Michael Samuel Naeem`;
  return `${head({
    title,
    description: p.description,
    canonical: url,
    ogImage: DEFAULT_OG,
    ogType: "website",
    jsonLd: workJsonLd(p, url),
  })}
<body>
  ${siteNav}
  <div class="wrap">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="/">Home</a> / <a href="/#projects">Work</a> / <span>${escapeHtml(p.name)}</span>
    </nav>
    <article>
      <h1>${escapeHtml(p.name)}</h1>
      ${p.company ? `<p class="post-meta">${escapeHtml(p.company)}</p>` : ""}
      <p class="lede">${escapeHtml(p.description)}</p>
      <div class="tags">${tags}</div>
      <p>${links}</p>
      ${faqBlock}
      ${relatedBlock}
      ${postCta}
    </article>
  </div>
  ${siteFooter}
</body>
</html>`;
}

function buildSitemap(posts, workSlugs) {
  const today = new Date().toISOString().slice(0, 10);
  const urls = [
    { loc: `${SITE_ORIGIN}/`, lastmod: today, changefreq: "monthly", priority: "1.0" },
    { loc: `${SITE_ORIGIN}/blog/`, lastmod: today, changefreq: "weekly", priority: "0.8" },
    ...posts.map((p) => ({
      loc: `${SITE_ORIGIN}/blog/${p.slug}/`,
      lastmod: (p.dateModified || p.datePublished).slice(0, 10),
      changefreq: "monthly",
      priority: "0.7",
    })),
    ...workSlugs.map((slug) => ({
      loc: `${SITE_ORIGIN}/work/${slug}/`,
      lastmod: today,
      changefreq: "monthly",
      priority: "0.7",
    })),
    {
      loc: `${SITE_ORIGIN}/Michael_Samuel_Naeem_Mobile_Developer_CV.pdf`,
      lastmod: today,
      changefreq: "monthly",
      priority: "0.6",
    },
  ];
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (u) =>
      `  <url>\n    <loc>${u.loc}</loc>\n    <lastmod>${u.lastmod}</lastmod>\n    <changefreq>${u.changefreq}</changefreq>\n    <priority>${u.priority}</priority>\n  </url>`,
  )
  .join("\n")}
</urlset>\n`;
}

async function main() {
  let files = [];
  try {
    files = (await readdir(CONTENT_DIR)).filter((f) => f.endsWith(".md"));
  } catch {
    console.warn(`[build-blog] No content dir at ${CONTENT_DIR}; skipping.`);
    return;
  }

  const posts = [];
  for (const file of files) {
    const raw = await readFile(path.join(CONTENT_DIR, file), "utf8");
    const { data, content } = matter(raw);
    if (data.draft) continue;
    posts.push({
      ...data,
      slug: data.slug || file.replace(/\.md$/, ""),
      markdown: content,
      html: marked.parse(content),
    });
  }

  posts.sort((a, b) => new Date(b.datePublished) - new Date(a.datePublished));

  await mkdir(path.join(BLOG_DIST, "assets"), { recursive: true });
  await copyFile(path.join(ROOT, "scripts/blog.css"), path.join(BLOG_DIST, "assets/blog.css"));

  for (const p of posts) {
    const related = posts.filter((r) => r.slug !== p.slug).slice(0, 3);
    const dir = path.join(BLOG_DIST, p.slug);
    await mkdir(dir, { recursive: true });
    await writeFile(path.join(dir, "index.html"), renderPost(p, related));
  }

  await writeFile(path.join(BLOG_DIST, "index.html"), renderHub(posts));

  // Project case-study pages — flagship projects only (avoid thin pages).
  const flagship = projects.filter((p) => p.highlight);
  const workSlugs = [];
  for (const project of flagship) {
    const slug = workSlug(project.name);
    workSlugs.push(slug);
    const dir = path.join(DIST, "work", slug);
    await mkdir(dir, { recursive: true });
    await writeFile(path.join(dir, "index.html"), renderWork(project, posts));
  }

  await writeFile(path.join(DIST, "sitemap.xml"), buildSitemap(posts, workSlugs));

  console.log(
    `[build-blog] Generated ${posts.length} post(s), ${workSlugs.length} /work page(s), /blog hub, and sitemap.xml`,
  );
}

main().catch((err) => {
  console.error("[build-blog] failed:", err);
  process.exit(1);
});
