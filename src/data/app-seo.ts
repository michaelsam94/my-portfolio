import type { Metadata } from "next";
import appSeoJson from "@/data/app-seo.json";
import { site } from "@/data/portfolio";
import { absoluteUrl } from "@/config/site";

export type AppFaq = {
  question: string;
  answer: string;
};

export type AppHowToStep = {
  name: string;
  text: string;
};

export type AppHowTo = {
  name: string;
  description: string;
  steps: AppHowToStep[];
};

export type AppSeoEntry = {
  seoTitle: string;
  seoDescription: string;
  searchHeading?: string;
  primaryKeyword: string;
  keywords: string[];
  answerFirst: string;
  applicationCategory: string;
  featureHighlights: string[];
  faqs: AppFaq[];
  howTo?: AppHowTo;
};

type AppSeoFile = {
  adFreeTagline: string;
  apps: Record<string, AppSeoEntry>;
};

const catalog = appSeoJson as AppSeoFile;

export const AD_FREE_TAGLINE = catalog.adFreeTagline;

export function getAppSeo(slug: string): AppSeoEntry | undefined {
  return catalog.apps[slug];
}

export function getAllAppSeoSlugs(): string[] {
  return Object.keys(catalog.apps);
}

const ANDROID_APP_CATEGORY_FALLBACK: Record<string, string> = {
  AI: "UtilitiesApplication",
  Audio: "MultimediaApplication",
  Developer: "DeveloperApplication",
  Document: "UtilitiesApplication",
  Finance: "FinanceApplication",
  Game: "GameApplication",
  Health: "HealthApplication",
  Media: "MultimediaApplication",
  Productivity: "ProductivityApplication",
  Scanner: "UtilitiesApplication",
  Utility: "UtilitiesApplication",
};

export function resolveApplicationCategory(slug: string, fallbackCategory?: string): string {
  const seo = getAppSeo(slug);
  if (seo?.applicationCategory) return seo.applicationCategory;
  if (fallbackCategory && ANDROID_APP_CATEGORY_FALLBACK[fallbackCategory]) {
    return ANDROID_APP_CATEGORY_FALLBACK[fallbackCategory];
  }
  return "UtilitiesApplication";
}

export function buildAndroidAppOffer(pageUrl: string) {
  return {
    "@type": "Offer" as const,
    price: 0,
    priceCurrency: "USD",
    url: pageUrl,
    availability: "https://schema.org/InStock",
    description: "Free ad-free Android app — no ads, no in-app advertising.",
  };
}

type AndroidSoftwareApplicationInput = {
  slug: string;
  title: string;
  description: string;
  category: string;
  pageUrl: string;
  packageId?: string;
  playStoreUrl?: string;
  githubUrl?: string;
  image?: string;
};

export function buildAndroidSoftwareApplicationNode(input: AndroidSoftwareApplicationInput) {
  const seo = getAppSeo(input.slug);
  const description =
    seo?.seoDescription ??
    `${input.description} Completely ad-free Android app — no ads.`;

  return {
    "@type": "SoftwareApplication" as const,
    additionalType: "https://schema.org/MobileApplication",
    "@id": `${input.pageUrl}#software`,
    name: input.title,
    alternateName: [
      input.packageId,
      `${input.title} ad-free Android app`,
      `${input.title} no ads`,
    ].filter(Boolean),
    description,
    applicationCategory: resolveApplicationCategory(input.slug, input.category),
    operatingSystem: "Android",
    url: input.pageUrl,
    image: input.image || undefined,
    isAccessibleForFree: true,
    offers: buildAndroidAppOffer(input.pageUrl),
    featureList: seo?.featureHighlights?.join(". "),
    keywords: seo?.keywords?.join(", "),
    author: {
      "@type": "Person" as const,
      name: site.name,
      url: site.origin,
    },
    publisher: {
      "@type": "Person" as const,
      name: site.name,
      url: site.origin,
    },
    sameAs: [input.playStoreUrl, input.githubUrl].filter(Boolean),
    downloadUrl: input.playStoreUrl || undefined,
    installUrl: input.playStoreUrl || undefined,
  };
}

