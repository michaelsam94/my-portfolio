import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

export type CatalogItem = {
  title: string;
  slug: string;
  category: string;
  description: string;
  image?: string;
  packageId?: string;
  playStoreUrl?: string;
  marketplaceUrl?: string;
  openVsxUrl?: string;
  githubUrl?: string;
  body: string;
};

const contentRoot = path.join(process.cwd(), "content");

async function readCatalog(collection: "apps" | "extensions", fallbackCategory: string): Promise<CatalogItem[]> {
  const fullDir = path.join(contentRoot, collection);
  const files = (await readdir(fullDir)).filter((file) => file.endsWith(".md")).sort();

  return Promise.all(
    files.map(async (file) => {
      const markdown = await readFile(path.join(fullDir, file), "utf8");
      const parsed = matter(markdown);
      const data = parsed.data as Record<string, string | undefined>;
      const slug = data.slug ?? file.replace(/\.md$/, "");
      const title =
        data.title ??
        slug
          .split("-")
          .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
          .join(" ");

      return {
        title,
        slug,
        category: data.category ?? fallbackCategory,
        description: data.description ?? parsed.content.replace(/\s+/g, " ").trim().slice(0, 180),
        image: data.image,
        packageId: data.packageId,
        playStoreUrl: data.playStoreUrl,
        marketplaceUrl: data.marketplaceUrl,
        openVsxUrl: data.openVsxUrl,
        githubUrl: data.githubUrl,
        body: parsed.content,
      };
    }),
  );
}

export async function getAppBySlug(slug: string) {
  const apps = await getAppCatalog();
  return apps.find((item) => item.slug === slug);
}

export async function getExtensionBySlug(slug: string) {
  const extensions = await getExtensionCatalog();
  return extensions.find((item) => item.slug === slug);
}

export async function getAppCatalog() {
  return readCatalog("apps", "Android");
}

export async function getExtensionCatalog() {
  return readCatalog("extensions", "VS Code");
}
