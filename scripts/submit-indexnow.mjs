import { readFile } from "node:fs/promises";

// Allow deploys to opt out (e.g. preview/staging) without editing the pipeline.
if (process.env.SKIP_INDEXNOW === "1" || process.env.SKIP_INDEXNOW === "true") {
  console.log("SKIP_INDEXNOW set — skipping IndexNow submission.");
  process.exit(0);
}

const APEX_HOST = "michaelsam94.com";
const BLOG_HOST = "blog.michaelsam94.com";
const APEX_ORIGIN = `https://${APEX_HOST}`;
const BLOG_ORIGIN = `https://${BLOG_HOST}`;
const KEY = "0eb1eb625c28368318e34f58bec177b0";
const ENDPOINT = "https://api.indexnow.org/indexnow";

function extractUrls(sitemap) {
  return [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
}

async function submitHost(host, origin, urlList) {
  if (urlList.length === 0) return 0;

  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      host,
      key: KEY,
      keyLocation: `${origin}/${KEY}.txt`,
      urlList,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`IndexNow submission failed for ${host}: ${response.status} ${body}`);
  }

  console.log(`Submitted ${urlList.length} URL(s) to IndexNow for ${host}.`);
  return urlList.length;
}

const sitemap = await readFile(new URL("../out/sitemap.xml", import.meta.url), "utf8");
const allUrls = extractUrls(sitemap);
const apexUrls = allUrls.filter((url) => url.startsWith(APEX_ORIGIN));
const blogUrls = allUrls.filter((url) => url.startsWith(BLOG_ORIGIN));

if (apexUrls.length === 0 && blogUrls.length === 0) {
  throw new Error("No canonical URLs found in out/sitemap.xml");
}

await submitHost(APEX_HOST, APEX_ORIGIN, apexUrls);
await submitHost(BLOG_HOST, BLOG_ORIGIN, blogUrls);
