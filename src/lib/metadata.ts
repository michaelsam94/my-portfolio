import type { Metadata } from "next";
import { portfolioFaq, profile, site } from "@/data/portfolio";

export const defaultMetadata: Metadata = {
  metadataBase: new URL(site.origin),
  title: {
    default: "Michael Sam - Senior Android Engineer",
    template: "%s | Michael Sam",
  },
  description: site.description,
  authors: [{ name: profile.name, url: site.origin }],
  creator: profile.name,
  publisher: profile.name,
  alternates: {
    canonical: site.origin,
    types: {
      "application/rss+xml": "/blog/feed.xml",
    },
  },
  openGraph: {
    title: "Michael Sam - Senior Android Engineer",
    description: site.description,
    url: site.origin,
    siteName: "Michael Sam",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Michael Sam - Senior Android Engineer" }],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    creator: "@michaelsam94",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
};

export function structuredData() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Person",
        "@id": `${site.origin}/#person`,
        name: profile.name,
        alternateName: ["Michael Sam", "michaelsam94", "michaelsam00", "MichaelSam94"],
        url: site.origin,
        image: `${site.origin}/profile-photo.png`,
        email: `mailto:${profile.email}`,
        telephone: profile.phone,
        jobTitle: ["Senior Android Engineer", "Mobile Architect", "Technical Lead", "Flutter Developer"],
        address: {
          "@type": "PostalAddress",
          addressLocality: "Cairo",
          addressCountry: "EG",
        },
        knowsAbout: [
          "Android development",
          "Kotlin",
          "Jetpack Compose",
          "Flutter",
          "OCPP",
          "WebRTC",
          "Robotics",
          "Mobile architecture",
        ],
        sameAs: [profile.github, profile.linkedin, profile.playStoreDeveloper, profile.vscodeMarketplace, profile.openVsx],
      },
      {
        "@type": "WebSite",
        "@id": `${site.origin}/#website`,
        name: "Michael Sam Portfolio",
        url: site.origin,
        publisher: { "@id": `${site.origin}/#person` },
      },
      {
        "@type": "FAQPage",
        "@id": `${site.origin}/#faq`,
        mainEntity: portfolioFaq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
    ],
  };
}
