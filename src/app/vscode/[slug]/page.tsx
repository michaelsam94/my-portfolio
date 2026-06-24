import { notFound } from "next/navigation";
import Link from "next/link";
import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import SectionWrapper from "@/components/SectionWrapper";
import { getExtensionBySlug, getExtensionCatalog } from "@/lib/content";
import { renderMarkdown } from "@/lib/markdown";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateStaticParams() {
  const extensions = await getExtensionCatalog();
  return extensions.map((extension) => ({ slug: extension.slug }));
}

export async function generateMetadata({ params }: PageProps) {
  const { slug } = await params;
  const extension = await getExtensionBySlug(slug);
  if (!extension) return {};
  return {
    title: extension.title,
    description: extension.description,
  };
}

export default async function ExtensionDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const [extension, extensions] = await Promise.all([getExtensionBySlug(slug), getExtensionCatalog()]);
  if (!extension) notFound();

  return (
    <main id="main-content" className="page-main">
      <article className="detail-article">
        <Link className="text-link" href="/#vscode">Back to portfolio</Link>
        <p className="hero-kicker">VS Code / {extension.slug}</p>
        <h1 className="detail-title">{extension.title}</h1>
        <p className="hero-headline">{extension.description}</p>
        <div className="card-links">
          {extension.marketplaceUrl ? <a className="text-link" href={extension.marketplaceUrl} target="_blank" rel="noopener noreferrer">Marketplace</a> : null}
          {extension.openVsxUrl ? <a className="text-link" href={extension.openVsxUrl} target="_blank" rel="noopener noreferrer">Open VSX</a> : null}
          {extension.githubUrl ? <a className="text-link" href={extension.githubUrl} target="_blank" rel="noopener noreferrer">GitHub</a> : null}
        </div>
        <div className="markdown-body">{renderMarkdown(extension.body)}</div>
      </article>
      <SectionWrapper id="more-extensions" heading="More VS Code Extensions" headingId="more-extensions-heading">
        <ProductCatalog items={extensions.filter((item) => item.slug !== extension.slug).slice(0, 8)} kind="vscode" />
      </SectionWrapper>
    </main>
  );
}
