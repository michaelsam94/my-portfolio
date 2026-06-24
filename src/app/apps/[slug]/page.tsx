import { notFound } from "next/navigation";
import Link from "next/link";
import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import CatalogArtwork from "@/components/section-catalog/CatalogArtwork";
import SectionWrapper from "@/components/SectionWrapper";
import { getAppBySlug, getAppCatalog } from "@/lib/content";
import { renderMarkdown } from "@/lib/markdown";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateStaticParams() {
  const apps = await getAppCatalog();
  return apps.map((app) => ({ slug: app.slug }));
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const app = await getAppBySlug(slug);
  if (!app) return {};
  return {
    title: app.title,
    description: app.description,
  };
}

export default async function AppDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const [app, apps] = await Promise.all([getAppBySlug(slug), getAppCatalog()]);
  if (!app) notFound();

  return (
    <main id="main-content" className="page-main">
        <article className="detail-article">
        <Link className="text-link" href="/#apps">Back to portfolio</Link>
        <p className="hero-kicker">{app.category} / {app.packageId}</p>
        <CatalogArtwork title={app.title} image={app.image} kind="apps" variant="detail" />
        <h1 className="detail-title">{app.title}</h1>
        <p className="hero-headline">{app.description}</p>
        <div className="card-links">
          {app.playStoreUrl ? <a className="text-link" href={app.playStoreUrl} target="_blank" rel="noopener noreferrer">Google Play</a> : null}
          {app.githubUrl ? <a className="text-link" href={app.githubUrl} target="_blank" rel="noopener noreferrer">GitHub</a> : null}
        </div>
        <div className="markdown-body">{renderMarkdown(app.body)}</div>
      </article>
      <SectionWrapper id="more-apps" heading="More Android Apps" headingId="more-apps-heading">
        <ProductCatalog items={apps.filter((item) => item.slug !== app.slug).slice(0, 8)} kind="apps" />
      </SectionWrapper>
    </main>
  );
}
