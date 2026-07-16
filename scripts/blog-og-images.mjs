/**
 * Build-time OG card generation for blog posts (1200×630 PNG).
 * Uses topic-cluster accent colors + per-post title text on a dark card
 * that matches the static blog aesthetic.
 */
import { mkdir, writeFile, stat } from "node:fs/promises";
import path from "node:path";

const W = 1200;
const H = 630;

/** Topic cluster palette — muted accents on the blog's dark base, not generic AI purple. */
export const TOPIC_CLUSTERS = {
  android: {
    label: "Android",
    accent: "#22d3ee",
    accentSoft: "rgba(34, 211, 238, 0.18)",
    tags: ["Android", "Jetpack Compose", "Kotlin Multiplatform", "Gradle", "NDK", "Native"],
  },
  kotlin: {
    label: "Kotlin",
    accent: "#38bdf8",
    accentSoft: "rgba(56, 189, 248, 0.18)",
    tags: ["Kotlin", "Coroutines", "KSP", "Kotlin/Native"],
  },
  flutter: {
    label: "Flutter",
    accent: "#fbbf24",
    accentSoft: "rgba(251, 191, 36, 0.16)",
    tags: ["Flutter", "Dart", "Riverpod", "Flutter Web"],
  },
  mobile: {
    label: "Mobile",
    accent: "#34d399",
    accentSoft: "rgba(52, 211, 153, 0.16)",
    tags: ["Mobile", "iOS", "Performance", "Architecture"],
  },
  ai: {
    label: "AI & LLM",
    accent: "#f472b6",
    accentSoft: "rgba(244, 114, 182, 0.16)",
    tags: ["AI", "LLM", "RAG", "AI Agents", "MCP", "Machine Learning", "NLP", "Prompt Engineering"],
  },
  backend: {
    label: "Backend",
    accent: "#60a5fa",
    accentSoft: "rgba(96, 165, 250, 0.16)",
    tags: ["Backend", "API", "GraphQL", "gRPC", "Webhooks", "REST"],
  },
  infra: {
    label: "Infrastructure",
    accent: "#818cf8",
    accentSoft: "rgba(129, 140, 248, 0.16)",
    tags: ["DevOps", "Infrastructure", "Kubernetes", "Platform Engineering", "SRE", "CI/CD"],
  },
  web: {
    label: "Web",
    accent: "#4ade80",
    accentSoft: "rgba(74, 222, 128, 0.16)",
    tags: ["Web", "Frontend", "CSS", "React", "Next.js", "Web Components"],
  },
  security: {
    label: "Security",
    accent: "#fb7185",
    accentSoft: "rgba(251, 113, 133, 0.16)",
    tags: ["Security", "Authentication", "OAuth", "JWT"],
  },
  iot: {
    label: "IoT & Edge",
    accent: "#a3e635",
    accentSoft: "rgba(163, 230, 53, 0.14)",
    tags: ["IoT", "Embedded", "Edge Computing", "MQTT", "OPC-UA"],
  },
  data: {
    label: "Data",
    accent: "#2dd4bf",
    accentSoft: "rgba(45, 212, 191, 0.16)",
    tags: ["Data Engineering", "Database", "PostgreSQL", "Redis", "Kafka"],
  },
  testing: {
    label: "Testing",
    accent: "#c084fc",
    accentSoft: "rgba(192, 132, 252, 0.14)",
    tags: ["Testing", "QA", "TDD"],
  },
  default: {
    label: "Engineering",
    accent: "#94a3b8",
    accentSoft: "rgba(148, 163, 184, 0.14)",
    tags: [],
  },
};

const TAG_TO_CLUSTER = new Map();
for (const [key, cluster] of Object.entries(TOPIC_CLUSTERS)) {
  if (key === "default") continue;
  for (const tag of cluster.tags) TAG_TO_CLUSTER.set(tag.toLowerCase(), key);
}

/** Resolve the best-matching topic cluster from post tags. */
export function primaryCluster(tags = []) {
  for (const tag of tags) {
    const key = TAG_TO_CLUSTER.get(String(tag).toLowerCase());
    if (key) return { key, ...TOPIC_CLUSTERS[key] };
  }
  return { key: "default", ...TOPIC_CLUSTERS.default };
}

const escapeXml = (s = "") =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");

/** Word-wrap a title into lines that fit the OG card (~42 chars per line). */
export function wrapTitle(title, maxChars = 42, maxLines = 4) {
  const words = String(title).trim().split(/\s+/);
  const lines = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length <= maxChars) {
      current = next;
    } else {
      if (current) lines.push(current);
      current = word;
      if (lines.length >= maxLines - 1) break;
    }
  }
  if (current && lines.length < maxLines) lines.push(current);
  if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length) {
    const last = lines[maxLines - 1];
    lines[maxLines - 1] = last.length > 3 ? last.slice(0, -1) + "…" : last + "…";
  }
  return lines;
}

