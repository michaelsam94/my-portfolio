import type { Metadata } from "next";
import ProductCatalog from "@/components/section-catalog/ProductCatalog";
import SectionWrapper from "@/components/SectionWrapper";
import { getAppCatalog } from "@/lib/content";
import { absoluteUrl } from "@/config/site";
import { site } from "@/data/portfolio";

const hubTitle = "Ad-Free Android Apps by Michael Samuel Naeem";
const hubDescription =
  "Browse completely ad-free Android apps by MichaelSam94 — PDF tools, photo optimizers, finance trackers, privacy utilities, scanners, and developer tools with no ads and no sponsored clutter.";

export const metadata: Metadata = {
  title: { absolute: hubTitle },
  description: hubDescription,
  keywords: [
    "ad-free Android apps",
    "no ads Android apps",
    "MichaelSam94 apps",
    "privacy Android utilities",
    "free Android tools without ads",
    "ad free PDF tools",
    "ad free expense tracker",
  ],
  alternates: { canonical: absoluteUrl("/apps/") },
  openGraph: {
    title: hubTitle,
    description: hubDescription,
    url: absoluteUrl("/apps/"),
    siteName: site.shortName,
    locale: "en_US",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: hubTitle }],
  },
  twitter: {
    card: "summary_large_image",
    title: hubTitle,
    description: hubDescription,
    creator: "@michaelsam94",
  },
};

export default async function AppsPage() {
  const apps = await getAppCatalog();
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "CollectionPage",
        "@id": `${absoluteUrl("/apps/")}#collection`,
        name: hubTitle,
        description: hubDescription,
        url: absoluteUrl("/apps/"),
        isPartOf: { "@id": `${site.origin}/#website` },
        about: "Ad-free Android applications published by Michael Samuel Naeem",
        author: { "@type": "Person", name: site.name, url: site.origin },
      },
      {
        "@type": "ItemList",
        "@id": `${absoluteUrl("/apps/")}#item-list`,
        name: "Ad-free Android apps",
        numberOfItems: apps.length,
        itemListElement: apps.map((app, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name: app.title,
          url: absoluteUrl(`/apps/${app.slug}/`),
          description: `${app.description} Completely ad-free.`,
        })),
      },
      {
        "@type": "FAQPage",
        "@id": `${absoluteUrl("/apps/")}#faq`,
        mainEntity: [
          {
            "@type": "Question",
            name: "Are MichaelSam94 Android apps ad-free?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Yes. Every Android app in this catalog is completely ad-free — no banner ads, interstitial ads, video ads, or sponsored clutter.",
            },
          },
          {
            "@type": "Question",
            name: "Where can I download these ad-free Android apps?",
            acceptedAnswer: {
              "@type": "Answer",
              text: "Each app page links to its Google Play listing under the MichaelSam94 developer account, plus GitHub when source is public.",
            },
          },
        ],
      },
    ],
  };

  return (
    <main id="main-content" className="page-main">
      <section className="detail-hero">
        <p className="hero-kicker">MichaelSam94 / Google Play / Ad-free</p>
        <h1 className="detail-title">Ad-Free Android Apps</h1>
        <p className="hero-headline">{hubDescription}</p>
        <p className="app-adfree-badge">
          Completely ad-free catalog — no ads, no trackers, no sponsored clutter across every listed app.
        </p>
      </section>
      <SectionWrapper
        id="apps"
        heading={`Published Ad-Free Android Apps (${apps.length})`}
        headingId="apps-heading"
      >
        <ProductCatalog items={apps} kind="apps" />
      </SectionWrapper>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    </main>
  );
}
