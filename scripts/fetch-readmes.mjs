/**
 * One-off content fetcher (run manually, requires `gh` auth — NOT part of the build).
 *
 *   node scripts/fetch-readmes.mjs
 *
 * Pulls the README of each published Play Store app and VS Code extension from
 * GitHub, sanitizes it into clean Markdown, and writes it to `content/apps/*.md`
 * and `content/extensions/*.md` with SEO frontmatter. Those files are committed so
 * the actual site build (`scripts/build-blog.mjs`) stays hermetic — Netlify never
 * needs network or `gh` auth.
 *
 * Re-run whenever an upstream README changes, then commit the regenerated content.
 */
import { execFileSync } from "node:child_process";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { playStoreApps, workSlug } from "../src/data/portfolio.ts";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const GH_USER = "michaelsam94";

/** Play Store app display name -> GitHub repo (names diverge in a few cases). */
const APP_REPO = {
  InsightlySpend: "InsightlySpend",
  "Tic Tac Toe": "tic_tac_toe",
  Subtrackr: "SubtrackrAnroid",
  WalkPlanner: "TrailMate",
  AuraSound: "AuraSound",
  "Wi-Fi Drop": "Wi-Fi-Drop",
  "Todo App": "TodoAppAiStudio",
  NotchCommand: "NotchCommand",
  ClipVault: "ClipVault",
  FrozenDroid: "FrozenDroid",
  "PDF Toolkit": "PDF-Toolkit",
  "Bulk QR & Barcode Suite": "Bulk-QR-Barcode-Suite",
  SensorScope: "SensorScope",
  "Doc Scanner Vectorizer": "Doc-Scanner-Vectorizer",
  FolderFlow: "FolderFlow",
  "Micro Budgeting": "Micro-Budgeting",
  StoreClear: "StoreClear",
  "Smooth-Mo": "Smooth-Mo",
  EdgeFlow: "EdgeFlow",
  PrivAI: "PrivAI",
  "Photo Optimizer": "Photo-Optimizer",
  "BLE Finder": "BLE-Finder",
  "ClearVoice AI": "ClearVoice-AI",
  DevPocket: "DevPocket",
};

/** VS Code extensions: marketplace name + repo (postgrabberext excluded — browser ext). */
const EXTENSIONS = [
  { repo: "pdfviewerext", name: "pdfviewerext", display: "PdfViewer", desc: "Open PDF files quickly from VS Code." },
  { repo: "pdftomdext", name: "pdftomdext", display: "PdfToMd", desc: "Convert PDF files to Markdown from VS Code." },
  { repo: "mdviewerext", name: "mdviewerext", display: "MdViewer", desc: "Preview Markdown files quickly from VS Code." },
  { repo: "docxviewerext", name: "docxviewerext", display: "DocxViewer", desc: "Preview DOCX files quickly from VS Code." },
  { repo: "contextporterext", name: "contextporterext", display: "Context Porter", desc: "Export AI session and project context to Markdown for handoff." },
  { repo: "docxtopdfext", name: "docxtopdfext", display: "DocxToPdf", desc: "Convert DOCX files to PDF from VS Code." },
  { repo: "docxtomdext", name: "docxtomdext", display: "DocxToMd", desc: "Convert DOCX files to Markdown from VS Code." },
  { repo: "mdtopdfext", name: "mdtopdfext", display: "MdToPdf", desc: "Convert Markdown files to PDF from VS Code." },
  { repo: "csvstuidoext", name: "csv-studio", display: "CSV Studio", desc: "View and edit CSV files as interactive spreadsheets in VS Code." },
];

function fetchReadme(repo) {
  try {
    const b64 = execFileSync("gh", ["api", `repos/${GH_USER}/${repo}/readme`, "--jq", ".content"], {
      encoding: "utf8",
    });
    return Buffer.from(b64, "base64").toString("utf8");
  } catch {
    return "";
  }
}

function fetchFile(repo, filePath) {
  try {
    const b64 = execFileSync("gh", ["api", `repos/${GH_USER}/${repo}/contents/${filePath}`, "--jq", ".content"], {
      encoding: "utf8",
    });
    return Buffer.from(b64, "base64").toString("utf8");
  } catch {
    return "";
  }
}

