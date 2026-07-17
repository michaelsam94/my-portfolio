import { readFile, writeFile, mkdir, rm } from "node:fs/promises";

const OUT = "/tmp/blogbatches";
await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });

const raw = await readFile("/tmp/master_topics.tsv", "utf8");
const rows = raw.trim().split("\n").map((l) => {
  const [slug, title, cat] = l.split("\t");
  return { slug, title, cat };
});

const BATCH = 20;
const batches = [];
for (let i = 0; i < rows.length; i += BATCH) batches.push(rows.slice(i, i + BATCH));

// Spread batch start dates across 2024-06-01 .. 2026-06-15 so posts look
// organically published over time; every post stays <= 2026-07-16 (today).
const START = new Date("2024-06-01").getTime();
const END = new Date("2026-06-15").getTime();
const step = (END - START) / Math.max(1, batches.length - 1);

const manifest = [];
batches.forEach((b, idx) => {
  const n = String(idx + 1).padStart(2, "0");
  const startDate = new Date(START + step * idx).toISOString().slice(0, 10);
  const lines = b.map((r) => `${r.slug}\t${r.title}\t${r.cat}`).join("\n");
  writeFile(`${OUT}/batch_${n}.tsv`, lines + "\n");
  manifest.push({ batch: n, startDate, count: b.length });
});

await writeFile(`${OUT}/manifest.json`, JSON.stringify(manifest, null, 2));
console.log(`Wrote ${batches.length} batches, ${rows.length} topics total.`);
console.log(manifest.map((m) => `batch_${m.batch}: ${m.count} posts, start ${m.startDate}`).join("\n"));
