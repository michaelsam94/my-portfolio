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
        <article key={item.slug} className="catalog-card">
          <span className="catalog-mark" aria-hidden="true">
            {kind === "apps" ? item.title.slice(0, 2).toUpperCase() : "&lt;/&gt;"}
          </span>
          <span className="project-meta">{item.category}</span>
          <h3>
            <a href={`${base}/${item.slug}/`}>{item.title}</a>
          </h3>
          <p>{item.description}</p>
          <span className="catalog-id">{item.packageId ?? item.slug}</span>
          <div className="catalog-actions" aria-label={`${item.title} links`}>
            <a href={`${base}/${item.slug}/`}>Details</a>
            {item.playStoreUrl ? (
              <a href={item.playStoreUrl} target="_blank" rel="noopener noreferrer">
                Google Play
              </a>
            ) : null}
            {item.marketplaceUrl ? (
              <a href={item.marketplaceUrl} target="_blank" rel="noopener noreferrer">
                VS Marketplace
              </a>
            ) : null}
            {item.openVsxUrl ? (
              <a href={item.openVsxUrl} target="_blank" rel="noopener noreferrer">
                Open VSX
              </a>
            ) : null}
            {item.githubUrl ? (
              <a href={item.githubUrl} target="_blank" rel="noopener noreferrer">
                GitHub
              </a>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