/** Drop markdown links/images whose target is a repo-relative path (would 404 on the site). */
function neutralizeRelativeLinks(s) {
  return s
    .replace(/!\[[^\]]*\]\((?!https?:)[^)]*\)/g, "") // relative images
    .replace(/\[([^\]]+)\]\((?!https?:|mailto:|#)[^)]*\)/g, "$1") // relative links → plain text
    .replace(/`([^`]*\/)`/g, "$1") // leftover `path/` inline code
    .replace(/^.*\b(screenshots?|feature graphic|app[- ]icon)\b.*\bplay[-_]?store.*$/gim, "") // stray asset sentences
    // Internal repo tooling references (folder paths, asset scripts) — not product content.
    .replace(/^.*(play[-_]store[/_][^\s)]*|app-assets\/scripts|init-play-store|verify-play-store).*$/gim, "");
}

/** Turn a Play Store `listing-descriptions.md` into clean product-page Markdown. */
function fromListing(md) {
  const drop = /^##\s+.*\b(App name|Short description|Title|Subtitle|Screenshots?|Promo|Keywords|Categor|Graphics|Assets|Icon|Feature)\b/i;
  const kept = [];
  let skip = false;
  for (let line of md.split("\n")) {
    if (/^##\s+/.test(line)) {
      skip = drop.test(line);
      line = line
        .replace(/\s*\([^)]*chars?[^)]*\)\s*$/i, "")
        .replace(/^##\s+Full description.*$/i, "## Overview")
        .replace(/^##\s+What'?s new.*$/i, "## Recent updates");
    }
    if (!skip) kept.push(line);
  }
  return neutralizeRelativeLinks(kept.join("\n")).replace(/^#\s+.*$/m, "").replace(/\n{3,}/g, "\n\n").trim();
}

/** Strip GitHub-flavored noise that doesn't belong on a public product page. */
function sanitize(md) {
  let s = md;
  s = s.replace(/<!--[\s\S]*?-->/g, ""); // HTML comments
  s = s.replace(/<div[\s\S]*?<\/div>/gi, ""); // banner / centered blocks
  s = s.replace(/<table[\s\S]*?<\/table>/gi, ""); // screenshot grids
  s = s.replace(/<img[^>]*>/gi, ""); // stray img tags
  s = s.replace(/```mermaid[\s\S]*?```/g, ""); // mermaid diagrams render as junk
  s = s.replace(/^\s*\[?!\[[^\]]*\]\([^)]*\)\]?(\([^)]*\))?\s*$/gim, ""); // badge image / badge-link lines
  s = s.replace(/!\[[^\]]*\]\((?!https?:)[^)]*\)/g, ""); // relative-path images (screenshots)
  s = s.replace(/^.*Demo link:.*$/gim, ""); // "Demo link: Not configured."

  // Drop dev/boilerplate sections (heading until next h2).
  const dropRe =
    /^##\s+.*\b(Getting Started|Build|Building|Development|Dev Setup|Setup|Installation|Install|Running|Run Locally|Run and deploy|Prerequisites|Project Structure|Folder Structure|Contributing|License|Scripts|Local Development|Roadmap|Acknowledg|Credits|Requirements|Configuration \(Dev\))\b/i;
  const kept = [];
  let skip = false;
  for (const line of s.split("\n")) {
    if (/^##\s+/.test(line)) skip = dropRe.test(line);
    if (!skip) kept.push(line);
  }
  s = kept.join("\n");

  // Demote a leading H1 (we render our own page title) and tidy whitespace.
  s = neutralizeRelativeLinks(s).replace(/^#\s+.*$/m, "").replace(/\n{3,}/g, "\n\n").trim();
  return s;
}

const wordCount = (s) => s.split(/\s+/).filter(Boolean).length;
const isBoilerplate = (raw, clean) =>
  /Run and deploy your AI Studio app/i.test(raw) || wordCount(clean) < 40;

const yaml = (obj) =>
  Object.entries(obj)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${k}: ${typeof v === "boolean" ? v : JSON.stringify(v)}`)
    .join("\n");

async function main() {
  const appsDir = path.join(ROOT, "content/apps");
  const extDir = path.join(ROOT, "content/extensions");
  await mkdir(appsDir, { recursive: true });
  await mkdir(extDir, { recursive: true });

  const report = [];

  for (const app of playStoreApps) {
    const repo = APP_REPO[app.name];
    if (!repo) {
      report.push(`SKIP app (no repo): ${app.name}`);
      continue;
    }
    const raw = fetchReadme(repo);
    let body = sanitize(raw);
    let source = "readme";
    // Boilerplate README (e.g. AI Studio scaffold) → use the Play Store listing copy.
    if (isBoilerplate(raw, body)) {
      const candidates = [
        "play-store/listing-descriptions.md",
        "play_store_assets/STORE_LISTING.md",
        "play-store/README.md",
        "play_store_assets/listing-descriptions.md",
      ];
      source = "none";
      body = "";
      for (const c of candidates) {
        const listing = fromListing(fetchFile(repo, c));
        if (wordCount(listing) >= 60) {
          body = listing;
          source = "listing";
          break;
        }
      }
      // Last resort: the repo's metadata.json description (a sentence or two).
      if (source === "none") {
        const meta = fetchFile(repo, "metadata.json");
        let metaDesc = "";
        try {
          const j = JSON.parse(meta);
          metaDesc = j.description || j.shortDescription || "";
        } catch {
          /* ignore */
        }
        const intro = [metaDesc, app.description].filter(Boolean).join(" ");
        if (intro) {
          body = intro;
          source = "metadata";
        }
      }
    }
    const thin = source === "none" || source === "metadata";
    const slug = workSlug(app.name);
    const fm = yaml({
      title: app.name,
      slug,
      kind: "app",
      category: app.category,
      packageId: app.packageId,
      playStoreUrl: app.playStoreUrl,
      githubUrl: `https://github.com/${GH_USER}/${repo}`,
      image: app.image,
      description: app.description,
      source,
      thin,
    });
    await writeFile(path.join(appsDir, `${slug}.md`), `---\n${fm}\n---\n\n${body}\n`);
    report.push(`app  ${source.padEnd(7)} ${slug} <- ${repo} (${wordCount(body)}w)`);
  }

  for (const ext of EXTENSIONS) {
    const raw = fetchReadme(ext.repo);
    const clean = sanitize(raw);
    const thin = isBoilerplate(raw, clean);
    const fm = yaml({
      title: ext.display,
      slug: ext.name,
      kind: "ext",
      marketplaceUrl: `https://marketplace.visualstudio.com/items?itemName=${GH_USER}.${ext.name}`,
      openVsxUrl: `https://open-vsx.org/extension/${GH_USER}/${ext.name}`,
      githubUrl: `https://github.com/${GH_USER}/${ext.repo}`,
      description: ext.desc,
      thin,
    });
    await writeFile(path.join(extDir, `${ext.name}.md`), `---\n${fm}\n---\n\n${thin ? "" : clean}\n`);
    report.push(`ext  ${thin ? "THIN" : "OK  "} ${ext.name} <- ${ext.repo} (${wordCount(clean)}w)`);
  }

  console.log(report.join("\n"));
  console.log(`\nWrote ${report.filter((r) => !r.startsWith("SKIP")).length} content file(s).`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