/** Build an SVG OG card string for a post. */
export function buildOgSvg({ title, tags = [], author = "Michael Samuel Naeem" }) {
  const cluster = primaryCluster(tags);
  const topicLabel = (tags[0] || cluster.label).slice(0, 32);
  const chipW = Math.min(420, topicLabel.length * 11 + 32);
  const lines = wrapTitle(title);
  const titleY = 280 - (lines.length - 1) * 28;
  const titleLines = lines
    .map(
      (line, i) =>
        `<tspan x="80" dy="${i === 0 ? 0 : 58}">${escapeXml(line)}</tspan>`,
    )
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0c0b0f"/>
      <stop offset="55%" stop-color="#12111a"/>
      <stop offset="100%" stop-color="#0f0e14"/>
    </linearGradient>
    <radialGradient id="glow" cx="85%" cy="15%" r="55%">
      <stop offset="0%" stop-color="${cluster.accent}" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="${cluster.accent}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M 48 0 L 0 0 0 48" fill="none" stroke="rgba(255,255,255,0.03)" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect width="${W}" height="${H}" fill="url(#glow)"/>
  <rect width="${W}" height="${H}" fill="url(#grid)"/>
  <rect x="0" y="0" width="6" height="${H}" fill="${cluster.accent}"/>
  <rect x="80" y="68" width="${chipW}" height="36" rx="8" fill="${cluster.accentSoft}" stroke="${cluster.accent}" stroke-opacity="0.35" stroke-width="1"/>
  <text x="96" y="92" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="15" font-weight="600" fill="${cluster.accent}" letter-spacing="0.04em">${escapeXml(topicLabel.toUpperCase())}</text>
  <text x="80" y="${titleY}" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="52" font-weight="700" fill="#f5f4f8" letter-spacing="-0.02em">${titleLines}</text>
  <line x1="80" y1="520" x2="320" y2="520" stroke="${cluster.accent}" stroke-width="3" stroke-linecap="round" opacity="0.7"/>
  <text x="80" y="560" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="22" font-weight="500" fill="#9b98a8">${escapeXml(author)}</text>
  <text x="80" y="592" font-family="Inter, ui-sans-serif, system-ui, sans-serif" font-size="18" font-weight="400" fill="#6b6578">blog.michaelsam94.com</text>
</svg>`;
}

/**
 * Generate PNG OG images for all posts into `ogDir`.
 * Returns a Map slug → absolute public URL path segment.
 */
export async function generateOgImages(posts, ogDir, blogOrigin, { concurrency = 24 } = {}) {
  await mkdir(ogDir, { recursive: true });

  let Resvg = null;
  try {
    ({ Resvg } = await import("@resvg/resvg-js"));
  } catch {
    console.warn("[build-blog] @resvg/resvg-js not installed; writing SVG OG images only.");
  }

  const ext = Resvg ? "png" : "svg";
  const urls = new Map();
  let skipped = 0;

  async function renderOne(post) {
    const outFile = path.join(ogDir, `${post.slug}.${ext}`);
    const publicUrl = `${blogOrigin}/og/${post.slug}.${ext}`;

    if (post.sourceMtime) {
      try {
        const outStat = await stat(outFile);
        if (outStat.mtimeMs >= post.sourceMtime) {
          urls.set(post.slug, publicUrl);
          skipped++;
          return;
        }
      } catch {
        /* regenerate */
      }
    }

    const svg = buildOgSvg({ title: post.title, tags: post.tags || [] });

    if (Resvg) {
      const png = new Resvg(svg, {
        fitTo: { mode: "width", value: W },
        font: { loadSystemFonts: true, defaultFontFamily: "Inter" },
      })
        .render()
        .asPng();
      await writeFile(outFile, png);
    } else {
      await writeFile(outFile, svg);
    }
    urls.set(post.slug, publicUrl);
  }

  let done = 0;
  for (let i = 0; i < posts.length; i += concurrency) {
    const batch = posts.slice(i, i + concurrency);
    await Promise.all(batch.map(renderOne));
    done = Math.min(i + concurrency, posts.length);
    if (posts.length > 50 && done % 100 < concurrency) {
      console.log(`[build-blog] OG images: ${done}/${posts.length}${skipped ? ` (${skipped} cached)` : ""}`);
    }
  }

  if (skipped) console.log(`[build-blog] OG images: reused ${skipped} cached file(s)`);
  return urls;
}
