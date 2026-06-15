import { readFile } from "node:fs/promises";

const TARGET_MIN = 70;
const TARGET_MAX = 180;

const files = [
  "src/components/SeoAnswerHub.tsx",
  "src/components/ConversationalGuide.tsx",
  "src/components/SeoKnowledgeGraph.tsx",
  "public/llms.txt",
  "public/llms-full.txt",
];

const stringPattern =
  /"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)'|`([^`\\]*(?:\\.[^`\\]*)*)`/g;

function unescapeLiteral(value) {
  return value.replace(/\\n/g, " ").replace(/\\"/g, '"').replace(/\\'/g, "'");
}

function shouldCheck(value) {
  if (value.endsWith("?")) return false;
  if (value.length < TARGET_MIN) return false;

  return (
    /[A-Za-z]/.test(value) &&
    !value.startsWith("http") &&
    !value.includes("schema.org") &&
    value.split(/\s+/).length >= 8
  );
}

let checked = 0;
let outside = 0;

for (const file of files) {
  const source = await readFile(file, "utf8");
  const matches = [...source.matchAll(stringPattern)];

  for (const match of matches) {
    const phrase = unescapeLiteral(match[1] ?? match[2] ?? match[3] ?? "").trim();
    if (!shouldCheck(phrase)) continue;

    checked += 1;
    const length = phrase.length;
    if (length < TARGET_MIN || length > TARGET_MAX) {
      outside += 1;
      console.log(`${file}: ${length} chars`);
      console.log(`  ${phrase}`);
    }
  }
}

if (outside > 0) {
  console.log(`Checked ${checked} phrases; ${outside} outside ${TARGET_MIN}-${TARGET_MAX} chars.`);
  process.exitCode = 1;
} else {
  console.log(`Checked ${checked} phrases; all are ${TARGET_MIN}-${TARGET_MAX} chars.`);
}
