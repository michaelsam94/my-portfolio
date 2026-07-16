import type { Metadata } from "next";
import { portfolioFaq, profile, site, skillGroups } from "@/data/portfolio";
import { citations } from "@/data/citations";

const PERSON_ID = `${site.origin}/#person`;
const WEBSITE_ID = `${site.origin}/#website`;
const SERVICE_ID = `${site.origin}/#software-engineering-services`;
const WEBPAGE_ID = `${site.origin}/#webpage`;
const FAQ_ID = `${site.origin}/#faq`;
const SKILLS_ID = `${site.origin}/#portfolio-skills`;
const SEO_TOPICS_ID = `${site.origin}/#seo-focus-topics`;

/** Service/hiring keywords ported from the legacy Vite build so they ship in the Next static export. */
export const serviceKeywords = [
  "senior Android developer",
  "Kotlin developer",
  "Jetpack Compose developer",
  "Flutter developer",
  "React developer",
  "AI automation developer",
  "OCPP developer",
  "OCPP expert",
  "OCPP engineer",
  "OCPP consultant",
  "EV charging software engineer",
  "mobile app architect",
  "remote software engineer",
  "freelance software engineer",
  "technical lead",
  "Android tech lead",
];

/** Full keyword set for the home `<meta name="keywords">` (person + service + product intent). */
const homeKeywords = [
  "Michael Samuel Naeem",
  "Michael Sam",
  "michaelsam94",
  "michaelsam00",
  ...serviceKeywords,
  "OCPP integrator",
  "OCPP mobile developer",
  "OCPP 1.6",
  "OCPP WebSocket",
  "Open Charge Point Protocol",
  "EV charging OCPP",
  "charging station protocol",
  "Cairo software engineer",
  "Egypt Android developer",
  "ad-free Android apps",
  "no ads Android apps",
  "Play Store developer MichaelSam94",
];

const allSkills = Array.from(new Set(skillGroups.flatMap((group) => [...group.items])));

/** Only include verification tags whose env values are set, so static export never emits empty tokens. */
function buildVerification(): Metadata["verification"] | undefined {
  const google = process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION;
  const bing = process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION;
  const yandex = process.env.NEXT_PUBLIC_YANDEX_SITE_VERIFICATION;

  const other: Record<string, string> = {};
  if (bing) other["msvalidate.01"] = bing;

  const verification: NonNullable<Metadata["verification"]> = {};
  if (google) verification.google = google;
  if (yandex) verification.yandex = yandex;
  if (Object.keys(other).length) verification.other = other;

  return Object.keys(verification).length ? verification : undefined;
}

