import { readdir, readFile, writeFile, access } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const DIST = path.join(ROOT, "out");
const ORIGIN = "https://michaelsam94.com";
const AUTHOR = "Michael Samuel Naeem";
const TODAY = new Date().toISOString().slice(0, 10);
const APP_SEO_PATH = path.join(ROOT, "src", "data", "app-seo.json");

const appSeoCatalog = JSON.parse(await readFile(APP_SEO_PATH, "utf8"));
const AD_FREE_TAGLINE = appSeoCatalog.adFreeTagline || "Completely ad-free — no ads, no trackers, no sponsored clutter.";

const COLLECTIONS = [
  {
    type: "apps",
    contentDir: path.join(ROOT, "content", "apps"),
    distBase: path.join(DIST, "apps"),
    urlBase: "apps",
    hubTitle: "Ad-free Android apps by Michael Samuel Naeem",
    hubDescription:
      "Complete index of completely ad-free Android apps by Michael Samuel Naeem on Google Play and GitHub — utility, privacy, productivity, developer, media, finance, and device tools with no ads.",
    schemaApplicationCategory: "MobileApplication",
    marketplaceLabel: "Google Play",
  },
  {
    type: "vscode",
    contentDir: path.join(ROOT, "content", "extensions"),
    distBase: path.join(DIST, "vscode"),
    urlBase: "vscode",
    hubTitle: "VS Code extensions by Michael Samuel Naeem",
    hubDescription:
      "Complete index of Michael Samuel Naeem Visual Studio Code extensions for PDF, DOCX, Markdown, CSV, and workspace document workflows.",
    schemaApplicationCategory: "DeveloperApplication",
    marketplaceLabel: "Visual Studio Marketplace",
  },
];

