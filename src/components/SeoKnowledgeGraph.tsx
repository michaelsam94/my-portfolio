import { portfolioFaq, profile } from "../data/portfolio";

const SITE_ORIGIN = "https://michaelsam94.tech";
const PERSON_ID = `${SITE_ORIGIN}/#person`;
const SERVICE_ID = `${SITE_ORIGIN}/#software-engineering-services`;
const FAQ_ID = `${SITE_ORIGIN}/#portfolio-faq`;

const serviceKeywords = [
  "senior Android developer",
  "Kotlin developer",
  "Jetpack Compose developer",
  "React developer",
  "AI automation developer",
  "OCPP developer",
  "mobile app architect",
  "remote software engineer",
  "freelance software engineer",
  "technical lead",
];

export default function SeoKnowledgeGraph() {
  const graph = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "ProfessionalService",
        "@id": SERVICE_ID,
        name: "Michael Samuel Naeem software engineering services",
        url: SITE_ORIGIN,
        image: `${SITE_ORIGIN}/profile-photo.png`,
        description:
          "Senior Android, Kotlin, Jetpack Compose, React, OCPP, and AI automation engineering for product teams hiring remote or contract software development help.",
        founder: { "@id": PERSON_ID },
        employee: { "@id": PERSON_ID },
        keywords: serviceKeywords.join(", "),
        areaServed: [
          { "@type": "Country", name: "United States" },
          { "@type": "Country", name: "Egypt" },
          { "@type": "Place", name: "Europe" },
          { "@type": "Place", name: "Remote teams worldwide" },
        ],
        serviceType: [
          "Android app development",
          "Kotlin and Jetpack Compose development",
          "React and TypeScript frontend development",
          "OCPP and EV charging software",
          "AI automation and workflow engineering",
          "Mobile technical leadership",
        ],
        availableChannel: {
          "@type": "ServiceChannel",
          serviceUrl: SITE_ORIGIN,
          servicePhone: profile.phone,
          serviceSmsNumber: profile.phone,
          availableLanguage: ["English", "Arabic"],
        },
        email: profile.email,
        sameAs: [profile.linkedin, profile.github, profile.playStoreDeveloper],
      },
      {
        "@type": "FAQPage",
        "@id": FAQ_ID,
        mainEntity: portfolioFaq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: item.answer,
          },
        })),
      },
      {
        "@type": "ItemList",
        "@id": `${SITE_ORIGIN}/#seo-focus-topics`,
        name: "Michael Samuel Naeem SEO, GEO, and AEO focus topics",
        itemListElement: serviceKeywords.map((name, index) => ({
          "@type": "ListItem",
          position: index + 1,
          name,
        })),
      },
    ],
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(graph) }}
    />
  );
}
