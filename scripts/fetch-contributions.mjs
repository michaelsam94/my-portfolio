/**
 * One-off generator (run manually, then commit the output).
 *
 *   node scripts/fetch-contributions.mjs
 *
 * Bakes the full GitHub contribution history (from account creation to now) into
 * `public/contributions.json`. The OpenSource component uses this as a reliable
 * fallback when the live Netlify function is unavailable or rate-limited — so the
 * contribution graph always shows the complete history, not just recent events.
 *
 * Re-run periodically to refresh, then commit the regenerated JSON.
 */
import { handler } from "../netlify/functions/github-contributions.js";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const USERNAME = "michaelsam94";

const res = await handler({ httpMethod: "GET", queryStringParameters: { username: USERNAME } });
if (res.statusCode !== 200) {
  console.error(`[fetch-contributions] failed: ${res.statusCode} ${res.body}`);
  process.exit(1);
}

const body = JSON.parse(res.body);
const out = {
  accountCreatedAt: body.accountCreatedAt,
  totalContributions: body.totalContributions,
  contributionDays: body.contributionDays,
  source: "static-snapshot",
  generatedAt: new Date().toISOString(),
};

await writeFile(path.join(ROOT, "public/contributions.json"), `${JSON.stringify(out)}\n`);
console.log(
  `[fetch-contributions] Wrote public/contributions.json — ${out.contributionDays.length} days, ${out.totalContributions} contributions, since ${out.accountCreatedAt?.slice(0, 10)}`,
);
