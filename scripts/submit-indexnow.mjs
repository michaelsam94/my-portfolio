import { readFile } from "node:fs/promises";

// Allow deploys to opt out (e.g. preview/staging) without editing the pipeline.
if (process.env.SKIP_INDEXNOW === "1" || process.env.SKIP_INDEXNOW === "true") {
  console.log("SKIP_INDEXNOW set — skipping IndexNow submission.");
  process.exit(0);
}

const HOST = "michaelsam94.com";
const ORIGIN = `https://${HOST}`;
const KEY = "0eb1eb625c28368318e34f58bec177b0";
const KEY_LOCATION = `${ORIGIN}/${KEY}.txt`;
const ENDPOINT = "https://api.indexnow.org/indexnow";

function extractUrls(sitemap) {
  return [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
}

const sitemap = await readFile(new URL("../out/sitemap.xml", import.meta.url), "utf8");
const urlList = extractUrls(sitemap).filter((url) => url.startsWith(ORIGIN));

if (urlList.length === 0) {
  throw new Error("No canonical URLs found in out/sitemap.xml");
}

const response = await fetch(ENDPOINT, {
  method: "POST",
  headers: { "content-type": "application/json; charset=utf-8" },
  body: JSON.stringify({
    host: HOST,
    key: KEY,
    keyLocation: KEY_LOCATION,
    urlList,
  }),
});

if (!response.ok) {
  const body = await response.text();
  throw new Error(`IndexNow submission failed: ${response.status} ${body}`);
}

console.log(`Submitted ${urlList.length} URL(s) to IndexNow for ${HOST}.`);
