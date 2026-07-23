import type { CatalogItem } from "@/lib/content";
import CatalogArtwork from "./CatalogArtwork";

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
        <article key={item.slug} className="catalog-card">
          <CatalogArtwork title={item.title} image={item.image} kind={kind} />
          <span className="project-meta">{item.category}</span>
<div className="catalog-title">{item.title}</div>
<p>{item.description}</p>
<span className="catalog-id">{item.packageId ?? item.slug}</span>
<div className="catalog-actions" aria-label={`${item.title} links`}>
<a href={`${base}/${item.slug}/`}>
  Explore {item.title} — {item.category} {kind === "apps" ? "Android app" : "VS Code extension"}
</a>
</div>
        </article>
      ))}
    </div>
  );
}