const escapeHtml = (value = "") =>
  String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const stripMarkdown = (value = "") =>
  value
    .replace(/^---[\s\S]*?---/, "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)]\([^)]*\)/g, "$1")
    .replace(/[#>*_\-|]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

function parseFrontmatter(markdown) {
  const match = markdown.match(/^---\n([\s\S]*?)\n---/);
  const data = {};
  if (!match) return data;

  for (const line of match[1].split("\n")) {
    const item = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!item) continue;
    data[item[1]] = item[2].trim().replace(/^["']|["']$/g, "");
  }

  return data;
}

async function readProducts(collection) {
  const files = (await readdir(collection.contentDir))
    .filter((file) => file.endsWith(".md"))
    .sort();

  return Promise.all(
    files.map(async (file) => {
      const slug = file.replace(/\.md$/, "");
      const markdown = await readFile(path.join(collection.contentDir, file), "utf8");
      const frontmatter = parseFrontmatter(markdown);
      const fallbackName = slug
        .split("-")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
      const title = frontmatter.title || frontmatter.name || fallbackName;
      const summary =
        frontmatter.description ||
        stripMarkdown(markdown).split(". ").slice(0, 2).join(". ").slice(0, 220);
      const marketplaceUrl =
        frontmatter.playStoreUrl || frontmatter.marketplaceUrl || frontmatter.openVsxUrl || "";

      return {
        slug,
        title,
        summary,
        category: frontmatter.category || collection.schemaApplicationCategory,
        packageId: frontmatter.packageId || frontmatter.extensionId || "",
        image: frontmatter.image || frontmatter.icon || "",
        marketplaceUrl,
        githubUrl: frontmatter.githubUrl || "",
        pageUrl: `${ORIGIN}/${collection.urlBase}/${slug}/`,
      };
    }),
  );
}

function jsonLdForProduct(collection, product) {
  const seo = collection.type === "apps" ? appSeoCatalog.apps?.[product.slug] : undefined;
  const isApp = collection.type === "apps";
  const description =
    seo?.seoDescription ||
    (isApp
      ? `${product.summary} ${AD_FREE_TAGLINE}`
      : product.summary);
  const software = {
    "@type": isApp ? ["SoftwareApplication", "MobileApplication"] : "SoftwareApplication",
    "@id": `${product.pageUrl}#software`,
    name: product.title,
    alternateName: [
      product.packageId,
      `${product.title} ${isApp ? "ad-free Android app" : "VS Code extension"}`,
      isApp ? `${product.title} no ads` : null,
    ].filter(Boolean),
    description,
    applicationCategory: seo?.applicationCategory || product.category,
    operatingSystem: isApp ? "Android" : "Windows, macOS, Linux",
    url: product.pageUrl,
    isAccessibleForFree: true,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      availability: "https://schema.org/InStock",
      description: isApp
        ? "Free ad-free Android app — no ads, no in-app advertising."
        : "Free VS Code extension.",
    },
    keywords: seo?.keywords?.join(", "),
    featureList: seo?.featureHighlights?.join(". "),
    author: {
      "@type": "Person",
      name: AUTHOR,
      url: ORIGIN,
    },
    publisher: {
      "@type": "Person",
      name: AUTHOR,
      url: ORIGIN,
    },
    sameAs: [product.marketplaceUrl, product.githubUrl].filter(Boolean),
    image: product.image || undefined,
    downloadUrl: product.marketplaceUrl || undefined,
  };

  const howToNode = seo?.howTo
    ? {
        "@type": "HowTo",
        "@id": `${product.pageUrl}#howto`,
        name: seo.howTo.name,
        description: seo.howTo.description,
        image: product.image || undefined,
        totalTime: "PT2M",
        step: seo.howTo.steps.map((step, index) => ({
          "@type": "HowToStep",
          position: index + 1,
          name: step.name,
          text: step.text,
          url: `${product.pageUrl}#howto-step-${index + 1}`,
        })),
      }
    : null;

  if (!seo?.faqs?.length && !howToNode) {
    return { "@context": "https://schema.org", ...software };
  }

  return {
    "@context": "https://schema.org",
    "@graph": [
      software,
      ...(seo?.faqs?.length
        ? [
            {
              "@type": "FAQPage",
              "@id": `${product.pageUrl}#faq`,
              mainEntity: seo.faqs.map((item) => ({
                "@type": "Question",
                name: item.question,
                acceptedAnswer: { "@type": "Answer", text: item.answer },
              })),
            },
          ]
        : []),
      ...(howToNode ? [howToNode] : []),
    ],
  };
}

function jsonLdForHub(collection, products) {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${ORIGIN}/${collection.urlBase}/#collection`,
        name: collection.hubTitle,
        description: collection.hubDescription,
        url: `${ORIGIN}/${collection.urlBase}/`,
        author: {
          "@type": "Person",
          name: AUTHOR,
          url: ORIGIN,
        },
        mainEntity: {
          "@id": `${ORIGIN}/${collection.urlBase}/#item-list`,
        },
      },
      {
        "@type": "ItemList",
        "@id": `${ORIGIN}/${collection.urlBase}/#item-list`,
        name: collection.hubTitle,
        numberOfItems: products.length,
        itemListElement: products.map((product, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name: product.title,
          url: product.pageUrl,
        })),
      },
    ],
  };
}

function discoverySection(collection, products, currentSlug = "") {
  const label = collection.type === "apps" ? "ad-free Android app" : "VS Code extension";
  const list = products
    .map((product) => {
      const current = product.slug === currentSlug ? ' aria-current="page"' : "";
      const seo = collection.type === "apps" ? appSeoCatalog.apps?.[product.slug] : undefined;
      const meta = [
        collection.type === "apps" ? "ad-free" : null,
        product.category,
        product.packageId,
        seo?.primaryKeyword,
      ]
        .filter(Boolean)
        .join(" · ");
      return `<li><a href="/${collection.urlBase}/${product.slug}/"${current}>${escapeHtml(product.title)}</a>${meta ? ` <span>${escapeHtml(meta)}</span>` : ""}</li>`;
    })
    .join("\n");

  const adFreeNote =
    collection.type === "apps"
      ? ` ${escapeHtml(AD_FREE_TAGLINE)} Every listed Android app is published without ads.`
      : "";

  return `<!-- seo-discovery:start -->
<section class="seo-discovery" aria-labelledby="${collection.type}-seo-discovery-title">
  <h2 id="${collection.type}-seo-discovery-title">All ${escapeHtml(label)} names</h2>
  <p>${escapeHtml(collection.hubDescription)}${adFreeNote} Search engines can discover each exact product name, package, marketplace listing, and source page from this index.</p>
  <ul>
${list}
  </ul>
</section>
<!-- seo-discovery:end -->`;
}

