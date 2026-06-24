import { access, readFile, stat } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  "next.config.mjs",
  "src/app/layout.tsx",
  "src/app/page.tsx",
  "src/app/globals.css",
  "src/components/hero/HeroGrid.tsx",
  "src/components/projects/ProjectGrid.tsx",
  "src/components/work/Timeline.tsx",
  "src/data/portfolio.ts",
  "src/lib/metadata.ts",
];

async function mustExist(file) {
  const fullPath = path.join(root, file);
  await access(fullPath);
  return fullPath;
}

async function readRequired(file) {
  return readFile(await mustExist(file), "utf8");
}

async function verify() {
  await Promise.all(requiredFiles.map(mustExist));

  const nextConfig = await readRequired("next.config.mjs");
  if (!nextConfig.includes("output: 'export'") && !nextConfig.includes('output: "export"')) {
    throw new Error("next.config.mjs must enable static export output.");
  }

  const css = await readRequired("src/app/globals.css");
  for (const token of ["--bg:", "--fg:", "--border-strong:", "--shadow-card:"]) {
    if (!css.includes(token)) {
      throw new Error(`Missing design token ${token} in globals.css.`);
    }
  }

  const page = await readRequired("src/app/page.tsx");
  for (const section of ["projects", "experience", "contact"]) {
    if (!page.includes(`id="${section}"`) && !page.includes(`id={${JSON.stringify(section)}}`)) {
      throw new Error(`Home page must include navigable #${section} section.`);
    }
  }

  const outDir = path.join(root, "out");
  const outStats = await stat(outDir).catch(() => null);
  if (outStats && !outStats.isDirectory()) {
    throw new Error("Static export target `out` exists but is not a directory.");
  }
}

verify()
  .then(() => {
    console.log("Static-site structure verified.");
  })
  .catch((error) => {
    console.error(error.message);
    process.exit(1);
  });
