import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import SectionWrapper from "@/components/SectionWrapper";
import { getExtensionCatalog } from "@/lib/content";

export const metadata = {
  title: "VS Code Extensions",
  description: "VS Code extensions by Michael Samuel Naeem for CSV, PDF, DOCX, Markdown, and AI context workflows.",
};

export default async function VscodePage() {
  const extensions = await getExtensionCatalog();

  return (
    <main id="main-content" className="page-main">
      <section className="detail-hero">
        <p className="hero-kicker">MichaelSam94 / Developer Tools</p>
        <h1 className="detail-title">VS Code Extensions</h1>
        <p className="hero-headline">Document and workspace tools for files engineers actually touch: CSV, PDF, DOCX, Markdown, exports, conversions, and context handoff.</p>
      </section>
      <SectionWrapper id="vscode" heading={`VS Code Extensions (${extensions.length})`} headingId="vscode-heading">
        <ProductCatalog items={extensions} kind="vscode" />
      </SectionWrapper>
    </main>
  );
}
