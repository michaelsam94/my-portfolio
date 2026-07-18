/**
 * Generate share-ready LinkedIn post copy for every blog article.
 * Output is JSON for manual posting — no LinkedIn API calls.
 */
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { primaryCluster } from "./blog-og-images.mjs";

const HASHTAG_MAP = {
  android: ["Android", "Kotlin", "MobileDevelopment"],
  kotlin: ["Kotlin", "Coroutines", "AndroidDev"],
  flutter: ["Flutter", "Dart", "MobileDevelopment"],
  mobile: ["MobileDevelopment", "SoftwareEngineering"],
  ai: ["AI", "LLM", "MachineLearning"],
  backend: ["Backend", "SoftwareArchitecture", "API"],
  infra: ["DevOps", "CloudComputing", "PlatformEngineering"],
  web: ["WebDevelopment", "Frontend", "JavaScript"],
  security: ["CyberSecurity", "AppSecurity"],
  iot: ["IoT", "EdgeComputing", "Embedded"],
  data: ["DataEngineering", "Database"],
  testing: ["SoftwareTesting", "QualityEngineering"],
  default: ["SoftwareEngineering", "Tech"],
};

/** Pick 3–5 LinkedIn hashtags from post tags and topic cluster. */
function hashtagsFor(post) {
  const cluster = primaryCluster(post.tags || []);
  const base = HASHTAG_MAP[cluster.key] || HASHTAG_MAP.default;
  const fromTags = (post.tags || [])
    .slice(0, 3)
    .map((t) => t.replace(/[^a-zA-Z0-9]/g, ""))
    .filter((t) => t.length > 2);
  const merged = [...new Set([...fromTags, ...base])].slice(0, 5);
  return merged.map((h) => `#${h}`);
}

/** Pull bullet hooks from FAQ or description. */
function bulletHooks(post) {
  if (post.faq?.length) {
    return post.faq.slice(0, 3).map((f) => f.q.replace(/\?$/, ""));
  }
  const tags = (post.tags || []).slice(0, 4);
  if (tags.length >= 2) return tags.map((t) => `Deep dive on ${t}`);
  return [];
}

/** Compose LinkedIn post text for one article. */
export function buildLinkedInPost(post, blogOrigin) {
  const url = `${blogOrigin}/${post.slug}/`;
  const desc = (post.description || "").trim();
  const bullets = bulletHooks(post);
  const tags = hashtagsFor(post);

  const lines = [desc, ""];

  if (bullets.length) {
    lines.push("What I cover:");
    for (const b of bullets) lines.push(`→ ${b}`);
    lines.push("");
  }

  lines.push("Read the full article:", url, "", tags.join(" "));

  return {
    slug: post.slug,
    title: post.title,
    url,
    text: lines.join("\n"),
    hashtags: tags,
    datePublished: post.datePublished,
    topicCluster: primaryCluster(post.tags || []).key,
  };
}

/** Build the full export object for all posts. */
export function buildLinkedInPosts(posts, blogOrigin) {
  return {
    generatedAt: new Date().toISOString(),
    blogOrigin,
    posts: posts.map((p) => buildLinkedInPost(p, blogOrigin)),
  };
}

/** Write linkedin-posts.json to the blog output directory. */
export async function writeLinkedInPosts(posts, blogDist, blogOrigin) {
  await mkdir(blogDist, { recursive: true });
  const data = buildLinkedInPosts(posts, blogOrigin);
  const outPath = path.join(blogDist, "linkedin-posts.json");
  await writeFile(outPath, JSON.stringify(data, null, 2) + "\n");
  return outPath;
}

/** LinkedIn share-offsite URL (opens LinkedIn share dialog with article URL). */
export function linkedInShareUrl(articleUrl) {
  return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(articleUrl)}`;
}

/** X (Twitter) intent URL with article title + link. */
export function xShareUrl(articleUrl, text = "") {
  const params = new URLSearchParams({ url: articleUrl });
  if (text) params.set("text", text);
  return `https://twitter.com/intent/tweet?${params.toString()}`;
}

/** Reddit submit intent. */
export function redditShareUrl(articleUrl, title = "") {
  const params = new URLSearchParams({ url: articleUrl });
  if (title) params.set("title", title);
  return `https://www.reddit.com/submit?${params.toString()}`;
}

/** Hacker News submit-link intent. */
export function hackerNewsShareUrl(articleUrl, title = "") {
  const params = new URLSearchParams({ u: articleUrl });
  if (title) params.set("t", title);
  return `https://news.ycombinator.com/submitlink?${params.toString()}`;
}

/** Bluesky compose intent (URL + title in the post body). */
export function blueskyShareUrl(articleUrl, title = "") {
  const text = title ? `${title}\n\n${articleUrl}` : articleUrl;
  return `https://bsky.app/intent/compose?text=${encodeURIComponent(text)}`;
}
