import { portfolioFaq, profile } from "../data/portfolio";
import { citations } from "../data/citations";

const SITE_ORIGIN = "https://michaelsam94.tech";
const PERSON_ID = `${SITE_ORIGIN}/#person`;
const SERVICE_ID = `${SITE_ORIGIN}/#software-engineering-services`;
const FAQ_ID = `${SITE_ORIGIN}/#portfolio-faq`;
const BIBLIOGRAPHY_ID = `${SITE_ORIGIN}/#bibliography`;

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

const conversationalQuestions = [
  {
    question: "Can you help my team ship a reliable Android app?",
    answer:
      "Yes. I build Android apps with Kotlin and Jetpack Compose, and I focus on clean architecture, fast screens, fewer crashes, predictable releases, and code that other engineers can keep improving.",
  },
  {
    question: "What should we send first?",
    answer:
      "Send the product goal, current tech stack, timeline, users affected, and anything that shows the problem clearly, such as screenshots, crash logs, store reviews, or a short recording.",
  },
  {
    question: "How do we start working together?",
    answer:
      "We can start with a focused audit, a small build, a rescue sprint, or a technical advisory call. If the fit is good, we can expand from there.",
  },
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
          "Senior Android, Kotlin, Jetpack Compose, React, OCPP, and AI automation engineering for product teams hiring remote or contract software development help, backed by 10+ years of experience, 120k+ users supported, and 99.9% uptime ownership.",
        founder: { "@id": PERSON_ID },
        employee: { "@id": PERSON_ID },
        keywords: serviceKeywords.join(", "),
        additionalProperty: [
          { "@type": "PropertyValue", name: "Software engineering experience", value: "10+ years" },
          { "@type": "PropertyValue", name: "Engineering leadership", value: "4+ years" },
          { "@type": "PropertyValue", name: "Commerce users supported", value: "120k+" },
          { "@type": "PropertyValue", name: "Merchants enabled", value: "240+" },
          { "@type": "PropertyValue", name: "Production uptime ownership", value: "99.9%" },
          { "@type": "PropertyValue", name: "Store operations improvement", value: "70% faster" },
          { "@type": "PropertyValue", name: "Vendor onboarding improvement", value: "50% faster" },
          { "@type": "PropertyValue", name: "API response improvement", value: "20% faster" },
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
        citation: citations.map((citation) => ({
          "@type": "CreativeWork",
          name: citation.title,
          publisher: citation.publisher,
          url: citation.url,
        })),
      },
      {
        "@type": "FAQPage",
        "@id": FAQ_ID,
        mainEntity: [...portfolioFaq, ...conversationalQuestions].map((item) => ({
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
      {
        "@type": "CreativeWork",
        "@id": BIBLIOGRAPHY_ID,
        name: "Michael Samuel Naeem portfolio bibliography",
        url: `${SITE_ORIGIN}/#citations`,
        citation: citations.map((citation) => ({
          "@type": "CreativeWork",
          name: citation.title,
          publisher: citation.publisher,
          url: citation.url,
          description: citation.supports,
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
