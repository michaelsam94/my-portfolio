/**
 * One-shot sync: update content/apps/*.md frontmatter descriptions + FAQ blocks
 * from src/data/app-seo.json (ad-free SEO/AEO/GEO copy).
 */
import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const APPS_DIR = path.join(ROOT, "content", "apps");
const SEO = JSON.parse(await readFile(path.join(ROOT, "src", "data", "app-seo.json"), "utf8"));

function upsertDescription(frontmatter, description) {
  if (/^description:\s*/m.test(frontmatter)) {
    return frontmatter.replace(/^description:\s*.*$/m, `description: ${JSON.stringify(description)}`);
  }
  return `${frontmatter.trimEnd()}\ndescription: ${JSON.stringify(description)}\n`;
}

function stripExistingSeoBlocks(body) {
  return body
    .replace(/\n## Frequently asked questions[\s\S]*?(?=\n## [A-Z]|\n?$)/, "\n")
    .replace(/\n## Related searches[\s\S]*?(?=\n## [A-Z]|\n?$)/, "\n")
    .trimEnd();
}

function ensureAdFreeLead(body, title, answerFirst) {
  const trimmed = body.trim();
  if (!trimmed) {
    return `${answerFirst}\n\n**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.\n`;
  }
  if (/ad-free|no ads|without ads/i.test(trimmed.slice(0, 500))) {
    return trimmed;
  }
  return `${answerFirst}\n\n**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.\n\n${trimmed}`;
}

const files = (await readdir(APPS_DIR)).filter((f) => f.endsWith(".md")).sort();
let updated = 0;

for (const file of files) {
  const slug = file.replace(/\.md$/, "");
  const seo = SEO.apps[slug];
  if (!seo) {
    console.warn(`[sync-app-seo] missing SEO entry for ${slug}`);
    continue;
  }

  const fullPath = path.join(APPS_DIR, file);
  const raw = await readFile(fullPath, "utf8");
  const match = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) {
    console.warn(`[sync-app-seo] no frontmatter in ${file}`);
    continue;
  }

  const titleMatch = match[1].match(/^title:\s*(.+)$/m);
  const title = (titleMatch?.[1] || slug).replace(/^["']|["']$/g, "");
  let frontmatter = upsertDescription(match[1], seo.seoDescription);
  if (!/^primaryKeyword:/m.test(frontmatter)) {
    frontmatter = `${frontmatter.trimEnd()}\nprimaryKeyword: ${JSON.stringify(seo.primaryKeyword)}\nkeywords: ${JSON.stringify(seo.keywords.slice(0, 10).join(", "))}\n`;
  } else {
    frontmatter = frontmatter
      .replace(/^primaryKeyword:\s*.*$/m, `primaryKeyword: ${JSON.stringify(seo.primaryKeyword)}`)
      .replace(/^keywords:\s*.*$/m, `keywords: ${JSON.stringify(seo.keywords.slice(0, 10).join(", "))}`);
  }

  let body = stripExistingSeoBlocks(match[2] || "");
  body = ensureAdFreeLead(body, title, seo.answerFirst);

  await writeFile(fullPath, `---\n${frontmatter.trim()}\n---\n\n${body.trim()}\n`);
  updated += 1;
  console.log(`[sync-app-seo] ${slug}`);
}

console.log(`[sync-app-seo] updated ${updated}/${files.length} apps`);