export const defaultMetadata: Metadata = {
  metadataBase: new URL(site.origin),
  title: {
    default: "Michael Sam - Senior Android Engineer",
    template: "%s | Michael Sam",
  },
  description: site.description,
  keywords: homeKeywords,
  authors: [{ name: profile.name, url: site.origin }],
  creator: profile.name,
  publisher: profile.name,
  category: "technology",
  alternates: {
    canonical: site.origin,
    types: {
      "application/rss+xml": "/blog/feed.xml",
    },
  },
  icons: {
    icon: [
    { url: "/favicon-48.png", sizes: "48x48", type: "image/png" },
      { url: "/favicon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  shortcut: ["/favicon-48.png"],
  },
  manifest: "/site.webmanifest",
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
  verification: buildVerification(),
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
        "@id": PERSON_ID,
        name: profile.name,
        givenName: "Michael Samuel",
        familyName: "Naeem",
        alternateName: ["Michael Sam", "michaelsam94", "michaelsam00", "MichaelSam94"],
        description:
          "Senior Android engineer, Flutter developer, mobile engineer, software engineer, technical lead, and mobile architect with 10+ years of experience. Based in Cairo, Egypt; open to remote roles in Europe, the United States, and worldwide.",
        url: site.origin,
        image: `${site.origin}/profile-photo.png`,
        email: `mailto:${profile.email}`,
        telephone: profile.phone,
        nationality: { "@type": "Country", name: "Egypt" },
        jobTitle: [
          "Senior Android Engineer",
          "Staff Android Engineer",
          "Mobile Architect",
          "Technical Lead",
          "Flutter Developer",
          "Software Engineer",
          "OCPP Engineer",
        ],
        hasOccupation: {
          "@type": "Occupation",
          name: "Senior Android Developer",
          description:
            "Senior Android and Flutter developer for remote roles with Kotlin, Jetpack Compose, Clean Architecture, robotics, EV infrastructure, and real-time mobile systems experience.",
        },
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
          "OCPP 1.6",
          "Open Charge Point Protocol",
          "EV charging infrastructure",
          "WebRTC",
          "Robotics",
          "Mobile architecture",
          "AI automation",
          "Real-time systems",
        ],
        sameAs: [profile.github, profile.linkedin, profile.playStoreDeveloper, profile.vscodeMarketplace, profile.openVsx],
      },
      {
        "@type": "WebSite",
        "@id": WEBSITE_ID,
        name: "Michael Sam Portfolio",
        url: site.origin,
        inLanguage: "en",
        publisher: { "@id": PERSON_ID },
      },
      {
        "@type": ["WebPage", "ProfilePage"],
        "@id": WEBPAGE_ID,
        url: site.origin,
        name: "Michael Samuel Naeem — Senior Android Engineer, Flutter Developer & Technical Lead",
        description: site.description,
        isPartOf: { "@id": WEBSITE_ID },
        about: { "@id": PERSON_ID },
        mainEntity: { "@id": PERSON_ID },
        speakable: {
          "@type": "SpeakableSpecification",
          cssSelector: [".hero-headline", "#answers-heading", "#faq-heading"],
        },
      },
      {
        "@type": "ProfessionalService",
        "@id": SERVICE_ID,
        name: "Michael Samuel Naeem software engineering services",
        url: site.origin,
        image: `${site.origin}/profile-photo.png`,
        description:
          "Senior Android, Kotlin, Jetpack Compose, Flutter, React, OCPP, and AI automation engineering for remote and contract teams, backed by 10+ years of experience, 120k+ users supported, and 99.9% uptime ownership.",
        founder: { "@id": PERSON_ID },
        employee: { "@id": PERSON_ID },
        email: `mailto:${profile.email}`,
        telephone: profile.phone,
        keywords: serviceKeywords.join(", "),
        additionalProperty: [
          { "@type": "PropertyValue", name: "Software engineering experience", value: "10+ years" },
          { "@type": "PropertyValue", name: "Engineering leadership", value: "4+ years" },
          { "@type": "PropertyValue", name: "Commerce users supported", value: "120k+" },
          { "@type": "PropertyValue", name: "Merchants enabled", value: "240+" },
          { "@type": "PropertyValue", name: "Production uptime ownership", value: "99.9%" },
          { "@type": "PropertyValue", name: "Published Android apps", value: "24 (all ad-free)" },
          { "@type": "PropertyValue", name: "Published VS Code extensions", value: "9" },
        ],
        areaServed: [
          { "@type": "Country", name: "United States" },
          { "@type": "Country", name: "Egypt" },
          { "@type": "Place", name: "Europe" },
          { "@type": "Place", name: "Remote teams worldwide" },
        ],
        serviceType: [
          "Android app development",
          "Kotlin and Jetpack Compose development",
          "Flutter cross-platform development",
          "React and TypeScript frontend development",
          "OCPP developer and EV charging software (OCPP 1.6, WebSocket)",
          "AI automation and workflow engineering",
          "Mobile technical leadership",
        ],
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: site.origin,
          servicePhone: profile.phone,
          availableLanguage: ["English", "Arabic"],
        },
        sameAs: [profile.linkedin, profile.github, profile.playStoreDeveloper],
        citation: citations.map((citation) => ({
          "@type": "CreativeWork",
          name: citation.title,
          publisher: citation.publisher,
          url: citation.url,
        })),
      },
      {
        "@type": "ItemList",
        "@id": SKILLS_ID,
        name: `${profile.name} — technical skills`,
        description:
          "Software engineering, Android, Flutter, and related tools and practices listed on this portfolio.",
        about: { "@id": PERSON_ID },
        numberOfItems: allSkills.length,
        itemListElement: allSkills.map((name, index) => ({
          "@type": "ListItem",
          position: index + 1,
          item: { "@type": "Thing", name },
        })),
      },
      {
        "@type": "ItemList",
        "@id": SEO_TOPICS_ID,
        name: "Michael Samuel Naeem SEO, GEO, and AEO focus topics",
        itemListElement: serviceKeywords.map((name, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name,
        })),
      },
      {
        "@type": "FAQPage",
        "@id": FAQ_ID,
        mainEntity: portfolioFaq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
    ],
  };
}
