import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import SectionWrapper from "@/components/SectionWrapper";
import { getAppCatalog } from "@/lib/content";

export const metadata = {
  title: "Android Apps",
  description: "Published Android apps by Michael Samuel Naeem under MichaelSam94 on Google Play.",
};

export default async function AppsPage() {
  const apps = await getAppCatalog();

  return (
    <main id="main-content" className="page-main">
      <section className="detail-hero">
        <p className="hero-kicker">MichaelSam94 / Google Play</p>
        <h1 className="detail-title">Android Apps</h1>
        <p className="hero-headline">A crawlable catalog of published Android tools across privacy, productivity, finance, scanners, utilities, and developer workflows.</p>
      </section>
      <SectionWrapper id="apps" heading={`Published Android Apps (${apps.length})`} headingId="apps-heading">
        <ProductCatalog items={apps} kind="apps" />
      </SectionWrapper>
    </main>
  );
}
