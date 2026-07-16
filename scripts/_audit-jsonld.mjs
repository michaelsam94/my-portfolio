import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const DIST = path.join(ROOT, "out", "apps");
const APP_SEO_PATH = path.join(ROOT, "src", "data", "app-seo.json");

const RICH_RESULT_FIELDS = ["offers", "aggregateRating", "applicationCategory", "operatingSystem"];

function countRichResultFields(node) {
  return RICH_RESULT_FIELDS.filter((field) => node[field] != null).length;
}

function extractSoftwareNodes(html) {
  const scripts = [...html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  const nodes = [];
  for (const [, raw] of scripts) {
    let data;
    try {
      data = JSON.parse(raw);
    } catch {
      continue;
    }
    const graph = data["@graph"] ?? [data];
    for (const item of graph) {
      const types = Array.isArray(item["@type"]) ? item["@type"] : [item["@type"]];
      if (types.some((type) => type === "SoftwareApplication" || type === "MobileApplication")) {
        nodes.push(item);
      }
    }
  }
  return nodes;
}

const appSeo = JSON.parse(await readFile(APP_SEO_PATH, "utf8"));
const slugs = (await readdir(DIST, { withFileTypes: true }))
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort();

const failures = [];

for (const slug of slugs) {
  const html = await readFile(path.join(DIST, slug, "index.html"), "utf8");
  const nodes = extractSoftwareNodes(html);
  if (!nodes.length) {
    failures.push({ slug, reason: "no SoftwareApplication JSON-LD node" });
    continue;
  }

  const primary = nodes.find((node) => node["@id"]?.endsWith("#software")) ?? nodes[0];
  const richFieldCount = countRichResultFields(primary);
  const missing = RICH_RESULT_FIELDS.filter((field) => primary[field] == null);
  const expectedCategory = appSeo.apps?.[slug]?.applicationCategory;

  if (richFieldCount < 2) {
    failures.push({
      slug,
      reason: `only ${richFieldCount}/2+ rich-result fields`,
      missing,
      node: primary,
    });
    continue;
  }

  if (primary.operatingSystem !== "Android") {
    failures.push({ slug, reason: `operatingSystem is ${JSON.stringify(primary.operatingSystem)}` });
  }

  if (!primary.offers?.priceCurrency || primary.offers.price == null) {
    failures.push({ slug, reason: "offers missing price or priceCurrency" });
  }

  if (expectedCategory && primary.applicationCategory !== expectedCategory) {
    failures.push({
      slug,
      reason: `applicationCategory ${JSON.stringify(primary.applicationCategory)} != ${expectedCategory}`,
    });
  }

  if (primary.aggregateRating) {
    failures.push({ slug, reason: "unexpected aggregateRating (must not invent ratings)" });
  }
}

if (failures.length) {
  console.error(`[audit-jsonld] ${failures.length} app(s) failed:`);
  for (const failure of failures) {
    console.error(`- ${failure.slug}: ${failure.reason}`);
    if (failure.missing) console.error(`  missing: ${failure.missing.join(", ")}`);
  }
  process.exit(1);
}

console.log(`[audit-jsonld] OK — ${slugs.length} apps each have offers + applicationCategory + operatingSystem`);
