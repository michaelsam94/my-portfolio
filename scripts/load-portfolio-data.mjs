import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import ts from "typescript";

const portfolioPath = path.resolve("src/data/portfolio.ts");

export async function loadPortfolioData() {
  const source = await readFile(portfolioPath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
    fileName: portfolioPath,
  }).outputText;

  const dir = await mkdtemp(path.join(tmpdir(), "portfolio-data-"));
  const file = path.join(dir, "portfolio.mjs");
  await writeFile(file, compiled);

  try {
    return await import(`${file}?t=${Date.now()}`);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