function replaceMarkedBlock(html, marker, replacement) {
  const pattern = new RegExp(`<!-- ${marker}:start -->[\\s\\S]*?<!-- ${marker}:end -->`);
  if (pattern.test(html)) return html.replace(pattern, replacement);
  if (html.includes("</main>")) return html.replace("</main>", `${replacement}\n</main>`);
  if (html.includes("</article>")) return html.replace("</article>", `${replacement}\n</article>`);
  return html.replace("</body>", `${replacement}\n</body>`);
}

function injectJsonLd(html, id, data) {
  const marker = `seo-jsonld-${id}`;
  const script = `<!-- ${marker}:start -->\n<script type="application/ld+json">${JSON.stringify(data)}</script>\n<!-- ${marker}:end -->`;
  const pattern = new RegExp(`<!-- ${marker}:start -->[\\s\\S]*?<!-- ${marker}:end -->`);
  if (pattern.test(html)) return html.replace(pattern, script);
  return html.replace("</head>", `${script}\n</head>`);
}

async function fileExists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

async function enhanceHtml(collection, products) {
  // The Next.js /apps hub and /apps/<slug> pages already emit richer JSON-LD
  // (SoftwareApplication, WebPage, FAQPage, HowTo, BreadcrumbList) during
  // `next build`. Re-injecting it here produced duplicate @id nodes on every
  // app page, which audit tools flag as structured-data markup errors. VS Code
  // pages get no JSON-LD from Next, so this script remains their only source.
  const injectSchema = collection.type !== "apps";

  const hubPath = path.join(collection.distBase, "index.html");
  if (await fileExists(hubPath)) {
    let html = await readFile(hubPath, "utf8");
    html = replaceMarkedBlock(html, "seo-discovery", discoverySection(collection, products));
    if (injectSchema) {
      html = injectJsonLd(html, `${collection.type}-hub`, jsonLdForHub(collection, products));
    }
    await writeFile(hubPath, html);
  }

  for (const product of products) {
    const file = path.join(collection.distBase, product.slug, "index.html");
    if (!(await fileExists(file))) continue;
    let html = await readFile(file, "utf8");
    html = replaceMarkedBlock(html, "seo-discovery", discoverySection(collection, products, product.slug));
    if (injectSchema) {
      html = injectJsonLd(html, `${collection.type}-${product.slug}`, jsonLdForProduct(collection, product));
    }
    await writeFile(file, html);
  }
}

function sitemapUrl(loc, priority = "0.6") {
  return `  <url>
    <loc>${loc}</loc>
    <lastmod>${TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>${priority}</priority>
  </url>`;
}

async function ensureSitemaps(allProducts) {
  const sitemapPath = path.join(DIST, "sitemap.xml");
  if (await fileExists(sitemapPath)) {
    let xml = await readFile(sitemapPath, "utf8");
    const missing = allProducts
      .map((product) => product.pageUrl)
      .filter((url) => !xml.includes(`<loc>${url}</loc>`));
    if (missing.length) {
      xml = xml.replace("</urlset>", `${missing.map((url) => sitemapUrl(url)).join("\n")}\n</urlset>`);
      await writeFile(sitemapPath, xml);
    }
    await writeFile(path.join(DIST, "sitemap-com.xml"), xml);
  }

  const txtPath = path.join(DIST, "sitemap.txt");
  if (await fileExists(txtPath)) {
    const urls = new Set((await readFile(txtPath, "utf8")).split(/\s+/).filter(Boolean));
    for (const product of allProducts) urls.add(product.pageUrl);
    await writeFile(txtPath, `${[...urls].sort().join("\n")}\n`);
  }
}

const allProducts = [];

for (const collection of COLLECTIONS) {
  const products = await readProducts(collection);
  allProducts.push(...products);
  await enhanceHtml(collection, products);
  console.log(`[enhance-product-seo] ${collection.type}: ${products.length} crawlable product pages indexed`);
}

await ensureSitemaps(allProducts);
