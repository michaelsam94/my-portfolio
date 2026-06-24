import type { CatalogItem } from "@/lib/content";

type ProductCatalogProps = {
  items: CatalogItem[];
  kind: "apps" | "vscode";
};

export default function ProductCatalog({ items, kind }: ProductCatalogProps) {
  const base = kind === "apps" ? "/apps" : "/vscode";
  const label = kind === "apps" ? "Published Android apps" : "VS Code extensions";

  return (
    <div className="catalog-wrap" aria-label={label}>
      {items.map((item) => (
        <a key={item.slug} className="catalog-card" href={`${base}/${item.slug}/`}>
          <span className="catalog-mark" aria-hidden="true">
            {kind === "apps" ? item.title.slice(0, 2).toUpperCase() : "&lt;/&gt;"}
          </span>
          <span className="project-meta">{item.category}</span>
          <h3>{item.title}</h3>
          <p>{item.description}</p>
          <span className="catalog-id">{item.packageId ?? item.slug}</span>
        </a>
      ))}
    </div>
  );
}