export function buildAppMetadata(input: {
  slug: string;
  title: string;
  description: string;
  image?: string;
}): Metadata {
  const seo = getAppSeo(input.slug);
  const pageTitle = seo?.seoTitle ?? `${input.title} — Ad-Free Android App`;
  const description =
    seo?.seoDescription ??
    `${input.description} Completely ad-free Android app by Michael Samuel Naeem — no ads, no trackers.`;
  const canonical = absoluteUrl(`/apps/${input.slug}/`);
  const ogImage = input.image
    ? [{ url: input.image, alt: `${input.title} — ad-free Android app icon` }]
    : [{ url: "/og-image.png", width: 1200, height: 630, alt: pageTitle }];

  return {
    title: { absolute: pageTitle },
    description,
    keywords: seo?.keywords,
    authors: [{ name: site.name, url: site.origin }],
    creator: site.name,
    publisher: site.name,
    alternates: { canonical },
    openGraph: {
      title: pageTitle,
      description,
      url: canonical,
      siteName: site.shortName,
      locale: "en_US",
      type: "website",
      images: ogImage,
    },
    twitter: {
      card: "summary_large_image",
      title: pageTitle,
      description,
      creator: "@michaelsam94",
      images: input.image ? [input.image] : ["/og-image.png"],
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
}

export function buildAppJsonLd(input: {
  slug: string;
  title: string;
  description: string;
  category: string;
  packageId?: string;
  playStoreUrl?: string;
  githubUrl?: string;
  image?: string;
}) {
  const seo = getAppSeo(input.slug);
  const pageUrl = absoluteUrl(`/apps/${input.slug}/`);
  const description =
    seo?.seoDescription ??
    `${input.description} Completely ad-free Android app — no ads.`;
  const faqs = seo?.faqs ?? [
    {
      question: `Is ${input.title} ad-free?`,
      answer: `Yes. ${input.title} is completely ad-free — no banner ads, interstitial ads, or sponsored clutter.`,
    },
  ];

  return {
    "@context": "https://schema.org",
    "@graph": [
      buildAndroidSoftwareApplicationNode({
        slug: input.slug,
        title: input.title,
        description: input.description,
        category: input.category,
        pageUrl,
        packageId: input.packageId,
        playStoreUrl: input.playStoreUrl,
        githubUrl: input.githubUrl,
        image: input.image,
      }),
      {
        "@type": "WebPage",
        "@id": `${pageUrl}#webpage`,
        url: pageUrl,
        name: seo?.seoTitle ?? input.title,
        description,
        isPartOf: { "@id": `${site.origin}/#website` },
        about: { "@id": `${pageUrl}#software` },
        primaryImageOfPage: input.image || undefined,
        speakable: {
          "@type": "SpeakableSpecification",
          cssSelector: [".app-seo-answer", ".detail-title", ".hero-headline"],
        },
      },
      {
        "@type": "FAQPage",
        "@id": `${pageUrl}#faq`,
        mainEntity: faqs.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: {
            "@type": "Answer",
            text: item.answer,
          },
        })),
      },
      ...(seo?.howTo
        ? [
            {
              "@type": "HowTo",
              "@id": `${pageUrl}#howto`,
              name: seo.howTo.name,
              description: seo.howTo.description,
              image: input.image || undefined,
              totalTime: "PT2M",
              step: seo.howTo.steps.map((step, index) => ({
                "@type": "HowToStep",
                position: index + 1,
                name: step.name,
                text: step.text,
                url: `${pageUrl}#howto-step-${index + 1}`,
              })),
            },
          ]
        : []),
      {
        "@type": "BreadcrumbList",
        "@id": `${pageUrl}#breadcrumb`,
        itemListElement: [
          {
            "@type": "ListItem",
            position: 1,
            name: "Home",
            item: site.origin,
          },
          {
            "@type": "ListItem",
            position: 2,
            name: "Android Apps",
            item: absoluteUrl("/apps/"),
          },
          {
            "@type": "ListItem",
            position: 3,
            name: input.title,
            item: pageUrl,
          },
        ],
      },
    ],
  };
}
